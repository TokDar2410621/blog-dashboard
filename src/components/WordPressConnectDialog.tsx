import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useMutation } from "@tanstack/react-query";
import { authFetch } from "@/lib/api-client";
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
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [url, setUrl] = useState("");
  const [discovery, setDiscovery] = useState<DiscoverResult | null>(null);
  const [username, setUsername] = useState("");
  const [appPassword, setAppPassword] = useState("");

  const reset = () => {
    setStep(1);
    setUrl("");
    setDiscovery(null);
    setUsername("");
    setAppPassword("");
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
        throw new Error(data.error || t("wpConnect.notWordPress"));
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
        body: JSON.stringify({ url, username, app_password: appPassword }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || t("wpConnect.connectError"));
      }
      return data as ConnectResult;
    },
    onSuccess: (d) => {
      toast.success(t("wpConnect.connected"));
      handleClose(false);
      navigate(`/dashboard/${d.site.id}`);
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
            {t("wpConnect.title")}
          </DialogTitle>
          <DialogDescription>{t("wpConnect.subtitle")}</DialogDescription>
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

        {/* Step 1 — URL */}
        {step === 1 && (
          <div className="space-y-3">
            <Label className="text-sm">{t("wpConnect.step1Title")}</Label>
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
              {t("wpConnect.step1Hint")}
            </p>
          </div>
        )}

        {/* Step 2 — Instructions for app password */}
        {step === 2 && discovery && (
          <div className="space-y-4">
            <div className="rounded border border-green-500/30 bg-green-500/5 p-3 flex items-start gap-2 text-sm">
              <CheckCircle2 className="h-4 w-4 text-green-600 shrink-0 mt-0.5" />
              <div>
                <strong>{t("wpConnect.detectedTitle")}</strong>
                <div className="text-xs text-muted-foreground mt-1">
                  {discovery.name || t("wpConnect.detectedDefault")}
                  {discovery.post_count !== null && discovery.post_count !== undefined && (
                    <> · {t("wpConnect.detectedPosts", { count: discovery.post_count })}</>
                  )}
                </div>
              </div>
            </div>

            <div className="space-y-2">
              <h4 className="text-sm font-semibold">{t("wpConnect.step2Title")}</h4>
              <ol className="text-sm space-y-2 list-decimal list-inside">
                <li>
                  {t("wpConnect.step2Item1")}{" "}
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
                <li>{t("wpConnect.step2Item2")}</li>
                <li>
                  {t("wpConnect.step2Item3")}
                  <code className="ml-1 px-1.5 py-0.5 rounded bg-muted text-xs font-mono">
                    BlogDashboard
                  </code>
                </li>
                <li>
                  {t("wpConnect.step2Item4")}
                </li>
              </ol>
            </div>

            <Button
              className="w-full"
              variant="outline"
              onClick={() => setStep(3)}
            >
              {t("wpConnect.step2Cta")}
              <ArrowRight className="h-4 w-4 ml-2" />
            </Button>

            <Button
              variant="ghost"
              size="sm"
              className="w-full text-xs"
              onClick={() => setStep(1)}
            >
              ← {t("wpConnect.back")}
            </Button>
          </div>
        )}

        {/* Step 3 — Credentials */}
        {step === 3 && (
          <div className="space-y-3">
            <div className="space-y-2">
              <Label className="text-sm">
                {t("wpConnect.usernameLabel")}
              </Label>
              <Input
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                placeholder="admin"
                autoComplete="off"
              />
              <p className="text-xs text-muted-foreground">
                {t("wpConnect.usernameHint")}
              </p>
            </div>

            <div className="space-y-2">
              <Label className="text-sm">
                {t("wpConnect.appPasswordLabel")}
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
                {t("wpConnect.appPasswordHint")}
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
                  {t("wpConnect.connecting")}
                </>
              ) : (
                <>
                  <CheckCircle2 className="h-4 w-4 mr-2" />
                  {t("wpConnect.connect")}
                </>
              )}
            </Button>

            <Button
              variant="ghost"
              size="sm"
              className="w-full text-xs"
              onClick={() => setStep(2)}
            >
              ← {t("wpConnect.back")}
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
