import type { Metadata } from "next";
import { Suspense } from "react";
import { CompetitorCompare } from "@/components/tools/CompetitorCompare";

export const metadata: Metadata = {
  title: "Comparaison de concurrents SEO - Gridar",
  description:
    "Compare ton site a ton principal concurrent sur 20+ dimensions SEO. Decouvre comment les depasser.",
  alternates: { canonical: "/tools/competitor-compare" },
  openGraph: {
    title: "Comparaison de concurrents SEO - Gridar",
    description:
      "Qui a le meilleur SEO? Compare ton site a ton concurrent et obtiens un plan d'action.",
    url: "https://www.gridar.app/tools/competitor-compare",
    type: "website",
  },
};

export default function CompetitorComparePage() {
  return (
    <Suspense fallback={null}>
      <CompetitorCompare />
    </Suspense>
  );
}
