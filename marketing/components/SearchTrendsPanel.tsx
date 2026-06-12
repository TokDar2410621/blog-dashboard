"use client";

import { useParams } from "next/navigation";
import { usePersistedState } from "@/hooks/usePersistedState";
import { useMutation } from "@tanstack/react-query";
import { authFetch } from "@/lib/api-client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  TrendingUp,
  Loader2,
  ArrowUp,
  Star,
} from "lucide-react";
import { toast } from "sonner";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip as ChartTooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";

type TrendPoint = { date: string; value: number };
type Query = { query: string; value: number };

type TrendsResult = {
  keyword: string;
  language: string;
  geo: string;
  timeframe: string;
  interest_over_time: TrendPoint[];
  top_queries: Query[];
  rising_queries: Query[];
};

export function SearchTrendsPanel({
  language,
  defaultKeyword = "",
}: {
  language: string;
  defaultKeyword?: string;
}) {
  const params = useParams<{ siteId: string }>();
  const siteId = params?.siteId;
  const persistKey = (slot: string) =>
    `gridar:site:${siteId || "global"}:search-trends:${slot}`;
  const [keyword, setKeyword] = usePersistedState<string>(persistKey("keyword"), defaultKeyword);
  const [timeframe, setTimeframe] = usePersistedState<string>(persistKey("timeframe"), "today 12-m");
  const [data, setData] = usePersistedState<TrendsResult | null>(persistKey("data"), null);

  const mutation = useMutation({
    mutationFn: async () => {
      const res = await authFetch("/trends/", {
        method: "POST",
        body: JSON.stringify({ keyword, language, timeframe }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(
          err.error ||
            "Erreur Google Trends (probable rate-limit). Réessaye dans quelques minutes.",
        );
      }
      return (await res.json()) as TrendsResult;
    },
    onSuccess: (d) => setData(d),
    onError: (err: Error) => toast.error(err.message),
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg flex items-center gap-2">
          <TrendingUp className="h-5 w-5 text-primary" />
          Tendances Google Trends
        </CardTitle>
        <p className="text-sm text-muted-foreground">
          Intérêt du mot-clé dans le temps + requêtes connexes les plus
          populaires et celles qui montent. Géo-localisé selon la langue
          (FR-CA, EN-US, ES-ES).
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-[1fr_auto_auto] gap-3 items-end">
          <div className="space-y-1">
            <Label className="text-xs">Mot-clé</Label>
            <Input
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              placeholder="Ex: travail hybride"
              onKeyDown={(e) => {
                if (e.key === "Enter") mutation.mutate();
              }}
            />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Période</Label>
            <Select value={timeframe} onValueChange={setTimeframe}>
              <SelectTrigger className="w-full md:w-32">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="today 1-m">1 mois</SelectItem>
                <SelectItem value="today 3-m">3 mois</SelectItem>
                <SelectItem value="today 12-m">12 mois</SelectItem>
                <SelectItem value="today 5-y">5 ans</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <Button
            onClick={() => mutation.mutate()}
            disabled={mutation.isPending || !keyword.trim()}
          >
            {mutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <>
                <TrendingUp className="h-4 w-4 mr-2" />
                Analyser
              </>
            )}
          </Button>
        </div>

        {mutation.isPending && (
          <div className="space-y-2">
            <Skeleton className="h-32 w-full" />
            <Skeleton className="h-16 w-full" />
          </div>
        )}

        {data && !mutation.isPending && (
          <>
            {data.interest_over_time.length > 0 ? (
              <div className="h-48 -ml-2">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart
                    data={data.interest_over_time}
                    margin={{ top: 8, right: 16, left: 0, bottom: 0 }}
                  >
                    <defs>
                      <linearGradient id="interestGradient" x1="0" y1="0" x2="0" y2="1">
                        <stop
                          offset="0%"
                          stopColor="hsl(var(--primary))"
                          stopOpacity={0.4}
                        />
                        <stop
                          offset="100%"
                          stopColor="hsl(var(--primary))"
                          stopOpacity={0}
                        />
                      </linearGradient>
                    </defs>
                    <CartesianGrid stroke="currentColor" strokeOpacity={0.08} />
                    <XAxis
                      dataKey="date"
                      tick={{ fontSize: 10 }}
                      stroke="currentColor"
                      strokeOpacity={0.5}
                      interval="preserveStartEnd"
                      minTickGap={40}
                    />
                    <YAxis
                      domain={[0, 100]}
                      tick={{ fontSize: 10 }}
                      stroke="currentColor"
                      strokeOpacity={0.5}
                      width={32}
                    />
                    <ChartTooltip
                      contentStyle={{
                        background: "hsl(var(--card))",
                        border: "1px solid hsl(var(--border))",
                        fontSize: 12,
                      }}
                      formatter={(value) => [value, "Intérêt"]}
                    />
                    <Area
                      type="monotone"
                      dataKey="value"
                      stroke="hsl(var(--primary))"
                      strokeWidth={2}
                      fill="url(#interestGradient)"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">
                Pas de données Trends pour ce mot-clé (volume trop faible).
              </p>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <h4 className="text-xs font-mono uppercase tracking-wide text-muted-foreground mb-2 flex items-center gap-1">
                  <Star className="h-3 w-3 text-amber-500" />
                  Top requêtes connexes
                </h4>
                {data.top_queries.length === 0 ? (
                  <p className="text-xs text-muted-foreground">
                    Aucune requête connexe.
                  </p>
                ) : (
                  <ul className="space-y-1">
                    {data.top_queries.map((q, i) => (
                      <li
                        key={i}
                        className="text-sm flex items-center justify-between gap-2 border-b last:border-0 py-1"
                      >
                        <span className="truncate">{q.query}</span>
                        <span className="text-xs font-mono text-muted-foreground shrink-0">
                          {q.value}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              <div>
                <h4 className="text-xs font-mono uppercase tracking-wide text-muted-foreground mb-2 flex items-center gap-1">
                  <ArrowUp className="h-3 w-3 text-green-600" />
                  Requêtes qui montent
                </h4>
                {data.rising_queries.length === 0 ? (
                  <p className="text-xs text-muted-foreground">
                    Aucune requête en hausse.
                  </p>
                ) : (
                  <ul className="space-y-1">
                    {data.rising_queries.map((q, i) => (
                      <li
                        key={i}
                        className="text-sm flex items-center justify-between gap-2 border-b last:border-0 py-1"
                      >
                        <span className="truncate">{q.query}</span>
                        <span className="text-xs font-mono text-green-600 shrink-0">
                          {q.value > 1000 ? "+1000%" : `+${q.value}%`}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>

            <p className="text-[10px] text-muted-foreground text-right">
              {`Geo: ${data.geo} | Période: ${data.timeframe}`}
            </p>
          </>
        )}
      </CardContent>
    </Card>
  );
}
