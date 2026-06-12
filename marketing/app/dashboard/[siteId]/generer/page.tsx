import type { Metadata } from "next";
import { Suspense } from "react";
import { AIGeneratorPage } from "@/components/dashboard/AIGeneratorPage";

export const metadata: Metadata = {
  title: "Générer un article - Gridar",
  description: "Utilise l'IA pour générer automatiquement un article de blog optimisé SEO.",
  robots: { index: false, follow: false },
};

// AIGeneratorPage reads ?tpl_id, ?title, ?topic, ?keywords and ?autostart via
// useSearchParams - Next.js requires a Suspense boundary around that for
// static prerendering. The AuthGuard + sidebar shell come from the
// [siteId]/layout.tsx, so this page only renders the content.
export default function GenererArticle() {
  return (
    <Suspense fallback={null}>
      <AIGeneratorPage />
    </Suspense>
  );
}
