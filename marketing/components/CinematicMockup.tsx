"use client";

import { useRef } from "react";
import {
  motion,
  useScroll,
  useTransform,
  useSpring,
  useReducedMotion,
} from "motion/react";
import ProductMockup3D from "@/components/ProductMockup3D";

/**
 * Revele le mockup produit au scroll (scale + montee lies a la position de
 * scroll, pas une animation au mount). Le mockup grossit et se redresse au fur
 * et a mesure qu'il entre dans le viewport, facon Apple. Respecte
 * prefers-reduced-motion (rendu statique).
 */
export function CinematicMockup() {
  const ref = useRef<HTMLDivElement>(null);
  const reduce = useReducedMotion();
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ["start end", "center center"],
  });

  const scaleRaw = useTransform(scrollYProgress, [0, 1], [0.82, 1.04]);
  const scale = useSpring(scaleRaw, { stiffness: 90, damping: 30, mass: 0.5 });
  const yRaw = useTransform(scrollYProgress, [0, 1], [70, 0]);
  const y = useSpring(yRaw, { stiffness: 90, damping: 30, mass: 0.5 });
  const opacity = useTransform(scrollYProgress, [0, 0.5], [0.25, 1]);

  return (
    <div ref={ref}>
      <motion.div style={reduce ? undefined : { scale, y, opacity }}>
        <ProductMockup3D />
      </motion.div>
    </div>
  );
}
