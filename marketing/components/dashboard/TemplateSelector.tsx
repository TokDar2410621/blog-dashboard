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
import { tplLabel } from "@/lib/articles-helpers";

interface TemplateSelectorProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSelectMarkdown: (template: MarkdownTemplate) => void;
  onSelectVisual: (template: VisualTemplate) => void;
  onSelectAI: (template: AITemplate) => void;
  onSelectBlank: () => void;
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

        {/* Tab buttons */}
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

        {/* Content */}
        <div className="flex-1 overflow-y-auto min-h-0 space-y-2">
          {/* Blank option (always shown for markdown/visual) */}
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

          {/* Markdown templates */}
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
                    <p className="font-medium text-sm">{tplLabel(tpl.nameKey)}</p>
                    <p className="text-xs text-muted-foreground">
                      {tplLabel(tpl.descriptionKey)}
                    </p>
                  </div>
                </CardContent>
              </Card>
            ))}

          {/* Visual templates */}
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
                    <p className="font-medium text-sm">{tplLabel(tpl.nameKey)}</p>
                    <p className="text-xs text-muted-foreground mb-2">
                      {tplLabel(tpl.descriptionKey)}
                    </p>
                    <pre className="text-[10px] text-muted-foreground font-mono bg-muted/50 p-2 rounded">
                      {tpl.preview}
                    </pre>
                  </div>
                </CardContent>
              </Card>
            ))}

          {/* AI templates */}
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
                    <p className="font-medium text-sm">{tplLabel(tpl.nameKey)}</p>
                    <p className="text-xs text-muted-foreground">
                      {tplLabel(tpl.descriptionKey)}
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
