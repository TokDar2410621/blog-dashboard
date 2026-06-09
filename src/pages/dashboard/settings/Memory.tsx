import { Brain, Loader2, RefreshCw, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useSettings } from "./useSettings";

export default function Memory() {
  const {
    manualNote, setManualNote,
    manualNoteTitle, setManualNoteTitle,
    memoriesQuery,
    rebuildMemory,
    addManualNote,
    deleteMemory,
  } = useSettings();

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <div>
            <CardTitle className="text-lg flex items-center gap-2">
              <Brain className="h-5 w-5" />
              Mémoire du site (RAG)
            </CardTitle>
            <CardDescription>
              Index vectoriel pgvector + Voyage AI. Chaque génération d'article retrieve les 8 extraits les plus pertinents (articles passés, KB, audits, notes) au lieu de tout balancer en prompt. Permet à l'IA de rester cohérente entre les requêtes.
            </CardDescription>
          </div>
          <div className="flex gap-2 shrink-0">
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => rebuildMemory.mutate(false)}
              disabled={rebuildMemory.isPending}
            >
              {rebuildMemory.isPending ? (
                <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
              ) : (
                <RefreshCw className="h-3.5 w-3.5 mr-1.5" />
              )}
              Réindexer
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {memoriesQuery.isLoading ? (
          <p className="text-xs text-muted-foreground">Chargement...</p>
        ) : memoriesQuery.data ? (
          <>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
              {(["article", "kb", "audit", "decision", "manual"] as const).map((k) => {
                const chunks = memoriesQuery.data!.counts_by_kind?.[k] || 0;
                const sources = memoriesQuery.data!.sources_by_kind?.[k] || 0;
                const showSources = chunks > 0 && sources > 0 && sources !== chunks;
                return (
                  <div
                    key={k}
                    className="rounded-md border bg-muted/30 p-2 text-center"
                  >
                    <div className="text-xl font-bold">{chunks}</div>
                    <div className="text-[10px] uppercase tracking-wide text-muted-foreground">
                      {k === "article" ? "Extraits"
                        : k === "kb" ? "Extraits KB"
                        : k === "audit" ? "Audits"
                        : k === "decision" ? "Décisions"
                        : "Notes"}
                    </div>
                    {showSources && (
                      <div className="text-[10px] text-muted-foreground mt-0.5">
                        de {sources} source{sources > 1 ? "s" : ""}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
            <p className="text-[11px] text-muted-foreground -mt-2">
              Chaque article publié est découpé en plusieurs extraits (chunks) pour la recherche sémantique. 1 article ~ 6-10 extraits selon sa longueur.
            </p>
          </>
        ) : null}

        <div className="space-y-2 border-t pt-4">
          <Label className="text-sm flex items-center gap-1.5">
            <Plus className="h-3.5 w-3.5" />
            Ajouter une note manuelle
          </Label>
          <Input
            value={manualNoteTitle}
            onChange={(e) => setManualNoteTitle(e.target.value)}
            placeholder="Titre court (ex: Voix de marque)"
            className="h-8 text-sm"
          />
          <Textarea
            value={manualNote}
            onChange={(e) => setManualNote(e.target.value)}
            placeholder={"Ex: 'Ne jamais utiliser le tutoiement.' / 'Cibler Montréal, pas Québec.' / 'Mettre tous les chiffres en majuscule.'"}
            className="min-h-[100px] text-sm"
          />
          <Button
            size="sm"
            onClick={() => addManualNote.mutate()}
            disabled={!manualNote.trim() || addManualNote.isPending}
          >
            {addManualNote.isPending ? (
              <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
            ) : (
              <Plus className="h-3.5 w-3.5 mr-1.5" />
            )}
            Ajouter
          </Button>
        </div>

        {memoriesQuery.data?.memories && memoriesQuery.data.memories.length > 0 && (
          <div className="border-t pt-4">
            <Label className="text-sm mb-2 block">Memoires recentes</Label>
            <div className="space-y-2 max-h-80 overflow-y-auto">
              {memoriesQuery.data.memories.slice(0, 30).map((m) => (
                <div
                  key={m.id}
                  className="flex items-start gap-2 p-2 rounded-md border bg-muted/20 text-xs"
                >
                  <span className="inline-block px-1.5 py-0.5 rounded bg-primary/10 text-primary uppercase text-[10px] font-mono shrink-0">
                    {m.kind}
                  </span>
                  <div className="flex-1 min-w-0">
                    {m.title && <div className="font-medium truncate">{m.title}</div>}
                    <div className="text-muted-foreground truncate">{m.content_preview}</div>
                  </div>
                  <button
                    type="button"
                    onClick={() => deleteMemory.mutate(m.id)}
                    className="text-muted-foreground hover:text-destructive shrink-0"
                    title="Supprimer"
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
