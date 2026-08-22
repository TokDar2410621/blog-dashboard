export type NavTool = {
  label: string;
  href: string;
  description: string;
};

/**
 * Source unique des outils gratuits exposes dans le navbar (menu deroulant)
 * et le footer (colonne). La page hub /tools garde sa propre liste enrichie
 * (icones + badges + flag available) ; garder les deux en phase a la main.
 */
export const NAV_TOOLS: NavTool[] = [
  {
    label: "Audit SEO + GEO",
    href: "/audit",
    description: "Score SEO complet, vitesse mobile, positions Google.ca.",
  },
  {
    label: "AI Visibility Checker",
    href: "/tools/ai-visibility-checker",
    description: "Es-tu recommandé par l'IA de Google?",
  },
  {
    label: "Competitor Gap Finder",
    href: "/tools/competitor-gap",
    description: "Les mots-clés où tes concurrents rankent, pas toi.",
  },
  {
    label: "Can I Rank?",
    href: "/tools/keyword-difficulty",
    description: "La difficulté d'un mot-clé pour TON site.",
  },
  {
    label: "Calculateur ROI SEO",
    href: "/tools/seo-roi-calculator",
    description: "Ton potentiel SEO en visiteurs, leads et revenus.",
  },
  {
    label: "AI Citation Checker",
    href: "/tools/ai-citation-checker",
    description: "L'IA de Google te cite-t-elle comme source?",
  },
  {
    label: "Comparaison de concurrents",
    href: "/tools/competitor-compare",
    description: "Ton site contre ton concurrent sur 20+ dimensions.",
  },
  {
    label: "Suivi de position Google",
    href: "/suivi-position-google-canada",
    description: "Ta position sur Google.ca, géolocalisée au Québec.",
  },
];
