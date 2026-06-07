import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { authFetch } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { GridarMark } from "@/components/GridarMark";
import { Sparkles, ShieldCheck, ArrowRight, Loader2, XCircle } from "lucide-react";

type IssueResponse = {
  access_token: string;
  token_type: "Bearer";
  name: string;
  prefix: string;
  scope: string;
  created_at: string;
};

type Phase =
  | { kind: "loading" }
  | { kind: "needs-login"; loginUrl: string }
  | { kind: "ready"; clientName: string; callbackUrl: string }
  | { kind: "issuing"; clientName: string }
  | { kind: "redirecting" }
  | { kind: "error"; message: string };

/**
 * OAuth bridge page used by mcp.gridar.app to mint an ApiToken on behalf of
 * the logged-in user, then redirect back to the MCP HTTP server with the
 * token piggy-backed on the redirect.
 *
 * Query params (sent by the MCP server's /authorize handler):
 *   - session_id: opaque identifier for this OAuth flow on mcp.gridar.app
 *   - client_name: human-readable client name ("Claude Desktop", "Codex CLI", ...)
 *   - return_to: where to redirect once the token is issued. Must be on the
 *                mcp.gridar.app domain (validated server-side; here we trust
 *                the host since the MCP server is the only party that links
 *                users to this page).
 */
export default function McpAuthorize() {
  const [params] = useSearchParams();
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const [phase, setPhase] = useState<Phase>({ kind: "loading" });

  const sessionId = params.get("session_id") ?? "";
  const clientName = params.get("client_name") ?? "MCP client";
  const returnTo = params.get("return_to") ?? "";

  useEffect(() => {
    if (authLoading) return;
    if (!sessionId || !returnTo) {
      setPhase({
        kind: "error",
        message: "Lien invalide. Reviens depuis le client MCP qui demande la connexion.",
      });
      return;
    }
    if (!isAuthenticated) {
      const here = window.location.pathname + window.location.search;
      const loginUrl = `/login?next=${encodeURIComponent(here)}`;
      setPhase({ kind: "needs-login", loginUrl });
      return;
    }
    setPhase({ kind: "ready", clientName, callbackUrl: returnTo });
  }, [authLoading, isAuthenticated, sessionId, returnTo, clientName]);

  const grant = async () => {
    setPhase({ kind: "issuing", clientName });
    try {
      const res = await authFetch("/auth/issue-mcp-token/", {
        method: "POST",
        body: JSON.stringify({ client_name: clientName, scope: "mcp:full" }),
      });
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      const data = (await res.json()) as IssueResponse;
      // Build the redirect URL: returnTo + session_id + access_token.
      // The MCP server will validate session_id, store the token mapped to
      // its OAuth code, then redirect the user-agent to the originally
      // requested client redirect_uri.
      const target = new URL(returnTo);
      target.searchParams.set("session_id", sessionId);
      target.searchParams.set("access_token", data.access_token);
      setPhase({ kind: "redirecting" });
      window.location.replace(target.toString());
    } catch (err) {
      setPhase({
        kind: "error",
        message:
          err instanceof Error
            ? `Echec de l'emission du token: ${err.message}`
            : "Echec de l'emission du token (raison inconnue).",
      });
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-zinc-950 text-zinc-100 px-4">
      <Card className="w-full max-w-md bg-zinc-900/60 border-white/10">
        <CardContent className="pt-8 pb-6 space-y-6">
          <div className="flex items-center gap-3">
            <GridarMark className="h-8 w-8 text-emerald-400" />
            <span className="font-semibold text-lg tracking-tight">Gridar MCP</span>
          </div>

          {phase.kind === "loading" && (
            <div className="text-sm text-zinc-400 flex items-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin" />
              Verification de ta session...
            </div>
          )}

          {phase.kind === "needs-login" && (
            <div className="space-y-4">
              <h1 className="text-xl font-semibold">Connexion requise</h1>
              <p className="text-sm text-zinc-400">
                Pour autoriser <strong>{clientName}</strong> a acceder a tes
                sites Gridar, connecte-toi d&apos;abord. Tu reviendras
                automatiquement sur cette page.
              </p>
              <Link to={phase.loginUrl}>
                <Button className="w-full bg-white text-zinc-950 hover:bg-zinc-200">
                  Me connecter <ArrowRight className="h-4 w-4 ml-2" />
                </Button>
              </Link>
            </div>
          )}

          {phase.kind === "ready" && (
            <div className="space-y-4">
              <h1 className="text-xl font-semibold">
                Connecter <span className="text-emerald-400">{phase.clientName}</span> ?
              </h1>
              <p className="text-sm text-zinc-400">
                Le client va pouvoir, en ton nom :
              </p>
              <ul className="text-sm space-y-2 text-zinc-300">
                <li className="flex gap-2">
                  <ShieldCheck className="h-4 w-4 text-emerald-400 shrink-0 mt-0.5" />
                  Lire la liste de tes sites, articles, mots-cles, autopilote.
                </li>
                <li className="flex gap-2">
                  <ShieldCheck className="h-4 w-4 text-emerald-400 shrink-0 mt-0.5" />
                  Generer, modifier, supprimer des articles.
                </li>
                <li className="flex gap-2">
                  <ShieldCheck className="h-4 w-4 text-emerald-400 shrink-0 mt-0.5" />
                  Configurer autopilote, RAG, page de preuve publique.
                </li>
              </ul>
              <p className="text-xs text-zinc-500">
                Tu peux revoquer cet acces a tout moment depuis
                <Link to="/account/api-keys" className="text-emerald-400 hover:underline ml-1">
                  /account/api-keys
                </Link>
                .
              </p>
              <div className="flex gap-2">
                <Button
                  onClick={() => window.history.back()}
                  variant="outline"
                  className="flex-1 bg-transparent border-white/15 hover:bg-white/5"
                >
                  Annuler
                </Button>
                <Button
                  onClick={grant}
                  className="flex-1 bg-emerald-500 text-zinc-950 hover:bg-emerald-400"
                >
                  <Sparkles className="h-4 w-4 mr-2" />
                  Autoriser
                </Button>
              </div>
            </div>
          )}

          {phase.kind === "issuing" && (
            <div className="text-sm text-zinc-400 flex items-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin" />
              Emission du token pour {phase.clientName}...
            </div>
          )}

          {phase.kind === "redirecting" && (
            <div className="text-sm text-zinc-400 flex items-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin" />
              Redirection vers le client MCP...
            </div>
          )}

          {phase.kind === "error" && (
            <div className="space-y-3">
              <div className="flex items-center gap-2 text-amber-400 text-sm">
                <XCircle className="h-4 w-4" />
                {phase.message}
              </div>
              <Link to="/account/api-keys">
                <Button variant="outline" className="w-full bg-transparent border-white/15 hover:bg-white/5">
                  Gerer mes cles API
                </Button>
              </Link>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
