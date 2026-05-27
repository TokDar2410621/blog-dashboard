"use client";

import { SidebarProvider, SidebarInset, SidebarTrigger } from "@/components/ui/sidebar";
import { DashboardSidebar } from "@/components/DashboardSidebar";
import { GridarMark } from "@/components/GridarMark";

/**
 * Per-site dashboard shell. Adds the sidebar + mobile header on top of
 * the AuthGuard from the parent /dashboard/layout.tsx. Marked 'use client'
 * because SidebarProvider holds the open/closed state in a context that
 * needs to be reactive.
 */
export default function SiteLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <SidebarProvider>
      <DashboardSidebar />
      <SidebarInset>
        <header className="md:hidden sticky top-0 z-30 flex h-12 items-center gap-2 border-b border-border/50 bg-background/95 backdrop-blur px-3">
          <SidebarTrigger />
          <GridarMark className="h-4 w-4 text-primary" />
          <span className="font-semibold text-sm">Gridar</span>
        </header>
        <div className="p-4 md:p-6">{children}</div>
      </SidebarInset>
    </SidebarProvider>
  );
}
