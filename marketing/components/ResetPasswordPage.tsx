"use client";

/**
 * Reset password page (port of the SPA's src/pages/ResetPassword.tsx).
 *
 * Two modes:
 *  - confirm: hit by the link in the password reset email
 *    (/reset-password?uid=...&token=...). Asks for a new password (twice),
 *    posts to the backend confirm endpoint, stores the returned JWT, and
 *    navigates to /sites. The backend also sets the cookie pair, so the
 *    user is fully logged in once we land on /sites.
 *  - request: no uid/token in the URL. Shows an email form that triggers
 *    the reset email (enumeration-safe on the backend), mirroring the
 *    "Mot de passe oublié ?" flow the SPA exposes on /login.
 *
 * A half-broken link (uid without token or vice versa) renders the same
 * "Lien invalide ou expiré" screen as the SPA, which is also shown when
 * the confirm endpoint rejects the token with a 400.
 */
import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loader2, AlertCircle, CheckCircle2, KeyRound, MailCheck } from "lucide-react";
import { GridarMark } from "@/components/GridarMark";
import {
  confirmPasswordReset,
  requestPasswordReset,
  ApiError,
} from "@/lib/api-client";
import { setTokens } from "@/lib/auth-storage";
import { useAuth } from "@/context/AuthContext";
import { toast } from "sonner";

export function ResetPasswordPage() {
  const params = useSearchParams();
  const router = useRouter();
  const { checkAuth } = useAuth();

  const uid = params.get("uid") || "";
  const token = params.get("token") || "";

  // confirm mode only when BOTH email-link params are present.
  const isConfirmMode = Boolean(uid && token);

  const [password, setPassword] = useState("");
  const [confirmPwd, setConfirmPwd] = useState("");
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  // Detail message returned by the backend after a successful reset request.
  const [sentDetail, setSentDetail] = useState<string | null>(null);
  // Partial params (uid XOR token) = broken link, same as the SPA's
  // `!uid || !token` guard, except the "no params at all" case now falls
  // through to the request form instead.
  const [invalid, setInvalid] = useState(
    Boolean(uid || token) && !(uid && token),
  );

  useEffect(() => {
    if ((uid || token) && !(uid && token)) setInvalid(true);
  }, [uid, token]);

  const onConfirmSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password !== confirmPwd) {
      toast.error("Les mots de passe ne correspondent pas.");
      return;
    }
    if (password.length < 8) {
      toast.error("Le mot de passe doit faire au moins 8 caractères.");
      return;
    }
    setLoading(true);
    try {
      const tokens = await confirmPasswordReset(uid, token, password);
      setTokens(tokens.access);
      await checkAuth();
      toast.success("Mot de passe mis à jour. Tu es connecté.");
      router.replace("/sites");
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "Lien invalide ou expiré.";
      toast.error(msg);
      if (err instanceof ApiError && err.status === 400) {
        setInvalid(true);
      }
    } finally {
      setLoading(false);
    }
  };

  const onRequestSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim()) {
      toast.error("Entre ton email d'abord.");
      return;
    }
    setLoading(true);
    try {
      const result = await requestPasswordReset(email.trim().toLowerCase());
      toast.success(result.detail);
      setSentDetail(
        result.detail ||
          "Si un compte existe avec cet email, tu recevras un lien sous peu.",
      );
    } catch (err) {
      const msg =
        err instanceof ApiError ? err.message : "La demande a échoué. Réessaie.";
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  if (invalid) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center p-4">
        <div className="max-w-sm w-full text-center space-y-4">
          <AlertCircle className="h-10 w-10 text-destructive mx-auto" />
          <h1 className="text-xl font-semibold">Lien invalide ou expiré</h1>
          <p className="text-sm text-muted-foreground">
            Ton lien de réinitialisation n'est plus valable. Demande un nouveau
            lien depuis la page de connexion.
          </p>
          <Link href="/login">
            <Button>Retour à la connexion</Button>
          </Link>
        </div>
      </div>
    );
  }

  if (isConfirmMode) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center p-4">
        <div className="w-full max-w-sm space-y-6">
          <div className="flex items-center justify-center gap-2 mb-4">
            <GridarMark className="h-7 w-7 text-emerald-400" />
            <span className="font-bold text-xl tracking-tight">Gridar</span>
          </div>
          <div className="text-center">
            <CheckCircle2 className="h-10 w-10 text-primary mx-auto mb-3" />
            <h1 className="text-2xl font-bold tracking-tight">Choisir un nouveau mot de passe</h1>
            <p className="text-sm text-muted-foreground mt-2">
              Une fois sauvegardé, tu seras connecté automatiquement.
            </p>
          </div>
          <form onSubmit={onConfirmSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="password">Nouveau mot de passe</Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoFocus
                minLength={8}
                autoComplete="new-password"
              />
              <p className="text-xs text-muted-foreground">Minimum 8 caractères.</p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="confirm">Confirmer</Label>
              <Input
                id="confirm"
                type="password"
                value={confirmPwd}
                onChange={(e) => setConfirmPwd(e.target.value)}
                required
                minLength={8}
                autoComplete="new-password"
              />
            </div>
            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  En cours...
                </>
              ) : (
                "Sauvegarder et me connecter"
              )}
            </Button>
          </form>
        </div>
      </div>
    );
  }

  // Request mode: no uid/token in the URL. Email form -> reset email.
  if (sentDetail) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center p-4">
        <div className="max-w-sm w-full text-center space-y-4">
          <MailCheck className="h-10 w-10 text-primary mx-auto" />
          <h1 className="text-xl font-semibold">Email envoyé</h1>
          <p className="text-sm text-muted-foreground">{sentDetail}</p>
          <Link href="/login">
            <Button variant="outline">Retour à la connexion</Button>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <div className="w-full max-w-sm space-y-6">
        <div className="flex items-center justify-center gap-2 mb-4">
          <GridarMark className="h-7 w-7 text-emerald-400" />
          <span className="font-bold text-xl tracking-tight">Gridar</span>
        </div>
        <div className="text-center">
          <KeyRound className="h-10 w-10 text-primary mx-auto mb-3" />
          <h1 className="text-2xl font-bold tracking-tight">Mot de passe oublié ?</h1>
          <p className="text-sm text-muted-foreground mt-2">
            Entre ton email et on t'envoie un lien de réinitialisation.
          </p>
        </div>
        <form onSubmit={onRequestSubmit} className="space-y-4">
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
          <Button type="submit" className="w-full" disabled={loading || !email.trim()}>
            {loading ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                En cours...
              </>
            ) : (
              "Envoyer le lien"
            )}
          </Button>
        </form>
        <div className="text-center">
          <Link
            href="/login"
            className="text-xs text-muted-foreground hover:text-foreground"
          >
            Retour à la connexion
          </Link>
        </div>
      </div>
    </div>
  );
}
