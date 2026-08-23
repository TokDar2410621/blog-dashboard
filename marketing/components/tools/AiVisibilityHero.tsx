"use client";

import type { ReactNode } from "react";
import { motion, useReducedMotion } from "motion/react";

/**
 * Hero full-bleed de la page AI Visibility. Deux mains qui se tendent (image
 * reelle detouree, /hero-hands.png) en fond plein ecran sur du noir. Le titre
 * serif est au centre ; l'image se fond vers le noir en bas, et la barre
 * d'input (children) se pose dans cette zone de transition image -> noir.
 */
export function AiVisibilityHero({ children }: { children?: ReactNode }) {
  const reduce = useReducedMotion();

  return (
    <section className="relative flex min-h-[calc(100svh-68px)] w-full flex-col items-center justify-center overflow-hidden bg-zinc-950 px-4">
      {/* Mains, full-bleed */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 bg-cover bg-center bg-no-repeat opacity-95"
        style={{ backgroundImage: "url('/hero-hands.png')" }}
      />

      {/* Scrim radial pour la lisibilite du titre */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(ellipse 58% 50% at center 38%, rgba(9,9,11,0.62) 0%, rgba(9,9,11,0.25) 45%, rgba(9,9,11,0) 78%)",
        }}
      />

      {/* Fondu vers le noir en bas : l'input se pose ici */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 bottom-0 h-2/3"
        style={{
          background:
            "linear-gradient(to bottom, rgba(9,9,11,0) 0%, rgba(9,9,11,0.78) 55%, rgb(9,9,11) 100%)",
        }}
      />

      {/* Contenu */}
      <div className="relative z-10 flex w-full max-w-2xl flex-col items-center text-center">
        <motion.div
          initial={{ opacity: 0, y: 22, filter: "blur(8px)" }}
          animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
          transition={{ duration: 0.9, ease: [0.16, 1, 0.3, 1] }}
        >
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

        {children && (
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.25, ease: [0.16, 1, 0.3, 1] }}
            className="mt-16 w-full max-w-xl"
          >
            {children}
          </motion.div>
        )}
      </div>
    </section>
  );
}
