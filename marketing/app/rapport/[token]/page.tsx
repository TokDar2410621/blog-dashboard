import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import {
  Gauge,
  Activity,
  TrendingUp,
  AlertTriangle,
  ArrowRight,
  ExternalLink,
} from "lucide-react";
import { GridarMark } from "@/components/GridarMark";
import { CopyLinkButton } from "@/components/CopyLinkButton";
import { fetchPublicReport } from "@/lib/report-api";

export const revalidate = 3600;

type PageProps = {
  params: Promise<{ token: string }>;
};

function scoreColor(s: number | null | undefined) {
  if (s == null) return "text-zinc-400";
  if (s >= 80) return "text-emerald-400";
  if (s >= 60) return "text-amber-400";
  return "text-red-400";
}

function scoreLabel(s: number | null | undefined) {
  if (s == null) return "Aucune donnee";
  if (s >= 90) return "Excellent";
  if (s >= 80) return "Tres bon";
  if (s >= 60) return "Correct";
  if (s >= 40) return "A ameliorer";
  return "Critique";
}

function positionColor(p: number | null) {
  if (p == null) return "text-zinc-500";
  if (p <= 10) return "text-emerald-400";
  if (p <= 30) return "text-amber-400";
  return "text-zinc-500";
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { token } = await params;
  const data = await fetchPublicReport(token).catch(() => null);
  if (!data) {
    return { title: "Rapport introuvable", robots: { index: false, follow: false } };
  }
  const score = data.composite_score ?? "-";
  const title = `Rapport SEO de ${data.domain} - Score ${score}/100 | Gridar`;
  const description = `Audit SEO complet de ${data.domain} : score ${score}/100, performance mobile, positions Google.ca et recommandations. Genere par Gridar.`;
  return {
    title,
    description,
    openGraph: { title, description, type: "article" },
    twitter: { card: "summary_large_image", title, description },
    // Shareable by link, but not something we want indexed by Google.
    robots: { index: false, follow: false },
  };
}

