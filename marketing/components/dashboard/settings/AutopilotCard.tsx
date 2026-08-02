"use client";

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
import { Rocket, Loader2, AlertCircle, Play, Clock, KeyRound, Info } from "lucide-react";
import { toast } from "sonner";
import Link from "next/link";

type AutopilotMode = "refresh_first" | "create_only" | "balanced";

type AutopilotConfig = {
  enabled: boolean;
  weekly_count: number;
  auto_publish: boolean;
  mode: AutopilotMode;
  min_refresh_interval_days: number;
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
  if (absSec < 60) return past ? "à l'instant" : "dans quelques secondes";
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
    mutationFn: async (payload: Partial<Pick<AutopilotConfig, "enabled" | "weekly_count" | "auto_publish" | "mode">>) => {
      const res = await authFetch(`/sites/${siteId}/autopilot/`, {
        method: "PUT",
        body: JSON.stringify(payload),
      });
      if (!res.ok) throw new Error("Erreur sauvegarde autopilote");
      return res.json() as Promise<AutopilotConfig>;
    },
    onSuccess: (data) => {
      queryClient.setQueryData(["autopilot", siteId], data);
      toast.success(data.enabled ? "Autopilote actif" : "Autopilote désactivé");
      setPendingEnabled(null);
    },
    onError: () => {
      toast.error("Sauvegarde échouée");
      setPendingEnabled(null);
    },
  });

  const runNow = useMutation({
    mutationFn: async () => {
      const res = await authFetch(`/sites/${siteId}/autopilot/run/`, { method: "POST" });
      const body = (await res.json()) as RunResult;
      if (!res.ok) {
        const msg = ("error" in body && body.error) || ("skipped_reason" in body && body.skipped_reason) || "Run échoué";
        throw new Error(msg as string);
      }
      return body;
    },
    onSuccess: (data) => {
      if (data.ok) {
        toast.success(`Article créé : "${data.post_title || data.topic}"`);
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

  if (cfg.isError || !cfg.data) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Rocket className="h-5 w-5" />
            Mode autopilote
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center justify-between gap-3">
            <p className="text-sm text-muted-foreground">
              Impossible de charger la configuration autopilote.
            </p>
            <Button size="sm" variant="outline" onClick={() => cfg.refetch()}>
              Réessayer
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  const c = cfg.data;
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
          Gridar génère automatiquement des articles en draft en piochant les sujets parmi tes mots-clés trackés.
          Tu reviews et publies a ta convenance.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-5">
        <div className="flex items-center justify-between gap-4 rounded-lg border p-4">
          <div className="space-y-0.5">
            <Label className="text-base">Activer l'autopilote</Label>
            <p className="text-sm text-muted-foreground">
              {isEnabled ? "Génération programmée active" : "Aucune génération automatique"}
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
                Aucun mot-clé tracké
              </p>
              <p className="text-amber-800 dark:text-amber-300 mt-0.5">
                Ajoute des mots-clés dans <Link href={`/dashboard/${siteId}/positions`} className="underline">Positions</Link> avant d'activer l'autopilote.
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

        <div className="space-y-2">
          <Label>Stratégie</Label>
          <Select
            value={c.mode || "balanced"}
            onValueChange={(v) => save.mutate({ mode: v as AutopilotMode })}
            disabled={save.isPending}
          >
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="balanced">Balanced - 1 refresh / 2 créations (défaut)</SelectItem>
              <SelectItem value="refresh_first">Refresh first - prioriser les articles en perte de trafic</SelectItem>
              <SelectItem value="create_only">Create only - générer uniquement de nouveaux articles</SelectItem>
            </SelectContent>
          </Select>
          <p className="text-xs text-muted-foreground">
            Le mode refresh utilise GSC pour repérer les articles dont les impressions baissent de plus de 20% sur 30j, puis les régénère avec des données à jour. Sans GSC connecté, seul le mode create_only fonctionne.
          </p>
        </div>

        <div className="flex items-center justify-between gap-4 rounded-lg border p-4">
          <div className="space-y-0.5 flex-1">
            <Label className="text-base">Publication automatique</Label>
            <p className="text-sm text-muted-foreground">
              {c.auto_publish
                ? "Les articles sont publiés directement (zéro review)"
                : "Les articles atterrissent en draft pour review"}
            </p>
          </div>
          <Switch
            checked={c.auto_publish}
            disabled={save.isPending}
            onCheckedChange={(v) => save.mutate({ auto_publish: v })}
          />
        </div>

        {c.auto_publish && (
          <div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm dark:border-amber-900 dark:bg-amber-950">
            <AlertCircle className="h-4 w-4 shrink-0 mt-0.5 text-amber-600" />
            <div className="flex-1">
              <p className="font-medium text-amber-900 dark:text-amber-200">
                Mode publication directe actif
              </p>
              <p className="text-amber-800 dark:text-amber-300 mt-0.5">
                Les articles partent en prod sans relecture. Vérifie ton prompt et ta mémoire site avant de laisser tourner. Un redeploy Vercel est déclenché automatiquement après chaque publication.
              </p>
            </div>
          </div>
        )}

        <div className="grid grid-cols-2 gap-3 text-sm">
          <div className="rounded-lg border p-3">
            <div className="flex items-center gap-1.5 text-muted-foreground mb-1">
              <KeyRound className="h-3.5 w-3.5" />
              <span>Mots-clés dispo</span>
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
            <Badge variant="secondary">Prêt à générer maintenant</Badge>
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
            Utile pour tester. Le sujet est pioché au hasard parmi les mots-clés trackés sans article existant.
          </p>
        </div>

        <div className="flex items-start gap-2 rounded-lg border border-blue-200 bg-blue-50 p-3 text-xs dark:border-blue-900 dark:bg-blue-950">
          <Info className="h-4 w-4 shrink-0 mt-0.5 text-blue-600" />
          <div className="flex-1 space-y-1">
            <p className="font-medium text-blue-900 dark:text-blue-200">
              Declenchement automatique
            </p>
            <p className="text-blue-800 dark:text-blue-300">
              L'autopilote tourne automatiquement chaque heure via un cron Railway. Si tes drafts n'apparaissent pas, c'est probablement que le service cron `run_autopilot` n'a pas été créé sur Railway. Voir `backend/SCHEDULED_JOBS.md` pour la procédure (5 minutes, ~$1-3/mois).
            </p>
            <p className="text-blue-800 dark:text-blue-300">
              En attendant, le bouton "Lancer maintenant" ci-dessus marche toujours.
            </p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
