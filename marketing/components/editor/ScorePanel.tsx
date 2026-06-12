"use client";

import { useMemo } from "react";
import { ContentScoreGauge } from "./ContentScoreGauge";
import { TermUsageTracker, type TermUsage } from "./TermUsageTracker";
import {
  TermMapHeatmap,
  type TermMapTermRow,
  type TermMapUrlCol,
} from "./TermMapHeatmap";
import { seededRandom } from "./heatmapColor";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import {
  computeCompositeScore,
  type SubScores,
  type ScoreInputs,
} from "./contentScore";

interface SubScoreRowProps {
  label: string;
  value: number;
}

function SubScoreRow({ label, value }: SubScoreRowProps) {
  const v = Math.max(0, Math.min(100, Math.round(value)));
  const color =
    v >= 80
      ? "bg-emerald-500"
      : v >= 60
        ? "bg-cyan-500"
        : v >= 40
          ? "bg-amber-500"
          : "bg-rose-500";
  return (
    <div className="space-y-1">
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-xs text-muted-foreground">{label}</span>
        <span className="text-xs tabular-nums font-medium">{v}</span>
      </div>
      <div className="h-1.5 w-full rounded-full bg-muted overflow-hidden">
        <div
          className={`h-full ${color} transition-all duration-500 ease-out`}
          style={{ width: `${v}%` }}
        />
      </div>
    </div>
  );
}

export interface ScorePanelProps extends ScoreInputs {
  terms: TermUsage[];
  trend?: number[];
  onTermClick?: (term: string) => void;
  activeTerm?: string | null;
  /** When provided, used instead of recomputing - lets the parent debounce. */
  precomputed?: { total: number; sub: SubScores };
  /**
   * Optional pre-computed Term Map. When omitted, the panel mocks data
   * client-side from `terms`. V2: populated by `gridar_serp_analyze`.
   */
  termMap?: {
    terms: TermMapTermRow[];
    urls: TermMapUrlCol[];
  };
  termMapLoading?: boolean;
}

/**
 * Build a deterministic mock Term Map from the existing TermUsage list.
 *
 * TODO(v2): replace this with the response from `gridar_serp_analyze`, which
 * returns the real top 10 SERP URLs and their per-term frequencies. The
 * "Toi" column comes from `TermUsage.current`.
 */
function buildMockTermMap(terms: TermUsage[]): {
  terms: TermMapTermRow[];
  urls: TermMapUrlCol[];
} {
  // 10 fake URL labels - kept short so they fit in the column headers.
  const FAKE_URLS = [
    "wikipedia",
    "moz.com",
    "ahrefs",
    "semrush",
    "hubspot",
    "neilpatel",
    "backlinko",
    "search-engine-journal",
    "yoast",
    "contentking",
  ];

  const urls: TermMapUrlCol[] = [
    { label: "Toi", url: "Ton article actuel" },
    ...FAKE_URLS.map((label) => ({ label, url: `https://${label}.com` })),
  ];

  const sorted = [...terms]
    .sort((a, b) => b.importance - a.importance)
    .slice(0, 30);

  const rows: TermMapTermRow[] = sorted.map((u) => {
    const rng = seededRandom(u.term);
    const frequency_per_url: Record<string, number> = {
      Toi: u.current,
    };
    // Generate a plausible distribution around the target range. Higher
    // importance terms get higher frequencies across competing URLs.
    const targetMid = (u.target[0] + u.target[1]) / 2;
    for (const label of FAKE_URLS) {
      // Bias the distribution: most URLs land near targetMid, with some
      // extremes. importance scales the spread.
      const base = targetMid * (0.4 + rng() * 1.4);
      const jitter = rng() * targetMid * 0.6;
      const v = Math.max(0, Math.round(base + jitter - targetMid * 0.3));
      frequency_per_url[label] = v;
    }
    return { term: u.term, frequency_per_url };
  });

  return { terms: rows, urls };
}

/**
 * Sticky right rail score panel: gauge + sub-scores + tabbed term tracker
 * (list view + Clearscope-style heatmap).
 * Designed to live inside a ResizablePanel so the parent controls width.
 */
export function ScorePanel(props: ScorePanelProps) {
  const composite = useMemo(() => {
    if (props.precomputed) return props.precomputed;
    return computeCompositeScore({
      title: props.title,
      excerpt: props.excerpt,
      content: props.content,
      slug: props.slug,
      coverImage: props.coverImage,
      keyword: props.keyword,
      secondaryKeywords: props.secondaryKeywords,
      language: props.language,
    });
  }, [
    props.precomputed,
    props.title,
    props.excerpt,
    props.content,
    props.slug,
    props.coverImage,
    props.keyword,
    props.secondaryKeywords,
    props.language,
  ]);

  // V1: mock the term map client-side. V2 will pass `termMap` from a real
  // backend call (gridar_serp_analyze) and skip this fallback entirely.
  const termMap = useMemo(() => {
    if (props.termMap) return props.termMap;
    return buildMockTermMap(props.terms);
  }, [props.termMap, props.terms]);

  return (
    <div className="h-full overflow-y-auto p-4">
      <div className="space-y-6">
        {/* Gauge */}
        <div className="flex justify-center pt-2">
          <ContentScoreGauge
            score={composite.total}
            trend={props.trend}
            label="Content Score"
          />
        </div>

        {/* Sub-scores */}
        <div className="space-y-3 rounded-lg border bg-card p-3">
          <h3 className="text-xs font-mono uppercase tracking-wider text-muted-foreground">
            Sous-scores
          </h3>
          <div className="space-y-2.5">
            <SubScoreRow label="Mots-cles" value={composite.sub.keywords} />
            <SubScoreRow label="Structure" value={composite.sub.structure} />
            <SubScoreRow label="Lisibilite" value={composite.sub.readability} />
            <SubScoreRow label="OQLF (FR-CA)" value={composite.sub.oqlf} />
            <SubScoreRow label="E-E-A-T" value={composite.sub.eeat} />
            <SubScoreRow label="Originalite" value={composite.sub.originality} />
          </div>
        </div>

        {/* Tabs: list (Termes) + heatmap (Term Map) */}
        <Tabs defaultValue="termes" className="rounded-lg border bg-card p-3">
          <TabsList className="w-full">
            <TabsTrigger value="termes">Termes</TabsTrigger>
            <TabsTrigger value="termmap">Term Map</TabsTrigger>
          </TabsList>
          <TabsContent value="termes" className="pt-3">
            <TermUsageTracker
              terms={props.terms}
              onTermClick={props.onTermClick}
              activeTerm={props.activeTerm}
            />
          </TabsContent>
          <TabsContent value="termmap" className="pt-3">
            <TermMapHeatmap
              terms={termMap.terms}
              urls={termMap.urls}
              loading={props.termMapLoading}
              onTermClick={props.onTermClick}
              activeTerm={props.activeTerm}
            />
          </TabsContent>
        </Tabs>

        <p className="text-[10px] leading-relaxed text-muted-foreground italic px-1">
          Calcul cote client (V1). Le score serveur dans l onglet SEO peut
          differer legerement. Brief recommended_terms supporte des qu il est
          disponible.
        </p>
      </div>
    </div>
  );
}
