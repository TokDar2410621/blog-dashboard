import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useMutation } from "@tanstack/react-query";
import { authFetch } from "@/lib/api-client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  ShieldCheck,
  AlertTriangle,
  ExternalLink,
  Loader2,
  Bot,
  FileSearch,
} from "lucide-react";
import { toast } from "sonner";

type PlagiarismResult = {
  ai_score: number;
  plagiarism_score: number;
  verdict: string;
  sources_matched: { url: string; percent: number; snippet: string }[];
};

export function PlagiarismCard({
  title,
  content,
  language,
}: {
  title: string;
  content: string;
  language: string;
}) {
  const { t } = useTranslation();
  const [data, setData] = useState<PlagiarismResult | null>(null);
  const [errorCode, setErrorCode] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: async () => {
      setErrorCode(null);
      const res = await authFetch("/plagiarism-check/", {
        method: "POST",
        body: JSON.stringify({ title, content, language }),
      });
      const json = await res.json();
      if (!res.ok) {
        if (json.code) setErrorCode(json.code);
        throw new Error(json.error || "Erreur analyse");
      }
      return json as PlagiarismResult;
    },
    onSuccess: (d) => setData(d),
    onError: (err: Error) => toast.error(err.message),
  });

  if (!content || content.length < 50) return null;

  const aiColor =
    !data
      ? "text-muted-foreground"
      : data.ai_score >= 80
      ? "text-red-600"
      : data.ai_score >= 50
      ? "text-amber-600"
      : "text-green-600";

  const plagColor =
    !data
      ? "text-muted-foreground"
      : data.plagiarism_score >= 30
      ? "text-red-600"
      : data.plagiarism_score >= 15
      ? "text-amber-600"
      : "text-green-600";

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg flex items-center gap-2">
          <ShieldCheck className="h-5 w-5 text-primary" />
          {t("plagiarism.title", "Originalité + Détection IA")}
        </CardTitle>
        <p className="text-xs text-muted-foreground">
          {t(
            "plagiarism.subtitle",
            "Vérifie si Google peut détecter ton article comme IA, et s'il existe déjà ailleurs sur le web."
          )}
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        {!data && !mutation.isPending && (
          <Button
            onClick={() => mutation.mutate()}
            disabled={mutation.isPending}
            variant="outline"
          >
            <FileSearch className="h-4 w-4 mr-2" />
            {t("plagiarism.run", "Analyser")}
          </Button>
        )}

        {mutation.isPending && <Skeleton className="h-32" />}

        {errorCode === "plagiarism_not_configured" && (
          <div className="rounded border border-amber-500/30 bg-amber-500/5 p-3 text-sm flex items-start gap-2">
            <AlertTriangle className="h-4 w-4 text-amber-600 shrink-0 mt-0.5" />
            <div>
              <strong>Module non configuré.</strong>
              <p className="text-xs mt-1 text-muted-foreground">
                Pour activer la détection IA + plagiat, configure{" "}
                <code className="px-1 rounded bg-muted">ORIGINALITY_API_KEY</code>{" "}
                sur Railway. Compte gratuit + ~0,01$/article sur{" "}
                <a
                  href="https://originality.ai"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-primary hover:underline"
                >
                  originality.ai
                </a>
                .
              </p>
            </div>
          </div>
        )}

        {data && !mutation.isPending && (
          <>
            <div className="grid grid-cols-2 gap-3">
              <div className="border rounded p-3">
                <div className="flex items-center gap-2 text-xs text-muted-foreground mb-1">
                  <Bot className="h-3 w-3" />
                  {t("plagiarism.aiScore", "Détection IA")}
                </div>
                <div className={`text-3xl font-bold ${aiColor}`}>
                  {data.ai_score}%
                </div>
                <div className="h-1.5 w-full bg-muted rounded mt-2 overflow-hidden">
                  <div
                    className={`h-full ${
                      data.ai_score >= 80
                        ? "bg-red-500"
                        : data.ai_score >= 50
                        ? "bg-amber-500"
                        : "bg-green-500"
                    }`}
                    style={{ width: `${Math.min(100, data.ai_score)}%` }}
                  />
                </div>
              </div>
              <div className="border rounded p-3">
                <div className="flex items-center gap-2 text-xs text-muted-foreground mb-1">
                  <FileSearch className="h-3 w-3" />
                  {t("plagiarism.plagScore", "Plagiat")}
                </div>
                <div className={`text-3xl font-bold ${plagColor}`}>
                  {data.plagiarism_score}%
                </div>
                <div className="h-1.5 w-full bg-muted rounded mt-2 overflow-hidden">
                  <div
                    className={`h-full ${
                      data.plagiarism_score >= 30
                        ? "bg-red-500"
                        : data.plagiarism_score >= 15
                        ? "bg-amber-500"
                        : "bg-green-500"
                    }`}
                    style={{
                      width: `${Math.min(100, data.plagiarism_score)}%`,
                    }}
                  />
                </div>
              </div>
            </div>

            {data.verdict && (
              <p className="text-sm border-l-4 border-primary/30 pl-3 py-1 bg-muted/30 rounded">
                {data.verdict}
              </p>
            )}

            {data.sources_matched.length > 0 && (
              <div>
                <h4 className="text-xs font-mono uppercase tracking-wide text-muted-foreground mb-2">
                  Sources matchées ({data.sources_matched.length})
                </h4>
                <ul className="space-y-2 text-xs">
                  {data.sources_matched.map((s, i) => (
                    <li key={i} className="flex items-start gap-2 border rounded p-2">
                      <span className="font-mono text-amber-600 shrink-0">
                        {s.percent}%
                      </span>
                      <div className="flex-1 min-w-0">
                        <a
                          href={s.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-primary hover:underline truncate block flex items-center gap-1"
                        >
                          {s.url}
                          <ExternalLink className="h-3 w-3 shrink-0" />
                        </a>
                        {s.snippet && (
                          <p className="text-muted-foreground mt-1">{s.snippet}</p>
                        )}
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            <Button
              variant="ghost"
              size="sm"
              onClick={() => mutation.mutate()}
              disabled={mutation.isPending}
            >
              {mutation.isPending ? (
                <Loader2 className="h-3 w-3 mr-2 animate-spin" />
              ) : (
                <FileSearch className="h-3 w-3 mr-2" />
              )}
              Re-analyser
            </Button>
          </>
        )}
      </CardContent>
    </Card>
  );
}
