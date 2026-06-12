/**
 * Fetch helper for the /sites page and its CMS connect dialogs
 * (WordPress / Shopify / Webflow / branding scan).
 *
 * Minimal replica of the SPA's authFetch: same-origin /api base (Next
 * rewrites forward to Django), Bearer token from sessionStorage when
 * available, httpOnly cookies always sent, silent refresh on 401.
 */
import { getToken, setTokens } from "./auth-storage";

const BACKEND_URL = "/api";

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
  signal?: AbortSignal,
): Promise<Response> {
  const url = `${BACKEND_URL}${path}`;
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  };

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
      throw new Error("Session expired");
    }
  }

  return res;
}
