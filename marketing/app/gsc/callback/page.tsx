import type { Metadata } from "next";
import { Suspense } from "react";
import { AuthGuard } from "@/components/AuthGuard";
import { GSCCallbackPage } from "@/components/GSCCallbackPage";

export const metadata: Metadata = {
  title: "Connexion GSC - Gridar",
  robots: { index: false, follow: false },
};

// Mirrors the SPA route: /gsc/callback is wrapped in AuthGuard (the backend
// call needs the user's session). GSCCallbackPage reads ?code & ?state &
// ?error via useSearchParams - Next.js requires a Suspense boundary around
// that for static prerendering.
export default function GSCCallback() {
  return (
    <AuthGuard>
      <Suspense fallback={null}>
        <GSCCallbackPage />
      </Suspense>
    </AuthGuard>
  );
}
