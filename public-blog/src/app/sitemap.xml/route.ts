import { listPosts } from "@/lib/api";
import { getCurrentSite } from "@/lib/site-context";

export const dynamic = "force-dynamic";

export async function GET() {
  const site = await getCurrentSite();
  if (!site) {
    return new Response("Site not configured", { status: 404 });
  }
  const posts = await listPosts(site.id, { language: site.default_language });
  const base = `https://${site.domain}`;

  const urls = [
    `<url><loc>${base}/</loc><changefreq>daily</changefreq><priority>1.0</priority></url>`,
    ...posts.results.map(
      (p) =>
        `<url><loc>${base}/${p.slug}</loc>${
          p.published_at ? `<lastmod>${p.published_at}</lastmod>` : ""
        }<changefreq>weekly</changefreq><priority>0.8</priority></url>`
    ),
  ].join("\n");

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${urls}
</urlset>`;

  return new Response(xml, {
    headers: {
      "Content-Type": "application/xml; charset=utf-8",
      "Cache-Control": "public, max-age=3600",
    },
  });
}
