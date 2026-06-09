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
import { useQuery } from "@tanstack/react-query";
import { authFetch } from "@/lib/api-client";
import { GridarMark } from "@/components/GridarMark";
import {
  LayoutDashboard,
  Gauge,
  FileText,
  Sparkles,
  Image,
  Settings,
  ArrowLeft,
  LogOut,
  Languages,
  TrendingUp,
  TrendingDown,
  Network,
  Link2,
  Move,
  Unlink2,
  Calendar,
  Coins,
  Search,
  Brain,
  Lightbulb,
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
    { label: t("sidebar.siteAudit") || "Audit du site", icon: Gauge, href: `${base}/audit-site` },
    { label: t("sidebar.opportunities") || "Opportunités SEO", icon: Lightbulb, href: `${base}/opportunites` },
    { label: t("sidebar.articles"), icon: FileText, href: `${base}/articles` },
    { label: t("sidebar.generate"), icon: Sparkles, href: `${base}/generer` },
    { label: t("sidebar.bulkAudit"), icon: TrendingUp, href: `${base}/audit-global` },
    { label: t("sidebar.positions"), icon: TrendingUp, href: `${base}/positions` },
    { label: t("sidebar.decay"), icon: TrendingDown, href: `${base}/decay` },
    { label: t("sidebar.clusters"), icon: Network, href: `${base}/clusters` },
    { label: t("sidebar.linkGraph"), icon: Link2, href: `${base}/link-graph` },
    { label: t("sidebar.redirects"), icon: Move, href: `${base}/redirects` },
    { label: t("sidebar.brokenLinks"), icon: Unlink2, href: `${base}/broken-links` },
    { label: t("sidebar.digest"), icon: Calendar, href: `${base}/digest` },
    { label: t("sidebar.images"), icon: Image, href: `${base}/images` },
    { label: t("sidebar.settings"), icon: Settings, href: `${base}/parametres` },
  ];

  const insightsItems = [
    {
      label: t("sidebar.serpAnalyzer") || "Analyseur SERP",
      icon: Search,
      href: `${base}/serp-analyzer`,
    },
  ];

  // "AI ERA" - next-gen SEO that targets LLM answers, not Google rankings.
  const aiEraItems: {
    label: string;
    icon: typeof Brain;
    href: string;
    badge?: string;
  }[] = [
    {
      label: t("sidebar.aiVisibility") || "Visibilite IA",
      icon: Brain,
      href: `${base}/ai-visibility`,
      badge: "NEW",
    },
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
          <GridarMark className="h-6 w-6 text-primary" />
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
        <SidebarGroup>
          <SidebarGroupLabel>
            {t("sidebar.insights") || "Insights"}
          </SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {insightsItems.map((item) => (
                <SidebarMenuItem key={item.href}>
                  <SidebarMenuButton
                    asChild
                    isActive={location.pathname.startsWith(item.href)}
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
        <SidebarGroup>
          <SidebarGroupLabel className="flex items-center gap-1.5">
            <span>{t("sidebar.aiEra") || "AI ERA"}</span>
            <span className="inline-block h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
          </SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {aiEraItems.map((item) => (
                <SidebarMenuItem key={item.href}>
                  <SidebarMenuButton
                    asChild
                    isActive={location.pathname.startsWith(item.href)}
                  >
                    <Link to={item.href}>
                      <item.icon className="h-4 w-4" />
                      <span className="flex-1">{item.label}</span>
                      {item.badge && (
                        <span className="ml-auto text-[9px] font-bold uppercase tracking-wider bg-emerald-500/20 text-emerald-300 border border-emerald-500/40 rounded px-1.5 py-0.5">
                          {item.badge}
                        </span>
                      )}
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
        <QuotaIndicator />
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

function QuotaIndicator() {
  const navigate = useNavigate();
  type SubInfo = {
    plan: "free" | "solo" | "pro" | "agency";
    limits: { articles_per_month: number | null };
    usage?: { articles_this_month: number };
    credits?: { balance: number };
  };
  const { data } = useQuery<SubInfo>({
    queryKey: ["billing-me"],
    queryFn: async () => {
      const res = await authFetch("/billing/me/");
      if (!res.ok) throw new Error("billing fetch failed");
      return res.json();
    },
    staleTime: 60_000,
  });
  if (!data) return null;
  const limit = data.limits.articles_per_month;
  const used = data.usage?.articles_this_month ?? 0;
  const credits = data.credits?.balance ?? 0;
  const pct = limit ? Math.min(100, (used / limit) * 100) : 0;
  const exhausted = limit !== null && used >= limit && credits === 0;
  const danger = exhausted;
  const warning = limit !== null && pct >= 80 && !exhausted;

  return (
    <button
      onClick={() => navigate("/billing")}
      className="mx-2 mb-2 rounded-lg border border-border/50 hover:border-border bg-muted/30 p-2.5 text-left transition-colors group"
      title="Voir mon plan et mes crédits"
    >
      <div className="flex items-center justify-between text-[11px] mb-1.5">
        <span className="text-muted-foreground uppercase tracking-wider font-mono">
          {data.plan}
        </span>
        <span
          className={`tabular-nums font-mono font-semibold ${
            danger
              ? "text-destructive"
              : warning
                ? "text-amber-500"
                : "text-foreground"
          }`}
        >
          {limit === null ? `${used} ce mois` : `${used} / ${limit}`}
        </span>
      </div>
      {limit !== null && (
        <div className="h-1 rounded-full bg-muted overflow-hidden mb-1.5">
          <div
            className={`h-full transition-all ${
              danger
                ? "bg-destructive"
                : warning
                  ? "bg-amber-500"
                  : "bg-primary"
            }`}
            style={{ width: `${pct}%` }}
          />
        </div>
      )}
      <div className="flex items-center gap-1 text-[11px] text-muted-foreground">
        <Coins className="h-3 w-3" />
        <span className="tabular-nums">
          {credits} crédit{credits !== 1 ? "s" : ""}
        </span>
        <span className="ml-auto opacity-0 group-hover:opacity-100 transition-opacity text-primary">
          gérer →
        </span>
      </div>
    </button>
  );
}
