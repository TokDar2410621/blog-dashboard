import { Link, useLocation, useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
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
import { useAuth } from "@/hooks/useAuth";
import { useSites } from "@/hooks/useDashboard";
import {
  LayoutDashboard,
  Globe,
  Plus,
  ArrowLeft,
  LogOut,
  Languages,
} from "lucide-react";
import MultiSiteOverview from "./MultiSiteOverview";

/**
 * Shell for `/dashboard/overview` - mirrors the structure of
 * `DashboardLayout` (SidebarProvider + SidebarInset + mobile topbar) so the
 * multi-site overview page lives in the same chrome as the per-site dashboard.
 *
 * The sidebar here is multi-site-aware: instead of per-site nav items (which
 * require a `:siteId` param), it lists the user's connected sites as quick
 * links so they can jump straight into any of them.
 */
export default function MultiSiteShell() {
  const { i18n } = useTranslation();
  const navigate = useNavigate();
  const { logout } = useAuth();
  const location = useLocation();
  const { data: sites = [] } = useSites();

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  const toggleLang = () => {
    i18n.changeLanguage(i18n.language === "fr" ? "en" : "fr");
  };

  const isOverview = location.pathname === "/dashboard/overview";

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
                    <Link to="/dashboard/overview">
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
                        <Link to={`/dashboard/${site.id}`}>
                          <Globe className="h-4 w-4" />
                          <span className="truncate">{site.name}</span>
                        </Link>
                      </SidebarMenuButton>
                    </SidebarMenuItem>
                  ))}
                  <SidebarMenuItem>
                    <SidebarMenuButton asChild>
                      <Link to="/sites">
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
              <SidebarMenuButton onClick={toggleLang}>
                <Languages className="h-4 w-4" />
                <span>{i18n.language === "fr" ? "English" : "Francais"}</span>
              </SidebarMenuButton>
            </SidebarMenuItem>
            <SidebarMenuItem>
              <SidebarMenuButton asChild>
                <Link to="/sites">
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
