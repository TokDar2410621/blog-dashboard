import type { Metadata } from "next";
import { Suspense } from "react";
import { CompetitorGapFinder } from "@/components/tools/CompetitorGapFinder";

export const metadata: Metadata = {
  title: "Competitor Gap Finder - Mots-cles manques - Gridar",
  description:
    "Decouvre les mots-cles sur lesquels tes concurrents rankent mais pas toi. Identifie tes opportunites SEO manquees.",
  alternates: { canonical: "/tools/competitor-gap" },
  openGraph: {
    title: "Competitor Gap Finder - Gridar",
    description:
      "Tes concurrents gagnent sur des mots-cles ou tu es absent. Trouve lesquels gratuitement.",
    url: "https://www.gridar.app/tools/competitor-gap",
    type: "website",
  },
};

export default function CompetitorGapPage() {
  return (
    <Suspense fallback={null}>
      <CompetitorGapFinder />
    </Suspense>
  );
}
