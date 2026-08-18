import type { Metadata } from "next";
import { Suspense } from "react";
import { SeoRoiCalculator } from "@/components/tools/SeoRoiCalculator";

export const metadata: Metadata = {
  title: "Calculateur ROI SEO - Gridar",
  description:
    "Traduis ton potentiel SEO en visiteurs, leads, clients et revenus. Simule 3 scenarios d'investissement.",
  alternates: { canonical: "/tools/seo-roi-calculator" },
  openGraph: {
    title: "Calculateur ROI SEO - Gridar",
    description:
      "Combien peut te rapporter le SEO? Calcule ton ROI et point de rentabilite en quelques secondes.",
    url: "https://www.gridar.app/tools/seo-roi-calculator",
    type: "website",
  },
};

export default function SeoRoiCalculatorPage() {
  return (
    <Suspense fallback={null}>
      <SeoRoiCalculator />
    </Suspense>
  );
}
