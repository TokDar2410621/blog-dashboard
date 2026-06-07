#!/usr/bin/env node
/**
 * Gridar MCP server - HTTP transport (Streamable HTTP).
 *
 * Same 43 tools as the stdio entry, but hosted as an HTTP service so MCP
 * clients (Claude Desktop, Claude Code, Cursor, Codex) can connect via URL
 * instead of installing the npm package locally.
 *
 *   - POST /mcp           : MCP Streamable HTTP transport (initialize +
 *                           tool calls). Optional GET/DELETE for SSE.
 *   - GET  /health        : healthcheck for Railway.
 *
 * Auth: every request must carry `Authorization: Bearer btb_xxx` (the
 * user's Gridar API token). The token is propagated to api.ts via
 * AsyncLocalStorage so a single hosted process serves many users without
 * leaking tokens across requests.
 *
 * Deploy:
 *   npm run build && node dist/http.js
 *   or set start command to `node dist/http.js` on Railway.
 *
 * Required env vars:
 *   PORT                       (Railway auto-sets this)
 *   BLOG_DASHBOARD_API_BASE    (defaults to https://api.gridar.app/api/v1)
 *
 * Optional:
 *   MCP_REQUIRE_AUTH=false     skip Bearer enforcement (dev only)
 *   MCP_ALLOWED_ORIGINS=*      CSV of allowed origins for CORS
 */
import { createHash, randomUUID } from "node:crypto";
import express, { type Request, type Response } from "express";
import { isInitializeRequest } from "@modelcontextprotocol/sdk/types.js";
import { StreamableHTTPServerTransport } from "@modelcontextprotocol/sdk/server/streamableHttp.js";
import { createMcpServer } from "./index.js";
import { withRequestToken } from "./api.js";

const PORT = Number(process.env.PORT ?? 8080);
const REQUIRE_AUTH = process.env.MCP_REQUIRE_AUTH !== "false";
const ALLOWED_ORIGINS = (process.env.MCP_ALLOWED_ORIGINS ?? "*")
  .split(",")
  .map((s) => s.trim())
  .filter(Boolean);

// OAuth configuration. Public base = the URL clients hit. Gridar base = the
// dashboard that owns the user accounts.
const PUBLIC_BASE = (
  process.env.MCP_PUBLIC_BASE ?? `http://localhost:${PORT}`
).replace(/\/$/, "");
const GRIDAR_BASE = (
  process.env.GRIDAR_BASE ?? "https://gridar.app"
).replace(/\/$/, "");
const OAUTH_CODE_TTL_MS = 5 * 60 * 1000; // 5 minutes

// Static OAuth client credentials. MCP clients that auto-register via RFC 7591
// receive these (always the same pair). Claude Code stores them in its
// keychain and uses them on subsequent /token requests. PKCE still protects
// the authorization code; the client_secret is purely a "this is a registered
// client" signal that some clients (Claude Code in particular) refuse to
// proceed without. Reference: obsidian-mcp does the same.
const OAUTH_CLIENT_ID =
  process.env.OAUTH_CLIENT_ID ?? "gridar-mcp-public";
const OAUTH_CLIENT_SECRET =
  process.env.OAUTH_CLIENT_SECRET ?? "gridar-mcp-public-secret";

const app = express();
app.use(express.json({ limit: "4mb" }));

// CORS - clients connect from various MCP hosts (browser, desktop). Be liberal
// on Origin but block credentials so cookies can't leak from third parties.
app.use((req, res, next) => {
  const origin = (req.headers.origin as string | undefined) ?? "*";
  const allowed =
    ALLOWED_ORIGINS.includes("*") || ALLOWED_ORIGINS.includes(origin);
  res.setHeader("Access-Control-Allow-Origin", allowed ? origin : "");
  res.setHeader(
    "Access-Control-Allow-Methods",
    "GET, POST, DELETE, OPTIONS",
  );
  res.setHeader(
    "Access-Control-Allow-Headers",
    "Content-Type, Authorization, Mcp-Session-Id, MCP-Protocol-Version",
  );
  res.setHeader(
    "Access-Control-Expose-Headers",
    "Mcp-Session-Id",
  );
  if (req.method === "OPTIONS") {
    res.status(204).end();
    return;
  }
  next();
});

app.get("/health", (_req, res) => {
  res.json({
    status: "ok",
    name: "gridar-mcp",
    version: "0.4.2",
    transport: "streamable-http",
    oauth: true,
  });
});

