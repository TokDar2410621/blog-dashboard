import { Link } from "react-router-dom";
import { useSites } from "@/hooks/useDashboard";
import { Button } from "@/components/ui/button";
import { MultiSiteHealthTable } from "@/components/dashboard/MultiSiteHealthTable";
import { Plus, LayoutDashboard, Inbox } from "lucide-react";

/**
 * Multi-site health summary page.
 *
 * Lives at `/dashboard/overview` (no siteId in the URL) and is reachable from
 * the site selector. For agencies / users with multiple connected sites it
 * provides a single dashboard pane with one row per site:
 *
 *   - composite SEO Score (`/sites/<id>/seo-score/`, already shipped)
 *   - AI Visibility (mock 0-100, V1 "NEW" badge)
 *   - organic traffic (mock for V1)
 *   - decay count (real, via `/sites/<id>/content-decay/?days=30`)
 *   - alerts count (mock for V1)
 *
 * Renders inside the same DashboardShell (`SidebarProvider` + `SidebarInset`)
 * as the per-site routes so users keep the sidebar + topbar context.
 */
export default function MultiSiteOverview() {
  const { data: sites = [], isLoading } = useSites();

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-xs text-muted-foreground font-mono uppercase tracking-wider">
            <LayoutDashboard className="h-3.5 w-3.5" />
            Vue multi-sites
          </div>
          <h1 className="text-2xl md:text-3xl font-bold tracking-tight mt-1">
            Sante de tous mes sites
          </h1>
          <p className="text-sm text-muted-foreground mt-1 max-w-xl">
            Un aperçu consolide de chaque site connecte: score SEO composite,
            visibilite IA, trafic organique et alertes. Clique sur "Ouvrir" pour
            plonger dans un site specifique.
          </p>
        </div>
        <Button asChild size="sm">
          <Link to="/sites">
            <Plus className="h-4 w-4 mr-1.5" />
            Ajouter un site
          </Link>
        </Button>
      </header>

      {!isLoading && sites.length === 0 ? (
        <div className="rounded-lg border border-dashed border-border/60 bg-card/40 p-10 text-center">
          <div className="mx-auto h-12 w-12 rounded-full bg-muted/40 flex items-center justify-center mb-4">
            <Inbox className="h-6 w-6 text-muted-foreground" />
          </div>
          <h2 className="text-lg font-semibold">Aucun site connecte</h2>
          <p className="text-sm text-muted-foreground mt-1 max-w-sm mx-auto">
            Connecte ton premier site pour activer la vue multi-sites et voir
            ton score SEO consolide.
          </p>
          <Button asChild className="mt-5">
            <Link to="/sites">
              <Plus className="h-4 w-4 mr-1.5" />
              Ajouter un site
            </Link>
          </Button>
        </div>
      ) : (
        <MultiSiteHealthTable sites={sites} isLoading={isLoading} />
      )}

      {sites.length > 0 && (
        <div className="flex justify-center pt-2">
          <Button asChild variant="outline" size="sm">
            <Link to="/sites">
              <Plus className="h-4 w-4 mr-1.5" />
              Ajouter un site
            </Link>
          </Button>
        </div>
      )}
    </div>
  );
}
