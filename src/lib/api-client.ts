import { getToken, setTokens } from "./sites";
import {
  loginResponseSchema,
  userSchema,
  siteSchema,
  paginatedPostsSchema,
  postDetailSchema,
  categorySchema,
  tagSchema,
  dashboardStatsSchema,
  generateArticleResponseSchema,
  generateImageResponseSchema,
  seoSuggestionsSchema,
  pexelsResponseSchema,
  type LoginResponse,
  type User,
  type Site,
  type PaginatedPosts,
  type PostDetail,
  type Category,
  type Tag,
  type DashboardStats,
  type GenerateArticleResponse,
  type GenerateImageResponse,
  type SEOSuggestions,
  type PexelsResponse,
} from "./schemas";

const BACKEND_URL = import.meta.env.VITE_API_URL || "http://localhost:8888/api";

export class ApiError extends Error {
  status: number;
  /** Machine-readable code for i18n (see `errors.*` in locale files) */
  code?: string;
  /** Raw response body when JSON-parseable. Use this to read flags the backend
   * sets alongside `error`, e.g. `quota_exceeded`, `limit_type`. */
  body?: Record<string, unknown>;
  constructor(
    message: string,
    status: number,
    code?: string,
    body?: Record<string, unknown>,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.body = body;
  }
}

async function refreshAccessToken(): Promise<boolean> {
  try {
    const res = await fetch(`${BACKEND_URL}/auth/token/refresh/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
    });
    if (!res.ok) return false;
    const data = await res.json();
    if (data.access) setTokens(data.access);
    return true;
  } catch {
    return false;
  }
}

export async function authFetch(
  path: string,
  options: RequestInit = {},
  signal?: AbortSignal
): Promise<Response> {
  const url = `${BACKEND_URL}${path}`;
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  };

  // Attach Bearer token if available (httpOnly cookie also sent automatically)
  const token = getToken();
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  if (!(options.body instanceof FormData) && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }

  let res = await fetch(url, { ...options, headers, signal, credentials: "include" });

  if (res.status === 401) {
    const refreshed = await refreshAccessToken();
    if (refreshed) {
      const newToken = getToken();
      if (newToken) headers.Authorization = `Bearer ${newToken}`;
      res = await fetch(url, { ...options, headers, signal, credentials: "include" });
    } else {
      throw new ApiError("Session expired", 401, "SESSION_EXPIRED");
    }
  }

  return res;
}

// Auth
export async function login(username: string, password: string): Promise<LoginResponse> {
  const res = await fetch(`${BACKEND_URL}/auth/token/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    throw new ApiError("Invalid credentials", res.status, "INVALID_CREDENTIALS");
  }
  const data = await res.json();
  return loginResponseSchema.parse(data);
}

export type EmailCheckResult = {
  exists: boolean;
  has_password: boolean;
  social_providers: string[];
};

/** Check whether an email is already registered, and how the account
 *  authenticates (password / OAuth providers). The lazy-registration flow
 *  on /login uses this to pivot:
 *    - !exists                       -> signup with password
 *    - exists && has_password        -> show password field (login)
 *    - exists && !has_password       -> show "Continue with <provider>" only
 *      (account is OAuth-only, no password was ever set)
 */
export async function checkEmail(email: string): Promise<EmailCheckResult> {
  const res = await fetch(`${BACKEND_URL}/auth/check-email/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ email }),
  });
  if (!res.ok) {
    let detail = "Validation failed";
    try {
      const body = await res.json();
      detail = body.error || detail;
    } catch { /* ignore */ }
    throw new ApiError(detail, res.status, "EMAIL_CHECK_FAILED");
  }
  return res.json();
}

/** Create a new account with email + password. Returns the JWT pair on
 *  success (HTTP 201). Backend uses the email as the Django username. */
export async function register(email: string, password: string): Promise<LoginResponse> {
  const res = await fetch(`${BACKEND_URL}/auth/register/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    let detail = "Registration failed";
    let code = "REGISTRATION_FAILED";
    try {
      const body = await res.json();
      detail = body.error || detail;
      if (body.email_exists) code = "EMAIL_EXISTS";
    } catch { /* ignore */ }
    throw new ApiError(detail, res.status, code);
  }
  const data = await res.json();
  return loginResponseSchema.parse(data);
}

/** Request a password reset email. Always returns success even if the email
 *  doesn't exist (the backend does enumeration-safe responses). */
export async function requestPasswordReset(email: string): Promise<{ detail: string }> {
  const res = await fetch(`${BACKEND_URL}/auth/password/reset/request/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ email }),
  });
  if (!res.ok) {
    let detail = "Reset request failed";
    try {
      const body = await res.json();
      detail = body.error || detail;
    } catch { /* ignore */ }
    throw new ApiError(detail, res.status, "PASSWORD_RESET_REQUEST_FAILED");
  }
  return res.json();
}

/** Submit a new password using the uid+token from the reset email link.
 *  Returns the JWT pair (user is logged in immediately on success). */
export async function confirmPasswordReset(
  uid: string,
  token: string,
  password: string,
): Promise<LoginResponse> {
  const res = await fetch(`${BACKEND_URL}/auth/password/reset/confirm/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ uid, token, password }),
  });
  if (!res.ok) {
    let detail = "Reset failed";
    try {
      const body = await res.json();
      detail = body.error || detail;
    } catch { /* ignore */ }
    throw new ApiError(detail, res.status, "PASSWORD_RESET_FAILED");
  }
  const data = await res.json();
  return loginResponseSchema.parse(data);
}

