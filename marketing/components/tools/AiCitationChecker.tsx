"use client";

import { useState } from "react";
import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Quote,
  Loader2,
  ArrowRight,
  CheckCircle2,
  XCircle,
  FileText,
  Lightbulb,
  Link as LinkIcon
} from "lucide-react";
import { GridarMark } from "@/components/GridarMark";
import { toast } from "sonner";
import { EmailGate } from "@/components/tools/EmailGate";
import { ToolHero } from "@/components/tools/ToolHero";

const API_BASE = "";

type QueryResult = {
  query: string;
  cited: boolean;
  context_snippet?: string;
  competing_sources: string[];
};

type CitationResult = {
  domain: string;
  citation_score: number;
  total_queries_tested: number;
  times_cited: number;
  citation_rate: number;
  results: QueryResult[];
  top_competing_sources: { domain: string; count: number }[];
  recommendations: string[];
};

function getScoreColor(s: number) {
  if (s >= 80) return "text-emerald-400";
  if (s >= 50) return "text-amber-400";
  return "text-red-400";
}

export function AiCitationChecker() {
  const [domain, setDomain] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<CitationResult | null>(null);

  const runAnalysis = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!domain.trim()) return;
    setLoading(true);
    setResult(null);
    try {
      const res = await fetch(`${API_BASE}/api/public/ai-citation/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ domain: domain.trim() }),
      });
      if (!res.ok) {
        throw new Error("Analyse impossible pour le moment.");
      }
      const data = await res.json();
      setResult(data);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Erreur");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto px-4 py-10 md:py-16">
      <ToolHero icon={Quote} badge="AI Citation Checker" title="Est-ce que l'IA te cite comme source?" subtitle="Verifie si l'IA de Google (Gemini) utilise tes contenus pour generer ses reponses." />

      <Card className="mb-8">
        <CardContent className="p-4">
          <form onSubmit={runAnalysis} className="flex flex-col sm:flex-row gap-2">
            <Input
              type="text"
              placeholder="tondomaine.com"
              value={domain}
              onChange={(e) => setDomain(e.target.value)}
              disabled={loading}
              required
              className="flex-1"
            />
            <Button
              type="submit"
              disabled={loading || !domain.trim()}
              className="bg-emerald-500 text-zinc-950 hover:bg-emerald-400 font-semibold shrink-0"
            >
              {loading ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Analyse en cours...
                </>
              ) : (
                <>
                  <Quote className="h-4 w-4 mr-2" />
                  Verifier les citations
                </>
              )}
            </Button>
          </form>
        </CardContent>
      </Card>

      {loading && (
        <div className="flex justify-center py-8">
          <Loader2 className="h-8 w-8 text-emerald-400 animate-spin" />
        </div>
      )}

      {result && (
        <div className="space-y-6">
          <Card className="border-emerald-500/30 bg-emerald-500/[0.04]">
            <CardContent className="p-6">
              <div className="flex flex-col md:flex-row items-center gap-8">
                <div className="text-center">
                  <div className="text-xs uppercase tracking-wide text-zinc-500 mb-1">Score de Citation IA</div>
                  <div className={`text-6xl font-bold tabular-nums ${getScoreColor(result.citation_score)}`}>
                    {result.citation_score}
                  </div>
                </div>
                <div className="flex-1 grid grid-cols-3 gap-4">
                  <div className="bg-white/[0.02] border border-white/5 p-4 rounded-lg text-center">
                    <div className="text-2xl font-bold text-zinc-100">{result.total_queries_tested}</div>
                    <div className="text-xs text-zinc-400 mt-1">Requetes testees</div>
                  </div>
                  <div className="bg-white/[0.02] border border-white/5 p-4 rounded-lg text-center">
                    <div className="text-2xl font-bold text-zinc-100">{result.times_cited}</div>
                    <div className="text-xs text-zinc-400 mt-1">Fois cite</div>
                  </div>
                  <div className="bg-white/[0.02] border border-white/5 p-4 rounded-lg text-center">
                    <div className={`text-2xl font-bold ${getScoreColor(result.citation_rate)}`}>{result.citation_rate}%</div>
                    <div className="text-xs text-zinc-400 mt-1">Taux de citation</div>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <div className="md:col-span-2 space-y-4">
              <h3 className="text-sm font-semibold uppercase tracking-wide text-zinc-200">
                Apercu des requetes
              </h3>
              <div className="space-y-3">
                {(result.results || []).map((req, i) => (
                  <Card key={i} className="border-white/5 bg-white/[0.01]">
                    <CardContent className="p-4 space-y-3">
                      <div className="flex items-start justify-between gap-4">
                        <div className="font-medium text-zinc-200 text-sm">"{req.query}"</div>
                        {req.cited ? (
                          <span className="flex items-center gap-1 text-xs text-emerald-400 bg-emerald-400/10 px-2 py-1 rounded border border-emerald-400/20 shrink-0">
                            <CheckCircle2 className="h-3 w-3" /> Cite
                          </span>
                        ) : (
                          <span className="flex items-center gap-1 text-xs text-zinc-500 bg-zinc-800 px-2 py-1 rounded border border-zinc-700 shrink-0">
                            <XCircle className="h-3 w-3" /> Non cite
                          </span>
                        )}
                      </div>
                      {req.context_snippet && (
                        <div className="text-xs text-zinc-400 italic bg-black/20 p-2 rounded border border-white/5">
                          <Quote className="h-3 w-3 inline mr-1 text-zinc-500" />
                          {req.context_snippet}
                        </div>
                      )}
                      {(req.competing_sources?.length ?? 0) > 0 && (
                        <div className="flex flex-wrap items-center gap-2 text-xs">
                          <span className="text-zinc-500 flex items-center gap-1">
                            <LinkIcon className="h-3 w-3" /> Sources:
                          </span>
                          {(req.competing_sources || []).map((src, j) => (
                            <span key={j} className="text-zinc-300 bg-white/5 px-1.5 py-0.5 rounded">{src}</span>
                          ))}
                        </div>
                      )}
                    </CardContent>
                  </Card>
                ))}
              </div>
            </div>

            <div className="space-y-6">
              <Card className="border-white/10 bg-white/[0.02]">
                <CardContent className="p-5">
                  <h3 className="text-sm font-semibold uppercase tracking-wide text-zinc-200 mb-4">
                    Top Sources Concurrentes
                  </h3>
                  <div className="space-y-2">
                    {(result.top_competing_sources || []).map((src, i) => (
                      <div key={i} className="flex items-center justify-between text-sm">
                        <span className="text-zinc-300 truncate mr-2">{src.domain}</span>
                        <span className="text-zinc-500 text-xs bg-zinc-800 px-1.5 py-0.5 rounded">
                          {src.count}
                        </span>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>

              <Card className="border-emerald-500/20 bg-emerald-500/[0.02]">
                <CardContent className="p-5">
                  <h3 className="text-sm font-semibold uppercase tracking-wide text-emerald-400 mb-4 flex items-center gap-2">
                    <Lightbulb className="h-4 w-4" /> Recommandations
                  </h3>
                  <ul className="space-y-3 text-sm text-zinc-300">
                    {(result.recommendations || []).map((rec, i) => (
                      <li key={i} className="flex items-start gap-2">
                        <ArrowRight className="h-4 w-4 text-emerald-500 shrink-0 mt-0.5" />
                        <span>{rec}</span>
                      </li>
                    ))}
                  </ul>
                </CardContent>
              </Card>
            </div>
          </div>

          <EmailGate
            headline="Recois l'analyse complete de tes citations IA"
            bulletPoints={[
              "Analyse sur 50+ requetes strategiques",
              "Sources IA concurrentes detaillees",
              "Plan d'action pour augmenter tes citations",
              "Suivi mensuel de ta progression"
            ]}
            domain={result.domain}
            tool="ai_citation"
          />

          <Card className="border-emerald-500/20 bg-emerald-500/[0.03]">
            <CardContent className="p-6 text-center space-y-3">
              <div className="flex items-center justify-center gap-2">
                <GridarMark className="h-5 w-5 text-emerald-400" />
                <h3 className="text-lg font-semibold text-zinc-100">
                  Prends ta place dans les reponses IA
                </h3>
              </div>
              <p className="text-sm text-zinc-400 max-w-lg mx-auto">
                Gridar optimise ton contenu pour etre cite par les IA en structurant tes donnees et en creant du contenu qui repond aux intentions complexes.
              </p>
              <Link href="/login">
                <Button className="bg-white text-zinc-950 hover:bg-zinc-200 font-semibold">
                  Creer mon projet Gridar
                  <ArrowRight className="h-4 w-4 ml-2" />
                </Button>
              </Link>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
