"use client";

import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { authFetch } from "@/lib/api-client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { BookOpen, AlertCircle } from "lucide-react";

type ReadabilityResult = {
  words: number;
  sentences: number;
  syllables: number;
  characters: number;
  avg_words_per_sentence: number;
  avg_syllables_per_word: number;
  flesch: number | null;
  ari: number | null;
  level:
    | "very_easy"
    | "easy"
    | "standard"
    | "fairly_difficult"
    | "difficult"
    | "very_difficult"
    | null;
  level_label: string;
};

const LEVEL_COLOR: Record<NonNullable<ReadabilityResult["level"]>, string> = {
  very_easy: "bg-green-500",
  easy: "bg-emerald-500",
  standard: "bg-blue-500",
  fairly_difficult: "bg-amber-500",
  difficult: "bg-orange-500",
  very_difficult: "bg-red-500",
};

const LEVEL_TEXT_COLOR: Record<NonNullable<ReadabilityResult["level"]>, string> = {
  very_easy: "text-green-600",
  easy: "text-emerald-600",
  standard: "text-blue-600",
  fairly_difficult: "text-amber-600",
  difficult: "text-orange-600",
  very_difficult: "text-red-600",
};

const LEVEL_LABEL: Record<NonNullable<ReadabilityResult["level"]>, string> = {
  very_easy: "Très facile (lecteur ~10 ans)",
  easy: "Facile (lecteur ~12 ans)",
  standard: "Standard (lecteur ~14 ans)",
  fairly_difficult: "Assez difficile (lycéen)",
  difficult: "Difficile (étudiant)",
  very_difficult: "Très difficile (spécialiste)",
};

export function ReadabilityCard({
  content,
  language,
}: {
  content: string;
  language: string;
}) {
  const [debounced, setDebounced] = useState(content);

  useEffect(() => {
    const handle = setTimeout(() => setDebounced(content), 800);
    return () => clearTimeout(handle);
  }, [content]);

  const { data, isLoading } = useQuery<ReadabilityResult>({
    queryKey: ["readability", language, debounced.length, debounced.slice(0, 200)],
    queryFn: async () => {
      const res = await authFetch("/readability/", {
        method: "POST",
        body: JSON.stringify({ content: debounced, language }),
      });
      if (!res.ok) throw new Error("readability failed");
      return res.json();
    },
    enabled: debounced.trim().length > 50,
    staleTime: 30 * 1000,
  });

  // Suggestions based on metrics
  const suggestions: string[] = [];
  if (data) {
    if (data.avg_words_per_sentence > 25) {
      suggestions.push(
        "Phrases trop longues (>25 mots/phrase). Coupe en plusieurs phrases courtes."
      );
    }
    if (data.avg_syllables_per_word > 1.9) {
      suggestions.push(
        "Mots complexes (1.9+ syllabes/mot). Privilégie le vocabulaire courant."
      );
    }
    if (data.flesch !== null && data.flesch < 50) {
      suggestions.push(
        "Score Flesch < 50 : ton article est dur à lire pour le grand public. Simplifie le style."
      );
    }
  }

  if (debounced.trim().length <= 50) {
    return null; // Don't show until article has some content
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg flex items-center gap-2">
          <BookOpen className="h-5 w-5 text-primary" />
          Lisibilité
        </CardTitle>
        <p className="text-xs text-muted-foreground">
          Score Flesch-Kincaid + ARI calculé sur ton contenu (rafraîchi 800 ms
          après ta dernière frappe).
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        {isLoading || !data ? (
          <Skeleton className="h-24" />
        ) : data.flesch === null ? (
          <p className="text-sm text-muted-foreground">
            Texte trop court pour un score fiable.
          </p>
        ) : (
          <>
            <div className="flex items-end gap-4">
              <div>
                <div
                  className={`text-4xl font-bold ${
                    data.level ? LEVEL_TEXT_COLOR[data.level] : ""
                  }`}
                >
                  {data.flesch}
                </div>
                <div className="text-xs text-muted-foreground">
                  Score Flesch
                </div>
              </div>
              <div className="flex-1">
                <div className="text-sm font-medium mb-1">
                  {data.level ? LEVEL_LABEL[data.level] : ""}
                </div>
                <div className="h-2 w-full bg-muted rounded overflow-hidden">
                  <div
                    className={`h-full ${
                      data.level ? LEVEL_COLOR[data.level] : "bg-muted"
                    }`}
                    style={{
                      width: `${Math.max(0, Math.min(100, data.flesch))}%`,
                    }}
                  />
                </div>
                <div className="flex justify-between text-[10px] text-muted-foreground mt-1">
                  <span>0 très difficile</span>
                  <span>100 très facile</span>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs">
              <div className="border rounded p-2">
                <div className="text-muted-foreground">Mots</div>
                <div className="font-mono font-bold">{data.words}</div>
              </div>
              <div className="border rounded p-2">
                <div className="text-muted-foreground">
                  Phrases
                </div>
                <div className="font-mono font-bold">{data.sentences}</div>
              </div>
              <div className="border rounded p-2">
                <div className="text-muted-foreground">Mots/phrase</div>
                <div className="font-mono font-bold">
                  {data.avg_words_per_sentence}
                </div>
              </div>
              <div className="border rounded p-2">
                <div className="text-muted-foreground">ARI</div>
                <div className="font-mono font-bold">{data.ari}</div>
              </div>
            </div>

            {suggestions.length > 0 && (
              <div className="border-t pt-3 space-y-2">
                <h4 className="text-xs font-mono uppercase tracking-wide text-muted-foreground">
                  Suggestions
                </h4>
                <ul className="space-y-1 text-xs">
                  {suggestions.map((s, i) => (
                    <li key={i} className="flex items-start gap-2">
                      <AlertCircle className="h-3 w-3 text-amber-600 shrink-0 mt-0.5" />
                      <span>{s}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
