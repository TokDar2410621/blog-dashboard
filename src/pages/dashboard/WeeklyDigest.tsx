import { useParams, Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { authFetch } from "@/lib/api-client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  FileText,
  Eye,
  TrendingUp,
  TrendingDown,
  Printer,
  Move,
  ArrowDown,
  ArrowUp,
  Calendar,
} from "lucide-react";

type Mover = {
  keyword: string;
  language: string;
  old_position: number | null;
  new_position: number | null;
  delta: number;
};

type DigestArticle = {
  slug: string;
  title: string;
  language?: string;
  view_count: number;
  published_at?: string;
};

type Digest = {
  site: { id: number; name: string; domain: string };
  period: {
    start: string;
    end: string;
    previous_start: string;
    previous_end: string;
  };
  totals: {
    total_published: number;
    published_this_week: number;
    recent_redirects: number;
    active_redirects: number;
    tracked_keywords: number;
  };
  published_this_week: DigestArticle[];
  top_views: { slug: string; title: string; view_count: number }[];
  top_movers: Mover[];
  worst_movers: Mover[];
  generated_at: string;
};

function formatPos(p: number | null) {
  return p === null ? "100+" : `#${p}`;
}

export default function WeeklyDigest() {
  const { t, i18n } = useTranslation();
  const { siteId } = useParams<{ siteId: string }>();
  const base = `/dashboard/${siteId}`;

  const { data, isLoading } = useQuery<Digest>({
    queryKey: ["weekly-digest", siteId],
    queryFn: async () => {
      const res = await authFetch(`/sites/${siteId}/weekly-digest/`);
      if (!res.ok) throw new Error("digest failed");
      return res.json();
    },
    staleTime: 30 * 60 * 1000, // 30 min
  });

  const fmtDate = (iso: string) =>
    new Date(iso).toLocaleDateString(i18n.language === "fr" ? "fr-CA" : "en-CA", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });

  return (
    <div className="space-y-6 max-w-4xl print:max-w-none print:p-8">
      <div className="flex items-center justify-between print:hidden">
        <div>
          <h1 className="text-2xl font-bold">{t("digest.title")}</h1>
          <p className="text-muted-foreground">{t("digest.subtitle")}</p>
        </div>
        <Button onClick={() => window.print()} variant="outline">
          <Printer className="h-4 w-4 mr-2" />
          {t("digest.print")}
        </Button>
      </div>

      {isLoading && <Skeleton className="h-96 w-full" />}

      {data && (
        <>
          {/* Header for print */}
          <div className="hidden print:block mb-6">
            <h1 className="text-3xl font-bold">{data.site.name}</h1>
            <p className="text-sm text-gray-600">{data.site.domain}</p>
            <p className="text-sm text-gray-600">
              {t("digest.report")}: {fmtDate(data.period.start)} -{" "}
              {fmtDate(data.period.end)}
            </p>
          </div>

          {/* Period card */}
          <Card>
            <CardContent className="py-4">
              <div className="flex items-center gap-2 text-sm">
                <Calendar className="h-4 w-4 text-muted-foreground" />
                <span className="font-medium">{t("digest.period")}</span>
                <span className="text-muted-foreground">
                  {fmtDate(data.period.start)} → {fmtDate(data.period.end)}
                </span>
              </div>
            </CardContent>
          </Card>

          {/* KPI cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Card>
              <CardContent className="pt-6">
                <div className="text-3xl font-bold">
                  {data.totals.published_this_week}
                </div>
                <div className="text-xs text-muted-foreground mt-1 flex items-center gap-1">
                  <FileText className="h-3 w-3" />
                  {t("digest.publishedThisWeek")}
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-3xl font-bold">{data.totals.total_published}</div>
                <div className="text-xs text-muted-foreground mt-1">
                  {t("digest.totalPublished")}
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-3xl font-bold">{data.totals.tracked_keywords}</div>
                <div className="text-xs text-muted-foreground mt-1 flex items-center gap-1">
                  <TrendingUp className="h-3 w-3" />
                  {t("digest.trackedKeywords")}
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-3xl font-bold">{data.totals.recent_redirects}</div>
                <div className="text-xs text-muted-foreground mt-1 flex items-center gap-1">
                  <Move className="h-3 w-3" />
                  {t("digest.recentRedirects")}
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Published this week */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <FileText className="h-5 w-5 text-primary" />
                {t("digest.publishedListTitle")}
              </CardTitle>
            </CardHeader>
            <CardContent>
              {data.published_this_week.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  {t("digest.nothingPublished")}
                </p>
              ) : (
                <ul className="space-y-2">
                  {data.published_this_week.map((p) => (
                    <li
                      key={p.slug}
                      className="flex items-center justify-between gap-2 border-b last:border-0 pb-2 last:pb-0"
                    >
                      <div className="flex items-center gap-2 flex-1 min-w-0">
                        <Link
                          to={`${base}/articles/${p.slug}`}
                          className="hover:text-primary truncate"
                        >
                          {p.title}
                        </Link>
                        {p.language && (
                          <span className="text-[10px] px-1 rounded bg-muted text-muted-foreground font-mono uppercase">
                            {p.language}
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-3 text-xs text-muted-foreground shrink-0">
                        {p.published_at && (
                          <span>{fmtDate(p.published_at)}</span>
                        )}
                        <span className="flex items-center gap-1">
                          <Eye className="h-3 w-3" />
                          {p.view_count}
                        </span>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </CardContent>
          </Card>

          {/* Two-column: top views + keyword movements */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 print:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <Eye className="h-4 w-4 text-primary" />
                  {t("digest.topViews")}
                </CardTitle>
              </CardHeader>
              <CardContent>
                {data.top_views.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    {t("digest.noViews")}
                  </p>
                ) : (
                  <ul className="space-y-1">
                    {data.top_views.map((v) => (
                      <li
                        key={v.slug}
                        className="flex items-center justify-between gap-2 text-sm border-b last:border-0 py-1"
                      >
                        <Link
                          to={`${base}/articles/${v.slug}`}
                          className="hover:text-primary truncate"
                        >
                          {v.title}
                        </Link>
                        <span className="font-mono text-xs text-muted-foreground shrink-0">
                          {v.view_count}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <ArrowUp className="h-4 w-4 text-green-600" />
                  {t("digest.topMovers")}
                </CardTitle>
              </CardHeader>
              <CardContent>
                {data.top_movers.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    {t("digest.noMovement")}
                  </p>
                ) : (
                  <ul className="space-y-1">
                    {data.top_movers.map((m, i) => (
                      <li
                        key={i}
                        className="flex items-center justify-between gap-2 text-sm border-b last:border-0 py-1"
                      >
                        <span className="truncate flex items-center gap-2">
                          <span>{m.keyword}</span>
                          <span className="text-[10px] uppercase text-muted-foreground">
                            {m.language}
                          </span>
                        </span>
                        <span className="text-xs font-mono shrink-0">
                          <span className="text-muted-foreground">
                            {formatPos(m.old_position)}
                          </span>
                          {" → "}
                          <span className="text-green-600 font-bold">
                            {formatPos(m.new_position)}
                          </span>
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>
          </div>

          {data.worst_movers.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <ArrowDown className="h-4 w-4 text-red-600" />
                  {t("digest.worstMovers")}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="space-y-1">
                  {data.worst_movers.map((m, i) => (
                    <li
                      key={i}
                      className="flex items-center justify-between gap-2 text-sm border-b last:border-0 py-1"
                    >
                      <span className="truncate flex items-center gap-2">
                        <span>{m.keyword}</span>
                        <span className="text-[10px] uppercase text-muted-foreground">
                          {m.language}
                        </span>
                      </span>
                      <span className="text-xs font-mono shrink-0">
                        <span className="text-muted-foreground">
                          {formatPos(m.old_position)}
                        </span>
                        {" → "}
                        <span className="text-red-600 font-bold">
                          {formatPos(m.new_position)}
                        </span>
                      </span>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}

          <p className="text-xs text-muted-foreground text-right">
            {t("digest.generatedAt")} {fmtDate(data.generated_at)}
          </p>
        </>
      )}
    </div>
  );
}
