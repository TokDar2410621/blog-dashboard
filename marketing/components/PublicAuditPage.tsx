"use client";

import { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Gauge,
  Activity,
  TrendingUp,
  Lock,
  CheckCircle2,
  AlertTriangle,
  Sparkles,
  Loader2,
  ArrowRight,
  ShieldCheck,
  Users,
  Zap,
  Download,
} from "lucide-react";
import { GridarMark } from "@/components/GridarMark";
import { toast } from "sonner";
import {
  FullReportSections,
  type FullReport,
} from "@/components/audit/FullReportSections";

// Empty base = same-origin via Next.js rewrites (see next.config.ts).
// Keeps auth cookies on gridar.app so logged-in visitors hit /api/public/* without a cross-origin hop.
const API_BASE = "";

type AuditResult = {
  domain: string;
  audited_at: string | null;
  composite_score: number | null;
  pagespeed: {
    performance?: number;
    seo?: number;
    accessibility?: number;
    avg?: number;
    error?: string;
  };
  crawl: {
    title?: string;
    h1?: string;
    meta_description?: string;
    error?: string;
  };
  top_keywords_estimated: { keyword: string; position: number | null }[];
  recos_partial: { severity: "high" | "medium" | "low"; message: string }[];
  full_report_gated: boolean;
  report_token?: string;
  full_report?: FullReport;
};

function scoreColor(s: number | null | undefined) {
  if (s == null) return "text-muted-foreground";
  if (s >= 80) return "text-emerald-500";
  if (s >= 60) return "text-amber-500";
  return "text-destructive";
}

function scoreLabel(s: number | null | undefined) {
  if (s == null) return "-";
  if (s >= 90) return "Excellent";
  if (s >= 80) return "Très bon";
  if (s >= 60) return "Correct";
  if (s >= 40) return "À améliorer";
  return "Critique";
}

