"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useDashboardStats } from "@/hooks/useDashboard";
import { StatsCard } from "@/components/StatsCard";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  FileText,
  Eye,
  PenLine,
  Clock,
  Sparkles,
  ArrowRight,
  Search,
  BarChart3,
  Settings,
} from "lucide-react";
import { HreflangCard } from "@/components/HreflangCard";

export default function Overview() {
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
              Impossible de charger les statistiques. Verifiez que le backend supporte l&apos;endpoint /api/sites/&lt;id&gt;/stats/.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  const totalPosts = stats?.total_posts ?? 0;
  const isFirstRun = totalPosts === 0;
  const base = `/dashboard/${siteId}`;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Tableau de bord</h1>
        <p className="text-muted-foreground">Site #{siteId}</p>
      </div>

      {isFirstRun && (
        <Card className="border-primary/30 bg-primary/5">
          <CardContent className="pt-6 space-y-4">
            <div className="flex items-start gap-3">
              <Sparkles className="h-6 w-6 text-primary shrink-0 mt-1" />
              <div className="flex-1">
                <h2 className="text-xl font-bold">Bienvenue ! Voici tes 4 prochains pas.</h2>
                <p className="text-sm text-muted-foreground mt-1">
                  En 10 minutes tu vas avoir ton premier article SEO publie.
                </p>
              </div>
            </div>

            <ol className="space-y-3 text-sm">
              <li className="flex items-start gap-3 p-3 rounded border bg-background">
                <span className="shrink-0 h-6 w-6 rounded-full bg-primary text-primary-foreground flex items-center justify-center text-xs font-bold">1</span>
                <div className="flex-1">
                  <strong>Configure le profil auteur (E-E-A-T)</strong>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Bio + credentials + photo. C&apos;est ce que Google recompense le plus en 2026.
                  </p>
                </div>
                <Link href={`${base}/parametres`}>
                  <Button size="sm" variant="outline">
                    <Settings className="h-3 w-3 mr-1.5" />
                    Parametres
                  </Button>
                </Link>
              </li>
              <li className="flex items-start gap-3 p-3 rounded border bg-background">
                <span className="shrink-0 h-6 w-6 rounded-full bg-primary text-primary-foreground flex items-center justify-center text-xs font-bold">2</span>
                <div className="flex-1">
                  <strong>Genere un brief strategique</strong>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Tape ton mot-cle cible, on extrait le top SERP + les vraies questions de ton audience.
                  </p>
                </div>
                <Link href={`${base}/generer`}>
                  <Button size="sm" variant="outline">
                    <Search className="h-3 w-3 mr-1.5" />
                    Brief
                  </Button>
                </Link>
              </li>
              <li className="flex items-start gap-3 p-3 rounded border bg-background">
                <span className="shrink-0 h-6 w-6 rounded-full bg-primary text-primary-foreground flex items-center justify-center text-xs font-bold">3</span>
                <div className="flex-1">
                  <strong>Genere ton premier article</strong>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Claude ecrit en suivant ton brief, en lexique quebecois, avec ta voix.
                  </p>
                </div>
                <Link href={`${base}/generer`}>
                  <Button size="sm">
                    <Sparkles className="h-3 w-3 mr-1.5" />
                    Generer
                  </Button>
                </Link>
              </li>
              <li className="flex items-start gap-3 p-3 rounded border bg-background">
                <span className="shrink-0 h-6 w-6 rounded-full bg-primary text-primary-foreground flex items-center justify-center text-xs font-bold">4</span>
                <div className="flex-1">
                  <strong>Suis tes mots-cles</strong>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Ajoute 5 mots-cles cibles. On snapshot leur position Google chaque jour.
                  </p>
                </div>
                <Link href={`${base}/positions`}>
                  <Button size="sm" variant="outline">
                    <BarChart3 className="h-3 w-3 mr-1.5" />
                    Positions
                  </Button>
                </Link>
              </li>
            </ol>

            <div className="pt-2 text-xs text-muted-foreground flex items-center gap-1">
              <ArrowRight className="h-3 w-3" />
              Une fois ton premier article publie, ce panneau disparait.
            </div>
          </CardContent>
        </Card>
      )}

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatsCard title="Total articles" value={stats?.total_posts ?? 0} icon={FileText} />
        <StatsCard title="Total vues" value={stats?.total_views ?? 0} icon={Eye} />
        <StatsCard title="Brouillons" value={stats?.drafts ?? 0} icon={PenLine} />
        <StatsCard title="Planifies" value={stats?.scheduled ?? 0} icon={Clock} />
      </div>

      {siteId && <HreflangCard siteId={siteId} />}

      {stats?.recent_posts && stats.recent_posts.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Articles recents</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {stats.recent_posts.map((post) => (
                <div
                  key={post.slug}
                  className="flex items-center justify-between py-2 border-b last:border-0"
                >
                  <div>
                    <p className="font-medium text-sm">{post.title}</p>
                    <p className="text-xs text-muted-foreground">
                      {new Date(post.created_at).toLocaleDateString("fr-CA")}
                    </p>
                  </div>
                  <div className="flex items-center gap-4 text-sm text-muted-foreground">
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
