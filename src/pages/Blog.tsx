/**
 * Blog index — lists every post in /posts/, newest first.
 * Public, indexable, served at /blog.
 */
import { Link, useNavigate } from "react-router-dom";
import { ArrowLeft, Clock } from "lucide-react";
import { Button } from "@/components/ui/button";
import { GridarMark } from "@/components/GridarMark";
import { getAllPosts, readingTime } from "@/lib/posts";

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

export default function Blog() {
  const navigate = useNavigate();
  const posts = getAllPosts();

  return (
    <div className="min-h-screen bg-background">
      <header className="sticky top-0 z-30 border-b border-border/50 bg-background/95 backdrop-blur">
        <div className="max-w-4xl mx-auto px-4 md:px-6 h-14 flex items-center gap-3">
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
            <GridarMark className="h-5 w-5" />
            <span className="font-semibold">Gridar</span>
            <span className="text-muted-foreground hidden sm:inline">/ Blog</span>
          </div>
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-4 md:px-6 py-12">
        <div className="mb-12">
          <h1 className="text-4xl md:text-5xl font-bold tracking-tight mb-3">
            Le blog Gridar
          </h1>
          <p className="text-lg text-muted-foreground">
            Tactiques SEO concrètes pour PME québécoises. Tout est rédigé,
            audité et publié avec Gridar — on dogfoode notre propre produit.
          </p>
        </div>

        {posts.length === 0 ? (
          <p className="text-muted-foreground">
            Aucun article publié pour l'instant. Reviens bientôt.
          </p>
        ) : (
          <div className="space-y-8">
            {posts.map((post) => (
              <article key={post.slug} className="group">
                <Link to={`/blog/${post.slug}`} className="block">
                  <div className="flex items-center gap-3 text-xs text-muted-foreground mb-2">
                    {post.date && <span>{formatDate(post.date)}</span>}
                    {post.date && (
                      <span className="inline-flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        {readingTime(post.body)} min
                      </span>
                    )}
                    {post.tags?.map((tag) => (
                      <span
                        key={tag}
                        className="px-1.5 py-0.5 rounded bg-muted text-muted-foreground"
                      >
                        {tag}
                      </span>
                    ))}
                  </div>
                  <h2 className="text-2xl font-bold tracking-tight group-hover:text-primary motion-safe:transition-colors mb-2">
                    {post.title}
                  </h2>
                  {post.excerpt && (
                    <p className="text-muted-foreground leading-relaxed">
                      {post.excerpt}
                    </p>
                  )}
                </Link>
              </article>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