export function PublicAuditPage() {
  const searchParams = useSearchParams();
  const [domain, setDomain] = useState("");
  const [auditing, setAuditing] = useState(false);
  const [result, setResult] = useState<AuditResult | null>(null);
  const [email, setEmail] = useState("");
  const [consented, setConsented] = useState(false);
  const [submittingLead, setSubmittingLead] = useState(false);
  const [leadCaptured, setLeadCaptured] = useState(false);
  const autorunFired = useRef(false);

  type Stats = {
    audits_this_month: number;
    leads_this_month: number;
    leads_this_week: number;
    total_leads: number;
  };
  const [stats, setStats] = useState<Stats | null>(null);
  useEffect(() => {
    fetch(`${API_BASE}/api/public/audit-stats/`)
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => d && setStats(d))
      .catch(() => {});
  }, []);

  const runAuditFor = async (target: string) => {
    const clean = target.trim();
    if (!clean) return;
    setAuditing(true);
    setResult(null);
    setLeadCaptured(false);
    try {
      const res = await fetch(`${API_BASE}/api/public/audit/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ domain: clean }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error || "Erreur audit");
      }
      const data = (await res.json()) as AuditResult;
      setResult(data);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Erreur");
    } finally {
      setAuditing(false);
    }
  };

  const runAudit = async (e: React.FormEvent) => {
    e.preventDefault();
    await runAuditFor(domain);
  };

  // Hero landing -> /audit?domain=...&autorun=1 : prefill + auto-launch.
  useEffect(() => {
    if (autorunFired.current) return;
    const prefill = searchParams?.get("domain") || "";
    if (!prefill) return;
    setDomain(prefill);
    if (searchParams?.get("autorun") === "1") {
      autorunFired.current = true;
      runAuditFor(prefill);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  const submitEmail = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim()) return;
    setSubmittingLead(true);
    try {
      const res = await fetch(`${API_BASE}/api/public/leads/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: email.trim(),
          domain: result?.domain || domain.trim(),
          consented_marketing: consented,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error || "Erreur");
      }
      const body = (await res.json().catch(() => ({}))) as {
        payload?: AuditResult;
        report_token?: string;
      };
      // Server enriches the payload synchronously and returns it; fall back
      // to GET /api/public/report/<token>/ if the response shape changes or
      // the enrichment ran async.
      if (body.payload) {
        setResult(body.payload);
      } else if (body.report_token || result?.report_token) {
        const token = body.report_token || result?.report_token;
        try {
          const r = await fetch(`${API_BASE}/api/public/report/${token}/`);
          if (r.ok) {
            const data = (await r.json()) as AuditResult;
            setResult(data);
          }
        } catch {
          // non-fatal: lead is captured, fallback teasers stay hidden.
        }
      }
      setLeadCaptured(true);
      toast.success("Rapport complet débloqué.");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Erreur");
    } finally {
      setSubmittingLead(false);
    }
  };

  return (
    <div className="dark min-h-screen bg-background text-foreground">
      <header className="border-b border-border/40 sticky top-0 bg-background/95 backdrop-blur z-20">
        <div className="max-w-5xl mx-auto px-4 py-3 flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2">
            <GridarMark className="h-5 w-5 text-primary" />
            <span className="font-bold">Gridar</span>
          </Link>
          <Link href="/login">
            <Button size="sm" variant="outline">
              Connexion
            </Button>
          </Link>
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-8 md:py-12">
        <div className="text-center max-w-2xl mx-auto mb-8">
          <h1 className="text-3xl md:text-4xl font-bold mb-3">
            Audit SEO gratuit de ton site en 30 secondes
          </h1>
          <p className="text-muted-foreground text-base md:text-lg mb-4">
            Entre ton domaine, découvre ton score SEO, tes positions sur Google et
            les principaux points à fixer. Sans inscription.
          </p>
          <div className="flex flex-wrap items-center justify-center gap-4 text-xs text-muted-foreground">
            {stats && (
              <span className="flex items-center gap-1.5">
                <Users className="h-3.5 w-3.5 text-primary" />
                <strong className="text-foreground">{stats.audits_this_month}</strong>
                {" "}audits ce mois-ci
              </span>
            )}
            <span className="flex items-center gap-1.5">
              <Zap className="h-3.5 w-3.5 text-primary" />
              Résultat en {"<"} 30s
            </span>
            <span className="flex items-center gap-1.5">
              <ShieldCheck className="h-3.5 w-3.5 text-primary" />
              Conforme Loi 25 (QC) + RGPD
            </span>
          </div>
        </div>

        <Card className="max-w-2xl mx-auto mb-8 print:hidden">
          <CardContent className="p-4">
            <form onSubmit={runAudit} className="flex flex-col sm:flex-row gap-2">
              <Input
                type="text"
                placeholder="tondomaine.com"
                value={domain}
                onChange={(e) => setDomain(e.target.value)}
                disabled={auditing}
                required
                className="flex-1"
              />
              <Button type="submit" disabled={auditing || !domain.trim()}>
                {auditing ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Audit en cours...
                  </>
                ) : (
                  <>
                    <Sparkles className="h-4 w-4 mr-2" />
                    Lancer l&apos;audit
                  </>
                )}
              </Button>
            </form>
            {auditing && (
              <p className="text-xs text-muted-foreground mt-3 text-center">
                On crawle ton site, on check ta vitesse mobile, on regarde où tu ranques. ~20s.
              </p>
            )}
          </CardContent>
        </Card>

        {result && (
          <div className="space-y-6 max-w-4xl mx-auto">
            <Card>
              <CardContent className="p-6">
                <div className="flex flex-col md:flex-row md:items-center gap-6">
                  <div className="flex flex-col items-center md:items-start">
                    <div className="text-xs uppercase tracking-wide text-muted-foreground flex items-center gap-1.5 mb-1">
                      <Gauge className="h-3.5 w-3.5" />
                      Score SEO global
                    </div>
                    <div className={`text-6xl font-bold tabular-nums ${scoreColor(result.composite_score)}`}>
                      {result.composite_score ?? "-"}
                      <span className="text-2xl text-muted-foreground font-normal">/100</span>
                    </div>
                    <div className={`text-sm font-medium ${scoreColor(result.composite_score)}`}>
                      {scoreLabel(result.composite_score)}
                    </div>
                  </div>
                  <div className="flex-1 text-sm text-muted-foreground">
                    <p className="mb-2">
                      Audit de <span className="font-mono text-foreground">{result.domain}</span>
                    </p>
                    {result.crawl.title && (
                      <p className="mb-1">
                        <span className="text-muted-foreground">Titre :</span>{" "}
                        <span className="text-foreground">{result.crawl.title}</span>
                      </p>
                    )}
                    {result.crawl.meta_description && (
                      <p className="line-clamp-2">
                        <span className="text-muted-foreground">Description :</span>{" "}
                        {result.crawl.meta_description}
                      </p>
                    )}
                    <button
                      type="button"
                      onClick={() => window.print()}
                      className="inline-flex items-center gap-1.5 text-xs text-primary hover:underline mt-2 bg-transparent border-0 p-0 cursor-pointer print:hidden"
                    >
                      <Download className="h-3 w-3" />
                      Sauvegarder en PDF (Ctrl+P)
                    </button>
                    {result.crawl.error && (
                      <p className="text-destructive">{result.crawl.error}</p>
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <Card>
                <CardHeader>
                  <CardTitle className="text-base flex items-center gap-2">
                    <Activity className="h-4 w-4" />
                    Performance mobile
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {result.pagespeed.error ? (
                    <p className="text-sm text-muted-foreground">{result.pagespeed.error}</p>
                  ) : "avg" in result.pagespeed ? (
                    <>
                      <div className={`text-3xl font-bold mb-3 ${scoreColor(result.pagespeed.avg)}`}>
                        {result.pagespeed.avg}/100
                      </div>
                      <div className="grid grid-cols-3 gap-2 text-center">
                        <div className="border rounded p-2">
                          <div className="text-[10px] uppercase text-muted-foreground">Perf</div>
                          <div className={`font-semibold ${scoreColor(result.pagespeed.performance)}`}>
                            {result.pagespeed.performance}
                          </div>
                        </div>
                        <div className="border rounded p-2">
                          <div className="text-[10px] uppercase text-muted-foreground">SEO</div>
                          <div className={`font-semibold ${scoreColor(result.pagespeed.seo)}`}>
                            {result.pagespeed.seo}
                          </div>
                        </div>
                        <div className="border rounded p-2">
                          <div className="text-[10px] uppercase text-muted-foreground">A11y</div>
                          <div className={`font-semibold ${scoreColor(result.pagespeed.accessibility)}`}>
                            {result.pagespeed.accessibility}
                          </div>
                        </div>
                      </div>
                    </>
                  ) : (
                    <p className="text-sm text-muted-foreground">Pas de données</p>
                  )}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-base flex items-center gap-2">
                    <TrendingUp className="h-4 w-4" />
                    Mots-clés principaux (estimés)
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  {result.top_keywords_estimated.length === 0 ? (
                    <p className="text-sm text-muted-foreground">
                      Pas réussi à extraire des mots-clés du site.
                    </p>
                  ) : (
                    <div className="space-y-1">
                      {result.top_keywords_estimated.map((kw, i) => (
                        <div
                          key={i}
                          className="flex items-center justify-between text-sm border-b border-border/30 py-1.5"
                        >
                          <span className="truncate">{kw.keyword}</span>
                          <span
                            className={`font-mono text-xs ${
                              kw.position == null
                                ? "text-muted-foreground"
                                : kw.position <= 10
                                ? "text-emerald-500"
                                : kw.position <= 30
                                ? "text-amber-500"
                                : "text-muted-foreground"
                            }`}
                          >
                            {kw.position == null
                              ? "hors top 50"
                              : `#${kw.position}`}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>

            <Card>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <AlertTriangle className="h-4 w-4 text-amber-500" />
                  Recommandations
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                {result.recos_partial.map((reco, i) => (
                  <div
                    key={i}
                    className={`border rounded p-2 flex items-center gap-2 text-sm ${
                      reco.severity === "high"
                        ? "border-destructive/40 bg-destructive/5"
                        : reco.severity === "medium"
                        ? "border-amber-500/40 bg-amber-500/5"
                        : "border-muted bg-muted/20"
                    }`}
                  >
                    <AlertTriangle
                      className={`h-4 w-4 shrink-0 ${
                        reco.severity === "high"
                          ? "text-destructive"
                          : "text-amber-500"
                      }`}
                    />
                    <span>{reco.message}</span>
                  </div>
                ))}

                <div className="relative pt-2">
                  {!leadCaptured && (
                    <>
                      {/* Screen: blurred teaser + lock overlay. The teasers are
                          rendered but visually gated. */}
                      <div className="print:hidden">
                        <div className="absolute inset-0 z-10 flex flex-col items-center justify-center gap-2 backdrop-blur-sm bg-background/40 rounded">
                          <Lock className="h-6 w-6 text-primary" />
                          <p className="text-sm font-medium">
                            7 autres recos à débloquer
                          </p>
                          <p className="text-xs text-muted-foreground">
                            Entre ton email plus bas pour les voir
                          </p>
                        </div>
                        <div className="opacity-30 select-none">
                          {[
                            { label: "Analyse de tes 3 principaux concurrents sur Google", sev: "medium" as const },
                            { label: "Liste des articles obsolètes à refresh en priorité", sev: "high" as const },
                            { label: "10 mots-clés ciblés que tu ne touches pas encore", sev: "medium" as const },
                            { label: "Backlinks: domaines référents + opportunités", sev: "low" as const },
                            { label: "Plan de génération d'articles pour les 30 prochains jours", sev: "medium" as const },
                            { label: "Schema.org + JSON-LD manquants sur tes pages clés", sev: "low" as const },
                            { label: "Comparatif Core Web Vitals desktop vs mobile", sev: "low" as const },
                          ].map((teaser, i) => (
                            <div
                              key={i}
                              className={`border rounded p-2 flex items-center gap-2 text-sm mb-2 ${
                                teaser.sev === "high"
                                  ? "border-destructive/40 bg-destructive/5"
                                  : teaser.sev === "medium"
                                  ? "border-amber-500/40 bg-amber-500/5"
                                  : "border-muted bg-muted/20"
                              }`}
                            >
                              <AlertTriangle
                                className={`h-4 w-4 shrink-0 ${
                                  teaser.sev === "high"
                                    ? "text-destructive"
                                    : teaser.sev === "medium"
                                    ? "text-amber-500"
                                    : "text-muted-foreground"
                                }`}
                              />
                              <span>{teaser.label}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                      {/* Print: a single honest locked block. Browsers drop
                          backdrop-filter and opacity inconsistently when
                          rendering to PDF, which leaks the teasers in clear. */}
                      <div className="hidden print:flex flex-col items-center justify-center gap-2 border border-dashed rounded p-6 text-center">
                        <Lock className="h-6 w-6" />
                        <p className="text-sm font-medium">
                          7 autres recommandations sont verrouillées
                        </p>
                        <p className="text-xs text-muted-foreground">
                          Débloque-les gratuitement en laissant ton email sur
                          gridar.app/audit
                        </p>
                      </div>
                    </>
                  )}
                  {leadCaptured && (
                    <div className="text-sm text-muted-foreground">
                      Rapport complet déverrouillé. Détails ci-dessous.
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>

            {leadCaptured && result.full_report && (
              <FullReportSections report={result.full_report} domain={result.domain} />
            )}

            {!leadCaptured && (
              <Card className="border-primary/40 bg-primary/5 print:hidden">
                <CardHeader>
                  <CardTitle className="text-lg flex items-center gap-2">
                    <Lock className="h-5 w-5 text-primary" />
                    Débloque le rapport complet
                  </CardTitle>
                  <CardDescription>
                    Concurrents, articles obsolètes, top mots-clés à viser,
                    rapport détaillé avec 15+ actions concrètes. Laisse ton
                    email pour accéder à tout.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <form onSubmit={submitEmail} className="space-y-3">
                    <div className="space-y-1">
                      <Label className="text-sm">Email professionnel</Label>
                      <Input
                        type="email"
                        placeholder="toi@tonentreprise.com"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        required
                        disabled={submittingLead}
                      />
                    </div>
                    <label className="flex items-start gap-2 text-xs text-muted-foreground cursor-pointer">
                      <input
                        type="checkbox"
                        checked={consented}
                        onChange={(e) => setConsented(e.target.checked)}
                        className="mt-0.5 h-4 w-4 rounded border-border"
                      />
                      <span>
                        J&apos;accepte de recevoir des conseils SEO gratuits par
                        email. Tu peux te désinscrire en 1 clic. Conforme Loi 25
                        (Québec) et RGPD.
                      </span>
                    </label>
                    <Button
                      type="submit"
                      disabled={submittingLead || !email.trim()}
                      className="w-full"
                    >
                      {submittingLead ? (
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      ) : (
                        <CheckCircle2 className="h-4 w-4 mr-2" />
                      )}
                      Accéder au rapport complet
                    </Button>
                  </form>
                </CardContent>
              </Card>
            )}

            {leadCaptured && (
              <Card className="border-emerald-500/40 bg-emerald-500/10">
                <CardContent className="p-6 text-center space-y-3">
                  <CheckCircle2 className="h-10 w-10 mx-auto text-emerald-500" />
                  <h3 className="font-semibold">Rapport débloqué</h3>
                  <p className="text-sm text-muted-foreground">
                    Pour aller plus loin, crée un compte Gridar et connecte ton
                    Google Search Console. On saura mesurer tes vraies
                    positions et générer les articles qui manquent.
                  </p>
                  <Link href="/login">
                    <Button>
                      Créer mon compte
                      <ArrowRight className="h-4 w-4 ml-2" />
                    </Button>
                  </Link>
                </CardContent>
              </Card>
            )}
          </div>
        )}
      </main>

      <footer className="mt-16 border-t border-border/40 py-6">
        <div className="max-w-5xl mx-auto px-4 text-center text-xs text-muted-foreground">
          Gridar, audit SEO + génération d&apos;articles FR-CA pour PME québécoises
        </div>
      </footer>
    </div>
  );
}
