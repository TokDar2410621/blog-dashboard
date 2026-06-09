import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeRaw from "rehype-raw";
import {
  ArrowLeft,
  ArrowRight,
  Clock,
  Sparkles,
  User,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { GridarMark } from "@/components/GridarMark";
import { ReadingProgress } from "@/components/ReadingProgress";
import { fetchBlogPost, fetchBlogPosts, readingTime } from "@/lib/blog-api";

export const revalidate = 3600;

// SSG: pre-render every published post at build time. The list itself is
// re-fetched on each redeploy + every hour via the ISR window on /blog.
export async function generateStaticParams() {
  const posts = await fetchBlogPosts();
  return posts.map((p) => ({ slug: p.slug }));
}

type PageProps = {
  params: Promise<{ slug: string }>;
};

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { slug } = await params;
  const post = await fetchBlogPost(slug);
  if (!post) return { title: "Article introuvable" };

  return {
    title: post.title,
    description: post.excerpt,
    alternates: { canonical: `/blog/${post.slug}` },
    openGraph: {
      type: "article",
      title: post.title,
      description: post.excerpt,
      url: `https://gridar.app/blog/${post.slug}`,
      publishedTime: post.published_at || undefined,
      authors: post.author ? [post.author] : undefined,
      images: post.cover_image ? [{ url: post.cover_image }] : undefined,
      locale: "fr_CA",
    },
    twitter: {
      card: "summary_large_image",
      title: post.title,
      description: post.excerpt,
      images: post.cover_image ? [post.cover_image] : undefined,
    },
  };
}

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

function gradientFor(slug: string): string {
  let h = 0;
  for (let i = 0; i < slug.length; i++) h = (h * 31 + slug.charCodeAt(i)) >>> 0;
  const angles = ["135deg", "120deg", "150deg", "180deg", "200deg", "165deg"];
  const angle = angles[h % angles.length];
  const hue = 145 + (h % 30);
  return `linear-gradient(${angle}, hsl(${hue}, 60%, 30%) 0%, hsl(${hue + 10}, 70%, 18%) 50%, #0a0a0a 100%)`;
}

type Heading = { id: string; text: string; level: 2 | 3 };

function slugify(text: string): string {
  return text
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/[^a-z0-9\s-]/g, "")
    .trim()
    .replace(/\s+/g, "-");
}

