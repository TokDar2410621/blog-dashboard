import { AutopilotCard } from "@/components/AutopilotCard";
import { useSettings } from "./useSettings";

export default function Autopilot() {
  const { siteId } = useSettings();
  if (!siteId) return null;
  return <AutopilotCard siteId={siteId} />;
}
