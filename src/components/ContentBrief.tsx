import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useMutation } from "@tanstack/react-query";
import { authFetch } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Sparkles,
  Loader2,
  ChevronDown,
  ChevronUp,
  Copy,
  Check,
} from "lucide-react";
import { toast } from "sonner";

export type ContentBrief = {
  search_intent: string;
  intent_explanation: string;
  recommended_titles: string[];
  outline: { level: number; text: string }[];
  word_count_target: number;
  faq: { question: string; answer_hint: string }[];
  entities: string[];
  schemas_suggested: string[];
  eeat_signals: string[];
};

export type ContentBriefResult = {
  keyword: string;
  language: string;
  serp_competitors: { rank: number; title: string; url: string; snippet: string }[];
  people_also_ask: string[];
  related_searches: string[];
  brief: ContentBrief;
};

type Props = {
  language: string;
  defaultKeyword?: string;
  onApply?: (data: {
    topic: string;
    title?: string;
    keywords: string;
    brief: ContentBrief;
  }) => void;
};

export function ContentBriefPanel({ language, defaultKeyword = "", onApply }: Props) {
  const { t } = useTranslation();
  const [keyword, setKeyword] = useState(defaultKeyword);
  const [open, setOpen] = useState(false);
  const [data, setData] = useState<ContentBriefResult | null>(null);
  const [copiedTitle, setCopiedTitle] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: async () => {
      const res = await authFetch("/content-brief/", {
        method: "POST",
        body: JSON.stringify({ keyword, language }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error || t("brief.error"));
      }
      return (await res.json()) as ContentBriefResult;
    },
    onSuccess: (d) => {
      setData(d);
      setOpen(true);
    },
    onError: (err: Error) => {
      toast.error(err.message);
    },
  });

  const handleGenerate = () => {
    if (!keyword.trim()) {
      toast.error(t("brief.keywordRequired"));
      return;
    }
    mutation.mutate();
  };

  const copy = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedTitle(text);
    toast.success(t("brief.copied"));
    setTimeout(() => setCopiedTitle(null), 1500);
  };

  const apply = () => {
    if (!data || !onApply) return;
    onApply({
      topic: data.keyword,
      title: data.brief.recommended_titles[0],
      keywords: data.brief.entities.slice(0, 6).join(", "),
      brief: data.brief,
    });
    toast.success(t("brief.applied"));
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg flex items-center gap-2">
          <Sparkles className="h-5 w-5 text-primary" />
          {t("brief.title")}
        </CardTitle>
        <p className="text-sm text-muted-foreground">{t("brief.subtitle")}</p>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label>{t("brief.keyword")}</Label>
          <div className="flex gap-2">
            <Input
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              placeholder={t("brief.keywordPlaceholder")}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleGenerate();
              }}
            />
            <Button onClick={handleGenerate} disabled={mutation.isPending}>
              {mutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <>
                  <Sparkles className="h-4 w-4 mr-2" />
                  {t("brief.generate")}
                </>
              )}
            </Button>
          </div>
        </div>

        {mutation.isPending && (
          <div className="space-y-2">
            <Skeleton className="h-6 w-3/4" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-5/6" />
          </div>
        )}

        {data && !mutation.isPending && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <button
                type="button"
                className="flex items-center gap-2 text-sm font-medium hover:text-primary"
                onClick={() => setOpen((o) => !o)}
              >
                {open ? (
                  <ChevronUp className="h-4 w-4" />
                ) : (
                  <ChevronDown className="h-4 w-4" />
                )}
                {t("brief.briefDetails")}
              </button>
              {onApply && (
                <Button size="sm" variant="default" onClick={apply}>
                  {t("brief.applyToGenerator")}
                </Button>
              )}
            </div>

            {open && (
              <div className="space-y-4 border-t pt-4">
                {/* Search intent */}
                <div>
                  <h4 className="text-xs font-mono uppercase tracking-wide text-muted-foreground mb-1">
                    {t("brief.searchIntent")}
                  </h4>
                  <div className="flex items-center gap-2">
                    <span className="text-xs px-2 py-1 rounded bg-primary/10 text-primary font-mono uppercase">
                      {data.brief.search_intent}
                    </span>
                    <span className="text-sm text-muted-foreground">
                      {data.brief.intent_explanation}
                    </span>
                  </div>
                </div>

                {/* Recommended titles */}
                <div>
                  <h4 className="text-xs font-mono uppercase tracking-wide text-muted-foreground mb-2">
                    {t("brief.recommendedTitles")}
                  </h4>
                  <div className="space-y-2">
                    {data.brief.recommended_titles.map((title) => (
                      <button
                        type="button"
                        key={title}
                        onClick={() => copy(title)}
                        className="w-full text-left px-3 py-2 rounded border hover:border-primary text-sm flex items-center justify-between group"
                      >
                        <span>{title}</span>
                        {copiedTitle === title ? (
                          <Check className="h-3 w-3 text-green-600" />
                        ) : (
                          <Copy className="h-3 w-3 opacity-0 group-hover:opacity-50" />
                        )}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Outline */}
                <div>
                  <h4 className="text-xs font-mono uppercase tracking-wide text-muted-foreground mb-2">
                    {t("brief.outline")}
                  </h4>
                  <ul className="space-y-1 text-sm">
                    {data.brief.outline.map((h, i) => (
                      <li
                        key={i}
                        className={
                          h.level === 3 ? "ml-6 text-muted-foreground" : "font-medium"
                        }
                      >
                        <span className="font-mono text-xs text-primary mr-2">
                          H{h.level}
                        </span>
                        {h.text}
                      </li>
                    ))}
                  </ul>
                </div>

                {/* Word count */}
                <div>
                  <h4 className="text-xs font-mono uppercase tracking-wide text-muted-foreground mb-1">
                    {t("brief.wordCountTarget")}
                  </h4>
                  <span className="text-2xl font-bold">{data.brief.word_count_target}</span>
                  <span className="text-sm text-muted-foreground ml-2">
                    {t("brief.words")}
                  </span>
                </div>

                {/* FAQ */}
                {data.brief.faq.length > 0 && (
                  <div>
                    <h4 className="text-xs font-mono uppercase tracking-wide text-muted-foreground mb-2">
                      {t("brief.faq")}
                    </h4>
                    <div className="space-y-2">
                      {data.brief.faq.map((f, i) => (
                        <details
                          key={i}
                          className="text-sm rounded border p-3 [&_summary::-webkit-details-marker]:hidden"
                        >
                          <summary className="cursor-pointer font-medium flex items-center justify-between">
                            <span>{f.question}</span>
                            <ChevronDown className="h-4 w-4 text-muted-foreground shrink-0" />
                          </summary>
                          <p className="mt-2 text-muted-foreground">{f.answer_hint}</p>
                        </details>
                      ))}
                    </div>
                  </div>
                )}

                {/* Entities */}
                {data.brief.entities.length > 0 && (
                  <div>
                    <h4 className="text-xs font-mono uppercase tracking-wide text-muted-foreground mb-2">
                      {t("brief.entities")}
                    </h4>
                    <div className="flex flex-wrap gap-2">
                      {data.brief.entities.map((e) => (
                        <span
                          key={e}
                          className="text-xs px-2 py-1 rounded bg-muted text-foreground/80"
                        >
                          {e}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Schemas */}
                {data.brief.schemas_suggested.length > 0 && (
                  <div>
                    <h4 className="text-xs font-mono uppercase tracking-wide text-muted-foreground mb-2">
                      {t("brief.schemas")}
                    </h4>
                    <div className="flex flex-wrap gap-2">
                      {data.brief.schemas_suggested.map((s) => (
                        <span
                          key={s}
                          className="text-xs px-2 py-1 rounded border border-primary/40 text-primary font-mono"
                        >
                          {s}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* EEAT */}
                {data.brief.eeat_signals.length > 0 && (
                  <div>
                    <h4 className="text-xs font-mono uppercase tracking-wide text-muted-foreground mb-2">
                      {t("brief.eeat")}
                    </h4>
                    <ul className="space-y-1 text-sm">
                      {data.brief.eeat_signals.map((s, i) => (
                        <li key={i} className="flex items-start gap-2">
                          <Check className="h-4 w-4 text-green-600 shrink-0 mt-0.5" />
                          <span>{s}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Competitors quick view */}
                {data.serp_competitors.length > 0 && (
                  <div>
                    <h4 className="text-xs font-mono uppercase tracking-wide text-muted-foreground mb-2">
                      {t("brief.competitors")} ({data.serp_competitors.length})
                    </h4>
                    <ol className="space-y-1 text-xs text-muted-foreground">
                      {data.serp_competitors.slice(0, 5).map((c) => (
                        <li key={c.rank} className="truncate">
                          {c.rank}. {c.title}
                        </li>
                      ))}
                    </ol>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
