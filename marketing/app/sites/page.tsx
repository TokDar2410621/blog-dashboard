"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Loader2, ArrowRight } from "lucide-react";
import { AuthGuard } from "@/components/AuthGuard";
import { fetchSites } from "@/lib/api-client";
import { GridarMark } from "@/components/GridarMark";

/**
 * Site selector placeholder. The Vite version has Create-site flow + tier
 * gating + onboarding nudge. For now we just list sites so a user landing
 * here post-login can pick one and reach /dashboard/[siteId].
 */
function SitesContent() {
  const { data, isLoading } = useQuery({
    queryKey: ["sites"],
    queryFn: fetchSites,
  });

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4 py-12">
      <div className="w-full max-w-2xl space-y-6">
        <div className="flex items-center justify-center gap-2 mb-8">
          <GridarMark className="h-8 w-8 text-primary" />
          <span className="text-xl font-semibold">Gridar</span>
        </div>
        <Card>
          <CardHeader>
            <CardTitle>Choisir un site</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {isLoading ? (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" />
                Chargement de tes sites...
              </div>
            ) : data && data.length > 0 ? (
              data.map((site) => (
                <Link
                  key={site.id}
                  href={`/dashboard/${site.id}`}
                  className="flex items-center justify-between rounded-lg border border-border/50 hover:border-primary p-4 transition-colors group"
                >
                  <div>
                    <div className="font-semibold">{site.name}</div>
                    <div className="text-xs text-muted-foreground font-mono">
                      {site.domain}
                    </div>
                  </div>
                  <ArrowRight className="h-4 w-4 text-muted-foreground group-hover:text-primary group-hover:translate-x-0.5 transition-all" />
                </Link>
              ))
            ) : (
              <div className="text-center py-8 space-y-3">
                <p className="text-sm text-muted-foreground">
                  Tu n&apos;as pas encore de site. La page de creation arrive bientot dans la migration Next.js.
                </p>
                <Button asChild variant="outline" size="sm">
                  <Link href="/">Retour au site</Link>
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

export default function SitesPage() {
  return (
    <AuthGuard>
      <SitesContent />
    </AuthGuard>
  );
}
