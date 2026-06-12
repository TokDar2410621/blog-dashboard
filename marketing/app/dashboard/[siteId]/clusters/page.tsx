import type { Metadata } from "next";
import { TopicClustersPage } from "@/components/dashboard/TopicClustersPage";

export const metadata: Metadata = {
  title: "Topic clusters - Gridar",
};

export default function ClustersPage() {
  return <TopicClustersPage />;
}