// ---------------------------------------------------------------------------
// OAuth 2.1 (PKCE) - MCP authorization flow
// ---------------------------------------------------------------------------
//
// Flow:
//   1. MCP client (Claude Desktop / Code / Cursor) discovers the OAuth metadata
//      via GET /.well-known/oauth-authorization-server.
//   2. Client opens GET /authorize?response_type=code&client_id=...&
//      redirect_uri=...&code_challenge=...&state=... in the user's browser.
//   3. We register a "pending grant" keyed by an opaque session_id and redirect
//      the user to gridar.app/oauth/mcp-authorize?session_id=...&return_to=...
//   4. The Gridar dashboard authenticates the user (JWT cookie), mints a
//      Bearer ApiToken via POST /api/auth/issue-mcp-token/, and redirects back
//      to OUR /callback?session_id=...&access_token=btb_xxx.
//   5. /callback looks up the pending grant, mints an opaque auth code, stores
//      `code -> { access_token, code_challenge, ... }`, and redirects the
//      user's browser to the MCP client's original redirect_uri with
//      ?code=...&state=...
//   6. The MCP client POSTs /token with the code + PKCE verifier. We verify
//      the verifier matches the original challenge, return the access_token
//      as a standard OAuth response, and discard the code.
//
// Storage is in-memory (Map). On Railway with a single replica that's fine.
// If we ever scale horizontally, swap for Redis with a 5min TTL.

type PendingGrant = {
  client_id: string;
  redirect_uri: string;
  code_challenge: string;
  code_challenge_method: "S256" | "plain";
  state: string;
  scope?: string;
  client_name: string;
  created_at: number;
};

type IssuedCode = {
  access_token: string;
  code_challenge: string;
  code_challenge_method: "S256" | "plain";
  redirect_uri: string;
  client_id: string;
  expires_at: number;
};

const pendingGrants = new Map<string, PendingGrant>();
const issuedCodes = new Map<string, IssuedCode>();

function verifyPkce(verifier: string, challenge: string, method: "S256" | "plain"): boolean {
  if (method === "plain") return verifier === challenge;
  const expected = createHash("sha256")
    .update(verifier)
    .digest("base64url");
  return expected === challenge;
}

function gcExpired() {
  const now = Date.now();
  for (const [k, v] of pendingGrants) {
    if (v.created_at + OAUTH_CODE_TTL_MS < now) pendingGrants.delete(k);
  }
  for (const [k, v] of issuedCodes) {
    if (v.expires_at < now) issuedCodes.delete(k);
  }
}

// 5.1 - Authorization server metadata (RFC 8414)
app.get("/.well-known/oauth-authorization-server", (_req, res) => {
  res.json({
    issuer: PUBLIC_BASE,
    authorization_endpoint: `${PUBLIC_BASE}/authorize`,
    token_endpoint: `${PUBLIC_BASE}/token`,
    registration_endpoint: `${PUBLIC_BASE}/register`,
    response_types_supported: ["code"],
    grant_types_supported: ["authorization_code"],
    code_challenge_methods_supported: ["S256", "plain"],
    // Both methods supported. client_secret_post matches what Claude Code
    // expects (obsidian-mcp uses the same), while `none` keeps PKCE-only
    // public clients (Continue.dev, MCP Inspector, ...) working.
    token_endpoint_auth_methods_supported: ["client_secret_post", "none"],
    scopes_supported: ["mcp:full"],
    service_documentation: "https://gridar.app/docs/integrations",
  });
});

// 5.1b - Dynamic Client Registration (RFC 7591). Returns the static
// OAuth_CLIENT_ID / OAUTH_CLIENT_SECRET pair so MCP clients (Claude Code,
// Cursor, Codex) can complete their OAuth handshake. Same pattern as
// obsidian-mcp: the DCR ritual is observed but the credentials are static.
// The real security is the user-side consent + PKCE, not per-client secrets.
app.post("/register", express.json(), (req, res) => {
  const body = (req.body ?? {}) as Record<string, unknown>;
  const redirect_uris = Array.isArray(body.redirect_uris)
    ? (body.redirect_uris as string[]).filter(
        (u) => typeof u === "string" && u.length > 0,
      )
    : [];
  if (!redirect_uris.length) {
    res.status(400).json({
      error: "invalid_client_metadata",
      error_description:
        "redirect_uris must be provided as a non-empty array of strings",
    });
    return;
  }
  const client_name =
    (typeof body.client_name === "string" && body.client_name) || "MCP client";

  res.status(201).json({
    client_id: OAUTH_CLIENT_ID,
    client_secret: OAUTH_CLIENT_SECRET,
    client_id_issued_at: Math.floor(Date.now() / 1000),
    client_name,
    redirect_uris,
    grant_types: ["authorization_code"],
    response_types: ["code"],
    token_endpoint_auth_method: "client_secret_post",
    scope: "mcp:full",
  });
});

