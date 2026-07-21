"use client";

/**
 * AiVisibility - track how a site is mentioned across LLM responses
 * (ChatGPT, Perplexity, Gemini, SearchGPT, Claude).
 *
 * V1 wires the new /v1/sites/<id>/ai-visibility/* endpoints. The backend run
 * endpoint currently fabricates plausible mocked results so the dashboard UX
 * can be validated without burning external LLM API budget. Real LLM calls
 * land in V2.
 */
import { useMemo, useState } from "react";
import { useParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Sparkles,
  Loader2,
  Plus,
  RefreshCw,
  Brain,
  Quote,
  ExternalLink,
  Globe,
  AlertCircle,
  TrendingUp,
  TrendingDown,
  Minus,
} from "lucide-react";
import { toast } from "sonner";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

import { PageBreadcrumb } from "@/components/PageBreadcrumb";
import {
  RangeSelector,
  type RangeValue,
} from "@/components/charts/RangeSelector";
import { EngineBadge, ALL_ENGINES } from "@/components/aivis/EngineBadge";

import {
  aiVisibilitySummary,
  createAiVisibilityPrompt,
  listAiVisibilityPrompts,
  runAiVisibility,
  suggestAiVisibilityPrompts,
  type AiVisibilityEngine,
  type AiVisibilitySummary,
  type AiVisibilityPrompt,
  type AiVisibilityPromptSuggestion,
} from "@/lib/api-client";

// Mock sparklines so the hero strip isn't empty before the user runs any check.
// Real values will land once the backend tracks daily snapshots (V2).
function mockSparkline(seed: number, len = 12): number[] {
  const out: number[] = [];
  let v = seed;
  for (let i = 0; i < len; i++) {
    v = Math.max(0, v + Math.round((Math.random() - 0.45) * 8));
    out.push(v);
  }
  return out;
}

