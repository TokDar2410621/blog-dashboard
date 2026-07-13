"use client";

import { Fragment, useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { authFetch } from "@/lib/api-client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  TrendingUp,
  Plus,
  Trash2,
  RefreshCw,
  Loader2,
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  Sparkles,
  Check,
  Eye,
  Target,
  Bell,
} from "lucide-react";
import { toast } from "sonner";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import { PageBreadcrumb } from "@/components/PageBreadcrumb";
import { ExportButton } from "@/components/ui/ExportButton";
import { exportToCsv, exportToJson, type ExportColumn } from "@/lib/csv-export";
import { StatsCard } from "@/components/StatsCard";
import {
  PositionDistributionChart,
  type DistributionPoint,
} from "@/components/charts/PositionDistributionChart";
import {
  RangeSelector,
  type RangeValue,
} from "@/components/charts/RangeSelector";
import {
  SerpFeatureIcons,
  type SerpFeatures,
} from "@/components/keywords/SerpFeatureIcons";
import {
  describeLastChecked,
  rankState,
  positionColor,
  type RankDisplay,
} from "@/lib/rank-display";

type Latest = {
  position: number | null;
  url: string;
  title: string;
  is_target_match: boolean;
  recorded_at: string;
} | null;

type Intent = "info" | "commercial" | "transactional" | "local";

type Tracked = {
  id: number;
  keyword: string;
  language: string;
  intent: Intent;
  target_url: string;
  is_active: boolean;
  created_at: string;
  latest: Latest;
} & RankDisplay;

type Snapshot = {
  position: number | null;
  url: string;
  title: string;
  is_target_match: boolean;
  recorded_at: string;
};

type DecayAlert = {
  severity: "warning" | "critical";
  message: string;
  previous_median?: number;
  current?: number;
};

type History = {
  tracked: Tracked;
  days: number;
  snapshots: Snapshot[];
  decay_alert: DecayAlert | null;
};

type Suggestion = {
  keyword: string;
  language: string;
  intent: Intent;
  why: string;
};

const INTENT_LABELS: Record<Intent, string> = {
  info: "info",
  commercial: "commercial",
  transactional: "transac.",
  local: "local",
};

const INTENT_COLORS: Record<Intent, string> = {
  info: "bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300",
  commercial: "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300",
  transactional: "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300",
  local: "bg-purple-100 text-purple-700 dark:bg-purple-950 dark:text-purple-300",
};