/** Exchange an OAuth `code` (from Google or GitHub) for our JWT cookie pair. */
export async function socialLogin(
  provider: "google" | "github",
  code: string,
  redirectUri: string,
): Promise<LoginResponse> {
  const res = await fetch(`${BACKEND_URL}/auth/${provider}/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ code, redirect_uri: redirectUri }),
  });
  if (!res.ok) {
    let detail = "OAuth login failed";
    try {
      const body = await res.json();
      detail = body.detail || body.non_field_errors?.[0] || detail;
    } catch {
      /* ignore */
    }
    throw new ApiError(detail, res.status, "OAUTH_LOGIN_FAILED");
  }
  const data = await res.json();
  // dj-rest-auth returns { access_token, refresh_token, user, access_expiration, refresh_expiration }
  return loginResponseSchema.parse({
    access: data.access_token ?? data.access,
    refresh: data.refresh_token ?? data.refresh,
  });
}

/** Tell the backend to wipe the httpOnly auth cookies. Best-effort: a failure
 *  here doesn't block the local clearTokens() that the caller should also do. */
export async function backendLogout(): Promise<void> {
  try {
    await fetch(`${BACKEND_URL}/auth/logout/`, {
      method: "POST",
      credentials: "include",
    });
  } catch {
    /* swallow - the local clearTokens() is what matters for UX */
  }
}

export async function fetchCurrentUser(): Promise<User> {
  const res = await authFetch("/auth/me/");
  if (!res.ok) throw new ApiError("Request failed", res.status, "REQUEST_FAILED");
  const data = await res.json();
  return userSchema.parse(data);
}

// Sites
export async function fetchSites(): Promise<Site[]> {
  const res = await authFetch("/sites/");
  if (!res.ok) throw new ApiError("Request failed", res.status, "REQUEST_FAILED");
  const data = await res.json();
  const list = data.results || data;
  return siteSchema.array().parse(list);
}

export async function createSite(data: { name: string; database_url?: string; domain: string }): Promise<Site> {
  const res = await authFetch("/sites/", {
    method: "POST",
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    // Prefer the backend's `error` field as the human message (used by quota
    // gates: 'Limite de sites atteinte (1/1)...'). Fall back to a stringified
    // body for validation errors.
    const message =
      typeof err.error === "string" && err.error
        ? err.error
        : JSON.stringify(err);
    throw new ApiError(message, res.status, "VALIDATION_ERROR", err);
  }
  const json = await res.json();
  return siteSchema.parse(json);
}

export async function fetchSite(id: number): Promise<Site> {
  const res = await authFetch(`/sites/${id}/`);
  if (!res.ok) throw new ApiError("Request failed", res.status, "REQUEST_FAILED");
  const data = await res.json();
  return siteSchema.parse(data);
}

export async function updateSite(id: number, data: Record<string, unknown>): Promise<Site> {
  const res = await authFetch(`/sites/${id}/`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new ApiError(JSON.stringify(err), res.status, "VALIDATION_ERROR");
  }
  const json = await res.json();
  return siteSchema.parse(json);
}

export async function deleteSite(id: number): Promise<void> {
  const res = await authFetch(`/sites/${id}/`, { method: "DELETE" });
  if (!res.ok) throw new ApiError("Request failed", res.status, "REQUEST_FAILED");
}

export async function testSiteConnection(id: number) {
  const res = await authFetch(`/sites/${id}/test/`, { method: "POST" });
  if (!res.ok) throw new ApiError("Request failed", res.status, "REQUEST_FAILED");
  return res.json();
}

export async function initSiteDB(id: number) {
  const res = await authFetch(`/sites/${id}/init_db/`, { method: "POST" });
  if (!res.ok) throw new ApiError("Request failed", res.status, "REQUEST_FAILED");
  return res.json();
}

// Dashboard Stats
export async function fetchDashboardStats(siteId: number): Promise<DashboardStats> {
  const res = await authFetch(`/sites/${siteId}/stats/`);
  if (!res.ok) throw new ApiError("Request failed", res.status, "REQUEST_FAILED");
  const data = await res.json();
  return dashboardStatsSchema.parse(data);
}

// Posts
export async function fetchAllPosts(siteId: number, page = 1): Promise<PaginatedPosts> {
  const res = await authFetch(`/sites/${siteId}/posts/?page=${page}`);
  if (!res.ok) throw new ApiError("Request failed", res.status, "REQUEST_FAILED");
  const data = await res.json();
  return paginatedPostsSchema.parse(data);
}

export async function fetchPost(siteId: number, slug: string, language?: string): Promise<PostDetail> {
  const suffix = language ? `?language=${encodeURIComponent(language)}` : "";
  const res = await authFetch(`/sites/${siteId}/posts/${slug}/${suffix}`);
  if (!res.ok) throw new ApiError("Request failed", res.status, "REQUEST_FAILED");
  const data = await res.json();
  return postDetailSchema.parse(data);
}

export async function createPost(siteId: number, data: Record<string, unknown>): Promise<PostDetail> {
  const res = await authFetch(`/sites/${siteId}/posts/`, {
    method: "POST",
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new ApiError(JSON.stringify(err), res.status, "VALIDATION_ERROR");
  }
  const json = await res.json();
  return postDetailSchema.parse(json);
}

export async function updatePost(siteId: number, slug: string, data: Record<string, unknown>, language?: string): Promise<PostDetail> {
  const suffix = language ? `?language=${encodeURIComponent(language)}` : "";
  const res = await authFetch(`/sites/${siteId}/posts/${slug}/${suffix}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new ApiError(JSON.stringify(err), res.status, "VALIDATION_ERROR");
  }
  const json = await res.json();
  return postDetailSchema.parse(json);
}

