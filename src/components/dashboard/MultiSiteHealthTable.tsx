import { useMemo } from "react";
import { Link } from "react-router-dom";
import { useQueries } from "@tanstack/react-query";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { authFetch } from "@/lib/api-client";
import type { Site } from "@/lib/schemas";
import { Globe, LogIn, AlertTriangle, TrendingDown, Sparkles } from "lucide-react";

export interface MultiSiteHealthTableProps {
  sites: Site[];
  isLoading?: boolean;
}

type SeoScoreResponse = {
  score: number;
  breakdown?: Record<string, unknown>;
  action_items?: Array<Record<string, unknown>>;
};

type DecayResponse = {
  declining?: Array<Record<string, unknown>>;
  count?: number;
};

/**
 * Deterministic pseudo-random number in [0, 1) seeded by `seed`.
 * Used for V1 mocks (AI visibility, organic traffic, alerts) so the row
 * does not jitter between renders. Replace with real API once shipped.
 */
function mulberry32(seed: number): number {
  let s = (seed * 1000 + 1) >>> 0;
  s = (s + 0x6d2b79f5) >>> 0;
  let t = s;
  t = Math.imul(t ^ (t >>> 15), t | 1);
  t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
  return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
}

function scoreColorClasses(score: number | null | undefined): string {
  if (score === null || score === undefined) return "text-muted-foreground";
  if (score >= 70) return "text-emerald-500";
  if (score >= 40) return "text-amber-500";
  return "text-destructive";
}

function scoreBadgeClasses(score: number | null | undefined): string {
  if (score === null || score === undefined) {
    return "bg-muted/40 text-muted-foreground border-border/50";
  }
  if (score >= 70) {
    return "bg-emerald-500/10 text-emerald-400 border-emerald-500/30";
  }
  if (score >= 40) {
    return "bg-amber-500/10 text-amber-400 border-amber-500/30";
  }
  return "bg-destructive/10 text-destructive border-destructive/30";
}

function formatNumber(n: number): string {
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return String(Math.round(n));
}

function ScoreCell({ score }: { score: number | null | undefined }) {
  return (
    <span
      className={cn(
        "inline-flex items-center justify-center rounded-md border px-2 py-1 text-sm font-mono tabular-nums font-semibold min-w-[3.25rem]",
        scoreBadgeClasses(score),
      )}
    >
      {score === null || score === undefined ? "-" : Math.round(score)}
    </span>
  );
}

