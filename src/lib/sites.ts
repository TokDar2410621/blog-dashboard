import { LS_KEY } from "./constants";

export interface Site {
  id: number;
  name: string;
  domain: string;
  database_url?: string;
  api_key?: string;
  is_hosted?: boolean;
  created_at: string;
}

export function getToken(): string | null {
  const sessionToken = sessionStorage.getItem(LS_KEY.TOKEN);
  if (sessionToken) return sessionToken;

  // One-time migration from localStorage to sessionStorage
  const legacyToken = localStorage.getItem(LS_KEY.TOKEN);
  if (legacyToken) {
    sessionStorage.setItem(LS_KEY.TOKEN, legacyToken);
    localStorage.removeItem(LS_KEY.TOKEN);
    return legacyToken;
  }
  return null;
}

export function setTokens(access: string): void {
  // Keep access token in sessionStorage only (reduced persistence surface)
  sessionStorage.setItem(LS_KEY.TOKEN, access);
  // Defensive cleanup for older builds that stored refresh in localStorage
  localStorage.removeItem(LS_KEY.REFRESH);
}

export function clearTokens(): void {
  sessionStorage.removeItem(LS_KEY.TOKEN);
  localStorage.removeItem(LS_KEY.TOKEN);
  localStorage.removeItem(LS_KEY.REFRESH);
  localStorage.removeItem(LS_KEY.ACTIVE_SITE);
}

export function getActiveSiteId(): number | null {
  const id = localStorage.getItem(LS_KEY.ACTIVE_SITE);
  return id ? parseInt(id, 10) : null;
}

export function setActiveSiteId(id: number): void {
  localStorage.setItem(LS_KEY.ACTIVE_SITE, id.toString());
}
