"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { authFetch } from "@/lib/sites-api";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Globe,
  Loader2,
  CheckCircle2,
  AlertCircle,
  ArrowRight,
  ExternalLink,
} from "lucide-react";
import { toast } from "sonner";
import { BrandingPreview } from "@/components/BrandingPreview";
import { useConfetti } from "@/hooks/useConfetti";

type DiscoverResult = {
  valid_wp: boolean;
  normalized_url?: string;
  name?: string;
  description?: string;
  post_count?: number | null;
  error?: string;
};

type ConnectResult = {
  site: { id: number; name: string; domain: string; wp_url: string };
  wp_user: { username: string; name: string; roles: string[] };
  discovery: { site_name: string; post_count: number | null };
};

type Props = {
  open: boolean;
  onOpenChange: (o: boolean) => void;
};

export function WordPressConnectDialog({ open, onOpenChange }: Props) {
  const router = useRouter();
  const fireConfetti = useConfetti();
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [url, setUrl] = useState("");
  const [discovery, setDiscovery] = useState<DiscoverResult | null>(null);
  const [username, setUsername] = useState("");
  const [appPassword, setAppPassword] = useState("");

  const [themeConfig, setThemeConfig] = useState<Record<string, string> | null>(null);

  const reset = () => {
    setStep(1);
    setUrl("");
    setDiscovery(null);
    setUsername("");
    setAppPassword("");
    setThemeConfig(null);
  };

  const handleClose = (o: boolean) => {
    if (!o) reset();
    onOpenChange(o);
  };

  const discoverMutation = useMutation({
    mutationFn: async () => {
      const res = await authFetch("/wp/discover/", {
        method: "POST",
        body: JSON.stringify({ url }),
      });
      const data = (await res.json()) as DiscoverResult;
      if (!res.ok || !data.valid_wp) {
        throw new Error(data.error || "Ce site n'est pas WordPress ou la REST API est désactivée.");
      }
      return data;
    },
    onSuccess: (d) => {
      setDiscovery(d);
      if (d.normalized_url) setUrl(d.normalized_url);
      setStep(2);
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const connectMutation = useMutation({
    mutationFn: async () => {
      const res = await authFetch("/wp/connect/", {
        method: "POST",
        body: JSON.stringify({
          url,
          username,
          app_password: appPassword,
          theme_config: themeConfig || undefined,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || "Erreur de connexion");
      }
      return data as ConnectResult;
    },
    onSuccess: (d) => {
      toast.success("Site WordPress connecté !");
      fireConfetti();
      handleClose(false);
      router.push(`/dashboard/${d.site.id}`);
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const wpProfileUrl = url ? `${url.replace(/\/$/, "")}/wp-admin/profile.php` : "#";

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Globe className="h-5 w-5" />
            Connecter ton site WordPress
          </DialogTitle>
          <DialogDescription>
            3 étapes : URL, génération d&apos;un Application Password, connexion. Aucun plugin à installer.
          </DialogDescription>
        </DialogHeader>

        {/* Stepper */}
        <div className="flex items-center gap-2 text-xs">
          {[1, 2, 3].map((n) => (
            <div
              key={n}
              className={`flex items-center gap-1 ${
                step >= n ? "text-primary" : "text-muted-foreground"
              }`}
            >
              <span
                className={`h-5 w-5 rounded-full flex items-center justify-center text-[10px] font-bold ${
                  step >= n
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted"
                }`}
              >
                {n}
              </span>
              {n < 3 && <ArrowRight className="h-3 w-3" />}
            </div>
          ))}
        </div>

        {/* Step 1 - URL */}
        {step === 1 && (
          <div className="space-y-3">
            <Label className="text-sm">URL de ton site WordPress</Label>
            <div className="flex gap-2">
              <Input
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://monsite.ca"
                onKeyDown={(e) => e.key === "Enter" && discoverMutation.mutate()}
              />
              <Button
                onClick={() => discoverMutation.mutate()}
                disabled={discoverMutation.isPending || !url.trim()}
              >
                {discoverMutation.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <ArrowRight className="h-4 w-4" />
                )}
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">
              Ex: https://monrestaurant.ca (sans /wp-admin). On va détecter automatiquement WordPress.
            </p>
          </div>
        )}

        {/* Step 2 - Instructions for app password */}
        {step === 2 && discovery && (
          <div className="space-y-4">
            <div className="rounded border border-green-500/30 bg-green-500/5 p-3 flex items-start gap-2 text-sm">
              <CheckCircle2 className="h-4 w-4 text-green-600 shrink-0 mt-0.5" />
              <div>
                <strong>WordPress détecté !</strong>
                <div className="text-xs text-muted-foreground mt-1">
                  {discovery.name || "Site WordPress"}
                  {discovery.post_count !== null && discovery.post_count !== undefined && (
                    <> · {discovery.post_count} articles publiés</>
                  )}
                </div>
              </div>
            </div>

            <BrandingPreview
              domain={discovery.normalized_url || url}
              onAppliedChange={(tc) => setThemeConfig(tc)}
            />

            <div className="space-y-2">
              <h4 className="text-sm font-semibold">Crée un Application Password (1 minute)</h4>
              <ol className="text-sm space-y-2 list-decimal list-inside">
                <li>
                  Va sur{" "}
                  <a
                    href={wpProfileUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary hover:underline inline-flex items-center gap-1"
                  >
                    /wp-admin/profile.php
                    <ExternalLink className="h-3 w-3" />
                  </a>
                </li>
                <li>Descends jusqu&apos;à la section &quot;Application Passwords&quot;.</li>
                <li>
                  Saisis un nom d&apos;application :
                  <code className="ml-1 px-1.5 py-0.5 rounded bg-muted text-xs font-mono">
                    BlogDashboard
                  </code>
                </li>
                <li>
                  Clique &quot;Add New Application Password&quot;. Copie le mot de passe généré (24 caractères).
                </li>
              </ol>
            </div>

            <Button
              className="w-full"
              variant="outline"
              onClick={() => setStep(3)}
            >
              J&apos;ai généré mon Application Password
              <ArrowRight className="h-4 w-4 ml-2" />
            </Button>

            <Button
              variant="ghost"
              size="sm"
              className="w-full text-xs"
              onClick={() => setStep(1)}
            >
              ← Retour
            </Button>
          </div>
        )}

        {/* Step 3 - Credentials */}
        {step === 3 && (
          <div className="space-y-3">
            <div className="space-y-2">
              <Label className="text-sm">
                Username WordPress
              </Label>
              <Input
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="admin"
                autoComplete="off"
              />
              <p className="text-xs text-muted-foreground">
                Le nom d&apos;utilisateur de ton compte admin WordPress.
              </p>
            </div>

            <div className="space-y-2">
              <Label className="text-sm">
                Application Password
              </Label>
              <Input
                value={appPassword}
                onChange={(e) => setAppPassword(e.target.value)}
                placeholder="xxxx xxxx xxxx xxxx xxxx xxxx"
                autoComplete="off"
                type="text"
                className="font-mono text-xs"
              />
              <p className="text-xs text-muted-foreground">
                Les 24 caractères séparés par espaces (collage exact, espaces inclus).
              </p>
            </div>

            {connectMutation.isError && (
              <div className="rounded border border-red-500/30 bg-red-500/5 p-2 flex items-start gap-2 text-xs text-red-700 dark:text-red-400">
                <AlertCircle className="h-3 w-3 shrink-0 mt-0.5" />
                <span>{(connectMutation.error as Error).message}</span>
              </div>
            )}

            <Button
              className="w-full"
              onClick={() => connectMutation.mutate()}
              disabled={
                connectMutation.isPending || !username.trim() || !appPassword.trim()
              }
              size="lg"
            >
              {connectMutation.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Connexion en cours...
                </>
              ) : (
                <>
                  <CheckCircle2 className="h-4 w-4 mr-2" />
                  Connecter
                </>
              )}
            </Button>

            <Button
              variant="ghost"
              size="sm"
              className="w-full text-xs"
              onClick={() => setStep(2)}
            >
              ← Retour
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
