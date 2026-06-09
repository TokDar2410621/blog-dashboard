"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { authFetch } from "@/lib/api-client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
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
import {
  TrendingUp,
  Plus,
  Trash2,
  RefreshCw,
  Loader2,
  AlertTriangle,
  ChevronDown,
  ChevronUp,
  Sparkles,
  Check,
} from "lucide-react";
import { toast } from "sonner";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";

type Latest = {
  position: number | null;
  url: string;
  title: string;
  is_target_match: boolean;
  recorded_at: string;
} | null;

type Intent = "info" | "commercial" | "transactional" | "local";

type Tracked = {
  id: number;
  keyword: string;
  language: string;
  intent: Intent;
  target_url: string;
  is_active: boolean;
  created_at: string;
  latest: Latest;
};

type Snapshot = {
  position: number | null;
  url: string;
  title: string;
  is_target_match: boolean;
  recorded_at: string;
};

type DecayAlert = {
  severity: "warning" | "critical";
  message: string;
  previous_median?: number;
  current?: number;
};

type History = {
  tracked: Tracked;
  days: number;
  snapshots: Snapshot[];
  decay_alert: DecayAlert | null;
};

type Suggestion = {
  keyword: string;
  language: string;
  intent: Intent;
  why: string;
};

const INTENT_LABELS: Record<Intent, string> = {
  info: "info",
  commercial: "commercial",
  transactional: "transac.",
  local: "local",
};

const INTENT_COLORS: Record<Intent, string> = {
  info: "bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300",
  commercial: "bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300",
  transactional: "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300",
  local: "bg-purple-100 text-purple-700 dark:bg-purple-950 dark:text-purple-300",
};

