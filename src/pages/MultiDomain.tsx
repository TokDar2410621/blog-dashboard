import { Link, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { authFetch } from "@/lib/api-client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  ArrowLeft,
  ExternalLink,
  CheckCircle2,
  XCircle,
  Eye,
  FileText,
  TrendingUp,
  Move as MoveIcon,
  Award,
} from "lucide-react";

type SiteStats = {
  id: number;
  name: string;
  domain: string;
  is_hosted: boolean;
  is_active: boolean;
  default_language: string;
  available_languages: string[];
  total_articles: number;
  published_articles: number;
  drafts: number;
  total_views: number;
  last_published_at: string | null;
  language_breakdown: Record<string, number>;
  tracked_keywords: number;
  redirects_count: number;
  gsc_configured: boolean;
  has_eeat_profile: boolean;
  error?: string;
};

type Result = {
  sites: SiteStats[];
  totals: {
    sites_count: number;
    active_sites: number;
    total_articles: number;
    total_views: number;
    total_tracked_keywords: number;
    sites_with_gsc: number;
    sites_with_eeat: number;
  };
};

export default function MultiDomain() {
  const { t } = useTranslation();
  const navigate = useNavigate();

  const { data, isLoading } = useQuery<Result>({
    queryKey: ["multi-domain-stats"],
    queryFn: async () => {
      const res = await authFetch("/multi-domain-stats/");
      if (!res.ok) throw new Error("fetch failed");
      return res.json();
    },
  });

  return (
    <div className="min-h-screen p-6">
      <div className="max-w-6xl mx-auto space-y-6">
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => navigate("/sites")}
            title={t("multiDomain.back")}
          >
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <div>
            <h1 className="text-2xl font-bold">{t("multiDomain.title")}</h1>
            <p className="text-muted-foreground">{t("multiDomain.subtitle")}</p>
          </div>
        </div>

        {isLoading && (
          <div className="space-y-3">
            <Skeleton className="h-32 w-full" />
            <Skeleton className="h-64 w-full" />
          </div>
        )}

        {data && (
          <>
            {/* Totals */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <Card>
                <CardContent className="pt-6">
                  <div className="text-3xl font-bold">{data.totals.active_sites}</div>
                  <div className="text-xs text-muted-foreground mt-1">
                    {t("multiDomain.activeSites", { total: data.totals.sites_count })}
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="pt-6">
                  <div className="text-3xl font-bold">{data.totals.total_articles}</div>
                  <div className="text-xs text-muted-foreground mt-1 flex items-center gap-1">
                    <FileText className="h-3 w-3" />
                    {t("multiDomain.totalPublished")}
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="pt-6">
                  <div className="text-3xl font-bold">{data.totals.total_views}</div>
                  <div className="text-xs text-muted-foreground mt-1 flex items-center gap-1">
                    <Eye className="h-3 w-3" />
                    {t("multiDomain.totalViews")}
                  </div>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="pt-6">
                  <div className="text-3xl font-bold">
                    {data.totals.total_tracked_keywords}
                  </div>
                  <div className="text-xs text-muted-foreground mt-1 flex items-center gap-1">
                    <TrendingUp className="h-3 w-3" />
                    {t("multiDomain.trackedKeywords")}
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Per-site table */}
            <Card>
              <CardHeader>
                <CardTitle className="text-lg">{t("multiDomain.perSite")}</CardTitle>
              </CardHeader>
              <CardContent className="p-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>{t("multiDomain.site")}</TableHead>
                      <TableHead className="text-right">
                        {t("multiDomain.articles")}
                      </TableHead>
                      <TableHead className="text-right">
                        {t("multiDomain.views")}
                      </TableHead>
                      <TableHead>{t("multiDomain.languages")}</TableHead>
                      <TableHead className="text-center">
                        {t("multiDomain.gsc")}
                      </TableHead>
                      <TableHead className="text-center">
                        {t("multiDomain.eeat")}
                      </TableHead>
                      <TableHead className="text-right">
                        <TrendingUp className="h-3 w-3 inline" />
                      </TableHead>
                      <TableHead className="text-right">
                        <MoveIcon className="h-3 w-3 inline" />
                      </TableHead>
                      <TableHead className="w-12"></TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {data.sites.map((s) => (
                      <TableRow key={s.id} className={!s.is_active ? "opacity-50" : ""}>
                        <TableCell>
                          <div className="flex flex-col">
                            <Link
                              to={`/dashboard/${s.id}`}
                              className="font-medium hover:text-primary"
                            >
                              {s.name}
                            </Link>
                            {s.domain && (
                              <span className="text-xs text-muted-foreground font-mono truncate max-w-xs">
                                {s.domain}
                              </span>
                            )}
                          </div>
                        </TableCell>
                        <TableCell className="text-right font-mono">
                          {s.published_articles ?? "-"}
                          {(s.drafts ?? 0) > 0 && (
                            <span className="text-xs text-muted-foreground ml-1">
                              (+{s.drafts})
                            </span>
                          )}
                        </TableCell>
                        <TableCell className="text-right font-mono">
                          {s.total_views ?? "-"}
                        </TableCell>
                        <TableCell>
                          <div className="flex gap-1">
                            {Object.entries(s.language_breakdown || {}).map(
                              ([lang, count]) => (
                                <span
                                  key={lang}
                                  className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground font-mono uppercase"
                                  title={`${count} articles`}
                                >
                                  {lang} ({count})
                                </span>
                              )
                            )}
                          </div>
                        </TableCell>
                        <TableCell className="text-center">
                          {s.gsc_configured ? (
                            <CheckCircle2 className="h-4 w-4 text-green-600 inline" />
                          ) : (
                            <XCircle className="h-4 w-4 text-muted-foreground inline" />
                          )}
                        </TableCell>
                        <TableCell className="text-center">
                          {s.has_eeat_profile ? (
                            <Award className="h-4 w-4 text-amber-500 inline" />
                          ) : (
                            <XCircle className="h-4 w-4 text-muted-foreground inline" />
                          )}
                        </TableCell>
                        <TableCell className="text-right font-mono text-xs">
                          {s.tracked_keywords ?? 0}
                        </TableCell>
                        <TableCell className="text-right font-mono text-xs">
                          {s.redirects_count ?? 0}
                        </TableCell>
                        <TableCell>
                          <Link to={`/dashboard/${s.id}`}>
                            <Button variant="ghost" size="icon">
                              <ExternalLink className="h-4 w-4" />
                            </Button>
                          </Link>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>

            {/* Coverage indicators */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Card>
                <CardHeader>
                  <CardTitle className="text-base">
                    {t("multiDomain.gscCoverage")}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">
                    {data.totals.sites_with_gsc} / {data.totals.sites_count}
                  </div>
                  <div className="h-2 w-full bg-muted rounded mt-2 overflow-hidden">
                    <div
                      className="h-full bg-primary"
                      style={{
                        width: `${
                          (data.totals.sites_with_gsc / Math.max(1, data.totals.sites_count)) *
                          100
                        }%`,
                      }}
                    />
                  </div>
                  <p className="text-xs text-muted-foreground mt-2">
                    {t("multiDomain.gscHint")}
                  </p>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-base">
                    {t("multiDomain.eeatCoverage")}
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-2xl font-bold">
                    {data.totals.sites_with_eeat} / {data.totals.sites_count}
                  </div>
                  <div className="h-2 w-full bg-muted rounded mt-2 overflow-hidden">
                    <div
                      className="h-full bg-amber-500"
                      style={{
                        width: `${
                          (data.totals.sites_with_eeat /
                            Math.max(1, data.totals.sites_count)) *
                          100
                        }%`,
                      }}
                    />
                  </div>
                  <p className="text-xs text-muted-foreground mt-2">
                    {t("multiDomain.eeatHint")}
                  </p>
                </CardContent>
              </Card>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
