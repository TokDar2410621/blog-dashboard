import { MarketingHeader } from "@/components/MarketingHeader";
import { CinematicFooter } from "@/components/ui/motion-footer";

export default function ToolsLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <MarketingHeader trail="Outils gratuits" />
      <main className="min-h-screen">{children}</main>
      <CinematicFooter />
    </>
  );
}
