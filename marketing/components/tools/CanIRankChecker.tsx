"use client";

import { useState } from "react";
import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Target,
  Loader2,
  ArrowRight,
  CheckCircle2,
  AlertTriangle,
  Clock,
  Zap,
} from "lucide-react";
import { GridarMark } from "@/components/GridarMark";
import { toast } from "sonner";
import { EmailGate } from "@/components/tools/EmailGate";
import { ToolImageHero } from "@/components/tools/ToolImageHero";

const API_BASE = "";

type Factor = {
  name: string;
  score: number;
};

type QuickWin = {
  title: string;
  description: string;
};

type Competitor = {
  domain: string;
  authority: number;
};

type CanIRankResult = {
  domain: string;
  keyword: string;
  overall_score: number;
  verdict: "Facile" | "Possible" | "Difficile" | "Tres difficile";
  factors: Factor[];
  quick_wins: QuickWin[];
  top_competitors: Competitor[];
  estimated_time_to_rank: string;
};

function getScoreColor(s: number) {
  if (s >= 70) return "text-emerald-400";
  if (s >= 40) return "text-amber-400";
  return "text-red-400";
}

function getVerdictBadge(verdict: string) {
  switch (verdict) {
    case "Facile":
      return "bg-emerald-500/15 text-emerald-400 border-emerald-500/30";
    case "Possible":
      return "bg-amber-500/15 text-amber-400 border-amber-500/30";
    case "Difficile":
      return "bg-orange-500/15 text-orange-400 border-orange-500/30";
    case "Tres difficile":
      return "bg-red-500/15 text-red-400 border-red-500/30";
    default:
      return "bg-zinc-800 text-zinc-400 border-zinc-700";
  }
}

