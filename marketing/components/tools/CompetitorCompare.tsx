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
import { ToolImageHero } from "@/components/tools/ToolImageHero";

const API_BASE = "";

type CategoryScore = {
  category: string;
  // null = la mesure n'a pas pu etre faite. Surtout pas 0, qui se lirait
  // comme un verdict alors que c'est une absence de donnee.
  domain_score: number | null;
  competitor_score: number | null;
  winner: "domain" | "competitor" | "tie";
  available: boolean;
  reason: string | null;
  domain_evidence: string[];
  competitor_evidence: string[];
  insight: string;
};

type CompareResult = {
  domain: string;
  competitor: string;
  brand?: string;
  competitor_brand?: string;
  overall_winner: "domain" | "competitor" | "tie";
  domain_total_score: number | null;
  competitor_total_score: number | null;
  categories_mesurees: number;
  categories_total: number;
  methodologie: string;
  categories: CategoryScore[];
  summary: string;
  domain_advantages: string[];
  competitor_advantages: string[];
  action_items: { priority: "Haute" | "Moyenne" | "Basse", text: string }[];
  queries_tested: string[];
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
    <>
      <ToolImageHero imageSrc="/hero-versus.webp" title="Qui a la meilleure strategie SEO?" subtitle="Compare ton site a ton concurrent principal sur 6 categories mesurees et decouvre comment le depasser.">
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
      </ToolImageHero>

      <div className="max-w-4xl mx-auto px-4 pb-16 pt-8">
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
                <div className="text-4xl font-black text-emerald-400">
                  {result.domain_total_score ?? "-"}<span className="text-xl text-zinc-500">/100</span>
                </div>
              </CardContent>
            </Card>

            <Card className={`border-2 ${getWinnerStyle(result.overall_winner === "competitor")}`}>
              <CardContent className="p-6 text-center space-y-2 relative">
                {result.overall_winner === "competitor" && (
                  <div className="absolute top-4 right-4"><Trophy className="h-6 w-6 text-emerald-400" /></div>
                )}
                <div className="text-sm font-semibold uppercase tracking-wide text-zinc-400">Concurrent</div>
                <div className="text-xl font-bold text-zinc-100">{result.competitor}</div>
                <div className="text-4xl font-black text-zinc-300">
                  {result.competitor_total_score ?? "-"}<span className="text-xl text-zinc-500">/100</span>
                </div>
              </CardContent>
            </Card>
          </div>

          <Card className="border-white/10 bg-white/[0.02]">
            <CardContent className="p-6">
              <div className="flex flex-wrap items-baseline justify-between gap-2 mb-6">
                <h3 className="text-sm font-semibold uppercase tracking-wide text-zinc-200">
                  Comparaison par categorie
                </h3>
                <span className="text-xs text-zinc-500">
                  {result.categories_mesurees}/{result.categories_total} categories mesurees
                </span>
              </div>
              <div className="space-y-6">
                {(result.categories || []).map((cat, i) => (
                  <div key={i} className="space-y-2">
                    <div className="flex justify-between items-center text-sm">
                      <span className="font-medium text-zinc-300">{cat.category}</span>
                      <span className="text-xs text-zinc-500 italic hidden sm:block">{cat.insight}</span>
                    </div>

                    {cat.available ? (
                      <>
                        <div className="grid grid-cols-[1fr_auto_1fr] gap-4 items-center">
                          <div className="flex flex-col gap-1 items-end">
                            <span className="text-xs text-emerald-400">{cat.domain_score}/100</span>
                            <div className="w-full bg-zinc-800 rounded-full h-2 flex justify-end">
                              <div
                                className="bg-emerald-500 h-2 rounded-full transition-all duration-500"
                                style={{ width: `${cat.domain_score ?? 0}%` }}
                              />
                            </div>
                          </div>
                          <div className="text-zinc-600 text-xs">VS</div>
                          <div className="flex flex-col gap-1 items-start">
                            <span className="text-xs text-zinc-400">{cat.competitor_score}/100</span>
                            <div className="w-full bg-zinc-800 rounded-full h-2">
                              <div
                                className="bg-zinc-500 h-2 rounded-full transition-all duration-500"
                                style={{ width: `${cat.competitor_score ?? 0}%` }}
                              />
                            </div>
                          </div>
                        </div>
                        {(cat.domain_evidence?.length || cat.competitor_evidence?.length) ? (
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-1 text-[11px] leading-relaxed text-zinc-500">
                            <ul className="space-y-0.5 sm:text-right">
                              {(cat.domain_evidence || []).map((p, j) => <li key={j}>{p}</li>)}
                            </ul>
                            <ul className="space-y-0.5">
                              {(cat.competitor_evidence || []).map((p, j) => <li key={j}>{p}</li>)}
                            </ul>
                          </div>
                        ) : null}
                      </>
                    ) : (
                      /* Pas de barre, pas de zero. Un zero se lirait comme un
                         verdict alors que c'est une absence de mesure. */
                      <div className="rounded-md border border-dashed border-white/10 px-3 py-2 text-xs text-zinc-500">
                        Non mesure{cat.reason ? ` : ${cat.reason}` : ""}
                      </div>
                    )}
                  </div>
                ))}
              </div>
              {result.methodologie && (
                <p className="mt-6 border-t border-white/5 pt-4 text-[11px] leading-relaxed text-zinc-500">
                  {result.methodologie}
                </p>
              )}
            </CardContent>
          </Card>

          {result.summary && (
            <Card className="border-white/10 bg-white/[0.02]">
              <CardContent className="p-6">
                <h3 className="text-sm font-semibold uppercase tracking-wide text-zinc-200 mb-3">
                  Ce qu'il faut retenir
                </h3>
                <p className="text-sm leading-relaxed text-zinc-400">{result.summary}</p>
              </CardContent>
            </Card>
          )}

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Card className="border-emerald-500/20 bg-emerald-500/[0.02]">
              <CardContent className="p-5">
                <h3 className="text-sm font-semibold uppercase tracking-wide text-emerald-400 mb-4 flex items-center gap-2">
                  <ShieldCheck className="h-4 w-4" /> Tes Avantages
                </h3>
                <ul className="space-y-3">
                  {(result.domain_advantages || []).map((adv, i) => (
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
                  {(result.competitor_advantages || []).map((adv, i) => (
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
                {(result.action_items || []).map((item, i) => (
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
              "6 categories mesurees, preuves a l'appui",
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
    </>
  );
}
