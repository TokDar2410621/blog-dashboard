"use client";

import React from "react";
import { motion } from "motion/react";
import { cn } from "@/lib/utils";

/**
 * Fond de traits qui derivent lentement. Trois ecarts avec la version
 * d'origine, chacun pour une raison mesuree dans ce projet :
 *
 * 1. Duree deterministe au lieu de Math.random() dans le rendu. Cette page
 *    est prerendue, donc un aleatoire tire pendant le rendu donne une valeur
 *    au serveur et une autre au client, ce qui casse l'hydratation. Le
 *    dephasage vient maintenant de l'index, qui donne le meme desordre visuel
 *    sans divergence.
 * 2. Mouvement neutralise via matchMedia lu directement au montage, et non
 *    via useReducedMotion(). Mesure du 2026-08-23 notee dans globals.css :
 *    le hook de motion@13 rend `false` alors que la media query correspond,
 *    parce qu'il n'ecoute que l'evenement `change`, qui ne survient jamais si
 *    la preference etait deja posee avant le chargement.
 * 3. Le champ `color` du tableau d'origine est retire : les traits peignent
 *    avec `currentColor`, il n'etait jamais lu.
 */
export function FloatingPathsBackground({
  position,
  children,
  className,
}: {
  position: number;
  className?: string;
  children: React.ReactNode;
}) {
  const [immobile, setImmobile] = React.useState(false);

  React.useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return;
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setImmobile(mq.matches);
    const onChange = (e: MediaQueryListEvent) => setImmobile(e.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  const paths = Array.from({ length: 36 }, (_, i) => ({
    id: i,
    d: `M-${380 - i * 5 * position} -${189 + i * 6}C-${
      380 - i * 5 * position
    } -${189 + i * 6} -${312 - i * 5 * position} ${216 - i * 6} ${
      152 - i * 5 * position
    } ${343 - i * 6}C${616 - i * 5 * position} ${470 - i * 6} ${
      684 - i * 5 * position
    } ${875 - i * 6} ${684 - i * 5 * position} ${875 - i * 6}`,
    width: 0.5 + i * 0.03,
    // 20 a 30 s, reparti sans repetition visible et identique des deux cotes.
    duration: 20 + ((i * 7) % 11),
    // L'original monte a 0.1 + 35 * 0.03, donc sature a 1 sur les derniers
    // traits. Ecrit pour du slate-950 sur fond clair, ou une barre opaque se
    // lit comme un trait fin. Ici les traits sont blancs sur noir et la meme
    // valeur donne des bandes qui traversent le titre. Plafond ramene a 0.22.
    opacity: 0.03 + i * 0.0055,
  }));

  return (
    <div className={cn("w-full relative", className)}>
      <div className="absolute inset-0 pointer-events-none" aria-hidden="true">
        <svg
          className="floating-paths w-full h-full text-slate-950 dark:text-white"
          viewBox="0 0 696 316"
          fill="none"
          preserveAspectRatio="xMidYMid slice"
        >
          {paths.map((path) => (
            <motion.path
              key={path.id}
              d={path.d}
              stroke="currentColor"
              strokeWidth={path.width}
              strokeOpacity={path.opacity}
              initial={{ pathLength: 0.3, opacity: 0.6 }}
              animate={
                immobile
                  ? { pathLength: 1, opacity: 0.5 }
                  : {
                      pathLength: 1,
                      opacity: [0.35, 0.7, 0.35],
                      pathOffset: [0, 1, 0],
                    }
              }
              transition={
                immobile
                  ? { duration: 0 }
                  : {
                      duration: path.duration,
                      repeat: Number.POSITIVE_INFINITY,
                      ease: "linear",
                    }
              }
            />
          ))}
        </svg>
      </div>
      {children}
    </div>
  );
}

export default FloatingPathsBackground;
