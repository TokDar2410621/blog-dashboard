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
  Trophy,
  Search,
  FileCode2,
  Monitor,
  CalendarClock,
  PenLine,
  Link2,
  Star,
} from "lucide-react";
import { GridarMark } from "@/components/GridarMark";
import { toast } from "sonner";

// Empty base = same-origin via Next.js rewrites (see next.config.ts).
// Keeps auth cookies on gridar.app so logged-in visitors hit /api/public/* without a cross-origin hop.
const API_BASE = "";

type Section<T> = T & { error?: string };

type Competitor = {
  domain: string;
  title?: string;
  sample_url?: string;
  pagespeed_score?: number | null;
  position_count?: number;
};

type UntappedKeyword = {
  keyword: string;
  volume_estimate: number;
  competitor_in_top10?: string | null;
};

type SchemaAudit = {
  present: string[];
  missing_recommended: string[];
  score: number;
};

type PageSpeedBlock = {
  performance?: number;
  seo?: number;
  accessibility?: number;
  avg?: number;
};

type CwvBreakdown = {
  mobile: PageSpeedBlock;
  desktop: PageSpeedBlock;
  gap_pp: number | null;
  advice: string;
};

type DecayCandidate = {
  keyword: string;
  year_detected: string;
  advice: string;
};

type ArticlePlanItem = {
  title: string;
  target_keyword: string;
  why: string;
  priority: "high" | "medium" | "low";
  estimated_words: number;
};

type BacklinksProxy = {
  estimated_mentions: number | null;
  top_referring_domains: { domain: string; mention_count: number }[];
  advice?: string;
};

type FullReport = {
  competitors?: Section<{ items: Competitor[] }>;
  untapped_keywords?: Section<{ items: UntappedKeyword[] }>;
  schema_audit?: Section<SchemaAudit>;
  cwv_breakdown?: Section<CwvBreakdown>;
  decay_candidates?: Section<{ items: DecayCandidate[] }>;
  article_plan?: Section<{ items: ArticlePlanItem[] }>;
  backlinks_proxy?: Section<BacklinksProxy>;
};

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

function VolumeStars({ count }: { count: number }) {
  return (
    <span className="inline-flex items-center gap-0.5">
      {[1, 2, 3].map((i) => (
        <Star
          key={i}
          className={`h-3 w-3 ${
            i <= count ? "fill-amber-400 text-amber-400" : "text-muted-foreground/30"
          }`}
        />
      ))}
    </span>
  );
}

function PriorityBadge({ priority }: { priority: "high" | "medium" | "low" }) {
  const styles = {
    high: "bg-destructive/15 text-destructive border-destructive/40",
    medium: "bg-amber-500/15 text-amber-600 border-amber-500/40",
    low: "bg-muted text-muted-foreground border-muted-foreground/30",
  };
  const label = { high: "Priorité haute", medium: "Priorité moyenne", low: "Priorité basse" };
  return (
    <span
      className={`inline-flex items-center gap-1 text-[10px] font-medium uppercase tracking-wide border rounded px-1.5 py-0.5 ${styles[priority]}`}
    >
      {label[priority]}
    </span>
  );
}

