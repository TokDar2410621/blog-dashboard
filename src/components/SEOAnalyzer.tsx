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
  GitCompare,
  Link as LinkIcon,
  Code2,
  Copy,
  BarChart3,
} from "lucide-react";
import { Link as RouterLink } from "react-router-dom";
import {
  authFetch,
  fetchSEOSuggestions,
  fetchGSCOAuthUrl,
  fetchGSCQueries,
  ApiError,
  type GSCQueryRow,
} from "@/lib/api-client";
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
  siteId?: number;
  currentSlug?: string;
  author?: string;
  publishedAt?: string;
  siteDomain?: string;
  language?: string;
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

interface CannibalizationPair {
  slug_a: string;
  slug_b: string;
  title_a: string;
  title_b: string;
  language: string;
  similarity: number;
  reason: string;
}

interface LinkSuggestion {
  slug: string;
  title: string;
  anchor_text: string;
  insert_hint: string;
  reason: string;
}

interface BacklinkDomain {
  domain: string;
  mentions: number;
  sample_url: string;
}

interface BacklinkResult {
  total_referring_domains: number;
  top_domains: BacklinkDomain[];
  raw_count: number;
  warning: string;
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
  siteId,
  currentSlug,
  author,
  publishedAt,
  siteDomain,
  language,
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
  const [cannibPairs, setCannibPairs] = useState<CannibalizationPair[] | null>(null);
  const [cannibLoading, setCannibLoading] = useState(false);

