"use client";

/**
 * SiteAudit - vue d'ensemble SEO du site (single-screen) qui agrège ce que
 * Gridar a éparpillé dans 8 pages séparées.
 *
 * Branché sur GET /api/sites/<id>/site-audit/ qui calcule un score composite
 * et retourne les top KPI en parallèle (PageSpeed + Keywords + Backlinks +
 * Stats + ContentDecay). Les sections en erreur sont rendues en mode dégradé.
 */
import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { authFetch, listStrategicOpportunities } from "@/lib/api-client";
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
  Lightbulb,
} from "lucide-react";
import { PageBreadcrumb } from "@/components/PageBreadcrumb";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { describeLastChecked, rankState } from "@/lib/rank-display";

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
  // Bloc de position stable (fenetre glissante) renvoye par le backend.
  stable_position: number | null;
  is_stable: boolean;
  found_ratio: number;
  last_checked: string | null;
  best_seen: number | null;
  samples: number;
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
    pending?: boolean;
  };
  keywords: {
    total?: number;
    top_10_count?: number;
    top_10_pct?: number;
    stable_ranked_count?: number;
    last_checked?: string | null;
    rows?: KeywordRow[];
    error?: string;
  };
  backlinks: {
    total_referring_domains?: number;
    top_domains?: [string, number][];
    error?: string;
    pending?: boolean;
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
  partial?: boolean;
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

/** Petite ligne "Verifie il y a X jours", en ambre si trop vieux. */
function AuditLastCheckedNote({ iso }: { iso: string | null }) {
  if (!iso) return null;
  const info = describeLastChecked(iso);
  return (
    <div
      title={info.full}
      className={`inline-flex items-center gap-1 text-[11px] ${
        info.isStale
          ? "text-amber-600 dark:text-amber-400"
          : "text-muted-foreground"
      }`}
    >
      {info.isStale && <AlertTriangle className="h-3 w-3 shrink-0" />}
      Verifie {info.label}
    </div>
  );
}

/**
 * Position honnete d'un mot-cle dans l'audit : #X seulement si consistant,
 * "a confirmer" (avec best_seen) si ca vacille, "non classe" sinon.
 */
function AuditKeywordRank({ kw }: { kw: KeywordRow }) {
  const state = rankState(kw);
  if (state.kind === "stable") {
    const color =
      state.position <= 10
        ? "text-emerald-500"
        : state.position <= 30
        ? "text-amber-500"
        : "text-muted-foreground";
    return (
      <span className={`font-mono text-xs shrink-0 ml-2 ${color}`}>
        #{state.position}
      </span>
    );
  }
  if (state.kind === "unstable") {
    return (
      <span className="shrink-0 ml-2 inline-flex items-center gap-1">
        <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300">
          a confirmer
        </span>
        {state.bestSeen != null && (
          <span className="font-mono text-[10px] text-muted-foreground">
            #{state.bestSeen}
          </span>
        )}
      </span>
    );
  }
  // none | unranked
  return (
    <span className="font-mono text-xs shrink-0 ml-2 text-muted-foreground">
      non classe
    </span>
  );
}

export function SiteAuditPage() {
  const params = useParams<{ siteId: string }>();
  const siteId = params?.siteId;
  const base = `/dashboard/${siteId}`;

  // The full audit blocks on PageSpeed (~20-30s) + backlinks. We fire two
  // requests: a `?fast=1` one that returns the DB-backed signals (score,
  // keywords, decay) in ~1s so the page paints right away, and the full one
  // that fills in PageSpeed + backlinks when it lands. A warm server cache
  // makes both return the complete payload instantly.
  const fullQuery = useQuery<AuditPayload>({
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

  const fastQuery = useQuery<AuditPayload>({
    queryKey: ["site-audit", siteId, "fast"],
    queryFn: async () => {
      const res = await authFetch(`/sites/${siteId}/site-audit/?fast=1`);
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error || "Erreur audit site");
      }
      return res.json();
    },
    staleTime: 60 * 1000,
    // Once the full payload is in hand there's nothing left to fast-load.
    enabled: !!siteId && !fullQuery.data,
  });

  const data = fullQuery.data ?? fastQuery.data;
  // Partial = we're showing the fast payload while the full one is still in
  // flight. Drives the per-card spinners on PageSpeed + backlinks + the score.
  const isPartial = !fullQuery.data && !!data?.partial;
  const isLoading = !data && (fullQuery.isLoading || fastQuery.isLoading);
  const isError = !data && !isLoading;
  const isRefetching = fullQuery.isRefetching;
  const refetch = () => {
    fullQuery.refetch();
    fastQuery.refetch();
  };

  // Strategic opportunities count - tiny GET, used to render the teaser
  // card. Doesn't block the page; if it 404s we just hide the teaser.
  const opportunitiesQuery = useQuery({
    queryKey: ["opportunities-count", siteId],
    queryFn: () => listStrategicOpportunities(Number(siteId)),
    enabled: !!siteId,
    staleTime: 5 * 60 * 1000,
    retry: 0,
  });
  const proposedOpportunities = (
    opportunitiesQuery.data?.results || []
  ).filter((o) => o.status === "proposed");
  const highPriorityCount = proposedOpportunities.filter(
    (o) => o.priority === "high",
  ).length;

  if (isLoading) {
    return (
      <div className="space-y-4 max-w-6xl">
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          Analyse de ton site en cours - on rassemble ton score, tes positions
          et ton declin...
        </div>
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
        <PageBreadcrumb trail={[{ label: "Audit du site" }]} />
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
      <PageBreadcrumb trail={[{ label: "Audit du site" }]} />
      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h1 className="text-2xl font-bold">Audit du site</h1>
          <p className="text-muted-foreground text-sm">
            Vue d&apos;ensemble SEO de{" "}
            <span className="font-mono break-all">{data.site_domain || data.site_name}</span>
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
              <TooltipProvider>
                <Tooltip>
                  <TooltipTrigger asChild>
                    <div
                      className={`text-5xl md:text-6xl font-bold tabular-nums cursor-help ${scoreColor(data.composite_score)}`}
                    >
                      {data.composite_score ?? "-"}
                      <span className="text-xl md:text-2xl text-muted-foreground font-normal">/100</span>
                    </div>
                  </TooltipTrigger>
                  <TooltipContent className="max-w-xs">
                    <p className="font-medium mb-1">Score SEO composite</p>
                    <p>
                      Moyenne ponderee de 4 signaux : PageSpeed (25%), positions
                      des mots-cles suivis (25%), profil de liens (25%) et
                      fraicheur du contenu (25%). Sources : Google PageSpeed
                      Insights, GSC ou estimations Serper.
                    </p>
                    <p className="mt-2 text-muted-foreground">
                      Excellent : 80+, Bon : 60-79, Moyen : 40-59, Faible : &lt;40.
                    </p>
                  </TooltipContent>
                </Tooltip>
              </TooltipProvider>
              <div className={`text-sm font-medium ${scoreColor(data.composite_score)}`}>
                {scoreLabel(data.composite_score)}
              </div>
              {isPartial && (
                <div className="flex items-center gap-1.5 text-[11px] text-muted-foreground mt-1">
                  <Loader2 className="h-3 w-3 animate-spin shrink-0" />
                  Score preliminaire - PageSpeed et liens se calculent encore
                </div>
              )}
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

      {/* Strategic opportunities teaser. Only renders when at least one
          proposed opportunity exists - the empty state lives on the
          dedicated /opportunites page so we don't double-noise this view. */}
      {proposedOpportunities.length > 0 && (
        <Card className="border-amber-500/30 bg-gradient-to-r from-amber-500/[0.06] via-amber-500/[0.02] to-transparent">
          <CardContent className="py-5 flex items-start gap-4 flex-wrap">
            <span className="h-10 w-10 rounded-lg bg-amber-500/15 border border-amber-500/30 flex items-center justify-center shrink-0">
              <Lightbulb className="h-5 w-5 text-amber-400" />
            </span>
            <div className="flex-1 min-w-[16rem]">
              <p className="text-[10px] font-mono uppercase tracking-wider text-amber-400 mb-1">
                Opportunités stratégiques détectées
              </p>
              <p className="font-semibold leading-snug">
                {proposedOpportunities.length} page
                {proposedOpportunities.length > 1 ? "s" : ""} à créer pour
                capturer le trafic de tes mots-clés
                {highPriorityCount > 0 && (
                  <>
                    {" "}
                    <span className="text-emerald-400">
                      ({highPriorityCount} priorité haute)
                    </span>
                  </>
                )}
              </p>
              <p className="text-sm text-muted-foreground mt-1">
                Claude a analysé tes mots-clés transactionnels et ton offre
                pour proposer des landings qui ranquent ET convertissent.
              </p>
            </div>
            <Link href={`${base}/opportunites`}>
              <Button>
                Voir les opportunités
                <ArrowRight className="h-4 w-4 ml-2" />
              </Button>
            </Link>
          </CardContent>
        </Card>
      )}

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
                className={`border rounded-md p-3 flex flex-wrap items-center gap-3 ${severityClasses(reco.severity)}`}
              >
                {severityIcon(reco.severity)}
                <div className="flex-1 min-w-[10rem] text-sm">{reco.message}</div>
                <Link href={reco.cta_href}>
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
                <Link href={`${base}/positions`}>
                  <Button size="sm">
                    Ajouter mes mots-cles
                    <ArrowRight className="h-3.5 w-3.5 ml-1.5" />
                  </Button>
                </Link>
              </div>
            ) : (
              <>
                <div className="flex items-baseline gap-3 mb-1">
                  <span className="text-2xl font-bold tabular-nums">
                    {data.keywords.top_10_count}/{data.keywords.total}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    dans le top 10 stable (
                    {Math.round(data.keywords.top_10_pct || 0)}%)
                  </span>
                </div>
                <AuditLastCheckedNote iso={data.keywords.last_checked ?? null} />
                <div className="mt-3 space-y-1 max-h-64 overflow-y-auto">
                  {(data.keywords.rows || []).map((kw) => (
                    <div
                      key={kw.id}
                      className="flex items-center justify-between text-sm border-b border-border/30 py-1.5"
                    >
                      <span className="truncate">{kw.keyword}</span>
                      <AuditKeywordRank kw={kw} />
                    </div>
                  ))}
                </div>
                <Link href={`${base}/positions`}>
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
            {data.pagespeed.pending ? (
              <div className="flex items-center justify-center gap-2 text-sm text-muted-foreground py-6">
                <Loader2 className="h-4 w-4 animate-spin" />
                Analyse PageSpeed en cours (~20-30s)...
              </div>
            ) : data.pagespeed.error ? (
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
            {data.backlinks.pending ? (
              <div className="flex items-center justify-center gap-2 text-sm text-muted-foreground py-6">
                <Loader2 className="h-4 w-4 animate-spin" />
                Analyse des liens en cours...
              </div>
            ) : data.backlinks.error ? (
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
                <Link href={`${base}/parametres/gsc`}>
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
                <Link href={`${base}/decay`}>
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

export default SiteAuditPage;
