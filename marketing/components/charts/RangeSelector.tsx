"use client";

import { ToggleGroup as ToggleGroupPrimitive } from "radix-ui";
import { cn } from "@/lib/utils";

export type RangeValue = "7d" | "30d" | "90d" | "6mo" | "1y";

// Labels map to J / S / M / 3M / 1A (jour, semaine, mois, 3 mois, 1 an).
const OPTIONS: Array<{ value: RangeValue; label: string }> = [
  { value: "7d", label: "J" },
  { value: "30d", label: "S" },
  { value: "90d", label: "M" },
  { value: "6mo", label: "3M" },
  { value: "1y", label: "1A" },
];

interface RangeSelectorProps {
  value: RangeValue;
  onChange: (value: RangeValue) => void;
  className?: string;
}

export function RangeSelector({ value, onChange, className }: RangeSelectorProps) {
  return (
    <ToggleGroupPrimitive.Root
      type="single"
      value={value}
      onValueChange={(v) => {
        if (v) onChange(v as RangeValue);
      }}
      className={cn(
        "inline-flex items-center rounded-md border bg-muted/30 p-0.5 text-xs",
        className
      )}
    >
      {OPTIONS.map((opt) => (
        <ToggleGroupPrimitive.Item
          key={opt.value}
          value={opt.value}
          className={cn(
            "px-2.5 h-7 rounded-sm font-mono uppercase tracking-wider text-muted-foreground",
            "hover:text-foreground transition-colors",
            "data-[state=on]:bg-background data-[state=on]:text-foreground data-[state=on]:shadow-sm"
          )}
          aria-label={`Periode ${opt.label}`}
        >
          {opt.label}
        </ToggleGroupPrimitive.Item>
      ))}
    </ToggleGroupPrimitive.Root>
  );
}

export { OPTIONS as RANGE_OPTIONS };
