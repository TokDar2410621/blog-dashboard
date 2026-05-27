/**
 * Client-side token storage. Mirrors the Vite app's `lib/sites.ts` so the
 * same backend flow (httpOnly refresh cookie + sessionStorage access token)
 * works identically in the Next.js port.
 *
 * SSR-safe: every accessor guards `typeof window !== "undefined"`. Server
 * Components calling these helpers get null and behave as if unauthenticated.
 */
import { LS_KEY } from "./constants";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  const sessionToken = sessionStorage.getItem(LS_KEY.TOKEN);
  if (sessionToken) return sessionToken;

  const legacyToken = localStorage.getItem(LS_KEY.TOKEN);
  if (legacyToken) {
    sessionStorage.setItem(LS_KEY.TOKEN, legacyToken);
    localStorage.removeItem(LS_KEY.TOKEN);
    return legacyToken;
  }
  return null;
}

export function setTokens(access: string): void {
  if (typeof window === "undefined") return;
  sessionStorage.setItem(LS_KEY.TOKEN, access);
  localStorage.removeItem(LS_KEY.REFRESH);
}

export function clearTokens(): void {
  if (typeof window === "undefined") return;
  sessionStorage.removeItem(LS_KEY.TOKEN);
  localStorage.removeItem(LS_KEY.TOKEN);
  localStorage.removeItem(LS_KEY.REFRESH);
  localStorage.removeItem(LS_KEY.ACTIVE_SITE);
}

export function getActiveSiteId(): number | null {
  if (typeof window === "undefined") return null;
  const id = localStorage.getItem(LS_KEY.ACTIVE_SITE);
  return id ? parseInt(id, 10) : null;
}

export function setActiveSiteId(id: number): void {
  if (typeof window === "undefined") return;
  localStorage.setItem(LS_KEY.ACTIVE_SITE, id.toString());
}
