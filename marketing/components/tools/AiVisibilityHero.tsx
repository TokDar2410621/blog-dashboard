"use client";

import { motion, useReducedMotion } from "motion/react";

/**
 * Hero full-bleed de la page AI Visibility. Deux mains qui se tendent (image
 * reelle generee puis detouree sur transparent, /hero-hands.png) en fond plein
 * ecran (cover) sur du noir, remplissant la largeur. Titre serif. Un scrim
 * sombre en degrade (pas un halo) assure la lisibilite du texte par-dessus.
 */
export function AiVisibilityHero() {
  const reduce = useReducedMotion();

  return (
    <section className="relative flex min-h-[64vh] w-full items-center justify-center overflow-hidden bg-zinc-950">
      {/* Mains, full-bleed, remplissent la largeur */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-cover bg-center bg-no-repeat opacity-95"
        style={{ backgroundImage: "url('/hero-hands.png')" }}
      />

      {/* Scrim sombre en degrade pour la lisibilite (pas un halo) */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(ellipse 60% 58% at center, rgba(9,9,11,0.66) 0%, rgba(9,9,11,0.30) 48%, rgba(9,9,11,0) 82%)",
        }}
      />

      {/* Contenu */}
      <motion.div
        initial={{ opacity: 0, y: 22, filter: "blur(8px)" }}
        animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
        transition={{ duration: 0.9, ease: [0.16, 1, 0.3, 1] }}
        className="relative z-10 max-w-2xl px-4 text-center"
      >
        <div className="mb-4 text-xs font-medium uppercase tracking-[0.3em] text-emerald-400/80">
          AI Visibility Checker
        </div>
        <h1
          style={{ fontFamily: "var(--font-fraunces), Georgia, serif" }}
          className="text-balance text-4xl font-medium leading-[1.05] tracking-tight text-white md:text-6xl"
        >
          Es-tu visible dans l'IA de Google?
        </h1>
        <p className="mx-auto mt-5 max-w-lg text-base leading-relaxed text-zinc-300 md:text-lg">
          Découvre si l'IA de Google (Gemini) recommande ton entreprise ou tes concurrents.
        </p>
      </motion.div>
    </section>
  );
}
