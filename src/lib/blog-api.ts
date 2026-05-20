/**
 * Public blog API client. Reads posts from the Gridar backend's hosted-mode
 * Site (gridar.app marketing blog). Previously the SPA loaded markdown files
 * at build time via Vite glob (see legacy `lib/posts.ts`); since the
 * dogfooding migration, the same content lives in the HostedPost table and
 * is served by `/api/public/sites/<id>/posts/`.
 *
 * The site ID is configured via the VITE_GRIDAR_BLOG_SITE_ID env var on
 * Vercel. Default = 1 (the first site the seed command creates).
 *
 * Endpoint shape (already implemented in backend/sites_mgmt/views.py):
 *   GET /api/public/sites/<id>/posts/         -> paginated list of published posts
 *   GET /api/public/sites/<id>/posts/<slug>/  -> single post detail
 */

const BACKEND_URL = import.meta.env.VITE_API_URL || "http://localhost:8888/api";
// Default = 6 (Gridar marketing blog, hosted mode, 12 published articles).
// Site #1 belongs to a different project (LocaSur) and would surface the wrong
// content if a Vercel env var override was missing. Override via
// VITE_GRIDAR_BLOG_SITE_ID if you ever fork Gridar to host a different blog.
const BLOG_SITE_ID = Number(import.meta.env.VITE_GRIDAR_BLOG_SITE_ID || 6);

export type BlogPost = {
  slug: string;
  title: string;
  excerpt: string;
  content: string;
  author: string;
  language: string;
  tags: string[];
  cover_image: string;
  reading_time: number;
  featured: boolean;
  status: string;
  view_count: number;
  published_at: string;
  category?: string | null;
  category_slug?: string | null;
};

type ListResponse = {
  count: number;
  next: string | null;
  previous: string | null;
  results: BlogPost[];
};

export async function fetchBlogPosts(): Promise<BlogPost[]> {
  const res = await fetch(
    `${BACKEND_URL}/public/sites/${BLOG_SITE_ID}/posts/?page_size=100&language=fr`,
  );
  if (!res.ok) throw new Error(`Failed to fetch posts: ${res.status}`);
  const data: ListResponse | BlogPost[] = await res.json();
  // The endpoint returns a paginated `{count, results}` shape; older code may
  // return a bare array. Normalize.
  return Array.isArray(data) ? data : data.results;
}

export async function fetchBlogPost(slug: string): Promise<BlogPost | null> {
  const res = await fetch(
    `${BACKEND_URL}/public/sites/${BLOG_SITE_ID}/posts/${encodeURIComponent(slug)}/`,
  );
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`Failed to fetch post: ${res.status}`);
  return res.json();
}

export function readingTime(content: string): number {
  if (!content) return 1;
  const words = content.trim().split(/\s+/).length;
  return Math.max(1, Math.round(words / 200));
}
