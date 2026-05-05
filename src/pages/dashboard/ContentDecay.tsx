import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useMutation } from "@tanstack/react-query";
import { authFetch } from "@/lib/api-client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  TrendingDown,
  Loader2,
  ArrowDown,
  RefreshCw,
  Trash2,
  Wrench,
  ArrowRight,
} from "lucide-react";
import { toast } from "sonner";

type DecayingPage = {
  url: string;
  slug: string;
  impressions_now: number;
  impressions_before: number;
  clicks_now: number;
  clicks_before: number;
  impressions_delta_pct: number;
  clicks_delta_pct: number | null;
  position_now: number | null;
  position_before: number | null;
  suggested_action: "redirect_or_remove" | "major_refresh" | "minor_refresh";
};

type DecayResult = {
  site_id: number;
  days: number;
  period_current: { start: string; end: string };
  period_previous: { start: string; end: string };
  decaying_count: number;
  healthy_count: number;
  new_pages_count: number;
  decaying: DecayingPage[];
};

const ACTION_META: Record<
  DecayingPage["suggested_action"],
  { color: string; icon: typeof Wrench }
> = {
  redirect_or_remove: { color: "red", icon: Trash2 },
  major_refresh: { color: "amber", icon: Wrench },
  minor_refresh: { color: "blue", icon: RefreshCw },
};

