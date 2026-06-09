import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { TooltipProvider } from "@/components/ui/tooltip";
import { HexTile, type HexTopic } from "./HexTile";

export type TopicalCluster = {
  theme: string;
  summary?: string;
  topics: HexTopic[];
};

type Props = {
  clusters: TopicalCluster[];
  onTopicClick?: (topic: HexTopic, clusterTheme: string) => void;
  hexSize?: number;
};

/**
 * Topical Map - clusters as cards, topics as hexagons.
 *
 * Layout: every odd-indexed row is offset by half a hex width to produce
 * the classic honeycomb tessellation. We do this with a per-row
 * marginLeft instead of CSS transforms so hit areas stay aligned.
 */
export function TopicalMap({ clusters, onTopicClick, hexSize = 92 }: Props) {
  // Tighter horizontal spacing - hexes nest at ~75% of their width
  const colStep = hexSize * 0.78;
  const rowStep = hexSize * 0.86;
  const rowOffset = colStep / 2;

  // Topics per row - keep grids compact and readable
  const perRow = 6;

  return (
    <TooltipProvider delayDuration={150}>
      <div className="space-y-6">
        {clusters.map((cluster, ci) => {
          const rows: HexTopic[][] = [];
          for (let i = 0; i < cluster.topics.length; i += perRow) {
            rows.push(cluster.topics.slice(i, i + perRow));
          }

          const coveredCount = cluster.topics.filter(
            (t) => t.status === "covered",
          ).length;
          const recommendedCount = cluster.topics.filter(
            (t) => t.status === "recommended",
          ).length;
          const missingCount = cluster.topics.filter(
            (t) => t.status === "missing",
          ).length;

          return (
            <Card key={ci} className="overflow-hidden">
              <CardHeader>
                <div className="flex items-start justify-between gap-3 flex-wrap">
                  <div>
                    <CardTitle className="text-lg">
                      <span className="text-xs font-mono text-muted-foreground mr-2">
                        #{ci + 1}
                      </span>
                      {cluster.theme}
                    </CardTitle>
                    {cluster.summary && (
                      <p className="text-sm text-muted-foreground mt-1">
                        {cluster.summary}
                      </p>
                    )}
                  </div>
                  <div className="flex gap-2 text-[11px] font-mono">
                    <span className="flex items-center gap-1 px-2 py-1 rounded bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
                      <span className="size-2 rounded-full bg-emerald-500" />
                      {coveredCount} couverts
                    </span>
                    {recommendedCount > 0 && (
                      <span className="flex items-center gap-1 px-2 py-1 rounded bg-amber-500/10 text-amber-600 dark:text-amber-400">
                        <span className="size-2 rounded-full bg-amber-500" />
                        {recommendedCount} suggeres
                      </span>
                    )}
                    {missingCount > 0 && (
                      <span className="flex items-center gap-1 px-2 py-1 rounded bg-zinc-500/10 text-zinc-600 dark:text-zinc-400">
                        <span className="size-2 rounded-full bg-zinc-500" />
                        {missingCount} manquants
                      </span>
                    )}
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                <div className="overflow-x-auto">
                  <div
                    className="inline-flex flex-col"
                    style={{ rowGap: 0 }}
                  >
                    {rows.map((row, ri) => (
                      <div
                        key={ri}
                        className="flex"
                        style={{
                          marginLeft: ri % 2 === 1 ? rowOffset : 0,
                          marginTop: ri === 0 ? 0 : -(hexSize - rowStep),
                        }}
                      >
                        {row.map((topic, ti) => (
                          <div
                            key={ti}
                            style={{
                              marginLeft: ti === 0 ? 0 : colStep - hexSize,
                            }}
                          >
                            <HexTile
                              topic={topic}
                              size={hexSize}
                              onClick={(t) =>
                                onTopicClick?.(t, cluster.theme)
                              }
                            />
                          </div>
                        ))}
                      </div>
                    ))}
                  </div>
                </div>
              </CardContent>
            </Card>
          );
        })}
      </div>
    </TooltipProvider>
  );
}
