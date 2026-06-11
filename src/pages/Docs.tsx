/**
 * Public product documentation served at /docs/*.
 *
 * Loads every .md file under repo-root /docs/ at build time via Vite's
 * import.meta.glob with `?raw`. No plugin required - just native Vite.
 *
 * URL → file mapping:
 *   /docs           → docs/README.md
 *   /docs/<slug>    → docs/<slug>.md
 *   /docs/connect   → docs/connect/README.md
 *   /docs/connect/<slug> → docs/connect/<slug>.md
 */
import { useMemo } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";
import { ArrowLeft, BookOpen, ExternalLink } from "lucide-react";
import { GridarMark } from "@/components/GridarMark";
import { Button } from "@/components/ui/button";

// Load every doc at build time as raw string.
// docs/ moved into marketing/ (the Next.js app owns the public docs since
// the gridar.app cutover); this page reads the same source until the SPA
// copy is retired. Relative path from THIS file: src/pages/ -> ../../marketing/docs
const docFiles = import.meta.glob("../../marketing/docs/**/*.md", {
  query: "?raw",
  import: "default",
  eager: true,
}) as Record<string, string>;

/** Convert a Vite glob path to a clean URL slug.
 *  '../../marketing/docs/README.md'            -> ''   (index)
 *  '../../marketing/docs/getting-started.md'   -> 'getting-started'
 *  '../../marketing/docs/connect/README.md'    -> 'connect'
 *  '../../marketing/docs/connect/wordpress.md' -> 'connect/wordpress'
 */
function pathToSlug(p: string): string {
  return p
    .replace("../../marketing/docs/", "")
    .replace(/\.md$/, "")
    .replace(/\/README$/, "")
    .replace(/^README$/, "");
}

/** Inverse: slug -> file path lookup. */
const slugMap: Record<string, string> = {};
for (const path in docFiles) {
  slugMap[pathToSlug(path)] = path;
}

// Sidebar navigation tree, hand-curated for the right reading order.
const NAV: { label: string; slug: string; section?: boolean }[] = [
  { label: "Démarrer", slug: "", section: true },
  { label: "Vue d'ensemble", slug: "" },
  { label: "Démarrage rapide", slug: "getting-started" },
  { label: "Référence Site Settings", slug: "site-settings" },

  { label: "Connecter ton site", slug: "connect", section: true },
  { label: "Comparaison des modes", slug: "connect" },
  { label: "WordPress", slug: "connect/wordpress" },
  { label: "Shopify", slug: "connect/shopify" },
  { label: "Webflow", slug: "connect/webflow" },
  { label: "Hébergé (sous-domaine)", slug: "connect/hosted" },
  { label: "Externe (API-pull)", slug: "connect/external" },

  { label: "Workflows", slug: "generate-article", section: true },
  { label: "Générer un article", slug: "generate-article" },
  { label: "Éditeur d'articles", slug: "editor" },
  { label: "Articles multilingues", slug: "translation" },
  { label: "Gestion des images", slug: "images" },

  { label: "Outils SEO", slug: "seo-tools", section: true },
  { label: "Outils SEO complets", slug: "seo-tools" },
  { label: "Outils de recherche", slug: "research" },
  { label: "Google Search Console", slug: "gsc" },

  { label: "Compte et facturation", slug: "plans-credits", section: true },
  { label: "Plans, crédits et quotas", slug: "plans-credits" },
  { label: "Multi-domaines (Agence)", slug: "multi-domain" },
  { label: "API REST publique", slug: "api" },
  { label: "Intégrations (MCP, n8n)", slug: "integrations" },

  { label: "Recettes pratiques", slug: "use-cases", section: true },
  { label: "10 use cases", slug: "use-cases" },

  { label: "Aide", slug: "faq", section: true },
  { label: "FAQ", slug: "faq" },
  { label: "Dépannage", slug: "troubleshooting" },
  { label: "Changelog", slug: "changelog" },
];

