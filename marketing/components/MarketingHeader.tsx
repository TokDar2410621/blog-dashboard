"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ChevronDown, Menu } from "lucide-react";
import { Button } from "@/components/ui/button";
import { GridarMark } from "@/components/GridarMark";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Sheet,
  SheetClose,
  SheetContent,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import { NAV_TOOLS } from "@/lib/tools-nav";
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

  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header
      className={`relative z-20 sticky top-0 border-b border-transparent backdrop-blur-xl bg-zinc-950/70 transition-colors ${
        scrolled ? "md:border-white/5" : ""
      }`}
    >
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
          <DropdownMenu>
            <DropdownMenuTrigger className="hidden md:inline-flex items-center gap-1 text-sm text-zinc-400 hover:text-white outline-none">
              Outils
              <ChevronDown className="h-3.5 w-3.5" />
            </DropdownMenuTrigger>
            <DropdownMenuContent
              align="start"
              className="w-64 bg-zinc-900 border-white/10 text-zinc-200"
            >
              {NAV_TOOLS.map((tool) => (
                <DropdownMenuItem
                  key={tool.href}
                  asChild
                  className="cursor-pointer focus:bg-white/5 focus:text-white"
                >
                  <Link href={tool.href} className="text-sm text-zinc-300">
                    {tool.label}
                  </Link>
                </DropdownMenuItem>
              ))}
              <DropdownMenuSeparator className="bg-white/10" />
              <DropdownMenuItem
                asChild
                className="cursor-pointer focus:bg-white/5 focus:text-white"
              >
                <Link href="/tools" className="text-sm text-emerald-400">
                  Voir tous les outils →
                </Link>
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
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
              className="hidden md:inline text-sm text-zinc-400 hover:text-white"
            >
              {headerCtaLabel}
            </Link>
          )}
          <Link href={authedHref}>
            <Button size="sm" className="bg-white text-zinc-950 hover:bg-zinc-200">
              {primaryCtaLabel}
            </Button>
          </Link>

          {/* Menu mobile */}
          <Sheet>
            <SheetTrigger asChild>
              <button
                type="button"
                aria-label="Ouvrir le menu"
                className="md:hidden inline-flex items-center justify-center rounded-md p-1.5 text-zinc-300 hover:text-white"
              >
                <Menu className="h-6 w-6" />
              </button>
            </SheetTrigger>
            <SheetContent
              side="right"
              className="w-72 border-white/10 bg-zinc-950 text-zinc-200"
            >
              <SheetTitle className="px-4 pt-4 text-zinc-100">Menu</SheetTitle>
              <nav className="flex flex-col gap-0.5 overflow-y-auto px-2 pb-6 text-sm">
                <SheetClose asChild>
                  <Link href="/#features" className="rounded-md px-2 py-2 text-zinc-300 hover:bg-white/5 hover:text-white">
                    Fonctionnalités
                  </Link>
                </SheetClose>
                <SheetClose asChild>
                  <Link href="/#pricing" className="rounded-md px-2 py-2 text-zinc-300 hover:bg-white/5 hover:text-white">
                    Tarifs
                  </Link>
                </SheetClose>

                <div className="mt-3 mb-1 px-2 text-xs font-medium uppercase tracking-wider text-zinc-500">
                  Outils
                </div>
                {NAV_TOOLS.map((tool) => (
                  <SheetClose asChild key={tool.href}>
                    <Link href={tool.href} className="rounded-md px-2 py-2 text-zinc-300 hover:bg-white/5 hover:text-white">
                      {tool.label}
                    </Link>
                  </SheetClose>
                ))}
                <SheetClose asChild>
                  <Link href="/tools" className="rounded-md px-2 py-2 text-emerald-400 hover:bg-white/5">
                    Voir tous les outils →
                  </Link>
                </SheetClose>

                <div className="my-2 h-px bg-white/10" />
                <SheetClose asChild>
                  <Link href="/blog" className="rounded-md px-2 py-2 text-zinc-300 hover:bg-white/5 hover:text-white">
                    Blog
                  </Link>
                </SheetClose>
                <SheetClose asChild>
                  <Link href="/docs" className="rounded-md px-2 py-2 text-zinc-300 hover:bg-white/5 hover:text-white">
                    Docs
                  </Link>
                </SheetClose>
                <SheetClose asChild>
                  <Link href={authedHref} className="rounded-md px-2 py-2 text-zinc-300 hover:bg-white/5 hover:text-white">
                    {headerCtaLabel}
                  </Link>
                </SheetClose>
              </nav>
            </SheetContent>
          </Sheet>
        </nav>
      </div>
    </header>
  );
}
