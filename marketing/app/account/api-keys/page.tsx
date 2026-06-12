import type { Metadata } from "next";
import { AuthGuard } from "@/components/AuthGuard";
import { ApiKeysPage } from "@/components/ApiKeysPage";

export const metadata: Metadata = {
  title: "Clés API - Gridar",
  description:
    "Crée et révoque des tokens API Gridar pour n8n, Zapier, Make ou tes propres scripts.",
  robots: { index: false, follow: false },
};

// No useSearchParams in ApiKeysPage, so no Suspense boundary needed.
export default function AccountApiKeys() {
  return (
    <AuthGuard>
      <ApiKeysPage />
    </AuthGuard>
  );
}
