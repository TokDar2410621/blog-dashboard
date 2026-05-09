import { lazy, Suspense } from "react";
import { Routes, Route } from "react-router-dom";
import { SidebarProvider, SidebarInset, SidebarTrigger } from "@/components/ui/sidebar";
import { DashboardSidebar } from "@/components/DashboardSidebar";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { Loader2, Newspaper } from "lucide-react";

// Lazy-load every dashboard page so they ship as their own chunks.
const Overview = lazy(() => import("./Overview"));
const PostList = lazy(() => import("./PostList"));
const PostEditor = lazy(() => import("./PostEditor"));
const AIGenerator = lazy(() => import("./AIGenerator"));
const ImageGallery = lazy(() => import("./ImageGallery"));
const SiteSettings = lazy(() => import("./SiteSettings"));
const BulkAudit = lazy(() => import("./BulkAudit"));
const KeywordTracker = lazy(() => import("./KeywordTracker"));
const ContentDecay = lazy(() => import("./ContentDecay"));
const TopicClusters = lazy(() => import("./TopicClusters"));
const LinkGraph = lazy(() => import("./LinkGraph"));
const Redirects = lazy(() => import("./Redirects"));
const BrokenLinks = lazy(() => import("./BrokenLinks"));
const WeeklyDigest = lazy(() => import("./WeeklyDigest"));

function PageLoader() {
  return (
    <div className="flex items-center justify-center py-12">
      <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
    </div>
  );
}

export default function DashboardLayout() {
  return (
    <SidebarProvider>
      <DashboardSidebar />
      <SidebarInset>
        {/* Mobile-only top bar so users can reach the sidebar (offcanvas) */}
        <header className="md:hidden sticky top-0 z-30 flex h-12 items-center gap-2 border-b border-border/50 bg-background/95 backdrop-blur px-3">
          <SidebarTrigger />
          <Newspaper className="h-4 w-4 text-primary" />
          <span className="font-semibold text-sm">Gridar</span>
        </header>
        <div className="p-4 md:p-6">
          <ErrorBoundary>
            <Suspense fallback={<PageLoader />}>
              <Routes>
                  <Route index element={<Overview />} />
                  <Route path="articles" element={<PostList />} />
                  <Route path="articles/nouveau" element={<PostEditor />} />
                  <Route path="articles/:slug" element={<PostEditor />} />
                  <Route path="generer" element={<AIGenerator />} />
                  <Route path="audit-global" element={<BulkAudit />} />
                  <Route path="positions" element={<KeywordTracker />} />
                  <Route path="decay" element={<ContentDecay />} />
                  <Route path="clusters" element={<TopicClusters />} />
                  <Route path="link-graph" element={<LinkGraph />} />
                  <Route path="redirects" element={<Redirects />} />
                  <Route path="broken-links" element={<BrokenLinks />} />
                  <Route path="digest" element={<WeeklyDigest />} />
                  <Route path="images" element={<ImageGallery />} />
                  <Route path="parametres" element={<SiteSettings />} />
                </Routes>
              </Suspense>
            </ErrorBoundary>
          </div>
      </SidebarInset>
    </SidebarProvider>
  );
}
