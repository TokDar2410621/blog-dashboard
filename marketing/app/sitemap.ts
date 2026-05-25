import type { MetadataRoute } from "next";
import { fetchBlogPosts } from "@/lib/blog-api";

const SITE = "https://gridar.app";

export const revalidate = 3600;

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const posts = await fetchBlogPosts();

  const staticRoutes: MetadataRoute.Sitemap = [
    { url: `${SITE}/`, changeFrequency: "weekly", priority: 1.0 },
    { url: `${SITE}/blog`, changeFrequency: "daily", priority: 0.9 },
    { url: `${SITE}/docs`, changeFrequency: "weekly", priority: 0.9 },
    { url: `${SITE}/api-docs`, changeFrequency: "monthly", priority: 0.7 },
    { url: `${SITE}/audit`, changeFrequency: "weekly", priority: 0.8 },
    { url: `${SITE}/privacy`, changeFrequency: "yearly", priority: 0.3 },
    { url: `${SITE}/terms`, changeFrequency: "yearly", priority: 0.3 },
  ];

  const postRoutes: MetadataRoute.Sitemap = posts.map((p) => ({
    url: `${SITE}/blog/${p.slug}`,
    lastModified: p.published_at ? new Date(p.published_at) : undefined,
    changeFrequency: "monthly",
    priority: 0.7,
  }));

  return [...staticRoutes, ...postRoutes];
}
