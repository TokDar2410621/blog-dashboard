/**
 * Reset password landing page.
 * Hit by the link in the password reset email: /reset-password?uid=...&token=...
 *
 * Reads uid + token from the URL, asks the user for a new password (twice),
 * posts to the backend confirm endpoint, stores the returned JWT, and
 * navigates to /sites. The backend also sets the cookie pair, so the user
 * is fully logged in once we land on /sites.
 */
import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Loader2, AlertCircle, CheckCircle2 } from "lucide-react";
import { GridarMark } from "@/components/GridarMark";
import { confirmPasswordReset, ApiError } from "@/lib/api-client";
import { setTokens } from "@/lib/sites";
import { useAuth } from "@/hooks/useAuth";
import { toast } from "sonner";

export default function ResetPassword() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const { checkAuth } = useAuth();

  const uid = params.get("uid") || "";
  const token = params.get("token") || "";

  const [password, setPassword] = useState("");
  const [confirmPwd, setConfirmPwd] = useState("");
  const [loading, setLoading] = useState(false);
  const [invalid, setInvalid] = useState(!uid || !token);

  useEffect(() => {
    if (!uid || !token) setInvalid(true);
  }, [uid, token]);

  const onSubmit = async (e: React.FormEvent) => {
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
      navigate("/sites", { replace: true });
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
          <Link to="/login">
            <Button>Retour à la connexion</Button>
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
          <CheckCircle2 className="h-10 w-10 text-primary mx-auto mb-3" />
          <h1 className="text-2xl font-bold tracking-tight">Choisir un nouveau mot de passe</h1>
          <p className="text-sm text-muted-foreground mt-2">
            Une fois sauvegardé, tu seras connecté automatiquement.
          </p>
        </div>
        <form onSubmit={onSubmit} className="space-y-4">
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