export default function ContentDecay() {
  const { t } = useTranslation();
  const { siteId } = useParams<{ siteId: string }>();
  const [days, setDays] = useState("30");
  const [data, setData] = useState<DecayResult | null>(null);
  const [errorCode, setErrorCode] = useState<string | null>(null);
  const base = `/dashboard/${siteId}`;

  const mutation = useMutation({
    mutationFn: async () => {
      setErrorCode(null);
      const res = await authFetch(
        `/sites/${siteId}/content-decay/?days=${days}`
      );
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        if (err.code) setErrorCode(err.code);
        throw new Error(err.error || t("decay.error"));
      }
      return (await res.json()) as DecayResult;
    },
    onSuccess: (d) => setData(d),
    onError: (err: Error) => toast.error(err.message),
  });

  return (
    <div className="space-y-6 max-w-5xl">
      <div>
        <h1 className="text-2xl font-bold">{t("decay.title")}</h1>
        <p className="text-muted-foreground">{t("decay.subtitle")}</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <TrendingDown className="h-5 w-5 text-amber-600" />
            {t("decay.runTitle")}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-end gap-3">
            <div className="space-y-2">
              <label className="text-sm font-medium">{t("decay.window")}</label>
              <Select value={days} onValueChange={setDays}>
                <SelectTrigger className="w-32">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="7">7 {t("decay.daysShort")}</SelectItem>
                  <SelectItem value="14">14 {t("decay.daysShort")}</SelectItem>
                  <SelectItem value="30">30 {t("decay.daysShort")}</SelectItem>
                  <SelectItem value="60">60 {t("decay.daysShort")}</SelectItem>
                  <SelectItem value="90">90 {t("decay.daysShort")}</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <Button
              onClick={() => mutation.mutate()}
              disabled={mutation.isPending}
              size="lg"
            >
              {mutation.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  {t("decay.running")}
                </>
              ) : (
                <>
                  <TrendingDown className="h-4 w-4 mr-2" />
                  {t("decay.run")}
                </>
              )}
            </Button>
          </div>
          {mutation.isPending && (
            <p className="text-xs text-muted-foreground mt-3">
              {t("decay.runWait")}
            </p>
          )}
        </CardContent>
      </Card>

      {errorCode === "gsc_not_configured" && (
        <Card>
          <CardContent className="py-6 text-center text-sm">
            <p className="mb-3">{t("decay.gscNotConfigured")}</p>
            <Link to={`${base}/parametres`}>
              <Button variant="outline">
                {t("decay.goToSettings")}
                <ArrowRight className="h-4 w-4 ml-2" />
              </Button>
            </Link>
          </CardContent>
        </Card>
      )}

      {errorCode === "gsc_reauth_required" && (
        <Card>
          <CardContent className="py-6 text-center text-sm">
            <p className="mb-3">{t("decay.gscReauthRequired")}</p>
            <Link to={`${base}/parametres`}>
              <Button variant="outline">
                {t("decay.goToSettings")}
                <ArrowRight className="h-4 w-4 ml-2" />
              </Button>
            </Link>
          </CardContent>
        </Card>
      )}

      {mutation.isPending && (
        <div className="space-y-3">
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-48 w-full" />
        </div>
      )}

      {data && !mutation.isPending && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Card>
              <CardContent className="pt-6">
                <div className="text-3xl font-bold text-amber-600 flex items-center gap-2">
                  <ArrowDown className="h-6 w-6" />
                  {data.decaying_count}
                </div>
                <div className="text-xs text-muted-foreground mt-1">
                  {t("decay.decaying")}
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-3xl font-bold text-green-600">
                  {data.healthy_count}
                </div>
                <div className="text-xs text-muted-foreground mt-1">
                  {t("decay.healthy")}
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-3xl font-bold text-blue-600">
                  {data.new_pages_count}
                </div>
                <div className="text-xs text-muted-foreground mt-1">
                  {t("decay.new")}
                </div>
              </CardContent>
            </Card>
          </div>

          <p className="text-xs text-muted-foreground">
            {t("decay.periodCompare", {
              cur_start: data.period_current.start,
              cur_end: data.period_current.end,
              prev_start: data.period_previous.start,
              prev_end: data.period_previous.end,
            })}
          </p>

          {data.decaying.length === 0 ? (
            <Card>
              <CardContent className="py-12 text-center text-muted-foreground">
                <TrendingDown className="h-10 w-10 mx-auto mb-3 opacity-30" />
                <p>{t("decay.noDecay")}</p>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-3">
              {data.decaying.map((page) => {
                const meta = ACTION_META[page.suggested_action];
                const ActionIcon = meta.icon;
                return (
                  <Card key={page.url}>
                    <CardContent className="py-4">
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex-1 min-w-0">
                          <Link
                            to={`${base}/articles/${page.slug}`}
                            className="font-medium text-sm hover:text-primary truncate block"
                          >
                            {page.slug || page.url}
                          </Link>
                          <p className="text-xs text-muted-foreground mt-1 truncate">
                            {page.url}
                          </p>

                          <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mt-3 text-xs">
                            <div>
                              <div className="text-muted-foreground mb-0.5">
                                {t("decay.impressions")}
                              </div>
                              <div className="font-mono">
                                <span className="text-muted-foreground">
                                  {page.impressions_before}
                                </span>{" "}
                                →{" "}
                                <span className="font-bold">
                                  {page.impressions_now}
                                </span>{" "}
                                <span
                                  className={
                                    page.impressions_delta_pct < 0
                                      ? "text-red-600"
                                      : "text-green-600"
                                  }
                                >
                                  ({page.impressions_delta_pct > 0 ? "+" : ""}
                                  {page.impressions_delta_pct}%)
                                </span>
                              </div>
                            </div>
                            <div>
                              <div className="text-muted-foreground mb-0.5">
                                {t("decay.clicks")}
                              </div>
                              <div className="font-mono">
                                <span className="text-muted-foreground">
                                  {page.clicks_before}
                                </span>{" "}
                                →{" "}
                                <span className="font-bold">{page.clicks_now}</span>
                                {page.clicks_delta_pct !== null && (
                                  <span
                                    className={
                                      page.clicks_delta_pct < 0
                                        ? " text-red-600"
                                        : " text-green-600"
                                    }
                                  >
                                    {" "}
                                    ({page.clicks_delta_pct > 0 ? "+" : ""}
                                    {page.clicks_delta_pct}%)
                                  </span>
                                )}
                              </div>
                            </div>
                            {page.position_now !== null && (
                              <div>
                                <div className="text-muted-foreground mb-0.5">
                                  {t("decay.position")}
                                </div>
                                <div className="font-mono">
                                  <span className="text-muted-foreground">
                                    #{page.position_before}
                                  </span>{" "}
                                  →{" "}
                                  <span className="font-bold">
                                    #{page.position_now}
                                  </span>
                                </div>
                              </div>
                            )}
                          </div>
                        </div>

                        <div className="shrink-0 flex flex-col items-end gap-2">
                          <span
                            className={`text-xs px-2 py-1 rounded font-mono uppercase flex items-center gap-1 ${
                              meta.color === "red"
                                ? "bg-red-500/10 text-red-700 dark:text-red-400"
                                : meta.color === "amber"
                                ? "bg-amber-500/10 text-amber-700 dark:text-amber-400"
                                : "bg-blue-500/10 text-blue-700 dark:text-blue-400"
                            }`}
                          >
                            <ActionIcon className="h-3 w-3" />
                            {t(`decay.action.${page.suggested_action}`)}
                          </span>
                          <Link to={`${base}/articles/${page.slug}`}>
                            <Button size="sm" variant="outline">
                              {t("decay.fix")}
                              <ArrowRight className="h-3 w-3 ml-1" />
                            </Button>
                          </Link>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          )}
        </>
      )}
    </div>
  );
}
