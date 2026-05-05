import Link from "next/link";
import { listPosts } from "@/lib/api";
import { getCurrentSite } from "@/lib/site-context";
import { notFound } from "next/navigation";

export default async function HomePage() {
  const site = await getCurrentSite();
  if (!site) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-24 text-center">
        <h1 className="text-3xl font-display font-bold mb-4">Site non configuré</h1>
        <p className="text-zinc-600 dark:text-zinc-400">
          Aucun blog n&apos;est associé à ce domaine. Si vous êtes propriétaire,
          ajoutez ce domaine dans les paramètres de votre site sur le tableau de bord.
        </p>
      </div>
    );
  }

  let postsResp;
  try {
    postsResp = await listPosts(site.id, { language: site.default_language });
  } catch {
    notFound();
  }

  const posts = postsResp.results;

  return (
    <div className="max-w-4xl mx-auto px-4 py-12">
      {site.description && (
        <p className="text-lg text-zinc-600 dark:text-zinc-400 mb-12 max-w-2xl">
          {site.description}
        </p>
      )}

      {posts.length === 0 ? (
        <p className="text-zinc-500">Aucun article publié pour l&apos;instant.</p>
      ) : (
        <div className="space-y-8">
          {posts.map((p) => (
            <article key={p.id} className="border-b pb-8 last:border-0">
              <Link href={`/${p.slug}`} className="group block">
                <div className="flex flex-col md:flex-row gap-6">
                  {p.cover_image && (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={p.cover_image}
                      alt={p.title}
                      className="w-full md:w-64 h-48 object-cover rounded-lg shrink-0"
                      loading="lazy"
                    />
                  )}
                  <div className="flex-1">
                    {p.category && (
                      <span className="text-xs uppercase tracking-wider text-brand mb-2 inline-block">
                        {p.category}
                      </span>
                    )}
                    <h2 className="text-2xl font-display font-semibold group-hover:text-brand transition-colors">
                      {p.title}
                    </h2>
                    {p.excerpt && (
                      <p className="mt-3 text-zinc-600 dark:text-zinc-400 line-clamp-3">
                        {p.excerpt}
                      </p>
                    )}
                    <div className="mt-3 flex items-center gap-3 text-xs text-zinc-500">
                      {p.published_at && (
                        <time dateTime={p.published_at}>
                          {new Date(p.published_at).toLocaleDateString("fr-CA", {
                            year: "numeric",
                            month: "long",
                            day: "numeric",
                          })}
                        </time>
                      )}
                      {p.reading_time && <span>· {p.reading_time} min</span>}
                    </div>
                  </div>
                </div>
              </Link>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
