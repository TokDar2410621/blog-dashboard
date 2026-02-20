import { useDashboardStats } from "@/hooks/useDashboard";
import { StatsCard } from "@/components/StatsCard";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { FileText, Eye, PenLine, Clock, Loader2 } from "lucide-react";
import { getActiveSite } from "@/lib/sites";

export default function Overview() {
  const { data: stats, isLoading, isError } = useDashboardStats();
  const site = getActiveSite();

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
              Impossible de charger les statistiques.
              Verifiez que le backend supporte l'endpoint /api/dashboard/stats/.
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Tableau de bord</h1>
        <p className="text-muted-foreground">
          {site?.name} &mdash; {site?.apiUrl}
        </p>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <StatsCard
          title="Total articles"
          value={stats?.total_posts ?? 0}
          icon={FileText}
        />
        <StatsCard
          title="Total vues"
          value={stats?.total_views ?? 0}
          icon={Eye}
        />
        <StatsCard
          title="Brouillons"
          value={stats?.drafts ?? 0}
          icon={PenLine}
        />
        <StatsCard
          title="Planifies"
          value={stats?.scheduled ?? 0}
          icon={Clock}
        />
      </div>

      {/* Recent Posts */}
      {stats?.recent_posts && stats.recent_posts.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Articles recents</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {stats.recent_posts.map(
                (post: {
                  slug: string;
                  title: string;
                  status: string;
                  view_count: number;
                  created_at: string;
                }) => (
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
                )
              )}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
