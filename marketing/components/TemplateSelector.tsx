"use client";

import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { FileText } from "lucide-react";
import {
  markdownTemplates,
  visualTemplates,
  aiTemplates,
  type MarkdownTemplate,
  type VisualTemplate,
  type AITemplate,
} from "@/lib/templates";

interface TemplateSelectorProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSelectMarkdown: (template: MarkdownTemplate) => void;
  onSelectVisual: (template: VisualTemplate) => void;
  onSelectAI: (template: AITemplate) => void;
  onSelectBlank: () => void;
}

// FR-CA labels for every templates.* key used by tpl.nameKey / tpl.descriptionKey.
// Mirrors src/i18n/fr.json templates branch. Hardcoded for now; the migration
// will plug i18n later if EN ships.
const FR: Record<string, string> = {
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
  "templates.visual.hero": "Hero",
  "templates.visual.heroDesc": "Image pleine largeur + texte centré",
  "templates.visual.minimal": "Minimal",
  "templates.visual.minimalDesc": "Texte épuré, sans fioritures",
  "templates.visual.sidebar": "Sidebar",
  "templates.visual.sidebarDesc": "Contenu + table des matières latérale",
  "templates.visual.magazine": "Magazine",
  "templates.visual.magazineDesc": "Mise en page éditoriale avec image",
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

function t(key: string): string {
  return FR[key] || key;
}

export function TemplateSelector({
  open,
  onOpenChange,
  onSelectMarkdown,
  onSelectVisual,
  onSelectAI,
  onSelectBlank,
}: TemplateSelectorProps) {
  const [tab, setTab] = useState<"markdown" | "visual" | "ai">("markdown");

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-2xl max-h-[80vh] flex flex-col">
        <DialogHeader>
          <DialogTitle>Choisir un template</DialogTitle>
          <DialogDescription>
            Sélectionnez un type de template pour votre article
          </DialogDescription>
        </DialogHeader>

        <div className="flex gap-2">
          <Button
            variant={tab === "markdown" ? "default" : "outline"}
            size="sm"
            onClick={() => setTab("markdown")}
          >
            Contenu
          </Button>
          <Button
            variant={tab === "visual" ? "default" : "outline"}
            size="sm"
            onClick={() => setTab("visual")}
          >
            Visuel
          </Button>
          <Button
            variant={tab === "ai" ? "default" : "outline"}
            size="sm"
            onClick={() => setTab("ai")}
          >
            IA
          </Button>
        </div>

        <div className="flex-1 overflow-y-auto min-h-0 space-y-2">
          {tab !== "ai" && (
            <Card
              className="cursor-pointer hover:border-primary/50 transition-colors"
              onClick={() => {
                onSelectBlank();
                onOpenChange(false);
              }}
            >
              <CardContent className="p-3 flex items-center gap-3">
                <FileText className="h-8 w-8 text-muted-foreground shrink-0" />
                <div className="min-w-0">
                  <p className="font-medium text-sm">Article vierge</p>
                  <p className="text-xs text-muted-foreground">
                    Commencer avec un éditeur vide
                  </p>
                </div>
              </CardContent>
            </Card>
          )}

          {tab === "markdown" &&
            markdownTemplates.map((tpl) => (
              <Card
                key={tpl.id}
                className="cursor-pointer hover:border-primary/50 transition-colors"
                onClick={() => {
                  onSelectMarkdown(tpl);
                  onOpenChange(false);
                }}
              >
                <CardContent className="p-3 flex items-center gap-3">
                  <tpl.icon className="h-8 w-8 text-primary shrink-0" />
                  <div className="min-w-0">
                    <p className="font-medium text-sm">{t(tpl.nameKey)}</p>
                    <p className="text-xs text-muted-foreground">
                      {t(tpl.descriptionKey)}
                    </p>
                  </div>
                </CardContent>
              </Card>
            ))}

          {tab === "visual" &&
            visualTemplates.map((tpl) => (
              <Card
                key={tpl.id}
                className="cursor-pointer hover:border-primary/50 transition-colors"
                onClick={() => {
                  onSelectVisual(tpl);
                  onOpenChange(false);
                }}
              >
                <CardContent className="p-3 flex items-start gap-3">
                  <tpl.icon className="h-8 w-8 text-primary shrink-0 mt-1" />
                  <div className="min-w-0 flex-1">
                    <p className="font-medium text-sm">{t(tpl.nameKey)}</p>
                    <p className="text-xs text-muted-foreground mb-2">
                      {t(tpl.descriptionKey)}
                    </p>
                    <pre className="text-[10px] text-muted-foreground font-mono bg-muted/50 p-2 rounded">
                      {tpl.preview}
                    </pre>
                  </div>
                </CardContent>
              </Card>
            ))}

          {tab === "ai" &&
            aiTemplates.map((tpl) => (
              <Card
                key={tpl.id}
                className="cursor-pointer hover:border-primary/50 transition-colors"
                onClick={() => {
                  onSelectAI(tpl);
                  onOpenChange(false);
                }}
              >
                <CardContent className="p-3 flex items-center gap-3">
                  <tpl.icon className="h-8 w-8 text-primary shrink-0" />
                  <div className="min-w-0 flex-1">
                    <p className="font-medium text-sm">{t(tpl.nameKey)}</p>
                    <p className="text-xs text-muted-foreground">
                      {t(tpl.descriptionKey)}
                    </p>
                  </div>
                  <div className="text-xs text-muted-foreground shrink-0">
                    {tpl.params.length === "short"
                      ? "~1000"
                      : tpl.params.length === "medium"
                        ? "~1700"
                        : "~3000"}{" "}
                    mots
                  </div>
                </CardContent>
              </Card>
            ))}
        </div>
      </DialogContent>
    </Dialog>
  );
}
