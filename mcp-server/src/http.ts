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
import { randomUUID } from "node:crypto";
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
    version: "0.3.2",
    transport: "streamable-http",
  });
});

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
    res.status(401).json({
      jsonrpc: "2.0",
      error: {
        code: -32001,
        message:
          "Unauthorized: missing Bearer token. Pass Authorization: Bearer btb_xxx (your Gridar API token).",
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
