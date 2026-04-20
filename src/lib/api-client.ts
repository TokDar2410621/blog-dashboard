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
  constructor(message: string, status: number, code?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
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
    throw new ApiError(JSON.stringify(err), res.status, "VALIDATION_ERROR");
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

export async function fetchPost(siteId: number, slug: string): Promise<PostDetail> {
  const res = await authFetch(`/sites/${siteId}/posts/${slug}/`);
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

export async function updatePost(siteId: number, slug: string, data: Record<string, unknown>): Promise<PostDetail> {
  const res = await authFetch(`/sites/${siteId}/posts/${slug}/`, {
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

export async function deletePost(siteId: number, slug: string): Promise<void> {
  const res = await authFetch(`/sites/${siteId}/posts/${slug}/`, { method: "DELETE" });
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
    throw new ApiError(err.error || "Generation failed", res.status);
  }
  const data = await res.json();
  return generateArticleResponseSchema.parse(data);
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
