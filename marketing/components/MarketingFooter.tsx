"use client";

import Link from "next/link";
import { GridarMark } from "@/components/GridarMark";
import { NAV_TOOLS } from "@/lib/tools-nav";
import { useAuth } from "@/context/AuthContext";

/**
 * Shared marketing footer, mirrors the landing footer:
 * - border-white/5 top border, zinc-500 text on zinc-950.
 * - Brand block + nav links + legal row at the bottom.
 */
export function MarketingFooter() {
  const { isAuthenticated } = useAuth();
  const authedHref = isAuthenticated ? "/sites" : "/login";
  const headerCtaLabel = isAuthenticated ? "Tableau de bord" : "Connexion";

  return (
    <footer className="relative z-10 border-t border-white/5 bg-zinc-950">
      <div className="max-w-6xl mx-auto px-6 py-12 text-sm text-zinc-500">
        <div className="flex flex-col md:flex-row justify-between gap-8">
          <div className="max-w-md">
            <div className="flex items-center gap-2 mb-3 text-zinc-100">
              <GridarMark className="h-[30px] w-[30px] text-emerald-400" />
              <span className="font-semibold text-[1.4rem]">Gridar</span>
            </div>
            <p>
              Le SaaS SEO bilingue FR-CA, conçu et opéré au Québec. Pour les PME
              québécoises qui veulent ranker. Aucun investisseur, aucun pivot prévu.
            </p>
          </div>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-8">
            <div className="flex flex-col gap-2">
              <span className="text-zinc-300 text-xs font-medium uppercase tracking-wider mb-1">
                Outils gratuits
              </span>
              {NAV_TOOLS.map((tool) => (
                <Link
                  key={tool.href}
                  href={tool.href}
                  className="hover:text-zinc-100"
                >
                  {tool.label}
                </Link>
              ))}
            </div>
            <div className="flex flex-col gap-2">
              <span className="text-zinc-300 text-xs font-medium uppercase tracking-wider mb-1">
                Ressources
              </span>
              <Link href="/tools" className="hover:text-zinc-100">Tous les outils</Link>
              <Link href="/docs" className="hover:text-zinc-100">Documentation</Link>
              <Link href="/blog" className="hover:text-zinc-100">Blog</Link>
              <Link href="/api-docs" className="hover:text-zinc-100">API REST</Link>
              <Link href="/docs/integrations" className="hover:text-zinc-100">Intégrations</Link>
              <Link href="/mcp" className="hover:text-zinc-100">Connecteur IA</Link>
            </div>
            <div className="flex flex-col gap-2">
              <span className="text-zinc-300 text-xs font-medium uppercase tracking-wider mb-1">
                Gridar
              </span>
              <Link href="/#pricing" className="hover:text-zinc-100">Tarifs</Link>
              <Link href={authedHref} className="hover:text-zinc-100">{headerCtaLabel}</Link>
              <a href="mailto:tokamdarius@gmail.com" className="hover:text-zinc-100">Contact</a>
              <a
                href="https://github.com/TokDar2410621/blog-dashboard"
                target="_blank"
                rel="noopener noreferrer"
                className="hover:text-zinc-100"
              >
                GitHub
              </a>
            </div>
          </div>
        </div>
        <div className="mt-12 pt-6 border-t border-white/5 text-xs flex flex-col md:flex-row gap-3 md:gap-0 justify-between items-start md:items-center">
          <span>© {new Date().getFullYear()} Gridar - Arivex Studio</span>
          <div className="flex flex-wrap gap-4">
            <Link href="/privacy" className="hover:text-zinc-100">Confidentialité</Link>
            <Link href="/terms" className="hover:text-zinc-100">Conditions</Link>
            <span>Fait à Saint-Hyacinthe, QC.</span>
          </div>
        </div>
      </div>
    </footer>
  );
}
