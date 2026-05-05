import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useMutation } from "@tanstack/react-query";
import { authFetch } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { HelpCircle, Loader2, Copy, Check, Code } from "lucide-react";
import { toast } from "sonner";

type PAAQuestion = { question: string; snippet: string; answer: string };
type PAAResult = {
  keyword: string;
  language: string;
  questions: PAAQuestion[];
  faq_schema: Record<string, unknown> | null;
};

type Props = {
  language: string;
  defaultKeyword?: string;
  onInsertSchema?: (jsonLd: string) => void;
};

export function PAAPanel({ language, defaultKeyword = "", onInsertSchema }: Props) {
  const { t } = useTranslation();
  const [keyword, setKeyword] = useState(defaultKeyword);
  const [data, setData] = useState<PAAResult | null>(null);
  const [copied, setCopied] = useState(false);

  const mutation = useMutation({
    mutationFn: async () => {
      const res = await authFetch("/paa/", {
        method: "POST",
        body: JSON.stringify({ keyword, language, generate_answers: true }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error || t("paa.error"));
      }
      return (await res.json()) as PAAResult;
    },
    onSuccess: (d) => setData(d),
    onError: (err: Error) => toast.error(err.message),
  });

  const handleGenerate = () => {
    if (!keyword.trim()) {
      toast.error(t("paa.keywordRequired"));
      return;
    }
    mutation.mutate();
  };

  const copySchema = () => {
    if (!data?.faq_schema) return;
    const json = JSON.stringify(data.faq_schema, null, 2);
    const tag = `<script type="application/ld+json">\n${json}\n</script>`;
    navigator.clipboard.writeText(tag);
    setCopied(true);
    toast.success(t("paa.schemaCopied"));
    setTimeout(() => setCopied(false), 1500);
  };

  const insertSchema = () => {
    if (!data?.faq_schema || !onInsertSchema) return;
    const json = JSON.stringify(data.faq_schema, null, 2);
    const tag = `<script type="application/ld+json">\n${json}\n</script>`;
    onInsertSchema(tag);
    toast.success(t("paa.schemaInserted"));
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg flex items-center gap-2">
          <HelpCircle className="h-5 w-5 text-primary" />
          {t("paa.title")}
        </CardTitle>
        <p className="text-sm text-muted-foreground">{t("paa.subtitle")}</p>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-2">
          <Label>{t("paa.keyword")}</Label>
          <div className="flex gap-2">
            <Input
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              placeholder={t("paa.keywordPlaceholder")}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleGenerate();
              }}
            />
            <Button onClick={handleGenerate} disabled={mutation.isPending}>
              {mutation.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <>
                  <HelpCircle className="h-4 w-4 mr-2" />
                  {t("paa.fetch")}
                </>
              )}
            </Button>
          </div>
        </div>

        {mutation.isPending && (
          <div className="space-y-2">
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
          </div>
        )}

        {data && !mutation.isPending && (
          <div className="space-y-4">
            {data.questions.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-4">
                {t("paa.noQuestions")}
              </p>
            ) : (
              <>
                <div className="space-y-2">
                  {data.questions.map((q, i) => (
                    <details
                      key={i}
                      className="rounded border p-3 [&_summary::-webkit-details-marker]:hidden"
                    >
                      <summary className="cursor-pointer font-medium text-sm flex items-center justify-between">
                        <span>{q.question}</span>
                      </summary>
                      {q.answer && (
                        <p className="mt-2 text-sm text-muted-foreground">
                          {q.answer}
                        </p>
                      )}
                    </details>
                  ))}
                </div>

                {data.faq_schema && (
                  <div className="border-t pt-4 space-y-2">
                    <div className="flex items-center justify-between">
                      <h4 className="text-xs font-mono uppercase tracking-wide text-muted-foreground">
                        {t("paa.faqSchema")}
                      </h4>
                      <div className="flex gap-2">
                        <Button size="sm" variant="outline" onClick={copySchema}>
                          {copied ? (
                            <Check className="h-3 w-3 mr-1 text-green-600" />
                          ) : (
                            <Copy className="h-3 w-3 mr-1" />
                          )}
                          {t("paa.copySchema")}
                        </Button>
                        {onInsertSchema && (
                          <Button size="sm" onClick={insertSchema}>
                            <Code className="h-3 w-3 mr-1" />
                            {t("paa.insertSchema")}
                          </Button>
                        )}
                      </div>
                    </div>
                    <pre className="text-[10px] bg-muted/50 rounded p-3 overflow-x-auto max-h-48 font-mono">
                      {JSON.stringify(data.faq_schema, null, 2)}
                    </pre>
                  </div>
                )}
              </>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
