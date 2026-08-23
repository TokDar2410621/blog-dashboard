import Link from "next/link";
import { BookOpen, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";
import { DOCS_NAV, rewriteDocLink } from "@/lib/docs";
import { MarketingHeader } from "@/components/MarketingHeader";
import { MarketingFooter } from "@/components/MarketingFooter";

type Props = {
  /** Current slug (empty string for /docs index). Used to highlight nav item. */
  slug: string;
  /** Markdown content to render, or null for the 404 state. */
  content: string | null;
};

export function DocsShell({ slug, content }: Props) {
  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      <MarketingHeader trail="Docs" />


      <div className="relative z-10 max-w-7xl mx-auto px-4 md:px-6 grid lg:grid-cols-[260px_1fr] gap-8 py-10">
        <aside className="lg:sticky lg:top-24 lg:self-start lg:max-h-[calc(100vh-7rem)] lg:overflow-y-auto">
          <div className="flex items-center justify-between mb-4">
            <span className="text-[11px] font-mono uppercase tracking-wider text-emerald-400/80">
              Documentation
            </span>
            <a
              href="https://github.com/TokDar2410621/blog-dashboard/tree/main/docs"
              target="_blank"
              rel="noopener noreferrer"
              className="text-[11px] text-zinc-500 hover:text-zinc-200 inline-flex items-center gap-1"
            >
              GitHub <ExternalLink className="h-3 w-3" />
            </a>
          </div>
          <nav className="space-y-0.5 text-sm">
            {DOCS_NAV.map((item, i) => {
              if (item.section) {
                return (
                  <div
                    key={`s-${i}`}
                    className="text-[11px] font-mono uppercase tracking-wider text-zinc-500 mt-5 mb-2 first:mt-0 px-2"
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
                      ? "bg-emerald-500/10 text-emerald-300 font-medium border border-emerald-500/20"
                      : "text-zinc-400 hover:bg-white/5 hover:text-zinc-100"
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
              className="prose prose-invert max-w-3xl
                         prose-headings:text-zinc-100 prose-headings:scroll-mt-24
                         prose-h1:text-4xl prose-h1:font-bold prose-h1:tracking-tight
                         prose-h2:mt-12 prose-h2:border-t prose-h2:border-white/10 prose-h2:pt-8 prose-h2:text-2xl
                         prose-h3:text-xl prose-h3:text-zinc-100
                         prose-p:text-zinc-300 prose-li:text-zinc-300
                         prose-strong:text-zinc-100
                         prose-code:before:content-none prose-code:after:content-none
                         prose-code:bg-zinc-900 prose-code:border prose-code:border-white/10 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:text-[0.9em] prose-code:font-mono prose-code:text-emerald-300
                         prose-pre:bg-zinc-900/80 prose-pre:border prose-pre:border-white/10 prose-pre:backdrop-blur-sm
                         prose-table:text-sm prose-th:text-zinc-100
                         prose-th:bg-white/5 prose-th:font-semibold prose-th:border-white/10
                         prose-td:border-white/10
                         prose-a:text-emerald-400 prose-a:no-underline hover:prose-a:text-emerald-300 hover:prose-a:underline
                         prose-hr:border-white/10
                         prose-blockquote:border-emerald-500/30 prose-blockquote:text-zinc-300"
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
              <BookOpen className="h-12 w-12 text-zinc-600 mb-4" />
              <h1 className="text-2xl font-bold mb-2 text-zinc-100">Page introuvable</h1>
              <p className="text-zinc-400 mb-6">
                La page <code className="bg-zinc-900 border border-white/10 px-1.5 py-0.5 rounded text-sm text-emerald-300">/docs/{slug}</code> n&apos;existe pas.
              </p>
              <Link href="/docs">
                <Button className="bg-white text-zinc-950 hover:bg-zinc-200">
                  <BookOpen className="h-4 w-4 mr-2" />
                  Retour a l&apos;index
                </Button>
              </Link>
            </div>
          )}
        </main>
      </div>

      <MarketingFooter />
    </div>
  );
}
