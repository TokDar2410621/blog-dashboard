"use client";

import { useState } from "react";
import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Eye,
  Loader2,
  ArrowRight,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Sparkles,
  TrendingUp,
  Users,
  Zap,
  Shield,
} from "lucide-react";
import { GridarMark } from "@/components/GridarMark";
import { toast } from "sonner";
import { EmailGate } from "@/components/tools/EmailGate";
import { AiVisibilityHero } from "@/components/tools/AiVisibilityHero";

const API_BASE = "";

type EngineBreakdown = {
  total: number;
  mentioned: number;
  rate: number;
};

type Competitor = {
  domain: string;
  mentions: number;
};

type SampleQuery = {
  query: string;
  engine: string;
  mentioned: boolean;
};

type AiVisResult = {
  domain: string;
  brand: string;
  sector: string;
  analyzed_at: string;
  ai_visibility_score: number;
  scores_breakdown: {
    score: number;
    mention_rate: number;
    citation_rate: number;
    share_of_voice: number;
    position_score: number;
  };
  engine_breakdown: Record<string, EngineBreakdown>;
  total_queries_tested: number;
  total_mentions: number;
  top_competitors: Competitor[];
  sample_queries: SampleQuery[];
  gated: {
    all_competitors: Competitor[];
    competitor_only_queries: { query: string; competitors: string[] }[];
    competitor_only_count: number;
    all_results: unknown[];
  };
};

function scoreColor(s: number) {
  if (s >= 80) return "text-emerald-400";
  if (s >= 60) return "text-amber-400";
  return "text-red-400";
}

function scoreLabel(s: number) {
  if (s >= 80) return "Excellente visibilite";
  if (s >= 60) return "Visibilite correcte";
  if (s >= 40) return "Visibilite faible";
  return "Presque invisible";
}

function businessConsequence(result: AiVisResult): string {
  const score = result.ai_visibility_score;
  const compCount = result.top_competitors.length;
  const gapCount = result.gated.competitor_only_count;

  if (score >= 80) {
    return "Ton entreprise est bien positionnee dans les reponses IA. Continue de produire du contenu de qualite pour maintenir cet avantage.";
  }
  if (score >= 60) {
    return `Ta visibilite IA est correcte, mais ${compCount} concurrent${compCount > 1 ? "s" : ""} sont mentionnes plus souvent. Il y a ${gapCount} requete${gapCount > 1 ? "s" : ""} ou ils apparaissent et pas toi.`;
  }
  if (score >= 30) {
    return `Quand un client potentiel demande a l'IA de Google (Gemini) une recommandation dans ton domaine, tes concurrents apparaissent ${compCount > 0 ? `${result.top_competitors[0]?.mentions || 0}x plus souvent` : "et pas toi"}. Chaque jour sans action, c'est du trafic qualifie qui va ailleurs.`;
  }
  return `Ton entreprise est quasi invisible pour l'IA de Google. Quand quelqu'un demande une recommandation dans ton secteur, l'IA ne te mentionne pas. Tes concurrents captent ce trafic a ta place.`;
}

const ENGINE_LABELS: Record<string, string> = {
  chatgpt: "ChatGPT",
  perplexity: "Perplexity",
  gemini: "Gemini",
  searchgpt: "SearchGPT",
  claude: "Claude",
};

const ENGINE_COLORS: Record<string, string> = {
  chatgpt: "text-emerald-400 bg-emerald-500/15 border-emerald-500/30",
  perplexity: "text-teal-300 bg-teal-500/15 border-teal-500/30",
  gemini: "text-blue-300 bg-blue-500/15 border-blue-500/30",
  searchgpt: "text-neutral-200 bg-neutral-500/15 border-neutral-500/40",
  claude: "text-orange-300 bg-orange-500/15 border-orange-500/30",
};

