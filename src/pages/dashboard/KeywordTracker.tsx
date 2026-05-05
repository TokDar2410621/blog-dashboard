import { useState } from "react";
import { useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
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

type Latest = {
  position: number | null;
  url: string;
  title: string;
  is_target_match: boolean;
  recorded_at: string;
} | null;

type Tracked = {
  id: number;
  keyword: string;
  language: string;
  target_url: string;
  is_active: boolean;
  created_at: string;
  latest: Latest;
};

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

export default function KeywordTracker() {
  const { t } = useTranslation();
  const { siteId } = useParams<{ siteId: string }>();
  const qc = useQueryClient();
  const [keyword, setKeyword] = useState("");
  const [language, setLanguage] = useState("fr");
  const [targetUrl, setTargetUrl] = useState("");
  const [expandedId, setExpandedId] = useState<number | null>(null);

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
        throw new Error(err.error || t("keywords.addError"));
      }
      return res.json();
    },
    onSuccess: () => {
      setKeyword("");
      setTargetUrl("");
      qc.invalidateQueries({ queryKey: ["tracked-keywords", siteId] });
      toast.success(t("keywords.added"));
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const remove = useMutation({
    mutationFn: async (id: number) => {
      const res = await authFetch(`/sites/${siteId}/keywords/${id}/`, {
        method: "DELETE",
      });
      if (!res.ok && res.status !== 204) {
        throw new Error(t("keywords.deleteError"));
      }
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tracked-keywords", siteId] });
      toast.success(t("keywords.deleted"));
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
        throw new Error(err.error || t("keywords.snapshotError"));
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
        t("keywords.snapshotDone", {
          processed: d.total_processed,
          ranked: d.snapshots_created - d.not_found_count,
        })
      );
    },
    onError: (err: Error) => toast.error(err.message),
  });

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

  return (
    <div className="space-y-6 max-w-5xl">
      <div>
        <h1 className="text-2xl font-bold">{t("keywords.title")}</h1>
        <p className="text-muted-foreground">{t("keywords.subtitle")}</p>
      </div>

      {/* Add form */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Plus className="h-5 w-5 text-primary" />
            {t("keywords.addTitle")}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-[1fr_auto_2fr_auto] gap-3 items-end">
            <div className="space-y-1">
              <label className="text-xs font-medium">{t("keywords.keyword")}</label>
              <Input
                value={keyword}
                onChange={(e) => setKeyword(e.target.value)}
                placeholder={t("keywords.keywordPlaceholder")}
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium">{t("keywords.language")}</label>
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
              <label className="text-xs font-medium">{t("keywords.targetUrl")}</label>
              <Input
                value={targetUrl}
                onChange={(e) => setTargetUrl(e.target.value)}
                placeholder={t("keywords.targetUrlPlaceholder")}
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
                  {t("keywords.add")}
                </>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Snapshot button */}
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          {list.data
            ? t("keywords.tracked", { count: list.data.length })
            : ""}
        </p>
        <Button
          onClick={() => snapshot.mutate()}
          disabled={snapshot.isPending || !list.data?.length}
          variant="outline"
        >
          {snapshot.isPending ? (
            <>
              <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              {t("keywords.snapshotting")}
            </>
          ) : (
            <>
              <RefreshCw className="h-4 w-4 mr-2" />
              {t("keywords.snapshotNow")}
            </>
          )}
        </Button>
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
              <p>{t("keywords.empty")}</p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("keywords.keyword")}</TableHead>
                  <TableHead className="w-16">{t("keywords.language")}</TableHead>
                  <TableHead className="w-24 text-center">{t("keywords.position")}</TableHead>
                  <TableHead>{t("keywords.lastSnapshot")}</TableHead>
                  <TableHead className="w-20"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {list.data.map((k) => {
                  const isExpanded = expandedId === k.id;
                  return (
                    <>
                      <TableRow
                        key={k.id}
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
                        <TableCell>
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground font-mono uppercase">
                            {k.language}
                          </span>
                        </TableCell>
                        <TableCell className="text-center">
                          {k.latest ? (
                            k.latest.position !== null ? (
                              <span
                                className={`text-xl font-bold ${
                                  k.latest.position <= 3
                                    ? "text-green-600"
                                    : k.latest.position <= 10
                                    ? "text-emerald-600"
                                    : k.latest.position <= 30
                                    ? "text-amber-600"
                                    : "text-muted-foreground"
                                }`}
                              >
                                #{k.latest.position}
                              </span>
                            ) : (
                              <span className="text-xs text-muted-foreground">
                                {t("keywords.notRanked")}
                              </span>
                            )
                          ) : (
                            <span className="text-xs text-muted-foreground">-</span>
                          )}
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground">
                          {k.latest
                            ? new Date(k.latest.recorded_at).toLocaleString("fr-CA")
                            : t("keywords.never")}
                        </TableCell>
                        <TableCell>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={(e) => {
                              e.stopPropagation();
                              if (
                                confirm(t("keywords.confirmDelete", { keyword: k.keyword }))
                              ) {
                                remove.mutate(k.id);
                              }
                            }}
                          >
                            <Trash2 className="h-4 w-4 text-muted-foreground hover:text-destructive" />
                          </Button>
                        </TableCell>
                      </TableRow>
                      {isExpanded && (
                        <TableRow key={`${k.id}-history`}>
                          <TableCell colSpan={5} className="bg-muted/30">
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
                                          {t("keywords.previousMedian")}: #
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
                                    {t("keywords.history90")} ({history.data.snapshots.length})
                                  </h4>
                                  {history.data.snapshots.length === 0 ? (
                                    <p className="text-xs text-muted-foreground">
                                      {t("keywords.noSnapshots")}
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
                    </>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
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
    <div className="w-full h-56 -ml-2">
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
