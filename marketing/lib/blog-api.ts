/**
 * Public blog API client. Reads HostedPost rows from the Gridar backend
 * (Site #6 in hosted mode = the gridar.app marketing blog).
 *
 * Used by Server Components - fetch() inherits Next.js' caching:
 *   { next: { revalidate: 3600 } } -> ISR, refresh every hour
 *   { cache: 'no-store' }            -> dynamic, every request
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || "https://api.gridar.app";
const BLOG_SITE_ID = Number(process.env.NEXT_PUBLIC_BLOG_SITE_ID || 6);
const REVALIDATE_SECONDS = 3600;

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
  const url = `${API_URL}/api/public/sites/${BLOG_SITE_ID}/posts/?page_size=100&language=fr`;
  const res = await fetch(url, { next: { revalidate: REVALIDATE_SECONDS } });
  if (!res.ok) {
    console.error(`fetchBlogPosts: ${res.status} from ${url}`);
    return [];
  }
  const data: ListResponse | BlogPost[] = await res.json();
  return Array.isArray(data) ? data : data.results;
}

export async function fetchBlogPost(slug: string): Promise<BlogPost | null> {
  const url = `${API_URL}/api/public/sites/${BLOG_SITE_ID}/posts/${encodeURIComponent(slug)}/`;
  const res = await fetch(url, { next: { revalidate: REVALIDATE_SECONDS } });
  if (res.status === 404) return null;
  if (!res.ok) {
    console.error(`fetchBlogPost(${slug}): ${res.status}`);
    return null;
  }
  return res.json();
}

export function readingTime(content: string): number {
  if (!content) return 1;
  const words = content.trim().split(/\s+/).length;
  return Math.max(1, Math.round(words / 200));
}
