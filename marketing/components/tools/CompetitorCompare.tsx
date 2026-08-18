"use client";

import { useState } from "react";
import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  GitCompare,
  Loader2,
  ArrowRight,
  Trophy,
  AlertTriangle,
  Zap,
  TrendingUp,
  ShieldCheck,
  CheckCircle2,
} from "lucide-react";
import { GridarMark } from "@/components/GridarMark";
import { toast } from "sonner";
import { EmailGate } from "@/components/tools/EmailGate";

const API_BASE = "";

type CategoryScore = {
  category: string;
  domain_score: number;
  competitor_score: number;
  insight: string;
};

type CompareResult = {
  domain: string;
  competitor: string;
  overall_winner: "domain" | "competitor" | "tie";
  domain_total_score: number;
  competitor_total_score: number;
  categories: CategoryScore[];
  domain_advantages: string[];
  competitor_advantages: string[];
  action_items: { priority: "Haute" | "Moyenne" | "Basse", text: string }[];
};

function getWinnerStyle(isWinner: boolean) {
  if (isWinner) return "border-emerald-500/50 bg-emerald-500/10";
  return "border-white/10 bg-white/[0.02]";
}

function getWinnerIcon(isWinner: boolean) {
  if (isWinner) return <Trophy className="h-5 w-5 text-emerald-400" />;
  return null;
}

