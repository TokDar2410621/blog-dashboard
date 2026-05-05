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
  Network,
  Loader2,
  Star,
  GitBranch,
  Lightbulb,
  Sparkles,
  Plus,
  AlertCircle,
} from "lucide-react";
import { toast } from "sonner";

type SlugRef = { slug: string; title: string; exists: boolean };

type SuggestedArticle = { title: string; rationale: string };

type Cluster = {
  theme: string;
  summary: string;
  pillar: SlugRef | null;
  spokes: SlugRef[];
  suggested_new_articles: SuggestedArticle[];
};

type ClusterResult = {
  site_id: number;
  language: string;
  article_count: number;
  clusters: Cluster[];
  unassigned: { slug: string; title: string }[];
  message?: string;
};

export default function TopicClusters() {
  const { t } = useTranslation();
  const { siteId } = useParams<{ siteId: string }>();
  const [language, setLanguage] = useState("fr");
  const [data, setData] = useState<ClusterResult | null>(null);
  const base = `/dashboard/${siteId}`;

  const mutation = useMutation({
    mutationFn: async () => {
      const res = await authFetch(`/sites/${siteId}/topic-clusters/`, {
        method: "POST",
        body: JSON.stringify({ language, limit: 80 }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error || t("clusters.error"));
      }
      return (await res.json()) as ClusterResult;
    },
    onSuccess: (d) => setData(d),
    onError: (err: Error) => toast.error(err.message),
  });

  return (
    <div className="space-y-6 max-w-6xl">
      <div>
        <h1 className="text-2xl font-bold">{t("clusters.title")}</h1>
        <p className="text-muted-foreground">{t("clusters.subtitle")}</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Network className="h-5 w-5 text-primary" />
            {t("clusters.runTitle")}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-end gap-3">
            <div className="space-y-2">
              <label className="text-sm font-medium">{t("clusters.language")}</label>
              <Select value={language} onValueChange={setLanguage}>
                <SelectTrigger className="w-32">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="fr">FR</SelectItem>
                  <SelectItem value="en">EN</SelectItem>
                  <SelectItem value="es">ES</SelectItem>
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
                  {t("clusters.running")}
                </>
              ) : (
                <>
                  <Network className="h-4 w-4 mr-2" />
                  {t("clusters.run")}
                </>
              )}
            </Button>
          </div>
          {mutation.isPending && (
            <p className="text-xs text-muted-foreground mt-3">
              {t("clusters.runWait")}
            </p>
          )}
        </CardContent>
      </Card>

      {mutation.isPending && (
        <div className="space-y-3">
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-32 w-full" />
        </div>
      )}

      {data && !mutation.isPending && (
        <>
          <div className="flex items-center gap-3 text-sm text-muted-foreground">
            <span>
              {t("clusters.summary", {
                clusters: data.clusters.length,
                articles: data.article_count,
              })}
            </span>
            {data.unassigned.length > 0 && (
              <span className="flex items-center gap-1 text-amber-600">
                <AlertCircle className="h-4 w-4" />
                {t("clusters.unassignedCount", { count: data.unassigned.length })}
              </span>
            )}
          </div>

          {data.message && (
            <Card>
              <CardContent className="py-6 text-center text-sm text-muted-foreground">
                {data.message}
              </CardContent>
            </Card>
          )}

          {data.clusters.map((cluster, idx) => (
            <Card key={idx}>
              <CardHeader>
                <CardTitle className="text-lg">
                  <span className="text-xs font-mono text-muted-foreground mr-2">
                    #{idx + 1}
                  </span>
                  {cluster.theme}
                </CardTitle>
                {cluster.summary && (
                  <p className="text-sm text-muted-foreground">{cluster.summary}</p>
                )}
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Pillar */}
                {cluster.pillar && (
                  <div>
                    <h4 className="text-xs font-mono uppercase tracking-wide text-muted-foreground mb-2 flex items-center gap-1">
                      <Star className="h-3 w-3 text-amber-500" />
                      {t("clusters.pillar")}
                    </h4>
                    <Link
                      to={`${base}/articles/${cluster.pillar.slug}`}
                      className="block border-2 border-primary/30 rounded p-3 hover:border-primary"
                    >
                      <div className="flex items-center gap-2">
                        <Star className="h-4 w-4 text-amber-500 fill-amber-500" />
                        <span className="font-medium text-sm">
                          {cluster.pillar.title}
                        </span>
                      </div>
                      <p className="text-xs text-muted-foreground mt-1 font-mono">
                        /{cluster.pillar.slug}
                      </p>
                    </Link>
                  </div>
                )}

                {/* Spokes */}
                {cluster.spokes.length > 0 && (
                  <div>
                    <h4 className="text-xs font-mono uppercase tracking-wide text-muted-foreground mb-2 flex items-center gap-1">
                      <GitBranch className="h-3 w-3" />
                      {t("clusters.spokes")} ({cluster.spokes.length})
                    </h4>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                      {cluster.spokes.map((sp) => (
                        <Link
                          key={sp.slug}
                          to={`${base}/articles/${sp.slug}`}
                          className="border rounded p-2 hover:border-primary text-sm flex items-center gap-2"
                        >
                          <GitBranch className="h-3 w-3 text-muted-foreground shrink-0" />
                          <span className="truncate">{sp.title}</span>
                          {!sp.exists && (
                            <span className="text-[10px] px-1 rounded bg-amber-500/10 text-amber-600 ml-auto shrink-0">
                              ?
                            </span>
                          )}
                        </Link>
                      ))}
                    </div>
                  </div>
                )}

                {/* Suggested new articles */}
                {cluster.suggested_new_articles.length > 0 && (
                  <div>
                    <h4 className="text-xs font-mono uppercase tracking-wide text-muted-foreground mb-2 flex items-center gap-1">
                      <Lightbulb className="h-3 w-3 text-amber-500" />
                      {t("clusters.suggestedGaps")}
                    </h4>
                    <div className="space-y-2">
                      {cluster.suggested_new_articles.map((sn, i) => (
                        <div
                          key={i}
                          className="border border-dashed rounded p-3 flex items-start justify-between gap-3"
                        >
                          <div className="flex-1 min-w-0">
                            <p className="font-medium text-sm">{sn.title}</p>
                            {sn.rationale && (
                              <p className="text-xs text-muted-foreground mt-1">
                                {sn.rationale}
                              </p>
                            )}
                          </div>
                          <Link
                            to={`${base}/generer?title=${encodeURIComponent(sn.title)}`}
                          >
                            <Button size="sm" variant="outline">
                              <Sparkles className="h-3 w-3 mr-1" />
                              {t("clusters.generate")}
                            </Button>
                          </Link>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          ))}

          {/* Unassigned articles */}
          {data.unassigned.length > 0 && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <AlertCircle className="h-4 w-4 text-amber-600" />
                  {t("clusters.unassignedTitle")}
                </CardTitle>
                <p className="text-xs text-muted-foreground">
                  {t("clusters.unassignedHint")}
                </p>
              </CardHeader>
              <CardContent>
                <ul className="text-sm space-y-1">
                  {data.unassigned.map((u) => (
                    <li key={u.slug}>
                      <Link
                        to={`${base}/articles/${u.slug}`}
                        className="hover:text-primary"
                      >
                        {u.title}
                      </Link>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}
        </>
      )}

      {!data && !mutation.isPending && (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            <Network className="h-10 w-10 mx-auto mb-3 opacity-30" />
            <p>{t("clusters.intro")}</p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
