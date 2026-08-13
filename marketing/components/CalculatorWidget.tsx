"use client";

/**
 * CalculatorWidget - "what you pay now vs Gridar" savings calculator.
 *
 * Embedded by LandingRenderer on price/calculator-intent landings so the page
 * actually DOES the calculation it promises. Every input is user-editable and
 * pre-filled with a typical estimate the visitor adjusts to their own reality,
 * so the page makes zero unverifiable claims about competitor prices. The Gridar
 * side uses the REAL published pricing (Solo 29.99 / Pro 89.99 / Agence 199.99,
 * see BillingPage). Pure client-side math, no backend.
 */
import { useState } from "react";
import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Calculator, ArrowRight, TrendingDown } from "lucide-react";

// Prix Gridar REELS (cf. marketing/components/BillingPage.tsx). Le plan Pro
// (89.99$) regroupe rédaction + 24 outils SEO = le remplacant direct d'un stack.
const GRIDAR_PRO = 89.99;
const GRIDAR_SOLO = 29.99;

type Line = { key: string; label: string; hint: string; default: number };

const LINES: Line[] = [
  { key: "content", label: "Rédaction de contenu", hint: "rédacteur ou agence, par mois", default: 400 },
  { key: "keywords", label: "Outil de mots-clés", hint: "ex : Ahrefs, Semrush", default: 130 },
  { key: "rank", label: "Suivi de positions", hint: "rank tracker", default: 30 },
  { key: "audit", label: "Audit technique / autres outils", hint: "par mois", default: 50 },
];

export function CalculatorWidget() {
  const [values, setValues] = useState<Record<string, string>>(
    Object.fromEntries(LINES.map((l) => [l.key, String(l.default)]))
  );

  const num = (k: string) => {
    const n = parseFloat(values[k]);
    return Number.isFinite(n) && n > 0 ? n : 0;
  };
  const total = LINES.reduce((sum, l) => sum + num(l.key), 0);
  const savings = Math.max(0, total - GRIDAR_PRO);
  const yearly = savings * 12;
  const fmt = (n: number) =>
    n.toLocaleString("fr-CA", { minimumFractionDigits: 0, maximumFractionDigits: 0 });

  return (
    <div className="w-full max-w-2xl mx-auto">
      <Card className="border-white/10 bg-white/[0.02]">
        <CardContent className="p-5 md:p-6">
          <div className="flex items-center gap-2 mb-4 text-zinc-200">
            <Calculator className="h-5 w-5 text-emerald-400" />
            <h3 className="font-semibold">Ce que tu paies en ce moment</h3>
          </div>
          <p className="text-xs text-zinc-500 mb-4">
            Ajuste chaque montant selon ce que tu paies vraiment (par mois, en $).
            Mets 0 si tu ne paies pas.
          </p>
          <div className="space-y-3">
            {LINES.map((l) => (
              <div
                key={l.key}
                className="flex items-center justify-between gap-4"
              >
                <div className="min-w-0">
                  <Label htmlFor={`calc-${l.key}`} className="text-zinc-200">
                    {l.label}
                  </Label>
                  <p className="text-xs text-zinc-500">{l.hint}</p>
                </div>
                <div className="flex items-center gap-1 shrink-0">
                  <Input
                    id={`calc-${l.key}`}
                    type="number"
                    inputMode="numeric"
                    min={0}
                    value={values[l.key]}
                    onChange={(e) =>
                      setValues((v) => ({ ...v, [l.key]: e.target.value }))
                    }
                    className="w-24 text-right"
                  />
                  <span className="text-zinc-500 text-sm">$</span>
                </div>
              </div>
            ))}
          </div>

          <div className="mt-5 flex items-baseline justify-between border-t border-white/10 pt-4">
            <span className="text-sm text-zinc-400">Ton coût actuel estimé</span>
            <span className="text-2xl font-bold text-zinc-100 tabular-nums">
              {fmt(total)}$<span className="text-sm text-zinc-500">/mois</span>
            </span>
          </div>
        </CardContent>
      </Card>

      {/* Verdict Gridar */}
      <Card className="mt-5 border-emerald-500/30 bg-emerald-500/[0.04]">
        <CardContent className="p-6 text-center space-y-3">
          <div className="flex items-center justify-center gap-2 text-zinc-100">
            <TrendingDown className="h-5 w-5 text-emerald-400" />
            <h3 className="text-lg font-semibold">
              Avec Gridar Pro à {GRIDAR_PRO}$/mois
            </h3>
          </div>
          {savings > 0 ? (
            <p className="text-zinc-300">
              Tu économises{" "}
              <span className="text-3xl font-bold text-emerald-400 tabular-nums align-middle">
                {fmt(savings)}$
              </span>{" "}
              par mois, soit{" "}
              <strong className="text-emerald-300">{fmt(yearly)}$ par an</strong>.
              Rédaction, 24 outils SEO, suivi et audits : tout dans un seul
              abonnement.
            </p>
          ) : (
            <p className="text-zinc-300">
              À ce niveau, le plan{" "}
              <strong className="text-emerald-300">Solo à {GRIDAR_SOLO}$/mois</strong>{" "}
              te suffit probablement, et tu gagnes l&apos;automatisation en prime.
            </p>
          )}
          <div className="pt-2">
            <Link href="/billing">
              <Button className="bg-white text-zinc-950 hover:bg-zinc-200 font-semibold">
                Voir les plans Gridar
                <ArrowRight className="h-4 w-4 ml-2" />
              </Button>
            </Link>
          </div>
          <p className="text-xs text-zinc-500">
            Prix Gridar réels et publics. Sans engagement.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
