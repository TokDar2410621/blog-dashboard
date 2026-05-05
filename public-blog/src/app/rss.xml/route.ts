import { listPosts } from "@/lib/api";
import { getCurrentSite } from "@/lib/site-context";

export const dynamic = "force-dynamic";

function escape(s: string) {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

export async function GET() {
  const site = await getCurrentSite();
  if (!site) {
    return new Response("Site not configured", { status: 404 });
  }
  const posts = await listPosts(site.id, { language: site.default_language });
  const base = `https://${site.domain}`;

  const items = posts.results
    .map((p) => {
      const link = `${base}/${p.slug}`;
      return `<item>
  <title>${escape(p.title)}</title>
  <link>${link}</link>
  <guid>${link}</guid>
  ${p.published_at ? `<pubDate>${new Date(p.published_at).toUTCString()}</pubDate>` : ""}
  <description>${escape(p.excerpt || "")}</description>
</item>`;
    })
    .join("\n");

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
<title>${escape(site.name)}</title>
<link>${base}</link>
<description>${escape(site.description || "")}</description>
<language>${site.default_language || "fr"}-CA</language>
${items}
</channel>
</rss>`;

  return new Response(xml, {
    headers: {
      "Content-Type": "application/rss+xml; charset=utf-8",
      "Cache-Control": "public, max-age=3600",
    },
  });
}
