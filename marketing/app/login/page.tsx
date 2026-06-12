import type { Metadata } from "next";
import { Suspense } from "react";
import { LoginPage } from "@/components/pages/LoginPage";

export const metadata: Metadata = {
  title: "Connexion - Gridar",
  description:
    "Connecte-toi à Gridar : articles, audit SEO, suivi Google et génération IA pour ton blog.",
  alternates: { canonical: "/login" },
  robots: { index: false, follow: false },
};

// LoginPage reads useSearchParams() (?next= set by AuthGuard), which Next.js
// requires to be wrapped in <Suspense> for static pre-rendering.
export default function Login() {
  return (
    <Suspense fallback={null}>
      <LoginPage />
    </Suspense>
  );
}
