"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";
import { GridarMark } from "@/components/GridarMark";
import { useAuth } from "@/context/AuthContext";

type Props = {
  /** Optional breadcrumb-style trailing label (e.g. "Docs", "Confidentialité"). */
  trail?: string;
};

/**
 * Shared marketing header. Mirrors the landing nav style:
 * - zinc-950 background, white/5 border, backdrop-blur, sticky top.
 * - Gridar mark + wordmark, auth-aware CTA on the right.
 * - Optional `trail` slot renders as "/ {label}" next to the wordmark.
 */
export function MarketingHeader({ trail }: Props) {
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const authedHref = isAuthenticated ? "/sites" : "/login";
  const primaryCtaLabel = isAuthenticated ? "Tableau de bord" : "Commencer";
  const headerCtaLabel = isAuthenticated ? "Tableau de bord" : "Connexion";
  const hideLoginAffordance = authLoading;

  return (
    <header className="relative z-20 border-b border-white/5 backdrop-blur-xl bg-zinc-950/70 sticky top-0">
      <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
        <Link href="/" className="flex items-center gap-2 group">
          <GridarMark className="h-[30px] w-[30px] text-emerald-400" />
          <span className="font-semibold tracking-tight text-[1.4rem] text-zinc-100 group-hover:text-white">
            Gridar
          </span>
          {trail && (
            <span className="hidden sm:inline text-zinc-500 ml-1 text-sm">
              / {trail}
            </span>
          )}
        </Link>
        <nav className="flex items-center gap-6">
          <Link
            href="/#features"
            className="hidden md:inline text-sm text-zinc-400 hover:text-white"
          >
            Fonctionnalités
          </Link>
          <Link
            href="/#pricing"
            className="hidden md:inline text-sm text-zinc-400 hover:text-white"
          >
            Tarifs
          </Link>
          <Link
            href="/blog"
            className="hidden md:inline text-sm text-zinc-400 hover:text-white"
          >
            Blog
          </Link>
          <Link
            href="/docs"
            className="hidden md:inline text-sm text-zinc-400 hover:text-white"
          >
            Docs
          </Link>
          {!hideLoginAffordance && (
            <Link
              href={authedHref}
              className="text-sm text-zinc-400 hover:text-white"
            >
              {headerCtaLabel}
            </Link>
          )}
          <Link href={authedHref}>
            <Button size="sm" className="bg-white text-zinc-950 hover:bg-zinc-200">
              {primaryCtaLabel}
            </Button>
          </Link>
        </nav>
      </div>
    </header>
  );
}
