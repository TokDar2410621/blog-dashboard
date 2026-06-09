import { useMemo } from "react";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { Skeleton } from "@/components/ui/skeleton";
import { heatmapColor } from "./heatmapColor";

export interface TermMapTermRow {
  /** Term being tracked. */
  term: string;
  /** Map of url label -> occurrences in that competing URL. */
  frequency_per_url: Record<string, number>;
}

export interface TermMapUrlCol {
  /** Short label shown in the column header (e.g. domain). */
  label: string;
  /** Occurrences of all tracked terms in this URL (for reference). */
  current_count?: number;
  /** Optional full url, used for the tooltip. */
  url?: string;
}

export interface TermMapHeatmapProps {
  terms: TermMapTermRow[];
  /** First entry should be "Toi" (the current article). */
  urls: TermMapUrlCol[];
  loading?: boolean;
  /** Click a row to highlight that term in the markdown editor. */
  onTermClick?: (term: string) => void;
  activeTerm?: string | null;
}

/**
 * Clearscope-style Term Map: rows = recommended terms, columns = top SERP
 * URLs, cells = term frequency. The first column ("Toi") represents the
 * current draft and is highlighted with an emerald border.
 *
 * V1: data is mocked client-side from termSeeds in ScorePanel.
 * V2: backend will populate this from `gridar_serp_analyze`.
 */
export function TermMapHeatmap({
  terms,
  urls,
  loading = false,
  onTermClick,
  activeTerm,
}: TermMapHeatmapProps) {
  // Find the max occurrence value across the whole grid so the heatmap
  // gradient is normalized.
  const max = useMemo(() => {
    let m = 1;
    for (const row of terms) {
      for (const u of urls) {
        const v = row.frequency_per_url[u.label] ?? 0;
        if (v > m) m = v;
      }
    }
    return m;
  }, [terms, urls]);

  if (loading) {
    return (
      <div className="space-y-2 p-2">
        {Array.from({ length: 8 }).map((_, i) => (
          <Skeleton key={i} className="h-6 w-full" />
        ))}
      </div>
    );
  }

  if (terms.length === 0 || urls.length === 0) {
    return (
      <div className="text-xs text-muted-foreground italic px-2 py-3">
        Aucune donnee Term Map disponible. Ajoute des tags ou lance un brief
        pour activer la heatmap.
      </div>
    );
  }

  // CSS grid template: 1 column for the term label, 1 narrow column per url.
  const gridTemplateColumns = `minmax(7rem, 1fr) repeat(${urls.length}, minmax(1.75rem, 1fr))`;

  return (
    <TooltipProvider delayDuration={120}>
      <div className="space-y-2">
        <div className="flex items-center justify-between px-1">
          <h3 className="text-xs font-mono uppercase tracking-wider text-muted-foreground">
            Term Map
          </h3>
          <span className="text-[10px] tabular-nums text-muted-foreground">
            {terms.length} termes x {urls.length} URLs
          </span>
        </div>

        <div className="overflow-x-auto rounded-md border bg-card">
          {/* Header row */}
          <div
            className="grid items-end gap-px border-b bg-muted/40 px-1 py-1.5 text-[10px]"
            style={{ gridTemplateColumns }}
          >
            <div className="px-1 font-mono uppercase tracking-wider text-muted-foreground">
              Terme
            </div>
            {urls.map((u, idx) => (
              <div
                key={u.label}
                className={`flex justify-center font-mono uppercase tabular-nums text-muted-foreground ${
                  idx === 0 ? "text-emerald-500 font-semibold" : ""
                }`}
                title={u.url ?? u.label}
              >
                <span className="truncate max-w-[3rem]">{u.label}</span>
              </div>
            ))}
          </div>

          {/* Body rows */}
          <div className="divide-y">
            {terms.map((row) => {
              const isActive = activeTerm === row.term;
              return (
                <div
                  key={row.term}
                  className={`grid items-stretch gap-px px-1 py-px transition-colors hover:bg-accent/40 ${
                    isActive ? "bg-accent/60" : ""
                  }`}
                  style={{ gridTemplateColumns }}
                >
                  <button
                    type="button"
                    onClick={() => onTermClick?.(row.term)}
                    className="flex items-center px-1 py-1 text-left text-xs font-medium truncate hover:text-emerald-500"
                    title={`Surligner "${row.term}" dans l editeur`}
                  >
                    {row.term}
                  </button>
                  {urls.map((u, idx) => {
                    const value = row.frequency_per_url[u.label] ?? 0;
                    const cellClass = heatmapColor(value, max);
                    const isYou = idx === 0;
                    return (
                      <Tooltip key={u.label}>
                        <TooltipTrigger asChild>
                          <div
                            className={`flex items-center justify-center text-[10px] tabular-nums font-medium rounded-sm ${cellClass} ${
                              isYou
                                ? "ring-1 ring-emerald-500/70 ring-inset"
                                : ""
                            }`}
                            style={{ minHeight: "1.5rem" }}
                          >
                            {value > 0 ? value : ""}
                          </div>
                        </TooltipTrigger>
                        <TooltipContent side="top">
                          <span className="font-mono text-[11px]">
                            {row.term} apparait {value} fois dans {u.label}
                          </span>
                        </TooltipContent>
                      </Tooltip>
                    );
                  })}
                </div>
              );
            })}
          </div>
        </div>

        <p className="text-[10px] leading-relaxed text-muted-foreground italic px-1">
          Colonne "Toi" = ton article actuel. Plus c est emerald, plus le terme
          est utilise par cette URL du top 10.
        </p>
      </div>
    </TooltipProvider>
  );
}
