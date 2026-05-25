"use client";

import { useEffect, useState } from "react";

export function ReadingProgress({ targetSelector }: { targetSelector: string }) {
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    function onScroll() {
      const el = document.querySelector<HTMLElement>(targetSelector);
      if (!el) return;
      const rect = el.getBoundingClientRect();
      const total = el.offsetHeight - window.innerHeight;
      const scrolled = -rect.top;
      const pct = total <= 0 ? 100 : Math.max(0, Math.min(100, (scrolled / total) * 100));
      setProgress(pct);
    }
    window.addEventListener("scroll", onScroll, { passive: true });
    onScroll();
    return () => window.removeEventListener("scroll", onScroll);
  }, [targetSelector]);

  return (
    <div
      className="fixed top-0 left-0 right-0 h-0.5 bg-emerald-400 z-50 transition-[width] duration-100"
      style={{ width: `${progress}%` }}
      aria-hidden
    />
  );
}
