import { lazy, Suspense } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "@/components/ui/sonner";
import { AuthGuard } from "@/components/AuthGuard";
import { AuthProvider } from "@/hooks/useAuth";
import { JobsProvider } from "@/context/JobsContext";
import { JobsDock } from "@/components/JobsDock";
import { Loader2 } from "lucide-react";
import "@/i18n";

const Login = lazy(() => import("./pages/Login"));
const Landing = lazy(() => import("./pages/Landing"));
const SiteSelector = lazy(() => import("./pages/SiteSelector"));
const MultiDomain = lazy(() => import("./pages/MultiDomain"));
const Billing = lazy(() => import("./pages/Billing"));
const ApiKeys = lazy(() => import("./pages/ApiKeys"));
const ApiDocs = lazy(() => import("./pages/ApiDocs"));
const OnboardingExternal = lazy(() => import("./pages/OnboardingExternal"));
const Docs = lazy(() => import("./pages/Docs"));
const Privacy = lazy(() => import("./pages/Privacy"));
const Terms = lazy(() => import("./pages/Terms"));
const AuthCallback = lazy(() => import("./pages/AuthCallback"));
const PublicAudit = lazy(() => import("./pages/PublicAudit"));
const ResetPassword = lazy(() => import("./pages/ResetPassword"));
const Blog = lazy(() => import("./pages/Blog"));
const BlogPost = lazy(() => import("./pages/BlogPost"));
const DashboardLayout = lazy(
  () => import("./pages/dashboard/DashboardLayout")
);

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5,
      retry: 1,
    },
  },
});

function Loader() {
  return (
    <div className="min-h-screen flex items-center justify-center">
      <Loader2 className="h-8 w-8 animate-spin text-primary" />
    </div>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <JobsProvider>
          <div className="dark bg-background text-foreground min-h-screen">
            <Suspense fallback={<Loader />}>
              <Routes>
                <Route path="/login" element={<Login />} />
                <Route path="/" element={<Landing />} />
                <Route
                  path="/sites"
                  element={
                    <AuthGuard>
                      <SiteSelector />
                    </AuthGuard>
                  }
                />
                <Route
                  path="/compare"
                  element={
                    <AuthGuard>
                      <MultiDomain />
                    </AuthGuard>
                  }
                />
                <Route
                  path="/billing"
                  element={
                    <AuthGuard>
                      <Billing />
                    </AuthGuard>
                  }
                />
                <Route
                  path="/account/api-keys"
                  element={
                    <AuthGuard>
                      <ApiKeys />
                    </AuthGuard>
                  }
                />
                <Route path="/api-docs" element={<ApiDocs />} />
                <Route path="/docs/*" element={<Docs />} />
                <Route path="/privacy" element={<Privacy />} />
                <Route path="/terms" element={<Terms />} />
                <Route path="/auth/:provider/callback" element={<AuthCallback />} />
                <Route path="/reset-password" element={<ResetPassword />} />
                <Route path="/blog" element={<Blog />} />
                <Route path="/blog/:slug" element={<BlogPost />} />
                <Route path="/audit" element={<PublicAudit />} />
                <Route
                  path="/onboarding/external"
                  element={
                    <AuthGuard>
                      <OnboardingExternal />
                    </AuthGuard>
                  }
                />
                <Route
                  path="/dashboard/:siteId/*"
                  element={
                    <AuthGuard>
                      <DashboardLayout />
                    </AuthGuard>
                  }
                />
                <Route path="*" element={<Navigate to="/" replace />} />
              </Routes>
            </Suspense>
            <JobsDock />
          </div>
          </JobsProvider>
        </BrowserRouter>
        <Toaster />
      </AuthProvider>
    </QueryClientProvider>
  );
}

export default App;
