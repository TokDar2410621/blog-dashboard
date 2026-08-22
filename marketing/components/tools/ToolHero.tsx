"use client";

import { motion } from "motion/react";
import type { LucideIcon } from "lucide-react";

type ToolHeroProps = {
  icon: LucideIcon;
  /** Nom court de l'outil, rendu en eyebrow (ex: "AI Visibility Checker"). */
  badge: string;
  title: string;
  subtitle: string;
};

/**
 * Hero cinematique sombre, partage par toutes les pages d'outils publiques.
 * Icone a halo + eyebrow + gros titre + sous-titre, sur un glow d'ambiance,
 * avec une entree motion. Centralise : ajuster ici met a jour toutes les pages.
 */
export function ToolHero({ icon: Icon, badge, title, subtitle }: ToolHeroProps) {
  return (
    <div className="relative mb-12 text-center">
      {/* Glow d'ambiance derriere le titre */}
      <div
        aria-hidden
        className="pointer-events-none absolute left-1/2 top-0 -z-10 h-72 w-[min(90vw,720px)] -translate-x-1/2 -translate-y-1/3 rounded-full bg-emerald-500/10 blur-[110px]"
      />
      <motion.div
        initial={{ opacity: 0, y: 24 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.7, ease: [0.16, 1, 0.3, 1] }}
      >
        <div className="mb-6 inline-flex h-12 w-12 items-center justify-center rounded-2xl border border-white/10 bg-white/[0.03] text-emerald-400 shadow-[0_0_40px_-10px_rgba(16,185,129,0.55)]">
          <Icon className="h-5 w-5" />
        </div>
        <div className="mb-4 text-xs font-medium uppercase tracking-[0.22em] text-emerald-400/70">
          {badge}
        </div>
        <h1 className="mx-auto max-w-3xl text-balance text-4xl font-semibold leading-[1.05] tracking-tight text-white md:text-5xl lg:text-6xl">
          {title}
        </h1>
        <p className="mx-auto mt-5 max-w-xl text-base leading-relaxed text-zinc-400 md:text-lg">
          {subtitle}
        </p>
      </motion.div>
    </div>
  );
}
