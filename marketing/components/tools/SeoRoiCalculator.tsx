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
import { ToolImageHero } from "@/components/tools/ToolImageHero";

const API_BASE = "";

type Scenario = {
  name: string;
  assumed_growth_percent: number;
  year_one_revenue: number;
  // null quand le budget est a zero : un ratio sans denominateur n'existe pas.
  roi_percent: number | null;
  // null = jamais rentable sur douze mois. Different de "rentable au mois 12".
  break_even_month: number | null;
  monthly_revenue: number[];
  totals: { net: number; total_cost: number; traffic_added: number };
};

type SeoRoiResult = {
  domain: string;
  // Ce que le site rapporte deja, EXCLU des projections. L'ancienne version
  // le comptait comme un gain du SEO, d'ou des ROI a six chiffres.
  baseline_monthly_revenue: number;
  revenue_per_visitor: number;
  conversion_source: "derive_des_demandes" | "taux_saisi";
  inputs: { avg_conversion_rate: number; monthly_leads: number | null };
  sensitivity: {
    note: string;
    points: { conversion_percent: number; year_one_revenue: number; label: string }[];
  };
  scenarios: {
    conservative: Scenario;
    moderate?: Scenario;
    aggressive?: Scenario;
  };
  insight: string;
  methodologie: string;
};

