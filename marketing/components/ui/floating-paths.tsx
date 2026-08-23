import React from "react";
import { cn } from "@/lib/utils";

/**
 * Fond de traits pour le hero.
 *
 * La version d'origine anime `pathLength` et `pathOffset` avec motion sur
 * chacun des 36 traits. Mesure du 2026-08-23 sur cette landing en 1440x900 :
 * 6 images par seconde, et la longueur du tiret qui retombe de 0,96 a 0,32
 * d'un coup a chaque bouclage. Deux defauts avec la meme racine :
 *
 * - `stroke-dasharray` et `stroke-dashoffset` obligent le navigateur a
 *   recalculer la geometrie du trace a chaque image, sur 36 courbes qui
 *   debordent largement du cadre. Rien de cela ne part au compositeur.
 * - `pathLength` monte de 0,3 a 1 pendant le cycle puis repart de 0,3 au
 *   redemarrage. Chaque trait ayant sa propre duree, ces ruptures tombent a
 *   des moments differents et se lisent comme un clignotement.
 *
 * Passer ces memes animations en CSS ne change rien a la cadence (mesure : 33
 * a 45 i/s contre 43 a 47 avant). Le cout ne vient pas de ce qui pilote
 * l'animation mais du fait de repeindre 36 grandes courbes a chaque image, et
 * animer quoi que ce soit A L'INTERIEUR du SVG force ce repaint.
 *
 * D'ou la forme retenue : le SVG ne bouge plus du tout, il est rasterise une
 * fois. C'est le calque HTML qui le porte qui derive, par transform, ce que le
 * compositeur execute sans repeindre. Les traits sont entiers et sans tiret,
 * donc ils ne peuvent plus se couper.
 *
 * Le calque deborde du hero (-inset-12) pour que la derive ne decouvre jamais
 * de bord. Plus de motion ici, donc plus de dependance a useReducedMotion(),
 * dont le defaut est documente ailleurs dans ce projet.
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
    // L'original monte a 0,1 + 35*0,03, donc sature a 1 sur les derniers
    // traits. Il est ecrit pour du slate-950 sur fond clair, ou une barre
    // opaque se lit comme un trait fin. Ici les traits sont blancs sur noir et
    // la meme valeur donne des bandes qui traversent le titre. Plafond a 0,22.
    opacity: 0.03 + i * 0.0055,
  }));

  return (
    // `overflow-hidden` va avec le -inset-12 du calque : sans lui, le
    // debordement de 3 rem ajoute une barre de defilement horizontale.
    <div className={cn("w-full relative overflow-hidden", className)}>
      <div
        className="floating-paths-layer absolute -inset-12 pointer-events-none"
        aria-hidden="true"
      >
        <svg
          className="floating-paths h-full w-full text-slate-950 dark:text-white"
          viewBox="0 40 696 316"
          fill="none"
          preserveAspectRatio="xMidYMid slice"
        >
          {paths.map((path) => (
            <path
              key={path.id}
              d={path.d}
              stroke="currentColor"
              strokeWidth={path.width}
              strokeOpacity={path.opacity}
            />
          ))}
        </svg>
      </div>
      {children}
    </div>
  );
}

export default FloatingPathsBackground;
