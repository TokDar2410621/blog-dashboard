/**
 * Blog index. Public, indexable, served at /blog.
 *
 * Layout: dark hero with brand, then a 'featured' card for the most recent
 * post, then a 2-column grid of the rest. Tags are clickable filters that
 * narrow the list client-side. Reuses the Landing's emerald glow + grid
 * background for visual cohesion with the marketing surface.
 */
import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowLeft,
  ArrowRight,
  Clock,
  Filter,
  Loader2,
  Sparkles,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { GridarMark } from "@/components/GridarMark";
import { fetchBlogPosts, readingTime, type BlogPost } from "@/lib/blog-api";

function formatDate(iso: string): string {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleDateString("fr-CA", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch {
    return iso;
  }
}

/** Pick a deterministic emerald gradient per slug so each card has a
 *  unique cover without us shipping image assets. Hash the slug to one of
 *  6 angles and slight hue shifts. */
function gradientFor(slug: string): string {
  let h = 0;
  for (let i = 0; i < slug.length; i++) h = (h * 31 + slug.charCodeAt(i)) >>> 0;
  const angles = ["135deg", "120deg", "150deg", "180deg", "200deg", "165deg"];
  const angle = angles[h % angles.length];
  const hue = 145 + (h % 30);
  return `linear-gradient(${angle}, hsl(${hue}, 60%, 30%) 0%, hsl(${hue + 10}, 70%, 18%) 50%, #0a0a0a 100%)`;
}

export default function Blog() {
  const navigate = useNavigate();
  const [activeTag, setActiveTag] = useState<string | null>(null);

  // Posts come from the Gridar backend HostedPost table (Site #1, hosted mode).
  // 5-min stale time because content updates are not real-time; long enough
  // to avoid refetch noise, short enough to pick up new articles on F5.
  const { data: posts = [], isLoading } = useQuery({
    queryKey: ["blog", "posts"],
    queryFn: fetchBlogPosts,
    staleTime: 5 * 60 * 1000,
  });

  const allTags = useMemo(() => {
    const s = new Set<string>();
    for (const p of posts) (p.tags ?? []).forEach((t) => s.add(t));
    return Array.from(s).sort();
  }, [posts]);

  const filtered: BlogPost[] = useMemo(() => {
    if (!activeTag) return posts;
    return posts.filter((p) => p.tags?.includes(activeTag));
  }, [posts, activeTag]);

  const featured = filtered[0];
  const rest = filtered.slice(1);

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      {/* Sticky top nav, same pattern as Docs/Landing */}
      <header className="sticky top-0 z-30 border-b border-white/5 bg-zinc-950/70 backdrop-blur-xl">
        <div className="max-w-6xl mx-auto px-4 md:px-6 h-14 flex items-center gap-3">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate("/")}
            className="-ml-2 text-zinc-400 hover:text-white hover:bg-white/5"
          >
            <ArrowLeft className="h-4 w-4 mr-1" />
            Accueil
          </Button>
          <div className="h-4 w-px bg-white/10" />
          <div className="flex items-center gap-2">
            <GridarMark className="h-5 w-5" />
            <span className="font-semibold">Gridar</span>
            <span className="text-zinc-500 hidden sm:inline">/ Blog</span>
          </div>
          <div className="flex-1" />
          <Link to="/login">
            <Button size="sm" className="bg-white text-zinc-950 hover:bg-zinc-200">
              Commencer
            </Button>
          </Link>
        </div>
      </header>

      {/* Hero */}
      <section className="relative overflow-hidden border-b border-white/5">
        <div
          aria-hidden
          className="absolute inset-0 pointer-events-none"
          style={{
            background:
              "radial-gradient(60% 50% at 50% 20%, rgba(16,185,129,0.18), transparent 70%)",
          }}
        />
        <div className="relative max-w-4xl mx-auto px-4 md:px-6 py-20 md:py-28 text-center">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-emerald-400/30 bg-emerald-400/10 text-emerald-300 text-xs font-mono uppercase tracking-wider mb-6">
            <Sparkles className="h-3 w-3" />
            Tactiques SEO QC
          </div>
          <h1 className="text-5xl md:text-6xl font-bold tracking-tight leading-[1.05] mb-5">
            Le blog{" "}
            <span className="bg-gradient-to-br from-emerald-300 via-emerald-400 to-cyan-400 bg-clip-text text-transparent">
              Gridar
            </span>
            .
          </h1>
          <p className="text-lg text-zinc-400 max-w-2xl mx-auto leading-relaxed">
            Tactiques SEO concrètes pour PME québécoises. Chaque article est
            rédigé, audité et publié avec Gridar. On dogfoode notre propre produit.
          </p>
        </div>
      </section>

      <main className="max-w-6xl mx-auto px-4 md:px-6 py-12">
        {/* Tag filter row */}
        {allTags.length > 0 && (
          <div className="flex items-center gap-2 mb-12 flex-wrap">
            <span className="inline-flex items-center gap-1.5 text-xs uppercase tracking-wider text-zinc-500 mr-1">
              <Filter className="h-3 w-3" />
              Filtrer
            </span>
            <button
              type="button"
              onClick={() => setActiveTag(null)}
              className={`text-xs px-3 py-1 rounded-full border transition-colors ${
                activeTag === null
                  ? "border-emerald-400/50 bg-emerald-400/10 text-emerald-300"
                  : "border-white/10 text-zinc-400 hover:border-white/20 hover:text-white"
              }`}
            >
              Tous
            </button>
            {allTags.map((tag) => (
              <button
                key={tag}
                type="button"
                onClick={() => setActiveTag(activeTag === tag ? null : tag)}
                className={`text-xs px-3 py-1 rounded-full border transition-colors ${
                  activeTag === tag
                    ? "border-emerald-400/50 bg-emerald-400/10 text-emerald-300"
                    : "border-white/10 text-zinc-400 hover:border-white/20 hover:text-white"
                }`}
              >
                {tag}
              </button>
            ))}
          </div>
        )}

        {isLoading ? (
          <div className="flex items-center justify-center py-16 text-zinc-500">
            <Loader2 className="h-6 w-6 animate-spin mr-2" />
            Chargement des articles...
          </div>
        ) : filtered.length === 0 ? (
          <p className="text-zinc-500 text-center py-16">
            {activeTag
              ? "Aucun article pour ce filtre."
              : "Aucun article publié pour l'instant. Reviens bientôt."}
          </p>
        ) : (
          <>
            {/* Featured (latest) */}
            {featured && (
              <Link to={`/blog/${featured.slug}`} className="block group mb-16">
                <article className="relative grid md:grid-cols-2 gap-0 rounded-2xl overflow-hidden border border-white/10 hover:border-emerald-400/40 transition-colors bg-zinc-900/40">
                  <div
                    className="aspect-[4/3] md:aspect-auto md:min-h-[320px] relative"
                    style={{ background: gradientFor(featured.slug) }}
                  >
                    <div className="absolute inset-0 flex items-center justify-center opacity-40 group-hover:opacity-60 transition-opacity">
                      <GridarMark className="h-32 w-32" />
                    </div>
                    <span className="absolute top-4 left-4 text-[10px] uppercase tracking-wider px-2 py-1 rounded-full bg-black/60 backdrop-blur border border-white/10 text-emerald-300 font-mono">
                      À la une
                    </span>
                  </div>
                  <div className="p-8 md:p-10 flex flex-col justify-center">
                    <div className="flex flex-wrap items-center gap-3 text-xs text-zinc-500 mb-3">
                      {featured.published_at && <span>{formatDate(featured.published_at)}</span>}
                      <span className="inline-flex items-center gap-1">
                        <Clock className="h-3 w-3" />
                        {readingTime(featured.content)} min
                      </span>
                      {featured.tags?.[0] && (
                        <span className="px-1.5 py-0.5 rounded bg-white/5 border border-white/10 text-zinc-400">
                          {featured.tags[0]}
                        </span>
                      )}
                    </div>
                    <h2 className="text-2xl md:text-3xl font-bold tracking-tight leading-tight mb-3 group-hover:text-emerald-300 transition-colors">
                      {featured.title}
                    </h2>
                    {featured.excerpt && (
                      <p className="text-zinc-400 leading-relaxed mb-5 line-clamp-3">
                        {featured.excerpt}
                      </p>
                    )}
                    <div className="inline-flex items-center gap-1 text-sm text-emerald-300 group-hover:gap-2 transition-all">
                      Lire l'article
                      <ArrowRight className="h-4 w-4" />
                    </div>
                  </div>
                </article>
              </Link>
            )}

            {/* Grid of remaining posts */}
            {rest.length > 0 && (
              <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-5">
                {rest.map((post) => (
                  <Link
                    key={post.slug}
                    to={`/blog/${post.slug}`}
                    className="group block"
                  >
                    <article className="h-full rounded-xl overflow-hidden border border-white/10 hover:border-emerald-400/40 transition-colors bg-zinc-900/40 flex flex-col">
                      <div
                        className="aspect-[16/9] relative"
                        style={{ background: gradientFor(post.slug) }}
                      >
                        <div className="absolute inset-0 flex items-center justify-center opacity-30 group-hover:opacity-50 transition-opacity">
                          <GridarMark className="h-16 w-16" />
                        </div>
                      </div>
                      <div className="p-6 flex flex-col flex-1">
                        <div className="flex items-center gap-3 text-xs text-zinc-500 mb-2">
                          {post.published_at && <span>{formatDate(post.published_at)}</span>}
                          <span className="inline-flex items-center gap-1">
                            <Clock className="h-3 w-3" />
                            {readingTime(post.content)} min
                          </span>
                        </div>
                        <h3 className="text-lg font-semibold tracking-tight leading-snug mb-2 group-hover:text-emerald-300 transition-colors">
                          {post.title}
                        </h3>
                        {post.excerpt && (
                          <p className="text-sm text-zinc-400 leading-relaxed line-clamp-3 flex-1">
                            {post.excerpt}
                          </p>
                        )}
                        {post.tags && post.tags.length > 0 && (
                          <div className="mt-4 flex flex-wrap gap-1.5">
                            {post.tags.slice(0, 3).map((tag) => (
                              <span
                                key={tag}
                                className="text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded bg-white/5 border border-white/10 text-zinc-500"
                              >
                                {tag}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    </article>
                  </Link>
                ))}
              </div>
            )}
          </>
        )}

        {/* CTA at bottom */}
        <section className="mt-24 rounded-2xl border border-emerald-500/20 bg-emerald-500/5 p-10 md:p-12 text-center relative overflow-hidden">
          <div
            aria-hidden
            className="absolute inset-0 pointer-events-none"
            style={{
              background:
                "radial-gradient(60% 50% at 50% 50%, rgba(16,185,129,0.18), transparent 70%)",
            }}
          />
          <div className="relative">
            <h2 className="text-3xl font-bold tracking-tight mb-3">
              Tu veux générer ce genre d'article sur ton site ?
            </h2>
            <p className="text-zinc-400 mb-8 max-w-xl mx-auto">
              Gridar le fait pour toi. Du brief au déploiement WordPress, Shopify
              ou Webflow. Aucune carte requise pour essayer.
            </p>
            <Link to="/login">
              <Button size="lg" className="bg-white text-zinc-950 hover:bg-zinc-200">
                <Sparkles className="h-4 w-4 mr-2" />
                Commencer gratuitement
              </Button>
            </Link>
          </div>
        </section>
      </main>
    </div>
  );
}
