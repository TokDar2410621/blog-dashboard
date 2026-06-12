"use client";

import Link from "next/link";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
  ArrowRight,
  Lightbulb,
  type LucideIcon,
} from "lucide-react";

export type RecommendationPriority = "high" | "medium" | "low";

export type Recommendation = {
  id: string;
  icon: LucideIcon;
  title: string;
  description: string;
  action_label: string;
  action_href: string;
  priority: RecommendationPriority;
};

type Props = {
  recommendations: Recommendation[];
  title?: string;
  subtitle?: string;
  emptyMessage?: string;
};

const PRIORITY_ORDER: Record<RecommendationPriority, number> = {
  high: 0,
  medium: 1,
  low: 2,
};

const PRIORITY_STYLE: Record<
  RecommendationPriority,
  { dot: string; label: string; iconBg: string; iconColor: string }
> = {
  high: {
    dot: "bg-red-500",
    label: "Prioritaire",
    iconBg: "bg-red-500/10",
    iconColor: "text-red-600 dark:text-red-400",
  },
  medium: {
    dot: "bg-amber-500",
    label: "Important",
    iconBg: "bg-amber-500/10",
    iconColor: "text-amber-600 dark:text-amber-400",
  },
  low: {
    dot: "bg-blue-500",
    label: "Optionnel",
    iconBg: "bg-blue-500/10",
    iconColor: "text-blue-600 dark:text-blue-400",
  },
};

export function RecommendationsPanel({
  recommendations,
  title = "Recommandations",
  subtitle = "Actions a fort impact, triees par priorite.",
  emptyMessage = "Aucune action recommandee. Tout est sain.",
}: Props) {
  const sorted = [...recommendations].sort(
    (a, b) => PRIORITY_ORDER[a.priority] - PRIORITY_ORDER[b.priority],
  );

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg flex items-center gap-2">
          <Lightbulb className="h-5 w-5 text-primary" />
          {title}
        </CardTitle>
        <p className="text-sm text-muted-foreground">{subtitle}</p>
      </CardHeader>
      <CardContent>
        {sorted.length === 0 ? (
          <p className="text-sm text-muted-foreground py-6 text-center">
            {emptyMessage}
          </p>
        ) : (
          <ul className="space-y-2">
            {sorted.map((reco) => {
              const Icon = reco.icon;
              const style = PRIORITY_STYLE[reco.priority];
              return (
                <li
                  key={reco.id}
                  className="flex items-start gap-3 rounded-lg border p-3 hover:bg-muted/40 transition-colors"
                >
                  <div
                    className={`shrink-0 h-9 w-9 rounded-md flex items-center justify-center ${style.iconBg}`}
                    aria-hidden
                  >
                    <Icon className={`h-4 w-4 ${style.iconColor}`} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span
                        className={`h-1.5 w-1.5 rounded-full ${style.dot}`}
                        aria-hidden
                      />
                      <span className="text-[10px] uppercase font-mono tracking-wide text-muted-foreground">
                        {style.label}
                      </span>
                    </div>
                    <p className="font-medium text-sm mt-0.5 truncate">
                      {reco.title}
                    </p>
                    <p className="text-xs text-muted-foreground mt-0.5 line-clamp-2">
                      {reco.description}
                    </p>
                  </div>
                  <div className="shrink-0 self-center">
                    <Link href={reco.action_href}>
                      <Button size="sm" variant="outline">
                        {reco.action_label}
                        <ArrowRight className="h-3 w-3 ml-1" />
                      </Button>
                    </Link>
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

export default RecommendationsPanel;