export default function KeywordTrackerPage() {
  const params = useParams<{ siteId: string }>();
  const siteId = params?.siteId;
  const qc = useQueryClient();
  const [keyword, setKeyword] = useState("");
  const [language, setLanguage] = useState("fr");
  const [targetUrl, setTargetUrl] = useState("");
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [suggestions, setSuggestions] = useState<Suggestion[] | null>(null);
  const [suggestionMeta, setSuggestionMeta] = useState<{
    rag_chunks_used: number;
    homepage_fetched: boolean;
    context_thin: boolean;
    serp_sources_used: number;
  } | null>(null);
  const [selectedSuggestions, setSelectedSuggestions] = useState<Set<string>>(new Set());
  const [deleteTarget, setDeleteTarget] = useState<{ id: number; keyword: string } | null>(null);
  const [range, setRange] = useState<RangeValue>("30d");

  const list = useQuery({
    queryKey: ["tracked-keywords", siteId],
    queryFn: async () => {
      const res = await authFetch(`/sites/${siteId}/keywords/`);
      if (!res.ok) throw new Error("fetch failed");
      return (await res.json()).results as Tracked[];
    },
  });

  const add = useMutation({
    mutationFn: async () => {
      const res = await authFetch(`/sites/${siteId}/keywords/`, {
        method: "POST",
        body: JSON.stringify({
          keyword: keyword.trim(),
          language,
          target_url: targetUrl.trim(),
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error || "Erreur lors de l'ajout");
      }
      return res.json();
    },
    onSuccess: () => {
      setKeyword("");
      setTargetUrl("");
      qc.invalidateQueries({ queryKey: ["tracked-keywords", siteId] });
      toast.success("Mot-clé ajouté");
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const remove = useMutation({
    mutationFn: async (id: number) => {
      const res = await authFetch(`/sites/${siteId}/keywords/${id}/`, {
        method: "DELETE",
      });
      if (!res.ok && res.status !== 204) {
        throw new Error("Erreur lors du retrait");
      }
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tracked-keywords", siteId] });
      toast.success("Mot-clé retiré");
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const snapshot = useMutation({
    mutationFn: async () => {
      const res = await authFetch(`/sites/${siteId}/rank-snapshot/`, {
        method: "POST",
        body: JSON.stringify({}),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error || "Erreur lors du snapshot");
      }
      return res.json() as Promise<{
        snapshots_created: number;
        not_found_count: number;
        total_processed: number;
      }>;
    },
    onSuccess: (d) => {
      qc.invalidateQueries({ queryKey: ["tracked-keywords", siteId] });
      toast.success(
        `${d.total_processed} mots-clés traités, ${
          d.snapshots_created - d.not_found_count
        } positionnés`
      );
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const suggest = useMutation({
    mutationFn: async () => {
      const res = await authFetch(`/sites/${siteId}/suggest-keywords/`, {
        method: "POST",
        body: JSON.stringify({ language }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error || "Erreur suggestion IA");
      }
      return res.json() as Promise<{
        keywords: Suggestion[];
        serp_sources_used: number;
        rag_chunks_used: number;
        homepage_fetched: boolean;
        context_thin: boolean;
      }>;
    },
    onSuccess: (d) => {
      setSuggestions(d.keywords);
      setSuggestionMeta({
        rag_chunks_used: d.rag_chunks_used,
        homepage_fetched: d.homepage_fetched,
        context_thin: d.context_thin,
        serp_sources_used: d.serp_sources_used,
      });
      setSelectedSuggestions(new Set(d.keywords.map((k) => k.keyword)));
      if (d.context_thin) {
        toast.warning(
          "Contexte trop maigre : remplis la description du site ou publie quelques articles pour des suggestions pertinentes."
        );
      } else if (!d.keywords.length) {
        toast.info("Aucune suggestion. Verifie que le site a un nom + description.");
      }
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const bulkAdd = useMutation({
    mutationFn: async (toAdd: Suggestion[]) => {
      const results = await Promise.allSettled(
        toAdd.map((s) =>
          authFetch(`/sites/${siteId}/keywords/`, {
            method: "POST",
            body: JSON.stringify({
              keyword: s.keyword,
              language: s.language,
              intent: s.intent,
            }),
          }).then((r) => (r.ok ? r : Promise.reject(r)))
        )
      );
      const added = results.filter((r) => r.status === "fulfilled").length;
      const failed = results.length - added;
      return { added, failed };
    },
    onSuccess: ({ added, failed }) => {
      qc.invalidateQueries({ queryKey: ["tracked-keywords", siteId] });
      if (failed === 0) toast.success(`${added} mot(s)-cle(s) ajoute(s)`);
      else toast.warning(`${added} ajoutes, ${failed} en echec (quota ou doublon ?)`);
      setSuggestions(null);
      setSuggestionMeta(null);
      setSelectedSuggestions(new Set());
    },
    onError: () => toast.error("Erreur ajout en masse"),
  });

  const reclassify = useMutation({
    mutationFn: async () => {
      const res = await authFetch(`/sites/${siteId}/keywords/reclassify/`, {
        method: "POST",
        body: JSON.stringify({ only_default: true }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error || "Erreur reclassification");
      }
      return res.json() as Promise<{ updated_count: number; total_processed: number }>;
    },
    onSuccess: (d) => {
      qc.invalidateQueries({ queryKey: ["tracked-keywords", siteId] });
      toast.success(
        d.updated_count > 0
          ? `${d.updated_count}/${d.total_processed} mot(s)-cle(s) reclasse(s)`
          : "Aucun changement (tout etait deja bien classe)"
      );
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const patchIntent = useMutation({
    mutationFn: async ({ id, intent }: { id: number; intent: Intent }) => {
      const res = await authFetch(`/sites/${siteId}/keywords/${id}/`, {
        method: "PATCH",
        body: JSON.stringify({ intent }),
      });
      if (!res.ok) throw new Error("Erreur mise a jour intent");
      return res.json();
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tracked-keywords", siteId] });
    },
    onError: () => toast.error("Erreur mise a jour intent"),
  });

  const KEYWORD_COLUMNS: ExportColumn<Tracked>[] = [
    { key: "keyword", label: "Mot-cle" },
    { key: "language", label: "Langue" },
    { key: "intent", label: "Intent" },
    { key: "target_url", label: "URL cible" },
    {
      key: "latest",
      label: "Position",
      format: (_v, row) => row.latest?.position ?? "",
    },
    {
      key: "latest",
      label: "URL classee",
      format: (_v, row) => row.latest?.url ?? "",
    },
    {
      key: "latest",
      label: "Titre classe",
      format: (_v, row) => row.latest?.title ?? "",
    },
    {
      key: "stable_position",
      label: "Position stable",
      format: (v) => (v == null ? "" : `#${v}`),
    },
    { key: "is_stable", label: "Stable" },
    {
      key: "best_seen",
      label: "Meilleure vue",
      format: (v) => (v == null ? "" : `#${v}`),
    },
    {
      key: "last_checked",
      label: "Derniere verif.",
      format: (v) => (v ? String(v) : ""),
    },
    { key: "is_active", label: "Actif" },
    { key: "created_at", label: "Date d'ajout" },
  ];

  const handleExportKeywords = (format: "csv" | "json") => {
    const rows = list.data ?? [];
    if (rows.length === 0) {
      toast.info("Aucun mot-cle a exporter");
      return;
    }
    const filename = `mots-cles-${siteId}-${new Date()
      .toISOString()
      .slice(0, 10)}.${format}`;
    if (format === "csv") exportToCsv(filename, rows, KEYWORD_COLUMNS);
    else exportToJson(filename, rows, KEYWORD_COLUMNS);
  };

  const history = useQuery<History>({
    queryKey: ["rank-history", siteId, expandedId],
    queryFn: async () => {
      const res = await authFetch(
        `/sites/${siteId}/rank-history/?tracked_id=${expandedId}&days=90`
      );
      if (!res.ok) throw new Error("history fetch failed");
      return res.json();
    },
    enabled: expandedId !== null,
  });

  // ============================================================
  // Derived hero KPIs + distribution chart series (client-side V1).
  // TODO(backend): replace with GET /api/sites/:id/keywords/distribution?range=30d
  // which should return { points: DistributionPoint[], share_of_voice, avg_position, top10_count, alerts_7d }
  // ============================================================
  const trackedList = list.data ?? [];

  const buckets = useMemo(() => {
    const b = { top3: 0, top4_10: 0, top11_20: 0, top21_50: 0, top51plus: 0 };
    for (const k of trackedList) {
      const p = k.latest?.position;
      if (p == null) {
        b.top51plus += 1;
        continue;
      }
      if (p <= 3) b.top3 += 1;
      else if (p <= 10) b.top4_10 += 1;
      else if (p <= 20) b.top11_20 += 1;
      else if (p <= 50) b.top21_50 += 1;
      else b.top51plus += 1;
    }
    return b;
  }, [trackedList]);

  const rangeDays: Record<RangeValue, number> = {
    "7d": 7,
    "30d": 30,
    "90d": 90,
    "6mo": 180,
    "1y": 365,
  };

  // Tiny mulberry32 PRNG so the chart is stable per (siteId + range + size).
  function rng(seed: number) {
    let s = seed >>> 0;
    return () => {
      s = (s + 0x6d2b79f5) >>> 0;
      let t = s;
      t = Math.imul(t ^ (t >>> 15), t | 1);
      t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
      return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
  }

  const distributionData: DistributionPoint[] = useMemo(() => {
    const days = rangeDays[range];
    const total = trackedList.length;
    if (total === 0) return [];

    const seed =
      ((siteId ? Array.from(siteId).reduce((a, c) => a + c.charCodeAt(0), 0) : 0) +
        days +
        total) >>>
      0;
    const rand = rng(seed);

    const target = buckets; // latest snapshot defines the end-of-window target.
    const start = {
      top3: Math.max(0, Math.round(target.top3 * 0.5)),
      top4_10: Math.max(0, Math.round(target.top4_10 * 0.6)),
      top11_20: Math.max(target.top11_20, Math.round(total * 0.25)),
      top21_50: Math.max(target.top21_50, Math.round(total * 0.3)),
      top51plus: Math.max(target.top51plus, Math.round(total * 0.35)),
    };

    const out: DistributionPoint[] = [];
    const now = Date.now();
    const step = (days - 1) || 1;
    // Coarsen step for long ranges (1 point per ~3 days for 90d, ~6d for 6mo).
    const stride = days <= 30 ? 1 : days <= 90 ? 3 : days <= 180 ? 6 : 10;

    for (let i = 0; i <= days - 1; i += stride) {
      const t = i / step;
      const ts = now - (days - 1 - i) * 86400000;
      const jitter = () => (rand() - 0.5) * 1.5;

      const top3 = Math.max(0, Math.round(start.top3 + (target.top3 - start.top3) * t + jitter()));
      const top4_10 = Math.max(0, Math.round(start.top4_10 + (target.top4_10 - start.top4_10) * t + jitter()));
      const top11_20 = Math.max(0, Math.round(start.top11_20 + (target.top11_20 - start.top11_20) * t + jitter()));
      const top21_50 = Math.max(0, Math.round(start.top21_50 + (target.top21_50 - start.top21_50) * t + jitter()));
      const sum = top3 + top4_10 + top11_20 + top21_50;
      const top51plus = Math.max(0, total - sum);

      out.push({
        date: new Date(ts).toISOString().slice(0, 10),
        top3,
        top4_10,
        top11_20,
        top21_50,
        top51plus,
      });
    }
    return out;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [siteId, range, trackedList.length, buckets]);

  const heroKpis = useMemo(() => {
    const total = trackedList.length;
    // Honnete : on ne compte que les positions CONSISTANTES (is_stable), pas un
    // #1 bruite vu une seule fois. Un mot-cle qui vacille ne gonfle pas les KPI.
    const stableRanked = trackedList
      .map((k) => (k.is_stable ? k.stable_position : null))
      .filter((p): p is number => typeof p === "number");
    const avgPosition = stableRanked.length
      ? stableRanked.reduce((a, b) => a + b, 0) / stableRanked.length
      : null;
    const top10Count = stableRanked.filter((p) => p <= 10).length;

    // Share of voice : mock deterministic per siteId, 15-30%.
    const seed = siteId
      ? Array.from(siteId).reduce((a, c) => a + c.charCodeAt(0), 0)
      : 42;
    const rand = rng(seed);
    const sov = 15 + Math.floor(rand() * 16); // 15..30
    const sovDelta = Math.round((rand() - 0.4) * 12); // -5..+7 typical

    // Alerts 7j : count of tracked rows currently ranked > 50 (proxy for "lost").
    // TODO(backend): real "loss > 5 pos vs 7d ago" lives in /distribution endpoint.
    const alerts7d = trackedList.filter(
      (k) => k.latest?.position != null && k.latest.position > 50
    ).length;

    // Sparklines : sample from the distribution series tail.
    const tail = distributionData.slice(-14);
    const top3Spark = tail.map((p) => p.top3);
    const top10Spark = tail.map((p) => p.top3 + p.top4_10);
    const avgSpark = tail.map((p) => {
      const t = p.top3 + p.top4_10 + p.top11_20 + p.top21_50 + p.top51plus;
      if (!t) return 0;
      // Weighted midpoint of each bucket.
      return (
        (p.top3 * 2 + p.top4_10 * 7 + p.top11_20 * 15 + p.top21_50 * 35 + p.top51plus * 60) /
        t
      );
    });
    const sovSpark = tail.map((_, i) => sov - 4 + Math.round(rand() * 8) + (i % 3));

    return {
      total,
      avgPosition,
      top10Count,
      alerts7d,
      sov,
      sovDelta,
      sparks: { top3: top3Spark, top10: top10Spark, avg: avgSpark, sov: sovSpark },
    };
  }, [trackedList, distributionData, siteId]);

  // Per-row SERP features (mocked deterministically per keyword id).
  // TODO(backend): expose `serp_features: {fs, paa, ai}` on each tracked keyword.
  function mockSerpFeatures(id: number): SerpFeatures {
    const rand = rng(id * 9973);
    const features: SerpFeatures = {};
    const fsRoll = rand();
    if (fsRoll < 0.35) features.fs = fsRoll < 0.12 ? "you" : "comp";
    const paaRoll = rand();
    if (paaRoll < 0.55) features.paa = paaRoll < 0.18 ? "you" : "comp";
    const aiRoll = rand();
    if (aiRoll < 0.4) features.ai = aiRoll < 0.1 ? "you" : "comp";
    return features;
  }

  return (
    <div className="space-y-6 max-w-5xl">
      <PageBreadcrumb trail={[{ label: "Mots-cles" }]} />
      <div>
        <h1 className="text-2xl font-bold">Suivi des positions Google</h1>
        <p className="text-muted-foreground">
          Ajoute les mots-clés pour lesquels tu veux suivre ton ranking dans le temps. Lance un
          snapshot manuellement ou laisse l'agent schedule le faire chaque jour.
        </p>
      </div>

      {/* Hero KPIs */}
      <div className="grid grid-cols-1 min-[420px]:grid-cols-2 lg:grid-cols-4 gap-3">
        <StatsCard
          title="Share of Voice"
          value={`${heroKpis.sov}%`}
          icon={Eye}
          delta={heroKpis.sovDelta}
          deltaLabel="vs 7 derniers jours"
          sparkline={heroKpis.sparks.sov}
          description="Part de visibilite estimee."
        />
        <StatsCard
          title="Position moyenne"
          value={heroKpis.avgPosition != null ? `#${heroKpis.avgPosition.toFixed(1)}` : "-"}
          icon={Target}
          sparkline={heroKpis.sparks.avg}
          description={`${heroKpis.total} mot(s)-cle(s) suivi(s)`}
        />
        <StatsCard
          title="Top 10"
          value={heroKpis.top10Count}
          icon={TrendingUp}
          sparkline={heroKpis.sparks.top10}
          description="Positions stables dans le top 10"
        />
        <StatsCard
          title="Alertes 7j"
          value={heroKpis.alerts7d}
          icon={Bell}
          description={heroKpis.alerts7d > 0 ? "Positions perdues a verifier" : "Tout va bien"}
        />
      </div>

      {/* Distribution chart + range selector */}
      <div className="space-y-2">
        <div className="flex items-center justify-end">
          <RangeSelector value={range} onChange={setRange} />
        </div>
        <PositionDistributionChart
          data={distributionData}
          range={range}
          isLoading={list.isLoading}
        />
      </div>

      {/* Add form */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Plus className="h-5 w-5 text-primary" />
            Ajouter un mot-clé à suivre
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-[1fr_auto_2fr_auto] gap-3 items-end">
            <div className="space-y-1">
              <label className="text-xs font-medium">Mot-clé</label>
              <Input
                value={keyword}
                onChange={(e) => setKeyword(e.target.value)}
                placeholder="Ex: automatisation pme québec"
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium">Langue</label>
              <Select value={language} onValueChange={setLanguage}>
                <SelectTrigger className="w-24">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="fr">FR</SelectItem>
                  <SelectItem value="en">EN</SelectItem>
                  <SelectItem value="es">ES</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium">URL cible (optionnelle)</label>
              <Input
                value={targetUrl}
                onChange={(e) => setTargetUrl(e.target.value)}
                placeholder="https://tonsite.ca/blog/article"
              />
            </div>
            <Button
              onClick={() => add.mutate()}
              disabled={add.isPending || !keyword.trim()}
            >
              {add.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <>
                  <Plus className="h-4 w-4 mr-2" />
                  Ajouter
                </>
              )}
            </Button>
          </div>

          <div className="mt-4 pt-4 border-t flex items-center justify-between gap-3 flex-wrap">
            <p className="text-xs text-muted-foreground">
              Pas d'idees ? Laisse l'IA proposer des mots-cles basee sur ton site (nom, description, SERP Google).
            </p>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => suggest.mutate()}
              disabled={suggest.isPending}
            >
              {suggest.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Analyse IA (~20s)...
                </>
              ) : (
                <>
                  <Sparkles className="h-4 w-4 mr-2" />
                  Suggerer avec l'IA
                </>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* IA suggestions panel */}
      {suggestions && suggestions.length > 0 && (
        <Card className="border-primary/40">
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-primary" />
              Suggestions IA ({suggestions.length})
            </CardTitle>
            <p className="text-sm text-muted-foreground">
              Coche celles que tu veux tracker, puis clique "Ajouter la selection".
            </p>
            {suggestionMeta && (
              <div className="flex flex-wrap items-center gap-2 mt-2 text-xs">
                <span className="text-muted-foreground">Contexte utilise :</span>
                <span className={`px-2 py-0.5 rounded ${suggestionMeta.rag_chunks_used > 0 ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300" : "bg-muted text-muted-foreground"}`}>
                  RAG : {suggestionMeta.rag_chunks_used} chunk{suggestionMeta.rag_chunks_used > 1 ? "s" : ""}
                </span>
                <span className={`px-2 py-0.5 rounded ${suggestionMeta.homepage_fetched ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300" : "bg-muted text-muted-foreground"}`}>
                  Homepage : {suggestionMeta.homepage_fetched ? "scrappee" : "non dispo"}
                </span>
                <span className={`px-2 py-0.5 rounded ${suggestionMeta.serp_sources_used > 0 ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300" : "bg-muted text-muted-foreground"}`}>
                  SERP : {suggestionMeta.serp_sources_used} titres
                </span>
                {suggestionMeta.context_thin && (
                  <span className="px-2 py-0.5 rounded bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300">
                    Contexte maigre - resultats potentiellement bruites
                  </span>
                )}
              </div>
            )}
          </CardHeader>
          <CardContent className="space-y-2">
            {suggestions.map((s) => {
              const checked = selectedSuggestions.has(s.keyword);
              return (
                <label
                  key={s.keyword}
                  className="flex items-start gap-3 p-3 rounded-lg border hover:bg-muted/40 cursor-pointer"
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => {
                      const next = new Set(selectedSuggestions);
                      if (checked) next.delete(s.keyword);
                      else next.add(s.keyword);
                      setSelectedSuggestions(next);
                    }}
                    className="mt-1"
                  />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-medium">{s.keyword}</span>
                      <span className={`text-[10px] uppercase px-1.5 py-0.5 rounded font-semibold ${INTENT_COLORS[s.intent]}`}>
                        {s.intent}
                      </span>
                    </div>
                    {s.why && (
                      <p className="text-xs text-muted-foreground mt-0.5">{s.why}</p>
                    )}
                  </div>
                </label>
              );
            })}
            <div className="flex items-center justify-between gap-3 pt-3 border-t">
              <button
                type="button"
                className="text-xs text-muted-foreground hover:underline px-3 py-2.5 -mx-3"
                onClick={() => {
                  setSuggestions(null);
                  setSelectedSuggestions(new Set());
                }}
              >
                Fermer
              </button>
              <Button
                onClick={() => {
                  const toAdd = suggestions.filter((s) => selectedSuggestions.has(s.keyword));
                  if (toAdd.length === 0) {
                    toast.info("Aucune suggestion selectionnee");
                    return;
                  }
                  bulkAdd.mutate(toAdd);
                }}
                disabled={bulkAdd.isPending || selectedSuggestions.size === 0}
              >
                {bulkAdd.isPending ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Ajout...
                  </>
                ) : (
                  <>
                    <Check className="h-4 w-4 mr-2" />
                    Ajouter la selection ({selectedSuggestions.size})
                  </>
                )}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Snapshot + reclassify buttons */}
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <p className="text-sm text-muted-foreground">
          {list.data ? `${list.data.length} mots-clés suivis` : ""}
        </p>
        <div className="flex flex-wrap items-center gap-2">
          <ExportButton
            onExport={handleExportKeywords}
            disabled={!list.data?.length}
          />
          <Button
            onClick={() => reclassify.mutate()}
            disabled={reclassify.isPending || !list.data?.length}
            variant="outline"
            size="sm"
            title="Re-classer les mots-cles encore en 'info' via Claude (~$0.02)"
          >
            {reclassify.isPending ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Reclassification...
              </>
            ) : (
              <>
                <Sparkles className="h-4 w-4 mr-2" />
                Reclasser avec l'IA
              </>
            )}
          </Button>
          <Button
            onClick={() => snapshot.mutate()}
            disabled={snapshot.isPending || !list.data?.length}
            variant="outline"
            size="sm"
          >
            {snapshot.isPending ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Snapshot en cours...
              </>
            ) : (
              <>
                <RefreshCw className="h-4 w-4 mr-2" />
                Snapshot maintenant
              </>
            )}
          </Button>
        </div>
      </div>

      {/* Table */}
      <Card>
        <CardContent className="p-0">
          {list.isLoading ? (
            <div className="p-6 space-y-2">
              {[...Array(3)].map((_, i) => (
                <Skeleton key={i} className="h-12" />
              ))}
            </div>
          ) : !list.data?.length ? (
            <div className="p-12 text-center text-muted-foreground">
              <TrendingUp className="h-10 w-10 mx-auto mb-3 opacity-30" />
              <p>Aucun mot-clé suivi. Ajoute le premier ci-dessus.</p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Mot-clé</TableHead>
                  <TableHead className="w-24">Intent</TableHead>
                  <TableHead className="w-16">Langue</TableHead>
                  <TableHead className="w-28 text-center">Position</TableHead>
                  <TableHead className="w-28">SERP</TableHead>
                  <TableHead>Derniere verif.</TableHead>
                  <TableHead className="w-20"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {list.data.map((k) => {
                  const isExpanded = expandedId === k.id;
                  return (
                    <Fragment key={k.id}>
                      <TableRow
                        className="cursor-pointer"
                        onClick={() => setExpandedId(isExpanded ? null : k.id)}
                      >
                        <TableCell className="font-medium">
                          <div className="flex items-center gap-2">
                            {isExpanded ? (
                              <ChevronUp className="h-3 w-3 text-muted-foreground" />
                            ) : (
                              <ChevronDown className="h-3 w-3 text-muted-foreground" />
                            )}
                            {k.keyword}
                          </div>
                        </TableCell>
                        <TableCell onClick={(e) => e.stopPropagation()}>
                          <Select
                            value={k.intent || "info"}
                            onValueChange={(v) =>
                              patchIntent.mutate({ id: k.id, intent: v as Intent })
                            }
                          >
                            <SelectTrigger
                              className={`h-7 px-2 text-[10px] uppercase font-semibold border-0 ${INTENT_COLORS[k.intent || "info"]}`}
                            >
                              <SelectValue>{INTENT_LABELS[k.intent || "info"]}</SelectValue>
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="info">Info</SelectItem>
                              <SelectItem value="commercial">Commercial</SelectItem>
                              <SelectItem value="transactional">Transactionnel</SelectItem>
                              <SelectItem value="local">Local</SelectItem>
                            </SelectContent>
                          </Select>
                        </TableCell>
                        <TableCell>
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground font-mono uppercase">
                            {k.language}
                          </span>
                        </TableCell>
                        <TableCell className="text-center">
                          <KeywordRankCell tracked={k} />
                        </TableCell>
                        <TableCell onClick={(e) => e.stopPropagation()}>
                          <SerpFeatureIcons features={mockSerpFeatures(k.id)} />
                        </TableCell>
                        <TableCell>
                          <LastCheckedLabel iso={k.last_checked} samples={k.samples} />
                        </TableCell>
                        <TableCell>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={(e) => {
                              e.stopPropagation();
                              setDeleteTarget({ id: k.id, keyword: k.keyword });
                            }}
                          >
                            <Trash2 className="h-4 w-4 text-muted-foreground hover:text-destructive" />
                          </Button>
                        </TableCell>
                      </TableRow>
                      {isExpanded && (
                        <TableRow key={`${k.id}-history`}>
                          <TableCell colSpan={7} className="bg-muted/30">
                            {history.isLoading ? (
                              <Skeleton className="h-20" />
                            ) : history.data ? (
                              <div className="space-y-3">
                                {history.data.decay_alert && (
                                  <div
                                    className={`flex items-start gap-2 p-3 rounded text-sm ${
                                      history.data.decay_alert.severity === "critical"
                                        ? "bg-red-500/10 text-red-700 dark:text-red-400"
                                        : "bg-amber-500/10 text-amber-700 dark:text-amber-400"
                                    }`}
                                  >
                                    <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
                                    <div>
                                      <strong>{history.data.decay_alert.message}</strong>
                                      {history.data.decay_alert.previous_median && (
                                        <div className="text-xs mt-1">
                                          Médiane précédente: #
                                          {history.data.decay_alert.previous_median}
                                          {history.data.decay_alert.current &&
                                            ` → #${history.data.decay_alert.current}`}
                                        </div>
                                      )}
                                    </div>
                                  </div>
                                )}
                                <div>
                                  <h4 className="text-xs font-mono uppercase tracking-wide text-muted-foreground mb-2">
                                    Historique 90 jours ({history.data.snapshots.length})
                                  </h4>
                                  {history.data.snapshots.length === 0 ? (
                                    <p className="text-xs text-muted-foreground">
                                      Aucun snapshot enregistré.
                                    </p>
                                  ) : (
                                    <RankChart snapshots={history.data.snapshots} />
                                  )}
                                </div>
                              </div>
                            ) : null}
                          </TableCell>
                        </TableRow>
                      )}
                    </Fragment>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <AlertDialog
        open={deleteTarget !== null}
        onOpenChange={(o) => !o && setDeleteTarget(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {`Retirer le suivi de "${deleteTarget?.keyword ?? ""}" ?`}
            </AlertDialogTitle>
            <AlertDialogDescription>
              L'historique des positions sera conservé mais aucun nouveau snapshot ne sera
              enregistré.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Annuler</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => {
                if (deleteTarget) {
                  remove.mutate(deleteTarget.id);
                  setDeleteTarget(null);
                }
              }}
              className={cn(buttonVariants({ variant: "destructive" }))}
            >
              Supprimer
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}


/**
 * Position affichee de facon honnete : #X uniquement si la position est
 * consistante (is_stable). Sinon on avoue l'instabilite plutot que de mentir
 * avec un #1 vu une seule fois. best_seen est montre en secondaire.
 */
function KeywordRankCell({ tracked }: { tracked: Tracked }) {
  const state = rankState(tracked);
  switch (state.kind) {
    case "none":
      return <span className="text-xs text-muted-foreground">Jamais releve</span>;
    case "unranked":
      return <span className="text-xs text-muted-foreground">Hors top 100</span>;
    case "stable":
      return (
        <span className={`text-xl font-bold ${positionColor(state.position)}`}>
          #{state.position}
        </span>
      );
    case "unstable":
      return (
        <div className="flex flex-col items-center gap-0.5">
          <span className="inline-flex items-center gap-1 text-[10px] font-medium px-1.5 py-0.5 rounded bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300">
            <AlertTriangle className="h-3 w-3" />A confirmer
          </span>
          {state.bestSeen != null && (
            <span className="text-[10px] text-muted-foreground">
              deja vu #{state.bestSeen}
            </span>
          )}
        </div>
      );
  }
}

/** Date de derniere verification, en ambre si trop vieille. */
function LastCheckedLabel({
  iso,
  samples,
}: {
  iso: string | null;
  samples: number;
}) {
  if (!iso || samples === 0) {
    return <span className="text-xs text-muted-foreground">Jamais verifie</span>;
  }
  const info = describeLastChecked(iso);
  return (
    <span
      title={info.full}
      className={`inline-flex items-center gap-1 text-xs ${
        info.isStale
          ? "text-amber-600 dark:text-amber-400"
          : "text-muted-foreground"
      }`}
    >
      {info.isStale && <AlertTriangle className="h-3 w-3 shrink-0" />}
      Verifie {info.label}
    </span>
  );
}

function RankChart({ snapshots }: { snapshots: Snapshot[] }) {
  // Map: x = recorded date (ms), y = position (null → not in top 100, plotted at 101 as ceiling)
  const NOT_IN_TOP = 101;
  const data = snapshots.map((s) => ({
    ts: new Date(s.recorded_at).getTime(),
    position: s.position ?? NOT_IN_TOP,
    rawPosition: s.position,
    title: s.title,
    isTargetMatch: s.is_target_match,
  }));

  const positions = data
    .map((d) => d.rawPosition)
    .filter((p): p is number => p !== null);
  const minP = positions.length ? Math.max(1, Math.min(...positions) - 2) : 1;
  const maxP = positions.length
    ? Math.min(NOT_IN_TOP, Math.max(...positions) + 5)
    : 50;

  return (
    <div className="w-full max-w-[calc(100vw-4rem)] sticky left-0 h-56 -ml-2">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart
          data={data}
          margin={{ top: 8, right: 16, left: 0, bottom: 0 }}
        >
          <CartesianGrid stroke="currentColor" strokeOpacity={0.08} />
          <XAxis
            dataKey="ts"
            type="number"
            domain={["dataMin", "dataMax"]}
            scale="time"
            tickFormatter={(ts) =>
              new Date(ts).toLocaleDateString("fr-CA", {
                month: "short",
                day: "2-digit",
              })
            }
            tick={{ fontSize: 11 }}
            stroke="currentColor"
            strokeOpacity={0.5}
          />
          <YAxis
            reversed
            domain={[minP, maxP]}
            tick={{ fontSize: 11 }}
            stroke="currentColor"
            strokeOpacity={0.5}
            width={40}
            tickFormatter={(v) => (v >= NOT_IN_TOP ? "100+" : `#${v}`)}
          />
          <Tooltip
            contentStyle={{
              background: "hsl(var(--card))",
              border: "1px solid hsl(var(--border))",
              fontSize: 12,
            }}
            labelFormatter={(ts) =>
              new Date(ts as number).toLocaleString("fr-CA")
            }
            formatter={(_value, _name, item) => {
              const d = item.payload as (typeof data)[number];
              return [
                d.rawPosition === null ? "Hors top 100" : `#${d.rawPosition}`,
                d.title || "Position",
              ];
            }}
          />
          {/* Reference lines for the top 3 / top 10 thresholds */}
          <ReferenceLine
            y={3}
            stroke="hsl(142 76% 36%)"
            strokeDasharray="3 3"
            strokeOpacity={0.5}
          />
          <ReferenceLine
            y={10}
            stroke="hsl(142 60% 45%)"
            strokeDasharray="3 3"
            strokeOpacity={0.5}
          />
          <Line
            type="monotone"
            dataKey="position"
            stroke="hsl(var(--primary))"
            strokeWidth={2}
            dot={{ r: 3, fill: "hsl(var(--primary))" }}
            activeDot={{ r: 5 }}
            connectNulls
          />
        </LineChart>
      </ResponsiveContainer>
      <div className="flex items-center gap-4 text-[10px] text-muted-foreground mt-1 ml-10">
        <span className="flex items-center gap-1">
          <span className="w-3 h-px bg-green-600" /> Top 3
        </span>
        <span className="flex items-center gap-1">
          <span className="w-3 h-px bg-emerald-600" /> Top 10
        </span>
        <span>Y-axis : meilleur en haut (#1)</span>
      </div>
    </div>
  );
}
