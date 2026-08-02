"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
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

export function LinkGraphPage() {
  const params = useParams<{ siteId: string }>();
  const siteId = params?.siteId;
  const [language, setLanguage] = useState<string>("");
  const base = `/dashboard/${siteId}`;

  const { data, isLoading, isError } = useQuery<GraphResult>({
    queryKey: ["link-graph", siteId, language],
    queryFn: async () => {
      const qs = language ? `?language=${language}` : "";
      const res = await authFetch(`/sites/${siteId}/link-graph/${qs}`);
      if (!res.ok) throw new Error("link-graph fetch failed");
      return res.json();
    },
    staleTime: 5 * 60 * 1000,
  });

  return (
    <div className="space-y-6 max-w-6xl">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Graphe de maillage interne</h1>
          <p className="text-muted-foreground">
            Identifie les articles orphelins (sans lien entrant), les hubs
            (&gt;=5 liens entrants) et les dead-ends (sans lien sortant) pour
            optimiser ton link juice.
          </p>
        </div>
        <Select value={language || "all"} onValueChange={(v) => setLanguage(v === "all" ? "" : v)}>
          <SelectTrigger className="w-32">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">Toutes</SelectItem>
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
            Impossible de charger le graphe.
          </CardContent>
        </Card>
      )}

      {data && data.article_count > 0 && (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Card>
              <CardContent className="pt-6">
                <div className="text-3xl font-bold">{data.article_count}</div>
                <div className="text-xs text-muted-foreground mt-1">
                  Articles
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-3xl font-bold">{data.edge_count}</div>
                <div className="text-xs text-muted-foreground mt-1">
                  Liens internes
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
                  Orphelins
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
                  Hubs
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
                  Orphelins
                </CardTitle>
                <p className="text-xs text-muted-foreground">
                  Aucun lien entrant. À relier depuis d'autres articles.
                </p>
              </CardHeader>
              <CardContent>
                {data.orphans.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    Aucun orphelin.
                  </p>
                ) : (
                  <ul className="space-y-1 max-h-96 overflow-y-auto">
                    {data.orphans.slice(0, 30).map((n) => (
                      <li key={n.slug} className="text-sm">
                        <Link
                          href={`${base}/articles/${n.slug}`}
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
                  Hubs
                </CardTitle>
                <p className="text-xs text-muted-foreground">
                  5+ liens entrants. Articles forts, prioriser leur SEO.
                </p>
              </CardHeader>
              <CardContent>
                {data.hubs.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    Aucun hub pour l'instant.
                  </p>
                ) : (
                  <ul className="space-y-1 max-h-96 overflow-y-auto">
                    {data.hubs.slice(0, 30).map((n) => (
                      <li key={n.slug} className="text-sm">
                        <Link
                          href={`${base}/articles/${n.slug}`}
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
                  Dead-ends
                </CardTitle>
                <p className="text-xs text-muted-foreground">
                  Aucun lien sortant. Ajouter des liens internes.
                </p>
              </CardHeader>
              <CardContent>
                {data.dead_ends.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    Aucun dead-end.
                  </p>
                ) : (
                  <ul className="space-y-1 max-h-96 overflow-y-auto">
                    {data.dead_ends.slice(0, 30).map((n) => (
                      <li key={n.slug} className="text-sm">
                        <Link
                          href={`${base}/articles/${n.slug}`}
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
              <CardTitle className="text-base">Top 10 articles les mieux connectés</CardTitle>
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
                        href={`${base}/articles/${n.slug}`}
                        className="hover:text-primary truncate flex-1"
                      >
                        {n.title}
                      </Link>
                      <div className="flex items-center gap-3 shrink-0 text-xs font-mono">
                        <span className="text-green-600" title="Liens entrants">
                          ↑ {n.in_degree}
                        </span>
                        <ArrowRight className="h-3 w-3 text-muted-foreground" />
                        <span className="text-blue-600" title="Liens sortants">
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
            <p>Aucun article publié à analyser.</p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
