"use client";

import { useState } from "react";
import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Loader2,
  ArrowRight,
  TrendingUp,
  Search,
  Target,
  Plus,
  X,
} from "lucide-react";
import { GridarMark } from "@/components/GridarMark";
import { toast } from "sonner";
import { EmailGate } from "@/components/tools/EmailGate";
import { ToolImageHero } from "@/components/tools/ToolImageHero";

const API_BASE = "";

type Opportunity = {
  keyword: string;
  competitor: string;
  position: number;
  intent: string;
  opportunity_score: number;
};

type GapResult = {
  domain: string;
  brand: string;
  sector: string;
  analyzed_at: string;
  competitors_detected: string[];
  competitors_source?: "deduits" | "fournis" | "aucun";
  queries_tested?: string[];
  queries_checked?: number;
  domain_ranks_for?: string[];
  total_gaps: number;
  // null : on n'a pas d'API de volume de recherche. L'ancienne version
  // affichait `total_gaps * 320`, un chiffre invente presente comme une
  // estimation de trafic.
  estimated_monthly_searches: number | null;
  // Present quand il n'y a rien a montrer, pour expliquer POURQUOI. Un
  // total_gaps: 0 muet se lit comme "ton site n'a aucun retard".
  notice?: string;
  top_opportunities: Opportunity[];
  gated: {
    all_opportunities: Opportunity[];
    remaining_count: number;
  };
};

const INTENT_STYLES: Record<string, string> = {
  commercial: "bg-emerald-500/15 text-emerald-300 border-emerald-500/30",
  transactional: "bg-blue-500/15 text-blue-300 border-blue-500/30",
  informational: "bg-zinc-500/15 text-zinc-400 border-zinc-600",
  navigational: "bg-amber-500/15 text-amber-300 border-amber-500/30",
  local: "bg-teal-500/15 text-teal-300 border-teal-500/30",
};

const INTENT_LABELS: Record<string, string> = {
  commercial: "Commercial",
  transactional: "Transactionnel",
  informational: "Informationnel",
  navigational: "Navigationnel",
  local: "Local",
};

function scoreColor(s: number) {
  if (s >= 80) return "text-emerald-400";
  if (s >= 60) return "text-amber-400";
  return "text-zinc-400";
}

