import { notFound, redirect } from "next/navigation";
import type { Metadata } from "next";
import Link from "next/link";
import { getPost, getTranslations, type Post } from "@/lib/api";
import { getCurrentSite, renderMarkdown } from "@/lib/site-context";

type Props = { params: Promise<{ slug: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const site = await getCurrentSite();
  if (!site) return { title: "Article" };
  try {
    const result = await getPost(site.id, slug);
    if ("redirect_to" in result) return { title: "Redirection" };
    const post = result;
    const url = `https://${site.domain}/${slug}`;
    return {
      title: post.title,
      description: post.excerpt,
      openGraph: {
        title: post.title,
        description: post.excerpt,
        type: "article",
        url,
        images: post.cover_image ? [{ url: post.cover_image }] : [],
        publishedTime: post.published_at || undefined,
        authors: post.author ? [post.author] : undefined,
      },
      twitter: {
        card: "summary_large_image",
        title: post.title,
        description: post.excerpt,
        images: post.cover_image ? [post.cover_image] : [],
      },
      alternates: { canonical: url },
    };
  } catch {
    return { title: "Article introuvable" };
  }
}

export default async function ArticlePage({ params }: Props) {
  const { slug } = await params;
  const site = await getCurrentSite();
  if (!site) notFound();

  let result;
  try {
    result = await getPost(site.id, slug);
  } catch {
    notFound();
  }

  if ("redirect_to" in result) {
    redirect(`/${result.redirect_to}`);
  }

  const post: Post = result;

  // Translations (for hreflang + language switcher)
  let translations: Awaited<ReturnType<typeof getTranslations>> | null = null;
  try {
    translations = await getTranslations(site.id, slug);
  } catch {
    /* not critical */
  }

  const articleSchema = {
    "@context": "https://schema.org",
    "@type": "BlogPosting",
    headline: post.title,
    description: post.excerpt,
    image: post.cover_image ? [post.cover_image] : undefined,
    datePublished: post.published_at,
    dateModified: post.updated_at || post.published_at,
    author: site.author?.name
      ? {
          "@type": "Person",
          name: site.author.name,
          jobTitle: site.author.role,
          description: site.author.bio,
        }
      : { "@type": "Person", name: post.author || "Admin" },
    publisher: {
      "@type": "Organization",
      name: site.name,
      url: `https://${site.domain}`,
    },
    mainEntityOfPage: {
      "@type": "WebPage",
      "@id": `https://${site.domain}/${slug}`,
    },
    inLanguage: post.language || site.default_language || "fr",
  };

  const html = renderMarkdown(post.content);
  const dateLabel = post.published_at
    ? new Date(post.published_at).toLocaleDateString(
        post.language === "en" ? "en-CA" : "fr-CA",
        { year: "numeric", month: "long", day: "numeric" }
      )
    : "";

  return (
    <article className="max-w-3xl mx-auto px-4 py-12">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(articleSchema) }}
      />

      {/* hreflang alternates as <link> tags via metadata is preferred but Next 14
          doesn't expose hreflang easily — render as visible language switcher */}
      {translations && translations.translations.length > 1 && (
        <div className="text-xs text-zinc-500 mb-4">
          {translations.translations.map((t, i) => (
            <span key={t.slug}>
              {i > 0 && " · "}
              {t.is_current ? (
                <span className="font-bold uppercase">{t.language}</span>
              ) : (
                <a href={t.url} className="uppercase hover:text-brand">
                  {t.language}
                </a>
              )}
            </span>
          ))}
        </div>
      )}

      <header className="mb-8">
        {post.category && (
          <span className="text-xs uppercase tracking-wider text-brand">
            {post.category}
          </span>
        )}
        <h1 className="text-4xl md:text-5xl font-display font-bold mt-2 leading-tight">
          {post.title}
        </h1>
        {post.excerpt && (
          <p className="mt-4 text-lg text-zinc-600 dark:text-zinc-400">
            {post.excerpt}
          </p>
        )}
        <div className="mt-6 flex items-center gap-3 text-sm text-zinc-500">
          {dateLabel && <time dateTime={post.published_at || ""}>{dateLabel}</time>}
          {post.reading_time && <span>· {post.reading_time} min de lecture</span>}
          {post.author && <span>· {post.author}</span>}
        </div>
      </header>

      {post.cover_image && (
        <div className="my-8">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src={post.cover_image}
            alt={post.title}
            className="w-full rounded-lg"
          />
        </div>
      )}

      <div
        className="prose-blog"
        dangerouslySetInnerHTML={{ __html: html }}
      />

      {post.tags && post.tags.length > 0 && (
        <div className="mt-12 flex flex-wrap gap-2">
          {post.tags.map((tag) => (
            <span
              key={tag}
              className="text-xs px-2 py-1 rounded bg-zinc-100 dark:bg-zinc-800"
            >
              #{tag}
            </span>
          ))}
        </div>
      )}

      <div className="mt-16 pt-8 border-t">
        <Link href="/" className="text-sm text-brand hover:underline">
          ← Retour au blog
        </Link>
      </div>
    </article>
  );
}
