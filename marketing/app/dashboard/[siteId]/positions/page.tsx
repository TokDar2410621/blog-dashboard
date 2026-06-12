import type { Metadata } from "next";
import KeywordTrackerPage from "@/components/dashboard/KeywordTrackerPage";

export const metadata: Metadata = {
  title: "Suivi des positions - Gridar",
};

export default function PositionsPage() {
  return <KeywordTrackerPage />;
}