export function CompetitorCompare() {
  const [domain, setDomain] = useState("");
  const [competitor, setCompetitor] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<CompareResult | null>(null);

  const runAnalysis = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!domain.trim() || !competitor.trim()) return;
    setLoading(true);
    setResult(null);
    try {
      const res = await fetch(`${API_BASE}/api/public/competitor-compare/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ domain: domain.trim(), competitor: competitor.trim() }),
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
      <div className="text-center mb-8">
        <div className="inline-flex items-center gap-2 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-xs font-medium text-emerald-300 mb-4">
          <GitCompare className="h-3 w-3" />
          <span>Comparaison de Concurrents</span>
        </div>
        <h1 className="text-3xl md:text-4xl font-bold tracking-tight mb-3">
          Qui a la meilleure strategie SEO?
        </h1>
        <p className="text-base md:text-lg text-zinc-400 max-w-xl mx-auto">
          Compare ton site a ton concurrent principal sur 20+ dimensions et decouvre comment le depasser.
        </p>
      </div>

      <Card className="mb-8">
        <CardContent className="p-4">
          <form onSubmit={runAnalysis} className="flex flex-col gap-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label htmlFor="domain">Ton site</Label>
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
                <Label htmlFor="competitor">Ton concurrent</Label>
                <Input
                  id="competitor"
                  placeholder="concurrent.com"
                  value={competitor}
                  onChange={(e) => setCompetitor(e.target.value)}
                  disabled={loading}
                  required
                />
              </div>
            </div>
            <div className="flex justify-center md:justify-end mt-2">
              <Button
                type="submit"
                disabled={loading || !domain.trim() || !competitor.trim()}
                className="bg-emerald-500 text-zinc-950 hover:bg-emerald-400 font-semibold w-full md:w-auto"
              >
                {loading ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Analyse en cours...
                  </>
                ) : (
                  <>
                    <GitCompare className="h-4 w-4 mr-2" />
                    Comparer les sites
                  </>
                )}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {loading && (
        <div className="flex justify-center py-8">
          <Loader2 className="h-8 w-8 text-emerald-400 animate-spin" />
        </div>
      )}

      {result && (
        <div className="space-y-8">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Card className={`border-2 ${getWinnerStyle(result.overall_winner === "domain")}`}>
              <CardContent className="p-6 text-center space-y-2 relative">
                {result.overall_winner === "domain" && (
                  <div className="absolute top-4 right-4"><Trophy className="h-6 w-6 text-emerald-400" /></div>
                )}
                <div className="text-sm font-semibold uppercase tracking-wide text-zinc-400">Ton site</div>
                <div className="text-xl font-bold text-zinc-100">{result.domain}</div>
                <div className="text-4xl font-black text-emerald-400">{result.domain_total_score}<span className="text-xl text-zinc-500">/100</span></div>
              </CardContent>
            </Card>

            <Card className={`border-2 ${getWinnerStyle(result.overall_winner === "competitor")}`}>
              <CardContent className="p-6 text-center space-y-2 relative">
                {result.overall_winner === "competitor" && (
                  <div className="absolute top-4 right-4"><Trophy className="h-6 w-6 text-emerald-400" /></div>
                )}
                <div className="text-sm font-semibold uppercase tracking-wide text-zinc-400">Concurrent</div>
                <div className="text-xl font-bold text-zinc-100">{result.competitor}</div>
                <div className="text-4xl font-black text-zinc-300">{result.competitor_total_score}<span className="text-xl text-zinc-500">/100</span></div>
              </CardContent>
            </Card>
          </div>

          <Card className="border-white/10 bg-white/[0.02]">
            <CardContent className="p-6">
              <h3 className="text-sm font-semibold uppercase tracking-wide text-zinc-200 mb-6">
                Comparaison par categorie
              </h3>
              <div className="space-y-6">
                {result.categories.map((cat, i) => (
                  <div key={i} className="space-y-2">
                    <div className="flex justify-between items-center text-sm">
                      <span className="font-medium text-zinc-300">{cat.category}</span>
                      <span className="text-xs text-zinc-500 italic hidden sm:block">{cat.insight}</span>
                    </div>
                    <div className="grid grid-cols-[1fr_auto_1fr] gap-4 items-center">
                      <div className="flex flex-col gap-1 items-end">
                        <span className="text-xs text-emerald-400">{cat.domain_score}/100</span>
                        <div className="w-full bg-zinc-800 rounded-full h-2 flex justify-end">
                          <div
                            className="bg-emerald-500 h-2 rounded-full transition-all duration-500"
                            style={{ width: `${cat.domain_score}%` }}
                          />
                        </div>
                      </div>
                      <div className="text-zinc-600 text-xs">VS</div>
                      <div className="flex flex-col gap-1 items-start">
                        <span className="text-xs text-zinc-400">{cat.competitor_score}/100</span>
                        <div className="w-full bg-zinc-800 rounded-full h-2">
                          <div
                            className="bg-zinc-500 h-2 rounded-full transition-all duration-500"
                            style={{ width: `${cat.competitor_score}%` }}
                          />
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Card className="border-emerald-500/20 bg-emerald-500/[0.02]">
              <CardContent className="p-5">
                <h3 className="text-sm font-semibold uppercase tracking-wide text-emerald-400 mb-4 flex items-center gap-2">
                  <ShieldCheck className="h-4 w-4" /> Tes Avantages
                </h3>
                <ul className="space-y-3">
                  {result.domain_advantages.map((adv, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-zinc-300">
                      <CheckCircle2 className="h-4 w-4 text-emerald-500 shrink-0 mt-0.5" />
                      <span>{adv}</span>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>

            <Card className="border-red-500/20 bg-red-500/[0.02]">
              <CardContent className="p-5">
                <h3 className="text-sm font-semibold uppercase tracking-wide text-red-400 mb-4 flex items-center gap-2">
                  <AlertTriangle className="h-4 w-4" /> Avantages du concurrent
                </h3>
                <ul className="space-y-3">
                  {result.competitor_advantages.map((adv, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-zinc-300">
                      <Zap className="h-4 w-4 text-red-500 shrink-0 mt-0.5" />
                      <span>{adv}</span>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          </div>

          <Card className="border-amber-500/20 bg-amber-500/[0.02]">
            <CardContent className="p-6">
              <h3 className="text-sm font-semibold uppercase tracking-wide text-amber-400 mb-4 flex items-center gap-2">
                 Plan d'action prioritaire
              </h3>
              <div className="space-y-3">
                {result.action_items.map((item, i) => (
                  <div key={i} className="flex items-start gap-3 bg-white/[0.02] p-3 rounded-md border border-white/5">
                    <span className={`text-[10px] uppercase font-bold px-2 py-0.5 rounded border mt-0.5 shrink-0 ${
                      item.priority === "Haute" ? "bg-red-500/10 text-red-400 border-red-500/20" :
                      item.priority === "Moyenne" ? "bg-amber-500/10 text-amber-400 border-amber-500/20" :
                      "bg-zinc-500/10 text-zinc-400 border-zinc-500/20"
                    }`}>
                      {item.priority}
                    </span>
                    <span className="text-sm text-zinc-300">{item.text}</span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          <EmailGate
            headline="Recois la comparaison complete avec plan d'action"
            bulletPoints={[
              "Analyse de 20+ dimensions SEO",
              "Forces et faiblesses detaillees",
              "Opportunites de depassement",
              "Plan d'action prioritise"
            ]}
            domain={result.domain}
            tool="competitor_compare"
          />

          <Card className="border-emerald-500/20 bg-emerald-500/[0.03]">
            <CardContent className="p-6 text-center space-y-3">
              <div className="flex items-center justify-center gap-2">
                <GridarMark className="h-5 w-5 text-emerald-400" />
                <h3 className="text-lg font-semibold text-zinc-100">
                  Pret a depasser ce concurrent?
                </h3>
              </div>
              <p className="text-sm text-zinc-400 max-w-lg mx-auto">
                Gridar analyse et depasse tes concurrents systematiquement. Nous executons le plan d'action pour prendre la premiere place.
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
