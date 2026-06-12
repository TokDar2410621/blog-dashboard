import type { Metadata } from "next";
import { Suspense } from "react";
import { AuthCallbackPage } from "@/components/AuthCallbackPage";

export const metadata: Metadata = {
  title: "Connexion en cours - Gridar",
  robots: { index: false, follow: false },
};

// Prerender the two real providers so /auth/google/callback and
// /auth/github/callback resolve as filesystem routes (they must win over the
// afterFiles SPA-proxy rewrites in next.config.ts). Unknown providers still
// fall through to the dynamic route, which renders the SPA's exact
// "Provider OAuth inconnu." error state.
export function generateStaticParams() {
  return [{ provider: "google" }, { provider: "github" }];
}

// AuthCallbackPage reads ?code & ?state & ?error via useSearchParams -
// Next.js requires a Suspense boundary around that for static prerendering.
export default function AuthCallback() {
  return (
    <Suspense fallback={null}>
      <AuthCallbackPage />
    </Suspense>
  );
}
