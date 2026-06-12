import type { Metadata } from "next";
import { Suspense } from "react";
import { ResetPasswordPage } from "@/components/ResetPasswordPage";

export const metadata: Metadata = {
  title: "Réinitialiser le mot de passe - Gridar",
  description: "Réinitialisation du mot de passe de ton compte Gridar.",
  robots: { index: false, follow: false },
};

// ResetPasswordPage reads ?uid & ?token via useSearchParams - Next.js requires
// a Suspense boundary around that for static prerendering.
export default function ResetPassword() {
  return (
    <Suspense fallback={null}>
      <ResetPasswordPage />
    </Suspense>
  );
}
