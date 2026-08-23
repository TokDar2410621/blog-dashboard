"use client";

/**
 * LoginPage - Next.js port of the SPA's src/pages/Login.tsx.
 *
 * Progressive email-first flow:
 *   email  -> checkEmail() pivots to:
 *     signup     (email unknown)
 *     oauth-only (account exists, no password, OAuth providers linked)
 *     login      (account exists with a password)
 *
 * Public page (no AuthGuard): an authenticated visitor is bounced to
 * ?next=<path> (set by AuthGuard) or /sites.
 */

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  ApiError,
  login,
  checkEmail,
  register,
  requestPasswordReset,
} from "@/lib/api-client";
import { setTokens, getToken } from "@/lib/auth-storage";
import { useAuth } from "@/context/AuthContext";
import {
  Loader2,
  CheckCircle2,
  Github,
  ArrowLeft,
  ArrowRight,
} from "lucide-react";
import { GridarMark } from "@/components/GridarMark";
import { toast } from "sonner";
import ProductMockup3D from "@/components/ProductMockup3D";

type Step = "email" | "login" | "signup" | "oauth-only";

/** French messages for machine-readable ApiError codes (mirrors the SPA's
 *  `errors.*` i18n namespace + getApiErrorMessage fallback chain). */
const API_ERROR_MESSAGES: Record<string, string> = {
  SESSION_EXPIRED: "Votre session a expiré. Connectez-vous à nouveau.",
  INVALID_CREDENTIALS: "Identifiants invalides",
  REQUEST_FAILED: "La requête n'a pas pu aboutir.",
  VALIDATION_ERROR: "Données invalides. Vérifiez les champs et réessayez.",
  GENERIC: "Une erreur s'est produite",
};

function getApiErrorMessage(error: unknown): string {
  if (error instanceof ApiError && error.code && API_ERROR_MESSAGES[error.code]) {
    return API_ERROR_MESSAGES[error.code];
  }
  if (error instanceof Error && error.message) return error.message;
  return API_ERROR_MESSAGES.GENERIC;
}

/** Multicolor Google "G" (inline so the page has zero asset dependencies). */
function GoogleIcon() {
  return (
    <svg className="h-4 w-4 mr-2" viewBox="0 0 24 24" aria-hidden>
      <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
      <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
      <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
      <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
    </svg>
  );
}

