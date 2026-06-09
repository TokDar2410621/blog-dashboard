import { useMemo } from "react";

export type LetterGrade = "F" | "C" | "B" | "A" | "A+";

export function scoreToGrade(score: number): LetterGrade {
  if (score >= 95) return "A+";
  if (score >= 80) return "A";
  if (score >= 60) return "B";
  if (score >= 40) return "C";
  return "F";
}

/**
 * Tailwind palette uses CSS variables for emerald/cyan/amber/destructive in the
 * Gridar theme. We map score buckets to the same color scale that the rest of
 * the dashboard already uses (see SEOAnalyzer.tsx).
 */
function colorsForScore(score: number) {
  if (score >= 80) {
    return {
      stroke: "stroke-emerald-500",
      fill: "fill-emerald-500",
      text: "text-emerald-500",
      bg: "bg-emerald-500/10",
      ring: "rgb(16 185 129)",
    };
  }
  if (score >= 60) {
    return {
      stroke: "stroke-cyan-500",
      fill: "fill-cyan-500",
      text: "text-cyan-500",
      bg: "bg-cyan-500/10",
      ring: "rgb(6 182 212)",
    };
  }
  if (score >= 40) {
    return {
      stroke: "stroke-amber-500",
      fill: "fill-amber-500",
      text: "text-amber-500",
      bg: "bg-amber-500/10",
      ring: "rgb(245 158 11)",
    };
  }
  return {
    stroke: "stroke-rose-500",
    fill: "fill-rose-500",
    text: "text-rose-500",
    bg: "bg-rose-500/10",
    ring: "rgb(244 63 94)",
  };
}

export interface ContentScoreGaugeProps {
  /** 0-100 */
  score: number;
  /** Last N scores for sparkline (optional). Most recent at the end. */
  trend?: number[];
  /** Override the computed letter grade label. */
  letterGrade?: LetterGrade;
  /** Optional sublabel under the score, eg. "Content Score". */
  label?: string;
}

/**
 * Surfer/Clearscope-style animated content score gauge.
 *
 * Uses a single SVG circle whose stroke-dasharray animates on score change.
 * Renders a letter grade and an optional 7-point sparkline below.
 */
export function ContentScoreGauge({
  score,
  trend,
  letterGrade,
  label = "Content Score",
}: ContentScoreGaugeProps) {
  const clamped = Math.max(0, Math.min(100, Math.round(score)));
  const grade = letterGrade ?? scoreToGrade(clamped);
  const colors = useMemo(() => colorsForScore(clamped), [clamped]);

  // Geometry: viewBox 200x200, stroke ring radius 88 -> circumference ~553
  const R = 88;
  const CIRC = 2 * Math.PI * R;
  const offset = CIRC * (1 - clamped / 100);

  // Sparkline path (last 7 points)
  const sparkPath = useMemo(() => {
    if (!trend || trend.length < 2) return null;
    const pts = trend.slice(-7);
    const w = 120;
    const h = 28;
    const min = 0;
    const max = 100;
    const step = w / (pts.length - 1);
    return pts
      .map((v, i) => {
        const x = i * step;
        const y = h - ((Math.max(min, Math.min(max, v)) - min) / (max - min)) * h;
        return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(" ");
  }, [trend]);

  return (
    <div className="flex flex-col items-center gap-2 select-none">
      <div className="relative">
        <svg viewBox="0 0 200 200" className="w-[180px] h-[180px]" aria-hidden>
          {/* Track */}
          <circle
            cx="100"
            cy="100"
            r={R}
            className="fill-none stroke-border"
            strokeWidth="14"
          />
          {/* Progress */}
          <circle
            cx="100"
            cy="100"
            r={R}
            className={`fill-none ${colors.stroke}`}
            strokeWidth="14"
            strokeLinecap="round"
            strokeDasharray={CIRC}
            strokeDashoffset={offset}
            style={{
              transform: "rotate(-90deg)",
              transformOrigin: "100px 100px",
              transition:
                "stroke-dashoffset 700ms cubic-bezier(0.22, 1, 0.36, 1), stroke 300ms ease",
            }}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <div className={`text-5xl font-bold tabular-nums ${colors.text}`}>
            {clamped}
          </div>
          <div className="text-xs uppercase tracking-widest text-muted-foreground mt-0.5">
            / 100
          </div>
        </div>
      </div>

      <div className="flex flex-col items-center">
        <div className="flex items-baseline gap-2">
          <span
            className={`text-2xl font-black ${colors.text}`}
            aria-label={`Grade ${grade}`}
          >
            {grade}
          </span>
          <span className="text-xs text-muted-foreground">{label}</span>
        </div>

        {sparkPath && (
          <div className="mt-2">
            <svg
              viewBox="0 0 120 28"
              className="w-[120px] h-[28px]"
              aria-label="Score trend (last 7)"
            >
              <path
                d={sparkPath}
                className={`fill-none ${colors.stroke}`}
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
              {/* End dot */}
              {trend && trend.length > 0 && (
                <circle
                  cx="120"
                  cy={
                    28 -
                    (Math.max(0, Math.min(100, trend[trend.length - 1])) / 100) *
                      28
                  }
                  r="2"
                  className={colors.fill}
                />
              )}
            </svg>
          </div>
        )}
      </div>
    </div>
  );
}
