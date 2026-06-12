"use client";

import { useId } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  type TooltipContentProps,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { TrendingUp } from "lucide-react";

export type DistributionPoint = {
  date: string;
  top3: number;
  top4_10: number;
  top11_20: number;
  top21_50: number;
  top51plus: number;
};

interface PositionDistributionChartProps {
  data: DistributionPoint[];
  range: string;
  isLoading?: boolean;
}

const BUCKETS: Array<{
  key: keyof Omit<DistributionPoint, "date">;
  label: string;
  color: string;
}> = [
  { key: "top3", label: "Top 3", color: "rgb(16 185 129)" }, // emerald-500
  { key: "top4_10", label: "4 - 10", color: "rgb(52 211 153)" }, // emerald-400
  { key: "top11_20", label: "11 - 20", color: "rgb(6 182 212)" }, // cyan-500
  { key: "top21_50", label: "21 - 50", color: "rgb(113 113 122)" }, // zinc-500
  { key: "top51plus", label: "51+", color: "rgb(63 63 70)" }, // zinc-700
];

function CustomTooltip({ active, payload, label }: Partial<TooltipContentProps<number, string>>) {
  if (!active || !payload || !payload.length) return null;
  const total = payload.reduce(
    (acc, p) => acc + (typeof p.value === "number" ? p.value : 0),
    0
  );

  return (
    <div className="rounded-md border bg-card p-3 shadow-md text-xs">
      <div className="font-medium mb-2">
        {label ? new Date(label).toLocaleDateString("fr-CA", { year: "numeric", month: "short", day: "2-digit" }) : ""}
      </div>
      <div className="space-y-1">
        {[...payload].reverse().map((entry) => {
          const bucket = BUCKETS.find((b) => b.key === entry.dataKey);
          if (!bucket) return null;
          return (
            <div key={String(entry.dataKey)} className="flex items-center justify-between gap-4">
              <div className="flex items-center gap-2">
                <span
                  className="inline-block h-2 w-2 rounded-sm"
                  style={{ background: bucket.color }}
                />
                <span className="text-muted-foreground">{bucket.label}</span>
              </div>
              <span className="font-mono font-medium">{entry.value}</span>
            </div>
          );
        })}
        <div className="mt-1 pt-1 border-t flex items-center justify-between gap-4">
          <span className="text-muted-foreground">Total</span>
          <span className="font-mono font-semibold">{total}</span>
        </div>
      </div>
    </div>
  );
}

export function PositionDistributionChart({
  data,
  range,
  isLoading = false,
}: PositionDistributionChartProps) {
  const uid = useId().replace(/:/g, "");

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between gap-3">
          <CardTitle className="text-base flex items-center gap-2">
            <TrendingUp className="h-4 w-4 text-emerald-500" />
            Distribution des positions
          </CardTitle>
          <span className="text-[10px] uppercase font-mono text-muted-foreground tracking-wider">
            {range}
          </span>
        </div>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <Skeleton className="h-64 w-full" />
        ) : !data.length ? (
          <div className="h-64 flex flex-col items-center justify-center text-center text-muted-foreground">
            <TrendingUp className="h-8 w-8 mb-2 opacity-30" />
            <p className="text-sm">Pas encore de donnees</p>
            <p className="text-xs">Lance un snapshot pour voir l'evolution.</p>
          </div>
        ) : (
          <>
            <div className="w-full h-64 -ml-2">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={data} margin={{ top: 10, right: 12, left: 0, bottom: 0 }}>
                  <defs>
                    {BUCKETS.map((b) => (
                      <linearGradient
                        key={b.key}
                        id={`grad-${uid}-${b.key}`}
                        x1="0"
                        y1="0"
                        x2="0"
                        y2="1"
                      >
                        <stop offset="0%" stopColor={b.color} stopOpacity={0.6} />
                        <stop offset="100%" stopColor={b.color} stopOpacity={0.05} />
                      </linearGradient>
                    ))}
                  </defs>
                  <CartesianGrid stroke="currentColor" strokeOpacity={0.08} vertical={false} />
                  <XAxis
                    dataKey="date"
                    tick={{ fontSize: 11 }}
                    stroke="currentColor"
                    strokeOpacity={0.5}
                    tickFormatter={(d: string) =>
                      new Date(d).toLocaleDateString("fr-CA", { month: "short", day: "2-digit" })
                    }
                    minTickGap={20}
                  />
                  <YAxis
                    tick={{ fontSize: 11 }}
                    stroke="currentColor"
                    strokeOpacity={0.5}
                    width={32}
                    allowDecimals={false}
                  />
                  <Tooltip content={<CustomTooltip />} />
                  {BUCKETS.map((b) => (
                    <Area
                      key={b.key}
                      type="monotone"
                      dataKey={b.key}
                      stackId="1"
                      stroke={b.color}
                      strokeWidth={1.5}
                      fill={`url(#grad-${uid}-${b.key})`}
                      isAnimationActive={false}
                    />
                  ))}
                </AreaChart>
              </ResponsiveContainer>
            </div>
            <div className="flex flex-wrap items-center gap-4 text-[11px] text-muted-foreground mt-2 ml-8">
              {BUCKETS.map((b) => (
                <span key={b.key} className="flex items-center gap-1.5">
                  <span
                    className="inline-block h-2 w-3 rounded-sm"
                    style={{ background: b.color }}
                  />
                  {b.label}
                </span>
              ))}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
