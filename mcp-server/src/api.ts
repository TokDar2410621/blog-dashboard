/** Thin HTTP client for the Gridar REST API.
 *
 * Two transport modes feed into this client:
 *  - stdio: BLOG_DASHBOARD_TOKEN env var is read once at boot, used for every
 *    request. The legacy single-user pattern.
 *  - http : the token is provided per-request via AsyncLocalStorage by the
 *    HTTP server's auth middleware. Lets one hosted process serve many users.
 *
 * The env var stays as a fallback so stdio installs keep working unchanged.
 */
import { AsyncLocalStorage } from "node:async_hooks";

const API_BASE =
  process.env.BLOG_DASHBOARD_API_BASE || "https://api.gridar.app/api/v1";

const ENV_TOKEN = process.env.BLOG_DASHBOARD_TOKEN;

type RequestCtx = { token: string };
const requestStorage = new AsyncLocalStorage<RequestCtx>();

/** Run `fn` with a per-request token in scope. Used by the HTTP server. */
export function withRequestToken<T>(token: string, fn: () => T | Promise<T>): T | Promise<T> {
  return requestStorage.run({ token }, fn);
}

function getToken(): string {
  const stored = requestStorage.getStore()?.token;
  if (stored) return stored;
  if (ENV_TOKEN) return ENV_TOKEN;
  throw new ApiError(
    "Missing Bearer token. Set BLOG_DASHBOARD_TOKEN env var (stdio) or " +
      "pass Authorization: Bearer btb_xxx on the HTTP request.",
    401,
  );
}

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public body?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T = unknown>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const url = path.startsWith("http") ? path : `${API_BASE}${path}`;
  const headers = {
    Authorization: `Bearer ${getToken()}`,
    "Content-Type": "application/json",
    Accept: "application/json",
    "User-Agent": "@gridar/mcp-server/0.4.2",
    ...(init.headers as Record<string, string> | undefined),
  };

  const res = await fetch(url, { ...init, headers });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new ApiError(
      (body as { error?: string }).error ||
        `HTTP ${res.status} on ${path}`,
      res.status,
      body,
    );
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

// ---------------------------------------------------------------------------
// Typed wrappers for the endpoints we expose as MCP tools.
// ---------------------------------------------------------------------------

export async function getMe() {
  return request<{
    username: string;
    email: string;
    plan: string;
    rate_limit_per_hour: number;
    usage: {
      articles_this_month: number;
      articles_per_month_limit: number | null;
      month_key: string;
    };
  }>("/me/");
}

export async function listSites() {
  return request<{
    results: {
      id: number;
      name: string;
      domain: string;
      is_hosted: boolean;
      is_wordpress: boolean;
      default_language: string;
      available_languages: string[];
    }[];
  }>("/sites/");
}

export async function listArticles(
  siteId: number,
  opts: { status?: string; language?: string; limit?: number } = {},
) {
  const qs = new URLSearchParams();
  if (opts.status) qs.set("status", opts.status);
  if (opts.language) qs.set("language", opts.language);
  if (opts.limit) qs.set("limit", String(opts.limit));
  const suffix = qs.toString() ? `?${qs}` : "";
  return request<{
    results: {
      slug: string;
      title: string;
      excerpt: string;
      status: string;
      language: string;
      published_at: string | null;
      view_count: number;
    }[];
  }>(`/sites/${siteId}/articles/${suffix}`);
}

export async function getArticle(siteId: number, slug: string) {
  return request<{
    slug: string;
    title: string;
    excerpt: string;
    content: string;
    cover_image: string;
    language: string;
    status: string;
    published_at: string | null;
    updated_at: string | null;
  }>(`/sites/${siteId}/articles/${encodeURIComponent(slug)}/`);
}

export async function generateArticle(
  siteId: number,
  body: {
    topic?: string;
    title?: string;
    type?: "guide" | "news" | "tutorial" | "comparison" | "review" | "story" | "local";
    length?: "short" | "medium" | "long";
    language?: "fr" | "en" | "es";
    keywords?: string;
    brief?: Record<string, unknown>;
  },
) {
  return request<{ output: string; post_count: number }>(
    `/sites/${siteId}/generate/`,
    { method: "POST", body: JSON.stringify(body) },
  );
}

