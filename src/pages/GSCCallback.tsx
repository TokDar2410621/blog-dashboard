/**
 * GSC OAuth callback handler.
 *
 * Google redirects here after the user consents to the Search Console scope:
 *   /gsc/callback?code=...&state=<base64(site_id)>
 *
 * The `state` is a URL-safe base64 encoding of the Site primary key (see
 * `_gsc_encode_state` in backend/sites_mgmt/views.py). We decode it client-side
 * to know which Site to POST to, then forward {code, state} to
 *   POST /api/sites/<site_id>/gsc/oauth-callback/
 * which exchanges the code for a refresh_token and persists it on the Site.
 *
 * Success and error both navigate back to the site's parametres page with a
 * sonner toast - the user never sees this loader for more than a moment.
 */
import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import { submitGSCOAuthCallback, ApiError } from "@/lib/api-client";

/** Decode a URL-safe base64 string (no padding) - mirrors the backend's
 *  `urlsafe_b64encode(str(site_id)).rstrip('=')`. */
function decodeStateToSiteId(state: string): number | null {
  try {
    const normalized = state.replace(/-/g, "+").replace(/_/g, "/");
    const padded = normalized + "=".repeat((4 - (normalized.length % 4)) % 4);
    const raw = atob(padded);
    const id = parseInt(raw, 10);
    return Number.isFinite(id) && id > 0 ? id : null;
  } catch {
    return null;
  }
}

export default function GSCCallback() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [pending, setPending] = useState(true);
  // StrictMode runs effects twice in dev, which would burn a single-use OAuth code.
  const exchangeStarted = useRef(false);

  useEffect(() => {
    if (exchangeStarted.current) return;
    exchangeStarted.current = true;

    const code = params.get("code");
    const state = params.get("state");
    const oauthError = params.get("error");

    if (oauthError) {
      toast.error(`Google a refusé la connexion : ${oauthError}`);
      navigate("/sites", { replace: true });
      return;
    }

    if (!code || !state) {
      toast.error("Réponse OAuth invalide (code ou state manquant).");
      navigate("/sites", { replace: true });
      return;
    }

    const siteId = decodeStateToSiteId(state);
    if (!siteId) {
      toast.error("State OAuth illisible. Relance la connexion GSC.");
      navigate("/sites", { replace: true });
      return;
    }

    submitGSCOAuthCallback(siteId, code, state)
      .then(() => {
        toast.success("Google Search Console connecté");
        navigate(`/dashboard/${siteId}/parametres`, { replace: true });
      })
      .catch((err) => {
        const msg =
          err instanceof ApiError
            ? err.message
            : "Connexion à Google Search Console impossible.";
        toast.error(msg);
        navigate(`/dashboard/${siteId}/parametres`, { replace: true });
      })
      .finally(() => setPending(false));
  }, [params, navigate]);

  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-background">
      <div className="max-w-sm w-full text-center space-y-4">
        <Loader2 className="h-10 w-10 animate-spin text-primary mx-auto" />
        <h1 className="text-xl font-semibold">
          {pending ? "Connexion GSC en cours..." : "Redirection..."}
        </h1>
        <p className="text-sm text-muted-foreground">
          On finalise le lien avec Google Search Console.
        </p>
      </div>
    </div>
  );
}
