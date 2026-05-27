"use client";

import { Suspense, useState, useEffect, useRef } from "react";
import { useRouter, useParams, useSearchParams } from "next/navigation";
import { usePersistedState } from "@/hooks/usePersistedState";
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
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Sparkles,
  Loader2,
  Pencil,
  RefreshCw,
  AlertTriangle,
  Coins,
} from "lucide-react";
import { toast } from "sonner";
import { useQuery, useMutation } from "@tanstack/react-query";
import { authFetch, ApiError } from "@/lib/api-client";

function AIGeneratorInner() {
  const router = useRouter();
  const params = useParams<{ siteId: string }>();
  const siteId = params?.siteId;
  const search = useSearchParams();
  const base = `/dashboard/${siteId}`;
  const generateArticle = useGenerateArticle();
  const { data: sites = [] } = useSites();
  const currentSite = sites.find((s: { id: number }) => s.id === Number(siteId));

  const ALL_LANGUAGES: { code: string; label: string }[] = [
    { code: "fr", label: "Francais" },
    { code: "en", label: "English" },
    { code: "es", label: "Espanol" },
  ];
  const allowedLanguages =
    currentSite?.available_languages && currentSite.available_languages.length > 0
      ? ALL_LANGUAGES.filter((l) => currentSite.available_languages!.includes(l.code))
      : ALL_LANGUAGES;

  const persistKey = (slot: string) => `gridar:site:${siteId}:ai-generator:${slot}`;
  const [topic, setTopic] = usePersistedState<string>(persistKey("topic"), "");
  const [title, setTitle] = usePersistedState<string>(persistKey("title"), "");
  const [searchMethod, setSearchMethod] = usePersistedState<string>(persistKey("searchMethod"), "serper");
  const [articleType, setArticleType] = usePersistedState<string>(persistKey("articleType"), "news");
  const [length, setLength] = usePersistedState<string>(persistKey("length"), "medium");
  const [language, setLanguage] = usePersistedState<string>(persistKey("language"), "fr");
  const [keywords, setKeywords] = usePersistedState<string>(persistKey("keywords"), "");
  const [dryRun, setDryRun] = usePersistedState<boolean>(persistKey("dryRun"), false);

  // Template + title pre-fill from query params
  useEffect(() => {
    if (!search) return;
    const tplId = search.get("tpl_id");
    if (tplId) {
      const tpl = aiTemplates.find((t) => t.id === tplId);
      if (tpl) {
        setArticleType(tpl.params.type);
        setLength(tpl.params.length);
        setSearchMethod(tpl.params.search);
      }
    }
    const presetTitle = search.get("title");
    if (presetTitle) setTitle(presetTitle);
    const presetTopic = search.get("topic");
    if (presetTopic) setTopic(presetTopic);
    const presetKeywords = search.get("keywords");
    if (presetKeywords) setKeywords(presetKeywords);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search]);

  const autoStartedRef = useRef(false);
  useEffect(() => {
    if (autoStartedRef.current) return;
    if (search?.get("autostart") !== "1") return;
    if (!title && !topic) return;
    autoStartedRef.current = true;
    const t = setTimeout(() => handleGenerate(), 50);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search, title, topic]);

  const [result, setResult] = usePersistedState<{
    output: string;
    post_count: number;
  } | null>(persistKey("result"), null);

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
  const cannotGenerate = !dryRun && quotaExhausted;

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

    try {
      const data = await generateArticle.mutateAsync(params);
      setResult(data);
      toast.success(dryRun ? "Apercu pret" : "Article publie");
    } catch (err) {
      if (err instanceof ApiError && err.status === 402 && err.body?.quota_exceeded) {
        setQuotaError(err.message);
        return;
      }
      const msg = err instanceof Error ? err.message : "";
      toast.error(msg || "Erreur generation");
    }
  };

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="text-2xl font-bold">Generer un article</h1>
        <p className="text-muted-foreground">
          Donne un sujet ou un titre, Claude redige avec ta voix et ta knowledge base.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Parametres</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label>Sujet</Label>
              <Input
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                placeholder="ex: meilleur CRM PME quebec"
              />
              <p className="text-xs text-muted-foreground">
                Le sujet (ou le titre) est requis. Tu peux laisser vide pour laisser l&apos;IA choisir.
              </p>
            </div>

            <div className="space-y-2">
              <Label>Titre force (optionnel)</Label>
              <Input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="ex: Comment choisir un CRM PME au Quebec en 2026"
              />
            </div>

            <div className="space-y-2">
              <Label>Methode de recherche</Label>
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
                  <SelectItem value="news">Actualite</SelectItem>
                  <SelectItem value="tutorial">Tutoriel</SelectItem>
                  <SelectItem value="comparison">Comparaison</SelectItem>
                  <SelectItem value="guide">Guide</SelectItem>
                  <SelectItem value="review">Review</SelectItem>
                  <SelectItem value="story">Recit personnel</SelectItem>
                  <SelectItem value="local">Local</SelectItem>
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
                  <SelectItem value="short">Court (~1000 mots)</SelectItem>
                  <SelectItem value="medium">Moyen (~1700 mots)</SelectItem>
                  <SelectItem value="long">Long (~3000 mots)</SelectItem>
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
                    <SelectItem key={l.code} value={l.code}>
                      {l.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label>Mots-cles (optionnel, separes par virgule)</Label>
              <Input
                value={keywords}
                onChange={(e) => setKeywords(e.target.value)}
                placeholder="ex: crm, pme, quebec"
              />
            </div>

            <div className="flex items-center gap-3">
              <Switch checked={dryRun} onCheckedChange={setDryRun} />
              <Label>Apercu seul (n&apos;enregistre pas, ne consomme pas de quota)</Label>
            </div>

            <Button
              data-testid="generate-article"
              className="w-full"
              size="lg"
              onClick={handleGenerate}
              disabled={generateArticle.isPending || cannotGenerate}
              title={
                cannotGenerate
                  ? "Quota mensuel epuise. Achete des credits pour continuer."
                  : undefined
              }
            >
              {generateArticle.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Generation en cours...
                </>
              ) : cannotGenerate ? (
                <>
                  <AlertTriangle className="h-4 w-4 mr-2" />
                  Quota epuise. Achete des credits
                </>
              ) : (
                <>
                  <Sparkles className="h-4 w-4 mr-2" />
                  Generer
                </>
              )}
            </Button>

            {quotaError && (
              <div className="rounded-lg border border-destructive/40 bg-destructive/[0.04] p-4 mt-3 space-y-3">
                <div className="flex items-start gap-3">
                  <AlertTriangle className="h-5 w-5 text-destructive shrink-0 mt-0.5" />
                  <div className="text-sm">
                    <div className="font-semibold mb-0.5">Generation bloquee</div>
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
                    +10 credits, 25$
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => buyCredits.mutate("medium")}
                    disabled={buyCredits.isPending}
                  >
                    +50 credits, 99$
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

        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Resultat</CardTitle>
          </CardHeader>
          <CardContent>
            {generateArticle.isPending ? (
              <div className="flex flex-col items-center justify-center py-12 gap-4">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
                <p className="text-muted-foreground text-sm">
                  Generation en cours (1-2 minutes pour un article moyen)...
                </p>
              </div>
            ) : result ? (
              <div className="space-y-4">
                <div className="bg-muted/50 rounded-md p-4 max-h-96 overflow-y-auto">
                  <pre className="text-xs whitespace-pre-wrap font-mono">
                    {result.output}
                  </pre>
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    onClick={() => router.push(`${base}/articles`)}
                  >
                    <Pencil className="h-4 w-4 mr-2" />
                    Voir mes articles
                  </Button>
                  <Button variant="outline" onClick={() => setResult(null)}>
                    <RefreshCw className="h-4 w-4 mr-2" />
                    Generer un autre
                  </Button>
                </div>
              </div>
            ) : (
              <div className="text-center py-12 text-muted-foreground">
                <Sparkles className="h-12 w-12 mx-auto mb-4 opacity-30" />
                <p>Lance une generation pour voir le resultat ici.</p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <p className="text-xs text-muted-foreground">
        Les panneaux de pre-redaction (Content Brief, PAA, Reddit/Quora, Trends) seront ajoutes dans une prochaine session.
      </p>
    </div>
  );
}

export default function AIGeneratorPage() {
  return (
    <Suspense
      fallback={
        <div className="flex justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      }
    >
      <AIGeneratorInner />
    </Suspense>
  );
}
