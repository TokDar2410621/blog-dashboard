"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useDashboardStats } from "@/hooks/useDashboard";
import { StatsCard } from "@/components/StatsCard";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { FileText, Eye, PenLine, Clock, Lightbulb, ArrowRight, Search, BarChart3, Settings, TrendingDown, Link2, Network, UserCheck } from "lucide-react";
import { HreflangCard } from "@/components/dashboard/HreflangCard";
import { ProofCard } from "@/components/dashboard/ProofCard";
import {
  RecommendationsPanel,
  type Recommendation,
} from "@/components/dashboard/RecommendationsPanel";

// TODO: backend doit retourner sparkline + delta_7d par metric
// (articles_count, total_views, drafts_count, scheduled_count) dans
// /api/sites/:id/stats/. En attendant on génère un mock déterministe
// à partir de la valeur actuelle pour ne pas avoir d'effet "qui saute".
function mockSparkline(seed: number, current: number, points = 7): number[] {
  if (current <= 0) {
    return Array.from({ length: points }, () => 0);
  }
  // PRNG déterministe (mulberry32) seedée par (seed * 1000 + current)
  let s = (seed * 1000 + current) >>> 0;
  const rand = () => {
    s = (s + 0x6d2b79f5) >>> 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
  const out: number[] = [];
  for (let i = 0; i < points; i++) {
    const drift = (i / (points - 1)) * 0.15; // légère tendance haussière
    const noise = (rand() - 0.5) * 0.2; // +/- 10%
    out.push(Math.max(0, current * (0.85 + drift + noise)));
  }
  // Assure que le dernier point reflète la valeur réelle.
  out[out.length - 1] = current;
  return out;
}

// TODO: backend doit retourner delta_7d. Mock = pente entre premier et dernier point.
function mockDelta(series: number[]): number {
  if (series.length < 2) return 0;
  const first = series[0];
  const last = series[series.length - 1];
  if (first <= 0) return last > 0 ? 100 : 0;
  return ((last - first) / first) * 100;
}

export function OverviewPage() {
  const { data: stats, isLoading, isError } = useDashboardStats();
  const params = useParams<{ siteId: string }>();
  const siteId = params?.siteId;

  if (isLoading) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold">Tableau de bord</h1>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <Skeleton key={i} className="h-32" />
          ))}
        </div>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-bold">Tableau de bord</h1>
        <Card>
          <CardContent className="py-12 text-center">
            <p className="text-muted-foreground">
              Impossible de charger les statistiques. Vérifiez que le backend supporte l&apos;endpoint /api/dashboard/stats/.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  const totalPosts = stats?.total_posts ?? 0;
  const totalViews = stats?.total_views ?? 0;
  const drafts = stats?.drafts ?? 0;
  const scheduled = stats?.scheduled ?? 0;
  const isFirstRun = totalPosts === 0;
  const base = `/dashboard/${siteId}`;

  // Recommandations derivees cote client des stats deja chargees. Quand le
  // backend exposera /sites/:id/recommendations/ on remplacera cette liste
  // par un fetch direct. Pour l'instant on se base sur les signaux dispos :
  // - drafts en attente -> publier
  // - 0 mots-cles trackes -> setup positions
  // - pas d'articles -> generer
  // - sinon -> couvrir des sujets manquants (Topic Clusters)
  // - liens internes : geree par /link-graph
  // - E-E-A-T : geree par /parametres (auteur)
  const recommendations: Recommendation[] = !isFirstRun
    ? [
        ...(drafts > 0
          ? [
              {
                id: "publish-drafts",
                icon: PenLine,
                title: `Publier ${drafts} brouillon${drafts > 1 ? "s" : ""}`,
                description:
                  "Tu as des articles prets a publier. Chaque jour d'attente, c'est du trafic perdu.",
                action_label: "Voir",
                action_href: `${base}/articles?status=draft`,
                priority: "high" as const,
              },
            ]
          : []),
        {
          id: "re-optimize-decay",
          icon: TrendingDown,
          title: "Re-optimiser les pages en declin",
          description:
            "Identifie les articles qui perdent en impressions GSC et re-genere-les en 1 clic.",
          action_label: "Analyser",
          action_href: `${base}/decay`,
          priority: "high",
        },
        {
          id: "cover-missing-topics",
          icon: Network,
          title: "Couvrir les sujets manquants",
          description:
            "Topic Clusters detecte les trous dans ta couverture editoriale et suggere les briefs a generer.",
          action_label: "Explorer",
          action_href: `${base}/clusters`,
          priority: "medium",
        },
        {
          id: "internal-links",
          icon: Link2,
          title: "Reparer les liens internes manquants",
          description:
            "Le link-graph identifie les articles orphelins et les liens contextuels a ajouter pour booster le PageRank interne.",
          action_label: "Voir",
          action_href: `${base}/link-graph`,
          priority: "medium",
        },
        {
          id: "eeat-author",
          icon: UserCheck,
          title: "Completer le profil auteur (E-E-A-T)",
          description:
            "Bio, credentials, photo, lien LinkedIn. C'est le signal que Google recompense le plus depuis 2024.",
          action_label: "Configurer",
          action_href: `${base}/parametres/auteur`,
          priority: "low",
        },
      ]
    : [];

  // TODO: remplacer par stats.sparkline_* et stats.delta_*_7d quand le backend les expose.
  const sparkPosts = mockSparkline(1, totalPosts);
  const sparkViews = mockSparkline(2, totalViews);
  const sparkDrafts = mockSparkline(3, drafts);
  const sparkScheduled = mockSparkline(4, scheduled);
  const deltaPosts = mockDelta(sparkPosts);
  const deltaViews = mockDelta(sparkViews);
  const deltaDrafts = mockDelta(sparkDrafts);
  const deltaScheduled = mockDelta(sparkScheduled);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Tableau de bord</h1>
        <p className="text-muted-foreground">Site #{siteId}</p>
      </div>

      {/* First-run guidance - only shown when the site has 0 articles */}
      {isFirstRun && (
        <Card className="border-primary/30 bg-primary/5">
          <CardContent className="pt-6 space-y-4">
            <div className="flex items-start gap-3">
              <Lightbulb className="h-6 w-6 text-primary shrink-0 mt-1" />
              <div className="flex-1">
                <h2 className="text-xl font-bold">Bienvenue ! Voici tes 4 prochains pas.</h2>
                <p className="text-sm text-muted-foreground mt-1">
                  En 10 minutes tu vas avoir ton premier article SEO publié.
                </p>
              </div>
            </div>

            <ol className="space-y-3 text-sm">
              <li className="flex flex-wrap items-start gap-3 p-3 rounded border bg-background">
                <span className="shrink-0 h-6 w-6 rounded-full bg-primary text-primary-foreground flex items-center justify-center text-xs font-bold">1</span>
                <div className="flex-1 min-w-[12rem]">
                  <strong>Configure le profil auteur (E-E-A-T)</strong>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Bio + crédentials + photo. C&apos;est ce que Google récompense le plus en 2026.
                  </p>
                </div>
                <Link href={`${base}/parametres/auteur`}>
                  <Button size="sm" variant="outline" className="h-10 md:h-8">
                    <Settings className="h-3 w-3 mr-1.5" />
                    Paramètres
                  </Button>
                </Link>
              </li>
              <li className="flex flex-wrap items-start gap-3 p-3 rounded border bg-background">
                <span className="shrink-0 h-6 w-6 rounded-full bg-primary text-primary-foreground flex items-center justify-center text-xs font-bold">2</span>
                <div className="flex-1 min-w-[12rem]">
                  <strong>Génère un brief stratégique</strong>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Tape ton mot-clé cible, on extrait le top SERP + les vraies questions de ton audience.
                  </p>
                </div>
                <Link href={`${base}/generer`}>
                  <Button size="sm" variant="outline" className="h-10 md:h-8">
                    <Search className="h-3 w-3 mr-1.5" />
                    Brief
                  </Button>
                </Link>
              </li>
              <li className="flex flex-wrap items-start gap-3 p-3 rounded border bg-background">
                <span className="shrink-0 h-6 w-6 rounded-full bg-primary text-primary-foreground flex items-center justify-center text-xs font-bold">3</span>
                <div className="flex-1 min-w-[12rem]">
                  <strong>Génère ton premier article</strong>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Claude écrit en suivant ton brief, en lexique québécois, avec ta voix.
                  </p>
                </div>
                <Link href={`${base}/generer`}>
                  <Button size="sm" className="h-10 md:h-8">
                    <PenLine className="h-3 w-3 mr-1.5" />
                    Générer
                  </Button>
                </Link>
              </li>
              <li className="flex flex-wrap items-start gap-3 p-3 rounded border bg-background">
                <span className="shrink-0 h-6 w-6 rounded-full bg-primary text-primary-foreground flex items-center justify-center text-xs font-bold">4</span>
                <div className="flex-1 min-w-[12rem]">
                  <strong>Suis tes mots-clés</strong>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Ajoute 5 mots-clés cibles. On snapshot leur position Google chaque jour.
                  </p>
                </div>
                <Link href={`${base}/positions`}>
                  <Button size="sm" variant="outline" className="h-10 md:h-8">
                    <BarChart3 className="h-3 w-3 mr-1.5" />
                    Positions
                  </Button>
                </Link>
              </li>
            </ol>

            <div className="pt-2 text-xs text-muted-foreground flex items-center gap-1">
              <ArrowRight className="h-3 w-3" />
              Une fois ton premier article publié, ce panneau disparaît.
            </div>
          </CardContent>
        </Card>
      )}

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatsCard
          title="Total articles"
          value={totalPosts}
          icon={FileText}
          sparkline={sparkPosts}
          delta={deltaPosts}
        />
        <StatsCard
          title="Total vues"
          value={totalViews}
          icon={Eye}
          sparkline={sparkViews}
          delta={deltaViews}
        />
        <StatsCard
          title="Brouillons"
          value={drafts}
          icon={PenLine}
          sparkline={sparkDrafts}
          delta={deltaDrafts}
        />
        <StatsCard
          title="Planifiés"
          value={scheduled}
          icon={Clock}
          sparkline={sparkScheduled}
          delta={deltaScheduled}
        />
      </div>

      {/* Proof of value (GSC baseline + attribution) */}
      {siteId && !isFirstRun && <ProofCard siteId={siteId} />}

      {/* Hreflang health */}
      {siteId && <HreflangCard siteId={siteId} />}

      {/* Recommendations inbox - actions a fort impact derivees des stats */}
      {!isFirstRun && (
        <RecommendationsPanel
          recommendations={recommendations}
          subtitle="Actions a fort impact, triees par priorite. Cliquez pour aller a la page concernee."
        />
      )}

      {/* Recent Posts */}
      {stats?.recent_posts && stats.recent_posts.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Articles récents</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {stats.recent_posts.map((post) => (
                <div
                  key={post.slug}
                  className="flex items-center justify-between py-2 border-b last:border-0"
                >
                  <div className="min-w-0 flex-1">
                    <p className="font-medium text-sm truncate">{post.title}</p>
                    <p className="text-xs text-muted-foreground">
                      {new Date(post.created_at).toLocaleDateString("fr-CA")}
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-4 text-sm text-muted-foreground">
                    <span className="flex items-center gap-1">
                      <Eye className="h-3 w-3" />
                      {post.view_count}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

export default OverviewPage;
