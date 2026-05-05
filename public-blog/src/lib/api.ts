/**
 * Public API client. Reads the dashboard's public endpoints — no auth,
 * just the optional X-Api-Key header per site.
 */

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ||
  "https://blog-dashboard-production-6480.up.railway.app/api";

export type Site = {
  id: number;
  name: string;
  domain: string;
  description?: string;
  og_image_url?: string;
  default_language?: string;
  available_languages?: string[];
  author?: {
    name: string;
    role?: string;
    bio?: string;
    credentials?: string;
    image_url?: string;
    linkedin?: string;
    twitter?: string;
    website?: string;
  };
  person_schema?: Record<string, unknown> | null;
  // Theme overrides (only present if Site.theme_config is set)
  theme_config?: {
    brand_color?: string;
    brand_fg?: string;
    font_sans?: string;
    font_display?: string;
    logo_url?: string;
  };
};

export type Post = {
  id: number;
  title: string;
  slug: string;
  excerpt: string;
  content: string;
  author: string;
  category?: string;
  category_slug?: string;
  tags?: string[];
  cover_image?: string;
  reading_time?: number;
  featured?: boolean;
  status?: string;
  view_count?: number;
  language?: string;
  translation_group?: string;
  scheduled_at?: string | null;
  published_at?: string | null;
  created_at?: string;
  updated_at?: string;
};

type FetchOpts = { siteApiKey?: string; revalidate?: number };

async function apiFetch<T>(path: string, opts: FetchOpts = {}): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };
  if (opts.siteApiKey) headers["X-Api-Key"] = opts.siteApiKey;

  const res = await fetch(`${API_BASE}${path}`, {
    headers,
    next: { revalidate: opts.revalidate ?? 300 }, // 5 min ISR by default
  });
  if (!res.ok) {
    throw new Error(`API ${res.status}: ${path}`);
  }
  return res.json();
}

export async function getSiteByDomain(domain: string): Promise<Site | null> {
  try {
    return await apiFetch<Site>(
      `/public/site-by-domain/?domain=${encodeURIComponent(domain)}`
    );
  } catch {
    return null;
  }
}

export async function getSite(siteId: number, apiKey?: string): Promise<Site> {
  return apiFetch<Site>(`/public/sites/${siteId}/`, { siteApiKey: apiKey });
}

export async function listPosts(
  siteId: number,
  opts: { language?: string; category?: string; featured?: boolean; page?: number; apiKey?: string } = {}
): Promise<{ count: number; results: Post[]; next: number | null; previous: number | null }> {
  const params = new URLSearchParams();
  if (opts.language) params.set("language", opts.language);
  if (opts.category) params.set("category", opts.category);
  if (opts.featured) params.set("featured", "true");
  if (opts.page) params.set("page", String(opts.page));
  const qs = params.toString() ? `?${params.toString()}` : "";
  return apiFetch(`/public/sites/${siteId}/posts/${qs}`, {
    siteApiKey: opts.apiKey,
  });
}

export async function getPost(
  siteId: number,
  slug: string,
  apiKey?: string
): Promise<Post | { redirect_to: string; status: number }> {
  const res = await fetch(
    `${API_BASE}/public/sites/${siteId}/posts/${slug}/`,
    {
      headers: apiKey ? { "X-Api-Key": apiKey } : {},
      next: { revalidate: 300 },
      redirect: "manual",
    }
  );
  if (res.status === 301) {
    const data = await res.json().catch(() => ({}));
    return { redirect_to: data.redirect_to || "/", status: 301 };
  }
  if (!res.ok) {
    throw new Error(`Post not found: ${slug}`);
  }
  return res.json();
}

export async function getTranslations(
  siteId: number,
  slug: string,
  apiKey?: string
): Promise<{
  current_language: string;
  translation_group: string;
  translations: Array<{ slug: string; language: string; title: string; url: string; is_current: boolean }>;
}> {
  return apiFetch(`/public/sites/${siteId}/posts/${slug}/translations/`, {
    siteApiKey: apiKey,
  });
}

export async function listCategories(
  siteId: number,
  apiKey?: string
): Promise<Array<{ id: number; name: string; slug: string; posts_count: number }>> {
  return apiFetch(`/public/sites/${siteId}/categories/`, { siteApiKey: apiKey });
}
