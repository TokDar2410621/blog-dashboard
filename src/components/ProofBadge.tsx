import { TrendingUp, AlertCircle, Clock } from "lucide-react";
import type { ProofAttribution } from "@/lib/api-client";

type BadgeVariant = "won" | "unindexed" | "pending" | "empty";

function variant(attribution: ProofAttribution | null, publishedAt: string | null): BadgeVariant {
  if (attribution && attribution.indexed && attribution.delta_vs_baseline?.impressions > 0) {
    return "won";
  }
  if (attribution && !attribution.indexed) return "unindexed";
  if (publishedAt) {
    const ageDays = Math.floor((Date.now() - new Date(publishedAt).getTime()) / (1000 * 60 * 60 * 24));
    if (ageDays < 30) return "pending";
  }
  return "empty";
}

export function ProofBadge({
  attribution,
  publishedAt,
}: {
  attribution: ProofAttribution | null;
  publishedAt: string | null;
}) {
  const v = variant(attribution, publishedAt);

  if (v === "won" && attribution) {
    const delta = attribution.delta_vs_baseline.impressions;
    const formatted = Math.abs(delta) >= 1000 ? `${(delta / 1000).toFixed(1)}k` : String(delta);
    return (
      <span
        className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[11px] font-medium bg-primary/10 text-primary"
        title={`+${delta} impressions GSC vs baseline (mesure J+${attribution.days_since_publish})`}
      >
        <TrendingUp className="h-3 w-3" />
        +{formatted} J+{attribution.days_since_publish}
      </span>
    );
  }

  if (v === "unindexed") {
    return (
      <span
        className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[11px] font-medium bg-amber-500/10 text-amber-600 dark:text-amber-400"
        title="Pas encore indexe par Google"
      >
        <AlertCircle className="h-3 w-3" />
        Pas indexe
      </span>
    );
  }

  if (v === "pending") {
    return (
      <span
        className="inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[11px] font-medium bg-muted text-muted-foreground"
        title="Le premier check d'attribution arrive a J+30 apres publication"
      >
        <Clock className="h-3 w-3" />
        J+30
      </span>
    );
  }

  return (
    <span className="text-[11px] text-muted-foreground/60" title="Pas de baseline GSC pour cet article">
      -
    </span>
  );
}
