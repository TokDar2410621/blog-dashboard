import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {
  fetchProofSummary,
  fetchProofShareState,
  enableProofShare,
  revokeProofShare,
  type ProofSummary,
  type ProofShareState,
} from "@/lib/api-client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import {
  TrendingUp, Share2, Copy, RefreshCw, CheckCircle2, Sparkles,
} from "lucide-react";

function formatNumber(n: number): string {
  if (Math.abs(n) >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return String(n);
}

export function ProofCard({ siteId }: { siteId: string | number }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [copied, setCopied] = useState(false);

  const summary = useQuery<ProofSummary>({
    queryKey: ["proof-summary", siteId],
    queryFn: () => fetchProofSummary(Number(siteId)),
    staleTime: 5 * 60 * 1000,
  });

  const share = useQuery<ProofShareState>({
    queryKey: ["proof-share", siteId],
    queryFn: () => fetchProofShareState(Number(siteId)),
    staleTime: 60 * 1000,
  });

  const enable = useMutation({
    mutationFn: (rotate: boolean) => enableProofShare(Number(siteId), { rotate }),
    onSuccess: (data) => qc.setQueryData(["proof-share", siteId], data),
  });

  const revoke = useMutation({
    mutationFn: () => revokeProofShare(Number(siteId)),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["proof-share", siteId] }),
  });

  if (summary.isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-primary" />
            {t("proof.cardTitle", "Preuve Gridar")}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <Skeleton className="h-20" />
        </CardContent>
      </Card>
    );
  }

  if (summary.isError || !summary.data) {
    return null;
  }

  const s = summary.data;
  const hasData = s.posts_with_attribution > 0;

  return (
    <Card className="border-primary/30 bg-primary/5">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Sparkles className="h-5 w-5 text-primary" />
          {t("proof.cardTitle", "Preuve Gridar")}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {!hasData ? (
          <div className="text-sm text-muted-foreground">
            <p>
              {t(
                "proof.empty",
                "Tes articles n'ont pas encore atteint le premier check J+30. La preuve arrive dès qu'un article a 30 jours d'historique GSC.",
              )}
            </p>
            <p className="mt-2">
              {t(
                "proof.emptyHint",
                "Si tu viens de connecter GSC, la baseline est capturée automatiquement en arrière-plan.",
              )}
            </p>
          </div>
        ) : (
          <>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <div className="flex items-baseline gap-2">
                  <span className="text-3xl font-bold text-primary">
                    +{formatNumber(s.total_impressions_gained)}
                  </span>
                  <TrendingUp className="h-4 w-4 text-primary" />
                </div>
                <p className="text-xs text-muted-foreground mt-1">
                  {t("proof.impressionsGained", "impressions gagnees")}
                </p>
              </div>
              <div>
                <div className="text-3xl font-bold text-primary">
                  +{formatNumber(s.total_clicks_gained)}
                </div>
                <p className="text-xs text-muted-foreground mt-1">
                  {t("proof.clicksGained", "clics gagnes")}
                </p>
              </div>
            </div>

            <p className="text-xs text-muted-foreground">
              {t("proof.attributionBase", "Sur {{count}} article(s) avec attribution active.", {
                count: s.posts_with_attribution,
              })}
            </p>

            {s.top_gainers.length > 0 && (
              <div className="border-t pt-3 space-y-2">
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                  {t("proof.topGainers", "Top articles gagnants")}
                </p>
                <ul className="space-y-1.5">
                  {s.top_gainers.slice(0, 3).map((g) => (
                    <li key={g.post_id} className="flex items-center justify-between text-sm">
                      <Link
                        to={`/dashboard/${siteId}/articles/${g.slug}`}
                        className="truncate hover:underline flex-1 mr-2"
                      >
                        {g.title}
                      </Link>
                      <span className="text-primary font-medium whitespace-nowrap">
                        +{formatNumber(g.impressions_gained)} J+{g.horizon}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <div className="border-t pt-3 space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium flex items-center gap-1.5">
                    <Share2 className="h-4 w-4" />
                    {t("proof.shareTitle", "Page publique de preuve")}
                  </p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {t(
                      "proof.shareDesc",
                      "Une URL en lecture seule à partager (équipe, client, LinkedIn).",
                    )}
                  </p>
                </div>
                <Switch
                  checked={!!share.data?.enabled}
                  onCheckedChange={(checked) => {
                    if (checked) enable.mutate(false);
                    else revoke.mutate();
                  }}
                  disabled={enable.isPending || revoke.isPending}
                />
              </div>

              {share.data?.enabled && share.data.public_url && (
                <div className="flex items-center gap-2">
                  <code className="text-xs bg-background border rounded px-2 py-1 flex-1 truncate">
                    {share.data.public_url}
                  </code>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      navigator.clipboard.writeText(share.data!.public_url!);
                      setCopied(true);
                      setTimeout(() => setCopied(false), 1500);
                    }}
                  >
                    {copied ? (
                      <CheckCircle2 className="h-3.5 w-3.5" />
                    ) : (
                      <Copy className="h-3.5 w-3.5" />
                    )}
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => enable.mutate(true)}
                    disabled={enable.isPending}
                    title={t("proof.rotateTitle", "Generer un nouveau token (revoque l'ancien)")}
                  >
                    <RefreshCw className="h-3.5 w-3.5" />
                  </Button>
                </div>
              )}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