export default function KeywordTracker() {
  const { siteId } = useParams<{ siteId: string }>();
  const qc = useQueryClient();
  const [keyword, setKeyword] = useState("");
  const [language, setLanguage] = useState("fr");
  const [targetUrl, setTargetUrl] = useState("");
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [suggestions, setSuggestions] = useState<Suggestion[] | null>(null);
  const [suggestionMeta, setSuggestionMeta] = useState<{
    rag_chunks_used: number;
    homepage_fetched: boolean;
    context_thin: boolean;
    serp_sources_used: number;
  } | null>(null);
  const [selectedSuggestions, setSelectedSuggestions] = useState<Set<string>>(new Set());

  const list = useQuery({
    queryKey: ["tracked-keywords", siteId],
    queryFn: async () => {
      const res = await authFetch(`/sites/${siteId}/keywords/`);
      if (!res.ok) throw new Error("fetch failed");
      return (await res.json()).results as Tracked[];
    },
  });

  const add = useMutation({
    mutationFn: async () => {
      const res = await authFetch(`/sites/${siteId}/keywords/`, {
        method: "POST",
        body: JSON.stringify({
          keyword: keyword.trim(),
          language,
          target_url: targetUrl.trim(),
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error || "Erreur lors de l'ajout");
      }
      return res.json();
    },
    onSuccess: () => {
      setKeyword("");
      setTargetUrl("");
      qc.invalidateQueries({ queryKey: ["tracked-keywords", siteId] });
      toast.success("Mot-cle ajoute");
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const remove = useMutation({
    mutationFn: async (id: number) => {
      const res = await authFetch(`/sites/${siteId}/keywords/${id}/`, {
        method: "DELETE",
      });
      if (!res.ok && res.status !== 204) {
        throw new Error("Erreur lors du retrait");
      }
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tracked-keywords", siteId] });
      toast.success("Mot-cle retire");
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const snapshot = useMutation({
    mutationFn: async () => {
      const res = await authFetch(`/sites/${siteId}/rank-snapshot/`, {
        method: "POST",
        body: JSON.stringify({}),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error || "Erreur lors du snapshot");
      }
      return res.json() as Promise<{
        snapshots_created: number;
        not_found_count: number;
        total_processed: number;
      }>;
    },
    onSuccess: (d) => {
      qc.invalidateQueries({ queryKey: ["tracked-keywords", siteId] });
      toast.success(
        `${d.total_processed} mots-cles traites, ${d.snapshots_created - d.not_found_count} positionnes`
      );
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const suggest = useMutation({
    mutationFn: async () => {
      const res = await authFetch(`/sites/${siteId}/suggest-keywords/`, {
        method: "POST",
        body: JSON.stringify({ language }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error || "Erreur suggestion IA");
      }
      return res.json() as Promise<{
        keywords: Suggestion[];
        serp_sources_used: number;
        rag_chunks_used: number;
        homepage_fetched: boolean;
        context_thin: boolean;
      }>;
    },
    onSuccess: (d) => {
      setSuggestions(d.keywords);
      setSuggestionMeta({
        rag_chunks_used: d.rag_chunks_used,
        homepage_fetched: d.homepage_fetched,
        context_thin: d.context_thin,
        serp_sources_used: d.serp_sources_used,
      });
      setSelectedSuggestions(new Set(d.keywords.map((k) => k.keyword)));
      if (d.context_thin) {
        toast.warning(
          "Contexte trop maigre : remplis la description du site ou publie quelques articles pour des suggestions pertinentes."
        );
      } else if (!d.keywords.length) {
        toast.info("Aucune suggestion. Vérifie que le site a un nom + description.");
      }
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const bulkAdd = useMutation({
    mutationFn: async (toAdd: Suggestion[]) => {
      const results = await Promise.allSettled(
        toAdd.map((s) =>
          authFetch(`/sites/${siteId}/keywords/`, {
            method: "POST",
            body: JSON.stringify({
              keyword: s.keyword,
              language: s.language,
              intent: s.intent,
            }),
          }).then((r) => (r.ok ? r : Promise.reject(r)))
        )
      );
      const added = results.filter((r) => r.status === "fulfilled").length;
      const failed = results.length - added;
      return { added, failed };
    },
    onSuccess: ({ added, failed }) => {
      qc.invalidateQueries({ queryKey: ["tracked-keywords", siteId] });
      if (failed === 0) toast.success(`${added} mot(s)-clé(s) ajouté(s)`);
      else toast.warning(`${added} ajoutés, ${failed} en échec (quota ou doublon ?)`);
      setSuggestions(null);
      setSuggestionMeta(null);
      setSelectedSuggestions(new Set());
    },
    onError: () => toast.error("Erreur ajout en masse"),
  });

  const reclassify = useMutation({
    mutationFn: async () => {
      const res = await authFetch(`/sites/${siteId}/keywords/reclassify/`, {
        method: "POST",
        body: JSON.stringify({ only_default: true }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error || "Erreur reclassification");
      }
      return res.json() as Promise<{ updated_count: number; total_processed: number }>;
    },
    onSuccess: (d) => {
      qc.invalidateQueries({ queryKey: ["tracked-keywords", siteId] });
      toast.success(
        d.updated_count > 0
          ? `${d.updated_count}/${d.total_processed} mot(s)-clé(s) reclassé(s)`
          : "Aucun changement (tout était déjà bien classé)"
      );
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const patchIntent = useMutation({
    mutationFn: async ({ id, intent }: { id: number; intent: Intent }) => {
      const res = await authFetch(`/sites/${siteId}/keywords/${id}/`, {
        method: "PATCH",
        body: JSON.stringify({ intent }),
      });
      if (!res.ok) throw new Error("Erreur mise à jour intent");
      return res.json();
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["tracked-keywords", siteId] });
    },
    onError: () => toast.error("Erreur mise à jour intent"),
  });

  const history = useQuery<History>({
    queryKey: ["rank-history", siteId, expandedId],
    queryFn: async () => {
      const res = await authFetch(
        `/sites/${siteId}/rank-history/?tracked_id=${expandedId}&days=90`
      );
      if (!res.ok) throw new Error("history fetch failed");
      return res.json();
    },
    enabled: expandedId !== null,
  });

  return (
    <div className="space-y-6 max-w-5xl">
      <div>
        <h1 className="text-2xl font-bold">{"Suivi des positions Google"}</h1>
        <p className="text-muted-foreground">{"Ajoute les mots-clés pour lesquels tu veux suivre ton ranking dans le temps. Lance un snapshot manuellement ou laisse l'agent schedule le faire chaque jour."}</p>
      </div>

      {/* Add form */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Plus className="h-5 w-5 text-primary" />
            {"Ajouter un mot-clé à suivre"}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-[1fr_auto_2fr_auto] gap-3 items-end">
            <div className="space-y-1">
              <label className="text-xs font-medium">{"Mot-clé"}</label>
              <Input
                value={keyword}
                onChange={(e) => setKeyword(e.target.value)}
                placeholder={"Ex: automatisation pme québec"}
              />
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium">{"Langue"}</label>
              <Select value={language} onValueChange={setLanguage}>
                <SelectTrigger className="w-24">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="fr">FR</SelectItem>
                  <SelectItem value="en">EN</SelectItem>
                  <SelectItem value="es">ES</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <label className="text-xs font-medium">{"URL cible (optionnelle)"}</label>
              <Input
                value={targetUrl}
                onChange={(e) => setTargetUrl(e.target.value)}
                placeholder={"https://tonsite.ca/blog/article"}
              />
            </div>
            <Button
              onClick={() => add.mutate()}
              disabled={add.isPending || !keyword.trim()}
            >
              {add.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <>
                  <Plus className="h-4 w-4 mr-2" />
                  {"Ajouter"}
                </>
              )}
            </Button>
          </div>

          <div className="mt-4 pt-4 border-t flex items-center justify-between gap-3 flex-wrap">
            <p className="text-xs text-muted-foreground">
              Pas d'idées ? Laisse l'IA proposer des mots-clés basée sur ton site (nom, description, SERP Google).
            </p>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => suggest.mutate()}
              disabled={suggest.isPending}
            >
              {suggest.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Analyse IA (~20s)...
                </>
              ) : (
                <>
                  <Sparkles className="h-4 w-4 mr-2" />
                  Suggérer avec l'IA
                </>
              )}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* IA suggestions panel */}
      {suggestions && suggestions.length > 0 && (
        <Card className="border-primary/40">
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-primary" />
              Suggestions IA ({suggestions.length})
            </CardTitle>
            <p className="text-sm text-muted-foreground">
              Coche celles que tu veux tracker, puis clique "Ajouter la sélection".
            </p>
            {suggestionMeta && (
              <div className="flex flex-wrap items-center gap-2 mt-2 text-xs">
                <span className="text-muted-foreground">Contexte utilisé :</span>
                <span className={`px-2 py-0.5 rounded ${suggestionMeta.rag_chunks_used > 0 ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300" : "bg-muted text-muted-foreground"}`}>
                  RAG : {suggestionMeta.rag_chunks_used} chunk{suggestionMeta.rag_chunks_used > 1 ? "s" : ""}
                </span>
                <span className={`px-2 py-0.5 rounded ${suggestionMeta.homepage_fetched ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300" : "bg-muted text-muted-foreground"}`}>
                  Homepage : {suggestionMeta.homepage_fetched ? "scrappée" : "non dispo"}
                </span>
                <span className={`px-2 py-0.5 rounded ${suggestionMeta.serp_sources_used > 0 ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300" : "bg-muted text-muted-foreground"}`}>
                  SERP : {suggestionMeta.serp_sources_used} titres
                </span>
                {suggestionMeta.context_thin && (
                  <span className="px-2 py-0.5 rounded bg-amber-100 text-amber-700 dark:bg-amber-950 dark:text-amber-300">
                    Contexte maigre - résultats potentiellement bruités
                  </span>
                )}
              </div>
            )}
          </CardHeader>
          <CardContent className="space-y-2">
            {suggestions.map((s) => {
              const checked = selectedSuggestions.has(s.keyword);
              return (
                <label
                  key={s.keyword}
                  className="flex items-start gap-3 p-3 rounded-lg border hover:bg-muted/40 cursor-pointer"
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => {
                      const next = new Set(selectedSuggestions);
                      if (checked) next.delete(s.keyword);
                      else next.add(s.keyword);
                      setSelectedSuggestions(next);
                    }}
                    className="mt-1"
                  />
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-medium">{s.keyword}</span>
                      <span className={`text-[10px] uppercase px-1.5 py-0.5 rounded font-semibold ${INTENT_COLORS[s.intent]}`}>
                        {s.intent}
                      </span>
                    </div>
                    {s.why && (
                      <p className="text-xs text-muted-foreground mt-0.5">{s.why}</p>
                    )}
                  </div>
                </label>
              );
            })}
            <div className="flex items-center justify-between gap-3 pt-3 border-t">
              <button
                type="button"
                className="text-xs text-muted-foreground hover:underline"
                onClick={() => {
                  setSuggestions(null);
                  setSelectedSuggestions(new Set());
                }}
              >
                Fermer
              </button>
              <Button
                onClick={() => {
                  const toAdd = suggestions.filter((s) => selectedSuggestions.has(s.keyword));
                  if (toAdd.length === 0) {
                    toast.info("Aucune suggestion selectionnee");
                    return;
                  }
                  bulkAdd.mutate(toAdd);
                }}
                disabled={bulkAdd.isPending || selectedSuggestions.size === 0}
              >
                {bulkAdd.isPending ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Ajout...
                  </>
                ) : (
                  <>
                    <Check className="h-4 w-4 mr-2" />
                    Ajouter la selection ({selectedSuggestions.size})
                  </>
                )}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Snapshot + reclassify buttons */}
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <p className="text-sm text-muted-foreground">
          {list.data
            ? `${list.data.length} mots-cles suivis`
            : ""}
        </p>
        <div className="flex items-center gap-2">
          <Button
            onClick={() => reclassify.mutate()}
            disabled={reclassify.isPending || !list.data?.length}
            variant="outline"
            size="sm"
            title="Re-classer les mots-cles encore en 'info' via Claude (~$0.02)"
          >
            {reclassify.isPending ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Reclassification...
              </>
            ) : (
              <>
                <Sparkles className="h-4 w-4 mr-2" />
                Reclasser avec l'IA
              </>
            )}
          </Button>
          <Button
            onClick={() => snapshot.mutate()}
            disabled={snapshot.isPending || !list.data?.length}
            variant="outline"
            size="sm"
          >
            {snapshot.isPending ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                {"Snapshot en cours..."}
              </>
            ) : (
              <>
                <RefreshCw className="h-4 w-4 mr-2" />
                {"Snapshot maintenant"}
              </>
            )}
          </Button>
        </div>
      </div>

      {/* Table */}
      <Card>
        <CardContent className="p-0">
          {list.isLoading ? (
            <div className="p-6 space-y-2">
              {[...Array(3)].map((_, i) => (
                <Skeleton key={i} className="h-12" />
              ))}
            </div>
          ) : !list.data?.length ? (
            <div className="p-12 text-center text-muted-foreground">
              <TrendingUp className="h-10 w-10 mx-auto mb-3 opacity-30" />
              <p>{"Aucun mot-cle suivi. Ajoute le premier ci-dessus."}</p>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{"Mot-cle"}</TableHead>
                  <TableHead className="w-24">Intent</TableHead>
                  <TableHead className="w-16">{"Langue"}</TableHead>
                  <TableHead className="w-24 text-center">{"Position"}</TableHead>
                  <TableHead>{"Dernier snapshot"}</TableHead>
                  <TableHead className="w-20"></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {list.data.map((k) => {
                  const isExpanded = expandedId === k.id;
                  return (
                    <>
                      <TableRow
                        key={k.id}
                        className="cursor-pointer"
                        onClick={() => setExpandedId(isExpanded ? null : k.id)}
                      >
                        <TableCell className="font-medium">
                          <div className="flex items-center gap-2">
                            {isExpanded ? (
                              <ChevronUp className="h-3 w-3 text-muted-foreground" />
                            ) : (
                              <ChevronDown className="h-3 w-3 text-muted-foreground" />
                            )}
                            {k.keyword}
                          </div>
                        </TableCell>
                        <TableCell onClick={(e) => e.stopPropagation()}>
                          <Select
                            value={k.intent || "info"}
                            onValueChange={(v) =>
                              patchIntent.mutate({ id: k.id, intent: v as Intent })
                            }
                          >
                            <SelectTrigger
                              className={`h-7 px-2 text-[10px] uppercase font-semibold border-0 ${INTENT_COLORS[k.intent || "info"]}`}
                            >
                              <SelectValue>{INTENT_LABELS[k.intent || "info"]}</SelectValue>
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="info">Info</SelectItem>
                              <SelectItem value="commercial">Commercial</SelectItem>
                              <SelectItem value="transactional">Transactionnel</SelectItem>
                              <SelectItem value="local">Local</SelectItem>
                            </SelectContent>
                          </Select>
                        </TableCell>
                        <TableCell>
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground font-mono uppercase">
                            {k.language}
                          </span>
                        </TableCell>
                        <TableCell className="text-center">
                          {k.latest ? (
                            k.latest.position !== null ? (
                              <span
                                className={`text-xl font-bold ${
                                  k.latest.position <= 3
                                    ? "text-green-600"
                                    : k.latest.position <= 10
                                    ? "text-emerald-600"
                                    : k.latest.position <= 30
                                    ? "text-amber-600"
                                    : "text-muted-foreground"
                                }`}
                              >
                                #{k.latest.position}
                              </span>
                            ) : (
                              <span className="text-xs text-muted-foreground">
                                {"Hors top 100"}
                              </span>
                            )
                          ) : (
                            <span className="text-xs text-muted-foreground">-</span>
                          )}
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground">
                          {k.latest
                            ? new Date(k.latest.recorded_at).toLocaleString("fr-CA")
                            : "Jamais"}
                        </TableCell>
                        <TableCell>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={(e) => {
                              e.stopPropagation();
                              if (
                                confirm(`Retirer le suivi de "${k.keyword}" ?`)
                              ) {
                                remove.mutate(k.id);
                              }
                            }}
                          >
                            <Trash2 className="h-4 w-4 text-muted-foreground hover:text-destructive" />
                          </Button>
                        </TableCell>
                      </TableRow>
                      {isExpanded && (
                        <TableRow key={`${k.id}-history`}>
                          <TableCell colSpan={6} className="bg-muted/30">
                            {history.isLoading ? (
                              <Skeleton className="h-20" />
                            ) : history.data ? (
                              <div className="space-y-3">
                                {history.data.decay_alert && (
                                  <div
                                    className={`flex items-start gap-2 p-3 rounded text-sm ${
                                      history.data.decay_alert.severity === "critical"
                                        ? "bg-red-500/10 text-red-700 dark:text-red-400"
                                        : "bg-amber-500/10 text-amber-700 dark:text-amber-400"
                                    }`}
                                  >
                                    <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
                                    <div>
                                      <strong>{history.data.decay_alert.message}</strong>
                                      {history.data.decay_alert.previous_median && (
                                        <div className="text-xs mt-1">
                                          {"Mediane precedente"}: #
                                          {history.data.decay_alert.previous_median}
                                          {history.data.decay_alert.current &&
                                            ` → #${history.data.decay_alert.current}`}
                                        </div>
                                      )}
                                    </div>
                                  </div>
                                )}
                                <div>
                                  <h4 className="text-xs font-mono uppercase tracking-wide text-muted-foreground mb-2">
                                    {"Historique 90 jours"} ({history.data.snapshots.length})
                                  </h4>
                                  {history.data.snapshots.length === 0 ? (
                                    <p className="text-xs text-muted-foreground">
                                      {"Aucun snapshot enregistré."}
                                    </p>
                                  ) : (
                                    <RankChart snapshots={history.data.snapshots} />
                                  )}
                                </div>
                              </div>
                            ) : null}
                          </TableCell>
                        </TableRow>
                      )}
                    </>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}


function RankChart({ snapshots }: { snapshots: Snapshot[] }) {
  // Map: x = recorded date (ms), y = position (null → not in top 100, plotted at 101 as ceiling)
  const NOT_IN_TOP = 101;
  const data = snapshots.map((s) => ({
    ts: new Date(s.recorded_at).getTime(),
    position: s.position ?? NOT_IN_TOP,
    rawPosition: s.position,
    title: s.title,
    isTargetMatch: s.is_target_match,
  }));

  const positions = data
    .map((d) => d.rawPosition)
    .filter((p): p is number => p !== null);
  const minP = positions.length ? Math.max(1, Math.min(...positions) - 2) : 1;
  const maxP = positions.length
    ? Math.min(NOT_IN_TOP, Math.max(...positions) + 5)
    : 50;

  return (
    <div className="w-full h-56 -ml-2">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart
          data={data}
          margin={{ top: 8, right: 16, left: 0, bottom: 0 }}
        >
          <CartesianGrid stroke="currentColor" strokeOpacity={0.08} />
          <XAxis
            dataKey="ts"
            type="number"
            domain={["dataMin", "dataMax"]}
            scale="time"
            tickFormatter={(ts) =>
              new Date(ts).toLocaleDateString("fr-CA", {
                month: "short",
                day: "2-digit",
              })
            }
            tick={{ fontSize: 11 }}
            stroke="currentColor"
            strokeOpacity={0.5}
          />
          <YAxis
            reversed
            domain={[minP, maxP]}
            tick={{ fontSize: 11 }}
            stroke="currentColor"
            strokeOpacity={0.5}
            width={40}
            tickFormatter={(v) => (v >= NOT_IN_TOP ? "100+" : `#${v}`)}
          />
          <Tooltip
            contentStyle={{
              background: "hsl(var(--card))",
              border: "1px solid hsl(var(--border))",
              fontSize: 12,
            }}
            labelFormatter={(ts) =>
              new Date(ts as number).toLocaleString("fr-CA")
            }
            formatter={(_value, _name, item) => {
              const d = item.payload as (typeof data)[number];
              return [
                d.rawPosition === null ? "Hors top 100" : `#${d.rawPosition}`,
                d.title || "Position",
              ];
            }}
          />
          {/* Reference lines for the top 3 / top 10 thresholds */}
          <ReferenceLine
            y={3}
            stroke="hsl(142 76% 36%)"
            strokeDasharray="3 3"
            strokeOpacity={0.5}
          />
          <ReferenceLine
            y={10}
            stroke="hsl(142 60% 45%)"
            strokeDasharray="3 3"
            strokeOpacity={0.5}
          />
          <Line
            type="monotone"
            dataKey="position"
            stroke="hsl(var(--primary))"
            strokeWidth={2}
            dot={{ r: 3, fill: "hsl(var(--primary))" }}
            activeDot={{ r: 5 }}
            connectNulls
          />
        </LineChart>
      </ResponsiveContainer>
      <div className="flex items-center gap-4 text-[10px] text-muted-foreground mt-1 ml-10">
        <span className="flex items-center gap-1">
          <span className="w-3 h-px bg-green-600" /> Top 3
        </span>
        <span className="flex items-center gap-1">
          <span className="w-3 h-px bg-emerald-600" /> Top 10
        </span>
        <span>Y-axis : meilleur en haut (#1)</span>
      </div>
    </div>
  );
}
