import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { authFetch } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Rocket, Loader2, AlertCircle, Play, Clock, KeyRound } from "lucide-react";
import { toast } from "sonner";
import { Link } from "react-router-dom";

type AutopilotConfig = {
  enabled: boolean;
  weekly_count: number;
  last_run_at: string | null;
  last_error: string;
  next_run_at: string | null;
  is_due: boolean;
  tracked_keywords_count: number;
  ready_to_run: boolean;
};

type RunResult =
  | { ok: true; topic: string; keyword_id: number; post_id: number | null; post_title: string | null }
  | { ok: false; skipped_reason?: string; error?: string };

function formatRelative(iso: string | null): string {
  if (!iso) return "jamais";
  const d = new Date(iso);
  const now = new Date();
  const diffMs = d.getTime() - now.getTime();
  const absSec = Math.abs(diffMs) / 1000;
  const past = diffMs < 0;
  if (absSec < 60) return past ? "a l'instant" : "dans quelques secondes";
  if (absSec < 3600) {
    const m = Math.round(absSec / 60);
    return past ? `il y a ${m} min` : `dans ${m} min`;
  }
  if (absSec < 86400) {
    const h = Math.round(absSec / 3600);
    return past ? `il y a ${h}h` : `dans ${h}h`;
  }
  const days = Math.round(absSec / 86400);
  return past ? `il y a ${days} j` : `dans ${days} j`;
}

