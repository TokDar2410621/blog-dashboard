import type { Metadata } from "next";
import { Suspense } from "react";
import { AiCitationChecker } from "@/components/tools/AiCitationChecker";

export const metadata: Metadata = {
  title: "AI Citation Checker - Es-tu cite par l'IA? - Gridar",
  description:
    "Decouvre si les moteurs IA utilisent ton site comme source pour leurs reponses. Analyse des citations.",
  alternates: { canonical: "/tools/ai-citation-checker" },
  openGraph: {
    title: "AI Citation Checker - Gridar",
    description:
      "Est-ce que les moteurs IA te citent? Decouvre quelles pages sont utilisees comme sources.",
    url: "https://www.gridar.app/tools/ai-citation-checker",
    type: "website",
  },
};

export default function AiCitationCheckerPage() {
  return (
    <Suspense fallback={null}>
      <AiCitationChecker />
    </Suspense>
  );
}
