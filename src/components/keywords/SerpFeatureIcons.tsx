import { Search, MessageSquare, Sparkles, type LucideIcon } from "lucide-react";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

export type SerpOwnership = "you" | "comp";

export type SerpFeatures = {
  fs?: SerpOwnership;
  paa?: SerpOwnership;
  ai?: SerpOwnership;
};

interface SerpFeatureIconsProps {
  features: SerpFeatures;
  className?: string;
}

type FeatureSpec = {
  key: keyof SerpFeatures;
  icon: LucideIcon;
  label: string;
  description: string;
};

const FEATURES: FeatureSpec[] = [
  {
    key: "fs",
    icon: Search,
    label: "Featured Snippet",
    description: "Position 0 - encadre repondant directement a la requete.",
  },
  {
    key: "paa",
    icon: MessageSquare,
    label: "People Also Ask",
    description: "Bloc 'Autres questions posees' affiche dans la SERP.",
  },
  {
    key: "ai",
    icon: Sparkles,
    label: "AI Overview",
    description: "Reponse generee par l'IA de Google en haut de page.",
  },
];

function ownershipLabel(owner: SerpOwnership) {
  return owner === "you" ? "Tu possedes cet emplacement" : "Possede par un concurrent";
}

export function SerpFeatureIcons({ features, className }: SerpFeatureIconsProps) {
  const present = FEATURES.filter((f) => features[f.key]);

  if (!present.length) {
    return (
      <div className={cn("flex items-center gap-1", className)}>
        <span className="text-xs text-muted-foreground">-</span>
      </div>
    );
  }

  return (
    <TooltipProvider delayDuration={150}>
      <div className={cn("flex items-center gap-1.5", className)}>
        {present.map((f) => {
          const owner = features[f.key]!;
          const Icon = f.icon;
          return (
            <Tooltip key={f.key}>
              <TooltipTrigger asChild>
                <span
                  className={cn(
                    "inline-flex items-center justify-center h-5 w-5 rounded",
                    owner === "you"
                      ? "text-emerald-600 dark:text-emerald-400 bg-emerald-500/10"
                      : "text-zinc-500 bg-zinc-500/10"
                  )}
                  aria-label={`${f.label} - ${ownershipLabel(owner)}`}
                >
                  <Icon className="h-3 w-3" />
                </span>
              </TooltipTrigger>
              <TooltipContent side="top" className="max-w-[220px]">
                <div className="font-medium">{f.label}</div>
                <div className="text-[10px] opacity-80 mt-0.5">{f.description}</div>
                <div className="text-[10px] mt-1">
                  {owner === "you" ? (
                    <span className="text-emerald-300">Tu possedes cet emplacement</span>
                  ) : (
                    <span className="text-zinc-300">Possede par un concurrent</span>
                  )}
                </div>
              </TooltipContent>
            </Tooltip>
          );
        })}
      </div>
    </TooltipProvider>
  );
}