function extractHeadings(md: string): Heading[] {
  const out: Heading[] = [];
  const cleaned = md.replace(/```[\s\S]*?```/g, "");
  for (const line of cleaned.split("\n")) {
    const m = line.match(/^(#{2,3})\s+(.+?)\s*$/);
    if (!m) continue;
    const level = m[1].length as 2 | 3;
    const text = m[2].trim();
    out.push({ id: slugify(text), text, level });
  }
  return out;
}

export default async function BlogPostPage({ params }: PageProps) {
  const { slug } = await params;
  const [post, allPosts] = await Promise.all([
    fetchBlogPost(slug),
    fetchBlogPosts(),
  ]);

  if (!post) {
    notFound();
  }

  const headings = extractHeadings(post.content);
  const idx = allPosts.findIndex((p) => p.slug === post.slug);
  const prev = idx > 0 ? allPosts[idx - 1] : undefined;
  const next = idx >= 0 && idx < allPosts.length - 1 ? allPosts[idx + 1] : undefined;

  const articleLd = {
    "@context": "https://schema.org",
    "@type": "Article",
    headline: post.title,
    description: post.excerpt,
    datePublished: post.published_at,
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

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(articleLd) }}
      />

      <ReadingProgress targetSelector="#blog-post-article" />

      <header className="sticky top-0 z-30 border-b border-white/5 bg-zinc-950/70 backdrop-blur-xl">
        <div className="max-w-6xl mx-auto px-4 md:px-6 h-14 flex items-center gap-3">
          <Link href="/blog">
            <Button
              variant="ghost"
              size="sm"
              className="-ml-2 text-zinc-400 hover:text-white hover:bg-white/5"
            >
              <ArrowLeft className="h-4 w-4 mr-1" />
              Blog
            </Button>
          </Link>
          <div className="h-4 w-px bg-white/10" />
          <div className="flex items-center gap-2">
            <GridarMark className="h-5 w-5" />
            <span className="font-semibold">Gridar</span>
          </div>
          <div className="flex-1" />
          <Link href="/login">
            <Button size="sm" className="bg-white text-zinc-950 hover:bg-zinc-200">
              Commencer
            </Button>
          </Link>
        </div>
      </header>

      <section className="relative border-b border-white/5 overflow-hidden">
        <div
          aria-hidden
          className="absolute inset-0 pointer-events-none opacity-50"
          style={{ background: gradientFor(post.slug) }}
        />
        <div
          aria-hidden
          className="absolute inset-0 pointer-events-none"
          style={{
            background:
              "radial-gradient(60% 50% at 50% 100%, rgba(0,0,0,0.6), transparent 70%)",
          }}
        />
        <div className="relative max-w-3xl mx-auto px-4 md:px-6 py-16 md:py-24">
          {post.tags && post.tags.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mb-6">
              {post.tags.map((tag) => (
                <span
                  key={tag}
                  className="text-[10px] uppercase tracking-wider px-2 py-1 rounded-full bg-black/40 backdrop-blur border border-white/10 text-emerald-300 font-mono"
                >
                  {tag}
                </span>
              ))}
            </div>
          )}
          <h1 className="text-4xl md:text-5xl lg:text-6xl font-bold tracking-tight leading-[1.1] mb-6">
            {post.title}
          </h1>
          {post.excerpt && (
            <p className="text-lg md:text-xl text-zinc-300 leading-relaxed mb-8 max-w-2xl">
              {post.excerpt}
            </p>
          )}
          <div className="flex items-center gap-4 text-sm text-zinc-400">
            {post.author && (
              <span className="inline-flex items-center gap-1.5">
                <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-emerald-400/20 text-emerald-300">
                  <User className="h-3 w-3" />
                </span>
                {post.author}
              </span>
            )}
            {post.published_at && <span>{formatDate(post.published_at)}</span>}
            <span className="inline-flex items-center gap-1">
              <Clock className="h-3.5 w-3.5" />
              {readingTime(post.content)} min de lecture
            </span>
          </div>
        </div>
      </section>

      <main id="blog-post-article" className="max-w-6xl mx-auto px-4 md:px-6 py-12 md:py-16 lg:grid lg:grid-cols-[1fr_220px] lg:gap-12">
        <article
          className="prose prose-invert prose-zinc max-w-none
                     prose-headings:scroll-mt-24
                     prose-h1:hidden
                     prose-h2:text-2xl prose-h2:font-bold prose-h2:mt-12 prose-h2:mb-4 prose-h2:tracking-tight prose-h2:border-t prose-h2:border-white/10 prose-h2:pt-8
                     prose-h3:text-xl prose-h3:font-semibold prose-h3:mt-8 prose-h3:mb-3
                     prose-p:text-zinc-300 prose-p:leading-relaxed
                     prose-strong:text-zinc-100
                     prose-code:before:content-none prose-code:after:content-none
                     prose-code:bg-white/5 prose-code:border prose-code:border-white/10 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:text-emerald-300 prose-code:text-[0.9em] prose-code:font-mono
                     prose-pre:bg-zinc-900 prose-pre:border prose-pre:border-white/10 prose-pre:rounded-xl
                     prose-a:text-emerald-300 prose-a:no-underline hover:prose-a:text-emerald-200 hover:prose-a:underline
                     prose-table:text-sm prose-th:text-zinc-200 prose-th:font-semibold prose-th:bg-white/5 prose-th:border-white/10 prose-td:border-white/10
                     prose-blockquote:border-l-emerald-400/50 prose-blockquote:text-zinc-300"
        >
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            rehypePlugins={[rehypeRaw]}
            components={{
              h2: ({ children, ...rest }) => {
                const text = typeof children === "string"
                  ? children
                  : Array.isArray(children)
                    ? children.join("")
                    : "";
                return <h2 id={slugify(String(text))} {...rest}>{children}</h2>;
              },
              h3: ({ children, ...rest }) => {
                const text = typeof children === "string"
                  ? children
                  : Array.isArray(children)
                    ? children.join("")
                    : "";
                return <h3 id={slugify(String(text))} {...rest}>{children}</h3>;
              },
            }}
          >
            {post.content}
          </ReactMarkdown>
        </article>

        {headings.length > 0 && (
          <aside className="hidden lg:block">
            <div className="sticky top-24">
              <div className="text-[11px] uppercase tracking-wider text-zinc-500 mb-3 font-mono">
                Dans cet article
              </div>
              <nav className="space-y-1.5 text-sm border-l border-white/10 pl-4">
                {headings.map((h) => (
                  <a
                    key={h.id}
                    href={`#${h.id}`}
                    className={`block text-zinc-400 hover:text-emerald-300 transition-colors leading-snug ${
                      h.level === 3 ? "pl-3 text-[13px]" : ""
                    }`}
                  >
                    {h.text}
                  </a>
                ))}
              </nav>
            </div>
          </aside>
        )}
      </main>

      <footer className="border-t border-white/5">
        <div className="max-w-3xl mx-auto px-4 md:px-6 py-12 space-y-12">
          {post.author && (
            <div className="rounded-2xl border border-white/10 bg-zinc-900/40 p-6 flex items-start gap-4">
              <div className="inline-flex h-12 w-12 items-center justify-center rounded-full bg-emerald-400/20 text-emerald-300 shrink-0">
                <User className="h-5 w-5" />
              </div>
              <div>
                <div className="text-xs uppercase tracking-wider text-zinc-500 mb-1 font-mono">
                  Ecrit par
                </div>
                <div className="font-semibold text-zinc-100 mb-1">
                  {post.author}
                </div>
                <p className="text-sm text-zinc-400 leading-relaxed">
                  Fondateur d&apos;Arivex Studio et de Gridar. Solo founder base a
                  Saint-Hyacinthe, QC. Specialiste SEO bilingue FR-CA.
                </p>
              </div>
            </div>
          )}

          <div className="rounded-2xl border border-emerald-500/20 bg-emerald-500/5 p-8 text-center relative overflow-hidden">
            <div
              aria-hidden
              className="absolute inset-0 pointer-events-none"
              style={{
                background:
                  "radial-gradient(60% 50% at 50% 50%, rgba(16,185,129,0.15), transparent 70%)",
              }}
            />
            <div className="relative">
              <h2 className="text-2xl font-bold tracking-tight mb-2">
                Tu veux générer ce genre d&apos;article sur ton site ?
              </h2>
              <p className="text-zinc-400 mb-6">
                Gridar le fait pour toi. Du brief à la publication sur
                WordPress, Shopify ou Webflow.
              </p>
              <Link href="/login">
                <Button size="lg" className="bg-white text-zinc-950 hover:bg-zinc-200">
                  <Sparkles className="h-4 w-4 mr-2" />
                  Essayer gratuitement
                </Button>
              </Link>
            </div>
          </div>

          {(prev || next) && (
            <nav className="grid sm:grid-cols-2 gap-4">
              {prev ? (
                <Link
                  href={`/blog/${prev.slug}`}
                  className="group rounded-xl border border-white/10 p-5 hover:border-emerald-400/40 transition-colors bg-zinc-900/40"
                >
                  <div className="text-xs text-zinc-500 mb-1.5 inline-flex items-center gap-1 uppercase tracking-wider font-mono">
                    <ArrowLeft className="h-3 w-3" />
                    Precedent
                  </div>
                  <div className="font-semibold leading-snug group-hover:text-emerald-300 transition-colors">
                    {prev.title}
                  </div>
                </Link>
              ) : (
                <div />
              )}
              {next && (
                <Link
                  href={`/blog/${next.slug}`}
                  className="group rounded-xl border border-white/10 p-5 hover:border-emerald-400/40 transition-colors bg-zinc-900/40 text-right"
                >
                  <div className="text-xs text-zinc-500 mb-1.5 inline-flex items-center gap-1 justify-end uppercase tracking-wider font-mono">
                    Suivant
                    <ArrowRight className="h-3 w-3" />
                  </div>
                  <div className="font-semibold leading-snug group-hover:text-emerald-300 transition-colors">
                    {next.title}
                  </div>
                </Link>
              )}
            </nav>
          )}
        </div>
      </footer>
    </div>
  );
}
