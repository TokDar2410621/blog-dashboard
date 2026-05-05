import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { authFetch } from "@/lib/api-client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Languages, ArrowRight, Info } from "lucide-react";

type LexiconMatch = {
  term: string;
  suggestion: string;
  explanation: string;
  count: number;
  positions: { line: number; col: number; matched_text: string }[];
};

type LexiconResult = {
  matches: LexiconMatch[];
  total_matches: number;
  unique_terms: number;
};

export function LexiconCard({
  content,
  language,
}: {
  content: string;
  language: string;
}) {
  const { t } = useTranslation();
  const [debounced, setDebounced] = useState(content);

  useEffect(() => {
    const handle = setTimeout(() => setDebounced(content), 1000);
    return () => clearTimeout(handle);
  }, [content]);

  const { data, isLoading } = useQuery<LexiconResult>({
    queryKey: ["lexicon", debounced.length, debounced.slice(0, 200)],
    queryFn: async () => {
      const res = await authFetch("/lexicon-check/", {
        method: "POST",
        body: JSON.stringify({ content: debounced }),
      });
      if (!res.ok) throw new Error("lexicon failed");
      return res.json();
    },
    enabled: debounced.trim().length > 50 && language === "fr",
    staleTime: 60 * 1000,
  });

  // Only render for French articles - lexicon is FR-FR vs FR-CA only.
  if (language !== "fr") return null;
  if (debounced.trim().length <= 50) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg flex items-center gap-2">
          <Languages className="h-5 w-5 text-primary" />
          {t("lexicon.title")}
        </CardTitle>
        <p className="text-xs text-muted-foreground">{t("lexicon.subtitle")}</p>
      </CardHeader>
      <CardContent className="space-y-3">
        {isLoading || !data ? (
          <Skeleton className="h-20" />
        ) : data.unique_terms === 0 ? (
          <p className="text-sm text-green-600 flex items-center gap-2">
            ✓ {t("lexicon.allClear")}
          </p>
        ) : (
          <>
            <p className="text-xs text-muted-foreground">
              {t("lexicon.summary", {
                terms: data.unique_terms,
                total: data.total_matches,
              })}
            </p>
            <ul className="space-y-2">
              {data.matches.map((m, i) => (
                <li
                  key={i}
                  className="flex items-start gap-3 border rounded p-2"
                >
                  <span className="font-mono text-xs px-2 py-1 rounded bg-amber-500/10 text-amber-700 dark:text-amber-400 shrink-0">
                    ×{m.count}
                  </span>
                  <div className="flex-1 min-w-0 text-sm">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-mono line-through text-muted-foreground">
                        {m.term}
                      </span>
                      <ArrowRight className="h-3 w-3 text-muted-foreground" />
                      <span className="font-mono text-green-700 dark:text-green-500 font-medium">
                        {m.suggestion}
                      </span>
                    </div>
                    {m.explanation && (
                      <div className="text-xs text-muted-foreground mt-1 flex items-start gap-1">
                        <Info className="h-3 w-3 shrink-0 mt-0.5" />
                        <span>{m.explanation}</span>
                      </div>
                    )}
                  </div>
                </li>
              ))}
            </ul>
          </>
        )}
      </CardContent>
    </Card>
  );
}
