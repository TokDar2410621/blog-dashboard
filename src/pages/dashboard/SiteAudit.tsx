/**
 * SiteAudit - vue d'ensemble SEO du site (single-screen) qui agrège ce que
 * Gridar a éparpillé dans 8 pages séparées.
 *
 * Branché sur GET /api/sites/<id>/site-audit/ qui calcule un score composite
 * et retourne les top KPI en parallèle (PageSpeed + Keywords + Backlinks +
 * Stats + ContentDecay). Les sections en erreur sont rendues en mode dégradé.
 */
import { useParams, Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { authFetch } from "@/lib/api-client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Gauge,
  TrendingUp,
  Link as LinkIcon,
  AlertTriangle,
  CheckCircle2,
  ArrowRight,
  RefreshCw,
  Loader2,
  ExternalLink,
  Activity,
  Search,
} from "lucide-react";

type ScoreComponent = { name: string; score: number; weight: number };
type Reco = {
  severity: "high" | "medium" | "low";
  message: string;
  cta_label: string;
  cta_href: string;
};
type KeywordRow = {
  id: number;
  keyword: string;
  language: string;
  position: number | null;
  is_target_match: boolean | null;
  recorded_at: string | null;
};
type DecayItem = {
  url: string;
  slug: string;
  impressions_now: number;
  impressions_before: number;
  impressions_delta_pct: number;
  position_now: number | null;
  suggested_action: string;
};

type AuditPayload = {
  site_id: number;
  site_name: string;
  site_domain: string | null;
  composite_score: number | null;
  score_components: ScoreComponent[];
  pagespeed: {
    performance?: number;
    seo?: number;
    accessibility?: number;
    avg?: number;
    url?: string;
    error?: string;
  };
  keywords: {
    total?: number;
    top_10_count?: number;
    top_10_pct?: number;
    rows?: KeywordRow[];
    error?: string;
  };
  backlinks: {
    total_referring_domains?: number;
    top_domains?: [string, number][];
    error?: string;
  };
  stats: Record<string, unknown>;
  decay: {
    days?: number;
    decaying_count?: number;
    healthy_count?: number;
    new_pages_count?: number;
    top_decaying?: DecayItem[];
    gsc_not_connected?: boolean;
    error?: string;
  };
  recos: Reco[];
  gsc_connected: boolean;
};

function scoreColor(score: number | null | undefined) {
  if (score == null) return "text-muted-foreground";
  if (score >= 80) return "text-emerald-500";
  if (score >= 60) return "text-amber-500";
  return "text-destructive";
}

function scoreLabel(score: number | null | undefined) {
  if (score == null) return "Aucune donnee";
  if (score >= 90) return "Excellent";
  if (score >= 80) return "Tres bon";
  if (score >= 60) return "Correct";
  if (score >= 40) return "A ameliorer";
  return "Critique";
}

function severityClasses(s: Reco["severity"]) {
  switch (s) {
    case "high":
      return "border-destructive/40 bg-destructive/5";
    case "medium":
      return "border-amber-500/40 bg-amber-500/5";
    default:
      return "border-muted bg-muted/20";
  }
}

function severityIcon(s: Reco["severity"]) {
  switch (s) {
    case "high":
      return <AlertTriangle className="h-4 w-4 text-destructive shrink-0" />;
    case "medium":
      return <AlertTriangle className="h-4 w-4 text-amber-500 shrink-0" />;
    default:
      return <CheckCircle2 className="h-4 w-4 text-muted-foreground shrink-0" />;
  }
}

