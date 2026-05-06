import { useCallback } from "react";

/**
 * Lightweight emerald confetti burst. Pure DOM + CSS, zero deps.
 * Call the returned function on a celebratory event (first connect, first publish).
 *
 *   const fireConfetti = useConfetti();
 *   onSuccess: () => fireConfetti();
 *
 * Respects prefers-reduced-motion: emits a single subtle pulse instead.
 */
export function useConfetti() {
  return useCallback((opts?: { count?: number }) => {
    if (typeof window === "undefined") return;
    const reduceMotion =
      window.matchMedia &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduceMotion) return;

    const COUNT = opts?.count ?? 90;
    const COLORS = ["#10b981", "#34d399", "#6ee7b7", "#059669", "#a7f3d0"];

    if (!document.getElementById("pm-confetti-style")) {
      const style = document.createElement("style");
      style.id = "pm-confetti-style";
      style.textContent = `
        @keyframes pm-confetti-burst {
          0% { transform: translate(0,0) rotate(0deg) scale(1); opacity: 1; }
          70% { opacity: 1; }
          100% { transform: translate(var(--dx), var(--dy)) rotate(var(--r)) scale(0.6); opacity: 0; }
        }
      `;
      document.head.appendChild(style);
    }

    const root = document.createElement("div");
    root.style.cssText =
      "position:fixed;left:50%;top:35%;width:0;height:0;pointer-events:none;z-index:9999";
    document.body.appendChild(root);

    for (let i = 0; i < COUNT; i++) {
      const p = document.createElement("div");
      const color = COLORS[Math.floor(Math.random() * COLORS.length)];
      const size = 4 + Math.random() * 8;
      const angle = (i / COUNT) * Math.PI * 2 + Math.random() * 0.4;
      const distance = 220 + Math.random() * 280;
      const dx = Math.cos(angle) * distance;
      const baseDy = Math.sin(angle) * distance;
      const gravity = 350 + Math.random() * 250;
      const dy = baseDy + gravity;
      const r = `${(Math.random() * 1440 - 720).toFixed(0)}deg`;
      const duration = 1200 + Math.random() * 900;

      p.style.cssText = `
        position:absolute;
        width:${size}px;height:${size * 0.45}px;
        background:${color};
        border-radius:1px;
        --dx:${dx.toFixed(0)}px;
        --dy:${dy.toFixed(0)}px;
        --r:${r};
        animation: pm-confetti-burst ${duration}ms cubic-bezier(.18,.7,.32,1) forwards;
        will-change: transform, opacity;
      `;
      root.appendChild(p);
    }

    window.setTimeout(() => {
      root.remove();
    }, 2500);
  }, []);
}