export default async function ReportPage({ params }: PageProps) {
  const { token } = await params;
  const data = await fetchPublicReport(token);
  if (!data) notFound();

  const ps = data.pagespeed || {};
  const hasPagespeed = typeof ps.avg === "number";
  const keywords = data.top_keywords_estimated || [];
  const recos = data.recos_partial || [];

  return (
    <div className="min-h-screen bg-gradient-to-b from-zinc-950 via-zinc-950 to-emerald-950/30 text-zinc-100">
      <div className="max-w-3xl mx-auto px-4 py-10 sm:py-16">
        <header className="flex items-center justify-between mb-10">
          <Link
            href="/"
            className="flex items-center gap-2 text-zinc-400 hover:text-zinc-100 transition-colors"
          >
            <GridarMark className="h-6 w-6" />
            <span className="font-medium">Gridar</span>
          </Link>
          <CopyLinkButton />
        </header>

        {/* Score hero */}
        <div className="mb-8">
          <p className="text-sm text-zinc-400 mb-1">Rapport SEO de</p>
          <h1 className="text-3xl sm:text-4xl font-bold tracking-tight break-words">
            {data.domain}
          </h1>
          {data.crawl?.title && (
            <p className="text-sm text-zinc-500 mt-2">
              <span className="text-zinc-400">Titre :</span> {data.crawl.title}
            </p>
          )}
          {data.crawl?.meta_description && (
            <p className="text-sm text-zinc-500 mt-1 line-clamp-2">
              <span className="text-zinc-400">Description :</span>{" "}
              {data.crawl.meta_description}
            </p>
          )}
        </div>

        <section className="rounded-xl border border-emerald-500/30 bg-emerald-500/[0.04] p-6 mb-6">
          <div className="flex items-center gap-1.5 text-xs uppercase tracking-wide text-zinc-400 mb-1">
            <Gauge className="h-3.5 w-3.5" />
            Score SEO global
          </div>
          <div className={`text-6xl font-bold tabular-nums ${scoreColor(data.composite_score)}`}>
            {data.composite_score ?? "-"}
            <span className="text-2xl text-zinc-500 font-normal">/100</span>
          </div>
          <div className={`text-sm font-medium ${scoreColor(data.composite_score)}`}>
            {scoreLabel(data.composite_score)}
          </div>
        </section>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-6">
          {/* PageSpeed */}
          <section className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-6">
            <div className="flex items-center gap-2 text-sm font-medium text-zinc-300 mb-4">
              <Activity className="h-4 w-4" />
              Performance mobile
            </div>
            {ps.error ? (
              <p className="text-sm text-zinc-500">{ps.error}</p>
            ) : hasPagespeed ? (
              <>
                <div className={`text-3xl font-bold mb-3 ${scoreColor(ps.avg)}`}>
                  {ps.avg}
                  <span className="text-base text-zinc-500 font-normal">/100</span>
                </div>
                <div className="grid grid-cols-3 gap-2 text-center">
                  <div className="rounded border border-zinc-800 p-2">
                    <div className="text-[10px] uppercase text-zinc-500">Perf</div>
                    <div className={`font-semibold ${scoreColor(ps.performance)}`}>
                      {ps.performance}
                    </div>
                  </div>
                  <div className="rounded border border-zinc-800 p-2">
                    <div className="text-[10px] uppercase text-zinc-500">SEO</div>
                    <div className={`font-semibold ${scoreColor(ps.seo)}`}>{ps.seo}</div>
                  </div>
                  <div className="rounded border border-zinc-800 p-2">
                    <div className="text-[10px] uppercase text-zinc-500">A11y</div>
                    <div className={`font-semibold ${scoreColor(ps.accessibility)}`}>
                      {ps.accessibility}
                    </div>
                  </div>
                </div>
              </>
            ) : (
              <p className="text-sm text-zinc-500">Pas de donnee PageSpeed.</p>
            )}
          </section>

          {/* Keywords */}
          <section className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-6">
            <div className="flex items-center gap-2 text-sm font-medium text-zinc-300 mb-4">
              <TrendingUp className="h-4 w-4" />
              Positions Google.ca (estimees)
            </div>
            {keywords.length === 0 ? (
              <p className="text-sm text-zinc-500">
                Pas de mot-cle extrait du site.
              </p>
            ) : (
              <div className="space-y-1">
                {keywords.map((kw, i) => (
                  <div
                    key={i}
                    className="flex items-center justify-between text-sm border-b border-zinc-800/60 py-1.5"
                  >
                    <span className="truncate text-zinc-200">{kw.keyword}</span>
                    <span className={`font-mono text-xs shrink-0 ml-2 ${positionColor(kw.position)}`}>
                      {kw.position == null ? "hors top 50" : `#${kw.position}`}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </section>
        </div>

        {/* Recommandations */}
        {recos.length > 0 && (
          <section className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-6 mb-8">
            <div className="flex items-center gap-2 text-sm font-medium text-zinc-300 mb-4">
              <AlertTriangle className="h-4 w-4 text-amber-400" />
              Recommandations
            </div>
            <div className="space-y-2">
              {recos.map((reco, i) => (
                <div
                  key={i}
                  className={`rounded border p-3 flex items-start gap-2 text-sm ${
                    reco.severity === "high"
                      ? "border-red-500/40 bg-red-500/5"
                      : reco.severity === "medium"
                      ? "border-amber-500/40 bg-amber-500/5"
                      : "border-zinc-800 bg-zinc-800/20"
                  }`}
                >
                  <AlertTriangle
                    className={`h-4 w-4 shrink-0 mt-0.5 ${
                      reco.severity === "high"
                        ? "text-red-400"
                        : reco.severity === "medium"
                        ? "text-amber-400"
                        : "text-zinc-500"
                    }`}
                  />
                  <span className="text-zinc-200">{reco.message}</span>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* CTA */}
        <section className="rounded-xl border border-emerald-500/20 bg-emerald-500/[0.03] p-6">
          <p className="font-medium text-zinc-100 mb-1">
            Va plus loin avec Gridar
          </p>
          <p className="text-sm text-zinc-400 mb-4">
            Cree un compte, connecte ton Google Search Console pour tes vraies
            positions, et laisse Gridar generer les articles qui te manquent en
            francais quebecois.
          </p>
          <Link
            href="/login"
            className="inline-flex items-center gap-2 rounded-md bg-emerald-500 px-4 py-2 text-sm font-semibold text-zinc-950 hover:bg-emerald-400 transition-colors"
          >
            Creer mon compte
            <ArrowRight className="h-4 w-4" />
          </Link>
        </section>

        <footer className="mt-10 pt-6 border-t border-zinc-800/60 flex items-center justify-between text-xs text-zinc-500">
          <span>Audit genere par Gridar</span>
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