export default function SiteAudit() {
  const { siteId } = useParams<{ siteId: string }>();
  const base = `/dashboard/${siteId}`;

  const { data, isLoading, isError, refetch, isRefetching } = useQuery<AuditPayload>({
    queryKey: ["site-audit", siteId],
    queryFn: async () => {
      const res = await authFetch(`/sites/${siteId}/site-audit/`);
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error || "Erreur audit site");
      }
      return res.json();
    },
    staleTime: 60 * 1000, // 1 min
  });

  if (isLoading) {
    return (
      <div className="space-y-4 max-w-6xl">
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-48 w-full" />
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Skeleton className="h-64" />
          <Skeleton className="h-64" />
        </div>
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="space-y-4 max-w-6xl">
        <h1 className="text-2xl font-bold">Audit du site</h1>
        <Card>
          <CardContent className="py-12 text-center">
            <AlertTriangle className="h-10 w-10 mx-auto mb-3 text-destructive" />
            <p className="text-muted-foreground mb-4">
              Impossible de charger l&apos;audit. Reessaye dans un instant.
            </p>
            <Button onClick={() => refetch()} variant="outline">
              <RefreshCw className="h-4 w-4 mr-2" />
              Reessayer
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-6xl">
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Audit du site</h1>
          <p className="text-muted-foreground text-sm">
            Vue d&apos;ensemble SEO de{" "}
            <span className="font-mono">{data.site_domain || data.site_name}</span>
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={() => refetch()}
          disabled={isRefetching}
        >
          {isRefetching ? (
            <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
          ) : (
            <RefreshCw className="h-3.5 w-3.5 mr-1.5" />
          )}
          Actualiser
        </Button>
      </div>

      {/* Composite score - hero card */}
      <Card>
        <CardContent className="p-6">
          <div className="flex flex-col md:flex-row md:items-center gap-6">
            <div className="flex flex-col items-center md:items-start gap-1">
              <div className="text-xs uppercase tracking-wide text-muted-foreground flex items-center gap-1.5">
                <Gauge className="h-3.5 w-3.5" />
                Score SEO global
              </div>
              <div className={`text-6xl font-bold tabular-nums ${scoreColor(data.composite_score)}`}>
                {data.composite_score ?? "-"}
                <span className="text-2xl text-muted-foreground font-normal">/100</span>
              </div>
              <div className={`text-sm font-medium ${scoreColor(data.composite_score)}`}>
                {scoreLabel(data.composite_score)}
              </div>
            </div>
            <div className="flex-1 grid grid-cols-2 md:grid-cols-4 gap-3 w-full">
              {data.score_components.map((c) => (
                <div key={c.name} className="rounded-md border bg-muted/30 p-3">
                  <div className="text-[10px] uppercase tracking-wide text-muted-foreground">
                    {c.name === "pagespeed"
                      ? "PageSpeed"
                      : c.name === "rankings"
                      ? "Rankings"
                      : c.name === "backlinks"
                      ? "Backlinks"
                      : c.name === "freshness"
                      ? "Fraicheur"
                      : c.name}
                  </div>
                  <div className={`text-2xl font-bold tabular-nums ${scoreColor(c.score)}`}>
                    {c.score}
                  </div>
                  <div className="text-[10px] text-muted-foreground">
                    poids {Math.round(c.weight * 100)}%
                  </div>
                </div>
              ))}
              {data.score_components.length === 0 && (
                <div className="col-span-full text-sm text-muted-foreground">
                  Aucune donnee mesurable encore. Connecte ton GSC ou ajoute des
                  mots-cles a suivre.
                </div>
              )}
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Recos prioritaires */}
      {data.recos.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <AlertTriangle className="h-5 w-5 text-amber-500" />
              Recommandations prioritaires
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {data.recos.map((reco, i) => (
              <div
                key={i}
                className={`border rounded-md p-3 flex items-center gap-3 ${severityClasses(reco.severity)}`}
              >
                {severityIcon(reco.severity)}
                <div className="flex-1 text-sm">{reco.message}</div>
                <Link to={reco.cta_href}>
                  <Button size="sm" variant="outline">
                    {reco.cta_label}
                    <ArrowRight className="h-3.5 w-3.5 ml-1.5" />
                  </Button>
                </Link>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Keywords */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <TrendingUp className="h-4 w-4" />
              Mots-cles suivis
            </CardTitle>
          </CardHeader>
          <CardContent>
            {data.keywords.error ? (
              <p className="text-sm text-muted-foreground">{data.keywords.error}</p>
            ) : !data.keywords.total ? (
              <div className="text-sm text-muted-foreground">
                <p className="mb-3">Aucun mot-cle suivi.</p>
                <Link to={`${base}/positions`}>
                  <Button size="sm">
                    Ajouter mes mots-cles
                    <ArrowRight className="h-3.5 w-3.5 ml-1.5" />
                  </Button>
                </Link>
              </div>
            ) : (
              <>
                <div className="flex items-baseline gap-3 mb-3">
                  <span className="text-2xl font-bold tabular-nums">
                    {data.keywords.top_10_count}/{data.keywords.total}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    dans le top 10 ({Math.round(data.keywords.top_10_pct || 0)}%)
                  </span>
                </div>
                <div className="space-y-1 max-h-64 overflow-y-auto">
                  {(data.keywords.rows || []).map((kw) => (
                    <div
                      key={kw.id}
                      className="flex items-center justify-between text-sm border-b border-border/30 py-1.5"
                    >
                      <span className="truncate">{kw.keyword}</span>
                      <span
                        className={`font-mono text-xs shrink-0 ml-2 ${
                          kw.position == null
                            ? "text-muted-foreground"
                            : kw.position <= 10
                            ? "text-emerald-500"
                            : kw.position <= 30
                            ? "text-amber-500"
                            : "text-muted-foreground"
                        }`}
                      >
                        {kw.position == null ? "non classe" : `#${kw.position}`}
                      </span>
                    </div>
                  ))}
                </div>
                <Link to={`${base}/positions`}>
                  <Button size="sm" variant="ghost" className="mt-3 w-full">
                    Gerer les mots-cles
                    <ArrowRight className="h-3.5 w-3.5 ml-1.5" />
                  </Button>
                </Link>
              </>
            )}
          </CardContent>
        </Card>

        {/* PageSpeed */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Activity className="h-4 w-4" />
              Performance mobile (PageSpeed)
            </CardTitle>
          </CardHeader>
          <CardContent>
            {data.pagespeed.error ? (
              <p className="text-sm text-muted-foreground">{data.pagespeed.error}</p>
            ) : "avg" in data.pagespeed ? (
              <>
                <div className={`text-3xl font-bold mb-2 ${scoreColor(data.pagespeed.avg)}`}>
                  {data.pagespeed.avg}
                  <span className="text-base text-muted-foreground font-normal">/100</span>
                </div>
                <div className="grid grid-cols-3 gap-2 text-center">
                  <div className="border rounded-md p-2">
                    <div className="text-[10px] uppercase text-muted-foreground">Perf</div>
                    <div className={`text-lg font-semibold ${scoreColor(data.pagespeed.performance)}`}>
                      {data.pagespeed.performance}
                    </div>
                  </div>
                  <div className="border rounded-md p-2">
                    <div className="text-[10px] uppercase text-muted-foreground">SEO</div>
                    <div className={`text-lg font-semibold ${scoreColor(data.pagespeed.seo)}`}>
                      {data.pagespeed.seo}
                    </div>
                  </div>
                  <div className="border rounded-md p-2">
                    <div className="text-[10px] uppercase text-muted-foreground">A11y</div>
                    <div className={`text-lg font-semibold ${scoreColor(data.pagespeed.accessibility)}`}>
                      {data.pagespeed.accessibility}
                    </div>
                  </div>
                </div>
                {data.pagespeed.url && (
                  <a
                    href={`https://pagespeed.web.dev/report?url=${encodeURIComponent(data.pagespeed.url)}`}
                    target="_blank"
                    rel="noreferrer"
                    className="text-xs text-primary mt-3 flex items-center gap-1"
                  >
                    Rapport complet Google
                    <ExternalLink className="h-3 w-3" />
                  </a>
                )}
              </>
            ) : (
              <p className="text-sm text-muted-foreground">
                Pas de domaine renseigne sur ce site.
              </p>
            )}
          </CardContent>
        </Card>

        {/* Backlinks */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <LinkIcon className="h-4 w-4" />
              Profil de liens
            </CardTitle>
          </CardHeader>
          <CardContent>
            {data.backlinks.error ? (
              <p className="text-sm text-muted-foreground">{data.backlinks.error}</p>
            ) : (
              <>
                <div className="text-3xl font-bold mb-1 tabular-nums">
                  {data.backlinks.total_referring_domains ?? 0}
                </div>
                <div className="text-xs text-muted-foreground mb-3">
                  domaines referrents estimes (via Serper)
                </div>
                {data.backlinks.top_domains && data.backlinks.top_domains.length > 0 && (
                  <div className="space-y-1">
                    {data.backlinks.top_domains.map(([domain, count]) => (
                      <div
                        key={domain}
                        className="flex items-center justify-between text-xs border-b border-border/30 py-1"
                      >
                        <span className="truncate font-mono">{domain}</span>
                        <span className="text-muted-foreground shrink-0 ml-2">
                          {count} mentions
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}
          </CardContent>
        </Card>

        {/* Content decay */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Search className="h-4 w-4" />
              Detection de declin (GSC)
            </CardTitle>
          </CardHeader>
          <CardContent>
            {data.decay.gsc_not_connected ? (
              <div className="text-sm text-muted-foreground">
                <p className="mb-3">
                  Google Search Console non connecte - pas de detection automatique.
                </p>
                <Link to={`${base}/parametres`}>
                  <Button size="sm" variant="outline">
                    Connecter GSC
                    <ArrowRight className="h-3.5 w-3.5 ml-1.5" />
                  </Button>
                </Link>
              </div>
            ) : data.decay.error ? (
              <p className="text-sm text-muted-foreground">{data.decay.error}</p>
            ) : (
              <>
                <div className="flex items-baseline gap-4 mb-3">
                  <div>
                    <div className="text-2xl font-bold text-destructive tabular-nums">
                      {data.decay.decaying_count || 0}
                    </div>
                    <div className="text-[10px] uppercase text-muted-foreground">En declin</div>
                  </div>
                  <div>
                    <div className="text-2xl font-bold text-emerald-500 tabular-nums">
                      {data.decay.healthy_count || 0}
                    </div>
                    <div className="text-[10px] uppercase text-muted-foreground">Sains</div>
                  </div>
                  {(data.decay.new_pages_count ?? 0) > 0 && (
                    <div>
                      <div className="text-2xl font-bold tabular-nums">
                        {data.decay.new_pages_count}
                      </div>
                      <div className="text-[10px] uppercase text-muted-foreground">Nouveaux</div>
                    </div>
                  )}
                </div>
                {data.decay.top_decaying && data.decay.top_decaying.length > 0 && (
                  <div className="space-y-1 max-h-40 overflow-y-auto">
                    {data.decay.top_decaying.slice(0, 5).map((d) => (
                      <div
                        key={d.slug}
                        className="text-xs border-b border-border/30 py-1"
                      >
                        <div className="truncate">{d.slug}</div>
                        <div className="text-destructive">
                          {Math.round(d.impressions_delta_pct)}% impressions
                        </div>
                      </div>
                    ))}
                  </div>
                )}
                <Link to={`${base}/decay`}>
                  <Button size="sm" variant="ghost" className="mt-3 w-full">
                    Voir le rapport complet
                    <ArrowRight className="h-3.5 w-3.5 ml-1.5" />
                  </Button>
                </Link>
              </>
            )}
          </CardContent>
        </Card>
      </div>

      {!data.gsc_connected && (
        <div className="text-xs text-muted-foreground text-center pt-4">
          Connecte Google Search Console (Parametres) pour des donnees exactes (au
          lieu d&apos;estimations Serper) et debloque la detection de declin.
        </div>
      )}
    </div>
  );
}