export async function auditArticle(body: {
  title: string;
  excerpt?: string;
  content: string;
  keyword?: string;
  language?: string;
}) {
  return request<{ score: number; suggestions: unknown[]; cache_hit: boolean }>(
    "/audit/",
    { method: "POST", body: JSON.stringify(body) },
  );
}

export async function getBrief(body: { keyword: string; language?: string }) {
  return request<{
    intent: string;
    outline: { level: number; text: string }[];
    entities: string[];
    faq: { question: string; answer: string }[];
    eeat_signals: string[];
  }>("/brief/", { method: "POST", body: JSON.stringify(body) });
}

export async function listKeywords(siteId: number) {
  return request<{
    results: {
      id: number;
      keyword: string;
      language: string;
      target_url: string;
      latest_position: number | null;
      latest_recorded_at: string | null;
    }[];
  }>(`/sites/${siteId}/keywords/`);
}

export async function snapshotKeywords(siteId: number) {
  return request<{ ok: boolean; count: number }>(
    `/sites/${siteId}/keywords/snapshot/`,
    { method: "POST" },
  );
}

export async function getWeeklyDigest(siteId: number) {
  return request<{
    site_id: number;
    period_start: string;
    period_end: string;
    summary: Record<string, unknown>;
  }>(`/sites/${siteId}/digest/weekly/`);
}

// ---------------------------------------------------------------------------
// Extended wrappers (0.2 / proof loop + full surface)
// ---------------------------------------------------------------------------

export async function getSiteDetail(siteId: number) {
  return request<Record<string, unknown>>(`/sites/${siteId}/detail/`);
}

export async function updateSite(siteId: number, fields: Record<string, unknown>) {
  return request<{ updated_fields: string[]; site_id: number }>(
    `/sites/${siteId}/update/`,
    { method: "PATCH", body: JSON.stringify(fields) },
  );
}

export async function createManualArticle(
  siteId: number,
  body: {
    title: string;
    content: string;
    excerpt?: string;
    slug?: string;
    status?: "draft" | "published" | "scheduled";
    author?: string;
    language?: "fr" | "en" | "es";
    cover_image?: string;
  },
) {
  return request<{ slug: string; id: number; status: string }>(
    `/sites/${siteId}/articles/manual/`,
    { method: "POST", body: JSON.stringify(body) },
  );
}

export async function updateArticle(
  siteId: number,
  slug: string,
  fields: Record<string, unknown>,
) {
  return request<{ updated_fields: string[]; slug: string }>(
    `/sites/${siteId}/articles/${encodeURIComponent(slug)}/manual/`,
    { method: "PATCH", body: JSON.stringify(fields) },
  );
}

export async function deleteArticle(siteId: number, slug: string) {
  return request<void>(
    `/sites/${siteId}/articles/${encodeURIComponent(slug)}/manual/`,
    { method: "DELETE" },
  );
}

export async function trackKeyword(
  siteId: number,
  body: { keyword: string; language?: "fr" | "en" | "es"; target_url?: string },
) {
  return request<{ id: number; keyword: string; language: string; reactivated?: boolean }>(
    `/sites/${siteId}/keywords/track/`,
    { method: "POST", body: JSON.stringify(body) },
  );
}

export async function untrackKeyword(siteId: number, keywordId: number) {
  return request<void>(
    `/sites/${siteId}/keywords/${keywordId}/untrack/`,
    { method: "DELETE" },
  );
}

