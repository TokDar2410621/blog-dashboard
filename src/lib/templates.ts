import {
  Newspaper,
  GraduationCap,
  GitCompare,
  BookOpen,
  Star,
  MessageSquare,
  MapPin,
  Layout,
  Minimize2,
  Columns3,
  BookMarked,
  Zap,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

// --- Markdown Templates (content skeletons) ---
export interface MarkdownTemplate {
  id: string;
  nameKey: string;
  descriptionKey: string;
  icon: LucideIcon;
  content_fr: string;
  content_en: string;
  defaults: Record<string, unknown>;
}

export const markdownTemplates: MarkdownTemplate[] = [
  {
    id: "news",
    nameKey: "templates.md.news",
    descriptionKey: "templates.md.newsDesc",
    icon: Newspaper,
    content_fr:
      "## Contexte\n\nPresentez le sujet et pourquoi il est pertinent aujourd'hui.\n\n## Les faits\n\nDetaillez les informations principales.\n\n## Impact\n\nQuel impact cela a-t-il sur les lecteurs ?\n\n## Conclusion\n\nResumez et donnez votre perspective.",
    content_en:
      "## Context\n\nIntroduce the topic and why it's relevant today.\n\n## The Facts\n\nDetail the main information.\n\n## Impact\n\nWhat impact does this have on readers?\n\n## Conclusion\n\nSummarize and give your perspective.",
    defaults: { status: "draft" },
  },
  {
    id: "tutorial",
    nameKey: "templates.md.tutorial",
    descriptionKey: "templates.md.tutorialDesc",
    icon: GraduationCap,
    content_fr:
      "## Prerequis\n\n- Prerequis 1\n- Prerequis 2\n\n## Etape 1 : Configuration\n\nExplications...\n\n```\n// Code ici\n```\n\n## Etape 2 : Implementation\n\nExplications...\n\n```\n// Code ici\n```\n\n## Etape 3 : Test\n\nComment verifier que tout fonctionne.\n\n## Depannage\n\n| Probleme | Solution |\n|----------|----------|\n| Erreur X | Faire Y |\n\n## Resume\n\nCe que vous avez appris.",
    content_en:
      "## Prerequisites\n\n- Prerequisite 1\n- Prerequisite 2\n\n## Step 1: Setup\n\nExplanations...\n\n```\n// Code here\n```\n\n## Step 2: Implementation\n\nExplanations...\n\n```\n// Code here\n```\n\n## Step 3: Testing\n\nHow to verify everything works.\n\n## Troubleshooting\n\n| Problem | Solution |\n|---------|----------|\n| Error X | Do Y |\n\n## Summary\n\nWhat you learned.",
    defaults: { status: "draft" },
  },
  {
    id: "comparison",
    nameKey: "templates.md.comparison",
    descriptionKey: "templates.md.comparisonDesc",
    icon: GitCompare,
    content_fr:
      "## Introduction\n\nPourquoi cette comparaison est importante.\n\n## Criteres de comparaison\n\n1. Critere A\n2. Critere B\n3. Critere C\n\n## Option 1 : [Nom]\n\n### Points forts\n- ...\n\n### Points faibles\n- ...\n\n## Option 2 : [Nom]\n\n### Points forts\n- ...\n\n### Points faibles\n- ...\n\n## Tableau comparatif\n\n| Critere | Option 1 | Option 2 |\n|---------|----------|----------|\n| Prix    |          |          |\n\n## Verdict\n\nNotre recommandation et pourquoi.",
    content_en:
      "## Introduction\n\nWhy this comparison matters.\n\n## Comparison Criteria\n\n1. Criterion A\n2. Criterion B\n3. Criterion C\n\n## Option 1: [Name]\n\n### Strengths\n- ...\n\n### Weaknesses\n- ...\n\n## Option 2: [Name]\n\n### Strengths\n- ...\n\n### Weaknesses\n- ...\n\n## Comparison Table\n\n| Criterion | Option 1 | Option 2 |\n|-----------|----------|----------|\n| Price     |          |          |\n\n## Verdict\n\nOur recommendation and why.",
    defaults: { status: "draft" },
  },
  {
    id: "guide",
    nameKey: "templates.md.guide",
    descriptionKey: "templates.md.guideDesc",
    icon: BookOpen,
    content_fr:
      "## Vue d'ensemble\n\nIntroduction au sujet.\n\n## Section 1 : Les bases\n\n...\n\n## Section 2 : Avance\n\n...\n\n## Section 3 : Bonnes pratiques\n\n...\n\n## Astuces\n\n> Conseil pro : ...\n\n## FAQ\n\n**Q: Question frequente ?**\nR: Reponse.\n\n**Q: Autre question ?**\nR: Reponse.",
    content_en:
      "## Overview\n\nIntroduction to the topic.\n\n## Section 1: The Basics\n\n...\n\n## Section 2: Advanced\n\n...\n\n## Section 3: Best Practices\n\n...\n\n## Tips\n\n> Pro tip: ...\n\n## FAQ\n\n**Q: Common question?**\nA: Answer.\n\n**Q: Another question?**\nA: Answer.",
    defaults: { status: "draft" },
  },
  {
    id: "review",
    nameKey: "templates.md.review",
    descriptionKey: "templates.md.reviewDesc",
    icon: Star,
    content_fr:
      "## Presentation\n\nQu'est-ce que [produit/outil] ?\n\n## Prise en main\n\nPremiere experience.\n\n## Points forts\n\n- ...\n\n## Points faibles\n\n- ...\n\n## Pour qui ?\n\nLe public cible ideal.\n\n## Verdict\n\n**Note : X/10**\n\nResume en une phrase.",
    content_en:
      "## Overview\n\nWhat is [product/tool]?\n\n## Getting Started\n\nFirst experience.\n\n## Pros\n\n- ...\n\n## Cons\n\n- ...\n\n## Who is it for?\n\nThe ideal target audience.\n\n## Verdict\n\n**Score: X/10**\n\nOne-sentence summary.",
    defaults: { status: "draft" },
  },
  {
    id: "story",
    nameKey: "templates.md.story",
    descriptionKey: "templates.md.storyDesc",
    icon: MessageSquare,
    content_fr:
      "## L'accroche\n\nCommencez par un moment marquant.\n\n## Le contexte\n\nOu en etiez-vous a ce moment-la ?\n\n## Le defi\n\nQuel probleme avez-vous rencontre ?\n\n## La resolution\n\nComment avez-vous surmonte ce defi ?\n\n## La lecon\n\nQu'avez-vous appris ? Quel conseil donneriez-vous ?",
    content_en:
      "## The Hook\n\nStart with a defining moment.\n\n## The Context\n\nWhere were you at that point?\n\n## The Challenge\n\nWhat problem did you face?\n\n## The Resolution\n\nHow did you overcome this challenge?\n\n## The Lesson\n\nWhat did you learn? What advice would you give?",
    defaults: { status: "draft" },
  },
];

// --- Visual Templates (layouts) ---
export interface VisualTemplate {
  id: string;
  nameKey: string;
  descriptionKey: string;
  icon: LucideIcon;
  cssClass: string;
  preview: string;
}

export const visualTemplates: VisualTemplate[] = [
  {
    id: "hero",
    nameKey: "templates.visual.hero",
    descriptionKey: "templates.visual.heroDesc",
    icon: Layout,
    cssClass: "template-hero",
    preview:
      "┌──────────────────────┐\n│ ████ COVER IMAGE ████ │\n│ ████████████████████  │\n├──────────────────────┤\n│    Centered Title     │\n│                       │\n│  Content here...      │\n└──────────────────────┘",
  },
  {
    id: "minimal",
    nameKey: "templates.visual.minimal",
    descriptionKey: "templates.visual.minimalDesc",
    icon: Minimize2,
    cssClass: "template-minimal",
    preview:
      "┌──────────────────────┐\n│                       │\n│  Title                │\n│                       │\n│  Clean, focused text  │\n│  No distractions      │\n│                       │\n└──────────────────────┘",
  },
  {
    id: "sidebar",
    nameKey: "templates.visual.sidebar",
    descriptionKey: "templates.visual.sidebarDesc",
    icon: Columns3,
    cssClass: "template-sidebar",
    preview:
      "┌────────────────┬─────┐\n│ Title           │ TOC │\n│                 │     │\n│ Content...      │ H2  │\n│                 │ H2  │\n│                 │ H2  │\n└────────────────┴─────┘",
  },
  {
    id: "magazine",
    nameKey: "templates.visual.magazine",
    descriptionKey: "templates.visual.magazineDesc",
    icon: BookMarked,
    cssClass: "template-magazine",
    preview:
      "┌──────────────────────┐\n│ ██ IMG ██  Title      │\n│ ██     ██  Excerpt    │\n├──────────────────────┤\n│ Col 1      │  Col 2   │\n│ Content    │  Sidebar  │\n└──────────────────────┘",
  },
];

// --- AI Templates (pre-configured prompts) ---
export interface AITemplate {
  id: string;
  nameKey: string;
  descriptionKey: string;
  icon: LucideIcon;
  params: {
    type: string;
    length: string;
    search: string;
  };
}

export const aiTemplates: AITemplate[] = [
  {
    id: "quick-news",
    nameKey: "templates.ai.quickNews",
    descriptionKey: "templates.ai.quickNewsDesc",
    icon: Zap,
    params: { type: "news", length: "short", search: "serper" },
  },
  {
    id: "deep-tutorial",
    nameKey: "templates.ai.deepTutorial",
    descriptionKey: "templates.ai.deepTutorialDesc",
    icon: GraduationCap,
    params: { type: "tutorial", length: "long", search: "gemini" },
  },
  {
    id: "product-comparison",
    nameKey: "templates.ai.comparison",
    descriptionKey: "templates.ai.comparisonDesc",
    icon: GitCompare,
    params: { type: "comparison", length: "medium", search: "serper" },
  },
  {
    id: "ultimate-guide",
    nameKey: "templates.ai.guide",
    descriptionKey: "templates.ai.guideDesc",
    icon: BookOpen,
    params: { type: "guide", length: "long", search: "gemini" },
  },
  {
    id: "personal-story",
    nameKey: "templates.ai.story",
    descriptionKey: "templates.ai.storyDesc",
    icon: MessageSquare,
    params: { type: "story", length: "medium", search: "serper" },
  },
  {
    id: "local-directory",
    nameKey: "templates.ai.local",
    descriptionKey: "templates.ai.localDesc",
    icon: MapPin,
    params: { type: "local", length: "medium", search: "serper" },
  },
];
