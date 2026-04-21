import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  CheckCircle,
  AlertTriangle,
  XCircle,
  Sparkles,
  Loader2,
  ChevronDown,
  ChevronUp,
  Wand2,
  Search,
} from "lucide-react";
import { fetchSEOSuggestions } from "@/lib/api-client";
import { toast } from "sonner";

type KeywordSource = "serper_related" | "serper_paa" | "gemini_longtail";

interface KeywordResult {
  keyword: string;
  source: KeywordSource;
  estimated_intent: "informational" | "commercial" | "navigational" | "transactional";
}

interface SEOAnalyzerProps {
  title: string;
  excerpt: string;
  content: string;
  slug: string;
  coverImage?: string;
  keyword?: string;
  onApplyFix?: (fixes: { title?: string; excerpt?: string; content?: string }) => void;
}

interface SEOCheck {
  id: string;
  label: string;
  status: "good" | "warning" | "bad";
  detail: string;
  score: number;
}

function countWords(text: string): number {
  return text.trim().split(/\s+/).filter(Boolean).length;
}

function extractHeadings(markdown: string): { h2: number; h3: number } {
  const h2 = (markdown.match(/^## /gm) || []).length;
  const h3 = (markdown.match(/^### /gm) || []).length;
  return { h2, h3 };
}

function countImages(markdown: string): { total: number; withAlt: number } {
  const images = markdown.match(/!\[([^\]]*)\]\([^)]+\)/g) || [];
  const withAlt = images.filter((img: string) => {
    const alt = img.match(/!\[([^\]]*)\]/)?.[1];
    return alt && alt.trim().length > 0;
  }).length;
  return { total: images.length, withAlt };
}

function countInternalLinks(markdown: string): number {
  const links = markdown.match(/\[([^\]]+)\]\(\/[^)]+\)/g) || [];
  return links.length;
}

function countExternalLinks(markdown: string): number {
  const links = markdown.match(/\[([^\]]+)\]\(https?:\/\/[^)]+\)/g) || [];
  return links.length;
}

function normalize(s: string): string {
  return s
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");
}

