"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarInset,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarProvider,
  SidebarSeparator,
  SidebarTrigger,
} from "@/components/ui/sidebar";
import { GridarMark } from "@/components/GridarMark";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { AuthGuard } from "@/components/AuthGuard";
import { useAuth } from "@/context/AuthContext";
import { useSites } from "@/hooks/useDashboard";
import { Button } from "@/components/ui/button";
import { MultiSiteHealthTable } from "@/components/dashboard/MultiSiteHealthTable";
import {
  LayoutDashboard,
  Globe,
  Plus,
  ArrowLeft,
  LogOut,
  Inbox,
} from "lucide-react";

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
function MultiSiteOverview() {
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
          <Link href="/sites">
            <Plus className="h-4 w-4 mr-1.5" />
            Ajouter un site
          </Link>
        </Button>
      </header>

      {!isLoading && sites.length === 0 ? (
        <div className="rounded-lg border border-dashed border-border/60 bg-card/40 p-6 md:p-10 text-center">
          <div className="mx-auto h-12 w-12 rounded-full bg-muted/40 flex items-center justify-center mb-4">
            <Inbox className="h-6 w-6 text-muted-foreground" />
          </div>
          <h2 className="text-lg font-semibold">Aucun site connecte</h2>
          <p className="text-sm text-muted-foreground mt-1 max-w-sm mx-auto">
            Connecte ton premier site pour activer la vue multi-sites et voir
            ton score SEO consolide.
          </p>
          <Button asChild className="mt-5">
            <Link href="/sites">
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
            <Link href="/sites">
              <Plus className="h-4 w-4 mr-1.5" />
              Ajouter un site
            </Link>
          </Button>
        </div>
      )}
    </div>
  );
}

/**
 * Shell for `/dashboard/overview` - mirrors the structure of
 * the per-site dashboard layout (SidebarProvider + SidebarInset + mobile
 * topbar) so the multi-site overview page lives in the same chrome as the
 * per-site dashboard.
 *
 * The sidebar here is multi-site-aware: instead of per-site nav items (which
 * require a `:siteId` param), it lists the user's connected sites as quick
 * links so they can jump straight into any of them.
 */
function MultiSiteShell() {
  const router = useRouter();
  const { logout } = useAuth();
  const pathname = usePathname();
  const { data: sites = [] } = useSites();

  const handleLogout = () => {
    logout();
    router.push("/login");
  };

  const isOverview = pathname === "/dashboard/overview";

  return (
    <SidebarProvider>
      <Sidebar>
        <SidebarHeader className="p-4">
          <div className="flex items-center gap-2">
            <GridarMark className="h-6 w-6 text-primary" />
            <div className="min-w-0">
              <p className="font-semibold text-sm truncate">Gridar</p>
              <p className="text-xs text-muted-foreground truncate">
                Vue multi-sites
              </p>
            </div>
          </div>
        </SidebarHeader>

        <SidebarContent>
          <SidebarGroup>
            <SidebarGroupLabel>Navigation</SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                <SidebarMenuItem>
                  <SidebarMenuButton asChild isActive={isOverview}>
                    <Link href="/dashboard/overview">
                      <LayoutDashboard className="h-4 w-4" />
                      <span>Sante des sites</span>
                    </Link>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>

          {sites.length > 0 && (
            <SidebarGroup>
              <SidebarGroupLabel>Mes sites</SidebarGroupLabel>
              <SidebarGroupContent>
                <SidebarMenu>
                  {sites.map((site) => (
                    <SidebarMenuItem key={site.id}>
                      <SidebarMenuButton asChild>
                        <Link href={`/dashboard/${site.id}`}>
                          <Globe className="h-4 w-4" />
                          <span className="truncate">{site.name}</span>
                        </Link>
                      </SidebarMenuButton>
                    </SidebarMenuItem>
                  ))}
                  <SidebarMenuItem>
                    <SidebarMenuButton asChild>
                      <Link href="/sites">
                        <Plus className="h-4 w-4" />
                        <span>Ajouter un site</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                </SidebarMenu>
              </SidebarGroupContent>
            </SidebarGroup>
          )}
        </SidebarContent>

        <SidebarFooter>
          <SidebarSeparator />
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarMenuButton asChild>
                <Link href="/sites">
                  <ArrowLeft className="h-4 w-4" />
                  <span>Retour aux sites</span>
                </Link>
              </SidebarMenuButton>
            </SidebarMenuItem>
            <SidebarMenuItem>
              <SidebarMenuButton onClick={handleLogout}>
                <LogOut className="h-4 w-4" />
                <span>Deconnexion</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
          </SidebarMenu>
        </SidebarFooter>
      </Sidebar>

      <SidebarInset>
        <header className="md:hidden sticky top-0 z-30 flex h-12 items-center gap-2 border-b border-border/50 bg-background/95 backdrop-blur px-3">
          <SidebarTrigger />
          <GridarMark className="h-4 w-4 text-primary" />
          <span className="font-semibold text-sm">Gridar</span>
        </header>
        <div className="p-4 md:p-6">
          <ErrorBoundary>
            <MultiSiteOverview />
          </ErrorBoundary>
        </div>
      </SidebarInset>
    </SidebarProvider>
  );
}

export default function MultiSiteOverviewPage() {
  return (
    <AuthGuard>
      <MultiSiteShell />
    </AuthGuard>
  );
}