export function CompetitorGapFinder() {
  const [domain, setDomain] = useState("");
  const [showCompetitors, setShowCompetitors] = useState(false);
  const [competitor1, setCompetitor1] = useState("");
  const [competitor2, setCompetitor2] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<GapResult | null>(null);

  const runAnalysis = async (e: React.FormEvent) => {
    e.preventDefault();
    const clean = domain.trim();
    if (!clean) return;
    setLoading(true);
    setResult(null);
    try {
      const competitors: string[] = [];
      if (competitor1.trim()) competitors.push(competitor1.trim());
      if (competitor2.trim()) competitors.push(competitor2.trim());

      const res = await fetch(`${API_BASE}/api/public/competitor-gap/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ domain: clean, competitors }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error || "Analyse impossible pour le moment.");
      }
      const data = (await res.json()) as GapResult;
      setResult(data);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Erreur");
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <ToolImageHero imageSrc="/hero-gap.webp" title="Tes concurrents gagnent sur des mots-cles ou tu es absent" subtitle="Trouve les opportunites SEO que tes concurrents exploitent mais que tu laisses passer.">
        {/* Input form */}
        <Card className="mb-8">
        <CardContent className="p-5">
          <form onSubmit={runAnalysis} className="space-y-3">
            <div>
              <Label htmlFor="gap-domain" className="text-zinc-300 text-sm">
                Ton site web
              </Label>
              <Input
                id="gap-domain"
                type="text"
                inputMode="url"
                placeholder="tondomaine.com"
                value={domain}
                onChange={(e) => setDomain(e.target.value)}
                disabled={loading}
                required
              />
            </div>

            {showCompetitors ? (
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <Label className="text-zinc-400 text-xs">
                    Concurrents (facultatif)
                  </Label>
                  <button
                    type="button"
                    onClick={() => {
                      setShowCompetitors(false);
                      setCompetitor1("");
                      setCompetitor2("");
                    }}
                    className="text-xs text-zinc-500 hover:text-zinc-300"
                  >
                    <X className="h-3 w-3 inline mr-1" />
                    Retirer
                  </button>
                </div>
                <Input
                  type="text"
                  placeholder="concurrent1.com"
                  value={competitor1}
                  onChange={(e) => setCompetitor1(e.target.value)}
                  disabled={loading}
                />
                <Input
                  type="text"
                  placeholder="concurrent2.com"
                  value={competitor2}
                  onChange={(e) => setCompetitor2(e.target.value)}
                  disabled={loading}
                />
              </div>
            ) : (
              <button
                type="button"
                onClick={() => setShowCompetitors(true)}
                className="flex items-center gap-1 text-xs text-zinc-500 hover:text-zinc-300"
              >
                <Plus className="h-3 w-3" />
                Ajouter des concurrents (facultatif)
              </button>
            )}

            <Button
              type="submit"
              disabled={loading || !domain.trim()}
              className="w-full bg-emerald-500 text-zinc-950 hover:bg-emerald-400 font-semibold"
            >
              {loading ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Analyse des concurrents...
                </>
              ) : (
                <>
                  <Search className="h-4 w-4 mr-2" />
                  Trouver les opportunites manquees
                </>
              )}
            </Button>
            <p className="text-center text-xs text-zinc-500">
              Si tu ne connais pas tes concurrents, Gridar les detecte
              automatiquement.
            </p>
          </form>
        </CardContent>
      </Card>
      </ToolImageHero>

      <div className="max-w-3xl mx-auto px-4 pb-16 pt-8">
      {/* Loading */}
      {loading && (
        <div className="space-y-3 mb-8">
          {[
            "Detection des concurrents SERP...",
            "Analyse des mots-cles concurrents...",
            "Identification des gaps...",
            "Calcul des scores d'opportunite...",
          ].map((step, i) => (
            <div
              key={i}
              className="flex items-center gap-3 text-sm text-zinc-400"
            >
              <Loader2 className="h-3.5 w-3.5 animate-spin text-emerald-400" />
              <span>{step}</span>
            </div>
          ))}
        </div>
      )}

      {/* Results */}
      {result && (
        <div className="space-y-6">
          {/* Summary hero */}
          <Card className="border-emerald-500/30 bg-emerald-500/[0.04]">
            <CardContent className="p-6 text-center">
              {result.notice ? (
                /* Rien a montrer, mais on dit POURQUOI. Un zero muet se lit
                   comme "ton site n'a aucun retard", l'inverse de la verite. */
                <p className="text-base leading-relaxed text-zinc-300">
                  {result.notice}
                </p>
              ) : (
                <>
                  <p className="text-sm text-zinc-400 mb-2">
                    Tes concurrents gagnent sur
                  </p>
                  <div className="text-5xl font-bold text-emerald-400 tabular-nums mb-1">
                    {result.total_gaps}
                  </div>
                  <p className="text-base text-zinc-200 mb-3">
                    mots-cles ou ton site est absent.
                  </p>
                  {typeof result.queries_checked === "number" && (
                    <div className="flex items-center justify-center gap-2 text-sm text-zinc-400">
                      <TrendingUp className="h-4 w-4 text-emerald-400" />
                      <span>
                        Sur{" "}
                        <strong className="text-zinc-100">
                          {result.queries_checked}
                        </strong>{" "}
                        recherches reellement testees
                        {result.domain_ranks_for?.length
                          ? `, ton site en place ${result.domain_ranks_for.length}`
                          : ""}
                      </span>
                    </div>
                  )}
                </>
              )}
            </CardContent>
          </Card>

          {/* Competitors detected */}
          {result.competitors_detected.length > 0 && (
            <div className="flex flex-wrap gap-2">
              <span className="text-xs text-zinc-500">Concurrents :</span>
              {result.competitors_detected.map((c, i) => (
                <span
                  key={i}
                  className="text-xs font-mono text-zinc-400 bg-zinc-800 rounded px-2 py-0.5"
                >
                  {c}
                </span>
              ))}
            </div>
          )}

          {/* Top 5 opportunities */}
          {result.top_opportunities.length > 0 && (
            <Card className="border-white/10 bg-white/[0.02]">
              <CardContent className="p-5">
                <div className="flex items-center gap-2 mb-4 text-zinc-200">
                  <Target className="h-4 w-4 text-emerald-400" />
                  <h3 className="text-sm font-semibold uppercase tracking-wide">
                    Meilleures opportunites
                  </h3>
                </div>
                <div className="space-y-3">
                  {result.top_opportunities.map((opp, i) => (
                    <div
                      key={i}
                      className="flex items-center justify-between gap-3 rounded-md border border-white/5 bg-white/[0.02] p-3"
                    >
                      <div className="min-w-0 flex-1">
                        <p className="text-sm text-zinc-100 font-medium truncate">
                          {opp.keyword}
                        </p>
                        <div className="flex items-center gap-2 mt-1">
                          <span className="text-xs text-zinc-500 font-mono">
                            {opp.competitor}
                          </span>
                          <span
                            className={`inline-flex items-center rounded-full border px-1.5 py-0.5 text-[10px] font-medium ${INTENT_STYLES[opp.intent] || INTENT_STYLES.informational}`}
                          >
                            {INTENT_LABELS[opp.intent] || opp.intent}
                          </span>
                        </div>
                      </div>
                      <div className="text-right shrink-0">
                        <div
                          className={`text-lg font-bold tabular-nums ${scoreColor(opp.opportunity_score)}`}
                        >
                          {opp.opportunity_score}
                        </div>
                        <div className="text-[10px] text-zinc-500 uppercase">
                          Score
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Email gate */}
          {result.gated.remaining_count > 0 && (
            <EmailGate
              headline="Recois la liste complete des opportunites"
              bulletPoints={[
                "Tous les mots-cles manques avec score d'opportunite",
                "Les pages concurrentes qui rankent",
                "L'intention de recherche de chaque mot-cle",
                "Les pages que tu devrais creer en priorite",
                "L'ordre de creation recommande",
              ]}
              domain={result.domain}
              tool="competitor_gap"
              hiddenCount={result.gated.remaining_count}
              hiddenLabel="autres opportunites trouvees"
            />
          )}

          {/* CTA Gridar */}
          <Card className="border-emerald-500/20 bg-emerald-500/[0.03]">
            <CardContent className="p-6 text-center space-y-3">
              <div className="flex items-center justify-center gap-2">
                <GridarMark className="h-5 w-5 text-emerald-400" />
                <h3 className="text-lg font-semibold text-zinc-100">
                  Transforme ces opportunites en pages
                </h3>
              </div>
              <p className="text-sm text-zinc-400 max-w-lg mx-auto">
                Gridar peut generer automatiquement les articles et les pages
                d'atterrissage pour capturer ces mots-cles. Contenu optimise en
                francais quebecois.
              </p>
              <Link href="/login">
                <Button className="bg-white text-zinc-950 hover:bg-zinc-200 font-semibold">
                  Creer ces opportunites dans Gridar
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
