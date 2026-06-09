/**
 * Client-side composite Content Score for the editor right rail.
 *
 * V1: pure heuristics so the score updates on every keystroke without
 * round-tripping to the backend. The richer signals (Plagiarism, GSC, real
 * Flesch from the backend) keep flowing in their own cards (LexiconCard,
 * ReadabilityCard, PlagiarismCard). Composite weights:
 *
 *   - keywords     25%
 *   - structure    20%
 *   - readability  20%
 *   - oqlf         15%   (French-Canadian lexicon proxy: anglicisms penalty)
 *   - eeat         10%   (author/date/links/sources proxies)
 *   - originality  10%   (lexical diversity proxy)
 *
 * TODO(v2): migrate this whole module behind an endpoint that already aggregates
 *           SEOAnalyzer + ReadabilityCard + LexiconCard + PlagiarismCard data
 *           so the score is identical between editor and audit views.
 */

export interface ScoreInputs {
  title: string;
  excerpt: string;
  content: string;
  slug: string;
  coverImage?: string;
  keyword: string;
  /** Additional keywords (eg. tags, brief recommended_terms). */
  secondaryKeywords?: string[];
  language: string;
}

export interface SubScores {
  keywords: number;
  structure: number;
  readability: number;
  oqlf: number;
  eeat: number;
  originality: number;
}

export interface CompositeScore {
  total: number;
  sub: SubScores;
}

const WEIGHTS = {
  keywords: 0.25,
  structure: 0.2,
  readability: 0.2,
  oqlf: 0.15,
  eeat: 0.1,
  originality: 0.1,
};

const clamp = (n: number, min = 0, max = 100) =>
  Math.max(min, Math.min(max, n));

function stripMarkdown(md: string): string {
  return md
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/`[^`]*`/g, " ")
    .replace(/!\[[^\]]*\]\([^)]+\)/g, " ")
    .replace(/\[[^\]]*\]\([^)]+\)/g, " ")
    .replace(/[#>*_~`]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function countOccurrences(haystack: string, needle: string): number {
  if (!needle) return 0;
  const re = new RegExp(
    `\\b${needle.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\b`,
    "gi",
  );
  return (haystack.match(re) || []).length;
}

function wordCount(text: string): number {
  return text.split(/\s+/).filter(Boolean).length;
}

function sentenceCount(text: string): number {
  return Math.max(1, (text.match(/[.!?]+\s/g) || []).length);
}

function syllableEstimate(word: string): number {
  // Cheap heuristic - good enough for FR/EN on the client.
  const w = word.toLowerCase().replace(/[^a-zàâäéèêëïîôöùûüÿç]/g, "");
  if (!w) return 0;
  const groups = w.match(/[aeiouàâäéèêëïîôöùûüÿy]+/g);
  return Math.max(1, groups ? groups.length : 1);
}

/** Approx Flesch reading ease (FR-friendly tuning). */
export function approxFlesch(text: string): number | null {
  const words = wordCount(text);
  if (words < 30) return null;
  const sentences = sentenceCount(text);
  const syllables = text
    .split(/\s+/)
    .filter(Boolean)
    .reduce((acc, w) => acc + syllableEstimate(w), 0);
  const wps = words / sentences;
  const spw = syllables / words;
  // Standard Flesch reading ease formula. Works approximately for FR too.
  return clamp(206.835 - 1.015 * wps - 84.6 * spw, 0, 100);
}

/* -------------------------------------------------------------------------- */
/*                              Sub-score scorers                             */
/* -------------------------------------------------------------------------- */

function scoreKeywords(i: ScoreInputs, plain: string): number {
  if (!i.keyword) return 50; // No primary keyword: neutral.
  const kw = i.keyword.toLowerCase();
  const total = wordCount(plain);
  if (total < 50) return 30;

  const inTitle = i.title.toLowerCase().includes(kw) ? 25 : 0;
  const inExcerpt = i.excerpt.toLowerCase().includes(kw) ? 15 : 0;
  const inSlug = i.slug.toLowerCase().includes(kw.replace(/\s+/g, "-"))
    ? 10
    : 0;
  // First paragraph
  const firstPara = plain.slice(0, 300).toLowerCase();
  const inFirst = firstPara.includes(kw) ? 15 : 0;

  // Density target 0.5%-2.5%
  const occ = countOccurrences(plain, i.keyword);
  const density = (occ / Math.max(1, total)) * 100;
  let densityScore = 0;
  if (density >= 0.5 && density <= 2.5) densityScore = 25;
  else if (density > 0 && density < 0.5) densityScore = 12;
  else if (density > 2.5 && density <= 4) densityScore = 12;
  else if (density > 4) densityScore = 4;

  // Secondary keyword coverage
  const sec = i.secondaryKeywords || [];
  const covered = sec.filter((k) => countOccurrences(plain, k) > 0).length;
  const secScore = sec.length
    ? clamp((covered / sec.length) * 10, 0, 10)
    : 10;

  return clamp(inTitle + inExcerpt + inSlug + inFirst + densityScore + secScore);
}

