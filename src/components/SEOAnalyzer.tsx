import { useEffect, useMemo, useState } from "react";
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
  Users,
  ExternalLink,
  Search,
  Gauge,
  Smartphone,
  Monitor,
} from "lucide-react";
import { authFetch, fetchSEOSuggestions } from "@/lib/api-client";
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
  articleUrl?: string;
  onApplyFix?: (fixes: { title?: string; excerpt?: string; content?: string }) => void;
}

interface PageSpeedResult {
  performance_score: number | null;
  seo_score: number | null;
  a11y_score: number | null;
  lcp_s: number | null;
  cls: number | null;
  fcp_s: number | null;
  strategy: string;
  tested_url: string;
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

interface AltTextAnalysis {
  total: number;
  withQuality: number;
  withGeneric: number;
  duplicates: number;
  missing: number;
  tooLong: number;
}

const GENERIC_ALT_LIST = ["image", "photo", "picture", "img", "bild", "cover"];
const GENERIC_ALT_REGEX = /^(image|photo|pic|img|picture)\s*\d*$/i;
const DIGITS_OR_WHITESPACE_REGEX = /^[\d\s]+$/;

function isGenericAlt(alt: string): boolean {
  const trimmed = alt.trim();
  if (trimmed.length === 0) return false; // empty = missing, not generic
  if (trimmed.length < 5) return true;
  if (GENERIC_ALT_REGEX.test(trimmed)) return true;
  if (DIGITS_OR_WHITESPACE_REGEX.test(trimmed)) return true;
  if (GENERIC_ALT_LIST.includes(trimmed.toLowerCase())) return true;
  return false;
}

function analyzeAltTexts(markdown: string): AltTextAnalysis {
  const images = markdown.match(/!\[([^\]]*)\]\([^)]+\)/g) || [];
  const alts: string[] = images.map((img) => {
    const m = img.match(/!\[([^\]]*)\]/);
    return m?.[1] ?? "";
  });

  // Find duplicates among non-empty alts (case-insensitive, trimmed)
  const altCounts = new Map<string, number>();
  for (const alt of alts) {
    const key = alt.trim().toLowerCase();
    if (key.length === 0) continue;
    altCounts.set(key, (altCounts.get(key) || 0) + 1);
  }
  const duplicateKeys = new Set<string>();
  for (const [key, count] of altCounts.entries()) {
    if (count > 1) duplicateKeys.add(key);
  }

  let withQuality = 0;
  let withGeneric = 0;
  let duplicates = 0;
  let missing = 0;
  let tooLong = 0;

  for (const alt of alts) {
    const trimmed = alt.trim();
    const key = trimmed.toLowerCase();

    if (trimmed.length === 0) {
      missing++;
      continue;
    }

    const isDuplicate = duplicateKeys.has(key);
    const generic = isGenericAlt(trimmed);
    const long = trimmed.length > 125;

    if (isDuplicate) duplicates++;
    if (generic) withGeneric++;
    if (long) tooLong++;

    if (!isDuplicate && !generic && !long && trimmed.length >= 5 && trimmed.length <= 125) {
      withQuality++;
    }
  }

  return {
    total: images.length,
    withQuality,
    withGeneric,
    duplicates,
    missing,
    tooLong,
  };
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