export function CanIRankChecker() {
  const [domain, setDomain] = useState("");
  const [keyword, setKeyword] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<CanIRankResult | null>(null);

  const runAnalysis = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!domain.trim() || !keyword.trim()) return;
    setLoading(true);
    setResult(null);
    try {
      const res = await fetch(`${API_BASE}/api/public/can-i-rank/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ domain: domain.trim(), keyword: keyword.trim() }),
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
    <>
      <ToolImageHero
        imageSrc="/hero-canirank.webp"
        title="Puis-je ranker sur ce mot-cle?"
        subtitle="Evalue tes chances reelles d'atteindre la premiere page selon l'autorite de ton domaine et tes concurrents actuels."
      >
      <Card className="mb-8">
        <CardContent className="p-4">
          <form onSubmit={runAnalysis} className="flex flex-col gap-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label htmlFor="domain">Ton domaine</Label>
                <Input
                  id="domain"
                  placeholder="tondomaine.com"
                  value={domain}
                  onChange={(e) => setDomain(e.target.value)}
                  disabled={loading}
                  required
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="keyword">Mot-cle vise</Label>
                <Input
                  id="keyword"
                  placeholder="ex: agence marketing montreal"
                  value={keyword}
                  onChange={(e) => setKeyword(e.target.value)}
                  disabled={loading}
                  required
                />
              </div>
            </div>
            <Button
              type="submit"
              disabled={loading || !domain.trim() || !keyword.trim()}
              className="bg-emerald-500 text-zinc-950 hover:bg-emerald-400 font-semibold w-full sm:w-auto self-end mt-2"
            >
              {loading ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Analyse en cours...
                </>
              ) : (
                <>
                  <Target className="h-4 w-4 mr-2" />
                  Analyser gratuitement
                </>
              )}
            </Button>
          </form>
        </CardContent>
      </Card>
      </ToolImageHero>

      <div className="max-w-3xl mx-auto px-4 pb-16 pt-8">
      {loading && (
        <div className="flex justify-center py-8">
          <Loader2 className="h-8 w-8 text-emerald-400 animate-spin" />
        </div>
      )}

      {result && (
        <div className="space-y-6">
          <Card className="border-emerald-500/30 bg-emerald-500/[0.04]">
            <CardContent className="p-6 md:p-8 flex flex-col md:flex-row items-center gap-8">
              <div className="relative flex items-center justify-center shrink-0">
                <svg className="w-32 h-32 transform -rotate-90">
                  <circle
                    cx="64"
                    cy="64"
                    r="56"
                    stroke="currentColor"
                    strokeWidth="8"
                    fill="transparent"
                    className="text-zinc-800"
                  />
                  <circle
                    cx="64"
                    cy="64"
                    r="56"
                    stroke="currentColor"
                    strokeWidth="8"
                    fill="transparent"
                    strokeDasharray={2 * Math.PI * 56}
                    strokeDashoffset={2 * Math.PI * 56 * (1 - result.overall_score / 100)}
                    className={`${getScoreColor(result.overall_score)} transition-all duration-1000`}
                  />
                </svg>
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                  <span className={`text-3xl font-bold tabular-nums ${getScoreColor(result.overall_score)}`}>
                    {result.overall_score}
                  </span>
                  <span className="text-xs text-zinc-500">/100</span>
                </div>
              </div>
              <div className="text-center md:text-left space-y-3">
                <h2 className="text-xl font-bold text-zinc-100">Score de probabilite</h2>
                <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium border ${getVerdictBadge(result.verdict)}`}>
                  Verdict: {result.verdict}
                </span>
                <p className="text-sm text-zinc-400">
                  Selon notre analyse, tes chances de ranker sur <strong>"{result.keyword}"</strong> avec <strong>{result.domain}</strong> sont de {result.overall_score}%.
                </p>
                <div className="flex items-center justify-center md:justify-start gap-2 text-sm text-zinc-300 mt-2">
                  <Clock className="h-4 w-4 text-emerald-400" />
                  <span>Temps estime: {result.estimated_time_to_rank}</span>
                </div>
              </div>
            </CardContent>
          </Card>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Card className="border-white/10 bg-white/[0.02]">
              <CardContent className="p-5">
                <h3 className="text-sm font-semibold uppercase tracking-wide text-zinc-200 mb-4">
                  Facteurs de ranking
                </h3>
                <div className="space-y-4">
                  {(result.factors || []).map((factor, i) => (
                    <div key={i} className="space-y-1.5">
                      <div className="flex items-center justify-between text-xs">
                        <span className="text-zinc-300">{factor.name}</span>
                        <span className={getScoreColor(factor.score)}>{factor.score}/100</span>
                      </div>
                      <div className="w-full bg-zinc-800 rounded-full h-1.5">
                        <div
                          className="bg-emerald-500 h-1.5 rounded-full transition-all duration-500"
                          style={{ width: `${Math.min(100, factor.score)}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>

            <Card className="border-white/10 bg-white/[0.02]">
              <CardContent className="p-5">
                <h3 className="text-sm font-semibold uppercase tracking-wide text-zinc-200 mb-4 flex items-center gap-2">
                  <Zap className="h-4 w-4 text-amber-400" />
                  Gains rapides
                </h3>
                <div className="space-y-3">
                  {(result.quick_wins || []).map((qw, i) => (
                    <div key={i} className="flex items-start gap-3 bg-white/[0.02] p-3 rounded-md border border-white/5">
                      <div className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-emerald-500/20 text-[10px] font-bold text-emerald-400 mt-0.5">
                        {i + 1}
                      </div>
                      <div>
                        <h4 className="text-sm font-medium text-zinc-200">{qw.title}</h4>
                        <p className="text-xs text-zinc-400 mt-0.5">{qw.description}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </div>

          <Card className="border-white/10 bg-white/[0.02]">
            <CardContent className="p-5">
              <h3 className="text-sm font-semibold uppercase tracking-wide text-zinc-200 mb-4">
                Top Concurrents Actuels
              </h3>
              <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
                {(result.top_competitors || []).map((comp, i) => (
                  <div key={i} className="flex items-center justify-between p-3 rounded border border-white/5 bg-zinc-900/50">
                    <span className="text-sm text-zinc-300 truncate mr-2">{comp.domain}</span>
                    <span className="text-xs font-mono px-2 py-0.5 bg-zinc-800 rounded text-emerald-400">
                      DA {comp.authority}
                    </span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          <EmailGate
            headline="Recois le plan d'action complet pour ranker sur ce mot-cle"
            bulletPoints={[
              "Analyse detaillee de 50+ facteurs de ranking",
              "Plan de contenu sur mesure",
              "Strategie de backlinks recommandee",
              "Calendrier d'execution mois par mois"
            ]}
            domain={result.domain}
            tool="can_i_rank"
          />

          <Card className="border-emerald-500/20 bg-emerald-500/[0.03]">
            <CardContent className="p-6 text-center space-y-3">
              <div className="flex items-center justify-center gap-2">
                <GridarMark className="h-5 w-5 text-emerald-400" />
                <h3 className="text-lg font-semibold text-zinc-100">
                  Besoin d'aide pour depasser ces concurrents?
                </h3>
              </div>
              <p className="text-sm text-zinc-400 max-w-lg mx-auto">
                Gridar cree le plan et execute la strategie pour toi. Nous construisons l'autorite de ton domaine et ton contenu mois apres mois.
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
    </>
  );
}
