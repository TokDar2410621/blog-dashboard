"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import {
  ArrowRight,
  Clock,
  Filter,
} from "lucide-react";
import { GridarMark } from "@/components/GridarMark";
import { readingTime, type BlogPost } from "@/lib/blog-api";

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

function gradientFor(slug: string): string {
  let h = 0;
  for (let i = 0; i < slug.length; i++) h = (h * 31 + slug.charCodeAt(i)) >>> 0;
  const angles = ["135deg", "120deg", "150deg", "180deg", "200deg", "165deg"];
  const angle = angles[h % angles.length];
  const hue = 145 + (h % 30);
  return `linear-gradient(${angle}, hsl(${hue}, 60%, 30%) 0%, hsl(${hue + 10}, 70%, 18%) 50%, #0a0a0a 100%)`;
}

export function BlogList({ posts }: { posts: BlogPost[] }) {
  const [activeTag, setActiveTag] = useState<string | null>(null);

  const allTags = useMemo(() => {
    const s = new Set<string>();
    for (const p of posts) (p.tags ?? []).forEach((t) => s.add(t));
    return Array.from(s).sort();
  }, [posts]);

  const filtered = useMemo(() => {
    if (!activeTag) return posts;
    return posts.filter((p) => p.tags?.includes(activeTag));
  }, [posts, activeTag]);

  const featured = filtered[0];
  const rest = filtered.slice(1);

  if (filtered.length === 0) {
    return (
      <p className="text-zinc-500 text-center py-16">
        {activeTag
          ? "Aucun article pour ce filtre."
          : "Aucun article publié pour l'instant. Reviens bientôt."}
      </p>
    );
  }

  return (
    <>
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

      {featured && (
        <Link href={`/blog/${featured.slug}`} className="block group mb-16">
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
              <div className="flex items-center gap-3 text-xs text-zinc-500 mb-3">
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
                Lire l&apos;article
                <ArrowRight className="h-4 w-4" />
              </div>
            </div>
          </article>
        </Link>
      )}

      {rest.length > 0 && (
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-5">
          {rest.map((post) => (
            <Link key={post.slug} href={`/blog/${post.slug}`} className="group block">
              <article className="h-full rounded-xl overflow-hidden border border-white/10 hover:border-emerald-400/40 transition-colors bg-zinc-900/40 flex flex-col">
                <div className="aspect-[16/9] relative" style={{ background: gradientFor(post.slug) }}>
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
  );
}
