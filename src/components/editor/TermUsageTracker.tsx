import { useMemo } from "react";
import { Badge } from "@/components/ui/badge";
import { CheckCircle2, AlertTriangle, AlertOctagon, Circle } from "lucide-react";

export interface TermUsage {
  /** Recommended term/keyword to track. */
  term: string;
  /** Current occurrences in the article. */
  current: number;
  /** [min, max] target range. */
  target: [number, number];
  /** Sort weight (typically volume * relevance from brief). */
  importance: number;
}

export type TermStatus = "optimal" | "under" | "over" | "absent";

export function statusForUsage(u: TermUsage): TermStatus {
  if (u.current <= 0) return "absent";
  if (u.current < u.target[0]) return "under";
  if (u.current > u.target[1]) return "over";
  return "optimal";
}

const STATUS_META: Record<
  TermStatus,
  {
    label: string;
    Icon: typeof CheckCircle2;
    iconClass: string;
    badgeVariant: "default" | "secondary" | "destructive" | "outline";
    badgeClass: string;
  }
> = {
  optimal: {
    label: "optimal",
    Icon: CheckCircle2,
    iconClass: "text-emerald-500",
    badgeVariant: "outline",
    badgeClass:
      "border-emerald-500/40 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
  },
  under: {
    label: "sous-utilise",
    Icon: AlertTriangle,
    iconClass: "text-amber-500",
    badgeVariant: "outline",
    badgeClass:
      "border-amber-500/40 bg-amber-500/10 text-amber-600 dark:text-amber-400",
  },
  over: {
    label: "sur-utilise",
    Icon: AlertOctagon,
    iconClass: "text-rose-500",
    badgeVariant: "outline",
    badgeClass:
      "border-rose-500/40 bg-rose-500/10 text-rose-600 dark:text-rose-400",
  },
  absent: {
    label: "absent",
    Icon: Circle,
    iconClass: "text-muted-foreground",
    badgeVariant: "outline",
    badgeClass:
      "border-border bg-muted/40 text-muted-foreground",
  },
};

export interface TermUsageTrackerProps {
  terms: TermUsage[];
  /** When set, the parent should scroll/highlight the term in the markdown editor. */
  onTermClick?: (term: string) => void;
  activeTerm?: string | null;
  title?: string;
}

/**
 * Surfer/Clearscope-style term tracker: shows recommended terms with current
 * vs target count, status badge, and a click handler that the parent can use
 * to highlight the matched term inline in the editor.
 */
export function TermUsageTracker({
  terms,
  onTermClick,
  activeTerm,
  title = "Termes recommandes",
}: TermUsageTrackerProps) {
  const sorted = useMemo(
    () => [...terms].sort((a, b) => b.importance - a.importance),
    [terms],
  );

  if (sorted.length === 0) {
    return (
      <div className="text-xs text-muted-foreground italic px-2 py-3">
        Aucun terme recommande pour cet article. Ajoute des mots-cles dans les
        tags ou genere un brief.
      </div>
    );
  }

  const optimalCount = sorted.filter((t) => statusForUsage(t) === "optimal")
    .length;

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between px-1">
        <h3 className="text-xs font-mono uppercase tracking-wider text-muted-foreground">
          {title}
        </h3>
        <span className="text-[10px] tabular-nums text-muted-foreground">
          {optimalCount}/{sorted.length} ok
        </span>
      </div>
      <ul className="space-y-1">
        {sorted.map((u) => {
          const status = statusForUsage(u);
          const meta = STATUS_META[status];
          const Icon = meta.Icon;
          const [minT, maxT] = u.target;
          const isActive = activeTerm === u.term;
          return (
            <li key={u.term}>
              <button
                type="button"
                onClick={() => onTermClick?.(u.term)}
                className={`w-full flex items-center gap-2 rounded-md px-2 py-1.5 text-left transition-colors hover:bg-accent ${
                  isActive ? "bg-accent ring-1 ring-primary/40" : ""
                }`}
              >
                <Icon className={`h-4 w-4 shrink-0 ${meta.iconClass}`} />
                <span className="flex-1 truncate text-sm font-medium">
                  {u.term}
                </span>
                <span className="text-xs tabular-nums text-muted-foreground shrink-0">
                  {u.current} / {minT}-{maxT}
                </span>
                <Badge
                  variant={meta.badgeVariant}
                  className={`text-[10px] ${meta.badgeClass}`}
                >
                  {meta.label}
                </Badge>
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