function Sparkline({ data, color }: { data: number[]; color: string }) {
  if (!data.length) return null;
  const max = Math.max(...data, 1);
  const min = Math.min(...data, 0);
  const range = Math.max(1, max - min);
  const points = data
    .map((v, i) => {
      const x = (i / (data.length - 1)) * 100;
      const y = 100 - ((v - min) / range) * 100;
      return `${x},${y}`;
    })
    .join(" ");
  return (
    <svg
      viewBox="0 0 100 100"
      preserveAspectRatio="none"
      className="h-8 w-full opacity-70"
      aria-hidden
    >
      <polyline
        fill="none"
        stroke={color}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        points={points}
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}

function ScoreGauge({ score }: { score: number }) {
  // Half-circle SVG gauge, emerald -> amber -> red bands.
  const clamped = Math.max(0, Math.min(100, score));
  const angle = (clamped / 100) * 180;
  const r = 64;
  const cx = 80;
  const cy = 80;
  const start = { x: cx - r, y: cy };
  const rad = ((180 - angle) * Math.PI) / 180;
  const end = { x: cx + r * Math.cos(rad), y: cy - r * Math.sin(rad) };
  const largeArc = angle > 180 ? 1 : 0;
  const arcPath = `M ${start.x} ${start.y} A ${r} ${r} 0 ${largeArc} 1 ${end.x} ${end.y}`;

  const color =
    clamped >= 70
      ? "rgb(16 185 129)"
      : clamped >= 40
        ? "rgb(245 158 11)"
        : "rgb(239 68 68)";

  return (
    <div className="relative w-40 h-24">
      <svg viewBox="0 0 160 90" className="w-full h-full">
        <path
          d={`M 16 80 A 64 64 0 0 1 144 80`}
          fill="none"
          stroke="rgb(63 63 70)"
          strokeWidth="10"
          strokeLinecap="round"
        />
        <path
          d={arcPath}
          fill="none"
          stroke={color}
          strokeWidth="10"
          strokeLinecap="round"
        />
      </svg>
      <div className="absolute inset-x-0 bottom-0 text-center">
        <div className="text-3xl font-bold tabular-nums">{clamped.toFixed(0)}</div>
        <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
          / 100
        </div>
      </div>
    </div>
  );
}

function DeltaBadge({ delta }: { delta: number }) {
  const isPos = delta > 0;
  const isNeg = delta < 0;
  const Icon = isPos ? TrendingUp : isNeg ? TrendingDown : Minus;
  return (
    <Badge
      variant={isPos ? "default" : isNeg ? "destructive" : "secondary"}
      className={
        isPos ? "bg-emerald-500 text-white hover:bg-emerald-500/90" : undefined
      }
    >
      <Icon className="h-3 w-3" />
      {isPos ? "+" : ""}
      {delta.toFixed(1)} pts
    </Badge>
  );
}

const INTENT_OPTIONS: { value: string; label: string }[] = [
  { value: "informational", label: "Informationnel" },
  { value: "commercial", label: "Commercial / Comparatif" },
  { value: "transactional", label: "Transactionnel" },
  { value: "navigational", label: "Navigationnel" },
  { value: "local", label: "Local" },
];

export default function AiVisibilityPage() {
  const { siteId } = useParams<{ siteId: string }>();
  const sid = Number(siteId);
  const qc = useQueryClient();

  const [range, setRange] = useState<RangeValue>("30d");

  const summaryQuery = useQuery<AiVisibilitySummary>({
    queryKey: ["ai-visibility-summary", sid],
    queryFn: () => aiVisibilitySummary(sid),
    enabled: !Number.isNaN(sid),
  });

  const promptsQuery = useQuery<{
    results: AiVisibilityPrompt[];
    count: number;
  }>({
    queryKey: ["ai-visibility-prompts", sid],
    queryFn: () => listAiVisibilityPrompts(sid),
    enabled: !Number.isNaN(sid),
  });

  const [promptText, setPromptText] = useState("");
  const [intent, setIntent] = useState<string>("informational");
  const [language, setLanguage] = useState<"fr" | "en" | "es">("fr");

  const createMutation = useMutation({
    mutationFn: () =>
      createAiVisibilityPrompt(sid, {
        prompt: promptText.trim(),
        target_intent: intent,
        language,
      }),
    onSuccess: () => {
      toast.success("Prompt ajoute. Lance un check pour le tester.");
      setPromptText("");
      qc.invalidateQueries({ queryKey: ["ai-visibility-prompts", sid] });
    },
    onError: (err: Error) => {
      toast.error(err.message || "Echec de la creation du prompt.");
    },
  });

  // AI-suggested prompts: Claude proposes questions a prospect would ask an LLM,
  // adapted to the site's market. The user reviews and adds the ones they want.
  const [suggestions, setSuggestions] = useState<AiVisibilityPromptSuggestion[]>([]);

  const suggestMutation = useMutation({
    mutationFn: () => suggestAiVisibilityPrompts(sid),
    onSuccess: (data) => {
      setSuggestions(data.prompts || []);
      if (!data.prompts?.length) toast("Aucune suggestion generee.");
    },
    onError: (err: Error) =>
      toast.error(err.message || "Echec des suggestions."),
  });

  const addSuggestionMutation = useMutation({
    mutationFn: (s: AiVisibilityPromptSuggestion) =>
      createAiVisibilityPrompt(sid, {
        prompt: s.prompt,
        target_intent: s.target_intent,
        language: (["fr", "en", "es"].includes(s.language)
          ? s.language
          : "fr") as "fr" | "en" | "es",
      }),
    onSuccess: (_data, s) => {
      toast.success("Prompt ajoute.");
      setSuggestions((prev) => prev.filter((x) => x.prompt !== s.prompt));
      qc.invalidateQueries({ queryKey: ["ai-visibility-prompts", sid] });
    },
    onError: (err: Error) => toast.error(err.message || "Echec de l'ajout."),
  });

  const runAllMutation = useMutation({
    mutationFn: () => runAiVisibility(sid),
    onSuccess: (data) => {
      toast.success(
        `${data.checks_run} checks executes sur ${data.prompts_checked} prompt(s).`,
      );
      qc.invalidateQueries({ queryKey: ["ai-visibility-summary", sid] });
      qc.invalidateQueries({ queryKey: ["ai-visibility-prompts", sid] });
    },
    onError: (err: Error) => {
      toast.error(err.message || "Echec du check global.");
    },
  });

  const runSingleMutation = useMutation({
    mutationFn: (promptId: number) => runAiVisibility(sid, { prompt_id: promptId }),
    onSuccess: (data) => {
      toast.success(`${data.checks_run} engines re-testes.`);
      qc.invalidateQueries({ queryKey: ["ai-visibility-summary", sid] });
      qc.invalidateQueries({ queryKey: ["ai-visibility-prompts", sid] });
    },
    onError: (err: Error) => {
      toast.error(err.message || "Echec du recheck.");
    },
  });

  const summary = summaryQuery.data;
  const prompts = promptsQuery.data?.results ?? [];

  // Mock sparklines (V1 - until daily snapshots ship).
  const sparkScore = useMemo(() => mockSparkline(summary?.score ?? 30), [summary]);
  const sparkMentions = useMemo(
    () => mockSparkline(summary?.total_mentions ?? 5),
    [summary],
  );
  const sparkPages = useMemo(
    () => mockSparkline(summary?.cited_pages_count ?? 3),
    [summary],
  );

  return (
    <div>
      <PageBreadcrumb trail={[{ label: "Visibilite IA" }]} />

      {/* Header */}
      <div className="flex items-start justify-between gap-4 mb-6 flex-wrap">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <Brain className="h-6 w-6 text-emerald-400" />
              Visibilite IA
            </h1>
            <Badge className="bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">
              NEW
            </Badge>
          </div>
          <p className="text-sm text-muted-foreground max-w-2xl">
            Mesure combien de fois ton site est cite dans les reponses de ChatGPT,
            Perplexity, Gemini, SearchGPT et Claude. Le nouveau SEO 2026.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <RangeSelector value={range} onChange={setRange} />
          <Button
            onClick={() => runAllMutation.mutate()}
            disabled={
              runAllMutation.isPending ||
              prompts.length === 0 ||
              promptsQuery.isLoading
            }
            className="h-auto min-h-9 whitespace-normal"
          >
            {runAllMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
            Lancer un check sur tous les prompts
          </Button>
        </div>
      </div>

      {/* Hero strip - 3 KPI */}
      {summaryQuery.isLoading ? (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-36 w-full" />
          ))}
        </div>
      ) : summary ? (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          {/* Score */}
          <Card className="overflow-hidden border-emerald-500/20">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm flex items-center gap-2 text-muted-foreground font-medium">
                <Sparkles className="h-4 w-4 text-emerald-400" />
                Score de visibilite IA
              </CardTitle>
            </CardHeader>
            <CardContent className="flex flex-wrap items-end justify-between gap-3 pb-4">
              <ScoreGauge score={summary.score} />
              <div className="flex flex-col items-end gap-2 flex-1">
                <DeltaBadge delta={summary.delta_7d} />
                <div className="text-[10px] uppercase tracking-wider text-muted-foreground">
                  vs 7 derniers jours
                </div>
                <div className="w-full max-w-[120px]">
                  <Sparkline data={sparkScore} color="rgb(16 185 129)" />
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Total mentions */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">
                Mentions totales
              </CardTitle>
              <Quote className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold tabular-nums">
                {summary.total_mentions}
              </div>
              <div className="mt-2">
                <Sparkline data={sparkMentions} color="rgb(20 184 166)" />
              </div>
              <p className="text-xs text-muted-foreground mt-1">
                sur {summary.total_checks} checks lances
              </p>
            </CardContent>
          </Card>

          {/* Cited pages */}
          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium">Pages citees</CardTitle>
              <Globe className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-3xl font-bold tabular-nums">
                {summary.cited_pages_count}
              </div>
              <div className="mt-2">
                <Sparkline data={sparkPages} color="rgb(59 130 246)" />
              </div>
              <p className="text-xs text-muted-foreground mt-1">
                URLs uniques retrouvees dans les reponses
              </p>
            </CardContent>
          </Card>
        </div>
      ) : null}

      {/* Breakdown per engine */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="text-base">Repartition par moteur IA</CardTitle>
          <CardDescription>
            Taux de citation pondere par moteur. ChatGPT pese 30%, Perplexity 25%,
            Gemini 20%, SearchGPT 15%, Claude 10%.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            {ALL_ENGINES.map((engine) => {
              const row = summary?.breakdown_by_engine?.[engine];
              const rate = row?.cite_rate ?? 0;
              const total = row?.total_checks ?? 0;
              return (
                <div
                  key={engine}
                  className="rounded-lg border border-border/60 bg-card p-3 flex flex-col gap-2"
                >
                  <EngineBadge engine={engine} />
                  <div className="text-2xl font-bold tabular-nums">
                    {rate.toFixed(0)}
                    <span className="text-sm text-muted-foreground font-normal">
                      %
                    </span>
                  </div>
                  <div className="h-1.5 rounded-full bg-muted overflow-hidden">
                    <div
                      className="h-full bg-emerald-500/70 transition-all"
                      style={{ width: `${Math.min(100, rate)}%` }}
                    />
                  </div>
                  <p className="text-[11px] text-muted-foreground">
                    {row?.cited_count ?? 0} citations / {total} checks
                  </p>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* Add prompt form */}
      <Card className="mb-6">
        <CardHeader>
          <div className="flex items-start justify-between gap-3 flex-wrap">
            <div>
              <CardTitle className="text-base flex items-center gap-2">
                <Plus className="h-4 w-4" />
                Ajouter un prompt a tracker
              </CardTitle>
              <CardDescription className="mt-1">
                Une question que tes prospects poseraient a un LLM. Exemple :
                "Quel est le meilleur outil SEO IA pour PME au Quebec ?"
              </CardDescription>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => suggestMutation.mutate()}
              disabled={suggestMutation.isPending}
            >
              {suggestMutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Sparkles className="h-4 w-4" />
              )}
              Suggerer des prompts
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div className="md:col-span-3">
              <Textarea
                placeholder="Tape la question que tes prospects poseraient..."
                value={promptText}
                onChange={(e) => setPromptText(e.target.value)}
                rows={2}
                className="resize-none"
              />
            </div>
            <div>
              <label className="text-xs text-muted-foreground mb-1 block">
                Intention ciblee
              </label>
              <Select value={intent} onValueChange={setIntent}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {INTENT_OPTIONS.map((o) => (
                    <SelectItem key={o.value} value={o.value}>
                      {o.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <label className="text-xs text-muted-foreground mb-1 block">
                Langue
              </label>
              <Select
                value={language}
                onValueChange={(v) => setLanguage(v as "fr" | "en" | "es")}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="fr">Francais</SelectItem>
                  <SelectItem value="en">English</SelectItem>
                  <SelectItem value="es">Espanol</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-end">
              <Button
                onClick={() => createMutation.mutate()}
                disabled={
                  createMutation.isPending || promptText.trim().length === 0
                }
                className="w-full"
              >
                {createMutation.isPending ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <Plus className="h-4 w-4" />
                )}
                Ajouter
              </Button>
            </div>
          </div>

          {suggestions.length > 0 && (
            <div className="mt-4 space-y-2">
              <p className="text-xs text-muted-foreground">
                Suggestions IA - clique pour ajouter :
              </p>
              {suggestions.map((s, i) => (
                <button
                  key={i}
                  type="button"
                  onClick={() => addSuggestionMutation.mutate(s)}
                  disabled={addSuggestionMutation.isPending}
                  className="w-full text-left flex items-start gap-2 rounded-md border border-border/60 bg-card hover:border-emerald-500/50 p-2.5 transition-colors disabled:opacity-50"
                >
                  <Plus className="h-4 w-4 mt-0.5 shrink-0 text-emerald-400" />
                  <span className="flex-1 min-w-0">
                    <span className="text-sm">{s.prompt}</span>
                    <span className="block text-[10px] uppercase tracking-wider text-muted-foreground mt-0.5">
                      {s.target_intent}
                    </span>
                  </span>
                </button>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Prompts table */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Prompts trackes</CardTitle>
          <CardDescription>
            Chaque prompt est teste sur les 5 moteurs IA. Les resultats sont
            mockes en V1 le temps que les APIs LLM soient connectees.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {promptsQuery.isLoading ? (
            <div className="space-y-2">
              {[0, 1, 2].map((i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          ) : prompts.length === 0 ? (
            <div className="flex flex-col items-center justify-center text-center py-12 border border-dashed border-border/60 rounded-lg">
              <Brain className="h-10 w-10 text-muted-foreground mb-3 opacity-50" />
              <p className="text-sm font-medium mb-1">
                Aucun prompt tracke encore
              </p>
              <p className="text-xs text-muted-foreground max-w-md">
                Ajoute ta premiere question pour tester la visibilite IA de ton
                site dans les reponses des LLMs.
              </p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Prompt</TableHead>
                    <TableHead className="text-right">Citations</TableHead>
                    <TableHead>Moteurs qui mentionnent</TableHead>
                    <TableHead>Dernier check</TableHead>
                    <TableHead className="text-right">Action</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {prompts.map((p) => (
                    <TableRow key={p.id}>
                      <TableCell className="max-w-md">
                        <div className="text-sm font-medium truncate">
                          {p.prompt}
                        </div>
                        <div className="flex items-center gap-2 mt-0.5">
                          {p.target_intent && (
                            <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
                              {p.target_intent}
                            </span>
                          )}
                          <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
                            {p.language}
                          </span>
                        </div>
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        <span className="font-semibold">{p.citation_count}</span>
                        <span className="text-muted-foreground text-xs">
                          {" / "}
                          {p.total_checks}
                        </span>
                      </TableCell>
                      <TableCell>
                        {p.engines_mentioning.length === 0 ? (
                          <span className="text-xs text-muted-foreground">
                            -
                          </span>
                        ) : (
                          <div className="flex flex-wrap gap-1">
                            {p.engines_mentioning.map((e) => (
                              <EngineBadge
                                key={e}
                                engine={e as AiVisibilityEngine}
                                showLabel={false}
                              />
                            ))}
                          </div>
                        )}
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">
                        {p.last_checked_at
                          ? new Date(p.last_checked_at).toLocaleString("fr-CA", {
                              dateStyle: "short",
                              timeStyle: "short",
                            })
                          : "Jamais"}
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => runSingleMutation.mutate(p.id)}
                          disabled={
                            runSingleMutation.isPending &&
                            runSingleMutation.variables === p.id
                          }
                        >
                          {runSingleMutation.isPending &&
                          runSingleMutation.variables === p.id ? (
                            <Loader2 className="h-3 w-3 animate-spin" />
                          ) : (
                            <RefreshCw className="h-3 w-3" />
                          )}
                          Recheck
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* V1 disclaimer */}
      <div className="mt-4 flex items-start gap-2 text-xs text-muted-foreground p-3 rounded-lg bg-muted/30 border border-border/40">
        <AlertCircle className="h-3.5 w-3.5 mt-0.5 shrink-0" />
        <p>
          V1 : les checks sont generes localement avec des resultats mockes
          plausibles. La connexion aux vraies APIs (ChatGPT, Perplexity, Gemini,
          SearchGPT, Claude) arrive en V2.{" "}
          <ExternalLink className="inline h-3 w-3" />
        </p>
      </div>
    </div>
  );
}