// 5.2 - Protected resource metadata (RFC 9728)
app.get("/.well-known/oauth-protected-resource", (_req, res) => {
  res.json({
    resource: PUBLIC_BASE,
    authorization_servers: [PUBLIC_BASE],
    scopes_supported: ["mcp:full"],
    bearer_methods_supported: ["header"],
  });
});

// 5.3 - /authorize: redirect the user to gridar.app for login
app.get("/authorize", (req, res) => {
  gcExpired();
  const {
    response_type,
    client_id,
    redirect_uri,
    code_challenge,
    code_challenge_method = "S256",
    state = "",
    scope = "mcp:full",
  } = req.query as Record<string, string>;

  if (response_type !== "code") {
    res.status(400).send("unsupported_response_type");
    return;
  }
  if (!redirect_uri || !code_challenge) {
    res.status(400).send("invalid_request: redirect_uri and code_challenge required");
    return;
  }
  if (code_challenge_method !== "S256" && code_challenge_method !== "plain") {
    res.status(400).send("invalid_request: code_challenge_method must be S256 or plain");
    return;
  }

  // Try to infer a friendly client name from the user-agent or query.
  const ua = (req.header("user-agent") ?? "").toLowerCase();
  let client_name = (req.query.client_name as string) || "MCP client";
  if (!req.query.client_name) {
    if (ua.includes("claude") && ua.includes("desktop")) client_name = "Claude Desktop";
    else if (ua.includes("claude")) client_name = "Claude Code";
    else if (ua.includes("cursor")) client_name = "Cursor";
    else if (ua.includes("codex")) client_name = "Codex CLI";
  }

  const session_id = randomUUID();
  pendingGrants.set(session_id, {
    client_id: client_id ?? "mcp-public",
    redirect_uri,
    code_challenge,
    code_challenge_method: code_challenge_method as "S256" | "plain",
    state,
    scope,
    client_name,
    created_at: Date.now(),
  });

  const returnTo = encodeURIComponent(`${PUBLIC_BASE}/callback`);
  const url = `${GRIDAR_BASE}/oauth/mcp-authorize?session_id=${session_id}&client_name=${encodeURIComponent(client_name)}&return_to=${returnTo}`;
  res.redirect(url);
});

// 5.4 - /callback: Gridar bridge redirects here with the freshly issued
//        ApiToken. We mint an OAuth code mapped to that token and redirect
//        the user's browser back to the MCP client's redirect_uri.
app.get("/callback", (req, res) => {
  gcExpired();
  const session_id = (req.query.session_id as string) ?? "";
  const access_token = (req.query.access_token as string) ?? "";
  const pending = session_id ? pendingGrants.get(session_id) : undefined;
  if (!pending) {
    res.status(400).send("invalid_or_expired_session");
    return;
  }
  if (!access_token.startsWith("btb_")) {
    res.status(400).send("invalid_access_token_format");
    return;
  }
  pendingGrants.delete(session_id);

  const code = randomUUID().replace(/-/g, "");
  issuedCodes.set(code, {
    access_token,
    code_challenge: pending.code_challenge,
    code_challenge_method: pending.code_challenge_method,
    redirect_uri: pending.redirect_uri,
    client_id: pending.client_id,
    expires_at: Date.now() + OAUTH_CODE_TTL_MS,
  });

  const target = new URL(pending.redirect_uri);
  target.searchParams.set("code", code);
  if (pending.state) target.searchParams.set("state", pending.state);
  res.redirect(target.toString());
});

// 5.5 - /token: exchange code (+ PKCE verifier) for the access token.
// Accepts both client_secret_post (validates the static secret if present)
// and `none` (PKCE-only). PKCE itself is always required and is the actual
// security barrier.
app.post(
  "/token",
  express.urlencoded({ extended: false }),
  (req, res) => {
    gcExpired();
    const body = (req.body ?? {}) as Record<string, string>;
    const {
      grant_type,
      code,
      redirect_uri,
      code_verifier,
      client_id,
      client_secret,
    } = body;

    if (grant_type !== "authorization_code") {
      res.status(400).json({ error: "unsupported_grant_type" });
      return;
    }
    if (!code || !code_verifier) {
      res.status(400).json({ error: "invalid_request" });
      return;
    }
    // If the client sent a secret, it must match the static one we issued
    // at /register. If it didn't, we accept (public client, PKCE-only path).
    if (client_secret !== undefined && client_secret !== OAUTH_CLIENT_SECRET) {
      res.status(401).json({
        error: "invalid_client",
        error_description: "client_secret does not match",
      });
      return;
    }
    if (client_id && client_id !== OAUTH_CLIENT_ID) {
      // Only check static match if the client identified itself. Don't reject
      // public clients that omit client_id (legacy MCP clients).
      res.status(400).json({ error: "invalid_client" });
      return;
    }
    const entry = issuedCodes.get(code);
    if (!entry) {
      res.status(400).json({ error: "invalid_grant" });
      return;
    }
    issuedCodes.delete(code);
    if (entry.expires_at < Date.now()) {
      res.status(400).json({ error: "invalid_grant", error_description: "code expired" });
      return;
    }
    if (entry.redirect_uri !== redirect_uri) {
      res.status(400).json({ error: "invalid_grant", error_description: "redirect_uri mismatch" });
      return;
    }
    if (!verifyPkce(code_verifier, entry.code_challenge, entry.code_challenge_method)) {
      res.status(400).json({ error: "invalid_grant", error_description: "PKCE verification failed" });
      return;
    }

    res.json({
      access_token: entry.access_token,
      token_type: "Bearer",
      scope: "mcp:full",
    });
  },
);

