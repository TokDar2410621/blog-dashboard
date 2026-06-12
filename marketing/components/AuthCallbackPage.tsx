"use client";

/**
 * OAuth callback handler.
 *
 * Provider-side redirect lands here:
 *   /auth/google/callback?code=...&state=...
 *   /auth/github/callback?code=...&state=...
 *
 * We extract the `code`, POST it to /api/auth/<provider>/ along with the
 * exact redirect_uri we registered with the provider, and the backend
 * returns the JWT cookie pair via dj-rest-auth + the access token in the
 * response body. We mirror the username/password login flow:
 *   setTokens(access) -> checkAuth() -> router.replace("/sites").
 */
import { useEffect, useRef, useState } from "react";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Loader2, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { socialLogin, ApiError } from "@/lib/api-client";
import { setTokens } from "@/lib/auth-storage";
import { useAuth } from "@/context/AuthContext";

export function AuthCallbackPage() {
  const { provider } = useParams<{ provider: string }>();
  const params = useSearchParams();
  const router = useRouter();
  const { checkAuth } = useAuth();
  const [error, setError] = useState<string | null>(null);
  // StrictMode runs effects twice in dev, which would burn a single-use OAuth code.
  const exchangeStarted = useRef(false);

  useEffect(() => {
    if (exchangeStarted.current) return;
    exchangeStarted.current = true;

    if (!provider || (provider !== "google" && provider !== "github")) {
      setError("Provider OAuth inconnu.");
      return;
    }

    const code = params.get("code");
    const oauthError = params.get("error");
    if (oauthError) {
      setError(`Le provider a refusé la connexion : ${oauthError}.`);
      return;
    }
    if (!code) {
      setError("Aucun code OAuth reçu. Réessaie depuis la page de connexion.");
      return;
    }

    const redirectUri = `${window.location.origin}/auth/${provider}/callback`;

    socialLogin(provider, code, redirectUri)
      .then(async (tokens) => {
        setTokens(tokens.access);
        await checkAuth();
        router.replace("/sites");
      })
      .catch((err) => {
        const msg =
          err instanceof ApiError
            ? err.message
            : "Connexion impossible. Réessaie.";
        setError(msg);
      });
  }, [provider, params, router, checkAuth]);

  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-background">
      <div className="max-w-sm w-full text-center space-y-4">
        {!error && (
          <>
            <Loader2 className="h-10 w-10 animate-spin text-primary mx-auto" />
            <h1 className="text-xl font-semibold">Connexion en cours...</h1>
            <p className="text-sm text-muted-foreground">
              On finalise ton lien {provider === "google" ? "Google" : "GitHub"}.
            </p>
          </>
        )}
        {error && (
          <>
            <AlertCircle className="h-10 w-10 text-destructive mx-auto" />
            <h1 className="text-xl font-semibold">Échec de la connexion</h1>
            <p className="text-sm text-muted-foreground">{error}</p>
            <Button onClick={() => router.replace("/login")}>
              Retour à la connexion
            </Button>
          </>
        )}
      </div>
    </div>
  );
}
