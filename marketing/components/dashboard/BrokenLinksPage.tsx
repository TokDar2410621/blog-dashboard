"use client";

import { useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { authFetch } from "@/lib/api-client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Unlink2,
  Loader2,
  ExternalLink,
  CheckCircle2,
  AlertCircle,
} from "lucide-react";
import { toast } from "sonner";

type BrokenLink = {
  url: string;
  status_code: number | null;
  error: string;
  articles: { slug: string; title: string }[];
  article_count: number;
};

type BrokenResult = {
  site_id: number;
  checked_count: number;
  broken_count: number;
  broken_links: BrokenLink[];
  note?: string;
};

export default function BrokenLinksPage() {
  const params = useParams<{ siteId: string }>();
  const siteId = params?.siteId;
  const [language, setLanguage] = useState<string>("");
  const [data, setData] = useState<BrokenResult | null>(null);
  const base = `/dashboard/${siteId}`;

  const mutation = useMutation({
    mutationFn: async () => {
      const res = await authFetch(`/sites/${siteId}/broken-links/`, {
        method: "POST",
        body: JSON.stringify({
          limit: 100,
          ...(language ? { language } : {}),
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error || "Erreur lors du scan");
      }
      return (await res.json()) as BrokenResult;
    },
    onSuccess: (d) => setData(d),
    onError: (err: Error) => toast.error(err.message),
  });

  const formatStatus = (link: BrokenLink) => {
    if (link.error) {
      return link.error === "timeout"
        ? "TIMEOUT"
        : link.error === "connection_error"
        ? "CONN ERR"
        : link.error.toUpperCase().slice(0, 12);
    }
    return link.status_code ? `${link.status_code}` : "?";
  };

  const statusColor = (link: BrokenLink) => {
    if (link.error) return "bg-red-500/10 text-red-700 dark:text-red-400";
    const code = link.status_code || 0;
    if (code >= 500) return "bg-red-500/10 text-red-700 dark:text-red-400";
    if (code >= 400) return "bg-amber-500/10 text-amber-700 dark:text-amber-400";
    return "bg-muted";
  };

  return (
    <div className="space-y-6 max-w-5xl">
      <div>
        <h1 className="text-2xl font-bold">Détecteur de liens cassés</h1>
        <p className="text-muted-foreground">
          Scanne les liens externes HTTP(S) de tes articles publiés et signale
          ceux qui sont morts (4xx/5xx, timeout, connexion). Cache 24h par URL.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Unlink2 className="h-5 w-5 text-amber-600" />
            Scanner les liens
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap items-end gap-3">
            <div className="space-y-2">
              <label className="text-sm font-medium">Langue</label>
              <Select
                value={language || "all"}
                onValueChange={(v) => setLanguage(v === "all" ? "" : v)}
              >
                <SelectTrigger className="w-32">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Toutes</SelectItem>
                  <SelectItem value="fr">FR</SelectItem>
                  <SelectItem value="en">EN</SelectItem>
                  <SelectItem value="es">ES</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <Button
              onClick={() => mutation.mutate()}
              disabled={mutation.isPending}
              size="lg"
            >
              {mutation.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Scan en cours...
                </>
              ) : (
                <>
                  <Unlink2 className="h-4 w-4 mr-2" />
                  Scanner
                </>
              )}
            </Button>
          </div>
          {mutation.isPending && (
            <p className="text-xs text-muted-foreground mt-3">
              HEAD request sur chaque URL unique. Compte 30s à 2 min selon le
              nombre de liens.
            </p>
          )}
        </CardContent>
      </Card>

      {mutation.isPending && (
        <div className="space-y-3">
          <Skeleton className="h-32 w-full" />
          <Skeleton className="h-48 w-full" />
        </div>
      )}

      {data && !mutation.isPending && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Card>
              <CardContent className="pt-6">
                <div className="text-3xl font-bold">{data.checked_count}</div>
                <div className="text-xs text-muted-foreground mt-1">
                  Liens uniques vérifiés
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div
                  className={`text-3xl font-bold flex items-center gap-2 ${
                    data.broken_count === 0 ? "text-green-600" : "text-red-600"
                  }`}
                >
                  {data.broken_count === 0 ? (
                    <CheckCircle2 className="h-6 w-6" />
                  ) : (
                    <AlertCircle className="h-6 w-6" />
                  )}
                  {data.broken_count}
                </div>
                <div className="text-xs text-muted-foreground mt-1">
                  Cassés
                </div>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-3xl font-bold text-green-600">
                  {data.checked_count - data.broken_count}
                </div>
                <div className="text-xs text-muted-foreground mt-1">
                  OK
                </div>
              </CardContent>
            </Card>
          </div>

          {data.note && (
            <Card>
              <CardContent className="py-4 text-sm text-muted-foreground text-center">
                {data.note}
              </CardContent>
            </Card>
          )}

          {data.broken_count === 0 && data.checked_count > 0 && (
            <Card>
              <CardContent className="py-12 text-center">
                <CheckCircle2 className="h-10 w-10 mx-auto mb-3 text-green-600" />
                <p className="text-sm">
                  Aucun lien cassé détecté. Tous tes liens externes sont vivants.
                </p>
              </CardContent>
            </Card>
          )}

          {data.broken_links.length > 0 && (
            <div className="space-y-3">
              {data.broken_links.map((link, idx) => (
                <Card key={idx}>
                  <CardContent className="py-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-2">
                          <span
                            className={`text-xs font-mono px-2 py-1 rounded ${statusColor(link)}`}
                          >
                            {formatStatus(link)}
                          </span>
                          <a
                            href={link.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-sm hover:text-primary truncate flex-1 min-w-0 flex items-center gap-1"
                            title={link.url}
                          >
                            <span className="truncate">{link.url}</span>
                            <ExternalLink className="h-3 w-3 shrink-0" />
                          </a>
                        </div>
                        <div className="text-xs text-muted-foreground">
                          {`Trouvé dans ${link.article_count} article${
                            link.article_count > 1 ? "s" : ""
                          }`}{" "}
                          :
                        </div>
                        <ul className="text-sm mt-1 space-y-0.5 ml-2">
                          {link.articles.slice(0, 5).map((a) => (
                            <li key={a.slug}>
                              <Link
                                href={`${base}/articles/${a.slug}`}
                                className="hover:text-primary text-xs"
                              >
                                → {a.title}
                              </Link>
                            </li>
                          ))}
                          {link.article_count > 5 && (
                            <li className="text-xs text-muted-foreground">
                              et {link.article_count - 5} de plus
                            </li>
                          )}
                        </ul>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </>
      )}

      {!data && !mutation.isPending && (
        <Card>
          <CardContent className="py-12 text-center text-muted-foreground">
            <Unlink2 className="h-10 w-10 mx-auto mb-3 opacity-30" />
            <p>
              Lance un scan pour détecter les liens externes morts dans tes
              articles.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