// Per-session transports. Streamable HTTP is stateful: the client gets a
// session ID at initialize, then includes it on every subsequent request.
const sessions = new Map<string, StreamableHTTPServerTransport>();

function extractBearer(req: Request): string | null {
  const auth = req.header("authorization");
  if (!auth?.toLowerCase().startsWith("bearer ")) return null;
  const token = auth.slice(7).trim();
  return token.length > 0 ? token : null;
}

async function dispatch(
  req: Request,
  res: Response,
  body: unknown,
): Promise<void> {
  const token = extractBearer(req);
  if (REQUIRE_AUTH && !token) {
    // MCP clients discover OAuth via the WWW-Authenticate challenge.
    res.setHeader(
      "WWW-Authenticate",
      `Bearer realm="gridar-mcp", resource_metadata="${PUBLIC_BASE}/.well-known/oauth-protected-resource"`,
    );
    res.status(401).json({
      jsonrpc: "2.0",
      error: {
        code: -32001,
        message:
          "Unauthorized: missing Bearer token. Either pass Authorization: Bearer btb_xxx, or let your MCP client perform the OAuth flow at " +
          PUBLIC_BASE +
          "/authorize",
      },
      id: null,
    });
    return;
  }

  const sessionId = req.header("mcp-session-id") ?? undefined;
  let transport = sessionId ? sessions.get(sessionId) : undefined;

  if (!transport) {
    if (!isInitializeRequest(body)) {
      res.status(400).json({
        jsonrpc: "2.0",
        error: {
          code: -32000,
          message:
            "Bad Request: No valid Mcp-Session-Id header and not an initialize request.",
        },
        id: null,
      });
      return;
    }
    transport = new StreamableHTTPServerTransport({
      sessionIdGenerator: () => randomUUID(),
      onsessioninitialized: (id) => {
        sessions.set(id, transport!);
      },
    });
    transport.onclose = () => {
      if (transport!.sessionId) sessions.delete(transport!.sessionId);
    };
    const server = createMcpServer();
    await server.connect(transport);
  }

  // Wrap the actual handle in AsyncLocalStorage so api.ts picks up the user's
  // Bearer token without us touching every tool handler.
  await withRequestToken(token ?? "", () =>
    transport!.handleRequest(req, res, body),
  );
}

app.post("/mcp", async (req, res) => {
  try {
    await dispatch(req, res, req.body);
  } catch (err) {
    // eslint-disable-next-line no-console
    console.error("[gridar-mcp] /mcp POST error:", err);
    if (!res.headersSent) {
      res.status(500).json({
        jsonrpc: "2.0",
        error: { code: -32603, message: "Internal error" },
        id: null,
      });
    }
  }
});

app.get("/mcp", async (req, res) => {
  // SSE notifications stream - same auth + session lookup, no body parse.
  try {
    await dispatch(req, res, undefined);
  } catch (err) {
    // eslint-disable-next-line no-console
    console.error("[gridar-mcp] /mcp GET error:", err);
    if (!res.headersSent) res.status(500).end();
  }
});

app.delete("/mcp", async (req, res) => {
  // Explicit session teardown from the client.
  try {
    await dispatch(req, res, undefined);
  } catch (err) {
    // eslint-disable-next-line no-console
    console.error("[gridar-mcp] /mcp DELETE error:", err);
    if (!res.headersSent) res.status(500).end();
  }
});

app.listen(PORT, "0.0.0.0", () => {
  // eslint-disable-next-line no-console
  console.error(
    `[gridar-mcp] HTTP server listening on :${PORT} (auth=${REQUIRE_AUTH ? "on" : "off"})`,
  );
});
