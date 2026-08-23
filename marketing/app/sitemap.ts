import type { MetadataRoute } from "next";
import { fetchBlogPosts } from "@/lib/blog-api";
import { listLandings } from "@/lib/landing-api";

const SITE = "https://www.gridar.app";

export const revalidate = 3600;

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const [posts, landings] = await Promise.all([
    fetchBlogPosts(),
    listLandings(),
  ]);

  const staticRoutes: MetadataRoute.Sitemap = [
    { url: `${SITE}/`, changeFrequency: "weekly", priority: 1.0 },
    { url: `${SITE}/blog`, changeFrequency: "daily", priority: 0.9 },
    { url: `${SITE}/docs`, changeFrequency: "weekly", priority: 0.9 },
    { url: `${SITE}/api-docs`, changeFrequency: "monthly", priority: 0.7 },
    { url: `${SITE}/audit`, changeFrequency: "weekly", priority: 0.8 },
    { url: `${SITE}/tools`, changeFrequency: "weekly", priority: 0.9 },
    {
      url: `${SITE}/tools/ai-visibility-checker`,
      changeFrequency: "weekly",
      priority: 0.85,
    },
    {
      url: `${SITE}/tools/competitor-gap`,
      changeFrequency: "weekly",
      priority: 0.85,
    },
    {
      url: `${SITE}/tools/ai-citation-checker`,
      changeFrequency: "weekly",
      priority: 0.85,
    },
    {
      url: `${SITE}/tools/competitor-compare`,
      changeFrequency: "weekly",
      priority: 0.85,
    },
    {
      url: `${SITE}/tools/keyword-difficulty`,
      changeFrequency: "weekly",
      priority: 0.85,
    },
    {
      url: `${SITE}/tools/seo-roi-calculator`,
      changeFrequency: "weekly",
      priority: 0.85,
    },
    // /tools/seo-audit stays out on purpose: it redirects to /audit, already
    // declared above. A sitemap must not advertise a redirect.
    {
      url: `${SITE}/suivi-position-google-canada`,
      changeFrequency: "weekly",
      priority: 0.85,
    },
    { url: `${SITE}/privacy`, changeFrequency: "yearly", priority: 0.3 },
    { url: `${SITE}/terms`, changeFrequency: "yearly", priority: 0.3 },
  ];

  const postRoutes: MetadataRoute.Sitemap = posts.map((p) => ({
    url: `${SITE}/blog/${p.slug}`,
    lastModified: p.published_at ? new Date(p.published_at) : undefined,
    changeFrequency: "monthly",
    priority: 0.7,
  }));

  // HostedLanding rows served at the site root via app/[slug]/page.tsx.
  // Higher priority than blog posts because these are conversion-optimized
  // money pages, not informational articles.
  const landingRoutes: MetadataRoute.Sitemap = landings.map((l) => ({
    url: `${SITE}/${l.slug}`,
    lastModified: l.updated_at ? new Date(l.updated_at) : undefined,
    changeFrequency: "monthly",
    priority: 0.85,
  }));

  return [...staticRoutes, ...postRoutes, ...landingRoutes];
}
