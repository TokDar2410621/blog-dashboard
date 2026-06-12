import ArticlesPage from "@/components/dashboard/ArticlesPage";

/**
 * Articles list route (/dashboard/[siteId]/articles).
 * Thin server component; the full port of the SPA's PostList lives in the
 * "use client" component. No useSearchParams in the client tree, so no
 * Suspense boundary is required here.
 */
export default function Page() {
  return <ArticlesPage />;
}
