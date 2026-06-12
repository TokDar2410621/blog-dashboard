"use client";

import Link from "next/link";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Button } from "@/components/ui/button";
import { CheckCircle2, Circle, Sparkles, ArrowRight } from "lucide-react";
import type { HexTopic } from "./HexTile";

type SelectedTopic = {
  topic: HexTopic;
  clusterTheme: string;
};

type Props = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  selection: SelectedTopic | null;
  /** Site base path - prefixed to generate/article links. */
  siteBase: string;
};

function inferIntent(label: string): string {
  const l = label.toLowerCase();
  if (/^(comment|how to|tuto|guide|installer)/.test(l)) return "Informationnel (guide)";
  if (/^(quel|quelle|meilleur|best|top|comparatif|vs)/.test(l))
    return "Commercial (comparaison)";
  if (/(prix|tarif|cout|acheter|abonnement|pricing)/.test(l))
    return "Transactionnel";
  if (/(definition|qu'est-ce|c'est quoi|what is)/.test(l))
    return "Informationnel (definition)";
  return "Informationnel";
}

function suggestionTitles(label: string, clusterTheme: string): string[] {
  // Tiny client-side prompt suite. Real titles will come from the article
  // generation pipeline; these are placeholders that help the user picture
  // what they would get.
  return [
    `Guide complet : ${label}`,
    `${label} - tout ce qu'il faut savoir en ${new Date().getFullYear()}`,
    `${clusterTheme} et ${label} : comment s'y prendre`,
  ];
}

export function TopicDrawer({
  open,
  onOpenChange,
  selection,
  siteBase,
}: Props) {
  if (!selection) {
    return (
      <Sheet open={open} onOpenChange={onOpenChange}>
        <SheetContent side="right" className="sm:max-w-md" />
      </Sheet>
    );
  }

  const { topic, clusterTheme } = selection;
  const Icon =
    topic.status === "covered"
      ? CheckCircle2
      : topic.status === "recommended"
        ? Sparkles
        : Circle;
  const iconColor =
    topic.status === "covered"
      ? "text-emerald-500"
      : topic.status === "recommended"
        ? "text-amber-500"
        : "text-zinc-400";

  const slug = (topic.meta?.slug as string) ?? null;
  const titles = suggestionTitles(topic.label, clusterTheme);

  const generateHref =
    `${siteBase}/generer?` +
    [
      `title=${encodeURIComponent(titles[0])}`,
      `topic=${encodeURIComponent(topic.label)}`,
      `keywords=${encodeURIComponent(`${topic.label}, ${clusterTheme}`)}`,
      `autostart=1`,
    ].join("&");

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="sm:max-w-md w-full flex flex-col">
        <SheetHeader className="border-b">
          <div className="flex items-start gap-3">
            <Icon className={`h-6 w-6 shrink-0 mt-0.5 ${iconColor}`} />
            <div>
              <SheetTitle className="text-base leading-tight">
                {topic.label}
              </SheetTitle>
              <SheetDescription className="text-xs">
                Cluster : <span className="font-mono">{clusterTheme}</span>
              </SheetDescription>
            </div>
          </div>
        </SheetHeader>

        <div className="flex-1 overflow-y-auto p-4 space-y-5">
          {/* Breakdown */}
          <section>
            <h3 className="text-[11px] font-mono uppercase tracking-wider text-muted-foreground mb-2">
              Donnees
            </h3>
            <div className="grid grid-cols-3 gap-2 text-center">
              <div className="border rounded p-2">
                <p className="text-[10px] text-muted-foreground">Volume</p>
                <p className="font-semibold text-sm">
                  {typeof topic.volume === "number"
                    ? topic.volume.toLocaleString()
                    : "-"}
                </p>
              </div>
              <div className="border rounded p-2">
                <p className="text-[10px] text-muted-foreground">KD</p>
                <p className="font-semibold text-sm">
                  {typeof topic.kd === "number" ? topic.kd : "-"}
                </p>
              </div>
              <div className="border rounded p-2">
                <p className="text-[10px] text-muted-foreground">Statut</p>
                <p className="font-semibold text-sm capitalize">
                  {topic.status === "covered"
                    ? "Couvert"
                    : topic.status === "recommended"
                      ? "Suggere"
                      : "Manquant"}
                </p>
              </div>
            </div>
            <p className="text-[11px] text-muted-foreground mt-2">
              Intent estime : <strong>{inferIntent(topic.label)}</strong>
            </p>
          </section>

          {/* Existing article shortcut */}
          {topic.status === "covered" && slug && (
            <section>
              <h3 className="text-[11px] font-mono uppercase tracking-wider text-muted-foreground mb-2">
                Article existant
              </h3>
              <Link
                href={`${siteBase}/articles/${slug}`}
                className="block border rounded p-3 hover:border-primary"
              >
                <p className="font-medium text-sm">{topic.label}</p>
                <p className="text-xs text-muted-foreground font-mono mt-1">
                  /{slug}
                </p>
              </Link>
            </section>
          )}

          {/* Suggestions */}
          {topic.status !== "covered" && (
            <section>
              <h3 className="text-[11px] font-mono uppercase tracking-wider text-muted-foreground mb-2">
                Suggestions de titres
              </h3>
              <ul className="space-y-2">
                {titles.map((tt, i) => (
                  <li
                    key={i}
                    className="text-sm border rounded p-2 hover:border-primary/40"
                  >
                    {tt}
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>

        {/* Footer CTA */}
        {topic.status !== "covered" && (
          <div className="border-t p-4">
            <Link href={generateHref} onClick={() => onOpenChange(false)}>
              <Button className="w-full" size="lg">
                <Sparkles className="h-4 w-4 mr-2" />
                Generer cet article
                <ArrowRight className="h-4 w-4 ml-2" />
              </Button>
            </Link>
            <p className="text-[10px] text-muted-foreground mt-2 text-center">
              Lance la generation automatiquement avec ces parametres
            </p>
          </div>
        )}
      </SheetContent>
    </Sheet>
  );
}
