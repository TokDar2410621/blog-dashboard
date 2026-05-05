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
  MessageSquare,
  Loader2,
  ExternalLink,
} from "lucide-react";
import { toast } from "sonner";

type Question = {
  title: string;
  snippet: string;
  url: string;
  source: "reddit" | "quora";
};

type Result = {
  keyword: string;
  language: string;
  reddit_count: number;
  quora_count: number;
  questions: Question[];
};

export function CommunityQuestionsPanel({
  language,
  defaultKeyword = "",
}: {
  language: string;
  defaultKeyword?: string;
}) {
  const { t } = useTranslation();
  const [keyword, setKeyword] = useState(defaultKeyword);
  const [data, setData] = useState<Result | null>(null);

  const mutation = useMutation({
    mutationFn: async () => {
      const res = await authFetch("/community-questions/", {
        method: "POST",
        body: JSON.stringify({ keyword, language }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error || t("community.error"));
      }
      return (await res.json()) as Result;
    },
    onSuccess: (d) => setData(d),
    onError: (err: Error) => toast.error(err.message),
  });

  const handleGenerate = () => {
    if (!keyword.trim()) {
      toast.error(t("community.keywordRequired"));
      return;
    }
    mutation.mutate();
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg flex items-center gap-2">
          <MessageSquare className="h-5 w-5 text-primary" />
          {t("community.title")}
        </CardTitle>
        <p className="text-sm text-muted-foreground">{t("community.subtitle")}</p>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label>{t("community.keyword")}</Label>
          <div className="flex gap-2">
            <Input
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              placeholder={t("community.keywordPlaceholder")}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleGenerate();
              }}
            />
            <Button onClick={handleGenerate} disabled={mutation.isPending}>
              {mutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <>
                  <MessageSquare className="h-4 w-4 mr-2" />
                  {t("community.fetch")}
                </>
              )}
            </Button>
          </div>
        </div>

        {mutation.isPending && (
          <div className="space-y-2">
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
          </div>
        )}

        {data && !mutation.isPending && (
          <div className="space-y-3">
            <p className="text-xs text-muted-foreground">
              {t("community.found", {
                reddit: data.reddit_count,
                quora: data.quora_count,
              })}
            </p>
            {data.questions.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                {t("community.noQuestions")}
              </p>
            ) : (
              <ul className="space-y-2">
                {data.questions.map((q, i) => (
                  <li key={i} className="border rounded p-3">
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <span
                            className={`text-[10px] px-1.5 py-0.5 rounded font-mono uppercase ${
                              q.source === "reddit"
                                ? "bg-orange-500/10 text-orange-700 dark:text-orange-400"
                                : "bg-red-500/10 text-red-700 dark:text-red-400"
                            }`}
                          >
                            {q.source}
                          </span>
                          <a
                            href={q.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-sm font-medium hover:text-primary truncate flex items-center gap-1"
                          >
                            <span className="truncate">{q.title}</span>
                            <ExternalLink className="h-3 w-3 shrink-0 opacity-60" />
                          </a>
                        </div>
                        {q.snippet && (
                          <p className="text-xs text-muted-foreground line-clamp-2">
                            {q.snippet}
                          </p>
                        )}
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
