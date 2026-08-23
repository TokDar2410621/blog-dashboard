import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowRight, ExternalLink, PenLine, TrendingUp } from "lucide-react";
import { GridarMark } from "@/components/GridarMark";
import { fetchPublicProof } from "@/lib/proof-api";

export const revalidate = 3600;

type PageProps = {
  params: Promise<{ token: string }>;
};

function formatNumber(n: number): string {
  if (Math.abs(n) >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return String(n);
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { token } = await params;
  const data = await fetchPublicProof(token).catch(() => null);
  if (!data) {
    return {
      title: "Preuve introuvable",
      robots: { index: false, follow: false },
    };
  }
  const title = `+${formatNumber(data.total_impressions_gained)} impressions Google sur ${data.site_name} - Preuve Gridar`;
  const description = `${data.site_name} a gagne ${data.total_impressions_gained.toLocaleString("fr-CA")} impressions et ${data.total_clicks_gained.toLocaleString("fr-CA")} clics Google grace a Gridar, mesures par Search Console sur ${data.posts_with_attribution} article(s).`;
  return {
    title,
    description,
    openGraph: { title, description, type: "article" },
    twitter: { card: "summary_large_image", title, description },
    robots: { index: false, follow: false },
  };
}

export default async function ProofPage({ params }: PageProps) {
  const { token } = await params;
  const data = await fetchPublicProof(token);
  if (!data) notFound();

  const noData = data.posts_with_attribution === 0;

  return (
    <div className="min-h-screen bg-gradient-to-b from-zinc-950 via-zinc-950 to-emerald-950/40 text-zinc-100">
      <div className="max-w-3xl mx-auto px-4 py-12 sm:py-20">
        <header className="flex items-center justify-between mb-12">
          <Link href="/" className="flex items-center gap-2 text-zinc-400 hover:text-zinc-100 transition-colors">
            <GridarMark className="h-6 w-6" />
            <span className="font-medium">Gridar</span>
          </Link>
          <span className="text-xs uppercase tracking-wider text-zinc-500">
            Preuve generee automatiquement
          </span>
        </header>

        <div className="mb-8">
          <p className="text-sm text-zinc-400 mb-2">Site mesure</p>
          <h1 className="text-3xl sm:text-4xl font-bold tracking-tight">
            {data.site_name}
          </h1>
          {data.domain && (
            <p className="text-sm text-zinc-500 mt-1">{data.domain}</p>
          )}
        </div>

        {noData ? (
          <section className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-8">
            <p className="text-zinc-300">
              Pas encore de mesure d'attribution disponible. Les premiers points arrivent
              automatiquement 30 jours apres la publication du premier article.
            </p>
          </section>
        ) : (
          <>
            <section className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-8">
              <div className="rounded-xl border border-emerald-500/30 bg-emerald-500/5 p-6">
                <div className="flex items-baseline gap-2 mb-1">
                  <span className="text-5xl font-bold text-emerald-400">
                    +{formatNumber(data.total_impressions_gained)}
                  </span>
                  <TrendingUp className="h-5 w-5 text-emerald-400" />
                </div>
                <p className="text-sm text-zinc-400">impressions Google gagnees</p>
                <p className="text-xs text-zinc-500 mt-2">
                  Mesure Search Console vs baseline pre-Gridar
                </p>
              </div>

              <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-6">
                <div className="text-5xl font-bold text-zinc-100 mb-1">
                  +{formatNumber(data.total_clicks_gained)}
                </div>
                <p className="text-sm text-zinc-400">clics organiques gagnes</p>
                <p className="text-xs text-zinc-500 mt-2">
                  Sur {data.posts_with_attribution} article{data.posts_with_attribution > 1 ? "s" : ""} mesure{data.posts_with_attribution > 1 ? "s" : ""}
                </p>
              </div>
            </section>

            {data.posts.length > 0 && (
              <section className="mb-12">
                <h2 className="text-sm font-medium uppercase tracking-wider text-zinc-400 mb-4">
                  Tous les articles mesures
                </h2>
                <ul className="space-y-3">
                  {data.posts.map((p) => {
                    const win = p.impressions_gained > 0;
                    const lose = p.impressions_gained < 0;
                    return (
                      <li
                        key={p.post_id}
                        className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4"
                      >
                        <div className="flex items-start justify-between gap-4">
                          <div className="flex-1 min-w-0">
                            <p className="font-medium text-zinc-100 truncate">{p.title}</p>
                            {p.top_queries.length > 0 ? (
                              <p className="text-xs text-zinc-500 mt-2 truncate">
                                Top requete : <span className="text-zinc-300">{p.top_queries[0].query}</span>
                                {p.top_queries[0].position !== null && (
                                  <span className="text-zinc-500"> · position {p.top_queries[0].position.toFixed(1)}</span>
                                )}
                              </p>
                            ) : (
                              !p.indexed && (
                                <p className="text-xs text-zinc-600 mt-2">Pas encore indexe par Google</p>
                              )
                            )}
                          </div>
                          <div className="text-right shrink-0">
                            <div
                              className={`font-semibold ${
                                win ? "text-emerald-400" : lose ? "text-red-400" : "text-zinc-500"
                              }`}
                            >
                              {win ? "+" : ""}
                              {formatNumber(p.impressions_gained)}
                            </div>
                            <div className="text-xs text-zinc-500">mesure J+{p.horizon}</div>
                          </div>
                        </div>
                      </li>
                    );
                  })}
                </ul>
                <p className="text-xs text-zinc-600 mt-4">
                  Liste complete, mesuree par Search Console. Les articles a plat ou en
                  baisse sont affiches comme les gagnants : une preuve qui cache ses zeros
                  n&apos;en est pas une.
                </p>
              </section>
            )}
          </>
        )}

        <section className="rounded-xl border border-emerald-500/20 bg-emerald-500/[0.03] p-6">
          <div className="flex items-start gap-3">
            <PenLine className="h-5 w-5 text-emerald-400 shrink-0 mt-1" />
            <div className="flex-1">
              <p className="font-medium text-zinc-100 mb-1">
                Tes propres impressions Google, mesurees pareil
              </p>
              <p className="text-sm text-zinc-400 mb-4">
                Gridar genere des articles SEO ancres sur ta marque, suit leur impact reel
                dans Search Console et te livre des pages de preuve comme celle-ci.
              </p>
              <Link
                href="/"
                className="inline-flex items-center gap-2 text-sm font-medium text-emerald-400 hover:text-emerald-300 transition-colors"
              >
                Voir Gridar <ArrowRight className="h-4 w-4" />
              </Link>
            </div>
          </div>
        </section>

        <footer className="mt-12 pt-6 border-t border-zinc-800/60 flex items-center justify-between text-xs text-zinc-500">
          <span>Donnees Search Console agregees</span>
          <Link
            href="/"
            className="inline-flex items-center gap-1 hover:text-zinc-300 transition-colors"
          >
            gridar.app <ExternalLink className="h-3 w-3" />
          </Link>
        </footer>
      </div>
    </div>
  );
}