export function AiVisibilityChecker() {
  const [domain, setDomain] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AiVisResult | null>(null);

  const runAnalysis = async (e: React.FormEvent) => {
    e.preventDefault();
    const clean = domain.trim();
    if (!clean) return;
    setLoading(true);
    setResult(null);
    try {
      const res = await fetch(`${API_BASE}/api/public/ai-visibility/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ domain: clean }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error || "Analyse impossible pour le moment.");
      }
      const data = (await res.json()) as AiVisResult;
      setResult(data);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Erreur");
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <AiVisibilityHero>
        {/* Input form */}
        <Card>
        <CardContent className="p-4">
          <form
            onSubmit={runAnalysis}
            className="flex flex-col sm:flex-row gap-2"
          >
            <Input
              type="text"
              inputMode="url"
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
                  <Eye className="h-4 w-4 mr-2" />
                  Analyser gratuitement
                </>
              )}
            </Button>
          </form>
          <p className="text-center text-xs text-zinc-500 mt-2">
            Aucune inscription. Resultat en moins de 60 secondes.
          </p>
        </CardContent>
      </Card>
      </AiVisibilityHero>

      <div className="max-w-3xl mx-auto px-4 pb-16 pt-8">
      {/* Loading state */}
      {loading && (
        <div className="space-y-3 mb-8">
          {[
            "Detection du secteur et de la marque...",
            "Generation de requetes commerciales...",
            "Interrogation de l'IA de Google...",
            "Calcul du score de visibilite...",
          ].map((step, i) => (
            <div
              key={i}
              className="flex items-center gap-3 text-sm text-zinc-400"
              style={{ animationDelay: `${i * 2}s` }}
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
          {/* Score hero */}
          <Card className="border-emerald-500/30 bg-emerald-500/[0.04]">
            <CardContent className="p-6">
              <div className="flex items-center gap-1.5 text-xs uppercase tracking-wide text-zinc-400 mb-1">
                <Eye className="h-3.5 w-3.5" />
                AI Visibility Score
              </div>
              <div className="flex items-baseline gap-2 mb-2">
                <span
                  className={`text-6xl font-bold tabular-nums ${scoreColor(result.ai_visibility_score)}`}
                >
                  {result.ai_visibility_score}
                </span>
                <span className="text-2xl text-zinc-500 font-normal">
                  /100
                </span>
              </div>
              <p
                className={`text-sm font-medium ${scoreColor(result.ai_visibility_score)}`}
              >
                {scoreLabel(result.ai_visibility_score)}
              </p>
              <p className="text-sm text-zinc-400 mt-3">
                {businessConsequence(result)}
              </p>
            </CardContent>
          </Card>

          {/* Engine breakdown */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {Object.entries(result.engine_breakdown).map(([engine, data]) => (
              <Card key={engine} className="border-white/10 bg-white/[0.02]">
                <CardContent className="p-4">
                  <div className="flex items-center justify-between mb-2">
                    <span
                      className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-[11px] font-medium ${ENGINE_COLORS[engine] || "text-zinc-300 bg-zinc-800 border-zinc-700"}`}
                    >
                      {ENGINE_LABELS[engine] || engine}
                    </span>
                    <span
                      className={`text-2xl font-bold tabular-nums ${scoreColor(data.rate)}`}
                    >
                      {data.rate}%
                    </span>
                  </div>
                  <div className="w-full bg-zinc-800 rounded-full h-1.5">
                    <div
                      className="bg-emerald-500 h-1.5 rounded-full transition-all duration-500"
                      style={{ width: `${Math.min(100, data.rate)}%` }}
                    />
                  </div>
                  <p className="text-xs text-zinc-500 mt-1">
                    Mentionne dans {data.mentioned}/{data.total} requetes
                  </p>
                </CardContent>
              </Card>
            ))}
          </div>

          {/* Competitors */}
          {result.top_competitors.length > 0 && (
            <Card className="border-white/10 bg-white/[0.02]">
              <CardContent className="p-5">
                <div className="flex items-center gap-2 mb-3 text-zinc-200">
                  <Users className="h-4 w-4 text-emerald-400" />
                  <h3 className="text-sm font-semibold uppercase tracking-wide">
                    Concurrents detectes
                  </h3>
                </div>
                <div className="space-y-2">
                  {result.top_competitors.map((comp, i) => (
                    <div
                      key={i}
                      className="flex items-center justify-between rounded-md border border-white/5 bg-white/[0.02] p-3"
                    >
                      <span className="text-sm text-zinc-200 font-mono">
                        {comp.domain}
                      </span>
                      <span className="text-xs text-zinc-500">
                        {comp.mentions} mention{comp.mentions > 1 ? "s" : ""}
                      </span>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Sample queries */}
          <Card className="border-white/10 bg-white/[0.02]">
            <CardContent className="p-5">
              <div className="flex items-center gap-2 mb-3 text-zinc-200">
                <Sparkles className="h-4 w-4 text-emerald-400" />
                <h3 className="text-sm font-semibold uppercase tracking-wide">
                  Requetes testees (apercu)
                </h3>
              </div>
              <div className="space-y-2">
                {result.sample_queries.map((sq, i) => (
                  <div
                    key={i}
                    className="flex items-center justify-between rounded-md border border-white/5 bg-white/[0.02] p-3"
                  >
                    <span className="text-sm text-zinc-300">" {sq.query} "</span>
                    {sq.mentioned ? (
                      <CheckCircle2 className="h-4 w-4 text-emerald-400 shrink-0" />
                    ) : (
                      <XCircle className="h-4 w-4 text-zinc-600 shrink-0" />
                    )}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Email gate */}
          <EmailGate
            headline="Recois le rapport complet de visibilite IA"
            bulletPoints={[
              "La liste complete des requetes testees",
              "Tous les concurrents mentionnes par les IA",
              "Les requetes ou tes concurrents apparaissent et pas toi",
              "Les pages a creer pour ameliorer ta visibilite",
              "Les actions recommandees par priorite",
            ]}
            domain={result.domain}
            tool="ai_visibility"
            hiddenCount={result.gated.competitor_only_count}
            hiddenLabel="requetes ou tes concurrents apparaissent et pas toi"
          />

          {/* CTA Gridar */}
          <Card className="border-emerald-500/20 bg-emerald-500/[0.03]">
            <CardContent className="p-6 text-center space-y-3">
              <div className="flex items-center justify-center gap-2">
                <GridarMark className="h-5 w-5 text-emerald-400" />
                <h3 className="text-lg font-semibold text-zinc-100">
                  Surveille ta visibilite IA en continu
                </h3>
              </div>
              <p className="text-sm text-zinc-400 max-w-lg mx-auto">
                Gridar peut surveiller automatiquement ces requetes et te montrer
                comment gagner en visibilite. Suivi quotidien, alertes et
                recommandations.
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
