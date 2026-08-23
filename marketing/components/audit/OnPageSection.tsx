"use client";

import { Check, X, FileCode2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export type OnPageResultat = {
  score: number;
  controles: {
    cle: string;
    libelle: string;
    poids: number;
    reussi: boolean;
  }[];
} | null;

/**
 * Les huit controles on-page lus sur la page d'accueil.
 *
 * C'est la partie de l'audit qui a le plus de valeur immediate : elle ne
 * depend d'aucune API tierce, elle est disponible pour un site mis en ligne le
 * matin meme, et chaque ligne ratee se corrige sans attendre Google. La
 * vitesse et les positions, elles, peuvent manquer ou mettre des mois a bouger.
 */
export function OnPageSection({ onpage }: { onpage?: OnPageResultat }) {
  if (!onpage || !onpage.controles?.length) return null;

  const rates = onpage.controles.filter((c) => !c.reussi);
  const teinte =
    onpage.score >= 85
      ? "text-emerald-400"
      : onpage.score >= 60
        ? "text-amber-300"
        : "text-red-400";

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center justify-between gap-3 text-base">
          <span className="flex items-center gap-2">
            <FileCode2 className="h-4 w-4" />
            Signaux de la page d{"'"}accueil
          </span>
          <span className={`font-mono text-sm tabular-nums ${teinte}`}>
            {onpage.score}/100
          </span>
        </CardTitle>
      </CardHeader>
      <CardContent>
        <p className="mb-3 text-sm text-muted-foreground">
          {rates.length === 0
            ? "Tout est en place sur la page d'accueil."
            : `${rates.length} ${rates.length > 1 ? "points" : "point"} à corriger, sans attendre Google.`}
        </p>
        <ul className="grid grid-cols-1 gap-x-6 gap-y-1.5 sm:grid-cols-2">
          {onpage.controles.map((c) => (
            <li key={c.cle} className="flex items-center gap-2 text-sm">
              {c.reussi ? (
                <Check aria-hidden="true" className="h-4 w-4 shrink-0 text-emerald-400" />
              ) : (
                <X aria-hidden="true" className="h-4 w-4 shrink-0 text-red-400" />
              )}
              <span className="sr-only">{c.reussi ? "Conforme :" : "À corriger :"}</span>
              <span className={c.reussi ? "text-muted-foreground" : "text-foreground"}>
                {c.libelle}
              </span>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}
