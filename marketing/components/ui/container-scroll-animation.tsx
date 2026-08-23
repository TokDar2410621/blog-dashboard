"use client";

import React, { useRef } from "react";
import { motion, useScroll, useTransform, type MotionValue } from "motion/react";
import { cn } from "@/lib/utils";

/**
 * ContainerScroll - l'ecran qui se redresse au scroll.
 *
 * La carte entre inclinee (rotateX 20deg) et s'aplatit a mesure que la section
 * traverse le viewport, pendant que le titre monte. Tout est pilote par la
 * position de scroll, jamais par une animation au mount : la progression suit
 * le doigt, sans easing parasite.
 *
 *   <ContainerScroll titleComponent={<h2>...</h2>}>
 *     <MonDashboard />
 *   </ContainerScroll>
 *
 * Transform et opacite uniquement, donc composite sur le GPU.
 *
 * MOUVEMENT SOBRE : la neutralisation passe par CSS
 * (.container-scroll-card / .container-scroll-header dans globals.css) et NON
 * par useReducedMotion(). Mesure du 2026-08-23 : dans motion@13, le hook rend
 * `false` alors que matchMedia('(prefers-reduced-motion: reduce)').matches vaut
 * `true`, parce qu'il ne se met a jour que sur l'evenement `change` de la media
 * query, lequel ne se declenche jamais quand la preference etait deja posee
 * avant le chargement. La media query CSS, elle, est juste des le premier
 * paint.
 */
export const ContainerScroll = ({
  titleComponent,
  children,
  className,
  cardClassName,
}: {
  titleComponent: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  cardClassName?: string;
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  // Offset explicite : l'offset par defaut ["start start", "end end"] rend une
  // course egale a (hauteur de section - hauteur de viewport), qui s'ecrase a
  // quelques pixels sur un ecran de 900px et s'INVERSE au-dela de 60rem de
  // haut. Ici la carte se redresse entre son entree par le bas et le moment ou
  // elle est centree, comme le reste de la maison (CinematicMockup).
  const { scrollYProgress } = useScroll({
    target: containerRef,
    offset: ["start end", "center center"],
  });
  const isMobile = useIsMobile();

  // Pas de reduction d'echelle sur mobile : la carte est deja w-full, elle ne
  // deborde pas, et un scale 0,7 rendrait la typographie du dashboard sous les
  // 10px. Elle se contente donc de ne pas grossir.
  const scaleRange: [number, number] = isMobile ? [1, 1] : [1.05, 1];

  const rotate = useTransform(scrollYProgress, [0, 1], [20, 0]);
  const scale = useTransform(scrollYProgress, [0, 1], scaleRange);
  const translate = useTransform(scrollYProgress, [0, 1], [0, -100]);

  return (
    <div
      ref={containerRef}
      className={cn(
        "relative flex h-[60rem] items-center justify-center p-2 md:h-[80rem] md:p-20",
        className,
      )}
    >
      <div
        className="relative w-full py-10 md:py-40"
        style={{ perspective: "1000px" }}
      >
        <Header translate={translate}>{titleComponent}</Header>
        <Card rotate={rotate} scale={scale} className={cardClassName}>
          {children}
        </Card>
      </div>
    </div>
  );
};

/** Le titre monte pendant que la carte se redresse : deux vitesses, une lecture. */
export const Header = ({
  translate,
  children,
}: {
  translate: MotionValue<number>;
  children: React.ReactNode;
}) => (
  <motion.div
    style={{ translateY: translate }}
    // pb-16 compense la remontee de la carte (-mt-12) plus sa surcote d'echelle
    // a l'entree (1,05). Sans ce coussin, le chassis peint par-dessus la
    // derniere ligne du sous-titre pendant le premier tiers du defilement.
    className="container-scroll-header mx-auto max-w-5xl pb-16 text-center"
  >
    {children}
  </motion.div>
);

/** Le chassis : bordure epaisse, ecran mat, contenu clippe dans l'ecran. */
export const Card = ({
  rotate,
  scale,
  className,
  children,
}: {
  rotate: MotionValue<number>;
  scale: MotionValue<number>;
  className?: string;
  children: React.ReactNode;
}) => (
  <motion.div
    style={{
      rotateX: rotate,
      scale,
      boxShadow:
        "0 0 #0000004d, 0 9px 20px #0000004a, 0 37px 37px #00000042, 0 84px 50px #00000026, 0 149px 60px #0000000a, 0 233px 65px #00000003",
    }}
    // La marge negative compense la montee du titre. En mode sobre le titre ne
    // bouge pas, donc globals.css remet une marge positive pour eviter que la
    // carte lui rentre dedans.
    className={cn(
      // 34rem en etroit : les titres passent sur deux lignes sous md pour rester
      // lisibles, ce qui coute de la hauteur. Mesure a l'appui, 30rem tranchait
      // les dernieres lignes.
      "container-scroll-card mx-auto -mt-12 h-[34rem] w-full max-w-5xl rounded-[30px] border-4 border-zinc-700 bg-zinc-900 p-2 shadow-2xl md:h-[40rem] md:p-6",
      className,
    )}
  >
    <div className="h-full w-full overflow-hidden rounded-2xl bg-zinc-950 md:rounded-2xl">
      {children}
    </div>
  </motion.div>
);

/**
 * matchMedia plutot qu'un listener resize : pas de lecture de layout a chaque
 * pixel redimensionne, et le navigateur ne notifie qu'au franchissement du
 * seuil. Rend false au premier paint serveur, donc l'echelle desktop est le
 * defaut et mobile se corrige a l'hydratation.
 */
function useIsMobile(query = "(width < 48rem)") {
  const [isMobile, setIsMobile] = React.useState(false);

  React.useEffect(() => {
    const mql = window.matchMedia(query);
    const sync = () => setIsMobile(mql.matches);
    sync();
    mql.addEventListener("change", sync);
    return () => mql.removeEventListener("change", sync);
  }, [query]);

  return isMobile;
}
