"use client";

import { motion, useReducedMotion } from "motion/react";

/**
 * Hero specifique a la page AI Visibility. Deux mains qui se tendent (image
 * reelle detouree, /hero-hands.png) emergeant du noir, avec une etincelle
 * emerald a la jonction des doigts (la connexion = rejoindre la visibilite IA).
 * Titre serif. Placeholder basse-res a swapper par une image HD.
 */
export function AiVisibilityHero() {
  const reduce = useReducedMotion();

  return (
    <div className="relative mb-10 flex min-h-[62vh] flex-col items-center justify-center overflow-hidden px-4 py-16 text-center">
      {/* Mains reaching, en fond */}
      <div className="pointer-events-none absolute inset-0 -z-20 flex items-center justify-center">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src="/hero-hands.png"
          alt=""
          aria-hidden="true"
          className="w-[min(94%,720px)] select-none object-contain opacity-[0.55]"
        />
      </div>

      {/* Vignette sombre pour la lisibilite du texte */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 -z-10"
        style={{
          background:
            "radial-gradient(ellipse 60% 62% at center, transparent 8%, rgba(9,9,11,0.80) 72%)",
        }}
      />

      {/* Etincelle emerald a la jonction des doigts */}
      <motion.div
        aria-hidden
        className="pointer-events-none absolute left-1/2 top-[42%] -z-10 h-48 w-48 -translate-x-1/2 -translate-y-1/2 rounded-full bg-emerald-400/40 blur-[64px]"
        animate={
          reduce ? undefined : { opacity: [0.35, 0.85, 0.35], scale: [0.9, 1.12, 0.9] }
        }
        transition={{ duration: 3.2, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.div
        aria-hidden
        className="pointer-events-none absolute left-1/2 top-[42%] -z-10 h-2 w-2 -translate-x-1/2 -translate-y-1/2 rounded-full bg-emerald-200"
        style={{ boxShadow: "0 0 22px 7px rgba(52,211,153,0.75)" }}
        animate={reduce ? undefined : { opacity: [0.6, 1, 0.6], scale: [1, 1.7, 1] }}
        transition={{ duration: 3.2, repeat: Infinity, ease: "easeInOut" }}
      />

      {/* Contenu */}
      <motion.div
        initial={{ opacity: 0, y: 22, filter: "blur(8px)" }}
        animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
        transition={{ duration: 0.9, ease: [0.16, 1, 0.3, 1] }}
        className="relative max-w-2xl"
      >
        <div className="mb-5 text-xs font-medium uppercase tracking-[0.3em] text-emerald-400/70">
          AI Visibility Checker
        </div>
        <h1
          style={{ fontFamily: "var(--font-fraunces), Georgia, serif" }}
          className="text-balance text-4xl font-medium leading-[1.05] tracking-tight text-white md:text-6xl"
        >
          Es-tu visible dans l'IA de Google?
        </h1>
        <p className="mx-auto mt-6 max-w-lg text-base leading-relaxed text-zinc-400 md:text-lg">
          Découvre si l'IA de Google (Gemini) recommande ton entreprise ou tes concurrents.
        </p>
      </motion.div>
    </div>
  );
}
