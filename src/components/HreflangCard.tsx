import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { authFetch } from "@/lib/api-client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Languages, AlertTriangle, CheckCircle2 } from "lucide-react";

type IncompleteGroup = {
  translation_group: string;
  languages_present: string[];
  missing_languages: string[];
  sample_title: string;
  sample_slug: string;
};

type Orphan = {
  slug: string;
  language: string;
  title: string;
  translation_group: string;
};

type HreflangSiteResult = {
  mode: "site";
  site_id: number;
  expected_languages: string[];
  total_groups: number;
  groups_complete: number;
  groups_incomplete: IncompleteGroup[];
  single_lang_orphans: Orphan[];
  orphan_count: number;
};

export function HreflangCard({ siteId }: { siteId: string }) {
  const { t } = useTranslation();
  const base = `/dashboard/${siteId}`;

  const { data, isLoading, isError } = useQuery<HreflangSiteResult>({
    queryKey: ["hreflang-check", siteId],
    queryFn: async () => {
      const res = await authFetch("/hreflang-check/", {
        method: "POST",
        body: JSON.stringify({ site_id: Number(siteId) }),
      });
      if (!res.ok) throw new Error("hreflang fetch failed");
      return res.json();
    },
    staleTime: 5 * 60 * 1000,
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg flex items-center gap-2">
          <Languages className="h-5 w-5 text-primary" />
          {t("hreflang.title")}
        </CardTitle>
        <p className="text-sm text-muted-foreground">{t("hreflang.subtitle")}</p>
      </CardHeader>
      <CardContent className="space-y-4">
        {isLoading && (
          <div className="space-y-2">
            <Skeleton className="h-6 w-full" />
            <Skeleton className="h-12 w-full" />
          </div>
        )}

        {isError && (
          <p className="text-sm text-muted-foreground">{t("hreflang.error")}</p>
        )}

        {data && (
          <>
            <div className="grid grid-cols-3 gap-3 text-center">
              <div className="rounded border p-3">
                <div className="text-2xl font-bold">{data.total_groups}</div>
                <div className="text-xs text-muted-foreground">
                  {t("hreflang.totalGroups")}
                </div>
              </div>
              <div className="rounded border p-3">
                <div className="text-2xl font-bold text-green-600 flex items-center justify-center gap-1">
                  <CheckCircle2 className="h-5 w-5" />
                  {data.groups_complete}
                </div>
                <div className="text-xs text-muted-foreground">
                  {t("hreflang.complete")}
                </div>
              </div>
              <div className="rounded border p-3">
                <div className="text-2xl font-bold text-amber-600 flex items-center justify-center gap-1">
                  <AlertTriangle className="h-5 w-5" />
                  {data.groups_incomplete.length}
                </div>
                <div className="text-xs text-muted-foreground">
                  {t("hreflang.incomplete")}
                </div>
              </div>
            </div>

            <div className="text-xs text-muted-foreground">
              {t("hreflang.expectedLanguages")} :{" "}
              <span className="font-mono">
                {data.expected_languages.map((l) => l.toUpperCase()).join(", ")}
              </span>
            </div>

            {data.groups_incomplete.length > 0 && (
              <div className="space-y-2">
                <h4 className="text-xs font-mono uppercase tracking-wide text-muted-foreground">
                  {t("hreflang.incompleteGroupsTitle")}
                </h4>
                <ul className="space-y-2 max-h-64 overflow-y-auto">
                  {data.groups_incomplete.slice(0, 20).map((g) => (
                    <li
                      key={g.translation_group}
                      className="border rounded p-2 text-sm flex items-center justify-between gap-2"
                    >
                      <Link
                        to={`${base}/articles/${g.sample_slug}`}
                        className="truncate hover:text-primary flex-1"
                      >
                        {g.sample_title || g.sample_slug}
                      </Link>
                      <div className="flex items-center gap-1 shrink-0">
                        {g.languages_present.map((l) => (
                          <span
                            key={l}
                            className="text-[10px] px-1.5 py-0.5 rounded bg-primary/10 text-primary font-mono uppercase"
                          >
                            {l}
                          </span>
                        ))}
                        {g.missing_languages.map((l) => (
                          <span
                            key={l}
                            className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-700 dark:text-amber-400 font-mono uppercase"
                            title={t("hreflang.missing")}
                          >
                            +{l}
                          </span>
                        ))}
                      </div>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {data.orphan_count > 0 && (
              <div className="text-xs text-muted-foreground border-t pt-3">
                {t("hreflang.orphans", { count: data.orphan_count })}
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}
