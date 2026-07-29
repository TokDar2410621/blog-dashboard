import type { Metadata } from "next";
import { Suspense } from "react";
import { PublicAuditPage } from "@/components/PublicAuditPage";

export const metadata: Metadata = {
  title: "Audit SEO gratuit de ton site - Gridar",
  description:
    "Audit SEO complet de ton site en 30 secondes : score composite, top mots-cles, vitesse mobile, recommandations. Sans inscription.",
  alternates: { canonical: "/audit" },
  openGraph: {
    title: "Audit SEO gratuit - 30 secondes",
    description: "Entre ton domaine, recois ton score SEO + top mots-cles + recos. Sans inscription.",
    url: "https://www.gridar.app/audit",
    type: "website",
  },
};

// PublicAuditPage uses useSearchParams() to prefill from /audit?domain=...&autorun=1
// (hero CTA on /). Next.js requires that to be wrapped in <Suspense> when the page
// is statically pre-rendered, otherwise the build fails at export time.
export default function AuditPage() {
  return (
    <Suspense fallback={null}>
      <PublicAuditPage />
    </Suspense>
  );
}