export function MultiSiteHealthTable({
  sites,
  isLoading = false,
}: MultiSiteHealthTableProps) {
  // Fetch SEO score for each site in parallel. Returns { score, breakdown, action_items }.
  const seoQueries = useQueries({
    queries: sites.map((site) => ({
      queryKey: ["site-seo-score", site.id],
      queryFn: async (): Promise<SeoScoreResponse> => {
        const res = await authFetch(`/sites/${site.id}/seo-score/`);
        if (!res.ok) throw new Error(`seo-score ${res.status}`);
        return res.json();
      },
      staleTime: 1000 * 60 * 5,
      retry: 0,
    })),
  });

  // Fetch decay count (number of declining posts over 30 days). Endpoint already shipped.
  const decayQueries = useQueries({
    queries: sites.map((site) => ({
      queryKey: ["site-content-decay", site.id, 30],
      queryFn: async (): Promise<DecayResponse> => {
        const res = await authFetch(`/sites/${site.id}/content-decay/?days=30`);
        if (!res.ok) throw new Error(`decay ${res.status}`);
        return res.json();
      },
      staleTime: 1000 * 60 * 10,
      retry: 0,
    })),
  });

  const rows = useMemo(() => {
    return sites.map((site, idx) => {
      const seo = seoQueries[idx];
      const decay = decayQueries[idx];
      const seoScore = seo?.data?.score ?? null;
      const seoLoading = !!seo?.isLoading;
      const declining = decay?.data?.declining;
      const decayCount = Array.isArray(declining)
        ? declining.length
        : (decay?.data?.count ?? 0);
      const decayLoading = !!decay?.isLoading;

      // V1 mocks - clearly labeled with "NEW" / mock badges in the cells.
      const aiVisibility = Math.round(mulberry32(site.id) * 100);
      const organicTraffic = Math.round(mulberry32(site.id + 7) * 12000);
      const alertsCount = Math.round(mulberry32(site.id + 13) * 5);

      return {
        site,
        seoScore,
        seoLoading,
        decayCount,
        decayLoading,
        aiVisibility,
        organicTraffic,
        alertsCount,
      };
    });
  }, [sites, seoQueries, decayQueries]);

  return (
    <div className="rounded-lg border border-border/50 bg-card overflow-hidden">
      <Table>
        <TableHeader>
          <TableRow className="bg-muted/30 hover:bg-muted/30">
            <TableHead className="font-medium">Site</TableHead>
            <TableHead className="font-medium">SEO Score</TableHead>
            <TableHead className="font-medium">AI Visibility</TableHead>
            <TableHead className="font-medium">Trafic organique</TableHead>
            <TableHead className="font-medium">Decay</TableHead>
            <TableHead className="font-medium">Alertes</TableHead>
            <TableHead className="font-medium text-right">Action</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {isLoading
            ? Array.from({ length: 3 }).map((_, i) => (
                <TableRow key={`skeleton-${i}`}>
                  <TableCell>
                    <div className="flex items-center gap-3">
                      <Skeleton className="h-8 w-8 rounded-full" />
                      <div className="space-y-1">
                        <Skeleton className="h-4 w-32" />
                        <Skeleton className="h-3 w-24" />
                      </div>
                    </div>
                  </TableCell>
                  <TableCell><Skeleton className="h-7 w-14" /></TableCell>
                  <TableCell><Skeleton className="h-7 w-14" /></TableCell>
                  <TableCell><Skeleton className="h-4 w-16" /></TableCell>
                  <TableCell><Skeleton className="h-4 w-10" /></TableCell>
                  <TableCell><Skeleton className="h-4 w-10" /></TableCell>
                  <TableCell className="text-right">
                    <Skeleton className="h-8 w-20 ml-auto" />
                  </TableCell>
                </TableRow>
              ))
            : rows.map(
                ({
                  site,
                  seoScore,
                  seoLoading,
                  decayCount,
                  decayLoading,
                  aiVisibility,
                  organicTraffic,
                  alertsCount,
                }) => (
                  <TableRow key={site.id}>
                    <TableCell>
                      <div className="flex items-center gap-3 min-w-0">
                        <div className="h-8 w-8 rounded-full bg-primary/10 border border-primary/20 flex items-center justify-center shrink-0">
                          <Globe className="h-4 w-4 text-primary" />
                        </div>
                        <div className="min-w-0">
                          <p className="font-medium truncate">{site.name}</p>
                          <p className="text-xs text-muted-foreground truncate">
                            {site.domain || "-"}
                          </p>
                        </div>
                      </div>
                    </TableCell>
                    <TableCell>
                      {seoLoading ? (
                        <Skeleton className="h-7 w-14" />
                      ) : (
                        <ScoreCell score={seoScore} />
                      )}
                    </TableCell>
                    <TableCell>
                      <div className="flex items-center gap-2">
                        <ScoreCell score={aiVisibility} />
                        <Badge
                          variant="outline"
                          className="border-primary/40 text-primary text-[10px] font-mono uppercase tracking-wider px-1.5 py-0"
                        >
                          <Sparkles className="h-2.5 w-2.5 mr-0.5" />
                          New
                        </Badge>
                      </div>
                    </TableCell>
                    <TableCell>
                      <span className="text-sm font-mono tabular-nums">
                        {formatNumber(organicTraffic)}
                      </span>
                      <span className="text-xs text-muted-foreground ml-1">
                        / mo
                      </span>
                    </TableCell>
                    <TableCell>
                      {decayLoading ? (
                        <Skeleton className="h-4 w-10" />
                      ) : (
                        <span
                          className={cn(
                            "inline-flex items-center gap-1 text-sm font-mono tabular-nums",
                            decayCount > 0
                              ? "text-amber-500"
                              : "text-muted-foreground",
                          )}
                        >
                          <TrendingDown className="h-3.5 w-3.5" />
                          {decayCount}
                        </span>
                      )}
                    </TableCell>
                    <TableCell>
                      <span
                        className={cn(
                          "inline-flex items-center gap-1 text-sm font-mono tabular-nums",
                          alertsCount > 0
                            ? "text-destructive"
                            : "text-muted-foreground",
                        )}
                      >
                        <AlertTriangle className="h-3.5 w-3.5" />
                        {alertsCount}
                      </span>
                    </TableCell>
                    <TableCell className="text-right">
                      <Button asChild size="sm" variant="outline">
                        <Link to={`/dashboard/${site.id}`}>
                          <LogIn className="h-3.5 w-3.5 mr-1.5" />
                          Ouvrir
                        </Link>
                      </Button>
                    </TableCell>
                  </TableRow>
                ),
              )}
        </TableBody>
      </Table>
    </div>
  );
}

export default MultiSiteHealthTable;
