import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { login } from "@/lib/api-client";
import { setTokens, getToken } from "@/lib/sites";
import { useAuth } from "@/hooks/useAuth";
import { getApiErrorMessage } from "@/lib/api-errors";
import { Loader2, Newspaper, Sparkles, CheckCircle2 } from "lucide-react";
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
              <Newspaper className="h-7 w-7 text-emerald-400" />
              <span className="font-bold text-xl tracking-tight">
                blog-dashboard
              </span>
            </div>
            <h1 className="text-3xl font-bold tracking-tight">
              {t("login.title")}
            </h1>
            <p className="text-sm text-muted-foreground mt-1">
              {t("login.subtitle")}
            </p>
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