export function SeoRoiCalculator() {
  const [domain, setDomain] = useState("");
  const [monthlyTraffic, setMonthlyTraffic] = useState("1000");
  // Par defaut on demande le nombre de DEMANDES par mois, pas le taux de
  // conversion. Un commerce sait dire "j'ai eu 15 appels le mois passe" ; il
  // ne sait pas dire "je convertis a 2 %". Le taux se derive des deux.
  const [monthlyLeads, setMonthlyLeads] = useState("20");
  const [conversionRate, setConversionRate] = useState("2.5");
  const [saisirLeTaux, setSaisirLeTaux] = useState(false);
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
          ...(saisirLeTaux
            ? { avg_conversion_rate: Number(conversionRate) }
            : { monthly_leads: Number(monthlyLeads) }),
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
    <>
      <ToolImageHero imageSrc="/hero-roi.webp" title="Calcule ton retour sur investissement SEO" subtitle="Decouvre combien le SEO peut rapporter a ton entreprise.">

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
                {/* Le trafic est devinable, contrairement au taux de
                    conversion. Plutot que de laisser l'utilisateur inventer un
                    chiffre, on lui dit ou lire le vrai. */}
                <Link
                  href="/sites"
                  className="block text-[10px] text-zinc-500 underline underline-offset-2 hover:text-zinc-300"
                >
                  Tu ne connais pas ton trafic ?
                </Link>
              </div>
              <div className="space-y-1.5 lg:col-span-1">
                {saisirLeTaux ? (
                  <>
                    <Label htmlFor="conv" className="text-xs">Taux de conv. (%)</Label>
                    {/* Pas de plancher a 0,1 : un site a fort trafic peut
                        convertir a 0,05 %, et le formulaire refusait cette
                        valeur pourtant vraie. */}
                    <Input id="conv" type="number" step="0.01" value={conversionRate} onChange={(e) => setConversionRate(e.target.value)} disabled={loading} required min="0" />
                  </>
                ) : (
                  <>
                    <Label htmlFor="leads" className="text-xs">Demandes / mois</Label>
                    <Input id="leads" type="number" step="1" value={monthlyLeads} onChange={(e) => setMonthlyLeads(e.target.value)} disabled={loading} required min="0" placeholder="appels, formulaires" />
                  </>
                )}
                <button
                  type="button"
                  onClick={() => setSaisirLeTaux((v) => !v)}
                  className="text-[10px] text-zinc-500 underline underline-offset-2 hover:text-zinc-300"
                >
                  {saisirLeTaux ? "Je ne connais pas mon taux" : "Je connais mon taux de conversion"}
                </button>
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

      </ToolImageHero>

      <div className="max-w-4xl mx-auto px-4 pb-16 pt-8">
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
              { id: "moderate", data: result.scenarios.moderate, label: "Modere", color: "text-emerald-400", border: "border-emerald-500/50 ring-1 ring-emerald-500/20 bg-emerald-500/[0.02]" },
              { id: "aggressive", data: result.scenarios.aggressive, label: "Agressif", color: "text-amber-400", border: "border-white/10" },
            ]
              // Quand l'utilisateur impose sa propre hypothese de croissance,
              // le backend ne rend qu'un seul scenario : les autres sont
              // absents plutot que remplis avec des valeurs inventees.
              .filter((sc): sc is { id: string; data: Scenario; label: string; color: string; border: string } => Boolean(sc.data))
              .map((sc) => (
              <Card key={sc.id} className={`${sc.border} flex flex-col`}>
                <CardHeader className="pb-2">
                  <CardTitle className={`text-sm uppercase tracking-wide ${sc.color}`}>
                    {sc.label}
                  </CardTitle>
                </CardHeader>
                <CardContent className="flex-1 space-y-4">
                  <div>
                    {/* Le revenu SUPPLEMENTAIRE, pas le chiffre d'affaires
                        total. Ce que le site rapporte deja est exclu. */}
                    <div className="text-xs text-zinc-500 mb-1">
                      Revenu supplementaire (an 1)
                    </div>
                    <div className="text-2xl font-bold text-zinc-100">
                      {formatCurrency(sc.data.year_one_revenue)}
                    </div>
                    <div className="mt-1 text-[11px] text-zinc-500">
                      hypothese : +{sc.data.assumed_growth_percent} % de trafic sur 12 mois
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <div className="bg-white/[0.02] p-2 rounded border border-white/5">
                      <div className="text-[10px] text-zinc-500 uppercase">Net</div>
                      <div className="text-sm font-semibold text-zinc-300">
                        {formatCurrency(sc.data.totals?.net ?? 0)}
                      </div>
                    </div>
                    <div className="bg-white/[0.02] p-2 rounded border border-white/5">
                      <div className="text-[10px] text-zinc-500 uppercase">Rentabilite</div>
                      <div className="text-sm font-semibold text-zinc-300">
                        {sc.data.break_even_month
                          ? `Mois ${sc.data.break_even_month}`
                          : "Pas en 12 mois"}
                      </div>
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
              {/* La barre porte `height` en pourcentage : son parent doit donc
                  avoir une hauteur reelle. Sans le `h-full` sur la colonne et
                  le conteneur `flex-1` autour de la barre, le pourcentage se
                  resolvait contre une hauteur auto (donc zero) et les douze
                  barres retombaient toutes sur `minHeight: 4px`. Vu en prod le
                  2026-08-25 : douze traits plats identiques. */}
              <div className="h-48 w-full flex items-end gap-2 pt-4">
                {(() => {
                  const revenus = result.scenarios?.moderate?.monthly_revenue || [];
                  const maxRev = Math.max(0, ...revenus);
                  return revenus.map((rev, i) => {
                  const height = maxRev > 0 ? (rev / maxRev) * 100 : 0;
                  return (
                    <div key={i} className="h-full flex-1 flex flex-col items-center gap-2 group relative">
                      <div className="w-full flex-1 flex items-end">
                        <div
                          className="w-full bg-emerald-500/80 rounded-t-sm transition-all duration-500 group-hover:bg-emerald-400"
                          style={{ height: `${height}%`, minHeight: '2px' }}
                        />
                      </div>
                      <div className="text-[10px] text-zinc-500">M{i+1}</div>
                      
                      <div className="opacity-0 group-hover:opacity-100 absolute -top-8 bg-zinc-800 text-xs px-2 py-1 rounded text-zinc-200 whitespace-nowrap pointer-events-none transition-opacity">
                        {formatCurrency(rev)}
                      </div>
                    </div>
                  );
                  });
                })()}
              </div>
              <p className="mt-6 text-sm text-zinc-400 bg-white/[0.02] p-4 rounded-md border border-white/5">
                <Target className="h-4 w-4 inline mr-2 text-emerald-400" />
                {result.insight}
              </p>
              {result.baseline_monthly_revenue > 0 && (
                <p className="mt-3 text-xs text-zinc-500">
                  Ton site rapporte deja {formatCurrency(result.baseline_monthly_revenue)} par
                  mois selon tes chiffres. Ce montant est exclu des projections
                  ci-dessus : seul le revenu supplementaire y figure.
                </p>
              )}
              {result.sensitivity?.points?.length ? (
                <div className="mt-4 rounded-md border border-white/5 bg-white/[0.02] p-4">
                  <div className="mb-3 text-xs text-zinc-400">
                    {result.sensitivity.note}
                  </div>
                  <div className="grid grid-cols-3 gap-2">
                    {result.sensitivity.points.map((pt) => (
                      <div key={pt.label} className="text-center">
                        <div className="text-[10px] uppercase tracking-wide text-zinc-500">
                          {pt.label}
                        </div>
                        <div className="text-[11px] text-zinc-500">
                          {pt.conversion_percent} %
                        </div>
                        <div className="mt-1 text-sm font-semibold text-zinc-200">
                          {formatCurrency(pt.year_one_revenue)}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
              {result.methodologie && (
                <p className="mt-3 border-t border-white/5 pt-3 text-[11px] leading-relaxed text-zinc-500">
                  {result.methodologie}
                </p>
              )}
              {/* L'escalade honnete : on ne demande pas de creer un compte pour
                  retenir de l'information, mais parce que Search Console est la
                  seule facon d'arreter de deviner le trafic. */}
              <div className="mt-4 rounded-md border border-emerald-500/20 bg-emerald-500/[0.03] p-4">
                <p className="text-xs leading-relaxed text-zinc-300">
                  Ces projections partent des chiffres que tu as saisis. Connecte
                  Search Console a Gridar et le trafic reel de ton site remplace
                  ton estimation.
                </p>
                <Link
                  href="/sites"
                  className="mt-2 inline-flex items-center gap-1 text-xs font-semibold text-emerald-400 hover:text-emerald-300"
                >
                  Utiliser mes vraies donnees
                  <ArrowRight className="h-3 w-3" />
                </Link>
              </div>
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
                Ces projections reposent sur des hypotheses de croissance, pas sur une analyse de ton domaine. Gridar mesure ta position reelle et travaille a l'ameliorer.
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
    </>
  );
}
