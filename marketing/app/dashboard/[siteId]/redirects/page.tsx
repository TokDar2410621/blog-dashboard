import { RedirectsPage } from "@/components/dashboard/RedirectsPage";

/**
 * /dashboard/[siteId]/redirects - thin server page. All logic lives in the
 * "use client" RedirectsPage component (no useSearchParams, so no Suspense
 * boundary is required).
 */
export default function RedirectsRoutePage() {
  return <RedirectsPage />;
}
