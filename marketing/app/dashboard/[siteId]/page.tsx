"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { authFetch } from "@/lib/api-client";
import { Loader2 } from "lucide-react";

/**
 * Placeholder Overview. The full version (recent posts + stats + traffic
 * chart) is the next item in the migration queue. For now we just want
 * to validate the layout + auth + react-query plumbing works end-to-end.
 */
export default function Overview() {
  const params = useParams<{ siteId: string }>();
  const siteId = params?.siteId;

  const { data, isLoading } = useQuery({
    queryKey: ["site", siteId],
    queryFn: async () => {
      const res = await authFetch(`/sites/${siteId}/`);
      if (!res.ok) throw new Error("site fetch failed");
      return res.json();
    },
    enabled: !!siteId,
  });

  return (
    <div className="space-y-6 max-w-5xl">
      <div>
        <h1 className="text-2xl font-bold">Tableau de bord</h1>
        <p className="text-muted-foreground text-sm">
          Site #{siteId} - {data?.name || (isLoading ? "..." : "?")}
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Migration Next.js en cours</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3 text-sm text-muted-foreground">
          <p>
            La foundation Next.js est en place : auth, sidebar, react-query, providers.
            Les vraies pages dashboard (Articles, Generation IA, Parametres, Positions, etc.)
            arrivent dans les prochaines sessions.
          </p>
          <p>Tu peux deja naviguer entre les sections de la sidebar pour valider le layout.</p>
          {isLoading ? (
            <div className="flex items-center gap-2 text-xs">
              <Loader2 className="h-3 w-3 animate-spin" />
              Verification API en cours...
            </div>
          ) : data ? (
            <div className="rounded border border-emerald-500/30 bg-emerald-500/5 p-3 text-emerald-300 text-xs">
              API OK. Site charge : <span className="font-mono">{data.domain}</span>
            </div>
          ) : (
            <div className="rounded border border-amber-500/30 bg-amber-500/5 p-3 text-amber-300 text-xs">
              API call failed. Verifie que le backend tourne et que tu es bien authentifie.
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
