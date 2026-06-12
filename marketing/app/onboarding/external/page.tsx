import type { Metadata } from "next";
import { AuthGuard } from "@/components/AuthGuard";
import OnboardingExternalPage from "@/components/OnboardingExternalPage";

export const metadata: Metadata = {
  title: "Onboarding mode externe",
  robots: { index: false },
};

export default function Page() {
  return (
    <AuthGuard>
      <OnboardingExternalPage />
    </AuthGuard>
  );
}
