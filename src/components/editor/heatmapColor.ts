/**
 * Maps a value in [0, max] to a Tailwind background class on a zinc -> emerald
 * gradient. Mirrors the Clearscope/Surfer heatmap aesthetic: dark when absent,
 * bright emerald when the term is heavily used in that competing URL.
 *
 * Returns a class string that includes both a background and a foreground
 * color so the displayed number stays readable across the gradient.
 */
export function heatmapColor(value: number, max: number): string {
  if (!Number.isFinite(value) || value <= 0) {
    return "bg-zinc-900/60 text-zinc-500";
  }
  const ceiling = Math.max(1, max);
  const ratio = Math.min(1, value / ceiling);

  // 5-step quantized scale so Tailwind can statically detect all classes.
  if (ratio >= 0.85) return "bg-emerald-500 text-emerald-50";
  if (ratio >= 0.65) return "bg-emerald-600 text-emerald-50";
  if (ratio >= 0.45) return "bg-emerald-700 text-emerald-50";
  if (ratio >= 0.25) return "bg-emerald-800 text-emerald-100";
  return "bg-emerald-950 text-emerald-200";
}

/**
 * Deterministic pseudo-random in [0, 1) seeded from a string. Used to fake
 * competing-URL frequencies in V1 until the backend ships
 * gridar_serp_analyze.
 */
export function seededRandom(seed: string): () => number {
  let h = 2166136261 >>> 0;
  for (let i = 0; i < seed.length; i++) {
    h ^= seed.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return () => {
    h += 0x6d2b79f5;
    let t = h;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
