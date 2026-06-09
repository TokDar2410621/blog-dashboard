import { lazy, Suspense } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { SidebarProvider, SidebarInset, SidebarTrigger } from "@/components/ui/sidebar";
import { DashboardSidebar } from "@/components/DashboardSidebar";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { Loader2 } from "lucide-react";
import { GridarMark } from "@/components/GridarMark";

// Lazy-load every dashboard page so they ship as their own chunks.
const Overview = lazy(() => import("./Overview"));
const SiteAudit = lazy(() => import("./SiteAudit"));
const PostList = lazy(() => import("./PostList"));
const PostEditor = lazy(() => import("./PostEditor"));
const AIGenerator = lazy(() => import("./AIGenerator"));
const ImageGallery = lazy(() => import("./ImageGallery"));
const SiteSettings = lazy(() => import("./SiteSettings"));
const SettingsLayout = lazy(() => import("./settings/SettingsLayout"));
const SettingsGeneral = lazy(() => import("./settings/General"));
const SettingsBranding = lazy(() => import("./settings/Branding"));
const SettingsAuthor = lazy(() => import("./settings/Author"));
const SettingsCta = lazy(() => import("./settings/Cta"));
const SettingsLanguages = lazy(() => import("./settings/Languages"));
const SettingsGsc = lazy(() => import("./settings/Gsc"));
const SettingsMemory = lazy(() => import("./settings/Memory"));
const SettingsAutopilot = lazy(() => import("./settings/Autopilot"));
const SettingsIntegrations = lazy(() => import("./settings/Integrations"));
const BulkAudit = lazy(() => import("./BulkAudit"));
const KeywordTracker = lazy(() => import("./KeywordTracker"));
const ContentDecay = lazy(() => import("./ContentDecay"));
const TopicClusters = lazy(() => import("./TopicClusters"));
const LinkGraph = lazy(() => import("./LinkGraph"));
const Redirects = lazy(() => import("./Redirects"));
const BrokenLinks = lazy(() => import("./BrokenLinks"));
const WeeklyDigest = lazy(() => import("./WeeklyDigest"));
const SerpAnalyzer = lazy(() => import("./SerpAnalyzer"));
const AiVisibility = lazy(() => import("./AiVisibility"));

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
          <GridarMark className="h-4 w-4 text-primary" />
          <span className="font-semibold text-sm">Gridar</span>
        </header>
        <div className="p-4 md:p-6">
          <ErrorBoundary>
            <Suspense fallback={<PageLoader />}>
              <Routes>
                  <Route index element={<Overview />} />
                  <Route path="audit-site" element={<SiteAudit />} />
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
                  <Route path="serp-analyzer" element={<SerpAnalyzer />} />
                  <Route path="ai-visibility" element={<AiVisibility />} />
                  <Route path="digest" element={<WeeklyDigest />} />
                  <Route path="images" element={<ImageGallery />} />
                  <Route path="parametres" element={<SettingsLayout />}>
                    <Route index element={<Navigate to="general" replace />} />
                    <Route path="general" element={<SettingsGeneral />} />
                    <Route path="branding" element={<SettingsBranding />} />
                    <Route path="auteur" element={<SettingsAuthor />} />
                    <Route path="cta" element={<SettingsCta />} />
                    <Route path="langues" element={<SettingsLanguages />} />
                    <Route path="gsc" element={<SettingsGsc />} />
                    <Route path="memoire" element={<SettingsMemory />} />
                    <Route path="autopilote" element={<SettingsAutopilot />} />
                    <Route path="integrations" element={<SettingsIntegrations />} />
                  </Route>
                  {/* Legacy redirect (kept so old deep links keep working) */}
                  <Route path="parametres/legacy" element={<SiteSettings />} />
                </Routes>
              </Suspense>
            </ErrorBoundary>
          </div>
      </SidebarInset>
    </SidebarProvider>
  );
}
