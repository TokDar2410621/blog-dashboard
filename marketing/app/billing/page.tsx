import type { Metadata } from "next";
import { Suspense } from "react";
import { AuthGuard } from "@/components/AuthGuard";
import { BillingPage } from "@/components/BillingPage";

export const metadata: Metadata = {
  title: "Abonnement - Gridar",
  description: "Gère ton plan, tes paiements et tes factures.",
  robots: { index: false, follow: false },
};

// BillingPage reads ?status & ?credits (Stripe return) via useSearchParams -
// Next.js requires a Suspense boundary around that for static prerendering.
export default function Billing() {
  return (
    <AuthGuard>
      <Suspense fallback={null}>
        <BillingPage />
      </Suspense>
    </AuthGuard>
  );
}
