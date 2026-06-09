"use client";

import { Suspense, useState, useEffect } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { GridarMark } from "@/components/GridarMark";
import { Loader2, ArrowRight } from "lucide-react";
import { useAuth } from "@/context/AuthContext";
import { login as loginApi } from "@/lib/api-client";
import { setTokens } from "@/lib/auth-storage";

function LoginForm() {
  const router = useRouter();
  const search = useSearchParams();
  const next = search?.get("next") || "/sites";
  const { checkAuth, isAuthenticated, isLoading: authLoading } = useAuth();

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!authLoading && isAuthenticated) {
      router.replace(next);
    }
  }, [isAuthenticated, authLoading, next, router]);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username || !password) return;
    setSubmitting(true);
    try {
      const tokens = await loginApi(username, password);
      setTokens(tokens.access);
      await checkAuth();
      router.push(next);
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Identifiants invalides",
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="relative">
      {/* Subtle emerald aura behind the form card, identical mood to landing mockups. */}
      <div className="absolute -inset-px rounded-2xl bg-gradient-to-br from-emerald-500/20 via-cyan-500/10 to-transparent blur-xl pointer-events-none" />
      <div className="relative rounded-2xl border border-white/10 bg-zinc-900/80 backdrop-blur-xl overflow-hidden">
        <div className="flex items-center justify-between px-4 py-2.5 border-b border-white/5">
          <div className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full bg-zinc-700" />
            <span className="h-2.5 w-2.5 rounded-full bg-zinc-700" />
            <span className="h-2.5 w-2.5 rounded-full bg-zinc-700" />
          </div>
          <span className="text-[10px] font-mono uppercase tracking-wider text-emerald-400">
            connexion sécurisée
          </span>
          <span />
        </div>
        <div className="p-6">
          <h1 className="text-2xl font-bold text-zinc-100 mb-1">Connexion</h1>
          <p className="text-sm text-zinc-400 mb-6">
            Retrouve ton tableau de bord SEO en un clic.
          </p>
          <form onSubmit={onSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="username" className="text-zinc-300">
                Utilisateur ou courriel
              </Label>
              <Input
                id="username"
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                disabled={submitting}
                required
                autoFocus
                className="bg-zinc-950/60 border-white/10 text-zinc-100 placeholder:text-zinc-500 focus-visible:ring-emerald-500/40 focus-visible:border-emerald-500/40"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password" className="text-zinc-300">
                Mot de passe
              </Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={submitting}
                required
                className="bg-zinc-950/60 border-white/10 text-zinc-100 placeholder:text-zinc-500 focus-visible:ring-emerald-500/40 focus-visible:border-emerald-500/40"
              />
            </div>
            <Button
              type="submit"
              disabled={submitting || !username || !password}
              className="w-full bg-white text-zinc-950 hover:bg-zinc-200 h-11 motion-safe:transition-transform motion-safe:hover:-translate-y-0.5"
            >
              {submitting ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Connexion...
                </>
              ) : (
                <>
                  Se connecter
                  <ArrowRight className="h-4 w-4 ml-2" />
                </>
              )}
            </Button>
          </form>
        </div>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <div className="relative min-h-screen bg-zinc-950 text-zinc-100 overflow-hidden">
      {/* Background grid + emerald top glow, same recipe as the landing hero. */}
      <div
        className="fixed inset-0 z-0 opacity-[0.04] pointer-events-none"
        style={{
          backgroundImage:
            "linear-gradient(to right, rgb(255 255 255 / 1) 1px, transparent 1px), linear-gradient(to bottom, rgb(255 255 255 / 1) 1px, transparent 1px)",
          backgroundSize: "48px 48px",
        }}
      />
      <div className="fixed inset-x-0 top-0 h-[40vh] z-0 pointer-events-none bg-gradient-to-b from-emerald-500/[0.05] via-transparent to-transparent" />
      <div className="pointer-events-none absolute inset-0 -z-0 overflow-hidden">
        <div className="absolute top-0 left-1/2 -translate-x-1/2 h-[600px] w-[1000px] rounded-full bg-gradient-to-br from-emerald-500/20 via-cyan-500/10 to-transparent blur-3xl" />
      </div>

      <main className="relative z-10 min-h-screen flex items-center justify-center px-4 py-16">
        <div className="w-full max-w-md space-y-6">
          <Link
            href="/"
            className="flex items-center justify-center gap-2 group"
          >
            <GridarMark className="h-9 w-9 text-emerald-400 motion-safe:transition-transform motion-safe:group-hover:scale-105" />
            <span className="text-2xl font-semibold tracking-tight text-zinc-100">
              Gridar
            </span>
          </Link>

          <Suspense
            fallback={
              <div className="flex justify-center py-12">
                <Loader2 className="h-6 w-6 animate-spin text-zinc-400" />
              </div>
            }
          >
            <LoginForm />
          </Suspense>

          <p className="text-center text-xs text-zinc-500">
            Migration Next.js en cours. La version complète (OAuth Google, reset password, lazy signup) revient bientôt.
          </p>
        </div>
      </main>
    </div>
  );
}
