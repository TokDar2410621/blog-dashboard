import type { Metadata } from "next";
import { SiteAuditPage } from "@/components/dashboard/SiteAuditPage";

export const metadata: Metadata = {
  title: "Audit du site | Gridar",
};

/**
 * /dashboard/[siteId]/audit-site - single-screen SEO audit (composite score
 * hero, strategic opportunities teaser, priority recos, keywords/pagespeed/
 * backlinks/decay cards). Thin server wrapper: the client component reads
 * siteId via useParams(). Renders inside the [siteId] layout shell.
 */
export default function Page() {
  return <SiteAuditPage />;
}
