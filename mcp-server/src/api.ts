/** Thin HTTP client for the Blog Dashboard REST API. */

const API_BASE =
  process.env.BLOG_DASHBOARD_API_BASE || "https://api.blog-dashboard.ca/api/v1";

const TOKEN = process.env.BLOG_DASHBOARD_TOKEN;

if (!TOKEN) {
  // eslint-disable-next-line no-console
  console.error(
    "[gridar-mcp] BLOG_DASHBOARD_TOKEN env var is required.\n" +
      "Generate one at https://blog-dashboard-ebon.vercel.app/account/api-keys " +
      "and pass it via your MCP client config (e.g. Claude Desktop config.json)."
  );
  process.exit(1);
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
    Authorization: `Bearer ${TOKEN}`,
    "Content-Type": "application/json",
    Accept: "application/json",
    "User-Agent": "@gridar/mcp-server/0.1.0",
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
