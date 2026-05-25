import type { Metadata } from "next";
import { PublicAuditPage } from "@/components/PublicAuditPage";

export const metadata: Metadata = {
  title: "Audit SEO gratuit de ton site - Gridar",
  description:
    "Audit SEO complet de ton site en 30 secondes : score composite, top mots-cles, vitesse mobile, recommandations. Sans inscription.",
  alternates: { canonical: "/audit" },
  openGraph: {
    title: "Audit SEO gratuit - 30 secondes",
    description: "Entre ton domaine, recois ton score SEO + top mots-cles + recos. Sans inscription.",
    url: "https://gridar.app/audit",
    type: "website",
  },
};

export default function AuditPage() {
  return <PublicAuditPage />;
}
