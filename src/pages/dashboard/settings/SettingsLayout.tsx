import { NavLink, Outlet, useParams } from "react-router-dom";
import { Loader2, Settings, Palette, User as UserIcon, Rocket, Languages, BarChart3, Brain, Plug, Sparkles } from "lucide-react";
import { PageBreadcrumb } from "@/components/PageBreadcrumb";
import { Button } from "@/components/ui/button";
import { Save } from "lucide-react";
import { useTranslation } from "react-i18next";
import { SettingsProvider } from "./SettingsContext";
import { useSettings } from "./useSettings";

type NavItem = {
  to: string;
  label: string;
  icon: typeof Settings;
};

function SettingsSidebar() {
  const { siteId } = useParams<{ siteId: string }>();
  const base = `/dashboard/${siteId}/parametres`;

  const items: NavItem[] = [
    { to: `${base}/general`, label: "General", icon: Settings },
    { to: `${base}/branding`, label: "Branding", icon: Palette },
    { to: `${base}/auteur`, label: "Auteur (EEAT)", icon: UserIcon },
    { to: `${base}/cta`, label: "Call-to-action", icon: Rocket },
    { to: `${base}/langues`, label: "Langues", icon: Languages },
    { to: `${base}/gsc`, label: "Search Console", icon: BarChart3 },
    { to: `${base}/memoire`, label: "Memoire (RAG)", icon: Brain },
    { to: `${base}/autopilote`, label: "Autopilote", icon: Sparkles },
    { to: `${base}/integrations`, label: "Integrations", icon: Plug },
  ];

  return (
    <nav className="w-full md:w-[220px] shrink-0 space-y-1">
      {items.map((it) => {
        const Icon = it.icon;
        return (
          <NavLink
            key={it.to}
            to={it.to}
            end
            className={({ isActive }) =>
              [
                "flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors",
                isActive
                  ? "bg-emerald-400/10 text-emerald-400 font-medium border border-emerald-400/30"
                  : "text-muted-foreground hover:text-foreground hover:bg-muted/50",
              ].join(" ")
            }
          >
            <Icon className="h-4 w-4 shrink-0" />
            <span className="truncate">{it.label}</span>
          </NavLink>
        );
      })}
    </nav>
  );
}

function SaveBar() {
  const { t } = useTranslation();
  const { updateSite, handleSave } = useSettings();
  return (
    <Button
      size="lg"
      onClick={handleSave}
      disabled={updateSite.isPending}
      className="w-full sm:w-auto"
    >
      {updateSite.isPending ? (
        <>
          <Loader2 className="h-4 w-4 mr-2 animate-spin" />
          {t("settings.saving")}
        </>
      ) : (
        <>
          <Save className="h-4 w-4 mr-2" />
          {t("settings.save")}
        </>
      )}
    </Button>
  );
}

function SettingsLayoutInner() {
  const { t } = useTranslation();
  const { isLoading } = useSettings();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-6xl">
      <PageBreadcrumb trail={[{ label: "Parametres" }]} />
      <div>
        <h1 className="text-2xl font-bold">{t("settings.title")}</h1>
        <p className="text-muted-foreground">{t("settings.subtitle")}</p>
      </div>

      <div className="flex flex-col md:flex-row gap-6">
        <SettingsSidebar />
        <div className="flex-1 min-w-0 space-y-6">
          <Outlet />
          <SaveBar />
        </div>
      </div>
    </div>
  );
}

export default function SettingsLayout() {
  return (
    <SettingsProvider>
      <SettingsLayoutInner />
    </SettingsProvider>
  );
}
