import type { Metadata } from "next";
import { LinkGraphPage } from "@/components/dashboard/LinkGraphPage";

export const metadata: Metadata = {
  title: "Maillage interne - Gridar",
};

export default function LinkGraphRoute() {
  return <LinkGraphPage />;
}
