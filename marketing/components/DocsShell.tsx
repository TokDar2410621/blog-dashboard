import Link from "next/link";
import { ArrowLeft, BookOpen, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import { GridarMark } from "@/components/GridarMark";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";
import { DOCS_NAV, rewriteDocLink } from "@/lib/docs";

type Props = {
  /** Current slug (empty string for /docs index). Used to highlight nav item. */
  slug: string;
  /** Markdown content to render, or null for the 404 state. */
  content: string | null;
};

export function DocsShell({ slug, content }: Props) {
  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-30 border-b border-border/50 bg-background/95 backdrop-blur">
        <div className="max-w-7xl mx-auto px-4 md:px-6 h-14 flex items-center gap-3">
          <Link href="/">
            <Button variant="ghost" size="sm" className="-ml-2">
              <ArrowLeft className="h-4 w-4 mr-1" />
              Accueil
            </Button>
          </Link>
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
        <aside className="lg:sticky lg:top-20 lg:self-start lg:max-h-[calc(100vh-6rem)] lg:overflow-y-auto">
          <nav className="space-y-0.5 text-sm">
            {DOCS_NAV.map((item, i) => {
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
                  href={`/docs${item.slug ? `/${item.slug}` : ""}`}
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

        <main className="min-w-0">
          {content ? (
            <article
              className="prose prose-zinc dark:prose-invert max-w-3xl
                         prose-headings:scroll-mt-20
                         prose-h1:text-3xl prose-h1:font-bold
                         prose-h2:mt-10 prose-h2:border-t prose-h2:border-border/40 prose-h2:pt-6
                         prose-code:before:content-none prose-code:after:content-none
                         prose-code:bg-muted prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:text-[0.9em] prose-code:font-mono
                         prose-pre:bg-muted/50 prose-pre:border prose-pre:border-border/50
                         prose-table:text-sm
                         prose-th:bg-muted/30 prose-th:font-semibold
                         prose-a:text-primary prose-a:no-underline hover:prose-a:underline"
            >
              <ReactMarkdown
                remarkPlugins={[remarkGfm]}
                rehypePlugins={[rehypeRaw]}
                components={{
                  a: ({ href, children, ...rest }) => {
                    if (!href) return <a {...rest}>{children}</a>;
                    if (href.startsWith("http") || href.startsWith("mailto:")) {
                      return (
                        <a href={href} target="_blank" rel="noopener noreferrer" {...rest}>
                          {children}
                        </a>
                      );
                    }
                    if (href.startsWith("#")) {
                      return <a href={href} {...rest}>{children}</a>;
                    }
                    return <Link href={rewriteDocLink(href)}>{children}</Link>;
                  },
                }}
              >
                {content}
              </ReactMarkdown>
            </article>
          ) : (
            <div className="flex flex-col items-center justify-center py-24 text-center">
              <BookOpen className="h-12 w-12 text-muted-foreground/50 mb-4" />
              <h1 className="text-2xl font-bold mb-2">Page introuvable</h1>
              <p className="text-muted-foreground mb-6">
                La page <code className="bg-muted px-1.5 py-0.5 rounded text-sm">/docs/{slug}</code> n&apos;existe pas.
              </p>
              <Link href="/docs">
                <Button>
                  <BookOpen className="h-4 w-4 mr-2" />
                  Retour a l&apos;index
                </Button>
              </Link>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
