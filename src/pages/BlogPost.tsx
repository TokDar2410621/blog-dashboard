/**
 * Single blog post - /blog/:slug
 */
import { useEffect } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";
import { ArrowLeft, Clock, BookOpen, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { GridarMark } from "@/components/GridarMark";
import { getAllPosts, getPost, readingTime } from "@/lib/posts";

function formatDate(iso: string): string {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleDateString("fr-CA", {
      year: "numeric",
      month: "long",
      day: "numeric",
    });
  } catch {
    return iso;
  }
}

export default function BlogPost() {
  const { slug = "" } = useParams<{ slug: string }>();
  const navigate = useNavigate();
  const post = getPost(slug);

  // Inject per-post Article JSON-LD into <head> so Google sees it.
  useEffect(() => {
    if (!post) return;
    const ld = {
      "@context": "https://schema.org",
      "@type": "Article",
      headline: post.title,
      description: post.excerpt,
      datePublished: post.date,
      author: post.author
        ? { "@type": "Person", name: post.author }
        : { "@type": "Organization", name: "Arivex Studio" },
      publisher: {
        "@type": "Organization",
        name: "Arivex Studio",
        logo: {
          "@type": "ImageObject",
          url: "https://gridar.app/brand/gridar-mark-512.png",
        },
      },
      mainEntityOfPage: `https://gridar.app/blog/${post.slug}`,
      inLanguage: "fr-CA",
      ...(post.cover_image && { image: post.cover_image }),
    };
    const script = document.createElement("script");
    script.type = "application/ld+json";
    script.id = "post-article-ld";
    script.text = JSON.stringify(ld);
    document.head.appendChild(script);
    return () => {
      document.getElementById("post-article-ld")?.remove();
    };
  }, [post]);

  if (!post) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center text-center p-6">
        <div className="max-w-sm space-y-4">
          <BookOpen className="h-12 w-12 text-muted-foreground/50 mx-auto" />
          <h1 className="text-2xl font-bold">Article introuvable</h1>
          <p className="text-muted-foreground">
            L'article <code className="bg-muted px-1.5 py-0.5 rounded text-sm">/blog/{slug}</code> n'existe pas (ou plus).
          </p>
          <Button onClick={() => navigate("/blog")}>
            <ArrowLeft className="h-4 w-4 mr-2" />
            Tous les articles
          </Button>
        </div>
      </div>
    );
  }

  // Adjacent posts (previous + next) for keep-reading at the bottom.
  const all = getAllPosts();
  const idx = all.findIndex((p) => p.slug === post.slug);
  const prev = idx > 0 ? all[idx - 1] : undefined;
  const next = idx < all.length - 1 ? all[idx + 1] : undefined;

  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-30 border-b border-border/50 bg-background/95 backdrop-blur">
        <div className="max-w-4xl mx-auto px-4 md:px-6 h-14 flex items-center gap-3">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate("/blog")}
            className="-ml-2"
          >
            <ArrowLeft className="h-4 w-4 mr-1" />
            Blog
          </Button>
          <div className="h-4 w-px bg-border" />
          <div className="flex items-center gap-2">
            <GridarMark className="h-5 w-5" />
            <span className="font-semibold">Gridar</span>
          </div>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 md:px-6 py-10">
        <article
          className="prose prose-zinc dark:prose-invert max-w-none
                     prose-headings:scroll-mt-20
                     prose-h1:text-4xl prose-h1:font-bold prose-h1:tracking-tight
                     prose-h2:mt-10 prose-h2:border-t prose-h2:border-border/40 prose-h2:pt-6
                     prose-code:before:content-none prose-code:after:content-none
                     prose-code:bg-muted prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:text-[0.9em] prose-code:font-mono
                     prose-pre:bg-muted/50 prose-pre:border prose-pre:border-border/50
                     prose-a:text-primary prose-a:no-underline hover:prose-a:underline"
        >
          <div className="text-sm text-muted-foreground mb-2 flex items-center gap-3">
            {post.date && <span>{formatDate(post.date)}</span>}
            <span className="inline-flex items-center gap-1">
              <Clock className="h-3 w-3" />
              {readingTime(post.body)} min de lecture
            </span>
            {post.author && <span>· par {post.author}</span>}
          </div>
          <h1 className="text-4xl md:text-5xl font-bold tracking-tight mb-6">{post.title}</h1>
          {post.excerpt && (
            <p className="text-lg text-muted-foreground not-prose mb-8">{post.excerpt}</p>
          )}
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            rehypePlugins={[rehypeRaw]}
          >
            {post.body}
          </ReactMarkdown>
        </article>

        {/* Adjacent posts */}
        {(prev || next) && (
          <nav className="mt-16 pt-8 border-t border-border/40 grid sm:grid-cols-2 gap-4">
            {prev ? (
              <Link
                to={`/blog/${prev.slug}`}
                className="group rounded-lg border border-border/50 p-4 hover:border-primary/40 motion-safe:transition-colors"
              >
                <div className="text-xs text-muted-foreground mb-1 inline-flex items-center gap-1">
                  <ArrowLeft className="h-3 w-3" />
                  Précédent
                </div>
                <div className="font-semibold group-hover:text-primary motion-safe:transition-colors">
                  {prev.title}
                </div>
              </Link>
            ) : (
              <div />
            )}
            {next && (
              <Link
                to={`/blog/${next.slug}`}
                className="group rounded-lg border border-border/50 p-4 hover:border-primary/40 motion-safe:transition-colors text-right"
              >
                <div className="text-xs text-muted-foreground mb-1 inline-flex items-center gap-1 justify-end">
                  Suivant
                  <ArrowRight className="h-3 w-3" />
                </div>
                <div className="font-semibold group-hover:text-primary motion-safe:transition-colors">
                  {next.title}
                </div>
              </Link>
            )}
          </nav>
        )}

        {/* Footer CTA - drive blog readers to /login (signup) */}
        <div className="mt-16 rounded-2xl border border-emerald-500/20 bg-emerald-500/5 p-8 text-center">
          <h2 className="text-2xl font-bold tracking-tight mb-2">
            Tu veux générer ce genre d'article sur ton site ?
          </h2>
          <p className="text-muted-foreground mb-6">
            Gridar le fait pour toi - du brief à la publication WordPress / Shopify / Webflow.
          </p>
          <Link to="/login">
            <Button size="lg">
              Essayer gratuitement
              <ArrowRight className="h-4 w-4 ml-2" />
            </Button>
          </Link>
        </div>
      </main>
    </div>
  );
}
