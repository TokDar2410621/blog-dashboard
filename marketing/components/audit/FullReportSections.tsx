import {
  Trophy,
  Search,
  FileCode2,
  Monitor,
  CalendarClock,
  PenLine,
  Link2,
  Star,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

// Shared, presentational-only. Rendered by both the client /audit page
// (PublicAuditPage) and the server /rapport/<token> share page. No hooks, no
// state, so it works in a Server Component without a "use client" boundary.

type Section<T> = T & { error?: string };

export type Competitor = {
  domain: string;
  title?: string;
  sample_url?: string;
  pagespeed_score?: number | null;
  position_count?: number;
};

export type UntappedKeyword = {
  keyword: string;
  volume_estimate: number;
  competitor_in_top10?: string | null;
};

export type SchemaAudit = {
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

export type CwvBreakdown = {
  mobile: PageSpeedBlock;
  desktop: PageSpeedBlock;
  gap_pp: number | null;
  advice: string;
};

export type DecayCandidate = {
  keyword: string;
  year_detected: string;
  advice: string;
};

export type ArticlePlanItem = {
  title: string;
  target_keyword: string;
  why: string;
  priority: "high" | "medium" | "low";
  estimated_words: number;
};

export type BacklinksProxy = {
  estimated_mentions: number | null;
  top_referring_domains: { domain: string; mention_count: number }[];
  advice?: string;
};

export type FullReport = {
  competitors?: Section<{ items: Competitor[] }>;
  untapped_keywords?: Section<{ items: UntappedKeyword[] }>;
  schema_audit?: Section<SchemaAudit>;
  cwv_breakdown?: Section<CwvBreakdown>;
  decay_candidates?: Section<{ items: DecayCandidate[] }>;
  article_plan?: Section<{ items: ArticlePlanItem[] }>;
  backlinks_proxy?: Section<BacklinksProxy>;
};

function scoreColor(s: number | null | undefined) {
  if (s == null) return "text-muted-foreground";
  if (s >= 80) return "text-emerald-500";
  if (s >= 60) return "text-amber-500";
  return "text-destructive";
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

export function FullReportSections({
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
