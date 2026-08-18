import type { Metadata } from "next";
import { Suspense } from "react";
import { CanIRankChecker } from "@/components/tools/CanIRankChecker";

export const metadata: Metadata = {
  title: "Can I Rank? - Analyse de difficulte de mot-cle - Gridar",
  description:
    "Decouvre si TON site peut ranker sur un mot-cle specifique. Analyse detaillee de difficulte personnalisee.",
  alternates: { canonical: "/tools/keyword-difficulty" },
  openGraph: {
    title: "Can I Rank? - Analyse de difficulte SEO - Gridar",
    description:
      "Est-ce que ton site peut atteindre la premiere page pour ce mot-cle? Fais le test gratuitement.",
    url: "https://www.gridar.app/tools/keyword-difficulty",
    type: "website",
  },
};

export default function KeywordDifficultyPage() {
  return (
    <Suspense fallback={null}>
      <CanIRankChecker />
    </Suspense>
  );
}
