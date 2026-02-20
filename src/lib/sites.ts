export interface SavedSite {
  id: string;
  name: string;
  apiUrl: string;
  token: string;
  refreshToken: string;
}

const SITES_KEY = "blog_dashboard_sites";
const ACTIVE_SITE_KEY = "blog_dashboard_active_site";

export function getSites(): SavedSite[] {
  const raw = localStorage.getItem(SITES_KEY);
  if (!raw) return [];
  try {
    return JSON.parse(raw);
  } catch {
    return [];
  }
}

export function addSite(site: SavedSite): void {
  const sites = getSites();
  const existing = sites.findIndex((s) => s.id === site.id);
  if (existing >= 0) {
    sites[existing] = site;
  } else {
    sites.push(site);
  }
  localStorage.setItem(SITES_KEY, JSON.stringify(sites));
}

export function removeSite(id: string): void {
  const sites = getSites().filter((s) => s.id !== id);
  localStorage.setItem(SITES_KEY, JSON.stringify(sites));
  const active = getActiveSite();
  if (active?.id === id) {
    localStorage.removeItem(ACTIVE_SITE_KEY);
  }
}

export function updateSiteTokens(
  id: string,
  token: string,
  refreshToken: string
): void {
  const sites = getSites();
  const site = sites.find((s) => s.id === id);
  if (site) {
    site.token = token;
    site.refreshToken = refreshToken;
    localStorage.setItem(SITES_KEY, JSON.stringify(sites));
  }
}

export function setActiveSite(id: string): void {
  localStorage.setItem(ACTIVE_SITE_KEY, id);
}

export function getActiveSite(): SavedSite | null {
  const id = localStorage.getItem(ACTIVE_SITE_KEY);
  if (!id) return null;
  return getSites().find((s) => s.id === id) || null;
}

export function generateSiteId(): string {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 8);
}
