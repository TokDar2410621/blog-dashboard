"use client";

/**
 * AuditWidget - lean, embeddable version of the public audit tool.
 *
 * Runs a real audit against /api/public/audit/ (same endpoint as the full
 * /audit page) and shows the composite score + top blocking recos, then sends
 * the visitor to /audit for the full gated report. Embedded by LandingRenderer
 * on audit-intent landing pages so those pages actually DO the audit they
 * promise instead of only describing it.
 */
import { useState } from "react";
import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Gauge,
  Loader2,
  Search,
  ArrowRight,
  AlertTriangle,
} from "lucide-react";
import { toast } from "sonner";

// Empty base = same-origin via Next.js rewrites (keeps /api/public/* on gridar.app).
const API_BASE = "";

type QuickAudit = {
  domain: string;
  composite_score: number | null;
  recos_partial?: { severity: "high" | "medium" | "low"; message: string }[];
};

export function AuditWidget() {
  const [domain, setDomain] = useState("");
  const [auditing, setAuditing] = useState(false);
  const [result, setResult] = useState<QuickAudit | null>(null);

  const run = async (e: React.FormEvent) => {
    e.preventDefault();
    const clean = domain.trim();
    if (!clean) return;
    setAuditing(true);
    setResult(null);
    try {
      const res = await fetch(`${API_BASE}/api/public/audit/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ domain: clean }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(
          err.error || "Audit impossible pour le moment, reessaie."
        );
      }
      const data = (await res.json()) as QuickAudit;
      setResult(data);
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : "Une erreur est survenue."
      );
    } finally {
      setAuditing(false);
    }
  };

  const score = result?.composite_score ?? null;
  const scoreColor =
    score == null
      ? "text-zinc-400"
      : score >= 80
      ? "text-emerald-400"
      : score >= 60
      ? "text-amber-400"
      : "text-red-400";

  return (
    <div className="w-full max-w-2xl mx-auto">
      <Card className="border-white/10 bg-white/[0.02]">
        <CardContent className="p-5 md:p-6">
          <form onSubmit={run} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="aw-domain" className="text-zinc-300">
                Ton domaine
              </Label>
              <Input
                id="aw-domain"
                type="text"
                inputMode="url"
                placeholder="tondomaine.com"
                value={domain}
                onChange={(e) => setDomain(e.target.value)}
                disabled={auditing}
                required
              />
            </div>
            <Button
              type="submit"
              disabled={auditing || !domain.trim()}
              className="w-full bg-emerald-500 text-zinc-950 hover:bg-emerald-400 font-semibold"
            >
              {auditing ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Analyse en cours...
                </>
              ) : (
                <>
                  <Search className="h-4 w-4 mr-2" />
                  Auditer mon site gratuitement
                </>
              )}
            </Button>
            <p className="text-center text-xs text-zinc-500">
              Aucune inscription. Score SEO + recommandations en 30 secondes.
            </p>
          </form>
        </CardContent>
      </Card>

      {result && (
        <div className="mt-6 space-y-5">
          <Card className="border-white/10 bg-white/[0.02]">
            <CardContent className="p-6 text-center">
              <div className="text-xs uppercase tracking-wide text-zinc-500 mb-1">
                Score SEO composite
              </div>
              <div
                className={`text-6xl font-bold tabular-nums leading-none ${scoreColor}`}
              >
                {score == null ? "-" : score}
              </div>
              <p className="mt-2 text-sm text-zinc-400">
                pour{" "}
                <span className="font-mono text-zinc-200">{result.domain}</span>
              </p>
            </CardContent>
          </Card>

          {(result.recos_partial?.length ?? 0) > 0 && (
            <Card className="border-white/10 bg-white/[0.02]">
              <CardContent className="p-5">
                <h3 className="text-sm font-semibold uppercase tracking-wide text-zinc-200 mb-3">
                  Ce qui te freine
                </h3>
                <ul className="space-y-2">
                  {(result.recos_partial || []).slice(0, 4).map((r, i) => (
                    <li
                      key={i}
                      className="flex items-start gap-2 text-sm text-zinc-300"
                    >
                      <AlertTriangle className="h-4 w-4 text-amber-400 shrink-0 mt-0.5" />
                      <span>{r.message}</span>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}

          <Card className="border-emerald-500/30 bg-emerald-500/[0.04]">
            <CardContent className="p-5 md:p-6 text-center space-y-4">
              <div className="flex items-center justify-center gap-2 text-zinc-100">
                <Gauge className="h-5 w-5 text-emerald-400" />
                <h3 className="text-lg font-semibold">
                  Le rapport complet t&apos;attend
                </h3>
              </div>
              <p className="text-sm text-zinc-400 max-w-xl mx-auto">
                Vitesse mobile detaillee, top mots-cles, donnees structurees et
                le plan pour corriger. Gratuit, sans carte.
              </p>
              <Link
                href={`/audit?domain=${encodeURIComponent(
                  result.domain
                )}&autorun=1`}
              >
                <Button className="bg-white text-zinc-950 hover:bg-zinc-200 font-semibold">
                  Voir le rapport complet
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