export function LoginPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { user, isLoading, checkAuth } = useAuth();

  // AuthGuard redirects here with ?next=<original-path>; honor it so the
  // round-trip lands the user back where they started. Internal paths only.
  const nextParam = searchParams.get("next");
  const nextPath =
    nextParam && nextParam.startsWith("/") && !nextParam.startsWith("//")
      ? nextParam
      : "/sites";

  const [step, setStep] = useState<Step>("email");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  // Providers detected for an OAuth-only account (used by the 'oauth-only' step).
  const [oauthProviders, setOauthProviders] = useState<string[]>([]);

  // SPA equivalent: <Navigate to="/sites" replace /> when already signed in.
  useEffect(() => {
    if (!isLoading && user) {
      router.replace(nextPath);
    }
  }, [isLoading, user, nextPath, router]);

  if (!isLoading && user) {
    return null;
  }

  if (isLoading && getToken()) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  const handleEmailSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim()) return;
    setLoading(true);
    try {
      const result = await checkEmail(email.trim().toLowerCase());
      if (!result.exists) {
        setStep("signup");
      } else if (!result.has_password && result.social_providers.length > 0) {
        // Account was created via OAuth only - no password to type.
        // Surface only the relevant OAuth buttons.
        setOauthProviders(result.social_providers);
        setStep("oauth-only");
      } else {
        setStep("login");
      }
    } catch (err) {
      toast.error(getApiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  const handleLoginSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      const tokens = await login(email.trim().toLowerCase(), password);
      setTokens(tokens.access);
      await checkAuth();
      toast.success("Connecté!");
      router.push(nextPath);
    } catch (err) {
      toast.error(getApiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  const handleSignupSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password !== confirmPassword) {
      toast.error("Les mots de passe ne correspondent pas.");
      return;
    }
    if (password.length < 8) {
      toast.error("Le mot de passe doit faire au moins 8 caractères.");
      return;
    }
    setLoading(true);
    try {
      const tokens = await register(email.trim().toLowerCase(), password);
      setTokens(tokens.access);
      await checkAuth();
      toast.success("Bienvenue sur Gridar !");
      router.push(nextPath);
    } catch (err) {
      toast.error(getApiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  const goBackToEmail = () => {
    setStep("email");
    setPassword("");
    setConfirmPassword("");
    setOauthProviders([]);
  };

  const handleForgotPassword = async () => {
    if (!email.trim()) {
      toast.error("Entre ton email d'abord.");
      return;
    }
    setLoading(true);
    try {
      const result = await requestPasswordReset(email.trim().toLowerCase());
      toast.success(result.detail);
    } catch (err) {
      toast.error(getApiErrorMessage(err));
    } finally {
      setLoading(false);
    }
  };

  const startOAuth = (provider: "google" | "github") => {
    const redirectUri = `${window.location.origin}/auth/${provider}/callback`;
    if (provider === "google") {
      const clientId = process.env.NEXT_PUBLIC_GOOGLE_OAUTH_CLIENT_ID;
      if (!clientId) {
        toast.error("Google OAuth pas encore configuré (NEXT_PUBLIC_GOOGLE_OAUTH_CLIENT_ID manquant).");
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
      const clientId = process.env.NEXT_PUBLIC_GITHUB_OAUTH_CLIENT_ID;
      if (!clientId) {
        toast.error("GitHub OAuth pas encore configuré (NEXT_PUBLIC_GITHUB_OAUTH_CLIENT_ID manquant).");
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

  // Header copy adapts to the current step.
  const heading =
    step === "email"
      ? "Bienvenue"
      : step === "login"
      ? "Bon retour"
      : step === "oauth-only"
      ? "Continue avec ton compte"
      : "Créer ton compte";

  const subheading =
    step === "email" ? "Entre ton email pour continuer" : email;

  return (
    <div className="min-h-screen bg-background grid lg:grid-cols-2 overflow-hidden">
      {/* Left: form */}
      <div className="flex items-center justify-center p-6 lg:p-12 relative">
        <div className="relative w-full max-w-sm space-y-8">
          <div>
            <div className="flex items-center gap-2 mb-3">
              <GridarMark className="h-7 w-7 text-emerald-400" />
              <span className="font-bold text-xl tracking-tight">Gridar</span>
            </div>
            <h1 className="text-3xl font-bold tracking-tight">{heading}</h1>
            <p className="text-sm text-muted-foreground mt-1 break-all">
              {subheading}
            </p>
          </div>

          {/* OAuth + separator: only on email step. Once the user picks
              email/password, we hide them to keep the flow focused. */}
          {step === "email" && (
            <>
              <div className="space-y-2">
                <Button
                  type="button"
                  variant="outline"
                  className="w-full"
                  onClick={() => startOAuth("google")}
                  disabled={loading}
                >
                  <GoogleIcon />
                  Continuer avec Google
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  className="w-full"
                  onClick={() => startOAuth("github")}
                  disabled={loading}
                >
                  <Github className="h-4 w-4 mr-2" />
                  Continuer avec GitHub
                </Button>
              </div>

              <div className="relative">
                <div className="absolute inset-0 flex items-center">
                  <span className="w-full border-t border-border/60"></span>
                </div>
                <div className="relative flex justify-center text-xs uppercase">
                  <span className="bg-background px-2 text-muted-foreground">
                    ou avec un email
                  </span>
                </div>
              </div>
            </>
          )}

          {/* Step 1 - email only */}
          {step === "email" && (
            <form onSubmit={handleEmailSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="email">Adresse courriel</Label>
                <Input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  autoFocus
                  autoComplete="email"
                  placeholder="toi@exemple.ca"
                />
              </div>
              <Button
                type="submit"
                className="w-full"
                disabled={loading || !email.trim()}
              >
                {loading ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <ArrowRight className="h-4 w-4 mr-2" />
                )}
                Continuer
              </Button>
            </form>
          )}

          {/* Step 2 - existing user, ask password */}
          {step === "login" && (
            <form onSubmit={handleLoginSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="password">Mot de passe</Label>
                <Input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  autoFocus
                  autoComplete="current-password"
                />
              </div>
              <Button type="submit" className="w-full" disabled={loading}>
                {loading ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Connexion...
                  </>
                ) : (
                  "Se connecter"
                )}
              </Button>
              <div className="flex items-center justify-between gap-3 text-xs">
                <button
                  type="button"
                  onClick={goBackToEmail}
                  className="min-h-10 py-2 px-2 -mx-2 text-muted-foreground hover:text-foreground inline-flex items-center gap-1"
                  disabled={loading}
                >
                  <ArrowLeft className="h-3 w-3" />
                  Modifier l&apos;email
                </button>
                <button
                  type="button"
                  onClick={handleForgotPassword}
                  className="min-h-10 py-2 px-2 -mx-2 text-muted-foreground hover:text-foreground"
                  disabled={loading}
                >
                  Mot de passe oublié ?
                </button>
              </div>
            </form>
          )}

          {/* Step 2b - OAuth-only account (no password ever set). Skip the
              password field entirely and surface only the relevant provider(s)
              the user actually has linked. */}
          {step === "oauth-only" && (
            <div className="space-y-4">
              <p className="text-sm text-muted-foreground">
                Ton compte a été créé via un fournisseur externe. Connecte-toi
                avec le même service :
              </p>
              <div className="space-y-2">
                {oauthProviders.includes("google") && (
                  <Button
                    type="button"
                    variant="outline"
                    className="w-full"
                    onClick={() => startOAuth("google")}
                    disabled={loading}
                  >
                    <GoogleIcon />
                    Continuer avec Google
                  </Button>
                )}
                {oauthProviders.includes("github") && (
                  <Button
                    type="button"
                    variant="outline"
                    className="w-full"
                    onClick={() => startOAuth("github")}
                    disabled={loading}
                  >
                    <Github className="h-4 w-4 mr-2" />
                    Continuer avec GitHub
                  </Button>
                )}
              </div>
              <button
                type="button"
                onClick={goBackToEmail}
                className="w-full min-h-10 py-2 text-xs text-muted-foreground hover:text-foreground inline-flex items-center justify-center gap-1"
                disabled={loading}
              >
                <ArrowLeft className="h-3 w-3" />
                Modifier l&apos;email
              </button>
            </div>
          )}

          {/* Step 3 - new user, password + confirm */}
          {step === "signup" && (
            <form onSubmit={handleSignupSubmit} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="password">Mot de passe</Label>
                <Input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  autoFocus
                  autoComplete="new-password"
                  minLength={8}
                />
                <p className="text-xs text-muted-foreground">
                  Minimum 8 caractères.
                </p>
              </div>
              <div className="space-y-2">
                <Label htmlFor="confirm-password">
                  Confirme le mot de passe
                </Label>
                <Input
                  id="confirm-password"
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  required
                  autoComplete="new-password"
                  minLength={8}
                />
              </div>
              <Button type="submit" className="w-full" disabled={loading}>
                {loading ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Connexion...
                  </>
                ) : (
                  "Créer mon compte"
                )}
              </Button>
              <p className="text-xs text-muted-foreground text-center">
                En créant un compte, tu acceptes nos{" "}
                <Link href="/terms" className="underline hover:text-foreground">
                  Conditions
                </Link>{" "}
                et la{" "}
                <Link href="/privacy" className="underline hover:text-foreground">
                  Politique de confidentialité
                </Link>
                .
              </p>
              <button
                type="button"
                onClick={goBackToEmail}
                className="w-full min-h-10 py-2 text-xs text-muted-foreground hover:text-foreground inline-flex items-center justify-center gap-1"
                disabled={loading}
              >
                <ArrowLeft className="h-3 w-3" />
                Modifier l&apos;email
              </button>
            </form>
          )}
        </div>
      </div>

      {/* Right: mockup showcase (desktop only) */}
      <div className="hidden lg:flex relative overflow-hidden bg-zinc-950">
        <div className="relative w-full flex flex-col justify-center px-12 py-16">
          <div className="max-w-md mb-10">
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-emerald-400/30 bg-emerald-400/10 text-emerald-300 text-xs font-mono uppercase tracking-wider mb-6">
              SEO #1 au Québec
            </div>
            <h2 className="text-3xl font-bold tracking-tight text-white leading-tight">
              Reprends ton blog là où tu l&apos;as laissé.
            </h2>
            <p className="text-zinc-400 mt-3 text-sm">
              Articles, audit SEO, suivi Google, génération IA. Tout en
              français-québécois.
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
