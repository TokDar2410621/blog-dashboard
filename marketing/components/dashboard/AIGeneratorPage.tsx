"use client";

import { useState, useEffect, useRef } from "react";
import { usePersistedState } from "@/hooks/usePersistedState";
import { useJobs } from "@/context/JobsContext";
import { useRouter, useParams, useSearchParams } from "next/navigation";
import { aiTemplates } from "@/lib/templates";
import { useGenerateArticle, useSites } from "@/hooks/useDashboard";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { PenLine, Lightbulb, FileText, Loader2, Pencil, RefreshCw, AlertTriangle, Coins } from "lucide-react";
import { toast } from "sonner";
import { ContentBriefPanel, type ContentBrief } from "@/components/dashboard/ContentBrief";
import { PAAPanel } from "@/components/dashboard/PAAPanel";
import { CommunityQuestionsPanel } from "@/components/dashboard/CommunityQuestionsPanel";
import { SearchTrendsPanel } from "@/components/SearchTrendsPanel";
import { QuotaBanner } from "@/components/dashboard/QuotaBanner";
import { useQuery, useMutation } from "@tanstack/react-query";
import { authFetch, ApiError } from "@/lib/api-client";
import { PageBreadcrumb } from "@/components/PageBreadcrumb";

export function AIGeneratorPage() {
  const router = useRouter();
  const params = useParams<{ siteId: string }>();
  const siteId = params?.siteId;
  const searchParams = useSearchParams();
  const base = `/dashboard/${siteId}`;
  const generateArticle = useGenerateArticle();
  const { data: sites = [] } = useSites();
  const currentSite = sites.find((s: { id: number }) => s.id === Number(siteId));
  const ALL_LANGUAGES: { code: string; label: string }[] = [
    { code: "fr", label: "Français" },
    { code: "en", label: "English" },
    { code: "es", label: "Español" },
  ];
  const allowedLanguages =
    currentSite?.available_languages && currentSite.available_languages.length > 0
      ? ALL_LANGUAGES.filter((l) => currentSite.available_languages!.includes(l.code))
      : ALL_LANGUAGES;

  // Persisted across navigations so the user doesn't lose form values or
  // the previous generation result when they leave and come back. Scoped by
  // siteId so switching sites doesn't show another site's form.
  const persistKey = (slot: string) => `gridar:site:${siteId}:ai-generator:${slot}`;
  const [topic, setTopic] = usePersistedState<string>(persistKey("topic"), "");
  const [title, setTitle] = usePersistedState<string>(persistKey("title"), "");
  const [searchMethod, setSearchMethod] = usePersistedState<string>(persistKey("searchMethod"), "serper");
  const [articleType, setArticleType] = usePersistedState<string>(persistKey("articleType"), "news");
  const [length, setLength] = usePersistedState<string>(persistKey("length"), "medium");
  const [language, setLanguage] = usePersistedState<string>(persistKey("language"), "fr");
  const [keywords, setKeywords] = usePersistedState<string>(persistKey("keywords"), "");
  const [dryRun, setDryRun] = usePersistedState<boolean>(persistKey("dryRun"), false);
  // activeBrief is transient (per-session UI state), don't persist
  const [activeBrief, setActiveBrief] = useState<ContentBrief | null>(null);

  // Template + title pre-fill from query params
  useEffect(() => {
    const tplId = searchParams?.get("tpl_id");
    if (tplId) {
      const tpl = aiTemplates.find((t) => t.id === tplId);
      if (tpl) {
        setArticleType(tpl.params.type);
        setLength(tpl.params.length);
        setSearchMethod(tpl.params.search);
      }
    }
    const presetTitle = searchParams?.get("title");
    if (presetTitle) setTitle(presetTitle);
    const presetTopic = searchParams?.get("topic");
    if (presetTopic) setTopic(presetTopic);
    const presetKeywords = searchParams?.get("keywords");
    if (presetKeywords) setKeywords(presetKeywords);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  // Autostart: when arriving from Topic Clusters or any other "one-click
  // generation" surface with ?autostart=1, fire handleGenerate() once the
  // preset values have landed in state. Guarded by a ref so it can only
  // fire ONCE per mount even if state updates re-trigger the effect.
  const autoStartedRef = useRef(false);
  useEffect(() => {
    if (autoStartedRef.current) return;
    if (searchParams?.get("autostart") !== "1") return;
    // Wait for at least one preset to be in state so we don't fire on a
    // blank form (state setters from the previous effect run synchronously
    // in React's batch, so title/topic will be set by the time this runs).
    if (!title && !topic) return;
    autoStartedRef.current = true;
    // Defer to next tick so React has finished flushing all state setters.
    const t = setTimeout(() => handleGenerate(), 50);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams, title, topic]);

  const [result, setResult] = usePersistedState<{
    output: string;
    post_count: number;
  } | null>(persistKey("result"), null);

  // Pre-flight: read user's plan + quota usage + credits to gate the button
  type SubInfo = {
    plan: string;
    limits: { articles_per_month: number | null };
    usage?: { articles_this_month: number };
    credits?: { balance: number };
  };
  const { data: subInfo } = useQuery<SubInfo>({
    queryKey: ["billing-me"],
    queryFn: async () => {
      const res = await authFetch("/billing/me/");
      if (!res.ok) throw new Error("billing fetch failed");
      return res.json();
    },
    staleTime: 30_000,
  });
  const articleLimit = subInfo?.limits.articles_per_month ?? null;
  const articleUsed = subInfo?.usage?.articles_this_month ?? 0;
  const credits = subInfo?.credits?.balance ?? 0;
  const quotaExhausted =
    articleLimit !== null && articleUsed >= articleLimit && credits === 0;
  // dry_run skips quota consumption, so don't gate it
  const cannotGenerate = !dryRun && quotaExhausted;

  // Delivery gate: if there's no way for generated content to reach the live
  // site, generating is a dead end (the "black hole"). Block it honestly.
  const deliveryStatus = currentSite?.delivery_status;
  const deliveryBlocked = deliveryStatus?.status === "blocked";

  // Inline error state when generation hits 402 quota_exceeded
  const [quotaError, setQuotaError] = useState<string | null>(null);

  const buyCredits = useMutation({
    mutationFn: async (pack: "small" | "medium" | "large") => {
      const res = await authFetch("/billing/credits/buy/", {
        method: "POST",
        body: JSON.stringify({ pack }),
      });
      const data = await res.json();
      if (!res.ok || !data.url) throw new Error(data.error || "Erreur achat");
      return data.url as string;
    },
    onSuccess: (url) => {
      window.location.href = url;
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const jobs = useJobs();

  const handleGenerate = async () => {
    setQuotaError(null);
    const params: Record<string, unknown> = {
      search: searchMethod,
      type: articleType,
      length,
      language,
      dry_run: dryRun,
    };
    if (topic) params.topic = topic;
    if (title) params.title = title;
    if (keywords) params.keywords = keywords;
    if (activeBrief) params.brief = activeBrief;

    // Register the generation as a global background job so the user can
    // navigate to other tool pages while it runs. The promise lives in the
    // JobsProvider (dashboard layout), so component unmount doesn't lose it.
    // When the job finishes, the dock shows it as 'done' and clicking takes
    // the user back here (where the persisted result is shown).
    const labelParts = [title, topic].filter(Boolean);
    const label = labelParts[0] || "Generation article";
    jobs.start({
      kind: "article-generation",
      label,
      siteId,
      targetUrl: `/dashboard/${siteId}/generer`,
      run: async () => {
        try {
          const data = await generateArticle.mutateAsync(params);
          setResult(data);
          toast.success(
            dryRun ? "Aperçu généré!" : "Article généré et publié!"
          );
          return data;
        } catch (err) {
          if (
            err instanceof ApiError &&
            err.status === 402 &&
            err.body?.quota_exceeded
          ) {
            setQuotaError(err.message);
            // Re-throw so the job is marked as 'error' with the proper message.
            throw err;
          }
          const msg = err instanceof Error ? err.message : "";
          toast.error(msg || "Erreur lors de la génération");
          throw err;
        }
      },
    });

    toast.info("Generation lancee. Tu peux naviguer ailleurs - le dock en bas a droite suit l'avancement.");
  };

  return (
    <div className="space-y-6 max-w-4xl">
      <PageBreadcrumb trail={[{ label: "Generer" }]} />
      <div>
        <h1 className="text-2xl font-bold">Générer un article</h1>
        <p className="text-muted-foreground">
          Utilisez l&apos;IA pour générer automatiquement un article de blog
        </p>
      </div>

      <QuotaBanner />

      {/* Delivery gate: honest about whether generated content can reach the site */}
      {deliveryStatus && deliveryStatus.status !== "ready" && (
        <div
          className={`rounded-lg border p-4 ${
            deliveryBlocked
              ? "border-destructive/40 bg-destructive/5"
              : "border-amber-500/40 bg-amber-500/5"
          }`}
        >
          <div className="flex items-start gap-3">
            <AlertTriangle
              className={`h-5 w-5 shrink-0 mt-0.5 ${
                deliveryBlocked ? "text-destructive" : "text-amber-600"
              }`}
            />
            <div className="space-y-1.5 min-w-0">
              <p className="font-medium text-sm">
                {deliveryBlocked
                  ? "Aucun chemin de livraison"
                  : "Livraison non confirmée"}
              </p>
              <p className="text-sm text-muted-foreground">
                {deliveryStatus.blocker}
              </p>
              {deliveryBlocked && (
                <Button
                  size="sm"
                  variant="outline"
                  className="mt-2"
                  onClick={() => router.push(`${base}/parametres/integrations`)}
                >
                  Configurer la livraison
                </Button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Content Brief - pre-writing brief (optional, fills the form when applied) */}
      <ContentBriefPanel
        language={language}
        defaultKeyword={keywords.split(",")[0]?.trim() || topic}
        onApply={({ topic: t2, title: ti2, keywords: kw2, brief }) => {
          if (t2) setTopic(t2);
          if (ti2) setTitle(ti2);
          if (kw2) setKeywords(kw2);
          setActiveBrief(brief);
        }}
      />

      {/* PAA harvester - questions + FAQ schema */}
      <PAAPanel
        language={language}
        defaultKeyword={keywords.split(",")[0]?.trim() || topic}
      />

      {/* Reddit / Quora community questions */}
      <CommunityQuestionsPanel
        language={language}
        defaultKeyword={keywords.split(",")[0]?.trim() || topic}
      />

      {/* Google Trends - interest over time + related/rising queries */}
      <SearchTrendsPanel
        language={language}
        defaultKeyword={keywords.split(",")[0]?.trim() || topic}
      />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Form */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Paramètres</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label>Sujet (optionnel)</Label>
              <Input
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                placeholder="Ex: Les tendances IA en 2026"
              />
              <p className="text-xs text-muted-foreground">
                Laissez vide pour un sujet auto-sélectionné
              </p>
            </div>

            <div className="space-y-2">
              <Label>Titre forcé (optionnel)</Label>
              <Input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Ex: Mon titre exact"
              />
            </div>

            <div className="space-y-2">
              <Label>Méthode de recherche</Label>
              <Select value={searchMethod} onValueChange={setSearchMethod}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="serper">Serper</SelectItem>
                  <SelectItem value="gemini">Gemini</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label>Type d&apos;article</Label>
              <Select value={articleType} onValueChange={setArticleType}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="news">Actualité / Opinion</SelectItem>
                  <SelectItem value="tutorial">Tutoriel</SelectItem>
                  <SelectItem value="comparison">Comparaison</SelectItem>
                  <SelectItem value="guide">Guide</SelectItem>
                  <SelectItem value="review">Review</SelectItem>
                  <SelectItem value="story">Récit personnel</SelectItem>
                  <SelectItem value="local">Annuaire local</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label>Longueur</Label>
              <Select value={length} onValueChange={setLength}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="short">Court (800-1200 mots)</SelectItem>
                  <SelectItem value="medium">
                    Moyen (1500-2000 mots)
                  </SelectItem>
                  <SelectItem value="long">Long (2500-3500 mots)</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label>Langue</Label>
              <Select value={language} onValueChange={setLanguage}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {allowedLanguages.map((l) => (
                    <SelectItem key={l.code} value={l.code}>{l.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label>Mots-clés SEO (optionnel)</Label>
              <Input
                value={keywords}
                onChange={(e) => setKeywords(e.target.value)}
                placeholder="mot-clé1, mot-clé2, ..."
              />
            </div>

            <div className="flex items-center gap-3">
              <Switch checked={dryRun} onCheckedChange={setDryRun} />
              <Label>Aperçu seulement (ne pas publier)</Label>
            </div>

            {activeBrief && (
              <div className="flex items-center justify-between gap-2 p-3 rounded border border-primary/30 bg-primary/5">
                <div className="flex items-center gap-2 text-xs">
                  <Lightbulb className="h-3 w-3 text-primary" />
                  <span>
                    <strong>Brief actif</strong> -{" "}
                    {`Claude utilisera l'outline (${activeBrief.outline?.length || 0} sections), ${activeBrief.faq?.length || 0} FAQ et les entités recommandées.`}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => setActiveBrief(null)}
                  className="text-xs text-muted-foreground hover:text-destructive"
                >
                  Retirer
                </button>
              </div>
            )}

            <Button
              data-testid="generate-article"
              className="w-full"
              size="lg"
              onClick={handleGenerate}
              disabled={generateArticle.isPending || cannotGenerate || deliveryBlocked}
              title={
                deliveryBlocked
                  ? "Aucun chemin de livraison : le contenu n'atteindrait pas ton site. Configure la livraison d'abord."
                  : cannotGenerate
                  ? "Quota mensuel épuisé. Achète des crédits pour continuer."
                  : undefined
              }
            >
              {generateArticle.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Génération en cours...
                </>
              ) : deliveryBlocked ? (
                <>
                  <AlertTriangle className="h-4 w-4 mr-2" />
                  Livraison à configurer
                </>
              ) : cannotGenerate ? (
                <>
                  <AlertTriangle className="h-4 w-4 mr-2" />
                  Quota épuisé · Achète des crédits
                </>
              ) : (
                <>
                  <PenLine className="h-4 w-4 mr-2" />
                  Générer
                </>
              )}
            </Button>

            {/* Inline error block when generation hits 402 quota_exceeded */}
            {quotaError && (
              <div className="rounded-lg border border-destructive/40 bg-destructive/[0.04] p-4 mt-3 space-y-3">
                <div className="flex items-start gap-3">
                  <AlertTriangle className="h-5 w-5 text-destructive shrink-0 mt-0.5" />
                  <div className="text-sm">
                    <div className="font-semibold mb-0.5">
                      Génération bloquée
                    </div>
                    <div className="text-muted-foreground">{quotaError}</div>
                  </div>
                </div>
                <div className="flex flex-wrap gap-2 pl-8">
                  <Button
                    size="sm"
                    onClick={() => buyCredits.mutate("small")}
                    disabled={buyCredits.isPending}
                  >
                    {buyCredits.isPending ? (
                      <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
                    ) : (
                      <Coins className="h-3.5 w-3.5 mr-1.5" />
                    )}
                    +10 crédits · 25$
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => buyCredits.mutate("medium")}
                    disabled={buyCredits.isPending}
                  >
                    +50 crédits · 99$
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => router.push("/billing")}
                  >
                    Voir les plans
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Result */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Résultat</CardTitle>
          </CardHeader>
          <CardContent>
            {generateArticle.isPending ? (
              <div className="flex flex-col items-center justify-center py-12 gap-4">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
                <p className="text-muted-foreground text-sm">
                  Génération en cours... Cela peut prendre 1-2 minutes
                </p>
              </div>
            ) : result ? (
              <div className="space-y-4">
                <div className="bg-muted/50 rounded-md p-4 max-h-96 overflow-y-auto">
                  <pre className="text-xs whitespace-pre-wrap break-words font-mono">
                    {result.output}
                  </pre>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button
                    variant="outline"
                    onClick={() => router.push(`${base}/articles`)}
                  >
                    <Pencil className="h-4 w-4 mr-2" />
                    Voir les articles
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => {
                      setResult(null);
                    }}
                  >
                    <RefreshCw className="h-4 w-4 mr-2" />
                    Générer un autre
                  </Button>
                </div>
              </div>
            ) : (
              <div className="text-center py-12 text-muted-foreground">
                <FileText className="h-12 w-12 mx-auto mb-4 opacity-30" />
                <p>Le résultat de la génération apparaîtra ici</p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
