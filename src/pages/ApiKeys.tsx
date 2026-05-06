import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { authFetch } from "@/lib/api-client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  ArrowLeft,
  Key,
  Plus,
  Copy,
  Check,
  Trash2,
  AlertTriangle,
  BookOpen,
  Loader2,
} from "lucide-react";
import { toast } from "sonner";

type Token = {
  id: number;
  name: string;
  prefix: string;
  last_used_at: string | null;
  revoked_at: string | null;
  created_at: string;
  is_active: boolean;
};

type CreatedToken = Token & { token: string; message: string };

export default function ApiKeys() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [name, setName] = useState("");
  const [revealed, setRevealed] = useState<CreatedToken | null>(null);
  const [copied, setCopied] = useState(false);

  const { data: tokens, isLoading } = useQuery<{ results: Token[] }>({
    queryKey: ["api-tokens"],
    queryFn: async () => {
      const res = await authFetch("/account/api-tokens/");
      if (!res.ok) throw new Error("Impossible de charger les tokens.");
      return res.json();
    },
  });

  const create = useMutation({
    mutationFn: async (n: string): Promise<CreatedToken> => {
      const res = await authFetch("/account/api-tokens/", {
        method: "POST",
        body: JSON.stringify({ name: n }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Erreur création.");
      return data;
    },
    onSuccess: (data) => {
      setRevealed(data);
      setName("");
      qc.invalidateQueries({ queryKey: ["api-tokens"] });
      toast.success("Token créé. Copie-le maintenant.");
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const revoke = useMutation({
    mutationFn: async (id: number) => {
      const res = await authFetch(`/account/api-tokens/${id}/`, {
        method: "DELETE",
      });
      if (!res.ok && res.status !== 204) {
        const d = await res.json().catch(() => ({}));
        throw new Error(d.error || "Erreur révocation.");
      }
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["api-tokens"] });
      toast.success("Token révoqué.");
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const copyToken = async () => {
    if (!revealed) return;
    try {
      await navigator.clipboard.writeText(revealed.token);
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    } catch {
      toast.error("Copie impossible. Sélectionne et copie manuellement.");
    }
  };

  const fmtDate = (iso: string | null) =>
    iso
      ? new Date(iso).toLocaleString("fr-CA", {
          year: "numeric",
          month: "short",
          day: "numeric",
          hour: "2-digit",
          minute: "2-digit",
        })
      : "Jamais";

  const list = tokens?.results ?? [];

  return (
    <div className="min-h-screen bg-background p-6">
      <div className="max-w-4xl mx-auto space-y-8">
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => navigate("/sites")}
            title="Retour"
          >
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <div className="flex-1">
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <Key className="h-6 w-6 text-primary" />
              Clés API
            </h1>
            <p className="text-muted-foreground">
              Crée des tokens pour intégrer blog-dashboard à n8n, Zapier, Make
              ou tes propres scripts.
            </p>
          </div>
          <Button variant="outline" onClick={() => navigate("/api-docs")}>
            <BookOpen className="h-4 w-4 mr-2" />
            Documentation
          </Button>
        </div>

        {/* Reveal banner — shown once after creation */}
        {revealed && (
          <Card className="border-emerald-500/40 bg-emerald-500/5">
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2 text-emerald-600 dark:text-emerald-400">
                <AlertTriangle className="h-5 w-5" />
                Copie ce token maintenant — il ne sera plus jamais affiché
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex items-center gap-2">
                <Input
                  readOnly
                  value={revealed.token}
                  className="font-mono text-xs"
                  onFocus={(e) => e.currentTarget.select()}
                />
                <Button onClick={copyToken} variant="default">
                  {copied ? (
                    <>
                      <Check className="h-4 w-4 mr-2" /> Copié
                    </>
                  ) : (
                    <>
                      <Copy className="h-4 w-4 mr-2" /> Copier
                    </>
                  )}
                </Button>
              </div>
              <p className="text-sm text-muted-foreground">
                {revealed.message}
              </p>
              <div className="text-right">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setRevealed(null)}
                >
                  J'ai copié, fermer
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Create form */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Plus className="h-5 w-5 text-primary" />
              Nouveau token
            </CardTitle>
          </CardHeader>
          <CardContent>
            <form
              className="flex flex-col md:flex-row gap-2"
              onSubmit={(e) => {
                e.preventDefault();
                if (!name.trim()) {
                  toast.error("Donne un nom à ton token.");
                  return;
                }
                create.mutate(name.trim());
              }}
            >
              <Input
                placeholder="Ex: n8n-prod, Zapier-marketing"
                value={name}
                onChange={(e) => setName(e.target.value)}
                maxLength={100}
              />
              <Button type="submit" disabled={create.isPending}>
                {create.isPending ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <Plus className="h-4 w-4 mr-2" />
                )}
                Créer le token
              </Button>
            </form>
            <p className="text-xs text-muted-foreground mt-2">
              Réservé aux plans Pro (60 req/h) et Agence (600 req/h). Plan
              gratuit bloqué.
            </p>
          </CardContent>
        </Card>

        {/* Token list */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Tes tokens</CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <Skeleton className="h-24" />
            ) : list.length === 0 ? (
              <div className="text-center py-12 text-muted-foreground">
                <Key className="h-12 w-12 mx-auto mb-3 opacity-30" />
                <p>Aucun token pour l'instant.</p>
              </div>
            ) : (
              <div className="divide-y divide-border/50">
                {list.map((t) => (
                  <div
                    key={t.id}
                    className="py-4 flex items-center justify-between gap-3"
                  >
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2">
                        <span className="font-medium truncate">{t.name}</span>
                        {t.revoked_at ? (
                          <span className="text-xs px-2 py-0.5 rounded bg-destructive/10 text-destructive">
                            Révoqué
                          </span>
                        ) : (
                          <span className="text-xs px-2 py-0.5 rounded bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
                            Actif
                          </span>
                        )}
                      </div>
                      <div className="text-xs text-muted-foreground mt-1 font-mono">
                        {t.prefix}…{" · "}
                        <span className="font-sans">
                          créé le {fmtDate(t.created_at)} · dernière
                          utilisation : {fmtDate(t.last_used_at)}
                        </span>
                      </div>
                    </div>
                    {!t.revoked_at && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          if (
                            confirm(
                              `Révoquer "${t.name}" ? Toute requête utilisant ce token échouera immédiatement.`,
                            )
                          ) {
                            revoke.mutate(t.id);
                          }
                        }}
                        disabled={revoke.isPending}
                      >
                        <Trash2 className="h-4 w-4 mr-1" />
                        Révoquer
                      </Button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
