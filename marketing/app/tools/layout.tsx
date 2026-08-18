import { MarketingHeader } from "@/components/MarketingHeader";
import { MarketingFooter } from "@/components/MarketingFooter";

export default function ToolsLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <MarketingHeader trail="Outils gratuits" />
      <main className="min-h-screen">{children}</main>
      <MarketingFooter />
    </>
  );
}
