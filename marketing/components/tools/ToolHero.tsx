"use client";

import { motion, useReducedMotion } from "motion/react";
import type { LucideIcon } from "lucide-react";

type ToolHeroProps = {
  icon: LucideIcon;
  /** Nom court de l'outil, rendu en eyebrow (ex: "AI Visibility Checker"). */
  badge: string;
  title: string;
  subtitle: string;
};

const container = {
  hidden: {},
  show: { transition: { staggerChildren: 0.12, delayChildren: 0.1 } },
};

const item = {
  hidden: { opacity: 0, y: 20, filter: "blur(8px)" },
  show: {
    opacity: 1,
    y: 0,
    filter: "blur(0px)",
    transition: { duration: 0.9, ease: [0.16, 1, 0.3, 1] as const },
  },
};

const SCAN_LINES = [20, 50, 80];

function Corner({ pos }: { pos: string }) {
  return (
    <div
      aria-hidden
      className={`pointer-events-none absolute h-7 w-7 border-emerald-400/50 ${pos}`}
    />
  );
}

/**
 * Hero cinematique sombre au motif "viseur / scan", partage par toutes les
 * pages d'outils. Panneau central avec coins en equerre + lignes de scan
 * animees + icone-embleme a anneaux + titre serif (Fraunces). Entree
 * choregraphiee (stagger + flou qui se dissipe). Respecte prefers-reduced-motion.
 * Centralise : ajuster ici met a jour toutes les pages d'outils.
 */
export function ToolHero({ icon: Icon, badge, title, subtitle }: ToolHeroProps) {
  const reduce = useReducedMotion();

  return (
    <div className="relative mb-12 pt-6">
      <div className="relative mx-auto max-w-3xl overflow-hidden rounded-[28px] border border-white/[0.08] bg-gradient-to-b from-white/[0.05] via-white/[0.02] to-transparent px-6 py-16 text-center shadow-[0_0_80px_-20px_rgba(16,185,129,0.35)] md:py-20">
        {/* Lignes de scan */}
        <div aria-hidden className="pointer-events-none absolute inset-0 -z-10">
          {SCAN_LINES.map((top) => (
            <motion.div
              key={top}
              className="absolute left-0 right-0 h-px bg-gradient-to-r from-transparent via-emerald-400/50 to-transparent"
              style={{ top: `${top}%` }}
              animate={reduce ? undefined : { opacity: [0.15, 0.6, 0.15] }}
              transition={{
                duration: 4.5,
                repeat: Infinity,
                ease: "easeInOut",
                delay: top / 60,
              }}
            />
          ))}
        </div>

        {/* Glow d'ambiance */}
        <div
          aria-hidden
          className="pointer-events-none absolute left-1/2 top-0 -z-10 h-72 w-[440px] -translate-x-1/2 -translate-y-1/4 rounded-full bg-emerald-500/20 blur-[120px]"
        />

        {/* Coins en equerre (viseur) */}
        <Corner pos="left-4 top-4 border-l-2 border-t-2 rounded-tl-sm" />
        <Corner pos="right-4 top-4 border-r-2 border-t-2 rounded-tr-sm" />
        <Corner pos="bottom-4 left-4 border-b-2 border-l-2 rounded-bl-sm" />
        <Corner pos="bottom-4 right-4 border-b-2 border-r-2 rounded-br-sm" />

        <motion.div variants={container} initial="hidden" animate="show">
          {/* Icone-embleme a anneaux */}
          <motion.div
            variants={item}
            className="relative mx-auto mb-8 flex h-20 w-20 items-center justify-center"
          >
            <div className="absolute inset-0 rounded-full bg-emerald-500/25 blur-2xl" />
            <div className="absolute inset-0 rounded-full border border-emerald-400/25" />
            <div className="absolute inset-[6px] rounded-full border border-emerald-400/15" />
            <div className="absolute inset-[12px] rounded-full border border-emerald-400/10" />
            <Icon className="relative h-8 w-8 text-emerald-400" strokeWidth={1.5} />
          </motion.div>

          <motion.div
            variants={item}
            className="mb-5 text-[0.7rem] font-medium uppercase tracking-[0.34em] text-emerald-400/70"
          >
            {badge}
          </motion.div>

          <motion.h1
            variants={item}
            style={{ fontFamily: "var(--font-fraunces), Georgia, serif" }}
            className="mx-auto max-w-2xl text-balance text-4xl font-medium leading-[1.05] tracking-tight text-white md:text-6xl"
          >
            {title}
          </motion.h1>

          <motion.p
            variants={item}
            className="mx-auto mt-6 max-w-lg text-base leading-relaxed text-zinc-400 md:text-lg"
          >
            {subtitle}
          </motion.p>
        </motion.div>
      </div>
    </div>
  );
}
