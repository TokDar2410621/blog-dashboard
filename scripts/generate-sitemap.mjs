/**
 * Generates public/sitemap.xml from the actual content on disk.
 *
 * Scans:
 *   - Static routes (hard-coded list below)
 *   - posts/*.md (blog)
 *   - docs/**\/*.md (product docs)
 *
 * Run automatically before every `npm run build` (see "prebuild" in
 * package.json). Also safe to call manually:  `npm run sitemap`.
 */
import { readdir, readFile, writeFile } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, "..");
const SITE = "https://gridar.app";

/** Routes that are part of the marketing surface (not auth-walled). */
const STATIC_ROUTES = [
  { path: "/", changefreq: "weekly", priority: "1.0" },
  { path: "/blog", changefreq: "daily", priority: "0.9" },
  { path: "/docs", changefreq: "weekly", priority: "0.9" },
  { path: "/api-docs", changefreq: "monthly", priority: "0.7" },
  { path: "/privacy", changefreq: "yearly", priority: "0.3" },
  { path: "/terms", changefreq: "yearly", priority: "0.3" },
];

/** Recursively walk a folder, return all *.md files relative to the root. */
async function walkMd(dir, baseDir) {
  const out = [];
  let entries;
  try {
    entries = await readdir(dir, { withFileTypes: true });
  } catch {
    return out;
  }
  for (const entry of entries) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) {
      out.push(...(await walkMd(full, baseDir)));
    } else if (entry.isFile() && entry.name.endsWith(".md")) {
      out.push(full.slice(baseDir.length + 1).replace(/\\/g, "/"));
    }
  }
  return out;
}

/** Extract YAML frontmatter date if present. Returns ISO string or null. */
async function extractDate(filePath) {
  try {
    const raw = await readFile(filePath, "utf-8");
    const m = raw.match(/^---\s*\n([\s\S]*?)\n---/);
    if (!m) return null;
    const dateMatch = m[1].match(/^date:\s*(.+?)\s*$/m);
    if (!dateMatch) return null;
    const value = dateMatch[1].replace(/^["']|["']$/g, "");
    if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return null;
    return value;
  } catch {
    return null;
  }
}

function escape(str) {
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&apos;");
}

function urlBlock({ loc, lastmod, changefreq, priority }) {
  const parts = [`    <loc>${escape(loc)}</loc>`];
  if (lastmod) parts.push(`    <lastmod>${lastmod}</lastmod>`);
  if (changefreq) parts.push(`    <changefreq>${changefreq}</changefreq>`);
  if (priority) parts.push(`    <priority>${priority}</priority>`);
  return `  <url>\n${parts.join("\n")}\n  </url>`;
}

async function main() {
  const urls = [];

  for (const r of STATIC_ROUTES) {
    urls.push(
      urlBlock({
        loc: `${SITE}${r.path}`,
        changefreq: r.changefreq,
        priority: r.priority,
      })
    );
  }

  // Blog posts
  const postsDir = join(ROOT, "posts");
  const postFiles = await walkMd(postsDir, postsDir);
  for (const file of postFiles) {
    const slug = file.replace(/\.md$/, "");
    const date = await extractDate(join(postsDir, file));
    urls.push(
      urlBlock({
        loc: `${SITE}/blog/${slug}`,
        lastmod: date || undefined,
        changefreq: "monthly",
        priority: "0.7",
      })
    );
  }

  // Docs (each .md becomes /docs/<slug>)
  const docsDir = join(ROOT, "docs");
  const docFiles = await walkMd(docsDir, docsDir);
  for (const file of docFiles) {
    // README.md at any level collapses to the parent's path.
    const slug = file.replace(/\.md$/, "").replace(/\/README$/, "").replace(/^README$/, "");
    const loc = slug ? `${SITE}/docs/${slug}` : `${SITE}/docs`;
    // Skip /docs (already in STATIC_ROUTES)
    if (loc === `${SITE}/docs`) continue;
    urls.push(
      urlBlock({
        loc,
        changefreq: "monthly",
        priority: "0.6",
      })
    );
  }

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${urls.join("\n")}
</urlset>
`;

  const outPath = join(ROOT, "public", "sitemap.xml");
  await writeFile(outPath, xml, "utf-8");
  console.log(`sitemap.xml: ${urls.length} URLs -> ${outPath}`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
