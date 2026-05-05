import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useMutation } from "@tanstack/react-query";
import { authFetch } from "@/lib/api-client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  TrendingUp,
  Loader2,
  AlertTriangle,
  CheckCircle2,
  ArrowRight,
} from "lucide-react";
import { toast } from "sonner";

type Distribution = {
  excellent: number;
  good: number;
  average: number;
  poor: number;
};

type AggregateItem = { text: string; count: number };

type WeakArticle = {
  slug: string;
  title: string;
  language: string | null;
  score: number;
  verdict: string;
};

type BulkResult = {
  site_id: number;
  audited_count: number;
  failed_count: number;
  cache_hits: number;
  mean_score: number | null;
  distribution: Distribution;
  top_weaknesses: AggregateItem[];
  top_actions: AggregateItem[];
  weakest_articles: WeakArticle[];
};

export default function BulkAudit() {
  const { t } = useTranslation();
  const { siteId } = useParams<{ siteId: string }>();
  const [limit, setLimit] = useState("50");
  const [data, setData] = useState<BulkResult | null>(null);
  const base = `/dashboard/${siteId}`;

  const mutation = useMutation({
    mutationFn: async () => {
      const res = await authFetch(
        `/sites/${siteId}/audit-all/?limit=${limit}`,
        { method: "GET" }
      );
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error || t("bulkAudit.error"));
      }
      return (await res.json()) as BulkResult;
    },
    onSuccess: (d) => setData(d),
    onError: (err: Error) => toast.error(err.message),
  });

  const total = data
    ? data.distribution.excellent +
      data.distribution.good +
      data.distribution.average +
      data.distribution.poor
    : 0;

  const pct = (n: number) => (total > 0 ? Math.round((n / total) * 100) : 0);

  return (
    <div className="space-y-6 max-w-5xl">
      <div>
        <h1 className="text-2xl font-bold">{t("bulkAudit.title")}</h1>
        <p className="text-muted-foreground">{t("bulkAudit.subtitle")}</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <TrendingUp className="h-5 w-5 text-primary" />
            {t("bulkAudit.runTitle")}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-end gap-3">
            <div className="space-y-2">
              <label className="text-sm font-medium">{t("bulkAudit.limit")}</label>
              <Select value={limit} onValueChange={setLimit}>
                <SelectTrigger className="w-32">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="10">10</SelectItem>
                  <SelectItem value="25">25</SelectItem>
                  <SelectItem value="50">50</SelectItem>
                  <SelectItem value="100">100</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <Button
              onClick={() => mutation.mutate()}
              disabled={mutation.isPending}
              size="lg"
            >
              {mutation.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  {t("bulkAudit.running")}
                </>
              ) : (
                <>
                  <TrendingUp className="h-4 w-4 mr-2" />
                  {t("bulkAudit.run")}
                </>
              )}
            </Button>
          </div>
          {mutation.isPending && (
            <p className="text-xs text-muted-foreground">{t("bulkAudit.runWait")}</p>
          )}
        </CardContent>
      </Card>

      {mutation.isPending && (
        <div className="space-y-3">
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-48 w-full" />
        </div>
      )}

      {data && !mutation.isPending && (
        <>
          {/* KPIs */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Card>
              <CardContent className="pt-6">
                <div className="text-3xl font-bold">{data.audited_count}</div>
                <div className="text-xs text-muted-foreground mt-1">
                  {t("bulkAudit.audited")}
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-3xl font-bold">
                  {data.mean_score ?? "-"}
                </div>
                <div className="text-xs text-muted-foreground mt-1">
                  {t("bulkAudit.meanScore")}
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-3xl font-bold text-green-600">
                  {data.distribution.excellent + data.distribution.good}
                </div>
                <div className="text-xs text-muted-foreground mt-1">
                  {t("bulkAudit.healthy")}
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-3xl font-bold text-amber-600">
                  {data.distribution.poor}
                </div>
                <div className="text-xs text-muted-foreground mt-1">
                  {t("bulkAudit.poor")}
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Distribution bar */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">{t("bulkAudit.distribution")}</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex h-8 w-full rounded overflow-hidden">
                {data.distribution.excellent > 0 && (
                  <div
                    className="bg-green-500 flex items-center justify-center text-white text-xs font-medium"
                    style={{ width: `${pct(data.distribution.excellent)}%` }}
                    title={`${t("bulkAudit.excellent")}: ${data.distribution.excellent}`}
                  >
                    {pct(data.distribution.excellent) > 8 &&
                      `${data.distribution.excellent}`}
                  </div>
                )}
                {data.distribution.good > 0 && (
                  <div
                    className="bg-emerald-500 flex items-center justify-center text-white text-xs font-medium"
                    style={{ width: `${pct(data.distribution.good)}%` }}
                    title={`${t("bulkAudit.good")}: ${data.distribution.good}`}
                  >
                    {pct(data.distribution.good) > 8 && `${data.distribution.good}`}
                  </div>
                )}
                {data.distribution.average > 0 && (
                  <div
                    className="bg-amber-500 flex items-center justify-center text-white text-xs font-medium"
                    style={{ width: `${pct(data.distribution.average)}%` }}
                    title={`${t("bulkAudit.average")}: ${data.distribution.average}`}
                  >
                    {pct(data.distribution.average) > 8 &&
                      `${data.distribution.average}`}
                  </div>
                )}
                {data.distribution.poor > 0 && (
                  <div
                    className="bg-red-500 flex items-center justify-center text-white text-xs font-medium"
                    style={{ width: `${pct(data.distribution.poor)}%` }}
                    title={`${t("bulkAudit.poor")}: ${data.distribution.poor}`}
                  >
                    {pct(data.distribution.poor) > 8 && `${data.distribution.poor}`}
                  </div>
                )}
              </div>
              <div className="flex flex-wrap gap-3 text-xs mt-3 text-muted-foreground">
                <span className="flex items-center gap-1">
                  <span className="w-3 h-3 rounded bg-green-500" />
                  {t("bulkAudit.excellent")} (≥85)
                </span>
                <span className="flex items-center gap-1">
                  <span className="w-3 h-3 rounded bg-emerald-500" />
                  {t("bulkAudit.good")} (70-84)
                </span>
                <span className="flex items-center gap-1">
                  <span className="w-3 h-3 rounded bg-amber-500" />
                  {t("bulkAudit.average")} (50-69)
                </span>
                <span className="flex items-center gap-1">
                  <span className="w-3 h-3 rounded bg-red-500" />
                  {t("bulkAudit.poor")} (&lt;50)
                </span>
              </div>
              {data.cache_hits > 0 && (
                <p className="text-xs text-muted-foreground mt-3">
                  {t("bulkAudit.cacheHits", { count: data.cache_hits })}
                </p>
              )}
            </CardContent>
          </Card>

          {/* Two-column: top issues + weakest articles */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <AlertTriangle className="h-4 w-4 text-amber-600" />
                  {t("bulkAudit.topWeaknesses")}
                </CardTitle>
              </CardHeader>
              <CardContent>
                {data.top_weaknesses.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    {t("bulkAudit.noWeaknesses")}
                  </p>
                ) : (
                  <ul className="space-y-2">
                    {data.top_weaknesses.map((w, i) => (
                      <li
                        key={i}
                        className="flex items-start gap-2 text-sm border-b pb-2 last:border-0"
                      >
                        <span className="text-xs font-mono px-2 py-0.5 rounded bg-amber-500/10 text-amber-700 dark:text-amber-400 shrink-0">
                          ×{w.count}
                        </span>
                        <span>{w.text}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <CheckCircle2 className="h-4 w-4 text-green-600" />
                  {t("bulkAudit.topActions")}
                </CardTitle>
              </CardHeader>
              <CardContent>
                {data.top_actions.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    {t("bulkAudit.noActions")}
                  </p>
                ) : (
                  <ul className="space-y-2">
                    {data.top_actions.map((a, i) => (
                      <li
                        key={i}
                        className="flex items-start gap-2 text-sm border-b pb-2 last:border-0"
                      >
                        <span className="text-xs font-mono px-2 py-0.5 rounded bg-green-500/10 text-green-700 dark:text-green-400 shrink-0">
                          ×{a.count}
                        </span>
                        <span>{a.text}</span>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Weakest articles */}
          {data.weakest_articles.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base">
                  {t("bulkAudit.weakestArticles")}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  {data.weakest_articles.map((a) => (
                    <Link
                      key={a.slug}
                      to={`${base}/articles/${a.slug}`}
                      className="flex items-center justify-between gap-2 border rounded p-3 hover:border-primary group"
                    >
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium truncate">
                            {a.title}
                          </span>
                          {a.language && (
                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground font-mono uppercase shrink-0">
                              {a.language}
                            </span>
                          )}
                        </div>
                        {a.verdict && (
                          <p className="text-xs text-muted-foreground mt-1 truncate">
                            {a.verdict}
                          </p>
                        )}
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <span
                          className={`text-2xl font-bold ${
                            a.score >= 70
                              ? "text-green-600"
                              : a.score >= 50
                              ? "text-amber-600"
                              : "text-red-600"
                          }`}
                        >
                          {a.score}
                        </span>
                        <ArrowRight className="h-4 w-4 text-muted-foreground group-hover:text-primary" />
                      </div>
                    </Link>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