function escapeRegExp(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/**
 * Returns true if any of the given terms appears in `text` as a whole word
 * (bounded by non-word characters). Avoids false positives such as "SEO"
 * matching "Seoul". Comparison is case-insensitive and diacritic-insensitive.
 */
function containsWholeWord(text: string, terms: string[]): boolean {
  const normalizedText = normalize(text);
  for (const term of terms) {
    const t = normalize(term).trim();
    if (!t) continue;
    const re = new RegExp(`\\b${escapeRegExp(t)}\\b`, "i");
    if (re.test(normalizedText)) return true;
  }
  return false;
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
  articleUrl,
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
  const [synonyms, setSynonyms] = useState<string[]>([]);
  const [competitorLoading, setCompetitorLoading] = useState(false);
  const [competitorData, setCompetitorData] = useState<{
    results: Array<{
      rank: number;
      url: string;
      title: string;
      snippet: string;
      word_count: number | null;
      h2_count: number | null;
      meta_description: string | null;
      fetch_error: boolean;
    }>;
    keyword: string;
    median_words: number | null;
    median_h2: number | null;
  } | null>(null);

  const userWordCount = useMemo(() => countWords(content), [content]);

  // Debounced fetch of semantic synonyms for the primary keyword so that
  // matching can span languages/variants (e.g. "SEO" ↔ "référencement").
  useEffect(() => {
    const kw = keyword.trim();
    if (!kw) {
      setSynonyms([]);
      return;
    }

    const controller = new AbortController();
    const timer = setTimeout(async () => {
      try {
        const res = await authFetch("/seo-synonyms/", {
          method: "POST",
          body: JSON.stringify({
            keyword: kw,
            language: i18n.language === "fr" ? "fr" : "en",
          }),
          signal: controller.signal,
        });
        if (!res.ok) return;
        const data: { synonyms?: string[] } = await res.json();
        if (Array.isArray(data.synonyms)) {
          setSynonyms(data.synonyms.filter((s) => typeof s === "string" && s.trim().length > 0));
        }
      } catch {
        // silent — fallback to keyword-only matching
      }
    }, 500);

    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [keyword, i18n.language]);
  const [kwSeed, setKwSeed] = useState("");
  const [kwLoading, setKwLoading] = useState(false);
  const [kwResults, setKwResults] = useState<KeywordResult[] | null>(null);

  const [psiUrl, setPsiUrl] = useState<string>(articleUrl ?? "");
  const [psiLoading, setPsiLoading] = useState<null | "mobile" | "desktop">(null);
  const [psiResult, setPsiResult] = useState<PageSpeedResult | null>(null);

  const checks = useMemo<SEOCheck[]>(() => {
    /*
     * SEO weight rationale (2025 ranking factors)
     * ------------------------------------------------------------------
     * Weights are calibrated against Google's 2025 signal hierarchy, where
     * keyword/intent alignment and content depth (E-E-A-T) dominate, while
     * pure technical basics (meta tags, slug) play a diminished role.
     *
     * The heaviest weight (keyword = 25) reflects that query/intent
     * alignment — the keyword living in the title, intro and H2s — is the
     * single strongest on-page relevance signal Google still relies on in
     * the post-HCU / AI Overview era. Content depth (word count = 15) and
     * title relevance (15) come next, followed by structure (headings 12,
     * internal links 10). Meta description (8), image alt-text (8), cover
     * image (4) and slug (3) are secondary UX/CTR signals rather than
     * direct ranking drivers.
     *
     * Good-state weights sum to exactly 100:
     *   keyword 25 + word-count 15 + title 15 + headings 12 + links 10
     *   + meta 8 + images 8 + cover 4 + slug 3 = 100
     * ------------------------------------------------------------------
     */
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
        score: 8,
      });
    } else if (descLen > 0 && descLen < 120) {
      results.push({
        id: "meta-desc",
        label: "Meta description",
        status: "warning",
        detail: lang === "fr" ? `${descLen}/160 - trop court` : `${descLen}/160 - too short`,
        score: 4,
      });
    } else if (descLen > 160) {
      results.push({
        id: "meta-desc",
        label: "Meta description",
        status: "bad",
        detail: lang === "fr" ? `${descLen}/160 - trop long` : `${descLen}/160 - too long`,
        score: 2,
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
        score: 15,
      });
    } else if (words >= 600) {
      results.push({
        id: "word-count",
        label: lang === "fr" ? "Nombre de mots" : "Word count",
        status: "warning",
        detail: `${words} ${lang === "fr" ? "mots - visez 1000+" : "words - aim for 1000+"}`,
        score: 9,
      });
    } else {
      results.push({
        id: "word-count",
        label: lang === "fr" ? "Nombre de mots" : "Word count",
        status: "bad",
        detail: `${words} ${lang === "fr" ? "mots - trop court" : "words - too short"}`,
        score: 3,
      });
    }

    // Keyword usage (primary keyword in title, first paragraph, H2s)
    // Uses word-boundary regex over keyword + Gemini-generated synonyms to
    // avoid false positives ("SEO" ≠ "Seoul") and false negatives
    // ("SEO" matches "référencement" via synonyms).
    if (keyword.trim()) {
      const terms = [keyword, ...synonyms];
      const titleHit = containsWholeWord(title, terms);
      const introHit = containsWholeWord(firstParagraph(content), terms);
      const h2s = content.match(/^## .+$/gm) || [];
      const h2Hits = h2s.filter((h) => containsWholeWord(h, terms)).length;
      const hits = Number(titleHit) + Number(introHit) + Math.min(h2Hits, 2);

      if (hits >= 3) {
        results.push({
          id: "keyword",
          label: lang === "fr" ? "Mot-clé principal" : "Primary keyword",
          status: "good",
          detail: lang === "fr" ? `Présent dans titre, intro et H2` : `In title, intro and H2`,
          score: 25,
        });
      } else if (hits >= 2) {
        results.push({
          id: "keyword",
          label: lang === "fr" ? "Mot-clé principal" : "Primary keyword",
          status: "warning",
          detail: lang === "fr" ? `Présent dans ${hits}/3 zones clés (titre, intro, H2)` : `In ${hits}/3 key zones`,
          score: 15,
        });
      } else {
        results.push({
          id: "keyword",
          label: lang === "fr" ? "Mot-clé principal" : "Primary keyword",
          status: "bad",
          detail: lang === "fr" ? `Manque dans titre, intro ou H2` : `Missing in title/intro/H2`,
          score: 5,
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
        score: 12,
      });
    } else if (headings.h2 >= 1) {
      results.push({
        id: "headings",
        label: lang === "fr" ? "Structure (H2/H3)" : "Structure (H2/H3)",
        status: "warning",
        detail: lang === "fr" ? `${headings.h2} H2 - ajoutez-en plus` : `${headings.h2} H2 - add more`,
        score: 6,
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

    // Images & alt text (quality-aware)
    const images = analyzeAltTexts(content);
    const imagesLabel = lang === "fr" ? "Images & alt-text" : "Images & alt-text";
    const imgWord = lang === "fr" ? "images" : "images";

    if (images.total === 0) {
      results.push({
        id: "images",
        label: imagesLabel,
        status: "bad",
        detail: lang === "fr" ? "Aucune image" : "No images",
        score: 2,
      });
    } else if (images.withQuality === images.total) {
      // GOOD: all alts are high quality
      results.push({
        id: "images",
        label: imagesLabel,
        status: "good",
        detail:
          lang === "fr"
            ? `${images.total} ${imgWord} — tous avec alt descriptif`
            : `${images.total} ${imgWord} — all with descriptive alt`,
        score: 15,
      });
    } else if (images.withQuality === 0) {
      // BAD: nothing usable — all generic / duplicate / missing / too long
      const parts: string[] = [];
      if (images.missing > 0) {
        parts.push(
          lang === "fr"
            ? `${images.missing} sans alt`
            : `${images.missing} missing alt`
        );
      }
      if (images.withGeneric > 0) {
        parts.push(
          lang === "fr"
            ? `${images.withGeneric} générique${images.withGeneric > 1 ? "s" : ""}`
            : `${images.withGeneric} generic`
        );
      }
      if (images.duplicates > 0) {
        parts.push(
          lang === "fr"
            ? `${images.duplicates} doublon${images.duplicates > 1 ? "s" : ""}`
            : `${images.duplicates} duplicate${images.duplicates > 1 ? "s" : ""}`
        );
      }
      if (images.tooLong > 0) {
        parts.push(
          lang === "fr"
            ? `${images.tooLong} trop long${images.tooLong > 1 ? "s" : ""}`
            : `${images.tooLong} too long`
        );
      }
      results.push({
        id: "images",
        label: imagesLabel,
        status: "bad",
        detail: `${images.total} ${imgWord} — ${parts.join(", ")}`,
        score: 2,
      });
    } else {
      // WARNING: some quality, but generic/duplicate/tooLong/missing present
      const parts: string[] = [];
      if (images.missing > 0) {
        parts.push(
          lang === "fr"
            ? `${images.missing} sans alt`
            : `${images.missing} missing alt`
        );
      }
      if (images.withGeneric > 0) {
        parts.push(
          lang === "fr"
            ? `${images.withGeneric} générique${images.withGeneric > 1 ? "s" : ""}`
            : `${images.withGeneric} generic`
        );
      }
      if (images.duplicates > 0) {
        parts.push(
          lang === "fr"
            ? `${images.duplicates} doublon${images.duplicates > 1 ? "s" : ""}`
            : `${images.duplicates} duplicate${images.duplicates > 1 ? "s" : ""}`
        );
      }
      if (images.tooLong > 0) {
        parts.push(
          lang === "fr"
            ? `${images.tooLong} trop long${images.tooLong > 1 ? "s" : ""}`
            : `${images.tooLong} too long`
        );
      }
      results.push({
        id: "images",
        label: imagesLabel,
        status: "warning",
        detail: `${images.total} ${imgWord} — ${parts.join(", ")}`,
        score: 8,
      });
    }

    // Cover image
    if (coverImage) {
      results.push({
        id: "cover",
        label: lang === "fr" ? "Image de couverture" : "Cover image",
        status: "good",
        detail: "OK",
        score: 4,
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
        score: 3,
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
        score: 1,
      });
    }

    return results;
  }, [title, excerpt, content, slug, coverImage, keyword, synonyms, i18n.language]);

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

  const handleCompetitorAnalysis = async () => {
    if (!keyword.trim()) return;
    setCompetitorLoading(true);
    try {
      const { authFetch } = await import("@/lib/api-client");
      const res = await authFetch("/competitors/", {
        method: "POST",
        body: JSON.stringify({
          keyword: keyword.trim(),
          language: i18n.language,
        }),
      });
      if (!res.ok) throw new Error("Competitor analysis failed");
      const data = await res.json();
      setCompetitorData(data);
    } catch {
      toast.error(
        i18n.language === "fr"
          ? "Erreur analyse concurrence"
          : "Competitor analysis error"
      );
    } finally {
      setCompetitorLoading(false);
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

  const runPageSpeed = async (strategy: "mobile" | "desktop") => {
    const target = (articleUrl ?? psiUrl).trim();
    if (!target) {
      toast.error(
        i18n.language === "fr" ? "URL requise" : "URL required"
      );
      return;
    }
    if (!/^https?:\/\//i.test(target)) {
      toast.error(
        i18n.language === "fr"
          ? "URL invalide (http:// ou https://)"
          : "Invalid URL (http:// or https://)"
      );
      return;
    }

    setPsiLoading(strategy);
    try {
      const { authFetch } = await import("@/lib/api-client");
      const res = await authFetch("/page-speed/", {
        method: "POST",
        body: JSON.stringify({ url: target, strategy }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error || "PageSpeed failed");
      }
      const data: PageSpeedResult = await res.json();
      setPsiResult(data);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "PageSpeed error";
      toast.error(
        i18n.language === "fr" ? `Erreur PageSpeed: ${msg}` : `PageSpeed error: ${msg}`
      );
    } finally {
      setPsiLoading(null);
    }
  };

  const lcpColor = (v: number | null) => {
    if (v === null) return "text-muted-foreground";
    if (v <= 2.5) return "text-green-500";
    if (v <= 4) return "text-yellow-500";
    return "text-red-500";
  };
  const lcpBg = (v: number | null) => {
    if (v === null) return "bg-muted";
    if (v <= 2.5) return "bg-green-500/10";
    if (v <= 4) return "bg-yellow-500/10";
    return "bg-red-500/10";
  };
  const clsColor = (v: number | null) => {
    if (v === null) return "text-muted-foreground";
    if (v <= 0.1) return "text-green-500";
    if (v <= 0.25) return "text-yellow-500";
    return "text-red-500";
  };
  const clsBg = (v: number | null) => {
    if (v === null) return "bg-muted";
    if (v <= 0.1) return "bg-green-500/10";
    if (v <= 0.25) return "bg-yellow-500/10";
    return "bg-red-500/10";
  };
  const fcpColor = (v: number | null) => {
    if (v === null) return "text-muted-foreground";
    if (v <= 1.8) return "text-green-500";
    if (v <= 3) return "text-yellow-500";
    return "text-red-500";
  };
  const fcpBg = (v: number | null) => {
    if (v === null) return "bg-muted";
    if (v <= 1.8) return "bg-green-500/10";
    if (v <= 3) return "bg-yellow-500/10";
    return "bg-red-500/10";
  };
  const scoreCircleColor = (v: number | null) => {
    if (v === null) return "text-muted-foreground bg-muted";
    if (v >= 90) return "text-green-500 bg-green-500/10";
    if (v >= 50) return "text-yellow-500 bg-yellow-500/10";
    return "text-red-500 bg-red-500/10";
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

      {/* Core Web Vitals */}
      <Card>
        <CardHeader className="py-3 px-4">
          <CardTitle className="text-sm flex items-center gap-2">
            <Gauge className="h-4 w-4" />
            {i18n.language === "fr" ? "Core Web Vitals" : "Core Web Vitals"}
          </CardTitle>
        </CardHeader>
        <CardContent className="px-4 pb-4 space-y-3">
          {!articleUrl && (
            <Input
              type="url"
              placeholder="https://exemple.com/mon-article"
              value={psiUrl}
              onChange={(e) => setPsiUrl(e.target.value)}
              className="text-sm"
            />
          )}
          {articleUrl && (
            <p className="text-xs text-muted-foreground break-all">
              {articleUrl}
            </p>
          )}
          <div className="flex gap-2 flex-wrap">
            <Button
              size="sm"
              variant="outline"
              onClick={() => runPageSpeed("mobile")}
              disabled={psiLoading !== null}
            >
              {psiLoading === "mobile" ? (
                <Loader2 className="h-4 w-4 mr-1.5 animate-spin" />
              ) : (
                <Smartphone className="h-4 w-4 mr-1.5" />
              )}
              {i18n.language === "fr" ? "Tester mobile" : "Test mobile"}
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => runPageSpeed("desktop")}
              disabled={psiLoading !== null}
            >
              {psiLoading === "desktop" ? (
                <Loader2 className="h-4 w-4 mr-1.5 animate-spin" />
              ) : (
                <Monitor className="h-4 w-4 mr-1.5" />
              )}
              {i18n.language === "fr" ? "Tester desktop" : "Test desktop"}
            </Button>
          </div>

          {psiResult && (
            <div className="space-y-3 pt-2 border-t">
              <p className="text-xs text-muted-foreground">
                {i18n.language === "fr" ? "Strategie" : "Strategy"}:{" "}
                <span className="font-medium">{psiResult.strategy}</span>
              </p>

              {/* Metric cards */}
              <div className="grid grid-cols-3 gap-2">
                <div className={`rounded-lg p-3 text-center ${lcpBg(psiResult.lcp_s)}`}>
                  <p className="text-[10px] uppercase tracking-wide text-muted-foreground">
                    LCP
                  </p>
                  <p className={`text-lg font-bold ${lcpColor(psiResult.lcp_s)}`}>
                    {psiResult.lcp_s !== null ? `${psiResult.lcp_s}s` : "—"}
                  </p>
                </div>
                <div className={`rounded-lg p-3 text-center ${clsBg(psiResult.cls)}`}>
                  <p className="text-[10px] uppercase tracking-wide text-muted-foreground">
                    CLS
                  </p>
                  <p className={`text-lg font-bold ${clsColor(psiResult.cls)}`}>
                    {psiResult.cls !== null ? psiResult.cls.toFixed(3) : "—"}
                  </p>
                </div>
                <div className={`rounded-lg p-3 text-center ${fcpBg(psiResult.fcp_s)}`}>
                  <p className="text-[10px] uppercase tracking-wide text-muted-foreground">
                    FCP
                  </p>
                  <p className={`text-lg font-bold ${fcpColor(psiResult.fcp_s)}`}>
                    {psiResult.fcp_s !== null ? `${psiResult.fcp_s}s` : "—"}
                  </p>
                </div>
              </div>

              {/* Score circles */}
              <div className="grid grid-cols-3 gap-2">
                <div className="flex flex-col items-center gap-1">
                  <div
                    className={`w-14 h-14 rounded-full flex items-center justify-center font-bold text-sm ${scoreCircleColor(
                      psiResult.performance_score
                    )}`}
                  >
                    {psiResult.performance_score ?? "—"}
                  </div>
                  <p className="text-[10px] text-muted-foreground">
                    {i18n.language === "fr" ? "Performance" : "Performance"}
                  </p>
                </div>
                <div className="flex flex-col items-center gap-1">
                  <div
                    className={`w-14 h-14 rounded-full flex items-center justify-center font-bold text-sm ${scoreCircleColor(
                      psiResult.seo_score
                    )}`}
                  >
                    {psiResult.seo_score ?? "—"}
                  </div>
                  <p className="text-[10px] text-muted-foreground">SEO</p>
                </div>
                <div className="flex flex-col items-center gap-1">
                  <div
                    className={`w-14 h-14 rounded-full flex items-center justify-center font-bold text-sm ${scoreCircleColor(
                      psiResult.a11y_score
                    )}`}
                  >
                    {psiResult.a11y_score ?? "—"}
                  </div>
                  <p className="text-[10px] text-muted-foreground">
                    {i18n.language === "fr" ? "Accessibilite" : "Accessibility"}
                  </p>
                </div>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

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

      {/* Competitor Analysis */}
      <Card>
        <CardHeader className="py-3 px-4">
          <CardTitle className="text-sm flex items-center gap-2">
            <Users className="h-4 w-4" />
            {i18n.language === "fr"
              ? "Analyse de la concurrence"
              : "Competitor analysis"}
          </CardTitle>
        </CardHeader>
        <CardContent className="px-4 pb-4 space-y-3">
          <Button
            size="sm"
            variant="outline"
            onClick={handleCompetitorAnalysis}
            disabled={competitorLoading || !keyword.trim()}
          >
            {competitorLoading ? (
              <>
                <Loader2 className="h-4 w-4 mr-1.5 animate-spin" />
                {i18n.language === "fr"
                  ? "Analyse en cours..."
                  : "Analyzing..."}
              </>
            ) : (
              <>
                <Users className="h-4 w-4 mr-1.5" />
                {i18n.language === "fr"
                  ? "Analyser le top 10"
                  : "Analyze top 10"}
              </>
            )}
          </Button>

          {!keyword.trim() && (
            <p className="text-xs text-muted-foreground">
              {i18n.language === "fr"
                ? "Definissez un mot-cle principal pour activer l'analyse."
                : "Set a primary keyword to enable analysis."}
            </p>
          )}

          {competitorData && (
            <div className="space-y-3 pt-2 border-t">
              {competitorData.median_words !== null && (
                <div
                  className={`text-xs p-2 rounded ${
                    userWordCount >= competitorData.median_words
                      ? "bg-green-500/10 text-green-600 dark:text-green-400"
                      : "bg-yellow-500/10 text-yellow-600 dark:text-yellow-400"
                  }`}
                >
                  {i18n.language === "fr"
                    ? `Votre article fait ${userWordCount} mots, la mediane est ${competitorData.median_words} — vous etes ${
                        userWordCount >= competitorData.median_words
                          ? "au-dessus"
                          : "sous"
                      }`
                    : `Your article is ${userWordCount} words, median is ${competitorData.median_words} — you are ${
                        userWordCount >= competitorData.median_words
                          ? "above"
                          : "below"
                      }`}
                </div>
              )}

              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="border-b text-left text-muted-foreground">
                      <th className="py-1.5 pr-2 font-medium">#</th>
                      <th className="py-1.5 pr-2 font-medium">
                        {i18n.language === "fr" ? "Titre" : "Title"}
                      </th>
                      <th className="py-1.5 pr-2 font-medium text-right">
                        {i18n.language === "fr" ? "Mots" : "Words"}
                      </th>
                      <th className="py-1.5 font-medium text-right">H2</th>
                    </tr>
                  </thead>
                  <tbody>
                    {competitorData.results.map((r) => {
                      const isBehind =
                        r.word_count !== null &&
                        userWordCount < r.word_count;
                      return (
                        <tr
                          key={r.rank}
                          className={`border-b last:border-0 ${
                            isBehind ? "bg-red-500/10 text-red-600 dark:text-red-400" : ""
                          }`}
                        >
                          <td className="py-1.5 pr-2 align-top">{r.rank}</td>
                          <td className="py-1.5 pr-2 align-top max-w-[220px]">
                            <a
                              href={r.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="inline-flex items-center gap-1 hover:underline truncate max-w-full"
                              title={r.title}
                            >
                              <span className="truncate">
                                {r.title || r.url}
                              </span>
                              <ExternalLink className="h-3 w-3 shrink-0" />
                            </a>
                          </td>
                          <td className="py-1.5 pr-2 align-top text-right">
                            {r.fetch_error || r.word_count === null
                              ? "—"
                              : r.word_count}
                          </td>
                          <td className="py-1.5 align-top text-right">
                            {r.fetch_error || r.h2_count === null
                              ? "—"
                              : r.h2_count}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              {competitorData.median_h2 !== null && (
                <p className="text-xs text-muted-foreground">
                  {i18n.language === "fr"
                    ? `Mediane H2: ${competitorData.median_h2}`
                    : `Median H2: ${competitorData.median_h2}`}
                </p>
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
