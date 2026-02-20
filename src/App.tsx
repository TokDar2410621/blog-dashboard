import { lazy, Suspense } from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Toaster } from "@/components/ui/sonner";
import { AuthGuard } from "@/components/AuthGuard";
import { Loader2 } from "lucide-react";

const SiteSelector = lazy(() => import("./pages/SiteSelector"));
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
      <BrowserRouter>
        <div className="dark">
          <Suspense fallback={<Loader />}>
            <Routes>
              <Route path="/" element={<SiteSelector />} />
              <Route
                path="/dashboard/*"
                element={
                  <AuthGuard>
                    <DashboardLayout />
                  </AuthGuard>
                }
              />
            </Routes>
          </Suspense>
        </div>
      </BrowserRouter>
      <Toaster />
    </QueryClientProvider>
  );
}

export default App;
