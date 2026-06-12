import type { Metadata } from "next";
import { SiteSelector } from "@/components/SiteSelector";

export const metadata: Metadata = {
  title: "Gridar",
  robots: { index: false, follow: false },
};

/**
 * /sites - authenticated site selector. Thin server wrapper around the
 * "use client" SiteSelector component (which itself mounts <AuthGuard>).
 * No useSearchParams in the subtree, so no <Suspense> boundary is needed.
 */
export default function SitesPage() {
  return <SiteSelector />;
}
