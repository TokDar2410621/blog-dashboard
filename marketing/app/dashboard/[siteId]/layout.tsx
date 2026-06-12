"use client";

import { SidebarProvider, SidebarInset, SidebarTrigger } from "@/components/ui/sidebar";
import { DashboardSidebar } from "@/components/DashboardSidebar";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { AuthGuard } from "@/components/AuthGuard";
import { JobsProvider } from "@/context/JobsContext";
import { JobsDock } from "@/components/JobsDock";
import { GridarMark } from "@/components/GridarMark";

/**
 * Client shell for every per-site dashboard page (/dashboard/[siteId]/*).
 * Mirrors the SPA's DashboardLayout: SidebarProvider + DashboardSidebar +
 * SidebarInset with a mobile-only topbar, wrapped in AuthGuard so the whole
 * subtree requires a session, and JobsProvider so background jobs survive
 * route changes within the dashboard.
 */
export default function DashboardSiteLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <AuthGuard>
      <JobsProvider>
        <SidebarProvider>
          <DashboardSidebar />
          <SidebarInset>
            {/* Mobile-only top bar so users can reach the sidebar (offcanvas) */}
            <header className="md:hidden sticky top-0 z-30 flex h-12 items-center gap-2 border-b border-border/50 bg-background/95 backdrop-blur px-3">
              <SidebarTrigger />
              <GridarMark className="h-4 w-4 text-primary" />
              <span className="font-semibold text-sm">Gridar</span>
            </header>
            <div className="p-4 md:p-6">
              <ErrorBoundary>{children}</ErrorBoundary>
            </div>
          </SidebarInset>
        </SidebarProvider>
        <JobsDock />
      </JobsProvider>
    </AuthGuard>
  );
}
