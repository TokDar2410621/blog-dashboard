import { getCurrentSite } from "@/lib/site-context";

export const dynamic = "force-dynamic";

export async function GET() {
  const site = await getCurrentSite();
  const sitemap = site ? `https://${site.domain}/sitemap.xml` : "";
  const body = `User-agent: *
Allow: /
${sitemap ? `Sitemap: ${sitemap}` : ""}`;
  return new Response(body, {
    headers: { "Content-Type": "text/plain; charset=utf-8" },
  });
}
