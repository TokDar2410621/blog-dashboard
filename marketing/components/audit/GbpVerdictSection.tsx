"use client";

import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { MapPin, Star, Check, AlertTriangle, X } from "lucide-react";
import type { GbpVerdict, GbpSignal } from "@/lib/report-api";

function StatusIcon({ status }: { status: GbpSignal["status"] }) {
  if (status === "ok")
    return <Check className="h-3.5 w-3.5 text-emerald-500 shrink-0" />;
  if (status === "warn")
    return <AlertTriangle className="h-3.5 w-3.5 text-amber-500 shrink-0" />;
  return <X className="h-3.5 w-3.5 text-destructive shrink-0" />;
}

function verdictStyle(v: GbpVerdict["verdict"]) {
  if (v === "strong")
    return { border: "border-emerald-500/40", bg: "bg-emerald-500/5", pill: "bg-emerald-500/15 text-emerald-400", label: "Fiche solide" };
  if (v === "weak")
    return { border: "border-amber-500/40", bg: "bg-amber-500/5", pill: "bg-amber-500/15 text-amber-400", label: "Fiche sous le pack" };
  return { border: "border-destructive/40", bg: "bg-destructive/5", pill: "bg-destructive/15 text-destructive", label: "Fiche introuvable" };
}

export function GbpVerdictSection({
  gbp,
}: {
  gbp: GbpVerdict | null | undefined;
}) {
  if (!gbp || !gbp.available) return null;

  const style = verdictStyle(gbp.verdict);

  // Not found: a real signal in itself (no verified profile, or it doesn't
  // link the site). This is the strongest hook for a local trade.
  if (!gbp.found) {
    return (
      <Card className={`${style.border} ${style.bg}`}>
        <CardHeader className="pb-3">
          <CardTitle className="text-base flex items-center gap-2">
            <MapPin className="h-4 w-4" />
            Ta fiche Google Business
            <span className={`ml-auto text-[11px] font-medium px-2 py-0.5 rounded ${style.pill}`}>
              {style.label}
            </span>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">{gbp.verdict_text}</p>
        </CardContent>
      </Card>
    );
  }

  const biz = gbp.business;
  const pack = gbp.pack || [];
  const rows = [
    { name: biz?.name || "Ta fiche", rating: biz?.rating ?? null, reviews: biz?.reviews ?? 0, you: true },
    ...pack.map((p) => ({ name: p.name, rating: p.rating, reviews: p.reviews, you: false })),
  ];
  const maxReviews = Math.max(1, ...rows.map((r) => r.reviews));

  return (
    <Card className={`${style.border} ${style.bg}`}>
      <CardHeader className="pb-3">
        <CardTitle className="text-base flex items-center gap-2 flex-wrap">
          <MapPin className="h-4 w-4" />
          Ta fiche Google Business
          {biz?.category && biz?.city && (
            <span className="text-xs font-normal text-muted-foreground">
              {biz.category} &middot; {biz.city}
            </span>
          )}
          <span className={`ml-auto text-[11px] font-medium px-2 py-0.5 rounded ${style.pill}`}>
            {style.label}
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm text-muted-foreground">{gbp.verdict_text}</p>

        {pack.length > 0 && (
          <div>
            <div className="text-[11px] uppercase tracking-wide text-muted-foreground mb-2">
              Toi vs le pack local {biz?.city ? `(${biz.city})` : ""}
            </div>
            <div className="space-y-1.5">
              {rows.map((r, i) => (
                <div
                  key={i}
                  className={`flex items-center gap-3 rounded px-2.5 py-1.5 text-sm ${
                    r.you ? "bg-foreground/[0.06] border border-border" : ""
                  }`}
                >
                  <span className={`flex-1 truncate ${r.you ? "font-semibold" : "text-muted-foreground"}`}>
                    {r.you ? "Toi : " : ""}
                    {r.name}
                  </span>
                  {r.rating != null && (
                    <span className="flex items-center gap-0.5 text-xs tabular-nums shrink-0">
                      <Star className="h-3 w-3 fill-amber-400 text-amber-400" />
                      {r.rating}
                    </span>
                  )}
                  <span className="w-24 shrink-0 hidden sm:block">
                    <span className="block h-1.5 rounded-full bg-border overflow-hidden">
                      <span
                        className={`block h-full rounded-full ${r.you ? "bg-primary" : "bg-muted-foreground/50"}`}
                        style={{ width: `${(r.reviews / maxReviews) * 100}%` }}
                      />
                    </span>
                  </span>
                  <span className={`w-20 text-right text-xs tabular-nums shrink-0 ${r.you ? "text-foreground font-semibold" : "text-muted-foreground"}`}>
                    {r.reviews} avis
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {gbp.signals && gbp.signals.length > 0 && (
          <div className="flex flex-wrap gap-x-4 gap-y-1.5 pt-1">
            {gbp.signals.map((s) => (
              <span
                key={s.key}
                className="flex items-center gap-1.5 text-xs text-muted-foreground"
                title={s.detail}
              >
                <StatusIcon status={s.status} />
                {s.label}
              </span>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
