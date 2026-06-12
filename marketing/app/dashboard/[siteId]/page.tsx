import type { Metadata } from "next";
import { OverviewPage } from "@/components/dashboard/OverviewPage";

export const metadata: Metadata = {
  title: "Tableau de bord | Gridar",
};

/**
 * /dashboard/[siteId] - per-site overview (stats, onboarding checklist,
 * proof of value, hreflang health, recommendations, recent posts).
 * Thin server wrapper: all logic lives in the client component, which reads
 * siteId via useParams(). Renders inside the [siteId] layout shell
 * (AuthGuard + sidebar), so no extra chrome here.
 */
export default function Page() {
  return <OverviewPage />;
}
