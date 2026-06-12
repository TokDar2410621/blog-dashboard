import type { ReactNode } from "react";
import SettingsLayoutClient from "@/components/dashboard/settings/SettingsLayoutClient";

/**
 * Settings shell for /dashboard/[siteId]/parametres/*.
 * Mirrors the SPA's SettingsLayout: SettingsProvider (shared form state +
 * centralised save) + settings sidebar nav + SaveBar under each sub-page.
 */
export default function ParametresLayout({ children }: { children: ReactNode }) {
  return <SettingsLayoutClient>{children}</SettingsLayoutClient>;
}
