/**
 * Server-side helpers for the Docs section. Walks the repo-root docs/
 * folder at build time, returns all slugs + each markdown file's content.
 * Mirrors the slug rules of the Vite implementation:
 *   docs/README.md             -> ''        (index)
 *   docs/foo.md                -> 'foo'
 *   docs/foo/README.md         -> 'foo'
 *   docs/foo/bar.md            -> 'foo/bar'
 */
import { readFile, readdir } from "node:fs/promises";
import path from "node:path";

const DOCS_DIR = path.resolve(process.cwd(), "..", "docs");

async function walk(dir: string): Promise<string[]> {
  const out: string[] = [];
  let entries;
  try {
    entries = await readdir(dir, { withFileTypes: true });
  } catch {
    return out;
  }
  for (const e of entries) {
    const full = path.join(dir, e.name);
    if (e.isDirectory()) {
      out.push(...(await walk(full)));
    } else if (e.isFile() && e.name.endsWith(".md")) {
      out.push(full);
    }
  }
  return out;
}

function fileToSlug(filePath: string): string {
  const rel = path.relative(DOCS_DIR, filePath).replace(/\\/g, "/");
  const trimmed = rel.replace(/\.md$/, "").replace(/\/README$/, "");
  return trimmed === "README" ? "" : trimmed;
}

export async function listDocSlugs(): Promise<string[]> {
  const files = await walk(DOCS_DIR);
  return files.map(fileToSlug);
}

export async function readDoc(slug: string): Promise<string | null> {
  const files = await walk(DOCS_DIR);
  for (const f of files) {
    if (fileToSlug(f) === slug) {
      return readFile(f, "utf-8");
    }
  }
  return null;
}

export const DOCS_NAV: { label: string; slug: string; section?: boolean }[] = [
  { label: "Demarrer", slug: "", section: true },
  { label: "Vue d'ensemble", slug: "" },
  { label: "Demarrage rapide", slug: "getting-started" },
  { label: "Reference Site Settings", slug: "site-settings" },

  { label: "Connecter ton site", slug: "connect", section: true },
  { label: "Comparaison des modes", slug: "connect" },
  { label: "WordPress", slug: "connect/wordpress" },
  { label: "Shopify", slug: "connect/shopify" },
  { label: "Webflow", slug: "connect/webflow" },
  { label: "Heberge (sous-domaine)", slug: "connect/hosted" },
  { label: "Externe (API-pull)", slug: "connect/external" },

  { label: "Workflows", slug: "generate-article", section: true },
  { label: "Generer un article", slug: "generate-article" },
  { label: "Editeur d'articles", slug: "editor" },
  { label: "Articles multilingues", slug: "translation" },
  { label: "Gestion des images", slug: "images" },

  { label: "Outils SEO", slug: "seo-tools", section: true },
  { label: "Outils SEO complets", slug: "seo-tools" },
  { label: "Outils de recherche", slug: "research" },
  { label: "Google Search Console", slug: "gsc" },

  { label: "Compte et facturation", slug: "plans-credits", section: true },
  { label: "Plans, credits et quotas", slug: "plans-credits" },
  { label: "Multi-domaines (Agence)", slug: "multi-domain" },
  { label: "API REST publique", slug: "api" },
  { label: "Integrations (MCP, n8n)", slug: "integrations" },

  { label: "Recettes pratiques", slug: "use-cases", section: true },
  { label: "10 use cases", slug: "use-cases" },

  { label: "Aide", slug: "faq", section: true },
  { label: "FAQ", slug: "faq" },
  { label: "Depannage", slug: "troubleshooting" },
  { label: "Changelog", slug: "changelog" },
];

export function rewriteDocLink(href: string): string {
  if (!href || href.startsWith("http") || href.startsWith("#") || href.startsWith("mailto:")) {
    return href;
  }
  let s = href.replace(/\.md$/, "").replace(/\/README$/, "");
  s = s.replace(/^\.\//, "").replace(/^\.\.\//, "");
  if (s.startsWith("/")) return `/docs${s}`;
  return `/docs/${s}`;
}