function FullReportSections({
  report,
  domain,
}: {
  report: FullReport;
  domain: string;
}) {
  const competitors = report.competitors?.items ?? [];
  const untapped = report.untapped_keywords?.items ?? [];
  const schema = report.schema_audit;
  const cwv = report.cwv_breakdown;
  const decay = report.decay_candidates?.items ?? [];
  const plan = report.article_plan?.items ?? [];
  const backlinks = report.backlinks_proxy;

  return (
    <div className="space-y-4">
      {/* Competitors */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Trophy className="h-4 w-4 text-amber-500" />
            Tes 3 principaux concurrents sur Google
          </CardTitle>
        </CardHeader>
        <CardContent>
          {report.competitors?.error && competitors.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              {report.competitors.error}
            </p>
          ) : competitors.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Pas réussi à identifier des concurrents distincts pour ce domaine.
            </p>
          ) : (
            <div className="space-y-2">
              {competitors.map((c, i) => (
                <div
                  key={i}
                  className="flex items-center justify-between border rounded p-2 gap-3"
                >
                  <div className="min-w-0">
                    <div className="font-mono text-sm truncate">{c.domain}</div>
                    {c.title && (
                      <div className="text-xs text-muted-foreground truncate">
                        {c.title}
                      </div>
                    )}
                  </div>
                  <div className="flex items-center gap-3 shrink-0">
                    {c.pagespeed_score != null && (
                      <div className="text-right">
                        <div className="text-[10px] uppercase text-muted-foreground">
                          PageSpeed
                        </div>
                        <div
                          className={`font-semibold ${scoreColor(c.pagespeed_score)}`}
                        >
                          {c.pagespeed_score}
                        </div>
                      </div>
                    )}
                    {c.sample_url && (
                      <a
                        href={c.sample_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-xs text-primary hover:underline print:hidden"
                      >
                        Voir
                      </a>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Untapped keywords */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Search className="h-4 w-4 text-primary" />
            10 mots-clés que tu ne touches pas encore
          </CardTitle>
        </CardHeader>
        <CardContent>
          {report.untapped_keywords?.error && untapped.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              {report.untapped_keywords.error}
            </p>
          ) : untapped.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Pas de mots-clés inexploités détectés sur cette base.
            </p>
          ) : (
            <div className="space-y-1">
              {untapped.map((u, i) => (
                <div
                  key={i}
                  className="flex items-center justify-between border-b border-border/30 py-1.5 text-sm gap-3"
                >
                  <span className="truncate flex-1">{u.keyword}</span>
                  <VolumeStars count={u.volume_estimate} />
                  {u.competitor_in_top10 && (
                    <span className="hidden sm:inline text-[10px] font-mono text-muted-foreground truncate max-w-[140px]">
                      {u.competitor_in_top10}
                    </span>
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Schema audit */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <FileCode2 className="h-4 w-4 text-primary" />
            Schema.org / JSON-LD
            {schema && (
              <span
                className={`ml-auto text-sm font-semibold ${scoreColor(schema.score)}`}
              >
                {schema.score}/100
              </span>
            )}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {report.schema_audit?.error && !schema?.present.length && !schema?.missing_recommended.length ? (
            <p className="text-sm text-muted-foreground">
              {report.schema_audit.error}
            </p>
          ) : !schema ? (
            <p className="text-sm text-muted-foreground">Pas de données.</p>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div>
                <div className="text-xs uppercase text-muted-foreground mb-1.5">
                  Présents
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {schema.present.length === 0 ? (
                    <span className="text-sm text-muted-foreground">Aucun</span>
                  ) : (
                    schema.present.map((s, i) => (
                      <span
                        key={i}
                        className="text-xs border border-emerald-500/40 bg-emerald-500/10 text-emerald-500 rounded px-2 py-0.5"
                      >
                        {s}
                      </span>
                    ))
                  )}
                </div>
              </div>
              <div>
                <div className="text-xs uppercase text-muted-foreground mb-1.5">
                  Manquants recommandés
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {schema.missing_recommended.length === 0 ? (
                    <span className="text-sm text-muted-foreground">
                      Tout est en place.
                    </span>
                  ) : (
                    schema.missing_recommended.map((s, i) => (
                      <span
                        key={i}
                        className="text-xs border border-destructive/40 bg-destructive/10 text-destructive rounded px-2 py-0.5"
                      >
                        {s}
                      </span>
                    ))
                  )}
                </div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* CWV desktop vs mobile */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Monitor className="h-4 w-4 text-primary" />
            Core Web Vitals : mobile vs desktop
          </CardTitle>
        </CardHeader>
        <CardContent>
          {report.cwv_breakdown?.error && !cwv?.desktop.avg ? (
            <p className="text-sm text-muted-foreground">
              {report.cwv_breakdown.error}
            </p>
          ) : !cwv ? (
            <p className="text-sm text-muted-foreground">Pas de données.</p>
          ) : (
            <>
              <div className="grid grid-cols-2 gap-3 mb-3">
                {(["mobile", "desktop"] as const).map((mode) => {
                  const block = cwv[mode];
                  return (
                    <div key={mode} className="border rounded p-3">
                      <div className="text-xs uppercase text-muted-foreground mb-1">
                        {mode === "mobile" ? "Mobile" : "Desktop"}
                      </div>
                      <div
                        className={`text-2xl font-bold tabular-nums ${scoreColor(block?.avg)}`}
                      >
                        {block?.avg ?? "-"}
                        <span className="text-sm text-muted-foreground font-normal">
                          /100
                        </span>
                      </div>
                      <div className="grid grid-cols-3 gap-1.5 text-center mt-2">
                        <div>
                          <div className="text-[9px] uppercase text-muted-foreground">
                            Perf
                          </div>
                          <div className={`text-sm font-semibold ${scoreColor(block?.performance)}`}>
                            {block?.performance ?? "-"}
                          </div>
                        </div>
                        <div>
                          <div className="text-[9px] uppercase text-muted-foreground">
                            SEO
                          </div>
                          <div className={`text-sm font-semibold ${scoreColor(block?.seo)}`}>
                            {block?.seo ?? "-"}
                          </div>
                        </div>
                        <div>
                          <div className="text-[9px] uppercase text-muted-foreground">
                            A11y
                          </div>
                          <div className={`text-sm font-semibold ${scoreColor(block?.accessibility)}`}>
                            {block?.accessibility ?? "-"}
                          </div>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
              {cwv.gap_pp != null && (
                <div className="text-xs text-muted-foreground">
                  Écart : <span className="font-semibold text-foreground">{cwv.gap_pp >= 0 ? `+${cwv.gap_pp}` : cwv.gap_pp} pts</span> en faveur du desktop.
                </div>
              )}
              {cwv.advice && (
                <p className="text-sm mt-2">{cwv.advice}</p>
              )}
            </>
          )}
        </CardContent>
      </Card>

      {/* Decay candidates */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <CalendarClock className="h-4 w-4 text-amber-500" />
            Articles probablement obsolètes
          </CardTitle>
        </CardHeader>
        <CardContent>
          {decay.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Aucun mot-clé avec une année dépassée détecté. Bon signe.
            </p>
          ) : (
            <div className="space-y-2">
              {decay.map((d, i) => (
                <div key={i} className="border border-amber-500/40 bg-amber-500/5 rounded p-2">
                  <div className="flex items-center gap-2 text-sm">
                    <span className="font-mono text-xs border border-amber-500/40 rounded px-1.5 py-0.5 text-amber-500">
                      {d.year_detected}
                    </span>
                    <span className="truncate">{d.keyword}</span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">{d.advice}</p>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Article plan */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <PenLine className="h-4 w-4 text-primary" />
            Plan d&apos;articles pour les 30 prochains jours
          </CardTitle>
        </CardHeader>
        <CardContent>
          {report.article_plan?.error && plan.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              {report.article_plan.error}
            </p>
          ) : plan.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              Pas assez de signal pour proposer un plan.
            </p>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              {plan.map((a, i) => (
                <div key={i} className="border rounded p-3 flex flex-col gap-1.5">
                  <div className="flex items-start justify-between gap-2">
                    <div className="font-semibold text-sm leading-tight">
                      {a.title}
                    </div>
                    <PriorityBadge priority={a.priority} />
                  </div>
                  <div className="text-xs text-muted-foreground">
                    Cible : <span className="font-mono text-foreground">{a.target_keyword}</span>
                  </div>
                  {a.why && (
                    <p className="text-xs text-muted-foreground">{a.why}</p>
                  )}
                  <div className="text-[10px] uppercase text-muted-foreground mt-1">
                    {a.estimated_words.toLocaleString("fr-CA")} mots estimés
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Backlinks proxy */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Link2 className="h-4 w-4 text-primary" />
            Backlinks : estimation
          </CardTitle>
        </CardHeader>
        <CardContent>
          {!backlinks ? (
            <p className="text-sm text-muted-foreground">Pas de données.</p>
          ) : backlinks.estimated_mentions == null ? (
            <p className="text-sm text-muted-foreground">
              {backlinks.advice ||
                `On a besoin de ton GSC pour analyser les vrais backlinks de ${domain}.`}
            </p>
          ) : (
            <>
              <div className="text-sm mb-3">
                Environ{" "}
                <span className="font-semibold text-foreground">
                  {backlinks.estimated_mentions.toLocaleString("fr-CA")}
                </span>{" "}
                mentions externes détectées sur Google.
              </div>
              {backlinks.top_referring_domains.length > 0 && (
                <div>
                  <div className="text-xs uppercase text-muted-foreground mb-1.5">
                    Top domaines référents
                  </div>
                  <div className="space-y-1">
                    {backlinks.top_referring_domains.map((d, i) => (
                      <div
                        key={i}
                        className="flex items-center justify-between text-sm border-b border-border/30 py-1"
                      >
                        <span className="font-mono truncate">{d.domain}</span>
                        <span className="text-xs text-muted-foreground">
                          {d.mention_count} mention{d.mention_count > 1 ? "s" : ""}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              {backlinks.advice && (
                <p className="text-xs text-muted-foreground mt-2">
                  {backlinks.advice}
                </p>
              )}
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
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
