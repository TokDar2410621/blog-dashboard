import { Suspense } from "react";
import { PostEditorPage } from "@/components/dashboard/PostEditorPage";

/**
 * /dashboard/[siteId]/articles/[slug] - edit an existing article.
 *
 * Thin server wrapper around the client PostEditorPage. The Suspense boundary
 * is required because PostEditorPage calls useSearchParams(). The slug param
 * is decoded so accented slugs match what react-router gave the SPA.
 */
export default async function EditArticlePage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  return (
    <Suspense fallback={null}>
      <PostEditorPage slug={decodeURIComponent(slug)} />
    </Suspense>
  );
}
