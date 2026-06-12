import type { Metadata } from "next";
import { AuthGuard } from "@/components/AuthGuard";
import { MultiDomainCompare } from "@/components/MultiDomainCompare";

export const metadata: Metadata = {
  title: "Comparaison multi-sites",
  robots: { index: false, follow: false },
};

export default function ComparePage() {
  return (
    <AuthGuard>
      <MultiDomainCompare />
    </AuthGuard>
  );
}
