/**
 * Helpers for the articles list page (/dashboard/[siteId]/articles).
 *
 * The SPA resolved these strings through react-i18next; the Next.js port
 * hardcodes the French catalog (src/i18n/fr.json) per the migration rules.
 */

/** French labels for `status.*` i18n keys (PostStatusBadge). */
export const STATUS_LABELS: Record<string, string> = {
  published: "Publié",
  draft: "Brouillon",
  scheduled: "Planifié",
};

/**
 * French labels for the template catalog keys stored in
 * `marketing/lib/templates.ts` (`nameKey` / `descriptionKey`).
 * Mirrors the `templates.*` section of src/i18n/fr.json.
 */
export const TEMPLATE_LABELS: Record<string, string> = {
  // Markdown templates
  "templates.md.news": "Actualité",
  "templates.md.newsDesc": "Intro, faits, impact, conclusion",
  "templates.md.tutorial": "Tutoriel",
  "templates.md.tutorialDesc": "Prérequis, étapes, dépannage, résumé",
  "templates.md.comparison": "Comparaison",
  "templates.md.comparisonDesc": "Critères, options, tableau, verdict",
  "templates.md.guide": "Guide",
  "templates.md.guideDesc": "Vue d'ensemble, sections, FAQ",
  "templates.md.review": "Review",
  "templates.md.reviewDesc": "Présentation, pros/cons, verdict",
  "templates.md.story": "Récit personnel",
  "templates.md.storyDesc": "Accroche, contexte, défi, leçon",
  // Visual templates
  "templates.visual.hero": "Hero",
  "templates.visual.heroDesc": "Image pleine largeur + texte centré",
  "templates.visual.minimal": "Minimal",
  "templates.visual.minimalDesc": "Texte épuré, sans fioritures",
  "templates.visual.sidebar": "Sidebar",
  "templates.visual.sidebarDesc": "Contenu + table des matières latérale",
  "templates.visual.magazine": "Magazine",
  "templates.visual.magazineDesc": "Mise en page éditoriale avec image",
  // AI templates
  "templates.ai.quickNews": "Actu rapide",
  "templates.ai.quickNewsDesc": "Article court, recherche Serper",
  "templates.ai.deepTutorial": "Tuto approfondi",
  "templates.ai.deepTutorialDesc": "Tutoriel long, recherche Gemini",
  "templates.ai.comparison": "Comparatif",
  "templates.ai.comparisonDesc": "Comparaison produits/outils",
  "templates.ai.guide": "Guide ultime",
  "templates.ai.guideDesc": "Guide complet et détaillé",
  "templates.ai.story": "Récit perso",
  "templates.ai.storyDesc": "Histoire personnelle et leçons",
  "templates.ai.local": "Annuaire local",
  "templates.ai.localDesc": "Ressources et services locaux",
};

/** Resolve a template i18n key to its French label (falls back to the key). */
export function tplLabel(key: string): string {
  return TEMPLATE_LABELS[key] ?? key;
}

/**
 * French pluralization of "posts.articleCount" / "posts.articleCount_other".
 * fr-CA plural rule: 0 and 1 take the singular form.
 */
export function formatArticleCount(count: number): string {
  return count > 1 ? `${count} articles` : `${count} article`;
}
