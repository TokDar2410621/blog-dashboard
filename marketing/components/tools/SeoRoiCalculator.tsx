"use client";

import { useState } from "react";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  TrendingUp,
  Loader2,
  ArrowRight,
  DollarSign,
  PieChart,
  Target
} from "lucide-react";
import { GridarMark } from "@/components/GridarMark";
import { toast } from "sonner";
import { EmailGate } from "@/components/tools/EmailGate";

const API_BASE = "";

type Scenario = {
  name: string;
  year_one_revenue: number;
  roi_percent: number;
  break_even_month: number;
  monthly_revenue: number[];
};

type SeoRoiResult = {
  domain: string;
  scenarios: {
    conservative: Scenario;
    moderate: Scenario;
    aggressive: Scenario;
  };
  insight: string;
};

export function SeoRoiCalculator() {
  const [domain, setDomain] = useState("");
  const [monthlyTraffic, setMonthlyTraffic] = useState("1000");
  const [conversionRate, setConversionRate] = useState("2.5");
  const [dealValue, setDealValue] = useState("500");
  const [seoInvestment, setSeoInvestment] = useState("2000");

  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SeoRoiResult | null>(null);

  const runAnalysis = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!domain.trim()) return;
    setLoading(true);
    setResult(null);
    try {
      const res = await fetch(`${API_BASE}/api/public/seo-roi/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          domain: domain.trim(),
          monthly_traffic: Number(monthlyTraffic),
          avg_conversion_rate: Number(conversionRate),
          avg_deal_value: Number(dealValue),
          monthly_seo_investment: Number(seoInvestment),
        }),
      });
      if (!res.ok) {
        throw new Error("Erreur de calcul.");
      }
      const data = await res.json();
      setResult(data);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Erreur");
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (val: number) => {
    return new Intl.NumberFormat("fr-CA", {
      style: "currency",
      currency: "CAD",
      maximumFractionDigits: 0,
    }).format(val);
  };

  return (
    <div className="max-w-4xl mx-auto px-4 py-10 md:py-16">
      <div className="text-center mb-8">
        <div className="inline-flex items-center gap-2 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-xs font-medium text-emerald-300 mb-4">
          <TrendingUp className="h-3 w-3" />
          <span>Calculateur ROI SEO</span>
        </div>
        <h1 className="text-3xl md:text-4xl font-bold tracking-tight mb-3">
          Calcule ton retour sur investissement SEO
        </h1>
        <p className="text-base md:text-lg text-zinc-400 max-w-xl mx-auto">
          Decouvre combien le SEO peut rapporter a ton entreprise.
        </p>
      </div>

      <Card className="mb-8">
        <CardContent className="p-6">
          <form onSubmit={runAnalysis} className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
              <div className="space-y-1.5 lg:col-span-1">
                <Label htmlFor="domain" className="text-xs">Domaine</Label>
                <Input id="domain" placeholder="tondomaine.com" value={domain} onChange={(e) => setDomain(e.target.value)} disabled={loading} required />
              </div>
              <div className="space-y-1.5 lg:col-span-1">
                <Label htmlFor="traffic" className="text-xs">Trafic mensuel</Label>
                <Input id="traffic" type="number" value={monthlyTraffic} onChange={(e) => setMonthlyTraffic(e.target.value)} disabled={loading} required min="1" />
              </div>
              <div className="space-y-1.5 lg:col-span-1">
                <Label htmlFor="conv" className="text-xs">Taux de conv. (%)</Label>
                <Input id="conv" type="number" step="0.1" value={conversionRate} onChange={(e) => setConversionRate(e.target.value)} disabled={loading} required min="0.1" />
              </div>
              <div className="space-y-1.5 lg:col-span-1">
                <Label htmlFor="deal" className="text-xs">Valeur client ($)</Label>
                <Input id="deal" type="number" value={dealValue} onChange={(e) => setDealValue(e.target.value)} disabled={loading} required min="1" />
              </div>
              <div className="space-y-1.5 lg:col-span-1">
                <Label htmlFor="budget" className="text-xs">Budget SEO ($/m)</Label>
                <Input id="budget" type="number" value={seoInvestment} onChange={(e) => setSeoInvestment(e.target.value)} disabled={loading} required min="1" />
              </div>
            </div>
            <div className="flex justify-end">
              <Button type="submit" disabled={loading || !domain.trim()} className="bg-emerald-500 text-zinc-950 hover:bg-emerald-400 font-semibold">
                {loading ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Calcul en cours...
                  </>
                ) : (
                  <>
                    <TrendingUp className="h-4 w-4 mr-2" />
                    Calculer le ROI
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
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {[
              { id: "conservative", data: result.scenarios.conservative, label: "Conservateur", color: "text-zinc-300", border: "border-white/10" },
              { id: "moderate", data: result.scenarios.moderate, label: "Modere (Recommande)", color: "text-emerald-400", border: "border-emerald-500/50 ring-1 ring-emerald-500/20 bg-emerald-500/[0.02]" },
              { id: "aggressive", data: result.scenarios.aggressive, label: "Agressif", color: "text-amber-400", border: "border-white/10" },
            ].map((sc) => (
              <Card key={sc.id} className={`${sc.border} flex flex-col`}>
                <CardHeader className="pb-2">
                  <CardTitle className={`text-sm uppercase tracking-wide ${sc.color}`}>
                    {sc.label}
                  </CardTitle>
                </CardHeader>
                <CardContent className="flex-1 space-y-4">
                  <div>
                    <div className="text-xs text-zinc-500 mb-1">Revenus (Annee 1)</div>
                    <div className="text-2xl font-bold text-zinc-100">{formatCurrency(sc.data.year_one_revenue)}</div>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <div className="bg-white/[0.02] p-2 rounded border border-white/5">
                      <div className="text-[10px] text-zinc-500 uppercase">ROI</div>
                      <div className="text-sm font-semibold text-zinc-300">+{sc.data.roi_percent}%</div>
                    </div>
                    <div className="bg-white/[0.02] p-2 rounded border border-white/5">
                      <div className="text-[10px] text-zinc-500 uppercase">Rentabilite</div>
                      <div className="text-sm font-semibold text-zinc-300">Mois {sc.data.break_even_month}</div>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          <Card className="border-white/10 bg-white/[0.02]">
            <CardHeader>
              <CardTitle className="text-sm uppercase tracking-wide text-zinc-200">
                Projection des revenus sur 12 mois (Scenario Modere)
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="h-48 w-full flex items-end gap-2 pt-4">
                {result.scenarios.moderate.monthly_revenue.map((rev, i) => {
                  const maxRev = Math.max(...result.scenarios.moderate.monthly_revenue);
                  const height = maxRev > 0 ? (rev / maxRev) * 100 : 0;
                  return (
                    <div key={i} className="flex-1 flex flex-col items-center gap-2 group relative">
                      <div 
                        className="w-full bg-emerald-500/80 rounded-t-sm transition-all duration-500 group-hover:bg-emerald-400"
                        style={{ height: `${height}%`, minHeight: '4px' }}
                      />
                      <div className="text-[10px] text-zinc-500">M{i+1}</div>
                      
                      <div className="opacity-0 group-hover:opacity-100 absolute -top-8 bg-zinc-800 text-xs px-2 py-1 rounded text-zinc-200 whitespace-nowrap pointer-events-none transition-opacity">
                        {formatCurrency(rev)}
                      </div>
                    </div>
                  );
                })}
              </div>
              <p className="mt-6 text-sm text-zinc-400 bg-white/[0.02] p-4 rounded-md border border-white/5">
                <Target className="h-4 w-4 inline mr-2 text-emerald-400" />
                {result.insight}
              </p>
            </CardContent>
          </Card>

          <EmailGate
            headline="Recois les projections detaillees mois par mois"
            bulletPoints={[
              "Projections de trafic sur 12 mois",
              "Estimations de revenus par scenario",
              "Point de rentabilite precis",
              "Recommandations d'investissement"
            ]}
            domain={result.domain}
            tool="seo_roi"
          />

          <Card className="border-emerald-500/20 bg-emerald-500/[0.03]">
            <CardContent className="p-6 text-center space-y-3">
              <div className="flex items-center justify-center gap-2">
                <GridarMark className="h-5 w-5 text-emerald-400" />
                <h3 className="text-lg font-semibold text-zinc-100">
                  Pret a atteindre tes objectifs?
                </h3>
              </div>
              <p className="text-sm text-zinc-400 max-w-lg mx-auto">
                Gridar optimise ton SEO pour atteindre le scenario agressif. Laisse-nous gerer la technique et le contenu pendant que tu clos tes ventes.
              </p>
              <Link href="/login">
                <Button className="bg-white text-zinc-950 hover:bg-zinc-200 font-semibold">
                  Demarrer mon projet
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