function rewriteRelativeLink(href: string): string {
  // Markdown uses relative paths between docs (e.g., 'connect/wordpress.md',
  // '../api.md'). Rewrite them to /docs/<slug> so they navigate inside React Router.
  if (!href || href.startsWith("http") || href.startsWith("#")) return href;
  // Strip .md extension and trailing /README
  let s = href.replace(/\.md$/, "").replace(/\/README$/, "");
  // Resolve '../' within the slug space - simplest is to drop them since the
  // doc tree is shallow (max 1 nesting level: /docs/connect/<slug>).
  s = s.replace(/^\.\//, "").replace(/^\.\.\//, "");
  if (s.startsWith("/")) return `/docs${s}`;
  return `/docs/${s}`;
}

export default function Docs() {
  const location = useLocation();
  const navigate = useNavigate();

  // /docs       -> ''
  // /docs/      -> ''
  // /docs/foo   -> 'foo'
  // /docs/foo/bar -> 'foo/bar'
  const slug = location.pathname
    .replace(/^\/docs\/?/, "")
    .replace(/\/$/, "");

  const md = useMemo(() => {
    const path = slugMap[slug];
    if (!path) return null;
    return docFiles[path];
  }, [slug]);

  return (
    <div className="min-h-screen bg-background">
      {/* Top bar */}
      <header className="sticky top-0 z-30 border-b border-border/50 bg-background/95 backdrop-blur">
        <div className="max-w-7xl mx-auto px-4 md:px-6 h-14 flex items-center gap-3">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate("/")}
            className="-ml-2"
          >
            <ArrowLeft className="h-4 w-4 mr-1" />
            Accueil
          </Button>
          <div className="h-4 w-px bg-border" />
          <div className="flex items-center gap-2">
            <GridarMark className="h-5 w-5 text-primary" />
            <span className="font-semibold">Gridar</span>
            <span className="text-muted-foreground hidden sm:inline">/ Docs</span>
          </div>
          <div className="flex-1" />
          <a
            href="https://github.com/TokDar2410621/blog-dashboard/tree/main/docs"
            target="_blank"
            rel="noopener noreferrer"
            className="text-xs text-muted-foreground hover:text-foreground inline-flex items-center gap-1"
          >
            Sur GitHub <ExternalLink className="h-3 w-3" />
          </a>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 md:px-6 grid lg:grid-cols-[260px_1fr] gap-8 py-8">
        {/* Sidebar nav */}
        <aside className="order-last lg:order-first lg:sticky lg:top-20 lg:self-start lg:max-h-[calc(100vh-6rem)] lg:overflow-y-auto">
          <nav className="space-y-0.5 text-sm">
            {NAV.map((item, i) => {
              if (item.section) {
                return (
                  <div
                    key={`s-${i}`}
                    className="text-[11px] font-mono uppercase tracking-wider text-muted-foreground mt-5 mb-2 first:mt-0 px-2"
                  >
                    {item.label}
                  </div>
                );
              }
              const isActive = slug === item.slug;
              return (
                <Link
                  key={item.slug || "index"}
                  to={`/docs${item.slug ? `/${item.slug}` : ""}`}
                  className={`block px-2 py-1.5 rounded text-sm transition-colors ${
                    isActive
                      ? "bg-primary/10 text-primary font-medium"
                      : "text-muted-foreground hover:bg-muted hover:text-foreground"
                  }`}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </aside>

        {/* Main content */}
        <main className="min-w-0">
          {md ? (
            <article
              className="prose prose-zinc dark:prose-invert max-w-3xl
                         prose-headings:scroll-mt-20
                         prose-h1:text-3xl prose-h1:font-bold
                         prose-h2:mt-10 prose-h2:border-t prose-h2:border-border/40 prose-h2:pt-6
                         prose-code:before:content-none prose-code:after:content-none
                         prose-code:bg-muted prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:text-[0.9em] prose-code:font-mono
                         [&_:not(pre)>code]:break-all
                         prose-pre:bg-muted/50 prose-pre:border prose-pre:border-border/50
                         prose-table:text-sm
                         prose-th:bg-muted/30 prose-th:font-semibold
                         prose-a:text-primary prose-a:no-underline hover:prose-a:underline"
            >
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                rehypePlugins={[rehypeRaw]}
                components={{
                  // Rewrite internal links to React Router navigation
                  a: ({ href, children, ...rest }) => {
                    if (!href) return <a {...rest}>{children}</a>;
                    if (href.startsWith("http") || href.startsWith("mailto:")) {
                      return (
                        <a
                          href={href}
                          target="_blank"
                          rel="noopener noreferrer"
                          {...rest}
                        >
                          {children}
                        </a>
                      );
                    }
                    if (href.startsWith("#")) {
                      return (
                        <a href={href} {...rest}>
                          {children}
                        </a>
                      );
                    }
                    return (
                      <Link to={rewriteRelativeLink(href)}>{children}</Link>
                    );
                  },
                  table: ({ node: _node, ...props }) => (
                    <div className="overflow-x-auto">
                      <table {...props} />
                    </div>
                  ),
                }}
              >
                {md}
              </ReactMarkdown>
            </article>
          ) : (
            <div className="flex flex-col items-center justify-center py-24 text-center">
              <BookOpen className="h-12 w-12 text-muted-foreground/50 mb-4" />
              <h1 className="text-2xl font-bold mb-2">Page introuvable</h1>
              <p className="text-muted-foreground mb-6">
                La page <code className="bg-muted px-1.5 py-0.5 rounded text-sm">/docs/{slug}</code> n'existe pas.
              </p>
              <Button onClick={() => navigate("/docs")}>
                <BookOpen className="h-4 w-4 mr-2" />
                Retour à l'index
              </Button>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
