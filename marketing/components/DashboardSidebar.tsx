"use client";

import Link from "next/link";
import { usePathname, useParams, useRouter } from "next/navigation";
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
import { useAuth } from "@/context/AuthContext";
import { useQuery } from "@tanstack/react-query";
import { authFetch } from "@/lib/api-client";
import { GridarMark } from "@/components/GridarMark";
import {
  LayoutDashboard,
  Gauge,
  FileText,
  Sparkles,
  ImageIcon,
  Settings,
  ArrowLeft,
  LogOut,
  TrendingUp,
  TrendingDown,
  Network,
  Link2,
  Move,
  Unlink2,
  Calendar,
  Coins,
} from "lucide-react";

/**
 * Per-site dashboard sidebar. Mirrors the Vite version but uses Next.js
 * routing primitives (next/link, usePathname, useParams) instead of
 * react-router-dom. Strings are hardcoded FR-CA for now - i18n will land
 * later in the migration (the marketing surface is already FR-only too).
 */
export function DashboardSidebar() {
  const pathname = usePathname() || "";
  const router = useRouter();
  const params = useParams<{ siteId: string }>();
  const siteId = params?.siteId;
  const { logout } = useAuth();

  const base = `/dashboard/${siteId}`;

  const navItems = [
    { label: "Tableau de bord", icon: LayoutDashboard, href: base },
    { label: "Audit du site", icon: Gauge, href: `${base}/audit-site` },
    { label: "Articles", icon: FileText, href: `${base}/articles` },
    { label: "Générer un article", icon: Sparkles, href: `${base}/generer` },
    { label: "Audit global SEO", icon: TrendingUp, href: `${base}/audit-global` },
    { label: "Suivi des positions", icon: TrendingUp, href: `${base}/positions` },
    { label: "Détection de déclin", icon: TrendingDown, href: `${base}/decay` },
    { label: "Topic clusters", icon: Network, href: `${base}/clusters` },
    { label: "Maillage interne", icon: Link2, href: `${base}/link-graph` },
    { label: "Redirections 301", icon: Move, href: `${base}/redirects` },
    { label: "Liens cassés", icon: Unlink2, href: `${base}/broken-links` },
    { label: "Rapport hebdo", icon: Calendar, href: `${base}/digest` },
    { label: "Images", icon: ImageIcon, href: `${base}/images` },
    { label: "Paramètres", icon: Settings, href: `${base}/parametres` },
  ];

  const handleLogout = () => {
    logout();
    router.push("/login");
  };

  return (
    <Sidebar>
      <SidebarHeader className="p-4">
        <div className="flex items-center gap-2">
          <GridarMark className="h-6 w-6 text-primary" />
          <div className="min-w-0">
            <p className="font-semibold text-sm truncate">Gridar</p>
            <p className="text-xs text-muted-foreground truncate">
              Site #{siteId}
            </p>
          </div>
        </div>
      </SidebarHeader>

      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Navigation</SidebarGroupLabel>
          <SidebarGroupContent>
            <SidebarMenu>
              {navItems.map((item) => (
                <SidebarMenuItem key={item.href}>
                  <SidebarMenuButton
                    asChild
                    isActive={
                      item.href === base
                        ? pathname === base
                        : pathname.startsWith(item.href)
                    }
                  >
                    <Link href={item.href}>
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
        <QuotaIndicator />
        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton asChild>
              <Link href="/sites">
                <ArrowLeft className="h-4 w-4" />
                <span>Changer de site</span>
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
  );
}

function QuotaIndicator() {
  const router = useRouter();
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
      onClick={() => router.push("/billing")}
      className="mx-2 mb-2 rounded-lg border border-border/50 hover:border-border bg-muted/30 p-2.5 text-left transition-colors group"
      title="Voir mon plan et mes credits"
    >
      <div className="flex items-center justify-between text-[11px] mb-1.5">
        <span className="text-muted-foreground uppercase tracking-wider font-mono">
          {data.plan}
        </span>
        <span
          className={`tabular-nums font-mono font-semibold ${
            danger ? "text-destructive" : warning ? "text-amber-500" : "text-foreground"
          }`}
        >
          {limit === null ? `${used} ce mois` : `${used} / ${limit}`}
        </span>
      </div>
      {limit !== null && (
        <div className="h-1 rounded-full bg-muted overflow-hidden mb-1.5">
          <div
            className={`h-full transition-all ${
              danger ? "bg-destructive" : warning ? "bg-amber-500" : "bg-primary"
            }`}
            style={{ width: `${pct}%` }}
          />
        </div>
      )}
      <div className="flex items-center gap-1 text-[11px] text-muted-foreground">
        <Coins className="h-3 w-3" />
        <span className="tabular-nums">
          {credits} credit{credits !== 1 ? "s" : ""}
        </span>
        <span className="ml-auto opacity-0 group-hover:opacity-100 transition-opacity text-primary">
          gerer
        </span>
      </div>
    </button>
  );
}
