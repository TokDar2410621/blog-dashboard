"use client";

import type * as React from "react";
import { CheckCircle2, Circle, Lightbulb } from "lucide-react";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

export type HexStatus = "covered" | "missing" | "recommended";

export type HexTopic = {
  label: string;
  status: HexStatus;
  volume?: number;
  kd?: number;
  /** Optional payload propagated to onClick (slug, suggested article, etc.). */
  meta?: Record<string, unknown>;
};

type Props = {
  topic: HexTopic;
  onClick?: (topic: HexTopic) => void;
  /** Tile size in px (width). Hex height is width * sqrt(3)/2 approx. */
  size?: number;
};

const STATUS_STYLES: Record<
  HexStatus,
  { fill: string; stroke: string; text: string; hover: string }
> = {
  covered: {
    fill: "fill-emerald-500/90",
    stroke: "stroke-emerald-400",
    text: "text-white",
    hover: "hover:fill-emerald-400",
  },
  missing: {
    fill: "fill-zinc-700",
    stroke: "stroke-zinc-500",
    text: "text-zinc-200",
    hover: "hover:fill-zinc-600",
  },
  recommended: {
    fill: "fill-amber-500/90",
    stroke: "stroke-amber-400",
    text: "text-zinc-900",
    hover: "hover:fill-amber-400",
  },
};

const ICONS = {
  covered: CheckCircle2,
  missing: Circle,
  recommended: Lightbulb,
};

const STATUS_LABEL: Record<HexStatus, string> = {
  covered: "Couvert",
  missing: "Manquant",
  recommended: "Recommande",
};

/**
 * SVG hexagon tile - the atomic unit of the Topical Map.
 *
 * Geometry: flat-top hexagon, base path is M30,0 L60,15 L60,45 L30,60 L0,45 L0,15 Z
 * (60x60 viewBox, scaled via `size`). Width is `size`, visual height is `size`
 * but the actual hex height equals width (flat-top with these coords).
 */
export function HexTile({ topic, onClick, size = 92 }: Props) {
  const styles = STATUS_STYLES[topic.status];
  const Icon = ICONS[topic.status];

  // Truncate label so it fits inside the hex
  const label =
    topic.label.length > 22 ? topic.label.slice(0, 20) + "..." : topic.label;

  const handleClick = () => onClick?.(topic);
  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onClick?.(topic);
    }
  };

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <div
          role="button"
          tabIndex={0}
          onClick={handleClick}
          onKeyDown={handleKey}
          aria-label={`${topic.label} - ${STATUS_LABEL[topic.status]}`}
          className="relative cursor-pointer transition-transform hover:scale-105 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary rounded"
          style={{ width: size, height: size }}
        >
          <svg
            viewBox="0 0 60 60"
            width={size}
            height={size}
            className="drop-shadow-sm"
          >
            <path
              d="M30,0 L60,15 L60,45 L30,60 L0,45 L0,15 Z"
              className={cn(
                "transition-colors",
                styles.fill,
                styles.stroke,
                styles.hover,
              )}
              strokeWidth={1}
            />
          </svg>
          <div
            className={cn(
              "absolute inset-0 flex flex-col items-center justify-center gap-1 pointer-events-none px-2",
              styles.text,
            )}
          >
            <Icon className="h-3.5 w-3.5 shrink-0" />
            <span className="text-[10px] font-medium leading-tight text-center break-words">
              {label}
            </span>
          </div>
        </div>
      </TooltipTrigger>
      <TooltipContent side="top" className="max-w-xs">
        <div className="space-y-1">
          <p className="font-semibold">{topic.label}</p>
          <p className="text-[10px] opacity-80 uppercase tracking-wider">
            {STATUS_LABEL[topic.status]}
          </p>
          <div className="flex gap-3 text-[11px] pt-1">
            {typeof topic.volume === "number" && (
              <span>Vol: {topic.volume.toLocaleString()}</span>
            )}
            {typeof topic.kd === "number" && <span>KD: {topic.kd}</span>}
          </div>
          {topic.status === "recommended" && (
            <p className="text-[10px] opacity-80 pt-1">
              Clic - generer cet article
            </p>
          )}
          {topic.status === "covered" && (
            <p className="text-[10px] opacity-80 pt-1">
              Clic - voir l'article
            </p>
          )}
          {topic.status === "missing" && (
            <p className="text-[10px] opacity-80 pt-1">
              Clic - voir le gap
            </p>
          )}
        </div>
      </TooltipContent>
    </Tooltip>
  );
}
