import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { TrendingUp, TrendingDown, Minus, type LucideIcon } from "lucide-react";
import { Area, AreaChart, ResponsiveContainer } from "recharts";
import { useId } from "react";

interface StatsCardProps {
  title: string;
  value: string | number;
  icon: LucideIcon;
  description?: string;
  /**
   * Sparkline series for the last N days. Each point is a numeric value.
   * If omitted, no sparkline is rendered.
   */
  sparkline?: number[];
  /**
   * Percentage delta vs the previous comparable window (e.g. 7d).
   * Positive => up, negative => down, 0/undefined => stable.
   */
  delta?: number;
  /**
   * Tooltip label explaining the delta window. Default "vs 7 derniers jours".
   */
  deltaLabel?: string;
}

function getDeltaVariant(delta: number): "default" | "secondary" | "destructive" {
  if (delta > 0) return "default";
  if (delta < 0) return "destructive";
  return "secondary";
}

function formatDelta(delta: number): string {
  const sign = delta > 0 ? "+" : "";
  return `${sign}${delta.toFixed(0)}%`;
}

export function StatsCard({
  title,
  value,
  icon: Icon,
  description,
  sparkline,
  delta,
  deltaLabel = "vs 7 derniers jours",
}: StatsCardProps) {
  const gradientId = useId().replace(/:/g, "");
  const hasSparkline = Array.isArray(sparkline) && sparkline.length > 1;
  const hasDelta = typeof delta === "number";

  const TrendIcon =
    hasDelta && delta! > 0
      ? TrendingUp
      : hasDelta && delta! < 0
      ? TrendingDown
      : Minus;

  // Recharts wants objects, not bare numbers.
  const chartData = hasSparkline
    ? sparkline!.map((v, i) => ({ i, v }))
    : [];

  // Emerald gradient for positive/stable, soft red for negative.
  const strokeColor =
    hasDelta && delta! < 0 ? "rgb(239 68 68)" : "rgb(16 185 129)";

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
        <Icon className="h-4 w-4 text-muted-foreground" />
      </CardHeader>
      <CardContent>
        <div className="flex items-center justify-between gap-2">
          <div className="text-2xl font-bold">{value}</div>
          {hasDelta && (
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <Badge
                    variant={getDeltaVariant(delta!)}
                    className={
                      delta! > 0
                        ? "bg-emerald-500 text-white hover:bg-emerald-500/90"
                        : undefined
                    }
                  >
                    <TrendIcon className="h-3 w-3" />
                    {formatDelta(delta!)}
                  </Badge>
                </TooltipTrigger>
                <TooltipContent side="top">{deltaLabel}</TooltipContent>
              </Tooltip>
            </TooltipProvider>
          )}
        </div>
        {hasSparkline && (
          <div className="mt-2 h-9 -mx-1">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData} margin={{ top: 2, right: 0, left: 0, bottom: 0 }}>
                <defs>
                  <linearGradient id={`spark-${gradientId}`} x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={strokeColor} stopOpacity={0.35} />
                    <stop offset="100%" stopColor={strokeColor} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <Area
                  type="monotone"
                  dataKey="v"
                  stroke={strokeColor}
                  strokeWidth={1.5}
                  fill={`url(#spark-${gradientId})`}
                  isAnimationActive={false}
                  dot={false}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}
        {description && (
          <p className="mt-1 text-xs text-muted-foreground">{description}</p>
        )}
      </CardContent>
    </Card>
  );
}
