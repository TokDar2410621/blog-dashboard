import { useState } from "react";
import { useTranslation } from "react-i18next";
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
  const { t } = useTranslation();
  const [keyword, setKeyword] = useState(defaultKeyword);
  const [timeframe, setTimeframe] = useState("today 12-m");
  const [data, setData] = useState<TrendsResult | null>(null);

  const mutation = useMutation({
    mutationFn: async () => {
      const res = await authFetch("/trends/", {
        method: "POST",
        body: JSON.stringify({ keyword, language, timeframe }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error || t("trends.error"));
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
          {t("trends.title")}
        </CardTitle>
        <p className="text-sm text-muted-foreground">{t("trends.subtitle")}</p>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-[1fr_auto_auto] gap-3 items-end">
          <div className="space-y-1">
            <Label className="text-xs">{t("trends.keyword")}</Label>
            <Input
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              placeholder={t("trends.keywordPlaceholder")}
              onKeyDown={(e) => {
                if (e.key === "Enter") mutation.mutate();
              }}
            />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">{t("trends.timeframe")}</Label>
            <Select value={timeframe} onValueChange={setTimeframe}>
              <SelectTrigger className="w-32">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="today 1-m">{t("trends.tf1m")}</SelectItem>
                <SelectItem value="today 3-m">{t("trends.tf3m")}</SelectItem>
                <SelectItem value="today 12-m">{t("trends.tf12m")}</SelectItem>
                <SelectItem value="today 5-y">{t("trends.tf5y")}</SelectItem>
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
                {t("trends.run")}
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
                      formatter={(value) => [value, t("trends.interest")]}
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
              <p className="text-sm text-muted-foreground">{t("trends.noData")}</p>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <h4 className="text-xs font-mono uppercase tracking-wide text-muted-foreground mb-2 flex items-center gap-1">
                  <Star className="h-3 w-3 text-amber-500" />
                  {t("trends.topQueries")}
                </h4>
                {data.top_queries.length === 0 ? (
                  <p className="text-xs text-muted-foreground">
                    {t("trends.noTop")}
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
                  {t("trends.risingQueries")}
                </h4>
                {data.rising_queries.length === 0 ? (
                  <p className="text-xs text-muted-foreground">
                    {t("trends.noRising")}
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
              {t("trends.geoLabel", { geo: data.geo, tf: data.timeframe })}
            </p>
          </>
        )}
      </CardContent>
    </Card>
  );
}
