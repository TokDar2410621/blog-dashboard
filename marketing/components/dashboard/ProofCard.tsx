"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
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
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";

function formatNumber(n: number): string {
  if (Math.abs(n) >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return String(n);
}

export function ProofCard({ siteId }: { siteId: string | number }) {
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
            Preuve Gridar
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
          Preuve Gridar
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {!hasData ? (
          <div className="text-sm text-muted-foreground">
            <p>
              Tes articles n&apos;ont pas encore atteint le premier check J+30. La preuve arrive dès qu&apos;un article a 30 jours d&apos;historique GSC.
            </p>
            <p className="mt-2">
              Si tu viens de connecter GSC, la baseline est capturée automatiquement en arrière-plan.
            </p>
          </div>
        ) : (
          <>
            <TooltipProvider>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <div className="flex items-baseline gap-2">
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <span className="text-3xl font-bold text-primary cursor-help">
                          +{formatNumber(s.total_impressions_gained)}
                        </span>
                      </TooltipTrigger>
                      <TooltipContent className="max-w-xs">
                        <p className="font-medium mb-1">Impressions gagnees</p>
                        <p>
                          Somme des impressions GSC supplementaires constatees
                          a J+30 / J+60 / J+90 apres publication, comparees a
                          la baseline pre-publication.
                        </p>
                        <p className="mt-2 text-muted-foreground">
                          Source : Google Search Console + snapshots de
                          baseline Gridar.
                        </p>
                      </TooltipContent>
                    </Tooltip>
                    <TrendingUp className="h-4 w-4 text-primary" />
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    impressions gagnees
                  </p>
                </div>
                <div>
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <div className="text-3xl font-bold text-primary cursor-help">
                        +{formatNumber(s.total_clicks_gained)}
                      </div>
                    </TooltipTrigger>
                    <TooltipContent className="max-w-xs">
                      <p className="font-medium mb-1">Clics gagnes</p>
                      <p>
                        Somme des clics GSC supplementaires constates a J+30 /
                        J+60 / J+90 apres publication, comparees a la baseline
                        pre-publication.
                      </p>
                      <p className="mt-2 text-muted-foreground">
                        Source : Google Search Console + snapshots de baseline
                        Gridar.
                      </p>
                    </TooltipContent>
                  </Tooltip>
                  <p className="text-xs text-muted-foreground mt-1">
                    clics gagnes
                  </p>
                </div>
              </div>
            </TooltipProvider>

            <p className="text-xs text-muted-foreground">
              Sur {s.posts_with_attribution} article(s) avec attribution active.
            </p>

            {s.top_gainers.length > 0 && (
              <div className="border-t pt-3 space-y-2">
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                  Top articles gagnants
                </p>
                <ul className="space-y-1.5">
                  {s.top_gainers.slice(0, 3).map((g) => (
                    <li key={g.post_id} className="flex items-center justify-between text-sm">
                      <Link
                        href={`/dashboard/${siteId}/articles/${g.slug}`}
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
                    Page publique de preuve
                  </p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Une URL en lecture seule à partager (équipe, client, LinkedIn).
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
                    title="Generer un nouveau token (revoque l'ancien)"
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