export async function deletePost(siteId: number, slug: string, language?: string): Promise<void> {
  const suffix = language ? `?language=${encodeURIComponent(language)}` : "";
  const res = await authFetch(`/sites/${siteId}/posts/${slug}/${suffix}`, { method: "DELETE" });
  if (!res.ok) throw new ApiError("Request failed", res.status, "REQUEST_FAILED");
}

// Categories
export async function fetchCategories(siteId: number): Promise<Category[]> {
  const res = await authFetch(`/sites/${siteId}/categories/`);
  if (!res.ok) throw new ApiError("Request failed", res.status, "REQUEST_FAILED");
  const data = await res.json();
  const list = data.results || data;
  return categorySchema.array().parse(list);
}

// Tags
export async function fetchTags(siteId: number): Promise<Tag[]> {
  const res = await authFetch(`/sites/${siteId}/tags/`);
  if (!res.ok) throw new ApiError("Request failed", res.status, "REQUEST_FAILED");
  const data = await res.json();
  const list = data.results || data;
  return tagSchema.array().parse(list);
}

// Generate Article
export async function generateArticle(
  siteId: number,
  params: Record<string, unknown>,
  signal?: AbortSignal
): Promise<GenerateArticleResponse> {
  const res = await authFetch(
    `/sites/${siteId}/generate/`,
    { method: "POST", body: JSON.stringify(params) },
    signal
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new ApiError(
      err.error || "Generation failed",
      res.status,
      undefined,
      err,
    );
  }
  const data = await res.json();
  return generateArticleResponseSchema.parse(data);
}

// Generate Sister Article (multi-lang translation that shares translation_group)
export type GenerateSisterArticleResponse = {
  slug: string;
  id: number;
  language: string;
  translation_group: string;
  status: string;
  title: string;
};