function firstParagraph(markdown: string): string {
  const stripped = markdown.replace(/^(#{1,6}\s.*|!\[.*?\]\(.*?\)|\s*)\n/gm, "");
  const paras = stripped.split(/\n\s*\n/).map((p) => p.trim()).filter(Boolean);
  return paras[0] || "";
}

export function SEOAnalyzer({
  title,
  excerpt,
  content,
  slug,
  coverImage,
  keyword = "",
  onApplyFix,
}: SEOAnalyzerProps) {
  const { i18n } = useTranslation();
  const [expanded, setExpanded] = useState(true);
  const [aiAuditLoading, setAiAuditLoading] = useState(false);
  const [aiAudit, setAiAudit] = useState<{
    score: number;
    verdict: string;
    strengths: string[];
    weaknesses: string[];
    actions: string[];
  } | null>(null);
  const [aiLoading, setAiLoading] = useState(false);
  const [fixLoading, setFixLoading] = useState(false);
  const [aiSuggestions, setAiSuggestions] = useState<{
    meta_descriptions?: string[];
    title_suggestions?: string[];
    keywords?: string[];
  } | null>(null);
  const [kwSeed, setKwSeed] = useState("");
  const [kwLoading, setKwLoading] = useState(false);
  const [kwResults, setKwResults] = useState<KeywordResult[] | null>(null);

  const checks = useMemo<SEOCheck[]>(() => {
    const results: SEOCheck[] = [];
    const lang = i18n.language;

    // Title length
    const titleLen = title.length;
    if (titleLen >= 50 && titleLen <= 60) {
      results.push({
        id: "title-length",
        label: lang === "fr" ? "Longueur du titre" : "Title length",
        status: "good",
        detail: `${titleLen}/60`,
        score: 15,
      });
    } else if (titleLen > 0 && titleLen < 50) {
      results.push({
        id: "title-length",
        label: lang === "fr" ? "Longueur du titre" : "Title length",
        status: "warning",
        detail: lang === "fr" ? `${titleLen}/60 - un peu court` : `${titleLen}/60 - a bit short`,
        score: 8,
      });
    } else if (titleLen > 60) {
      results.push({
        id: "title-length",
        label: lang === "fr" ? "Longueur du titre" : "Title length",
        status: "bad",
        detail: lang === "fr" ? `${titleLen}/60 - trop long` : `${titleLen}/60 - too long`,
        score: 3,
      });
    } else {
      results.push({
        id: "title-length",
        label: lang === "fr" ? "Longueur du titre" : "Title length",
        status: "bad",
        detail: lang === "fr" ? "Titre manquant" : "Missing title",
        score: 0,
      });
    }

    // Meta description
    const descLen = excerpt.length;
    if (descLen >= 120 && descLen <= 160) {
      results.push({
        id: "meta-desc",
        label: "Meta description",
        status: "good",
        detail: `${descLen}/160`,
        score: 15,
      });
    } else if (descLen > 0 && descLen < 120) {
      results.push({
        id: "meta-desc",
        label: "Meta description",
        status: "warning",
        detail: lang === "fr" ? `${descLen}/160 - trop court` : `${descLen}/160 - too short`,
        score: 8,
      });
    } else if (descLen > 160) {
      results.push({
        id: "meta-desc",
        label: "Meta description",
        status: "bad",
        detail: lang === "fr" ? `${descLen}/160 - trop long` : `${descLen}/160 - too long`,
        score: 3,
      });
    } else {
      results.push({
        id: "meta-desc",
        label: "Meta description",
        status: "bad",
        detail: lang === "fr" ? "Description manquante" : "Missing description",
        score: 0,
      });
    }

    // Word count (seuils révisés : 600/1000 au lieu de 800/1500)
    const words = countWords(content);
    if (words >= 1000) {
      results.push({
        id: "word-count",
        label: lang === "fr" ? "Nombre de mots" : "Word count",
        status: "good",
        detail: `${words} ${lang === "fr" ? "mots" : "words"}`,
        score: 10,
      });
    } else if (words >= 600) {
      results.push({
        id: "word-count",
        label: lang === "fr" ? "Nombre de mots" : "Word count",
        status: "warning",
        detail: `${words} ${lang === "fr" ? "mots - visez 1000+" : "words - aim for 1000+"}`,
        score: 6,
      });
    } else {
      results.push({
        id: "word-count",
        label: lang === "fr" ? "Nombre de mots" : "Word count",
        status: "bad",
        detail: `${words} ${lang === "fr" ? "mots - trop court" : "words - too short"}`,
        score: 2,
      });
    }

    // Keyword usage (primary keyword in title, first paragraph, H2s)
    if (keyword.trim()) {
      const kw = normalize(keyword);
      const titleHit = normalize(title).includes(kw);
      const introHit = normalize(firstParagraph(content)).includes(kw);
      const h2s = content.match(/^## .+$/gm) || [];
      const h2Hits = h2s.filter((h) => normalize(h).includes(kw)).length;
      const hits = Number(titleHit) + Number(introHit) + Math.min(h2Hits, 2);

      if (hits >= 3) {
        results.push({
          id: "keyword",
          label: lang === "fr" ? "Mot-clé principal" : "Primary keyword",
          status: "good",
          detail: lang === "fr" ? `Présent dans titre, intro et H2` : `In title, intro and H2`,
          score: 20,
        });
      } else if (hits >= 2) {
        results.push({
          id: "keyword",
          label: lang === "fr" ? "Mot-clé principal" : "Primary keyword",
          status: "warning",
          detail: lang === "fr" ? `Présent dans ${hits}/3 zones clés (titre, intro, H2)` : `In ${hits}/3 key zones`,
          score: 12,
        });
      } else {
        results.push({
          id: "keyword",
          label: lang === "fr" ? "Mot-clé principal" : "Primary keyword",
          status: "bad",
          detail: lang === "fr" ? `Manque dans titre, intro ou H2` : `Missing in title/intro/H2`,
          score: 4,
        });
      }
    }

    // Internal / external links
    const internal = countInternalLinks(content);
    const external = countExternalLinks(content);
    if (internal >= 2) {
      results.push({
        id: "links",
        label: lang === "fr" ? "Maillage interne" : "Internal links",
        status: "good",
        detail: lang === "fr" ? `${internal} liens internes, ${external} externes` : `${internal} internal, ${external} external`,
        score: 10,
      });
    } else if (internal >= 1) {
      results.push({
        id: "links",
        label: lang === "fr" ? "Maillage interne" : "Internal links",
        status: "warning",
        detail: lang === "fr" ? `${internal} lien interne — visez 2+` : `${internal} internal — aim for 2+`,
        score: 5,
      });
    } else {
      results.push({
        id: "links",
        label: lang === "fr" ? "Maillage interne" : "Internal links",
        status: "bad",
        detail: lang === "fr" ? "Aucun lien interne" : "No internal links",
        score: 0,
      });
    }

    // Heading structure
    const headings = extractHeadings(content);
    if (headings.h2 >= 2) {
      results.push({
        id: "headings",
        label: lang === "fr" ? "Structure (H2/H3)" : "Structure (H2/H3)",
        status: "good",
        detail: `${headings.h2} H2, ${headings.h3} H3`,
        score: 15,
      });
    } else if (headings.h2 >= 1) {
      results.push({
        id: "headings",
        label: lang === "fr" ? "Structure (H2/H3)" : "Structure (H2/H3)",
        status: "warning",
        detail: lang === "fr" ? `${headings.h2} H2 - ajoutez-en plus` : `${headings.h2} H2 - add more`,
        score: 8,
      });
    } else {
      results.push({
        id: "headings",
        label: lang === "fr" ? "Structure (H2/H3)" : "Structure (H2/H3)",
        status: "bad",
        detail: lang === "fr" ? "Aucun sous-titre H2" : "No H2 headings",
        score: 0,
      });
    }

    // Images & alt text
    const images = countImages(content);
    if (images.total > 0 && images.withAlt === images.total) {
      results.push({
        id: "images",
        label: lang === "fr" ? "Images & alt-text" : "Images & alt-text",
        status: "good",
        detail: `${images.total} images, ${lang === "fr" ? "tous avec alt" : "all with alt"}`,
        score: 15,
      });
    } else if (images.total > 0) {
      results.push({
        id: "images",
        label: lang === "fr" ? "Images & alt-text" : "Images & alt-text",
        status: "warning",
        detail: `${images.withAlt}/${images.total} ${lang === "fr" ? "avec alt-text" : "with alt-text"}`,
        score: 8,
      });
    } else {
      results.push({
        id: "images",
        label: lang === "fr" ? "Images & alt-text" : "Images & alt-text",
        status: "bad",
        detail: lang === "fr" ? "Aucune image" : "No images",
        score: 3,
      });
    }

    // Cover image
    if (coverImage) {
      results.push({
        id: "cover",
        label: lang === "fr" ? "Image de couverture" : "Cover image",
        status: "good",
        detail: "OK",
        score: 10,
      });
    } else {
      results.push({
        id: "cover",
        label: lang === "fr" ? "Image de couverture" : "Cover image",
        status: "bad",
        detail: lang === "fr" ? "Manquante" : "Missing",
        score: 0,
      });
    }

    // Slug
    if (slug && slug.length > 0 && slug.length <= 60) {
      results.push({
        id: "slug",
        label: "Slug",
        status: "good",
        detail: `/${slug}`,
        score: 5,
      });
    } else if (!slug) {
      results.push({
        id: "slug",
        label: "Slug",
        status: "bad",
        detail: lang === "fr" ? "Manquant" : "Missing",
        score: 0,
      });
    } else {
      results.push({
        id: "slug",
        label: "Slug",
        status: "warning",
        detail: lang === "fr" ? "Trop long" : "Too long",
        score: 3,
      });
    }

    return results;
  }, [title, excerpt, content, slug, coverImage, keyword, i18n.language]);

  const totalScore = useMemo(() => {
    const maxScore = 100;
    const raw = checks.reduce((sum, c) => sum + c.score, 0);
    return Math.min(maxScore, raw);
  }, [checks]);

  const scoreColor =
    totalScore >= 70
      ? "text-green-500"
      : totalScore >= 40
        ? "text-yellow-500"
        : "text-red-500";

  const scoreBg =
    totalScore >= 70
      ? "bg-green-500/10"
      : totalScore >= 40
        ? "bg-yellow-500/10"
        : "bg-red-500/10";

  const hasIssues = checks.some((c) => c.status !== "good");

  const handleAiAudit = async () => {
    setAiAuditLoading(true);
    try {
      const { authFetch } = await import("@/lib/api-client");
      const res = await authFetch("/seo-audit/", {
        method: "POST",
        body: JSON.stringify({
          title,
          excerpt,
          content: content.slice(0, 5000),
          keyword,
          language: i18n.language,
        }),
      });
      if (!res.ok) throw new Error("Audit failed");
      const data = await res.json();
      setAiAudit(data);
    } catch {
      toast.error(i18n.language === "fr" ? "Erreur audit IA" : "AI audit error");
    } finally {
      setAiAuditLoading(false);
    }
  };

  const handleFixAll = async () => {
    if (!onApplyFix) return;
    setFixLoading(true);
    try {
      const { authFetch } = await import("@/lib/api-client");
      const issues = checks
        .filter((c) => c.status !== "good")
        .map((c) => `${c.label}: ${c.detail}`)
        .join("\n");

      const res = await authFetch("/seo-fix/", {
        method: "POST",
        body: JSON.stringify({
          title,
          excerpt,
          content: content.slice(0, 4000),
          issues,
          language: i18n.language,
        }),
      });
      if (!res.ok) throw new Error("Erreur");
      const data = await res.json();
      onApplyFix({
        title: data.title || undefined,
        excerpt: data.excerpt || undefined,
        content: data.content || undefined,
      });
      toast.success(i18n.language === "fr" ? "Corrections appliquées !" : "Fixes applied!");
    } catch {
      toast.error(i18n.language === "fr" ? "Erreur correction IA" : "AI fix error");
    } finally {
      setFixLoading(false);
    }
  };

  const handleAiSuggest = async () => {
    setAiLoading(true);
    try {
      const data = await fetchSEOSuggestions({
        title,
        content: content.substring(0, 2000),
        excerpt,
        language: i18n.language,
      });
      setAiSuggestions(data);
    } catch {
      toast.error(
        i18n.language === "fr"
          ? "Erreur lors des suggestions IA"
          : "Error getting AI suggestions"
      );
    } finally {
      setAiLoading(false);
    }
  };

  const handleKeywordResearch = async () => {
    const seed = kwSeed.trim();
    if (!seed) return;
    setKwLoading(true);
    try {
      const { authFetch } = await import("@/lib/api-client");
      const res = await authFetch("/keyword-research/", {
        method: "POST",
        body: JSON.stringify({
          seed_keyword: seed,
          language: i18n.language,
        }),
      });
      if (!res.ok) throw new Error("Keyword research failed");
      const data = await res.json();
      setKwResults(data.keywords || []);
    } catch {
      toast.error(
        i18n.language === "fr"
          ? "Erreur recherche de mots-cles"
          : "Keyword research error"
      );
    } finally {
      setKwLoading(false);
    }
  };

  const copyKeyword = async (kw: string) => {
    try {
      await navigator.clipboard.writeText(kw);
      toast.success(i18n.language === "fr" ? "Copie !" : "Copied!");
    } catch {
      toast.error(i18n.language === "fr" ? "Erreur copie" : "Copy error");
    }
  };

  const StatusIcon = ({ status }: { status: string }) => {
    if (status === "good") return <CheckCircle className="h-4 w-4 text-green-500" />;
    if (status === "warning") return <AlertTriangle className="h-4 w-4 text-yellow-500" />;
    return <XCircle className="h-4 w-4 text-red-500" />;
  };

  return (
    <div className="space-y-4">
      {/* Score Card */}
      <Card>
        <CardContent className="p-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div
                className={`w-14 h-14 rounded-full flex items-center justify-center ${scoreBg}`}
              >
                <span className={`text-xl font-bold ${scoreColor}`}>
                  {totalScore}
                </span>
              </div>
              <div>
                <p className="font-medium text-sm">
                  {i18n.language === "fr" ? "Score SEO" : "SEO Score"}
                </p>
                <p className="text-xs text-muted-foreground">
                  {totalScore >= 70
                    ? i18n.language === "fr"
                      ? "Bon"
                      : "Good"
                    : totalScore >= 40
                      ? i18n.language === "fr"
                        ? "A ameliorer"
                        : "Needs improvement"
                      : i18n.language === "fr"
                        ? "Faible"
                        : "Poor"}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              {hasIssues && onApplyFix && (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleFixAll}
                  disabled={fixLoading}
                  className="text-xs"
                >
                  {fixLoading ? (
                    <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />
                  ) : (
                    <Wand2 className="h-3.5 w-3.5 mr-1" />
                  )}
                  {i18n.language === "fr" ? "Corriger avec IA" : "Fix with AI"}
                </Button>
              )}
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setExpanded(!expanded)}
              >
                {expanded ? (
                  <ChevronUp className="h-4 w-4" />
                ) : (
                  <ChevronDown className="h-4 w-4" />
                )}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Checks */}
      {expanded && (
        <Card>
          <CardContent className="p-4 space-y-2">
            {checks.map((check) => (
              <div
                key={check.id}
                className="flex items-center gap-3 py-1.5 border-b last:border-0"
              >
                <StatusIcon status={check.status} />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium">{check.label}</p>
                  <p className="text-xs text-muted-foreground">{check.detail}</p>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* AI Audit */}
      <Card>
        <CardHeader className="py-3 px-4">
          <CardTitle className="text-sm flex items-center gap-2">
            <Wand2 className="h-4 w-4" />
            {i18n.language === "fr" ? "Audit SEO par IA" : "AI SEO Audit"}
          </CardTitle>
        </CardHeader>
        <CardContent className="px-4 pb-4 space-y-3">
          <Button
            size="sm"
            variant="outline"
            onClick={handleAiAudit}
            disabled={aiAuditLoading || !title}
          >
            {aiAuditLoading ? (
              <>
                <Loader2 className="h-4 w-4 mr-1.5 animate-spin" />
                {i18n.language === "fr" ? "Analyse en cours..." : "Analyzing..."}
              </>
            ) : (
              <>
                <Wand2 className="h-4 w-4 mr-1.5" />
                {i18n.language === "fr" ? "Lancer l'audit" : "Run audit"}
              </>
            )}
          </Button>

          {aiAudit && (
            <div className="space-y-3 pt-2 border-t">
              <div className="flex items-center gap-3">
                <div
                  className={`w-12 h-12 rounded-full flex items-center justify-center font-bold ${
                    aiAudit.score >= 70
                      ? "bg-green-500/10 text-green-500"
                      : aiAudit.score >= 40
                      ? "bg-yellow-500/10 text-yellow-500"
                      : "bg-red-500/10 text-red-500"
                  }`}
                >
                  {aiAudit.score}
                </div>
                <p className="text-sm text-muted-foreground flex-1">{aiAudit.verdict}</p>
              </div>

              {aiAudit.strengths?.length > 0 && (
                <div>
                  <p className="text-xs font-semibold mb-1 text-green-500">
                    ✓ {i18n.language === "fr" ? "Points forts" : "Strengths"}
                  </p>
                  <ul className="text-xs space-y-1 text-muted-foreground">
                    {aiAudit.strengths.map((s, i) => (
                      <li key={i}>• {s}</li>
                    ))}
                  </ul>
                </div>
              )}

              {aiAudit.weaknesses?.length > 0 && (
                <div>
                  <p className="text-xs font-semibold mb-1 text-red-500">
                    ✗ {i18n.language === "fr" ? "Points faibles" : "Weaknesses"}
                  </p>
                  <ul className="text-xs space-y-1 text-muted-foreground">
                    {aiAudit.weaknesses.map((w, i) => (
                      <li key={i}>• {w}</li>
                    ))}
                  </ul>
                </div>
              )}

              {aiAudit.actions?.length > 0 && (
                <div>
                  <p className="text-xs font-semibold mb-1 text-primary">
                    → {i18n.language === "fr" ? "Actions à faire" : "Action items"}
                  </p>
                  <ul className="text-xs space-y-1 text-muted-foreground">
                    {aiAudit.actions.map((a, i) => (
                      <li key={i}>• {a}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* AI Suggestions */}
      <Card>
        <CardHeader className="py-3 px-4">
          <CardTitle className="text-sm flex items-center gap-2">
            <Sparkles className="h-4 w-4" />
            {i18n.language === "fr" ? "Suggestions IA" : "AI Suggestions"}
          </CardTitle>
        </CardHeader>
        <CardContent className="px-4 pb-4">
          <Button
            size="sm"
            variant="outline"
            onClick={handleAiSuggest}
            disabled={aiLoading || !title}
          >
            {aiLoading ? (
              <>
                <Loader2 className="h-4 w-4 mr-1.5 animate-spin" />
                {i18n.language === "fr" ? "Analyse..." : "Analyzing..."}
              </>
            ) : (
              <>
                <Sparkles className="h-4 w-4 mr-1.5" />
                {i18n.language === "fr" ? "Obtenir des suggestions" : "Get suggestions"}
              </>
            )}
          </Button>

          {aiSuggestions && (
            <div className="mt-4 space-y-4">
              {aiSuggestions.meta_descriptions &&
                aiSuggestions.meta_descriptions.length > 0 && (
                  <div>
                    <p className="text-xs font-medium mb-2">
                      {i18n.language === "fr"
                        ? "Meta descriptions suggerees"
                        : "Suggested meta descriptions"}
                    </p>
                    {aiSuggestions.meta_descriptions.map((desc, i) => (
                      <p
                        key={i}
                        className="text-xs text-muted-foreground p-2 bg-muted/50 rounded mb-1 cursor-pointer hover:bg-muted transition-colors"
                        title={
                          i18n.language === "fr"
                            ? "Cliquer pour copier"
                            : "Click to copy"
                        }
                        onClick={() => {
                          navigator.clipboard.writeText(desc);
                          toast.success(
                            i18n.language === "fr" ? "Copie!" : "Copied!"
                          );
                        }}
                      >
                        {desc}
                      </p>
                    ))}
                  </div>
                )}

              {aiSuggestions.title_suggestions &&
                aiSuggestions.title_suggestions.length > 0 && (
                  <div>
                    <p className="text-xs font-medium mb-2">
                      {i18n.language === "fr"
                        ? "Titres alternatifs"
                        : "Alternative titles"}
                    </p>
                    {aiSuggestions.title_suggestions.map((t, i) => (
                      <p
                        key={i}
                        className="text-xs text-muted-foreground p-2 bg-muted/50 rounded mb-1 cursor-pointer hover:bg-muted transition-colors"
                        onClick={() => {
                          navigator.clipboard.writeText(t);
                          toast.success(
                            i18n.language === "fr" ? "Copie!" : "Copied!"
                          );
                        }}
                      >
                        {t}
                      </p>
                    ))}
                  </div>
                )}

              {aiSuggestions.keywords && aiSuggestions.keywords.length > 0 && (
                <div>
                  <p className="text-xs font-medium mb-2">
                    {i18n.language === "fr"
                      ? "Mots-cles recommandes"
                      : "Recommended keywords"}
                  </p>
                  <div className="flex flex-wrap gap-1">
                    {aiSuggestions.keywords.map((kw, i) => (
                      <span
                        key={i}
                        className="text-xs px-2 py-0.5 bg-primary/10 text-primary rounded-full"
                      >
                        {kw}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Keyword Research */}
      <Card>
        <CardHeader className="py-3 px-4">
          <CardTitle className="text-sm flex items-center gap-2">
            <Search className="h-4 w-4" />
            {i18n.language === "fr"
              ? "Recherche de mots-cles"
              : "Keyword research"}
          </CardTitle>
        </CardHeader>
        <CardContent className="px-4 pb-4 space-y-3">
          <div className="flex gap-2">
            <Input
              value={kwSeed}
              onChange={(e) => setKwSeed(e.target.value)}
              placeholder={
                i18n.language === "fr"
                  ? "Mot-cle de depart..."
                  : "Seed keyword..."
              }
              onKeyDown={(e) => {
                if (e.key === "Enter" && !kwLoading) {
                  e.preventDefault();
                  handleKeywordResearch();
                }
              }}
              disabled={kwLoading}
              className="h-9 text-sm"
            />
            <Button
              size="sm"
              variant="outline"
              onClick={handleKeywordResearch}
              disabled={kwLoading || !kwSeed.trim()}
            >
              {kwLoading ? (
                <>
                  <Loader2 className="h-4 w-4 mr-1.5 animate-spin" />
                  {i18n.language === "fr" ? "Recherche..." : "Searching..."}
                </>
              ) : (
                <>
                  <Search className="h-4 w-4 mr-1.5" />
                  {i18n.language === "fr" ? "Rechercher" : "Search"}
                </>
              )}
            </Button>
          </div>

          {kwResults && kwResults.length === 0 && (
            <p className="text-xs text-muted-foreground">
              {i18n.language === "fr"
                ? "Aucun mot-cle trouve."
                : "No keywords found."}
            </p>
          )}

          {kwResults && kwResults.length > 0 && (
            <div className="space-y-3 pt-1">
              {(
                [
                  {
                    source: "serper_related" as KeywordSource,
                    labelFr: "Recherches associees",
                    labelEn: "Related searches",
                  },
                  {
                    source: "serper_paa" as KeywordSource,
                    labelFr: "Les gens demandent aussi",
                    labelEn: "People also ask",
                  },
                  {
                    source: "gemini_longtail" as KeywordSource,
                    labelFr: "Long-tail (IA)",
                    labelEn: "Long-tail (AI)",
                  },
                ]
              ).map((group) => {
                const items = kwResults.filter((k) => k.source === group.source);
                if (items.length === 0) return null;
                return (
                  <div key={group.source}>
                    <p className="text-xs font-medium mb-2">
                      {i18n.language === "fr" ? group.labelFr : group.labelEn}
                    </p>
                    <div className="flex flex-wrap gap-1">
                      {items.map((item, i) => (
                        <Badge
                          key={`${group.source}-${i}`}
                          variant="secondary"
                          className="cursor-pointer hover:bg-primary/20 transition-colors text-xs font-normal"
                          title={`${item.estimated_intent} - ${
                            i18n.language === "fr"
                              ? "Cliquer pour copier"
                              : "Click to copy"
                          }`}
                          onClick={() => copyKeyword(item.keyword)}
                        >
                          {item.keyword}
                        </Badge>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
