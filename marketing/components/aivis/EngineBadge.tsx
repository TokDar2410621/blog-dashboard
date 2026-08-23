import { cn } from "@/lib/utils";
import {
  Bot,
  Compass,
  Search,
  Gem,
  MessageSquare,
  type LucideIcon,
} from "lucide-react";
import type { AiVisibilityEngine } from "@/lib/api-client";

/**
 * Brand-coloured badge for each LLM engine we track. Used in the breakdown
 * cards and per-prompt rows.
 *
 * Colour mapping (monochrome icon on tinted background):
 *  - chatgpt    -> emerald (OpenAI brand green)
 *  - perplexity -> teal/turquoise
 *  - gemini     -> blue (Google brand)
 *  - searchgpt  -> neutral / black (OpenAI Search)
 *  - claude     -> orange (Anthropic brand)
 */

type EngineMeta = {
  label: string;
  Icon: LucideIcon;
  /** Tailwind classes for the badge background + icon colour. */
  className: string;
};

const ENGINE_META: Record<AiVisibilityEngine, EngineMeta> = {
  chatgpt: {
    label: "ChatGPT",
    Icon: Bot,
    className:
      "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
  },
  perplexity: {
    label: "Perplexity",
    Icon: Search,
    className:
      "bg-teal-500/15 text-teal-300 border-teal-500/30",
  },
  gemini: {
    label: "Gemini",
    Icon: Gem,
    className:
      "bg-blue-500/15 text-blue-300 border-blue-500/30",
  },
  searchgpt: {
    label: "SearchGPT",
    Icon: Compass,
    className:
      "bg-neutral-500/15 text-neutral-200 border-neutral-500/40",
  },
  claude: {
    label: "Claude",
    Icon: MessageSquare,
    className:
      "bg-orange-500/15 text-orange-300 border-orange-500/30",
  },
};

interface EngineBadgeProps {
  engine: AiVisibilityEngine;
  size?: "sm" | "md";
  showLabel?: boolean;
  className?: string;
}

export function EngineBadge({
  engine,
  size = "sm",
  showLabel = true,
  className,
}: EngineBadgeProps) {
  const meta = ENGINE_META[engine];
  const Icon = meta.Icon;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border font-medium",
        size === "sm" ? "px-2 py-0.5 text-[11px]" : "px-2.5 py-1 text-xs",
        meta.className,
        className,
      )}
      aria-label={meta.label}
    >
      <Icon className={size === "sm" ? "h-3 w-3" : "h-3.5 w-3.5"} />
      {showLabel && <span>{meta.label}</span>}
    </span>
  );
}

/** Convenience helper: ordered list of every engine in canonical order. */
export const ALL_ENGINES: AiVisibilityEngine[] = [
  "chatgpt",
  "perplexity",
  "gemini",
  "searchgpt",
  "claude",
];

export function getEngineLabel(engine: AiVisibilityEngine): string {
  return ENGINE_META[engine].label;
}
