"use client";

import { useMemo, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { useMutation } from "@tanstack/react-query";
import { authFetch } from "@/lib/api-client";
import { usePersistedState } from "@/hooks/usePersistedState";
import { useJobs } from "@/context/JobsContext";
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
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Network,
  Loader2,
  Star,
  GitBranch,
  Lightbulb,
  Sparkles,
  AlertCircle,
  Hexagon,
  List as ListIcon,
  Layers,
  Copy,
} from "lucide-react";
import { toast } from "sonner";
import { PageBreadcrumb } from "@/components/PageBreadcrumb";
import {
  TopicalMap,
  type TopicalCluster,
} from "@/components/topics/TopicalMap";
import { TopicDrawer } from "@/components/topics/TopicDrawer";
import type { HexTopic, HexStatus } from "@/components/topics/HexTile";

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

type ClusterBuildPage = {
  role: "pillar" | "spoke";
  exists: boolean;
  keyword: string;
  slug: string;
  build_prompt?: string;
};

type ClusterBuild = {
  pillar: ClusterBuildPage;
  spokes: ClusterBuildPage[];
  counts: { pillar: number; spokes: number };
  note: string;
};

export function TopicClustersPage() {
  const params = useParams<{ siteId: string }>();
  const siteId = params?.siteId;
  // Persisted across navigations - clusters are expensive to recompute
  // (Serper + Gemini, ~30s + cost). Keeping the result around lets the user
  // come back and act on suggestions without re-running.
  const persistKey = (slot: string) => `gridar:site:${siteId}:topic-clusters:${slot}`;
  const [language, setLanguage] = usePersistedState<string>(persistKey("language"), "fr");
  const [data, setData] = usePersistedState<ClusterResult | null>(persistKey("data"), null);
  const [view, setView] = usePersistedState<"map" | "list">(
    persistKey("view"),
    "map",
  );
  const base = `/dashboard/${siteId}`;

  const [drawerOpen, setDrawerOpen] = useState(false);
  const [selection, setSelection] = useState<{
    topic: HexTopic;
    clusterTheme: string;
  } | null>(null);

  const jobs = useJobs();

  const mutation = useMutation({
    mutationFn: async () => {
      const res = await authFetch(`/sites/${siteId}/topic-clusters/`, {
        method: "POST",
        body: JSON.stringify({ language, limit: 80 }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error || "Erreur lors du clustering");
      }
      return (await res.json()) as ClusterResult;
    },
    onSuccess: (d) => setData(d),
    onError: (err: Error) => toast.error(err.message),
  });

  // "Construire tout le cluster": generate the coordinated build bundle (pillar
  // + every missing spoke) with the internal mesh baked into each prompt. The
  // existing pillar is linked, not rebuilt. No LLM/quota - the agent writes it.
  const [buildResult, setBuildResult] = useState<{
    idx: number;
    bundle: ClusterBuild;
  } | null>(null);

  const buildMutation = useMutation({
    mutationFn: async (vars: { idx: number; cluster: Cluster }) => {
      const c = vars.cluster;
      const spokeTitles = [
        ...c.suggested_new_articles.map((s) => s.title),
        ...c.spokes.filter((s) => !s.exists).map((s) => s.title),
      ];
      const res = await authFetch(`/sites/${siteId}/clusters/build/`, {
        method: "POST",
        body: JSON.stringify({
          pillar_keyword: c.pillar?.title || c.theme,
          pillar_slug: c.pillar?.exists ? c.pillar.slug : undefined,
          spokes: spokeTitles,
          language,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error || "Erreur lors de la construction");
      }
      const bundle = (await res.json()) as ClusterBuild;
      return { idx: vars.idx, bundle };
    },
    onSuccess: (r) => setBuildResult(r),
    onError: (err: Error) => toast.error(err.message),
  });

  const copyPrompt = (text: string) => {
    navigator.clipboard.writeText(text).then(
      () => toast.success("Prompt copié"),
      () => toast.error("Copie impossible"),
    );
  };

  /**
   * Map the backend cluster shape to the hex grid shape consumed by TopicalMap.
   *
   * - pillar + spokes that "exist" become "covered" hexes
   * - spokes flagged exists=false become "missing" hexes (the LLM hinted at
   *   them but no article matched)
   * - suggested_new_articles become "recommended" hexes
   *
   * Volume/KD aren't returned by the cluster endpoint yet - left undefined.
   */
  const hexClusters = useMemo<TopicalCluster[]>(() => {
    if (!data) return [];
    return data.clusters.map((c) => {
      const topics: HexTopic[] = [];
      if (c.pillar) {
        topics.push({
          label: c.pillar.title,
          status: (c.pillar.exists ? "covered" : "missing") as HexStatus,
          meta: { slug: c.pillar.slug, pillar: true },
        });
      }
      for (const sp of c.spokes) {
        topics.push({
          label: sp.title,
          status: (sp.exists ? "covered" : "missing") as HexStatus,
          meta: { slug: sp.slug },
        });
      }
      for (const sn of c.suggested_new_articles) {
        topics.push({
          label: sn.title,
          status: "recommended" as HexStatus,
          meta: { rationale: sn.rationale },
        });
      }
      return {
        theme: c.theme,
        summary: c.summary,
        topics,
      };
    });
  }, [data]);

  const handleTopicClick = (topic: HexTopic, clusterTheme: string) => {
    // Covered articles already have a dedicated page - go straight there
    // for that case, otherwise open the drawer to let the user pick an
    // angle and trigger generation.
    if (topic.status === "covered" && topic.meta?.slug) {
      // We could navigate, but keeping the drawer behavior consistent
      // lets the user discover the article preview + decide. Open drawer.
      setSelection({ topic, clusterTheme });
      setDrawerOpen(true);
      return;
    }
    setSelection({ topic, clusterTheme });
    setDrawerOpen(true);
  };

  /** Fires the analysis as a background job so the user can navigate away. */
  const runClusters = () => {
    jobs.start({
      kind: "topic-clusters",
      label: `Analyse clusters (${language.toUpperCase()})`,
      siteId,
      targetUrl: `/dashboard/${siteId}/clusters`,
      run: () => mutation.mutateAsync(),
    });
    toast.info("Analyse clusters lancee. Suis l'avancement dans le dock en bas a droite.");
  };

  return (
    <div className="space-y-6 max-w-6xl">
      <PageBreadcrumb trail={[{ label: "Clusters" }]} />
      <div>
        <h1 className="text-2xl font-bold">Topic clusters (pillars + spokes)</h1>
        <p className="text-muted-foreground">
          Gemini groupe tes articles publiés par thème, identifie le pillar
          candidate de chaque cluster et propose les articles à écrire pour
          combler les trous.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Network className="h-5 w-5 text-primary" />
            Lancer le clustering
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-end gap-3">
            <div className="space-y-2">
              <label className="text-sm font-medium">Langue</label>
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
              onClick={runClusters}
              disabled={mutation.isPending}
              size="lg"
            >
              {mutation.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Clustering...
                </>
              ) : (
                <>
                  <Network className="h-4 w-4 mr-2" />
                  Analyser
                </>
              )}
            </Button>
          </div>
          {mutation.isPending && (
            <p className="text-xs text-muted-foreground mt-3">
              Gemini analyse jusqu'à 80 articles. Compte 10-30s selon la taille du blog.
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
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <div className="flex items-center gap-3 text-sm text-muted-foreground">
              <span>
                {data.clusters.length} clusters trouvés sur {data.article_count} articles analysés.
              </span>
              {data.unassigned.length > 0 && (
                <span className="flex items-center gap-1 text-amber-600">
                  <AlertCircle className="h-4 w-4" />
                  {data.unassigned.length} non rattachés
                </span>
              )}
            </div>

            <Tabs
              value={view}
              onValueChange={(v) => setView(v as "map" | "list")}
              className="w-auto"
            >
              <TabsList>
                <TabsTrigger value="map" className="gap-1.5">
                  <Hexagon className="h-3.5 w-3.5" />
                  Topical Map
                </TabsTrigger>
                <TabsTrigger value="list" className="gap-1.5">
                  <ListIcon className="h-3.5 w-3.5" />
                  Liste
                </TabsTrigger>
              </TabsList>
            </Tabs>
          </div>

          {data.message && (
            <Card>
              <CardContent className="py-6 text-center text-sm text-muted-foreground">
                {data.message}
              </CardContent>
            </Card>
          )}

          {view === "map" && hexClusters.length > 0 && (
            <TopicalMap
              clusters={hexClusters}
              onTopicClick={handleTopicClick}
            />
          )}

          {view === "list" && data.clusters.map((cluster, idx) => (
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
                      Pillar candidate (à développer en page exhaustive)
                    </h4>
                    <Link
                      href={`${base}/articles/${cluster.pillar.slug}`}
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
                      Spokes (sous-sujets) ({cluster.spokes.length})
                    </h4>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                      {cluster.spokes.map((sp) => (
                        <Link
                          key={sp.slug}
                          href={`${base}/articles/${sp.slug}`}
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
                      Articles à écrire pour combler le cluster
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
                            href={
                              `${base}/generer?` +
                              [
                                `title=${encodeURIComponent(sn.title)}`,
                                `topic=${encodeURIComponent(cluster.theme)}`,
                                `keywords=${encodeURIComponent(cluster.theme)}`,
                                `autostart=1`,
                              ].join("&")
                            }
                          >
                            <Button size="sm" variant="outline">
                              <Sparkles className="h-3 w-3 mr-1" />
                              Générer
                            </Button>
                          </Link>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Build the whole cluster at once (pillar linked, spokes
                    generated) with the internal mesh baked in. */}
                {(cluster.suggested_new_articles.length > 0 ||
                  cluster.spokes.some((s) => !s.exists)) && (
                  <div className="pt-1 border-t">
                    <Button
                      size="sm"
                      className="mt-3"
                      onClick={() => buildMutation.mutate({ idx, cluster })}
                      disabled={buildMutation.isPending}
                    >
                      {buildMutation.isPending &&
                      buildMutation.variables?.idx === idx ? (
                        <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                      ) : (
                        <Layers className="h-3 w-3 mr-1" />
                      )}
                      Construire tout le cluster (maillage inclus)
                    </Button>
                  </div>
                )}

                {buildResult?.idx === idx && (
                  <div className="border rounded-lg p-3 bg-muted/30 space-y-3">
                    <div className="flex items-center justify-between gap-2 flex-wrap">
                      <p className="text-sm font-medium flex items-center gap-1.5">
                        <Layers className="h-4 w-4" />
                        Bundle du cluster (maillage pilier ↔ spokes inclus)
                      </p>
                      <span className="text-xs text-muted-foreground">
                        {buildResult.bundle.pillar.exists
                          ? "pilier existant lié"
                          : "pilier à construire"}{" "}
                        · {buildResult.bundle.spokes.length} article(s)
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground">
                      {buildResult.bundle.note}
                    </p>
                    {[buildResult.bundle.pillar, ...buildResult.bundle.spokes]
                      .filter((p) => p.build_prompt)
                      .map((p, i) => (
                        <div
                          key={i}
                          className="border rounded p-2 bg-background flex items-center justify-between gap-2"
                        >
                          <div className="min-w-0">
                            <p className="text-sm font-medium truncate">
                              {p.role === "pillar" ? "Pilier" : "Spoke"} ·{" "}
                              {p.keyword}
                            </p>
                            <p className="text-xs text-muted-foreground font-mono truncate">
                              /{p.slug}
                            </p>
                          </div>
                          <Button
                            size="sm"
                            variant="outline"
                            className="shrink-0"
                            onClick={() => copyPrompt(p.build_prompt as string)}
                          >
                            <Copy className="h-3 w-3 mr-1" />
                            Copier le prompt
                          </Button>
                        </div>
                      ))}
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
                  Articles non rattachés
                </CardTitle>
                <p className="text-xs text-muted-foreground">
                  Articles trop spécifiques ou hors-sujet pour les clusters trouvés.
                </p>
              </CardHeader>
              <CardContent>
                <ul className="text-sm space-y-1">
                  {data.unassigned.map((u) => (
                    <li key={u.slug}>
                      <Link
                        href={`${base}/articles/${u.slug}`}
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
            <p>Lance le clustering pour découvrir les structures thématiques de ton site.</p>
          </CardContent>
        </Card>
      )}

      <TopicDrawer
        open={drawerOpen}
        onOpenChange={setDrawerOpen}
        selection={selection}
        siteBase={base}
      />
    </div>
  );
}