  useEffect(() => {
    if (!siteId) return;
    let cancelled = false;
    setCannibLoading(true);
    (async () => {
      try {
        const { authFetch } = await import("@/lib/api-client");
        const res = await authFetch(`/sites/${siteId}/cannibalization/`);
        if (!res.ok) throw new Error("Failed");
        const data = await res.json();
        if (!cancelled) setCannibPairs(data.pairs || []);
      } catch {
        if (!cancelled) setCannibPairs([]);
      } finally {
        if (!cancelled) setCannibLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [siteId]);

  const relevantCannibPairs = useMemo(() => {
    if (!cannibPairs || !currentSlug) return [];
    return cannibPairs.filter(
      (p) => p.slug_a === currentSlug || p.slug_b === currentSlug
    );
  }, [cannibPairs, currentSlug]);

  const [linkLoading, setLinkLoading] = useState(false);
  const [linkSuggestions, setLinkSuggestions] = useState<LinkSuggestion[] | null>(null);

  const [backlinksLoading, setBacklinksLoading] = useState(false);
  const [backlinks, setBacklinks] = useState<BacklinkResult | null>(null);
  const [backlinksError, setBacklinksError] = useState<string | null>(null);

  const [schemaLoading, setSchemaLoading] = useState(false);
  const [schema, setSchema] = useState<{
    schema_type: string;
    script_tag: string;
    jsonld?: unknown;
    warning?: string;
  } | null>(null);

  // --- Search Console (real perf) state ---
  const [gscLoading, setGscLoading] = useState(false);
  const [gscQueries, setGscQueries] = useState<GSCQueryRow[] | null>(null);
  const [gscNeedsAuth, setGscNeedsAuth] = useState(false);
  const [gscError, setGscError] = useState<string | null>(null);
  const [gscConnecting, setGscConnecting] = useState(false);

  const canFetchGsc = !!siteId && !!slug;

  useEffect(() => {
    if (!canFetchGsc) return;
    let cancelled = false;
    setGscLoading(true);
    setGscError(null);
    setGscNeedsAuth(false);
    fetchGSCQueries(siteId as number, slug)
      .then((data) => {
        if (cancelled) return;
        setGscQueries(data.queries);
      })
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 401) {
          setGscNeedsAuth(true);
          setGscQueries(null);
        } else if (err instanceof ApiError) {
          setGscError(err.message || "Search Console error");
          setGscQueries(null);
        } else {
          setGscError("Search Console error");
          setGscQueries(null);
        }
      })
      .finally(() => {
        if (!cancelled) setGscLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [canFetchGsc, siteId, slug]);

  const handleConnectGsc = async () => {
    if (!siteId) return;
    setGscConnecting(true);
    try {
      const { url } = await fetchGSCOAuthUrl(siteId);
      window.open(url, "_blank", "noopener,noreferrer");
    } catch (err) {
      const msg =
        err instanceof ApiError
          ? err.message
          : i18n.language === "fr"
            ? "Impossible d'obtenir l'URL OAuth"
            : "Failed to get OAuth URL";
      toast.error(msg);
    } finally {
      setGscConnecting(false);
    }
  };

  // Real perf score: capped(clicks * 2 + impressions / 100, 100).
  const gscPerfScore = useMemo(() => {
    if (!gscQueries || gscQueries.length === 0) return 0;
    const totalClicks = gscQueries.reduce((s, q) => s + q.clicks, 0);
    const totalImpr = gscQueries.reduce((s, q) => s + q.impressions, 0);
    const raw = totalClicks * 2 + totalImpr / 100;
    return Math.min(100, Math.round(raw));
  }, [gscQueries]);

  const sortedGscQueries = useMemo(() => {
    if (!gscQueries) return [];
    return [...gscQueries].sort((a, b) => b.clicks - a.clicks);
  }, [gscQueries]);

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

  const [fixingItem, setFixingItem] = useState<string | null>(null);

  const handleFixSingle = async (issue: string, kind: "weakness" | "action") => {
    if (!onApplyFix) return;
    const itemKey = `${kind}:${issue}`;
    setFixingItem(itemKey);
    try {
      const { authFetch } = await import("@/lib/api-client");
      const lang = language || i18n.language || "fr";
      const auditCtx = aiAudit
        ? `Score actuel: ${aiAudit.score}/100. Verdict: ${aiAudit.verdict}.`
        : "";
      const issueLabel =
        kind === "weakness"
          ? `Faiblesse a corriger: ${issue}`
          : `Action a appliquer: ${issue}`;
      const res = await authFetch("/seo-fix/", {
        method: "POST",
        body: JSON.stringify({
          title,
          excerpt,
          content: content.slice(0, 4000),
          issues: issueLabel,
          language: lang,
          keyword: keyword || undefined,
          audit_context: auditCtx || undefined,
        }),
      });
      if (!res.ok) throw new Error("Erreur");
      const data = await res.json();
      onApplyFix({
        title: data.title || undefined,
        excerpt: data.excerpt || undefined,
        content: data.content || undefined,
      });
      toast.success(
        i18n.language === "fr" ? "Correction appliquée" : "Fix applied"
      );
    } catch {
      toast.error(
        i18n.language === "fr" ? "Erreur correction" : "Fix error"
      );
    } finally {
      setFixingItem(null);
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

      // Build competitor summary (if the user ran the competitor analysis)
      let competitorSummary = "";
      if (competitorData) {
        const medianW = competitorData.median_words;
        const medianH2 = competitorData.median_h2;
        const topTitles = competitorData.results
          .slice(0, 5)
          .filter((r) => !r.fetch_error)
          .map((r) => `  - "${r.title}" (${r.word_count ?? "?"} mots, ${r.h2_count ?? "?"} H2)`)
          .join("\n");
        competitorSummary = `Top SERP for this keyword (median ${medianW ?? "?"} words, ${medianH2 ?? "?"} H2):\n${topTitles}`;
      }

      // Build audit context (if the user ran the AI audit)
      let auditContext = "";
      if (aiAudit) {
        auditContext = [
          `AI audit score: ${aiAudit.score}/100`,
          `Verdict: ${aiAudit.verdict}`,
          aiAudit.weaknesses?.length
            ? `Weaknesses:\n${aiAudit.weaknesses.map((w) => `- ${w}`).join("\n")}`
            : "",
          aiAudit.actions?.length
            ? `Actions:\n${aiAudit.actions.map((a) => `- ${a}`).join("\n")}`
            : "",
        ]
          .filter(Boolean)
          .join("\n\n");
      }

      // Prefer the article's own language (prop) over the UI language
      const lang = language || i18n.language || "fr";

      const res = await authFetch("/seo-fix/", {
        method: "POST",
        body: JSON.stringify({
          title,
          excerpt,
          content: content.slice(0, 4000),
          issues,
          language: lang,
          keyword: keyword || undefined,
          competitor_summary: competitorSummary || undefined,
          audit_context: auditContext || undefined,
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

  const handleLinkSuggest = async () => {
    if (!siteId) return;
    setLinkLoading(true);
    try {
      const { authFetch } = await import("@/lib/api-client");
      const res = await authFetch(`/sites/${siteId}/link-suggestions/`, {
        method: "POST",
        body: JSON.stringify({
          title,
          content,
          current_slug: currentSlug || "",
          language: i18n.language,
        }),
      });
      if (!res.ok) throw new Error("Link suggestions failed");
      const data = await res.json();
      setLinkSuggestions(data.suggestions || []);
    } catch {
      toast.error(
        i18n.language === "fr"
          ? "Erreur suggestions de liens"
          : "Link suggestions error"
      );
    } finally {
      setLinkLoading(false);
    }
  };

  const copyMarkdownLink = (anchor: string, linkSlug: string) => {
    const md = `[${anchor}](/${linkSlug})`;
    navigator.clipboard.writeText(md);
    toast.success(
      i18n.language === "fr" ? "Markdown copie!" : "Markdown copied!"
    );
  };

  const handleBacklinks = async () => {
    if (!articleUrl) return;
    setBacklinksLoading(true);
    setBacklinksError(null);
    try {
      const { authFetch } = await import("@/lib/api-client");
      const res = await authFetch("/backlinks/", {
        method: "POST",
        body: JSON.stringify({ url: articleUrl }),
      });
      const data = await res.json();
      if (!res.ok) {
        setBacklinksError(
          data?.error ||
            (i18n.language === "fr"
              ? "Erreur lors de la recherche"
              : "Lookup failed")
        );
        if (data?.warning) {
          setBacklinks({
            total_referring_domains: 0,
            top_domains: [],
            raw_count: 0,
            warning: data.warning,
          });
        }
        return;
      }
      setBacklinks(data);
    } catch {
      setBacklinksError(
        i18n.language === "fr" ? "Erreur reseau" : "Network error"
      );
    } finally {
      setBacklinksLoading(false);
    }
  };

  const handleGenerateSchema = async () => {
    setSchemaLoading(true);
    try {
      const { authFetch } = await import("@/lib/api-client");
      const res = await authFetch("/seo-schema/", {
        method: "POST",
        body: JSON.stringify({
          title,
          excerpt,
          content,
          author: author || "",
          cover_image: coverImage || "",
          published_at: publishedAt || "",
          site_domain: siteDomain || "",
          slug,
          language: language || i18n.language,
        }),
      });
      if (!res.ok) throw new Error("Schema failed");
      const data = await res.json();
      setSchema(data);
      if (data.warning) {
        toast.warning(
          i18n.language === "fr"
            ? "Schema genere sans detection IA"
            : "Schema generated without AI detection"
        );
      }
    } catch {
      toast.error(
        i18n.language === "fr"
          ? "Erreur generation du schema"
          : "Error generating schema"
      );
    } finally {
      setSchemaLoading(false);
    }
  };

  const handleCopySchema = () => {
    if (!schema) return;
    navigator.clipboard.writeText(schema.script_tag);
    toast.success(i18n.language === "fr" ? "Copie!" : "Copied!");
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
      {/* Cannibalization */}
      {siteId && currentSlug && (
        <Card>
          <CardHeader className="py-3 px-4">
            <CardTitle className="text-sm flex items-center gap-2">
              <GitCompare className="h-4 w-4" />
              {i18n.language === "fr" ? "Cannibalisation" : "Cannibalization"}
            </CardTitle>
          </CardHeader>
          <CardContent className="px-4 pb-4 space-y-2">
            {cannibLoading ? (
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                {i18n.language === "fr" ? "Analyse en cours..." : "Analyzing..."}
              </div>
            ) : relevantCannibPairs.length === 0 ? (
              <p className="text-xs text-muted-foreground flex items-center gap-1.5">
                <CheckCircle className="h-3.5 w-3.5 text-green-500" />
                {i18n.language === "fr"
                  ? "Aucun conflit détecté ✅"
                  : "No conflict detected ✅"}
              </p>
            ) : (
              <div className="space-y-2">
                <p className="text-xs font-semibold text-red-500 flex items-center gap-1.5">
                  <AlertTriangle className="h-3.5 w-3.5" />
                  {i18n.language === "fr"
                    ? `${relevantCannibPairs.length} article(s) en conflit`
                    : `${relevantCannibPairs.length} conflicting article(s)`}
                </p>
                <ul className="space-y-1.5">
                  {relevantCannibPairs.map((p, i) => {
                    const otherSlug = p.slug_a === currentSlug ? p.slug_b : p.slug_a;
                    const otherTitle = p.slug_a === currentSlug ? p.title_b : p.title_a;
                    return (
                      <li
                        key={i}
                        className="text-xs p-2 rounded border border-red-500/30 bg-red-500/5"
                      >
                        <div className="flex items-start justify-between gap-2">
                          <div className="min-w-0 flex-1">
                            <p className="font-medium truncate">{otherTitle}</p>
                            <p className="text-muted-foreground truncate">
                              /{otherSlug}
                            </p>
                            <p className="text-muted-foreground mt-0.5">
                              {p.reason}
                            </p>
                          </div>
                          <span className="text-red-500 font-semibold whitespace-nowrap">
                            {Math.round(p.similarity * 100)}%
                          </span>
                        </div>
                      </li>
                    );
                  })}
                </ul>
              </div>
            )}
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
                  <ul className="text-xs space-y-1.5">
                    {aiAudit.weaknesses.map((w, i) => {
                      const key = `weakness:${w}`;
                      const busy = fixingItem === key;
                      return (
                        <li
                          key={i}
                          className="flex items-start gap-2 group"
                        >
                          <span className="text-muted-foreground flex-1">
                            • {w}
                          </span>
                          {onApplyFix && (
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-6 px-2 text-xs shrink-0 opacity-70 group-hover:opacity-100"
                              disabled={busy || fixingItem !== null}
                              onClick={() => handleFixSingle(w, "weakness")}
                            >
                              {busy ? (
                                <Loader2 className="h-3 w-3 animate-spin" />
                              ) : (
                                <>
                                  <Wand2 className="h-3 w-3 mr-1" />
                                  {i18n.language === "fr" ? "Corriger" : "Fix"}
                                </>
                              )}
                            </Button>
                          )}
                        </li>
                      );
                    })}
                  </ul>
                </div>
              )}

              {aiAudit.actions?.length > 0 && (
                <div>
                  <p className="text-xs font-semibold mb-1 text-primary">
                    → {i18n.language === "fr" ? "Actions à faire" : "Action items"}
                  </p>
                  <ul className="text-xs space-y-1.5">
                    {aiAudit.actions.map((a, i) => {
                      const key = `action:${a}`;
                      const busy = fixingItem === key;
                      return (
                        <li
                          key={i}
                          className="flex items-start gap-2 group"
                        >
                          <span className="text-muted-foreground flex-1">
                            • {a}
                          </span>
                          {onApplyFix && (
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-6 px-2 text-xs shrink-0 opacity-70 group-hover:opacity-100"
                              disabled={busy || fixingItem !== null}
                              onClick={() => handleFixSingle(a, "action")}
                            >
                              {busy ? (
                                <Loader2 className="h-3 w-3 animate-spin" />
                              ) : (
                                <>
                                  <Wand2 className="h-3 w-3 mr-1" />
                                  {i18n.language === "fr" ? "Appliquer" : "Apply"}
                                </>
                              )}
                            </Button>
                          )}
                        </li>
                      );
                    })}
                  </ul>
                </div>
              )}

              {onApplyFix && (aiAudit.weaknesses?.length > 0 || aiAudit.actions?.length > 0) && (
                <div className="pt-2 border-t">
                  <Button
                    variant="default"
                    size="sm"
                    onClick={handleFixAll}
                    disabled={fixLoading || fixingItem !== null}
                    className="w-full"
                  >
                    {fixLoading ? (
                      <>
                        <Loader2 className="h-4 w-4 mr-1.5 animate-spin" />
                        {i18n.language === "fr" ? "Correction en cours..." : "Fixing..."}
                      </>
                    ) : (
                      <>
                        <Wand2 className="h-4 w-4 mr-1.5" />
                        {i18n.language === "fr"
                          ? "Tout corriger en une fois"
                          : "Fix everything at once"}
                      </>
                    )}
                  </Button>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Backlinks */}
      <Card>
        <CardHeader className="py-3 px-4">
          <CardTitle className="text-sm flex items-center gap-2">
            <LinkIcon className="h-4 w-4" />
            {i18n.language === "fr" ? "Backlinks" : "Backlinks"}
          </CardTitle>
        </CardHeader>
        <CardContent className="px-4 pb-4 space-y-3">
          {!articleUrl && (
            <p className="text-xs text-muted-foreground">
              {i18n.language === "fr"
                ? "Publiez d'abord l'article et renseignez un domaine de site pour verifier les backlinks."
                : "Publish the article and set a site domain first to check backlinks."}
            </p>
          )}
          <Button
            size="sm"
            variant="outline"
            onClick={handleBacklinks}
            disabled={backlinksLoading || !articleUrl}
          >
            {backlinksLoading ? (
              <>
                <Loader2 className="h-4 w-4 mr-1.5 animate-spin" />
                {i18n.language === "fr" ? "Recherche..." : "Searching..."}
              </>
            ) : (
              <>
                <LinkIcon className="h-4 w-4 mr-1.5" />
                {i18n.language === "fr"
                  ? "Verifier les backlinks"
                  : "Check backlinks"}
              </>
            )}
          </Button>

          {articleUrl && (
            <p className="text-[10px] text-muted-foreground break-all">
              {i18n.language === "fr" ? "URL analysee : " : "URL: "}
              {articleUrl}
            </p>
          )}

          {backlinksError && (
            <p className="text-xs text-red-500">{backlinksError}</p>
          )}

          {backlinks && (
            <div className="space-y-3 pt-2 border-t">
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 rounded-full flex items-center justify-center font-bold bg-primary/10 text-primary">
                  {backlinks.total_referring_domains}
                </div>
                <p className="text-sm text-muted-foreground flex-1">
                  {i18n.language === "fr"
                    ? `domaines referents trouves (${backlinks.raw_count} resultats bruts)`
                    : `referring domains found (${backlinks.raw_count} raw results)`}
                </p>
              </div>

              {backlinks.top_domains.length > 0 && (
                <div>
                  <p className="text-xs font-semibold mb-1">
                    {i18n.language === "fr" ? "Top domaines" : "Top domains"}
                  </p>
                  <ul className="text-xs space-y-1">
                    {backlinks.top_domains.slice(0, 5).map((d) => (
                      <li
                        key={d.domain}
                        className="flex items-center justify-between gap-2 border-b pb-1 last:border-0"
                      >
                        <a
                          href={d.sample_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="truncate hover:underline text-primary"
                          title={d.sample_url}
                        >
                          {d.domain}
                        </a>
                        <span className="text-muted-foreground whitespace-nowrap">
                          {d.mentions}{" "}
                          {i18n.language === "fr" ? "mention(s)" : "mention(s)"}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {backlinks.top_domains.length === 0 && !backlinksError && (
                <p className="text-xs text-muted-foreground">
                  {i18n.language === "fr"
                    ? "Aucun domaine referent detecte."
                    : "No referring domains detected."}
                </p>
              )}

              {backlinks.warning && (
                <p className="text-[11px] text-yellow-600 dark:text-yellow-500 flex items-start gap-1">
                  <AlertTriangle className="h-3 w-3 mt-0.5 flex-shrink-0" />
                  <span>{backlinks.warning}</span>
                </p>
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

      {/* Backlinks */}
      <Card>
        <CardHeader className="py-3 px-4">
          <CardTitle className="text-sm flex items-center gap-2">
            <LinkIcon className="h-4 w-4" />
            {i18n.language === "fr" ? "Backlinks" : "Backlinks"}
          </CardTitle>
        </CardHeader>
        <CardContent className="px-4 pb-4 space-y-3">
          {!articleUrl && (
            <p className="text-xs text-muted-foreground">
              {i18n.language === "fr"
                ? "Publiez d'abord l'article et renseignez un domaine de site pour verifier les backlinks."
                : "Publish the article and set a site domain first to check backlinks."}
            </p>
          )}
          <Button
            size="sm"
            variant="outline"
            onClick={handleBacklinks}
            disabled={backlinksLoading || !articleUrl}
          >
            {backlinksLoading ? (
              <>
                <Loader2 className="h-4 w-4 mr-1.5 animate-spin" />
                {i18n.language === "fr" ? "Recherche..." : "Searching..."}
              </>
            ) : (
              <>
                <LinkIcon className="h-4 w-4 mr-1.5" />
                {i18n.language === "fr"
                  ? "Verifier les backlinks"
                  : "Check backlinks"}
              </>
            )}
          </Button>

          {articleUrl && (
            <p className="text-[10px] text-muted-foreground break-all">
              {i18n.language === "fr" ? "URL analysee : " : "URL: "}
              {articleUrl}
            </p>
          )}

          {backlinksError && (
            <p className="text-xs text-red-500">{backlinksError}</p>
          )}

          {backlinks && (
            <div className="space-y-3 pt-2 border-t">
              <div className="flex items-center gap-3">
                <div className="w-12 h-12 rounded-full flex items-center justify-center font-bold bg-primary/10 text-primary">
                  {backlinks.total_referring_domains}
                </div>
                <p className="text-sm text-muted-foreground flex-1">
                  {i18n.language === "fr"
                    ? `domaines referents trouves (${backlinks.raw_count} resultats bruts)`
                    : `referring domains found (${backlinks.raw_count} raw results)`}
                </p>
              </div>

              {backlinks.top_domains.length > 0 && (
                <div>
                  <p className="text-xs font-semibold mb-1">
                    {i18n.language === "fr" ? "Top domaines" : "Top domains"}
                  </p>
                  <ul className="text-xs space-y-1">
                    {backlinks.top_domains.slice(0, 5).map((d) => (
                      <li
                        key={d.domain}
                        className="flex items-center justify-between gap-2 border-b pb-1 last:border-0"
                      >
                        <a
                          href={d.sample_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="truncate hover:underline text-primary"
                          title={d.sample_url}
                        >
                          {d.domain}
                        </a>
                        <span className="text-muted-foreground whitespace-nowrap">
                          {d.mentions}{" "}
                          {i18n.language === "fr" ? "mention(s)" : "mention(s)"}
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {backlinks.top_domains.length === 0 && !backlinksError && (
                <p className="text-xs text-muted-foreground">
                  {i18n.language === "fr"
                    ? "Aucun domaine referent detecte."
                    : "No referring domains detected."}
                </p>
              )}

              {backlinks.warning && (
                <p className="text-[11px] text-yellow-600 dark:text-yellow-500 flex items-start gap-1">
                  <AlertTriangle className="h-3 w-3 mt-0.5 flex-shrink-0" />
                  <span>{backlinks.warning}</span>
                </p>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Internal Link Suggestions */}
      <Card>
        <CardHeader className="py-3 px-4">
          <CardTitle className="text-sm flex items-center gap-2">
            <LinkIcon className="h-4 w-4" />
            {i18n.language === "fr"
              ? "Suggestions de liens internes"
              : "Internal link suggestions"}
          </CardTitle>
        </CardHeader>
        <CardContent className="px-4 pb-4 space-y-3">
          <Button
            size="sm"
            variant="outline"
            onClick={handleLinkSuggest}
            disabled={linkLoading || !siteId || !content.trim()}
          >
            {linkLoading ? (
              <>
                <Loader2 className="h-4 w-4 mr-1.5 animate-spin" />
                {i18n.language === "fr" ? "Analyse..." : "Analyzing..."}
              </>
            ) : (
              <>
                <LinkIcon className="h-4 w-4 mr-1.5" />
                {i18n.language === "fr" ? "Suggerer des liens" : "Suggest links"}
              </>
            )}
          </Button>

          {linkSuggestions && linkSuggestions.length === 0 && (
            <p className="text-xs text-muted-foreground">
              {i18n.language === "fr"
                ? "Aucune suggestion pertinente trouvee."
                : "No relevant suggestions found."}
            </p>
          )}

          {linkSuggestions && linkSuggestions.length > 0 && (
            <div className="space-y-2">
              {linkSuggestions.map((s, i) => (
                <div
                  key={`${s.slug}-${i}`}
                  className="border rounded-md p-3 space-y-2 bg-muted/30"
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-bold break-words">
                        {s.anchor_text}
                      </p>
                      <p className="text-xs mt-0.5">
                        <span className="text-muted-foreground">
                          {"\u2192 "}
                        </span>
                        {siteId ? (
                          <RouterLink
                            to={`/dashboard/${siteId}/articles/${s.slug}`}
                            className="text-primary hover:underline"
                          >
                            {s.title}
                          </RouterLink>
                        ) : (
                          <span className="text-primary">{s.title}</span>
                        )}
                      </p>
                    </div>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="shrink-0 h-7 px-2 text-xs"
                      onClick={() => copyMarkdownLink(s.anchor_text, s.slug)}
                      title={
                        i18n.language === "fr"
                          ? "Copier le markdown"
                          : "Copy markdown"
                      }
                    >
                      <Copy className="h-3.5 w-3.5 mr-1" />
                      {i18n.language === "fr" ? "Copier" : "Copy"}
                    </Button>
                  </div>
                  {s.insert_hint && (
                    <p className="text-xs italic text-muted-foreground border-l-2 border-primary/30 pl-2">
                      "{s.insert_hint}"
                    </p>
                  )}
                  {s.reason && (
                    <p className="text-xs text-muted-foreground">{s.reason}</p>
                  )}
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Schema.org JSON-LD */}
      <Card>
        <CardHeader className="py-3 px-4">
          <CardTitle className="text-sm flex items-center gap-2">
            <Code2 className="h-4 w-4" />
            {i18n.language === "fr"
              ? "Schema.org JSON-LD"
              : "Schema.org JSON-LD"}
          </CardTitle>
        </CardHeader>
        <CardContent className="px-4 pb-4 space-y-3">
          <Button
            size="sm"
            variant="outline"
            onClick={handleGenerateSchema}
            disabled={schemaLoading || !title || !content}
          >
            {schemaLoading ? (
              <>
                <Loader2 className="h-4 w-4 mr-1.5 animate-spin" />
                {i18n.language === "fr" ? "Generation..." : "Generating..."}
              </>
            ) : (
              <>
                <Code2 className="h-4 w-4 mr-1.5" />
                {i18n.language === "fr"
                  ? "Generer le schema"
                  : "Generate schema"}
              </>
            )}
          </Button>

          {schema && (
            <div className="space-y-2 pt-2 border-t">
              <div className="flex items-center justify-between gap-2">
                <Badge variant="secondary" className="font-mono text-xs">
                  {schema.schema_type}
                </Badge>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={handleCopySchema}
                  className="h-7 px-2 text-xs"
                >
                  <Copy className="h-3.5 w-3.5 mr-1" />
                  {i18n.language === "fr" ? "Copier" : "Copy"}
                </Button>
              </div>
              <pre className="text-[11px] leading-relaxed p-3 bg-muted rounded-md overflow-x-auto max-h-80 whitespace-pre-wrap break-all font-mono">
                <code>{schema.script_tag}</code>
              </pre>
              <p className="text-xs text-muted-foreground">
                {i18n.language === "fr"
                  ? "Collez ce <script> dans le <head> de l'article pour activer les Rich Results Google."
                  : "Paste this <script> into the article <head> to enable Google Rich Results."}
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Search Console (real perf) */}
      {canFetchGsc && (
        <Card>
          <CardHeader className="py-3 px-4">
            <CardTitle className="text-sm flex items-center gap-2">
              <BarChart3 className="h-4 w-4" />
              {i18n.language === "fr"
                ? "Search Console (vraie perf)"
                : "Search Console (real performance)"}
            </CardTitle>
            {articleUrl && (
              <p className="text-xs text-muted-foreground truncate">
                {articleUrl}
              </p>
            )}
          </CardHeader>
          <CardContent className="px-4 pb-4 space-y-3">
            {gscLoading && (
              <div className="flex items-center text-xs text-muted-foreground">
                <Loader2 className="h-4 w-4 mr-1.5 animate-spin" />
                {i18n.language === "fr" ? "Chargement..." : "Loading..."}
              </div>
            )}

            {!gscLoading && gscNeedsAuth && (
              <div className="space-y-2">
                <p className="text-xs text-muted-foreground">
                  {i18n.language === "fr"
                    ? "Connecte ton compte Google Search Console pour voir les vraies impressions et clics."
                    : "Connect your Google Search Console account to see real impressions and clicks."}
                </p>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={handleConnectGsc}
                  disabled={gscConnecting}
                >
                  {gscConnecting ? (
                    <Loader2 className="h-4 w-4 mr-1.5 animate-spin" />
                  ) : (
                    <BarChart3 className="h-4 w-4 mr-1.5" />
                  )}
                  {i18n.language === "fr"
                    ? "Connecter Google Search Console"
                    : "Connect Google Search Console"}
                </Button>
              </div>
            )}

            {!gscLoading && !gscNeedsAuth && gscError && (
              <p className="text-xs text-red-500">{gscError}</p>
            )}

            {!gscLoading && !gscNeedsAuth && !gscError && gscQueries && (
              <>
                {gscQueries.length === 0 ? (
                  <p className="text-xs text-muted-foreground">
                    {i18n.language === "fr"
                      ? "Aucune donnée Search Console pour cet article sur la période."
                      : "No Search Console data for this article in the range."}
                  </p>
                ) : (
                  <>
                    <div className="flex items-center gap-3">
                      <div
                        className={`w-12 h-12 rounded-full flex items-center justify-center font-bold ${
                          gscPerfScore >= 70
                            ? "bg-green-500/10 text-green-500"
                            : gscPerfScore >= 40
                              ? "bg-yellow-500/10 text-yellow-500"
                              : "bg-red-500/10 text-red-500"
                        }`}
                      >
                        {gscPerfScore}
                      </div>
                      <div>
                        <p className="text-sm font-medium">
                          {i18n.language === "fr"
                            ? "Score perf réelle"
                            : "Real perf score"}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {i18n.language === "fr"
                            ? "Basé sur clics & impressions"
                            : "Based on clicks & impressions"}
                        </p>
                      </div>
                    </div>

                    <div className="overflow-x-auto">
                      <table className="w-full text-xs">
                        <thead>
                          <tr className="text-left text-muted-foreground border-b">
                            <th className="py-1.5 pr-2 font-medium">
                              {i18n.language === "fr" ? "Requête" : "Query"}
                            </th>
                            <th className="py-1.5 px-2 font-medium text-right">
                              {i18n.language === "fr" ? "Clics" : "Clicks"}
                            </th>
                            <th className="py-1.5 px-2 font-medium text-right">
                              Impr.
                            </th>
                            <th className="py-1.5 px-2 font-medium text-right">
                              CTR
                            </th>
                            <th className="py-1.5 pl-2 font-medium text-right">
                              {i18n.language === "fr" ? "Pos." : "Pos."}
                            </th>
                          </tr>
                        </thead>
                        <tbody>
                          {sortedGscQueries.map((row) => (
                            <tr
                              key={row.query}
                              className="border-b last:border-0"
                            >
                              <td className="py-1.5 pr-2 truncate max-w-[180px]">
                                {row.query}
                              </td>
                              <td className="py-1.5 px-2 text-right">
                                {row.clicks}
                              </td>
                              <td className="py-1.5 px-2 text-right">
                                {row.impressions}
                              </td>
                              <td className="py-1.5 px-2 text-right">
                                {(row.ctr * 100).toFixed(1)}%
                              </td>
                              <td className="py-1.5 pl-2 text-right">
                                {row.position.toFixed(1)}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </>
                )}
              </>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
