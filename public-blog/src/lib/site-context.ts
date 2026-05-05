/**
 * Resolve the site for the current request from the request host header.
 *
 * Priority:
 * 1. Explicit env override NEXT_PUBLIC_SITE_ID (single-tenant deploys for testing)
 * 2. Hostname → /public/site-by-domain/<host>/ lookup
 *
 * Returns null if no site matches; the caller decides whether to render a
 * fallback page or 404.
 */
import { headers } from "next/headers";
import { getSiteByDomain, getSite, type Site } from "./api";

export async function getCurrentSite(): Promise<Site | null> {
  // Single-tenant override for local dev / preview deploys
  const overrideId = process.env.NEXT_PUBLIC_SITE_ID;
  if (overrideId) {
    try {
      return await getSite(Number(overrideId));
    } catch {
      return null;
    }
  }

  const headerList = await headers();
  const host = headerList.get("host") || "";
  if (!host) return null;

  // Strip port for local dev
  const hostname = host.split(":")[0];
  return await getSiteByDomain(hostname);
}

export function renderMarkdown(text: string): string {
  // Minimal markdown → HTML for the public blog. We intentionally keep it
  // simple: bold/italic/code/headings/lists/links/images. The dashboard
  // produces well-formed markdown, so we don't need a full parser.
  let html = text.replace(/\r\n/g, "\n");

  // Code blocks (triple backtick)
  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_m, lang, code) => {
    const escaped = code
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
    return `<pre class="bg-zinc-100 dark:bg-zinc-900 rounded p-4 overflow-x-auto text-sm"><code class="language-${lang}">${escaped}</code></pre>`;
  });

  // Headings
  html = html.replace(/^### (.+)$/gm, '<h3 class="text-xl font-display font-semibold mt-8 mb-3">$1</h3>');
  html = html.replace(/^## (.+)$/gm, '<h2 class="text-2xl font-display font-semibold mt-10 mb-4">$1</h2>');
  html = html.replace(/^# (.+)$/gm, '<h1 class="text-3xl font-display font-bold mt-12 mb-5">$1</h1>');

  // Images first (before links since both use brackets)
  html = html.replace(
    /!\[([^\]]*)\]\(([^)]+)\)/g,
    '<img src="$2" alt="$1" class="my-8 w-full rounded-lg border" loading="lazy" />'
  );

  // Links
  html = html.replace(
    /\[([^\]]+)\]\(([^)]+)\)/g,
    '<a href="$2" class="text-brand underline hover:no-underline">$1</a>'
  );

  // Bold + italic
  html = html.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/(?<!\*)\*([^*\n]+)\*(?!\*)/g, "<em>$1</em>");

  // Inline code
  html = html.replace(/`([^`]+)`/g, '<code class="px-1 rounded bg-zinc-100 dark:bg-zinc-800 text-sm">$1</code>');

  // Blockquotes
  html = html.replace(/^> (.+)$/gm, '<blockquote class="border-l-4 border-brand pl-4 italic my-6">$1</blockquote>');

  // Lists (simple)
  html = html.replace(/(^[-*] .+(\n|$))+/gm, (block) => {
    const items = block
      .trim()
      .split("\n")
      .map((l) => l.replace(/^[-*]\s+/, ""))
      .map((l) => `<li>${l}</li>`)
      .join("");
    return `<ul class="list-disc pl-6 space-y-2 my-4">${items}</ul>`;
  });

  // Paragraphs (any remaining double-newline-separated block that isn't HTML)
  html = html
    .split(/\n\n+/)
    .map((block) => {
      const trimmed = block.trim();
      if (!trimmed) return "";
      if (/^<(h\d|ul|ol|blockquote|pre|img|p|div)/.test(trimmed)) return trimmed;
      return `<p class="my-4 leading-relaxed">${trimmed}</p>`;
    })
    .join("\n");

  return html;
}

export function getThemeStyle(site: Site): React.CSSProperties {
  const cfg = site.theme_config || {};
  const style: Record<string, string> = {};
  if (cfg.brand_color) style["--brand-color"] = cfg.brand_color;
  if (cfg.brand_fg) style["--brand-fg"] = cfg.brand_fg;
  if (cfg.font_sans) style["--font-sans"] = cfg.font_sans;
  if (cfg.font_display) style["--font-display"] = cfg.font_display;
  return style as React.CSSProperties;
}