function scoreStructure(i: ScoreInputs): number {
  const md = i.content;
  const h1 = (md.match(/^#\s+/gm) || []).length;
  const h2 = (md.match(/^##\s+/gm) || []).length;
  const h3 = (md.match(/^###\s+/gm) || []).length;
  const lists = (md.match(/^[-*]\s+/gm) || []).length;
  const links = (md.match(/\[[^\]]+\]\(https?:[^)]+\)/g) || []).length;
  const images = (md.match(/!\[[^\]]*\]\([^)]+\)/g) || []).length;
  const paragraphs = md
    .split(/\n{2,}/)
    .filter((p) => p.trim().length > 0).length;

  let s = 0;
  // Exactly one H1 (often title itself; we accept 0 or 1)
  s += h1 <= 1 ? 10 : 5;
  s += clamp(h2 * 8, 0, 24); // up to 3 H2 -> full points
  s += clamp(h3 * 4, 0, 12);
  s += lists >= 1 ? 10 : 0;
  s += clamp(links * 4, 0, 16); // mix of internal/external
  s += i.coverImage ? 8 : 0;
  s += images >= 1 ? 8 : 0;
  s += paragraphs >= 4 ? 12 : paragraphs * 3;
  return clamp(s);
}

function scoreReadability(plain: string): number {
  const f = approxFlesch(plain);
  if (f === null) return 50;
  // Sweet spot 60-80
  if (f >= 60 && f <= 80) return 95;
  if (f >= 50 && f < 60) return 80;
  if (f > 80 && f <= 90) return 80;
  if (f >= 30 && f < 50) return 55;
  return 35;
}

// Short anglicism list - matches the spirit of the backend lexicon.
const ANGLICISMS_FR_CA = [
  "checker",
  "canceller",
  "downloader",
  "uploader",
  "scroller",
  "feedback",
  "meeting",
  "deadline",
  "weekend",
  "shopping",
  "business",
  "marketing",
  "manager",
  "performant",
  "checklist",
];

function scoreOQLF(i: ScoreInputs, plain: string): number {
  if (i.language !== "fr") return 90; // Not applicable - default high.
  let hits = 0;
  const lower = plain.toLowerCase();
  for (const term of ANGLICISMS_FR_CA) {
    if (new RegExp(`\\b${term}\\b`, "i").test(lower)) hits += 1;
  }
  return clamp(100 - hits * 12);
}

function scoreEEAT(i: ScoreInputs, plain: string): number {
  const links = (i.content.match(/\[[^\]]+\]\(https?:[^)]+\)/g) || []).length;
  const externalLinks = (
    i.content.match(/\[[^\]]+\]\(https?:\/\/(?!localhost)[^)]+\)/g) || []
  ).length;
  const dates = /\b(20[0-9]{2})\b/.test(plain) ? 1 : 0;
  const numbers = (plain.match(/\b\d+([.,]\d+)?\s?(%|€|\$|km|kg)\b/gi) || [])
    .length;
  let s = 30;
  s += clamp(externalLinks * 10, 0, 30);
  s += clamp(links * 4, 0, 20);
  s += dates * 10;
  s += clamp(numbers * 4, 0, 20);
  return clamp(s);
}

function scoreOriginality(plain: string): number {
  const words = plain.toLowerCase().split(/\s+/).filter((w) => w.length > 3);
  if (words.length < 40) return 60;
  const unique = new Set(words).size;
  const ratio = unique / words.length;
  // 0.5+ = excellent, 0.3-0.5 = ok, <0.3 = repetitive
  if (ratio >= 0.5) return 95;
  if (ratio >= 0.4) return 80;
  if (ratio >= 0.3) return 65;
  return 45;
}

export function computeCompositeScore(i: ScoreInputs): CompositeScore {
  const plain = stripMarkdown(i.content);
  const sub: SubScores = {
    keywords: scoreKeywords(i, plain),
    structure: scoreStructure(i),
    readability: scoreReadability(plain),
    oqlf: scoreOQLF(i, plain),
    eeat: scoreEEAT(i, plain),
    originality: scoreOriginality(plain),
  };
  const total =
    sub.keywords * WEIGHTS.keywords +
    sub.structure * WEIGHTS.structure +
    sub.readability * WEIGHTS.readability +
    sub.oqlf * WEIGHTS.oqlf +
    sub.eeat * WEIGHTS.eeat +
    sub.originality * WEIGHTS.originality;
  return { total: Math.round(clamp(total)), sub };
}

/* -------------------------------------------------------------------------- */
/*                          Term tracker helpers                              */
/* -------------------------------------------------------------------------- */

export interface TermSeed {
  term: string;
  importance: number;
}

/**
 * Pick a target range based on article length and term importance.
 *
 * Heuristic: longer articles can absorb more occurrences; very high-importance
 * terms (primary keyword) target slightly higher ranges.
 */
export function targetRangeFor(
  wordCountTotal: number,
  importance: number,
): [number, number] {
  const base = Math.max(2, Math.round(wordCountTotal / 300));
  const boost = importance > 0.7 ? 2 : importance > 0.4 ? 1 : 0;
  const min = base + boost;
  const max = min + 3;
  return [min, max];
}

export function buildTermUsage(
  content: string,
  seeds: TermSeed[],
): {
  term: string;
  current: number;
  target: [number, number];
  importance: number;
}[] {
  const plain = stripMarkdown(content);
  const words = wordCount(plain);
  return seeds.map((s) => ({
    term: s.term,
    current: countOccurrences(plain, s.term),
    target: targetRangeFor(words, s.importance),
    importance: s.importance,
  }));
}
