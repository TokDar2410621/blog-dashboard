import { ContentDecayPage } from "@/components/dashboard/ContentDecayPage";

/**
 * /dashboard/[siteId]/decay - thin server page. All logic lives in the
 * "use client" ContentDecayPage component (no useSearchParams, so no
 * Suspense boundary is required).
 */
export default function DecayPage() {
  return <ContentDecayPage />;
}
