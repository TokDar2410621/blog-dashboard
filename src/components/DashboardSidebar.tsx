import { Link, useLocation, useParams, useNavigate } from "react-router-dom";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarSeparator,
} from "@/components/ui/sidebar";
import { useAuth } from "@/hooks/useAuth";
import { useTranslation } from "react-i18next";
import {
  LayoutDashboard,
  FileText,
  Sparkles,
  Image,
  Settings,
  ArrowLeft,
  LogOut,
  Newspaper,
  Languages,
  TrendingUp,
} from "lucide-react";

export function DashboardSidebar() {
  const location = useLocation();
  const navigate = useNavigate();
  const { siteId } = useParams<{ siteId: string }>();
  const { logout } = useAuth();
  const { t, i18n } = useTranslation();

  const base = `/dashboard/${siteId}`;

  const navItems = [
    { label: t("sidebar.dashboard"), icon: LayoutDashboard, href: base },
    { label: t("sidebar.articles"), icon: FileText, href: `${base}/articles` },
    { label: t("sidebar.generate"), icon: Sparkles, href: `${base}/generer` },
    { label: t("sidebar.bulkAudit"), icon: TrendingUp, href: `${base}/audit-global` },
    { label: t("sidebar.images"), icon: Image, href: `${base}/images` },
    { label: t("sidebar.settings"), icon: Settings, href: `${base}/parametres` },
  ];

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  const toggleLang = () => {
    i18n.changeLanguage(i18n.language === "fr" ? "en" : "fr");
  };

  return (
    <Sidebar>
      <SidebarHeader className="p-4">
        <div className="flex items-center gap-2">
          <Newspaper className="h-6 w-6 text-primary" />
          <div className="min-w-0">
            <p className="font-semibold text-sm truncate">{t("sidebar.appName")}</p>
            <p className="text-xs text-muted-foreground truncate">
              {t("sidebar.siteLabel", { id: siteId })}
            </p>
          </div>
        </div>
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>{t("sidebar.nav")}</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {navItems.map((item) => (
                <SidebarMenuItem key={item.href}>
                  <SidebarMenuButton
                    asChild
                    isActive={
                      item.href === base
                        ? location.pathname === base
                        : location.pathname.startsWith(item.href)
                    }
                  >
                    <Link to={item.href}>
                      <item.icon className="h-4 w-4" />
                      <span>{item.label}</span>
                    </Link>
                  </SidebarMenuButton>
                </SidebarMenuItem>
              ))}
            </SidebarMenu>
          </SidebarGroupContent>
        </SidebarGroup>
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
              <Link to="/">
                <ArrowLeft className="h-4 w-4" />
                <span>{t("sidebar.switchSite")}</span>
              </Link>
            </SidebarMenuButton>
          </SidebarMenuItem>
          <SidebarMenuItem>
            <SidebarMenuButton onClick={handleLogout}>
              <LogOut className="h-4 w-4" />
              <span>{t("sidebar.logout")}</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
    </Sidebar>
  );
}
