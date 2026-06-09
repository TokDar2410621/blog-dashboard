import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  Search,
  Loader2,
  Sparkles,
  ExternalLink,
  HelpCircle,
  Video,
  Globe,
  FileText,
  Layers,
  AlertCircle,
} from "lucide-react";
import { toast } from "sonner";

import { serpAnalyze, type SerpAnalyzeResponse } from "@/lib/api-client";
import { usePersistedState } from "@/hooks/usePersistedState";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { PageBreadcrumb } from "@/components/PageBreadcrumb";

type Lang = "fr" | "en" | "es";

export default function SerpAnalyzer() {
  const { siteId } = useParams<{ siteId: string }>();
  const navigate = useNavigate();
  const persistKey = (slot: string) =>
    `gridar:site:${siteId}:serp-analyzer:${slot}`;

  const [keyword, setKeyword] = usePersistedState<string>(
    persistKey("keyword"),
    "",
  );
  const [language, setLanguage] = usePersistedState<Lang>(
    persistKey("language"),
    "fr",
  );
  const [data, setData] = usePersistedState<SerpAnalyzeResponse | null>(
    persistKey("data"),
    null,
  );

  const mutation = useMutation({
    mutationFn: async () => {
      const trimmed = keyword.trim();
      if (!trimmed) {
        throw new Error("Saisis un mot-cle a analyser.");
      }
      if (!siteId) throw new Error("Site introuvable.");
      return serpAnalyze(Number(siteId), {
        keyword: trimmed,
        language,
      });
    },
    onSuccess: (d) => setData(d),
    onError: (err: Error) => toast.error(err.message),
  });

  const handleAnalyze = () => mutation.mutate();
  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") handleAnalyze();
  };

  const handleGenerate = () => {
    if (!data || !siteId) return;
    const params = new URLSearchParams({
      topic: data.keyword,
      autostart: "1",
      serp_analyzed: "true",
      language: data.language,
    });
    navigate(`/dashboard/${siteId}/generer?${params.toString()}`);
  };

  return (
    <div className="space-y-6 max-w-6xl">
      <PageBreadcrumb trail={[{ label: "Analyseur SERP" }]} />

      <div>
        <h1 className="text-2xl font-bold">Analyseur SERP</h1>
        <p className="text-muted-foreground">
          Saisis un mot-cle pour disseder le top 10 Google : longueur d&apos;article,
          structure, signaux (FAQ, video) et benchmarks moyens. Utilise les
          conclusions pour generer un article qui bat le SERP.
        </p>
      </div>

      {/* Search form */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Search className="h-5 w-5 text-primary" />
            Analyser un mot-cle
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col md:flex-row md:items-end gap-3">
            <div className="flex-1 space-y-2">
              <label className="text-sm font-medium">Mot-cle cible</label>
              <Input
                value={keyword}
                onChange={(e) => setKeyword(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="ex: meilleur CRM PME"
                disabled={mutation.isPending}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium">Langue</label>
              <Select
                value={language}
                onValueChange={(v) => setLanguage(v as Lang)}
                disabled={mutation.isPending}
              >
                <SelectTrigger className="w-32">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="fr">Francais</SelectItem>
                  <SelectItem value="en">English</SelectItem>
                  <SelectItem value="es">Espanol</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <Button
              onClick={handleAnalyze}
              disabled={mutation.isPending || !keyword.trim()}
              size="lg"
            >
              {mutation.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Analyse en cours...
                </>
              ) : (
                <>
                  <Search className="h-4 w-4 mr-2" />
                  Analyser
                </>
              )}
            </Button>
          </div>
          {mutation.isPending && (
            <p className="text-xs text-muted-foreground mt-3">
              On interroge Google et on telecharge les 10 pages : ~15-30s.
            </p>
          )}
        </CardContent>
      </Card>

      {/* Loading skeleton */}
      {mutation.isPending && (
        <div className="space-y-3">
          <Skeleton className="h-28 w-full" />
          <Skeleton className="h-40 w-full" />
          <Skeleton className="h-64 w-full" />
        </div>
      )}

      {/* Empty state */}
      {!mutation.isPending && !data && (
        <Card className="border-dashed">
          <CardContent className="py-12 text-center space-y-2">
            <Search className="h-10 w-10 mx-auto text-muted-foreground/50" />
            <p className="font-medium">
              Entre un mot-cle pour analyser son SERP top 10.
            </p>
            <p className="text-sm text-muted-foreground max-w-md mx-auto">
              On va scanner les 10 premiers resultats Google (titres, longueur,
              structure, FAQ, video) et te donner un benchmark concret pour
              ecrire mieux qu&apos;eux.
            </p>
          </CardContent>
        </Card>
      )}

      {/* Results */}
      {data && !mutation.isPending && (
        <>
          {/* Hero strip */}
          <Card className="border-primary/30 bg-primary/5">
            <CardContent className="py-5 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
              <div>
                <div className="text-xs uppercase tracking-wider text-muted-foreground font-mono">
                  Analyse top 10 pour
                </div>
                <div className="text-xl font-semibold mt-1">
                  &laquo;&nbsp;{data.keyword}&nbsp;&raquo;
                  <span className="ml-2 text-xs font-normal text-muted-foreground">
                    ({data.language.toUpperCase()})
                  </span>
                </div>
              </div>
              <Button onClick={handleGenerate} size="lg" className="shrink-0">
                <Sparkles className="h-4 w-4 mr-2" />
                Generer un article qui bat ce SERP
              </Button>
            </CardContent>
          </Card>

          {/* KPIs */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <KpiCard
              icon={<FileText className="h-4 w-4" />}
              label="Mots moyens"
              value={data.averages.word_count_avg.toLocaleString("fr-CA")}
              hint="par page du top 10"
            />
            <KpiCard
              icon={<Layers className="h-4 w-4" />}
              label="Headings moyens"
              value={String(data.averages.headings_avg)}
              hint="h1+h2+h3 par page"
            />
            <KpiCard
              icon={<HelpCircle className="h-4 w-4" />}
              label="Avec FAQ"
              value={`${data.averages.faq_pct}%`}
              hint="schema ou bloc FAQ"
            />
            <KpiCard
              icon={<Video className="h-4 w-4" />}
              label="Avec video"
              value={`${data.averages.video_pct}%`}
              hint="video native ou Youtube"
            />
          </div>

          {/* Correlation chart - words vs position */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">
                Word count par position
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={data.top_10.map((r) => ({
                      position: `#${r.position}`,
                      words: r.word_count ?? 0,
                      headings: r.headings_count ?? 0,
                    }))}
                    margin={{ top: 10, right: 16, left: 0, bottom: 0 }}
                  >
                    <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
                    <XAxis
                      dataKey="position"
                      tick={{ fontSize: 11 }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <YAxis
                      tick={{ fontSize: 11 }}
                      axisLine={false}
                      tickLine={false}
                    />
                    <Tooltip
                      contentStyle={{
                        background: "hsl(var(--card))",
                        border: "1px solid hsl(var(--border))",
                        borderRadius: "0.5rem",
                        fontSize: "12px",
                      }}
                    />
                    <Bar
                      dataKey="words"
                      fill="hsl(var(--primary))"
                      radius={[4, 4, 0, 0]}
                      name="Mots"
                    />
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <p className="text-xs text-muted-foreground mt-2">
                Plus une page est haute, plus elle a generalement de contenu.
                Repere si tes futurs articles doivent depasser{" "}
                <strong>{data.averages.word_count_avg}</strong> mots.
              </p>
            </CardContent>
          </Card>

          {/* Top 10 table */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base flex items-center gap-2">
                <Globe className="h-4 w-4 text-primary" />
                Top 10 SERP detaille
              </CardTitle>
            </CardHeader>
            <CardContent className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead className="w-12">#</TableHead>
                    <TableHead>Domaine + Titre</TableHead>
                    <TableHead className="text-right w-24">Mots</TableHead>
                    <TableHead className="text-right w-24">Headings</TableHead>
                    <TableHead className="w-32">Signaux</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.top_10.map((r) => (
                    <TableRow key={`${r.position}-${r.url}`}>
                      <TableCell className="font-mono text-sm">
                        {r.position}
                      </TableCell>
                      <TableCell className="max-w-md">
                        <div className="font-medium text-sm truncate">
                          {r.title || r.url}
                        </div>
                        <a
                          href={r.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-xs text-muted-foreground hover:text-primary inline-flex items-center gap-1 truncate max-w-full"
                        >
                          {r.domain || r.url}
                          <ExternalLink className="h-3 w-3 shrink-0" />
                        </a>
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {r.fetch_error ? (
                          <AlertCircle className="h-3.5 w-3.5 inline text-amber-500" />
                        ) : (
                          (r.word_count ?? 0).toLocaleString("fr-CA")
                        )}
                      </TableCell>
                      <TableCell className="text-right tabular-nums">
                        {r.fetch_error ? "-" : (r.headings_count ?? 0)}
                      </TableCell>
                      <TableCell>
                        <div className="flex flex-wrap gap-1">
                          {r.has_faq && (
                            <Badge variant="secondary" className="text-[10px]">
                              FAQ
                            </Badge>
                          )}
                          {r.has_video && (
                            <Badge variant="secondary" className="text-[10px]">
                              Video
                            </Badge>
                          )}
                          {r.fetch_error && (
                            <Badge variant="outline" className="text-[10px]">
                              Inaccessible
                            </Badge>
                          )}
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>

          {/* SEO factors table (ton URL vs moyenne top 10) - V1 simplified */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base">
                Facteurs SEO : moyennes du top 10
              </CardTitle>
            </CardHeader>
            <CardContent className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Facteur</TableHead>
                    <TableHead className="text-right">
                      Moyenne top 10
                    </TableHead>
                    <TableHead className="text-right">Recommandation</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  <FactorRow
                    label="Word count"
                    value={data.averages.word_count_avg.toLocaleString("fr-CA")}
                    reco={`Vise ${Math.round(
                      data.averages.word_count_avg * 1.15,
                    ).toLocaleString("fr-CA")} mots (top 10 +15%)`}
                  />
                  <FactorRow
                    label="Headings (h1+h2+h3)"
                    value={String(data.averages.headings_avg)}
                    reco={`Structure en ${Math.max(
                      Math.ceil(data.averages.headings_avg),
                      5,
                    )} sections minimum`}
                  />
                  <FactorRow
                    label="Presence d'un bloc FAQ"
                    value={`${data.averages.faq_pct}%`}
                    reco={
                      data.averages.faq_pct >= 30
                        ? "Ajouter une section FAQ obligatoire"
                        : "Optionnel (peu present dans le SERP)"
                    }
                  />
                  <FactorRow
                    label="Video integree"
                    value={`${data.averages.video_pct}%`}
                    reco={
                      data.averages.video_pct >= 40
                        ? "Ajouter une video (Youtube embed ou demo)"
                        : "Optionnel"
                    }
                  />
                  <FactorRow
                    label="Diversite des domaines"
                    value={`${
                      new Set(data.top_10.map((r) => r.domain).filter(Boolean))
                        .size
                    } / 10`}
                    reco="Plus c'est haut, plus le SERP est ouvert (donc accessible)"
                  />
                  <FactorRow
                    label="Pages inaccessibles (bot bloque)"
                    value={`${data.top_10.filter((r) => r.fetch_error).length}`}
                    reco="Bloque par le bot Gridar : valeurs estimees a partir du snippet"
                  />
                </TableBody>
              </Table>
              <p className="text-xs text-muted-foreground mt-3">
                Note V1 : ce tableau presente les benchmarks SERP. Les facteurs
                propres a ton URL (comparaison cote a cote) arrivent dans une
                prochaine version.
              </p>
            </CardContent>
          </Card>

          {/* Final CTA */}
          <Card className="border-primary/30">
            <CardContent className="py-6 flex flex-col md:flex-row md:items-center md:justify-between gap-4">
              <div>
                <div className="font-semibold">Pret a passer a l&apos;action ?</div>
                <p className="text-sm text-muted-foreground mt-1">
                  Gridar prend ces metriques en entree et genere un article
                  optimise pour battre le top 10.
                </p>
              </div>
              <Button onClick={handleGenerate} size="lg">
                <Sparkles className="h-4 w-4 mr-2" />
                Generer un article qui bat ce SERP
              </Button>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}

function KpiCard({
  icon,
  label,
  value,
  hint,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  hint?: string;
}) {
  return (
    <Card>
      <CardContent className="pt-6">
        <div className="flex items-center justify-between mb-1">
          <span className="text-xs uppercase tracking-wider text-muted-foreground font-mono">
            {label}
          </span>
          <span className="text-muted-foreground">{icon}</span>
        </div>
        <div className="text-3xl font-bold tabular-nums">{value}</div>
        {hint && (
          <div className="text-xs text-muted-foreground mt-1">{hint}</div>
        )}
      </CardContent>
    </Card>
  );
}

function FactorRow({
  label,
  value,
  reco,
}: {
  label: string;
  value: string;
  reco: string;
}) {
  return (
    <TableRow>
      <TableCell className="font-medium">{label}</TableCell>
      <TableCell className="text-right tabular-nums">{value}</TableCell>
      <TableCell className="text-right text-muted-foreground text-sm">
        {reco}
      </TableCell>
    </TableRow>
  );
}
