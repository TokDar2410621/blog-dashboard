"use client";

/**
 * QuotaBanner - surfaces the user's monthly article quota state and credit
 * balance. Hidden when usage is below `warnAt` (default 70%). Renders a soft
 * warning between `warnAt` and 100%, and a hard block when exhausted.
 *
 * Reuses the data already exposed on /billing/me/ - no extra request.
 */
import { useQuery, useMutation } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { authFetch } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { AlertTriangle, Coins, Lightbulb, Zap, Loader2 } from "lucide-react";
import { toast } from "sonner";

type Subscription = {
  plan: "free" | "solo" | "pro" | "agency";
  limits: { articles_per_month: number | null };
  usage?: { articles_this_month: number };
  credits?: { balance: number };
};

export function QuotaBanner({
  warnAt = 70,
}: {
  warnAt?: number;
}) {
  const router = useRouter();

  const { data: sub } = useQuery<Subscription>({
    queryKey: ["billing-me"],
    queryFn: async () => {
      const res = await authFetch("/billing/me/");
      if (!res.ok) throw new Error("billing fetch failed");
      return res.json();
    },
    staleTime: 30_000,
  });

  const buyCredits = useMutation({
    mutationFn: async (pack: "small" | "medium" | "large") => {
      const res = await authFetch("/billing/credits/buy/", {
        method: "POST",
        body: JSON.stringify({ pack }),
      });
      const data = await res.json();
      if (!res.ok || !data.url) throw new Error(data.error || "Erreur achat");
      return data.url as string;
    },
    onSuccess: (url) => {
      window.location.href = url;
    },
    onError: (e: Error) => toast.error(e.message),
  });

  if (!sub) return null;
  const limit = sub.limits.articles_per_month;
  if (limit == null) return null; // unlimited - no banner needed
  const used = sub.usage?.articles_this_month ?? 0;
  const credits = sub.credits?.balance ?? 0;
  const pct = limit > 0 ? (used / limit) * 100 : 100;

  // Below the warn threshold AND no exhaustion -> don't render anything
  if (pct < warnAt && used < limit) return null;

  const exhausted = used >= limit;
  const hasFallback = credits > 0;

  // ------ Exhausted, no credits -> hard block, emerald CTA ------
  if (exhausted && !hasFallback) {
    return (
      <div className="rounded-lg border border-destructive/40 bg-destructive/[0.04] p-4 mb-4 flex flex-col md:flex-row items-start md:items-center gap-3 md:justify-between">
        <div className="flex items-start gap-3">
          <AlertTriangle className="h-5 w-5 text-destructive shrink-0 mt-0.5" />
          <div>
            <div className="font-semibold text-sm">
              Quota mensuel atteint ({used}/{limit} articles)
            </div>
            <div className="text-xs text-muted-foreground mt-0.5">
              Achète des crédits pour continuer ce mois-ci, ou attends le 1er du mois prochain.
            </div>
          </div>
        </div>
        <div className="flex gap-2 shrink-0">
          <Button
            size="sm"
            variant="default"
            onClick={() => buyCredits.mutate("small")}
            disabled={buyCredits.isPending}
          >
            {buyCredits.isPending ? (
              <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
            ) : (
              <Coins className="h-3.5 w-3.5 mr-1.5" />
            )}
            +10 crédits · 25$
          </Button>
          <Button size="sm" variant="outline" onClick={() => router.push("/billing")}>
            Voir les plans
          </Button>
        </div>
      </div>
    );
  }

  // ------ Exhausted, has credits -> soft notice that credits will be used ------
  if (exhausted && hasFallback) {
    return (
      <div className="rounded-lg border border-amber-500/30 bg-amber-500/[0.04] p-4 mb-4 flex items-center gap-3">
        <Zap className="h-5 w-5 text-amber-500 shrink-0" />
        <div className="flex-1 text-sm">
          <span className="font-semibold">Quota mensuel atteint.</span>{" "}
          <span className="text-muted-foreground">
            Tu utilises maintenant tes crédits ({credits} disponibles · 1 par article).
          </span>
        </div>
        <Button
          size="sm"
          variant="ghost"
          onClick={() => router.push("/billing")}
          className="text-amber-700 dark:text-amber-300"
        >
          Gérer
        </Button>
      </div>
    );
  }

  // ------ Approaching limit (>= warnAt%, < 100%) -> just a friendly nudge ------
  return (
    <div className="rounded-lg border border-border/50 bg-muted/30 p-3 mb-4 flex items-center gap-3 text-sm">
      <Lightbulb className="h-4 w-4 text-primary shrink-0" />
      <div className="flex-1">
        Plus que <span className="font-semibold">{limit - used}</span> articles
        ce mois-ci{" "}
        <span className="text-muted-foreground">
          ({used}/{limit} · plan {sub.plan})
        </span>
        {credits > 0 && (
          <span className="text-muted-foreground">
            {" "}· {credits} crédits en réserve
          </span>
        )}
      </div>
      <Button
        size="sm"
        variant="ghost"
        onClick={() => router.push("/billing")}
        className="text-xs"
      >
        Plus de crédits
      </Button>
    </div>
  );
}
