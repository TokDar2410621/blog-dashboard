import { getCurrentSite } from "@/lib/site-context";

export const dynamic = "force-dynamic";

/**
 * Serves the site's IndexNow ownership key, resolved from the request Host.
 * Bing / Yandex / Seznam / Naver fetch this to verify the site owns the key
 * before accepting URL submissions. The key is public by design (it only proves
 * control of the domain, grants nothing else).
 *
 * The engines demand the file be named after the key, so `/<key>.txt` is
 * rewritten here (see next.config.js) with the requested filename in `?key=`;
 * a filename that is not this tenant's key must 404 rather than hand back the
 * real one. `/indexnow-key.txt` with no param stays served for compatibility.
 */
export async function GET(request: Request) {
  const site = await getCurrentSite();
  const key = (site?.indexnow_key || "").trim();
  if (!key) {
    return new Response("Not found", { status: 404 });
  }
  const asked = new URL(request.url).searchParams.get("key");
  if (asked && asked.toLowerCase() !== key.toLowerCase()) {
    return new Response("Not found", { status: 404 });
  }
  return new Response(key, {
    headers: {
      "Content-Type": "text/plain; charset=utf-8",
      "Cache-Control": "public, max-age=3600",
    },
  });
}
