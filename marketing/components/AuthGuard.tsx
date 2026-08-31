"use client";

import { useEffect } from "react";
import { useRouter, usePathname } from "next/navigation";
import { Loader2 } from "lucide-react";
import { useAuth } from "@/context/AuthContext";

/**
 * Wraps any subtree that must be authenticated. Redirects to /login with a
 * ?next=<current-path + query> so the user lands back where they started after
 * signing in. While the AuthContext is still validating, shows a centered
 * spinner instead of flashing the page.
 *
 * La query string fait PARTIE du retour, et ce detail casse un flux entier
 * quand on l'oublie. `usePathname()` rend `/gsc/callback` sans le
 * `?code=...&state=...` que Google vient d'y deposer : un utilisateur pas
 * encore authentifie partait au login, revenait sur `/gsc/callback` nu, et le
 * code OAuth a usage unique etait brule sans jamais etre echange. La connexion
 * Search Console echouait alors en silence, en affichant juste « reponse OAuth
 * invalide ». Constate le 2026-08-30 : les quatre sites portaient encore un
 * jeton `webmasters.readonly` malgre plusieurs tentatives de reconnexion.
 *
 * On lit `window.location.search` plutot que `useSearchParams()` : le hook
 * imposerait une frontiere Suspense a chaque appelant d'AuthGuard, alors que
 * l'effet ne tourne que cote client, ou `window` existe toujours.
 */
export function AuthGuard({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      const search = typeof window !== "undefined" ? window.location.search : "";
      const next = encodeURIComponent(`${pathname || "/"}${search}`);
      router.replace(`/login?next=${next}`);
    }
  }, [isAuthenticated, isLoading, pathname, router]);

  if (isLoading || !isAuthenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return <>{children}</>;
}