export async function generateSisterArticle(
  siteId: number,
  sourceSlug: string,
  body: { target_language: "fr" | "en" | "es" },
  signal?: AbortSignal,
): Promise<GenerateSisterArticleResponse> {
  const res = await authFetch(
    `/v1/sites/${siteId}/articles/${encodeURIComponent(sourceSlug)}/generate-sister-article/`,
    { method: "POST", body: JSON.stringify(body) },
    signal,
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new ApiError(
      err.error || "Sister article generation failed",
      res.status,
      undefined,
      err,
    );
  }
  return res.json();
}

// Pexels Search
export async function searchPexels(query: string): Promise<PexelsResponse> {
  const res = await authFetch(`/pexels/search/?query=${encodeURIComponent(query)}`);
  if (!res.ok) {
    throw new ApiError("Pexels search failed", res.status, "REQUEST_FAILED");
  }
  const data = await res.json();
  return pexelsResponseSchema.parse(data);
}

// Serper Image Search
export async function searchSerperImages(query: string): Promise<PexelsResponse> {
  const res = await authFetch(`/serper/images/?query=${encodeURIComponent(query)}`);
  if (!res.ok) {
    throw new ApiError("Serper search failed", res.status, "REQUEST_FAILED");
  }
  const data = await res.json();
  return pexelsResponseSchema.parse(data);
}

// Generate Cover Image (Gemini)
export async function generateCoverImage(
  prompt: string,
  signal?: AbortSignal
): Promise<GenerateImageResponse> {
  const res = await authFetch(
    "/generate-image/",
    { method: "POST", body: JSON.stringify({ prompt }) },
    signal
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new ApiError(err.error || "Image generation failed", res.status);
  }
  const data = await res.json();
  return generateImageResponseSchema.parse(data);
}

// Images
export async function fetchImages(siteId: number) {
  const res = await authFetch(`/sites/${siteId}/images/`);
  if (!res.ok) throw new ApiError("Request failed", res.status, "REQUEST_FAILED");
  return res.json();
}

export async function uploadImage(siteId: number, file: File) {
  const formData = new FormData();
  formData.append("image", file);
  const res = await authFetch(`/sites/${siteId}/images/upload/`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    throw new ApiError("Upload failed", res.status, "REQUEST_FAILED");
  }
  return res.json();
}

