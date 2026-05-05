import { lazy, Suspense } from "react";
import { Routes, Route } from "react-router-dom";
import { SidebarProvider, SidebarInset } from "@/components/ui/sidebar";
import { DashboardSidebar } from "@/components/DashboardSidebar";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { Loader2 } from "lucide-react";

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
      <div className="flex min-h-screen w-full">
        <DashboardSidebar />
        <SidebarInset className="flex-1">
          <div className="p-6">
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
      </div>
    </SidebarProvider>
  );
}
