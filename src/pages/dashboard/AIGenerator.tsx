import { useState, useEffect } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
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
import { Sparkles, Loader2, Pencil, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { ContentBriefPanel } from "@/components/ContentBrief";
import { PAAPanel } from "@/components/PAAPanel";
import { CommunityQuestionsPanel } from "@/components/CommunityQuestionsPanel";
import { SearchTrendsPanel } from "@/components/SearchTrendsPanel";

export default function AIGenerator() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { siteId } = useParams<{ siteId: string }>();
  const [searchParams] = useSearchParams();
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

  const [topic, setTopic] = useState("");
  const [title, setTitle] = useState("");
  const [searchMethod, setSearchMethod] = useState("serper");
  const [articleType, setArticleType] = useState("news");
  const [length, setLength] = useState("medium");
  const [language, setLanguage] = useState<string>("fr");
  const [keywords, setKeywords] = useState("");
  const [dryRun, setDryRun] = useState(false);

  // Template + title pre-fill from query params
  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    const tplId = searchParams.get("tpl_id");
    if (tplId) {
      const tpl = aiTemplates.find((t) => t.id === tplId);
      if (tpl) {
        setArticleType(tpl.params.type);
        setLength(tpl.params.length);
        setSearchMethod(tpl.params.search);
      }
    }
    const presetTitle = searchParams.get("title");
    if (presetTitle) setTitle(presetTitle);
    const presetTopic = searchParams.get("topic");
    if (presetTopic) setTopic(presetTopic);
    const presetKeywords = searchParams.get("keywords");
    if (presetKeywords) setKeywords(presetKeywords);
  }, [searchParams]);
  /* eslint-enable react-hooks/set-state-in-effect */

  const [result, setResult] = useState<{
    output: string;
    post_count: number;
  } | null>(null);

  const handleGenerate = async () => {
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
      toast.success(
        dryRun ? t("ai.previewSuccess") : t("ai.publishSuccess")
      );
    } catch {
      toast.error(t("ai.error"));
    }
  };

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="text-2xl font-bold">{t("ai.title")}</h1>
        <p className="text-muted-foreground">
          {t("ai.subtitle")}
        </p>
      </div>

      {/* Content Brief — pre-writing brief (optional, fills the form when applied) */}
      <ContentBriefPanel
        language={language}
        defaultKeyword={keywords.split(",")[0]?.trim() || topic}
        onApply={({ topic: t2, title: ti2, keywords: kw2 }) => {
          if (t2) setTopic(t2);
          if (ti2) setTitle(ti2);
          if (kw2) setKeywords(kw2);
        }}
      />

      {/* PAA harvester — questions + FAQ schema */}
      <PAAPanel
        language={language}
        defaultKeyword={keywords.split(",")[0]?.trim() || topic}
      />

      {/* Reddit / Quora community questions */}
      <CommunityQuestionsPanel
        language={language}
        defaultKeyword={keywords.split(",")[0]?.trim() || topic}
      />

      {/* Google Trends — interest over time + related/rising queries */}
      <SearchTrendsPanel
        language={language}
        defaultKeyword={keywords.split(",")[0]?.trim() || topic}
      />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Form */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">{t("ai.params")}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label>{t("ai.topic")}</Label>
              <Input
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                placeholder={t("ai.topicPlaceholder")}
              />
              <p className="text-xs text-muted-foreground">
                {t("ai.topicHelp")}
              </p>
            </div>

            <div className="space-y-2">
              <Label>{t("ai.forcedTitle")}</Label>
              <Input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder={t("ai.forcedTitlePlaceholder")}
              />
            </div>

            <div className="space-y-2">
              <Label>{t("ai.searchMethod")}</Label>
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
              <Label>{t("ai.articleType")}</Label>
              <Select value={articleType} onValueChange={setArticleType}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="news">{t("ai.typeNews")}</SelectItem>
                  <SelectItem value="tutorial">{t("ai.typeTutorial")}</SelectItem>
                  <SelectItem value="comparison">{t("ai.typeComparison")}</SelectItem>
                  <SelectItem value="guide">{t("ai.typeGuide")}</SelectItem>
                  <SelectItem value="review">{t("ai.typeReview")}</SelectItem>
                  <SelectItem value="story">{t("ai.typeStory")}</SelectItem>
                  <SelectItem value="local">{t("ai.typeLocal")}</SelectItem>
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label>{t("ai.length")}</Label>
              <Select value={length} onValueChange={setLength}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="short">{t("ai.lengthShort")}</SelectItem>
                  <SelectItem value="medium">
                    {t("ai.lengthMedium")}
                  </SelectItem>
                  <SelectItem value="long">{t("ai.lengthLong")}</SelectItem>
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
              <Label>{t("ai.keywords")}</Label>
              <Input
                value={keywords}
                onChange={(e) => setKeywords(e.target.value)}
                placeholder={t("ai.keywordsPlaceholder")}
              />
            </div>

            <div className="flex items-center gap-3">
              <Switch checked={dryRun} onCheckedChange={setDryRun} />
              <Label>{t("ai.dryRun")}</Label>
            </div>

            <Button
              className="w-full"
              size="lg"
              onClick={handleGenerate}
              disabled={generateArticle.isPending}
            >
              {generateArticle.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  {t("ai.generating")}
                </>
              ) : (
                <>
                  <Sparkles className="h-4 w-4 mr-2" />
                  {t("ai.generate")}
                </>
              )}
            </Button>
          </CardContent>
        </Card>

        {/* Result */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">{t("ai.result")}</CardTitle>
          </CardHeader>
          <CardContent>
            {generateArticle.isPending ? (
              <div className="flex flex-col items-center justify-center py-12 gap-4">
                <Loader2 className="h-8 w-8 animate-spin text-primary" />
                <p className="text-muted-foreground text-sm">
                  {t("ai.generatingWait")}
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
                    onClick={() => navigate(`${base}/articles`)}
                  >
                    <Pencil className="h-4 w-4 mr-2" />
                    {t("ai.viewArticles")}
                  </Button>
                  <Button
                    variant="outline"
                    onClick={() => {
                      setResult(null);
                    }}
                  >
                    <RefreshCw className="h-4 w-4 mr-2" />
                    {t("ai.generateAnother")}
                  </Button>
                </div>
              </div>
            ) : (
              <div className="text-center py-12 text-muted-foreground">
                <Sparkles className="h-12 w-12 mx-auto mb-4 opacity-30" />
                <p>{t("ai.resultPlaceholder")}</p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
