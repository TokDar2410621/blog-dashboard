import { Suspense } from "react";
import { PostEditorPage } from "@/components/dashboard/PostEditorPage";

/**
 * /dashboard/[siteId]/articles/nouveau - create a new article.
 *
 * Thin server wrapper around the client PostEditorPage. The Suspense boundary
 * is required because PostEditorPage calls useSearchParams() (template
 * pre-fill via ?tpl_type=&tpl_id=).
 */
export default function NewArticlePage() {
  return (
    <Suspense fallback={null}>
      <PostEditorPage />
    </Suspense>
  );
}
