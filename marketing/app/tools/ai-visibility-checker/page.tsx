import type { Metadata } from "next";
import { Suspense } from "react";
import { AiVisibilityChecker } from "@/components/tools/AiVisibilityChecker";

export const metadata: Metadata = {
  title: "AI Visibility Checker - Es-tu visible dans l'IA de Google? - Gridar",
  description:
    "Decouvre si l'IA de Google (Gemini) recommande ton entreprise ou tes concurrents. Score de visibilite IA gratuit.",
  alternates: { canonical: "/tools/ai-visibility-checker" },
  openGraph: {
    title: "AI Visibility Checker - Gridar",
    description:
      "Est-ce que l'IA de Google recommande ton entreprise? Decouvre ton score de visibilite IA gratuitement.",
    url: "https://www.gridar.app/tools/ai-visibility-checker",
    type: "website",
  },
};

export default function AiVisibilityCheckerPage() {
  return (
    <Suspense fallback={null}>
      <AiVisibilityChecker />
    </Suspense>
  );
}