export function AutopilotCard({ siteId }: { siteId: string | number }) {
  const queryClient = useQueryClient();
  const [pendingEnabled, setPendingEnabled] = useState<boolean | null>(null);

  const cfg = useQuery<AutopilotConfig>({
    queryKey: ["autopilot", siteId],
    queryFn: async () => {
      const res = await authFetch(`/sites/${siteId}/autopilot/`);
      if (!res.ok) throw new Error("Erreur chargement autopilote");
      return res.json();
    },
  });

  const save = useMutation({
    mutationFn: async (payload: Partial<Pick<AutopilotConfig, "enabled" | "weekly_count">>) => {
      const res = await authFetch(`/sites/${siteId}/autopilot/`, {
        method: "PUT",
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error("Erreur sauvegarde autopilote");
      return res.json() as Promise<AutopilotConfig>;
    },
    onSuccess: (data) => {
      queryClient.setQueryData(["autopilot", siteId], data);
      toast.success(data.enabled ? "Autopilote actif" : "Autopilote desactive");
      setPendingEnabled(null);
    },
    onError: () => {
      toast.error("Sauvegarde echouee");
      setPendingEnabled(null);
    },
  });

  const runNow = useMutation({
    mutationFn: async () => {
      const res = await authFetch(`/sites/${siteId}/autopilot/run/`, { method: "POST" });
      const body = (await res.json()) as RunResult;
      if (!res.ok) {
        const msg = ("error" in body && body.error) || ("skipped_reason" in body && body.skipped_reason) || "Run echoue";
        throw new Error(msg as string);
      }
      return body;
    },
    onSuccess: (data) => {
      if (data.ok) {
        toast.success(`Article cree : "${data.post_title || data.topic}"`);
      }
      queryClient.invalidateQueries({ queryKey: ["autopilot", siteId] });
      queryClient.invalidateQueries({ queryKey: ["site-posts"] });
    },
    onError: (e: Error) => {
      toast.error(e.message);
    },
  });

  if (cfg.isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Rocket className="h-5 w-5" />
            Mode autopilote
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Loader2 className="h-4 w-4 animate-spin" />
        </CardContent>
      </Card>
    );
  }

  const c = cfg.data!;
  const isEnabled = pendingEnabled ?? c.enabled;
  const noKeywords = c.tracked_keywords_count === 0;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg flex items-center gap-2">
          <Rocket className="h-5 w-5" />
          Mode autopilote
        </CardTitle>
        <CardDescription>
          Gridar genere automatiquement des articles en draft en piochant les sujets parmi tes mots-cles trackes.
          Tu reviews et publies a ta convenance.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="flex items-center justify-between gap-4 rounded-lg border p-4">
          <div className="space-y-0.5">
            <Label className="text-base">Activer l'autopilote</Label>
            <p className="text-sm text-muted-foreground">
              {isEnabled ? "Generation programmee active" : "Aucune generation automatique"}
            </p>
          </div>
          <Switch
            checked={isEnabled}
            disabled={save.isPending || (noKeywords && !c.enabled)}
            onCheckedChange={(v) => {
              setPendingEnabled(v);
              save.mutate({ enabled: v });
            }}
          />
        </div>

        {noKeywords && (
          <div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm dark:border-amber-900 dark:bg-amber-950">
            <AlertCircle className="h-4 w-4 shrink-0 mt-0.5 text-amber-600" />
            <div className="flex-1">
              <p className="font-medium text-amber-900 dark:text-amber-200">
                Aucun mot-cle tracke
              </p>
              <p className="text-amber-800 dark:text-amber-300 mt-0.5">
                Ajoute des mots-cles dans <Link to={`/dashboard/sites/${siteId}/positions`} className="underline">Positions</Link> avant d'activer l'autopilote.
              </p>
            </div>
          </div>
        )}

        <div className="space-y-2">
          <Label>Cadence</Label>
          <Select
            value={String(c.weekly_count)}
            onValueChange={(v) => save.mutate({ weekly_count: parseInt(v, 10) })}
            disabled={save.isPending}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="1">1 article / semaine</SelectItem>
              <SelectItem value="2">2 articles / semaine</SelectItem>
              <SelectItem value="3">3 articles / semaine</SelectItem>
              <SelectItem value="5">5 articles / semaine</SelectItem>
              <SelectItem value="7">1 article / jour</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="grid grid-cols-2 gap-3 text-sm">
          <div className="rounded-lg border p-3">
            <div className="flex items-center gap-1.5 text-muted-foreground mb-1">
              <KeyRound className="h-3.5 w-3.5" />
              <span>Mots-cles dispo</span>
            </div>
            <p className="text-2xl font-semibold">{c.tracked_keywords_count}</p>
          </div>
          <div className="rounded-lg border p-3">
            <div className="flex items-center gap-1.5 text-muted-foreground mb-1">
              <Clock className="h-3.5 w-3.5" />
              <span>Prochain run</span>
            </div>
            <p className="text-sm font-medium">
              {c.enabled ? formatRelative(c.next_run_at) : "-"}
            </p>
          </div>
        </div>

        <div className="space-y-2 text-sm">
          <div className="flex items-center justify-between">
            <span className="text-muted-foreground">Dernier run :</span>
            <span className="font-medium">{formatRelative(c.last_run_at)}</span>
          </div>
          {c.last_error && (
            <div className="flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/5 p-2 text-xs">
              <AlertCircle className="h-3.5 w-3.5 shrink-0 mt-0.5 text-destructive" />
              <span className="font-mono">{c.last_error}</span>
            </div>
          )}
          {c.is_due && c.enabled && c.ready_to_run && (
            <Badge variant="secondary">Pret a generer maintenant</Badge>
          )}
        </div>

        <div className="border-t pt-4">
          <Button
            onClick={() => runNow.mutate()}
            disabled={runNow.isPending || noKeywords}
            className="w-full"
            variant="outline"
          >
            {runNow.isPending ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Generation en cours (1-2 min)...
              </>
            ) : (
              <>
                <Play className="h-4 w-4 mr-2" />
                Lancer maintenant (1 article)
              </>
            )}
          </Button>
          <p className="text-xs text-muted-foreground mt-2">
            Utile pour tester. Le sujet est pioche au hasard parmi les mots-cles trackes sans article existant.
          </p>
        </div>
      </CardContent>
    </Card>
  );
}