export async function analyzeCompetitors(body: {
  keyword: string;
  language?: "fr" | "en" | "es";
}) {
  return request<Record<string, unknown>>(`/competitors/`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function getContentDecay(siteId: number, days = 30) {
  return request<Record<string, unknown>>(
    `/sites/${siteId}/content-decay/?days=${days}`,
  );
}

export async function getBrokenLinks(siteId: number) {
  return request<Record<string, unknown>>(`/sites/${siteId}/broken-links/`);
}

export async function checkHreflang(body: { site_id?: number; html?: string }) {
  return request<Record<string, unknown>>(`/hreflang-check/`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function detectCannibalization(siteId: number) {
  return request<Record<string, unknown>>(`/sites/${siteId}/cannibalization/`);
}

export async function suggestInternalLinks(
  siteId: number,
  body: { article_slug?: string; content?: string; keyword?: string },
) {
  return request<Record<string, unknown>>(
    `/sites/${siteId}/link-suggestions/`,
    { method: "POST", body: JSON.stringify(body) },
  );
}

export async function bulkAudit(siteId: number) {
  return request<Record<string, unknown>>(`/sites/${siteId}/audit-all/`);
}

export async function checkReadability(body: { content: string; language?: string }) {
  return request<Record<string, unknown>>(`/readability/`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function checkPlagiarism(body: { content: string }) {
  return request<Record<string, unknown>>(`/plagiarism/`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function getGscQueries(siteId: number, days = 28, limit = 50) {
  return request<Record<string, unknown>>(
    `/sites/${siteId}/gsc-queries/?days=${days}&limit=${limit}`,
  );
}

export async function getAutopilotConfig(siteId: number) {
  return request<Record<string, unknown>>(`/sites/${siteId}/autopilot/`);
}

export async function setAutopilotConfig(
  siteId: number,
  body: {
    enabled?: boolean;
    weekly_count?: number;
    auto_publish?: boolean;
  },
) {
  return request<Record<string, unknown>>(`/sites/${siteId}/autopilot/`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function runAutopilotNow(siteId: number) {
  return request<Record<string, unknown>>(
    `/sites/${siteId}/autopilot/run/`,
    { method: "POST" },
  );
}

export async function listMemories(siteId: number) {
  return request<Record<string, unknown>>(`/sites/${siteId}/memories/`);
}

export async function addMemory(
  siteId: number,
  body: { content: string; title?: string; kind?: string },
) {
  return request<Record<string, unknown>>(`/sites/${siteId}/memories/`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function deleteMemory(siteId: number, memoryId: number) {
  return request<void>(
    `/sites/${siteId}/memories/${memoryId}/`,
    { method: "DELETE" },
  );
}

export async function rebuildMemory(siteId: number) {
  return request<Record<string, unknown>>(
    `/sites/${siteId}/memories/rebuild/`,
    { method: "POST" },
  );
}

export async function getProofSummary(siteId: number) {
  return request<Record<string, unknown>>(`/sites/${siteId}/proof/summary/`);
}

export async function getProofAttribution(siteId: number, postId?: number) {
  const q = postId ? `?post=${postId}` : "";
  return request<Record<string, unknown>>(
    `/sites/${siteId}/proof/attribution/${q}`,
  );
}

export async function enableProofShare(siteId: number, rotate = false) {
  return request<Record<string, unknown>>(
    `/sites/${siteId}/proof/share/`,
    { method: "POST", body: JSON.stringify({ rotate }) },
  );
}

export async function revokeProofShare(siteId: number) {
  return request<Record<string, unknown>>(
    `/sites/${siteId}/proof/share/`,
    { method: "DELETE" },
  );
}

export async function suggestKeywords(siteId: number, body?: Record<string, unknown>) {
  return request<Record<string, unknown>>(
    `/sites/${siteId}/suggest-keywords/`,
    { method: "POST", body: JSON.stringify(body ?? {}) },
  );
}

export async function suggestCompetitors(siteId: number, body?: Record<string, unknown>) {
  return request<Record<string, unknown>>(
    `/sites/${siteId}/suggest-competitors/`,
    { method: "POST", body: JSON.stringify(body ?? {}) },
  );
}

export async function keywordResearch(body: {
  seed?: string;
  language?: "fr" | "en" | "es";
  country?: string;
}) {
  return request<Record<string, unknown>>(`/keyword-research/`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function pageSpeed(body: { url: string; strategy?: "mobile" | "desktop" }) {
  return request<Record<string, unknown>>(`/page-speed/`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function peopleAlsoAsk(body: {
  keyword: string;
  language?: "fr" | "en" | "es";
}) {
  return request<Record<string, unknown>>(`/paa/`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}
