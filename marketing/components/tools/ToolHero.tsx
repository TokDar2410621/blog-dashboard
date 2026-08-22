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
  show: { transition: { staggerChildren: 0.12, delayChildren: 0.15 } },
};

const item = {
  hidden: { opacity: 0, y: 24, filter: "blur(10px)" },
  show: {
    opacity: 1,
    y: 0,
    filter: "blur(0px)",
    transition: { duration: 0.9, ease: [0.16, 1, 0.3, 1] as const },
  },
};

/**
 * Hero cinematique sombre, partage par toutes les pages d'outils publiques.
 * Aurore vivante en arriere-plan (halos qui derivent en boucle) + grille de
 * profondeur + entree choregraphiee (stagger + flou qui se dissipe).
 * Centralise : ajuster ici met a jour toutes les pages d'outils.
 */
export function ToolHero({ icon: Icon, badge, title, subtitle }: ToolHeroProps) {
  const reduce = useReducedMotion();

  return (
    <div className="relative isolate mb-14 overflow-hidden pt-4 text-center">
      {/* Aurore vivante */}
      <div aria-hidden className="pointer-events-none absolute inset-0 -z-10">
        <motion.div
          className="absolute left-1/2 top-[-25%] h-[540px] w-[540px] -translate-x-1/2 rounded-full bg-emerald-500/25 blur-[130px]"
          animate={
            reduce
              ? undefined
              : { x: [0, 60, -40, 0], y: [0, 30, -20, 0], scale: [1, 1.15, 0.95, 1] }
          }
          transition={{ duration: 20, repeat: Infinity, ease: "easeInOut" }}
        />
        <motion.div
          className="absolute left-[18%] top-[5%] h-[380px] w-[380px] rounded-full bg-cyan-500/15 blur-[120px]"
          animate={
            reduce
              ? undefined
              : { x: [0, -50, 30, 0], y: [0, 40, 10, 0], opacity: [0.5, 0.85, 0.55, 0.5] }
          }
          transition={{ duration: 26, repeat: Infinity, ease: "easeInOut" }}
        />
        <motion.div
          className="absolute right-[14%] top-[-5%] h-[320px] w-[320px] rounded-full bg-emerald-400/10 blur-[110px]"
          animate={reduce ? undefined : { x: [0, 40, -30, 0], y: [0, -30, 20, 0] }}
          transition={{ duration: 23, repeat: Infinity, ease: "easeInOut" }}
        />
      </div>

      {/* Grille de profondeur, masquee aux bords */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 -z-10 opacity-[0.15] [mask-image:radial-gradient(ellipse_at_center,black,transparent_70%)]"
        style={{
          backgroundImage:
            "linear-gradient(to right, rgba(255,255,255,0.06) 1px, transparent 1px), linear-gradient(to bottom, rgba(255,255,255,0.06) 1px, transparent 1px)",
          backgroundSize: "44px 44px",
        }}
      />

      <motion.div
        variants={container}
        initial="hidden"
        animate="show"
        className="py-16 md:py-24"
      >
        <motion.div
          variants={item}
          className="mb-6 inline-flex h-14 w-14 items-center justify-center rounded-2xl border border-white/10 bg-white/[0.03] text-emerald-400 shadow-[0_0_50px_-8px_rgba(16,185,129,0.6)] backdrop-blur-sm"
        >
          <Icon className="h-6 w-6" />
        </motion.div>
        <motion.div
          variants={item}
          className="mb-5 text-xs font-medium uppercase tracking-[0.28em] text-emerald-400/70"
        >
          {badge}
        </motion.div>
        <motion.h1
          variants={item}
          className="mx-auto max-w-4xl text-balance text-4xl font-semibold leading-[1.02] tracking-tight text-white md:text-6xl lg:text-7xl"
        >
          {title}
        </motion.h1>
        <motion.p
          variants={item}
          className="mx-auto mt-6 max-w-xl text-base leading-relaxed text-zinc-400 md:text-lg"
        >
          {subtitle}
        </motion.p>
      </motion.div>
    </div>
  );
}
