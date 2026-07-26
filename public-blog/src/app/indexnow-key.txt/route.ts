import { getCurrentSite } from "@/lib/site-context";

export const dynamic = "force-dynamic";

/**
 * Serves the site's IndexNow ownership key at `/indexnow-key.txt`, resolved
 * from the request Host. Bing / Yandex / Seznam / Naver fetch this to verify
 * the site owns the key before accepting URL submissions. The key is public by
 * design (it only proves control of the domain, grants nothing else).
 */
export async function GET() {
  const site = await getCurrentSite();
  const key = (site?.indexnow_key || "").trim();
  if (!key) {
    return new Response("Not found", { status: 404 });
  }
  return new Response(key, {
    headers: {
      "Content-Type": "text/plain; charset=utf-8",
      "Cache-Control": "public, max-age=3600",
    },
  });
}
