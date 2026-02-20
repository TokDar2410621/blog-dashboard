import { getActiveSite, updateSiteTokens } from "./sites";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function refreshAccessToken(
  apiUrl: string,
  refreshToken: string
): Promise<{ access: string } | null> {
  try {
    const res = await fetch(`${apiUrl}/auth/token/refresh/`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh: refreshToken }),
    });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function authFetch(
  path: string,
  options: RequestInit = {}
): Promise<Response> {
  const site = getActiveSite();
  if (!site) throw new ApiError("Aucun site actif", 401);

  const url = `${site.apiUrl}${path}`;
  const headers: Record<string, string> = {
    Authorization: `Bearer ${site.token}`,
    ...(options.headers as Record<string, string>),
  };

  if (
    !(options.body instanceof FormData) &&
    !headers["Content-Type"]
  ) {
    headers["Content-Type"] = "application/json";
  }

  let res = await fetch(url, { ...options, headers });

  if (res.status === 401 && site.refreshToken) {
    const refreshed = await refreshAccessToken(
      site.apiUrl,
      site.refreshToken
    );
    if (refreshed) {
      updateSiteTokens(site.id, refreshed.access, site.refreshToken);
      headers.Authorization = `Bearer ${refreshed.access}`;
      res = await fetch(url, { ...options, headers });
    } else {
      throw new ApiError("Session expiree", 401);
    }
  }

  return res;
}

export async function publicFetch(
  apiUrl: string,
  path: string
): Promise<Response> {
  return fetch(`${apiUrl}${path}`, {
    headers: { Accept: "application/json" },
  });
}

// Auth
export async function login(
  apiUrl: string,
  username: string,
  password: string
): Promise<{ access: string; refresh: string }> {
  const res = await fetch(`${apiUrl}/auth/token/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username, password }),
  });
  if (!res.ok) {
    throw new ApiError("Identifiants invalides", res.status);
  }
  return res.json();
}

export async function fetchCurrentUser(): Promise<{
  username: string;
  email: string;
}> {
  const res = await authFetch("/auth/me/");
  if (!res.ok) throw new ApiError("Erreur", res.status);
  return res.json();
}

// Dashboard Stats
export async function fetchDashboardStats() {
  const res = await authFetch("/dashboard/stats/");
  if (!res.ok) throw new ApiError("Erreur", res.status);
  return res.json();
}

// Posts
export async function fetchAllPosts(page = 1) {
  const res = await authFetch(`/posts/all_posts/?page=${page}`);
  if (!res.ok) throw new ApiError("Erreur", res.status);
  return res.json();
}

export async function fetchPost(slug: string) {
  const res = await authFetch(`/posts/${slug}/`);
  if (!res.ok) throw new ApiError("Erreur", res.status);
  return res.json();
}

export async function createPost(data: Record<string, unknown>) {
  const res = await authFetch("/posts/", {
    method: "POST",
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new ApiError(
      JSON.stringify(err),
      res.status
    );
  }
  return res.json();
}

export async function updatePost(
  slug: string,
  data: Record<string, unknown>
) {
  const res = await authFetch(`/posts/${slug}/`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new ApiError(JSON.stringify(err), res.status);
  }
  return res.json();
}

export async function deletePost(slug: string) {
  const res = await authFetch(`/posts/${slug}/`, {
    method: "DELETE",
  });
  if (!res.ok) throw new ApiError("Erreur", res.status);
}

// Categories
export async function fetchCategories() {
  const res = await authFetch("/categories/");
  if (!res.ok) throw new ApiError("Erreur", res.status);
  const data = await res.json();
  return data.results || data;
}

// Tags
export async function fetchTags() {
  const res = await authFetch("/tags/");
  if (!res.ok) throw new ApiError("Erreur", res.status);
  const data = await res.json();
  return data.results || data;
}

// Generate Article
export async function generateArticle(
  params: Record<string, unknown>
) {
  const res = await authFetch("/generate-article/", {
    method: "POST",
    body: JSON.stringify(params),
  });
  if (!res.ok) throw new ApiError("Erreur generation", res.status);
  return res.json();
}

// Upload Image
export async function uploadImage(file: File) {
  const formData = new FormData();
  formData.append("image", file);
  const res = await authFetch("/upload/", {
    method: "POST",
    body: formData,
  });
  if (!res.ok) throw new ApiError("Erreur upload", res.status);
  return res.json();
}

// Image Gallery
export async function fetchImages() {
  const res = await authFetch("/images/");
  if (!res.ok) throw new ApiError("Erreur", res.status);
  return res.json();
}
