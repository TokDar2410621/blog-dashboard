import type { Metadata } from "next";
import { redirect } from "next/navigation";

export const metadata: Metadata = {
  title: "Audit SEO gratuit - Gridar",
  description: "Audit SEO complet en 30 secondes. Sans inscription.",
  alternates: { canonical: "/audit" },
};

// Redirect to the main /audit page which already exists
export default function SeoAuditToolPage() {
  redirect("/audit");
}
