import type { Metadata } from "next";
import { Suspense } from "react";
import { UnsubscribePage } from "@/components/UnsubscribePage";

export const metadata: Metadata = {
  title: "Se désabonner - Gridar",
  description: "Désabonnement des courriels Gridar.",
  robots: { index: false, follow: false },
};

// UnsubscribePage reads ?email & ?t via useSearchParams - Next.js requires
// a Suspense boundary around that for static prerendering.
export default function Unsubscribe() {
  return (
    <Suspense fallback={null}>
      <UnsubscribePage />
    </Suspense>
  );
}
