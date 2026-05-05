import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { authFetch } from "@/lib/api-client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Network,
  Unlink,
  Link as LinkIcon,
  TreePalm,
  ArrowRight,
} from "lucide-react";

type Node = {
  slug: string;
  title: string;
  in_degree: number;
  out_degree: number;
};

type GraphResult = {
  site_id: number;
  language: string | null;
  article_count: number;
  edge_count: number;
  nodes: Node[];
  edges: { from: string; to: string }[];
  orphans: Node[];
  orphans_count: number;
  hubs: Node[];
  hubs_count: number;
  dead_ends: Node[];
  dead_ends_count: number;
};

export default function LinkGraph() {
  const { t } = useTranslation();
  const { siteId } = useParams<{ siteId: string }>();
  const [language, setLanguage] = useState<string>("");
  const base = `/dashboard/${siteId}`;

  const { data, isLoading, isError } = useQuery<GraphResult>({
    queryKey: ["link-graph", siteId, language],
    queryFn: async () => {
      const params = language ? `?language=${language}` : "";
      const res = await authFetch(`/sites/${siteId}/link-graph/${params}`);
      if (!res.ok) throw new Error("link-graph fetch failed");
      return res.json();
    },
    staleTime: 5 * 60 * 1000,
  });

  return (
    <div className="space-y-6 max-w-6xl">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">{t("linkGraph.title")}</h1>
          <p className="text-muted-foreground">{t("linkGraph.subtitle")}</p>
        </div>
        <Select value={language || "all"} onValueChange={(v) => setLanguage(v === "all" ? "" : v)}>
          <SelectTrigger className="w-32">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">{t("linkGraph.allLangs")}</SelectItem>
            <SelectItem value="fr">FR</SelectItem>
            <SelectItem value="en">EN</SelectItem>
            <SelectItem value="es">ES</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {isLoading && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Skeleton className="h-64" />
          <Skeleton className="h-64" />
          <Skeleton className="h-64" />
        </div>
      )}

      {isError && (
        <Card>
          <CardContent className="py-6 text-center text-sm text-muted-foreground">
            {t("linkGraph.error")}
          </CardContent>
        </Card>
      )}

      {data && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Card>
              <CardContent className="pt-6">
                <div className="text-3xl font-bold">{data.article_count}</div>
                <div className="text-xs text-muted-foreground mt-1">
                  {t("linkGraph.articles")}
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-3xl font-bold">{data.edge_count}</div>
                <div className="text-xs text-muted-foreground mt-1">
                  {t("linkGraph.links")}
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-3xl font-bold text-amber-600 flex items-center gap-2">
                  <Unlink className="h-6 w-6" />
                  {data.orphans_count}
                </div>
                <div className="text-xs text-muted-foreground mt-1">
                  {t("linkGraph.orphans")}
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-3xl font-bold text-green-600 flex items-center gap-2">
                  <LinkIcon className="h-6 w-6" />
                  {data.hubs_count}
                </div>
                <div className="text-xs text-muted-foreground mt-1">
                  {t("linkGraph.hubs")}
                </div>
              </CardContent>
            </Card>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Orphans */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <Unlink className="h-4 w-4 text-amber-600" />
                  {t("linkGraph.orphansTitle")}
                </CardTitle>
                <p className="text-xs text-muted-foreground">
                  {t("linkGraph.orphansHint")}
                </p>
              </CardHeader>
              <CardContent>
                {data.orphans.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    {t("linkGraph.noOrphans")}
                  </p>
                ) : (
                  <ul className="space-y-1 max-h-96 overflow-y-auto">
                    {data.orphans.slice(0, 30).map((n) => (
                      <li key={n.slug} className="text-sm">
                        <Link
                          to={`${base}/articles/${n.slug}`}
                          className="hover:text-primary flex items-center justify-between gap-2 py-1 border-b last:border-0"
                        >
                          <span className="truncate">{n.title}</span>
                          <span className="text-[10px] font-mono text-muted-foreground shrink-0">
                            ↑{n.in_degree} ↓{n.out_degree}
                          </span>
                        </Link>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>

            {/* Hubs */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <LinkIcon className="h-4 w-4 text-green-600" />
                  {t("linkGraph.hubsTitle")}
                </CardTitle>
                <p className="text-xs text-muted-foreground">
                  {t("linkGraph.hubsHint")}
                </p>
              </CardHeader>
              <CardContent>
                {data.hubs.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    {t("linkGraph.noHubs")}
                  </p>
                ) : (
                  <ul className="space-y-1 max-h-96 overflow-y-auto">
                    {data.hubs.slice(0, 30).map((n) => (
                      <li key={n.slug} className="text-sm">
                        <Link
                          to={`${base}/articles/${n.slug}`}
                          className="hover:text-primary flex items-center justify-between gap-2 py-1 border-b last:border-0"
                        >
                          <span className="truncate">{n.title}</span>
                          <span className="text-[10px] font-mono text-green-600 shrink-0">
                            ↑{n.in_degree}
                          </span>
                        </Link>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>

            {/* Dead-ends */}
            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <TreePalm className="h-4 w-4 text-red-600" />
                  {t("linkGraph.deadEndsTitle")}
                </CardTitle>
                <p className="text-xs text-muted-foreground">
                  {t("linkGraph.deadEndsHint")}
                </p>
              </CardHeader>
              <CardContent>
                {data.dead_ends.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    {t("linkGraph.noDeadEnds")}
                  </p>
                ) : (
                  <ul className="space-y-1 max-h-96 overflow-y-auto">
                    {data.dead_ends.slice(0, 30).map((n) => (
                      <li key={n.slug} className="text-sm">
                        <Link
                          to={`${base}/articles/${n.slug}`}
                          className="hover:text-primary flex items-center justify-between gap-2 py-1 border-b last:border-0"
                        >
                          <span className="truncate">{n.title}</span>
                          <span className="text-[10px] font-mono text-muted-foreground shrink-0">
                            ↑{n.in_degree}
                          </span>
                        </Link>
                      </li>
                    ))}
                  </ul>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Top connected nodes */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">{t("linkGraph.topConnected")}</CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="space-y-1">
                {[...data.nodes]
                  .sort((a, b) => (b.in_degree + b.out_degree) - (a.in_degree + a.out_degree))
                  .slice(0, 10)
                  .map((n) => (
                    <li
                      key={n.slug}
                      className="text-sm flex items-center justify-between gap-2 border-b last:border-0 py-2"
                    >
                      <Link
                        to={`${base}/articles/${n.slug}`}
                        className="hover:text-primary truncate flex-1"
                      >
                        {n.title}
                      </Link>
                      <div className="flex items-center gap-3 shrink-0 text-xs font-mono">
                        <span className="text-green-600" title={t("linkGraph.in")}>
                          ↑ {n.in_degree}
                        </span>
                        <ArrowRight className="h-3 w-3 text-muted-foreground" />
                        <span className="text-blue-600" title={t("linkGraph.out")}>
                          ↓ {n.out_degree}
                        </span>
                      </div>
                    </li>
                  ))}
              </ul>
            </CardContent>
          </Card>
        </>
      )}

      {!isLoading && !isError && !data?.article_count && (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            <Network className="h-10 w-10 mx-auto mb-3 opacity-30" />
            <p>{t("linkGraph.empty")}</p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