// SEO Suggestions (AI)
export async function fetchSEOSuggestions(params: {
  title: string;
  content: string;
  excerpt: string;
  language: string;
}): Promise<SEOSuggestions> {
  const res = await authFetch("/seo-suggest/", {
    method: "POST",
    body: JSON.stringify(params),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new ApiError(err.error || "SEO request failed", res.status);
  }
  const data = await res.json();
  return seoSuggestionsSchema.parse(data);
}

// Google Search Console
export interface GSCQueryRow {
  query: string;
  clicks: number;
  impressions: number;
  ctr: number;
  position: number;
}

export interface GSCQueriesResponse {
  page_url: string;
  days: number;
  queries: GSCQueryRow[];
}

export async function fetchGSCOAuthUrl(siteId: number): Promise<{ url: string }> {
  const res = await authFetch(`/sites/${siteId}/gsc/oauth-url/`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new ApiError(err.error || "GSC OAuth URL failed", res.status);
  }
  return res.json();
}

export async function submitGSCOAuthCallback(
  siteId: number,
  code: string,
  state: string
): Promise<{ success: boolean }> {
  const res = await authFetch(`/sites/${siteId}/gsc/oauth-callback/`, {
    method: "POST",
    body: JSON.stringify({ code, state }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new ApiError(err.error || "GSC OAuth callback failed", res.status);
  }
  return res.json();
}

export async function fetchGSCQueries(
  siteId: number,
  slug: string,
  days = 28
): Promise<GSCQueriesResponse> {
  const res = await authFetch(
    `/sites/${siteId}/gsc/queries/?slug=${encodeURIComponent(slug)}&days=${days}`
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new ApiError(
      err.error || "GSC queries failed",
      res.status,
      err.code || undefined
    );
  }
  return res.json();
}

// Upload inline image (returns { url })
export async function uploadInlineImage(file: File): Promise<{ url: string }> {
  const formData = new FormData();
  formData.append("image", file);
  const res = await authFetch("/upload-image/", {
    method: "POST",
    body: formData,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new ApiError(err.error || "Upload failed", res.status, "REQUEST_FAILED");
  }
  return res.json();
}

// ---- Proof loop (baseline + attribution) ----

export type ProofQueryRow = {
  query: string;
  impressions: number;
  clicks: number;
  position: number | null;
};

export type ProofAttribution = {
  id: number;
  post_id: number;
  post_slug: string;
  post_title: string;
  days_since_publish: 30 | 60 | 90;
  captured_at: string;
  period_start: string;
  period_end: string;
  indexed: boolean;
  impressions: number;
  clicks: number;
  avg_position: number | null;
  top_queries: ProofQueryRow[];
  delta_vs_baseline: {
    impressions: number;
    clicks: number;
    avg_position: number | null;
  };
};

export type ProofTopGainer = {
  post_id: number;
  title: string;
  slug: string;
  horizon: 30 | 60 | 90;
  impressions_gained: number;
  clicks_gained: number;
  top_queries: ProofQueryRow[];
};

export type ProofSummary = {
  site_id: number;
  site_name: string;
  domain?: string;
  posts_with_attribution: number;
  total_impressions_gained: number;
  total_clicks_gained: number;
  top_gainers: ProofTopGainer[];
};

export type ProofShareState = {
  enabled: boolean;
  token: string | null;
  public_url: string | null;
  created_at?: string;
  revoked_at?: string | null;
  rotated?: boolean;
};

export async function fetchProofSummary(siteId: number): Promise<ProofSummary> {
  const res = await authFetch(`/sites/${siteId}/proof/summary/`);
  if (!res.ok) throw new ApiError("Proof summary failed", res.status);
  return res.json();
}

export async function fetchProofAttribution(
  siteId: number,
  postId?: number,
): Promise<{ attributions: ProofAttribution[] }> {
  const q = postId ? `?post=${postId}` : "";
  const res = await authFetch(`/sites/${siteId}/proof/attribution/${q}`);
  if (!res.ok) throw new ApiError("Proof attribution failed", res.status);
  return res.json();
}

export async function fetchProofShareState(siteId: number): Promise<ProofShareState> {
  const res = await authFetch(`/sites/${siteId}/proof/share/`);
  if (!res.ok) throw new ApiError("Proof share state failed", res.status);
  return res.json();
}

export async function enableProofShare(
  siteId: number,
  opts?: { rotate?: boolean },
): Promise<ProofShareState> {
  const res = await authFetch(`/sites/${siteId}/proof/share/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ rotate: !!opts?.rotate }),
  });
  if (!res.ok) throw new ApiError("Enable share failed", res.status);
  return res.json();
}

export async function revokeProofShare(siteId: number): Promise<ProofShareState> {
  const res = await authFetch(`/sites/${siteId}/proof/share/`, { method: "DELETE" });
  if (!res.ok) throw new ApiError("Revoke share failed", res.status);
  return res.json();
}

// ---------------------------------------------------------------------------
// Topic Cluster Planner (2026-06-08)
// ---------------------------------------------------------------------------

export type KeywordIntent =
  | "transactional"
  | "commercial"
  | "informational"
  | "navigational"
  | "local";

export type ProposedPage = {
  type: "landing" | "article";
  title: string;
  slug: string;
  keyword: string;
  role: "pillar" | "cluster" | "alternative" | "standalone";
  page_subtype?: string;
};

export type KeywordStrategy = {
  id: number;
  site_id: number;
  keyword: string;
  intent: KeywordIntent;
  intent_confidence: number;
  proposed_structure: string;
  proposed_pages: ProposedPage[];
  rationale: string;
  status: string;
  created: boolean;
};

export type HostedLandingDraft = {
  id: number;
  slug: string;
  title?: string;
  h1?: string;
  status: string;
  page_subtype?: string;
};

export async function classifyKeywordIntent(
  keyword: string,
  siteId?: number,
): Promise<{
  keyword: string;
  intent: KeywordIntent;
  confidence: number;
  navigational_match: boolean;
}> {
  const res = await authFetch(`/v1/classify-intent/`, {
    method: "POST",
    body: JSON.stringify({ keyword, site_id: siteId }),
  });
  if (!res.ok) throw new ApiError("Intent classification failed", res.status);
  return res.json();
}

export async function proposeKeywordStrategy(
  siteId: number,
  keyword: string,
  language?: "fr" | "en" | "es",
): Promise<KeywordStrategy> {
  const res = await authFetch(`/v1/sites/${siteId}/keyword-strategy/`, {
    method: "POST",
    body: JSON.stringify({ keyword, language }),
  });
  if (!res.ok) throw new ApiError("Strategy proposal failed", res.status);
  return res.json();
}

export async function approveKeywordStrategy(
  siteId: number,
  strategyId: number,
  customizations?: { pages?: ProposedPage[] },
): Promise<{
  id: number;
  status: string;
  generated_landings: number[];
  planned_articles: unknown[];
  errors: unknown[];
}> {
  const res = await authFetch(
    `/v1/sites/${siteId}/keyword-strategy/${strategyId}/approve/`,
    {
      method: "POST",
      body: JSON.stringify({ customizations: customizations ?? {} }),
    },
  );
  if (!res.ok) throw new ApiError("Strategy approval failed", res.status);
  return res.json();
}

export async function createLandingManual(
  siteId: number,
  body: Record<string, unknown>,
): Promise<HostedLandingDraft> {
  const res = await authFetch(`/v1/sites/${siteId}/landings/manual/`, {
    method: "POST",
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new ApiError("Landing creation failed", res.status);
  return res.json();
}

export async function generateLandingAi(
  siteId: number,
  body: {
    keyword: string;
    primary_cta_text?: string;
    primary_cta_url?: string;
    value_props?: unknown[];
    page_subtype?: "service" | "product" | "pillar" | "comparison" | "local";
    language?: "fr" | "en" | "es";
  },
): Promise<HostedLandingDraft> {
  const res = await authFetch(`/v1/sites/${siteId}/landings/generate/`, {
    method: "POST",
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new ApiError("Landing generation failed", res.status);
  return res.json();
}

export async function linkPagesV1(
  siteId: number,
  body: { source_slug: string; target_slug: string; anchor_text: string },
): Promise<{
  status: string;
  source_slug: string;
  source_type?: string;
  target_slug: string;
  target_type?: string;
  anchor_text?: string;
  inserted_inline?: boolean;
}> {
  const res = await authFetch(`/v1/sites/${siteId}/link-pages/`, {
    method: "POST",
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new ApiError("Link insertion failed", res.status);
  return res.json();
}

// SERP Analyzer (2026-06-08) - Surfer-style top-10 benchmark
export type SerpAnalyzeResult = {
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
};

export type SerpAnalyzeResponse = {
  keyword: string;
  language: string;
  top_10: SerpAnalyzeResult[];
  averages: {
    word_count_avg: number;
    headings_avg: number;
    faq_pct: number;
    video_pct: number;
  };
};

export async function serpAnalyze(
  siteId: number,
  body: { keyword: string; language?: "fr" | "en" | "es" },
): Promise<SerpAnalyzeResponse> {
  const res = await authFetch(`/v1/sites/${siteId}/serp-analyze/`, {
    method: "POST",
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new ApiError(
      typeof err.error === "string" ? err.error : "SERP analyze failed",
      res.status,
      "SERP_ANALYZE_FAILED",
      err,
    );
  }
  return res.json();
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

export type AiVisibilityEngineBreakdown = {
  total_checks: number;
  cited_count: number;
  cite_rate: number;
};

export type AiVisibilitySummary = {
  score: number;
  total_mentions: number;
  cited_pages_count: number;
  total_checks: number;
  total_prompts: number;
  breakdown_by_engine: Record<AiVisibilityEngine, AiVisibilityEngineBreakdown>;
  delta_7d: number;
};

export type AiVisibilityPrompt = {
  id: number;
  prompt: string;
  target_intent: string | null;
  language: string;
  created_at: string;
  total_checks: number;
  citation_count: number;
  engines_mentioning: AiVisibilityEngine[];
  last_checked_at: string | null;
};

export type AiVisibilityRunResult = {
  id: number;
  prompt_id: number;
  engine: AiVisibilityEngine;
  is_cited: boolean;
  citation_url: string | null;
  citation_rank: number | null;
  checked_at: string;
};

export type AiVisibilityRunResponse = {
  checks_run: number;
  prompts_checked: number;
  engines_per_prompt: number;
  results: AiVisibilityRunResult[];
  mocked: boolean;
  note: string;
};

export async function aiVisibilitySummary(
  siteId: number,
): Promise<AiVisibilitySummary> {
  const res = await authFetch(`/v1/sites/${siteId}/ai-visibility/summary/`);
  if (!res.ok) throw new ApiError("AI visibility summary failed", res.status);
  return res.json();
}

export async function listAiVisibilityPrompts(
  siteId: number,
): Promise<{ results: AiVisibilityPrompt[]; count: number }> {
  const res = await authFetch(`/v1/sites/${siteId}/ai-visibility/prompts/`);
  if (!res.ok) throw new ApiError("AI visibility prompts failed", res.status);
  return res.json();
}

export async function createAiVisibilityPrompt(
  siteId: number,
  body: {
    prompt: string;
    target_intent?: string | null;
    language?: "fr" | "en" | "es";
  },
): Promise<{
  id: number;
  prompt: string;
  target_intent: string | null;
  language: string;
  created_at: string;
}> {
  const res = await authFetch(`/v1/sites/${siteId}/ai-visibility/prompts/`, {
    method: "POST",
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new ApiError(
      typeof err.error === "string" ? err.error : "AI prompt creation failed",
      res.status,
      "AI_PROMPT_CREATE_FAILED",
      err,
    );
  }
  return res.json();
}

export async function runAiVisibility(
  siteId: number,
  body: { prompt_id?: number } = {},
): Promise<AiVisibilityRunResponse> {
  const res = await authFetch(`/v1/sites/${siteId}/ai-visibility/run/`, {
    method: "POST",
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new ApiError(
      typeof err.error === "string" ? err.error : "AI visibility run failed",
      res.status,
      "AI_VIS_RUN_FAILED",
      err,
    );
  }
  return res.json();
}

// ============================================================================
// Strategic Opportunities
// ============================================================================
// /api/v1/sites/<id>/strategic-opportunities/*
// Backed by the Claude strategic engine: for each non-info-intent keyword
// without a matching landing, the engine proposes a page concept tied to the
// site's existing assets + a conversion mechanism. UI lives at
// /dashboard/<siteId>/opportunites.

export type StrategicOpportunityConcept = {
  page_concept: string;
  page_type:
    | "tool_landing"
    | "service_page"
    | "comparison"
    | "guide_pillar"
    | "quiz_landing"
    | "calculator"
    | "local_landing"
    | "lead_magnet"
    | string;
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
  qualitative_traffic: "élevé" | "moyen" | "faible" | "marginal" | "inconnu";
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
  options: { includeDismissed?: boolean } = {},
): Promise<{ results: StrategicOpportunity[]; count: number }> {
  const qs = options.includeDismissed ? "?include_dismissed=1" : "";
  const res = await authFetch(
    `/v1/sites/${siteId}/strategic-opportunities/${qs}`,
  );
  if (!res.ok) {
    throw new ApiError("Liste des opportunités impossible", res.status);
  }
  return res.json();
}

export async function refreshStrategicOpportunities(
  siteId: number,
  body: { max_keywords?: number } = {},
): Promise<{
  refreshed: Array<{ id: number; keyword: string; priority: string }>;
  skipped: Array<{ keyword: string; reason: string }>;
  count_refreshed: number;
  count_skipped: number;
  count_candidates: number;
}> {
  const res = await authFetch(
    `/v1/sites/${siteId}/strategic-opportunities/refresh/`,
    { method: "POST", body: JSON.stringify(body) },
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new ApiError(
      typeof err.error === "string"
        ? err.error
        : "Régénération des opportunités impossible",
      res.status,
      "OPPORTUNITIES_REFRESH_FAILED",
      err,
    );
  }
  return res.json();
}

export async function actionStrategicOpportunity(
  siteId: number,
  opportunityId: number,
  action: "dismiss" | "restore" | "approve",
): Promise<{
  id: number;
  status: StrategicOpportunity["status"];
  landing_id?: number;
  landing_slug?: string;
  note?: string;
}> {
  const res = await authFetch(
    `/v1/sites/${siteId}/strategic-opportunities/${opportunityId}/${action}/`,
    { method: "POST", body: JSON.stringify({}) },
  );
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new ApiError(
      typeof err.error === "string" ? err.error : `Action ${action} impossible`,
      res.status,
      `OPPORTUNITY_${action.toUpperCase()}_FAILED`,
      err,
    );
  }
  return res.json();
}
