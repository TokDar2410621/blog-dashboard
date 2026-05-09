import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { login } from "@/lib/api-client";
import { setTokens, getToken } from "@/lib/sites";
import { useAuth } from "@/hooks/useAuth";
import { getApiErrorMessage } from "@/lib/api-errors";
import { Loader2, Sparkles, CheckCircle2, Github } from "lucide-react";
import { GridarMark } from "@/components/GridarMark";
import { toast } from "sonner";
import { Navigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import ProductMockup3D from "@/components/ProductMockup3D";

export default function Login() {
  const navigate = useNavigate();
  const { t, i18n } = useTranslation();
  const { user, isLoading, checkAuth } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  if (!isLoading && user) {
    return <Navigate to="/sites" replace />;
  }

  if (isLoading && getToken()) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const tokens = await login(username, password);
      setTokens(tokens.access);
      await checkAuth();
      toast.success(t("login.success"));
      navigate("/sites");
    } catch (e) {
      toast.error(getApiErrorMessage(e, t));
    } finally {
      setLoading(false);
    }
  };

  const toggleLang = () => {
    i18n.changeLanguage(i18n.language === "fr" ? "en" : "fr");
  };

  const startOAuth = (provider: "google" | "github") => {
    const redirectUri = `${window.location.origin}/auth/${provider}/callback`;
    if (provider === "google") {
      const clientId = import.meta.env.VITE_GOOGLE_OAUTH_CLIENT_ID;
      if (!clientId) {
        toast.error("Google OAuth pas encore configuré (VITE_GOOGLE_OAUTH_CLIENT_ID manquant).");
        return;
      }
      const params = new URLSearchParams({
        client_id: clientId,
        redirect_uri: redirectUri,
        response_type: "code",
        scope: "openid email profile",
        access_type: "online",
        prompt: "select_account",
      });
      window.location.href = `https://accounts.google.com/o/oauth2/v2/auth?${params}`;
    } else {
      const clientId = import.meta.env.VITE_GITHUB_OAUTH_CLIENT_ID;
      if (!clientId) {
        toast.error("GitHub OAuth pas encore configuré (VITE_GITHUB_OAUTH_CLIENT_ID manquant).");
        return;
      }
      const params = new URLSearchParams({
        client_id: clientId,
        redirect_uri: redirectUri,
        scope: "read:user user:email",
      });
      window.location.href = `https://github.com/login/oauth/authorize?${params}`;
    }
  };

  return (
    <div className="min-h-screen bg-background grid lg:grid-cols-2 overflow-hidden">
      {/* Left: form */}
      <div className="flex items-center justify-center p-6 lg:p-12 relative">
        {/* Subtle emerald radial glow behind the form */}
        <div
          aria-hidden
          className="absolute inset-0 pointer-events-none"
          style={{
            background:
              "radial-gradient(60% 50% at 50% 30%, rgba(16,185,129,0.08), transparent 70%)",
          }}
        />
        <div className="relative w-full max-w-sm space-y-8">
          <div>
            <div className="flex items-center gap-2 mb-3">
              <GridarMark className="h-7 w-7 text-emerald-400" />
              <span className="font-bold text-xl tracking-tight">
                Gridar
              </span>
            </div>
            <h1 className="text-3xl font-bold tracking-tight">
              {t("login.title")}
            </h1>
            <p className="text-sm text-muted-foreground mt-1">
              {t("login.subtitle")}
            </p>
          </div>

          <div className="space-y-2">
            <Button
              type="button"
              variant="outline"
              className="w-full"
              onClick={() => startOAuth("google")}
              disabled={loading}
            >
              <svg className="h-4 w-4 mr-2" viewBox="0 0 24 24" aria-hidden>
                <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
              </svg>
              {t("login.continueWithGoogle", "Continuer avec Google")}
            </Button>
            <Button
              type="button"
              variant="outline"
              className="w-full"
              onClick={() => startOAuth("github")}
              disabled={loading}
            >
              <Github className="h-4 w-4 mr-2" />
              {t("login.continueWithGithub", "Continuer avec GitHub")}
            </Button>
          </div>

          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <span className="w-full border-t border-border/60"></span>
            </div>
            <div className="relative flex justify-center text-xs uppercase">
              <span className="bg-background px-2 text-muted-foreground">
                {t("login.orContinueWith", "ou avec un mot de passe")}
              </span>
            </div>
          </div>

          <form onSubmit={handleLogin} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="username">{t("login.username")}</Label>
              <Input
                id="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
                autoFocus
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">{t("login.password")}</Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  {t("login.loading")}
                </>
              ) : (
                t("login.submit")
              )}
            </Button>
          </form>

          <div className="text-center">
            <Button variant="ghost" size="sm" onClick={toggleLang}>
              {i18n.language === "fr" ? "EN" : "FR"}
            </Button>
          </div>
        </div>
      </div>

      {/* Right: mockup showcase (desktop only) */}
      <div className="hidden lg:flex relative overflow-hidden bg-zinc-950">
        {/* Emerald glow background */}
        <div
          aria-hidden
          className="absolute inset-0 pointer-events-none"
          style={{
            background:
              "radial-gradient(70% 60% at 70% 30%, rgba(16,185,129,0.15), transparent 70%), radial-gradient(40% 40% at 30% 80%, rgba(16,185,129,0.10), transparent 70%)",
          }}
        />

        <div className="relative w-full flex flex-col justify-center px-12 py-16">
          <div className="max-w-md mb-10">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-emerald-400/30 bg-emerald-400/10 text-emerald-300 text-xs font-mono uppercase tracking-wider mb-6">
              <Sparkles className="h-3 w-3" />
              SEO #1 au Québec
            </div>
            <h2 className="text-3xl font-bold tracking-tight text-white leading-tight">
              Reprends ton blog là où tu l'as laissé.
            </h2>
            <p className="text-zinc-400 mt-3 text-sm">
              Articles, audit SEO, suivi Google, génération IA. Tout en français-québécois.
            </p>
            <ul className="mt-6 space-y-2.5 text-sm text-zinc-300">
              <li className="flex items-start gap-2">
                <CheckCircle2 className="h-4 w-4 text-emerald-400 mt-0.5 shrink-0" />
                IA qui rédige en québécois, pas en français de France
              </li>
              <li className="flex items-start gap-2">
                <CheckCircle2 className="h-4 w-4 text-emerald-400 mt-0.5 shrink-0" />
                Connecte WordPress, Shopify, Webflow ou un blog hébergé
              </li>
              <li className="flex items-start gap-2">
                <CheckCircle2 className="h-4 w-4 text-emerald-400 mt-0.5 shrink-0" />
                Audit SEO + tracking Google sur tes mots-clés
              </li>
            </ul>
          </div>

          {/* Scaled-down mockup, peeking from the bottom */}
          <div
            className="relative"
            style={{
              transform: "scale(0.55)",
              transformOrigin: "0 0",
              width: "180%",
              marginTop: "-100px",
            }}
          >
            <ProductMockup3D />
          </div>
        </div>
      </div>
    </div>
  );
}
