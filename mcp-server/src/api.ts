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
    "User-Agent": "@gridar/mcp-server/0.7.0",
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

export async function generateSisterArticle(
  siteId: number,
  sourceSlug: string,
  body: { target_language: "fr" | "en" | "es" },
) {
  return request<{
    slug: string;
    id: number;
    language: string;
    translation_group: string;
    status: string;
    title: string;
  }>(
    `/sites/${siteId}/articles/${encodeURIComponent(sourceSlug)}/generate-sister-article/`,
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

export async function serpAnalyze(
  siteId: number,
  body: { keyword: string; language?: "fr" | "en" | "es" },
) {
  return request<{
    keyword: string;
    language: string;
    top_10: {
      position: number;
      url: string;
      domain: string;
      title: string;
      snippet: string;
      word_count: number | null;
      headings_count: number | null;
      has_faq: boolean;
      has_video: boolean;
      fetch_error: boolean;
    }[];
    averages: {
      word_count_avg: number;
      headings_avg: number;
      faq_pct: number;
      video_pct: number;
    };
  }>(`/sites/${siteId}/serp-analyze/`, {
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

export async function getGscQueries(
  siteId: number,
  slug: string,
  days = 28,
  limit = 50,
) {
  // Backend (GSCQueriesView) requires `slug` — it filters GSC rows to the
  // single article page URL (property URL + slug). Without it the API 400s
  // with "slug is required." `limit` is accepted but ignored server-side
  // (rowLimit is hardcoded to 25); kept for forward-compat.
  return request<Record<string, unknown>>(
    `/sites/${siteId}/gsc-queries/?slug=${encodeURIComponent(slug)}&days=${days}&limit=${limit}`,
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
  // Backend (KeywordResearchView) reads `seed_keyword` + `language` from the
  // POST body. The tool exposes the nicer `seed` alias, so remap it here or
  // the seed never reaches the server ("Le mot-cle de depart est requis").
  // `country` is not consumed server-side, so it is intentionally dropped.
  return request<Record<string, unknown>>(`/keyword-research/`, {
    method: "POST",
    body: JSON.stringify({
      seed_keyword: body.seed,
      language: body.language,
    }),
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

// ---------------------------------------------------------------------------
// Topic Cluster Planner (0.5.0)
// ---------------------------------------------------------------------------

export async function classifyIntent(body: {
  keyword: string;
  site_id?: number;
}) {
  return request<{
    keyword: string;
    intent: "transactional" | "commercial" | "informational" | "navigational" | "local";
    confidence: number;
    navigational_match: boolean;
  }>(`/classify-intent/`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function proposeKeywordStrategy(
  siteId: number,
  body: { keyword: string; language?: "fr" | "en" | "es" },
) {
  return request<{
    id: number;
    site_id: number;
    keyword: string;
    intent: string;
    intent_confidence: number;
    proposed_structure: string;
    proposed_pages: unknown[];
    rationale: string;
    status: string;
    created: boolean;
  }>(`/sites/${siteId}/keyword-strategy/`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function approveStrategy(
  siteId: number,
  strategyId: number,
  body: { customizations?: Record<string, unknown> } = {},
) {
  return request<{
    id: number;
    status: string;
    generated_landings: number[];
    planned_articles: unknown[];
    errors: unknown[];
  }>(`/sites/${siteId}/keyword-strategy/${strategyId}/approve/`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function createLanding(
  siteId: number,
  body: {
    title: string;
    h1?: string;
    slug?: string;
    hero_subtitle?: string;
    hero_cta_text?: string;
    hero_cta_url?: string;
    value_props?: unknown[];
    social_proof?: unknown[];
    faq?: unknown[];
    cta_bottom_text?: string;
    cta_bottom_url?: string;
    body_markdown?: string;
    target_keyword?: string;
    schema_type?: string;
    page_subtype?: string;
    language?: "fr" | "en" | "es";
    status?: "draft" | "published";
    cover_image?: string;
    meta_description?: string;
  },
) {
  return request<{ id: number; slug: string; status: string }>(
    `/sites/${siteId}/landings/manual/`,
    { method: "POST", body: JSON.stringify(body) },
  );
}

export async function generateLanding(
  siteId: number,
  body: {
    keyword: string;
    primary_cta_text?: string;
    primary_cta_url?: string;
    value_props?: unknown[];
    page_subtype?: "service" | "product" | "pillar" | "comparison" | "local";
    language?: "fr" | "en" | "es";
  },
) {
  return request<{
    id: number;
    slug: string;
    title: string;
    h1: string;
    status: string;
    page_subtype: string;
  }>(`/sites/${siteId}/landings/generate/`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function linkPages(
  siteId: number,
  body: {
    source_slug: string;
    target_slug: string;
    anchor_text: string;
  },
) {
  return request<{
    status: string;
    source_slug: string;
    source_type?: string;
    target_slug: string;
    target_type?: string;
    anchor_text?: string;
    inserted_inline?: boolean;
  }>(`/sites/${siteId}/link-pages/`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function siteSeoScore(siteId: number) {
  return request<{
    score: number;
    breakdown: {
      indexability: boolean;
      author_bio_filled: boolean;
      business_model_declared: boolean;
      gsc_connected: boolean;
      has_cluster: boolean;
      hreflang_valid: boolean;
      cwv_ok: number | boolean;
      faq_coverage: number;
      no_transactional_blog: boolean;
    };
    action_items: { issue: string; fix_url: string }[];
  }>(`/sites/${siteId}/seo-score/`);
}

export async function aiOverviewReadiness(siteId: number, slug: string) {
  return request<{
    score: number;
    breakdown: {
      faq_density: number;
      h2_h3_structure: boolean;
      eeat_signals: number;
      concrete_data: number;
      extractible_quotes: number;
    };
    suggestions: string[];
  }>(
    `/sites/${siteId}/articles/${encodeURIComponent(slug)}/ai-overview-readiness/`,
  );
}

export async function checkRenderability(body: { url: string }) {
  return request<{
    url: string;
    is_prerendered: boolean;
    html_contains_main_text: boolean;
    word_count: number;
    warning: string;
    suggestion: string;
  }>(`/check-renderability/`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function linkOpportunities(body: {
  keyword: string;
  language?: "fr" | "en" | "es";
}) {
  return request<{
    keyword: string;
    language: string;
    targets: {
      domain: string;
      url: string;
      title: string;
      snippet: string;
      source_query: string;
    }[];
    count: number;
  }>(`/link-opportunities/`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

// ---------------------------------------------------------------------------
// AI Visibility tracking (2026-06-08)
// ---------------------------------------------------------------------------

export type AiVisibilityEngine =
  | "chatgpt"
  | "perplexity"
  | "gemini"
  | "searchgpt"
  | "claude";

export async function aiVisibilitySummary(siteId: number) {
  return request<{
    score: number;
    total_mentions: number;
    cited_pages_count: number;
    total_checks: number;
    total_prompts: number;
    breakdown_by_engine: Record<
      AiVisibilityEngine,
      { total_checks: number; cited_count: number; cite_rate: number }
    >;
    delta_7d: number;
  }>(`/sites/${siteId}/ai-visibility/summary/`);
}

export async function runAiVisibility(
  siteId: number,
  body: { prompt_id?: number } = {},
) {
  return request<{
    checks_run: number;
    prompts_checked: number;
    engines_per_prompt: number;
    results: {
      id: number;
      prompt_id: number;
      engine: AiVisibilityEngine;
      is_cited: boolean;
      citation_url: string | null;
      citation_rank: number | null;
      checked_at: string;
    }[];
    mocked: boolean;
    note: string;
  }>(`/sites/${siteId}/ai-visibility/run/`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

// ---------------------------------------------------------------------------
// Strategic Opportunities (2026-06-09)
// ---------------------------------------------------------------------------
//
// For each non-info-intent tracked keyword without a matching landing, the
// backend engine produces a structured page concept tied to the site's
// existing assets and a quantitative traffic + lead estimate. Approving an
// opportunity generates the matching HostedLanding via the LandingGenerator.

export type StrategicOpportunityConcept = {
  page_concept: string;
  page_type: string;
  suggested_title: string;
  suggested_url_path: string;
  hook: string;
  capture_mechanism: string;
  conversion_path: string;
  angle: string;
  asset_match: boolean;
  asset_used: string | null;
  why_this_works: string;
  priority?: "high" | "medium" | "low";
};

export type StrategicOpportunityEstimate = {
  monthly_volume: number;
  target_position: number;
  estimated_visits: number;
  estimated_leads_range: [number, number];
  estimated_paid_range: [number, number];
  qualitative_traffic: string;
};

export type StrategicOpportunity = {
  id: number;
  keyword: string;
  intent: "info" | "commercial" | "transactional" | "local";
  language: string;
  current_position: number | null;
  priority: "high" | "medium" | "low";
  status: "proposed" | "approved" | "dismissed" | "done";
  concept: StrategicOpportunityConcept;
  estimate: StrategicOpportunityEstimate;
  tracked_keyword_id: number | null;
  generated_landing_id: number | null;
  generated_landing_slug: string | null;
  created_at: string;
  refreshed_at: string | null;
};

export async function listStrategicOpportunities(
  siteId: number,
  opts: { include_dismissed?: boolean } = {},
) {
  const qs = opts.include_dismissed ? "?include_dismissed=1" : "";
  return request<{ results: StrategicOpportunity[]; count: number }>(
    `/sites/${siteId}/strategic-opportunities/${qs}`,
  );
}

export async function refreshStrategicOpportunities(
  siteId: number,
  body: { max_keywords?: number } = {},
) {
  return request<{
    refreshed: { id: number; keyword: string; priority: string }[];
    skipped: { keyword: string; reason: string }[];
    count_refreshed: number;
    count_skipped: number;
    count_candidates: number;
  }>(`/sites/${siteId}/strategic-opportunities/refresh/`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function actionStrategicOpportunity(
  siteId: number,
  opportunityId: number,
  action: "approve" | "dismiss" | "restore",
) {
  return request<{
    id: number;
    status: StrategicOpportunity["status"];
    landing_id?: number;
    landing_slug?: string;
    note?: string;
  }>(`/sites/${siteId}/strategic-opportunities/${opportunityId}/${action}/`, {
    method: "POST",
    body: JSON.stringify({}),
  });
}

// ---------------------------------------------------------------------------
// Prompt export (2026-06-10)
// ---------------------------------------------------------------------------
// Ready-to-paste prompt for the user's AI coding assistant (ChatGPT, Lovable,
// v0, Bolt...). Pure templating server-side - no LLM call, no quota.

export type PromptStack =
  | "nextjs"
  | "react"
  | "html"
  | "astro"
  | "wordpress"
  | "webflow"
  | "generic";

export type PromptExportResponse = {
  prompt: string;
  source: "landing" | "opportunity";
  landing_id?: number;
  opportunity_id?: number;
  slug?: string;
  keyword?: string;
  stack: PromptStack;
  char_count: number;
};

export async function exportPagePrompt(
  siteId: number,
  opts: {
    landing_id?: number;
    opportunity_id?: number;
    stack?: PromptStack;
  },
) {
  const stackQs = opts.stack ? `?stack=${opts.stack}` : "";
  if (opts.landing_id != null) {
    return request<PromptExportResponse>(
      `/sites/${siteId}/landings/${opts.landing_id}/prompt/${stackQs}`,
    );
  }
  if (opts.opportunity_id != null) {
    return request<PromptExportResponse>(
      `/sites/${siteId}/strategic-opportunities/${opts.opportunity_id}/prompt/${stackQs}`,
    );
  }
  throw new ApiError(
    "exportPagePrompt requires landing_id or opportunity_id",
    400,
  );
}

// Every queue entry carries (kind, id): echo them back to markPageBuilt.
export type BuildQueueLanding = {
  kind: "landing";
  id: number;
  opportunity_id: number;
  keyword: string;
  intent: string;
  priority: string;
  page_type: string | null;
  suggested_title: string | null;
  suggested_slug: string;
  concept: Record<string, unknown>;
  build_prompt: string;
};

// Ready-to-integrate copy generated by Gridar (C2): paste `content` verbatim.
export type BuildQueueArticleReady = {
  kind: "article";
  id: number;
  post_id: number;
  title: string;
  slug: string;
  language: string;
  excerpt: string;
  content: string;
};

// A brief the agent writes the article from (fallback when Gridar has no
// generated copy yet), sourced from an info-intent tracked keyword.
export type BuildQueueArticleBrief = {
  kind: "article_brief";
  id: number;
  tracked_keyword_id: number;
  keyword: string;
  intent: string;
  language: string;
  build_prompt: string;
};

export type BuildQueueArticle = BuildQueueArticleReady | BuildQueueArticleBrief;

export type BuildQueueResponse = {
  site_id: number;
  stack: string;
  delivery_mode: "auto" | "agent";
  landings: BuildQueueLanding[];
  articles: BuildQueueArticle[];
  counts: {
    landings: number;
    articles: number;
    articles_ready: number;
    articles_brief: number;
  };
  note: string;
};

export async function pullBuildQueue(
  siteId: number,
  opts: { stack?: PromptStack } = {},
) {
  const qs = opts.stack ? `?stack=${opts.stack}` : "";
  return request<BuildQueueResponse>(`/sites/${siteId}/build-queue/${qs}`);
}

export async function markPageBuilt(
  siteId: number,
  body: { kind: "landing" | "article" | "article_brief"; id: number; url: string },
) {
  return request<{ ok: boolean; kind: string; id: number; url: string; status?: string; delivered?: boolean }>(
    `/sites/${siteId}/build-queue/mark-built/`,
    { method: "POST", body: JSON.stringify(body) },
  );
}

// ── Topic clusters ────────────────────────────────────────────────────────

export type ClusterSpoke = {
  keyword: string;
  language: string;
  intent: string;
  source: string;
  covered: boolean;
};

export type TopicCluster = {
  anchor: string;
  size: number;
  missing: number;
  pillar: {
    keyword: string;
    language: string;
    intent: string;
    suggested_title: string;
    suggested_slug: string;
    source: string;
    covered: boolean;
  };
  spokes: ClusterSpoke[];
};

export type ClusterMapResponse = {
  site_id: number;
  clusters: TopicCluster[];
  total_keywords: number;
  clustered: number;
  unclustered: number;
};

export async function clusterMap(siteId: number) {
  return request<ClusterMapResponse>(`/sites/${siteId}/clusters/`);
}

export type ClusterBuildPage = {
  role: "pillar" | "spoke";
  exists: boolean;
  keyword: string;
  language: string;
  slug: string;
  // Present only for pages to BUILD (an existing pillar omits them).
  kind?: "article_brief";
  id?: number;
  tracked_keyword_id?: number;
  build_prompt?: string;
};

export type ClusterBuildResponse = {
  site_id: number;
  stack: string;
  language: string;
  delivery_mode: "auto" | "agent";
  pillar: ClusterBuildPage;
  spokes: ClusterBuildPage[];
  counts: { pillar: number; spokes: number };
  note: string;
};

export async function buildCluster(
  siteId: number,
  body: { pillar_keyword: string; spokes: string[]; stack?: PromptStack; language?: string; pillar_slug?: string },
) {
  return request<ClusterBuildResponse>(`/sites/${siteId}/clusters/build/`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

// ── Index coverage ─────────────────────────────────────────────────────────

export type IndexCoveragePage = {
  url: string;
  indexed: boolean;
  reason: string;
  source: "gsc" | "serper";
};

export type IndexCoverageResponse = {
  site_id: number;
  domain: string;
  sitemap_found: boolean;
  method: "gsc+serper" | "serper";
  gsc_used: boolean;
  total_expected: number;
  indexed_count: number;
  not_indexed_count: number;
  coverage_pct: number | null;
  google_knows_count: number;
  inspected: number;
  pages: IndexCoveragePage[];
  not_indexed: IndexCoveragePage[];
  orphans: string[];
  note: string;
  error?: string;
};

export async function indexCoverage(siteId: number, maxInspect?: number) {
  const qs = maxInspect != null ? `?max_inspect=${maxInspect}` : "";
  return request<IndexCoverageResponse>(`/sites/${siteId}/index-coverage/${qs}`);
}
