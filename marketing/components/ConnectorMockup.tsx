"use client";

import type { SVGProps } from "react";
import { Plug, Check, ArrowUp } from "lucide-react";

type ConnectorMockupProps = {
  /** Nom du client IA affiche dans la barre de titre (ex: "ChatGPT"). */
  client: string;
  Logo: (p: SVGProps<SVGSVGElement>) => React.JSX.Element;
  /** Question posee par l'utilisateur dans le mockup. */
  prompt: string;
  /** Outil Gridar appele (nom reel du serveur MCP). */
  tool: string;
};

const SITE = "demo-entreprise.ca";

const PRIORITIES = [
  {
    severity: "high" as const,
    title: "Aucune balise title sur 12 pages",
    detail: "Google affiche l'URL a la place. Corrige en priorite.",
  },
  {
    severity: "high" as const,
    title: "Vitesse mobile a 34/100",
    detail: "3,8 s avant le premier contenu. La moitie des visiteurs partent.",
  },
  {
    severity: "medium" as const,
    title: "Pas de schema LocalBusiness",
    detail: "Ta fiche n'est pas comprise comme un commerce local.",
  },
];

const SEV_DOT: Record<"high" | "medium", string> = {
  high: "bg-red-400",
  medium: "bg-amber-400",
};

/**
 * Mockup du connecteur en action : une fenetre de conversation ou l'IA appelle
 * reellement un outil Gridar (nom d'outil du serveur MCP), avec le resultat
 * rendu. Montre ce que la page promet au lieu de le decrire.
 *
 * Animation d'entree en CSS pur : le contenu reste visible dans le HTML initial
 * (lisible par les crawlers qui n'executent pas le JS), l'animation ne fait que
 * le rejouer, et prefers-reduced-motion la coupe.
 */
export function ConnectorMockup({
  client,
  Logo,
  prompt,
  tool,
}: ConnectorMockupProps) {
  return (
    <div className="mockup-root relative mx-auto w-full max-w-2xl">
      <style
        dangerouslySetInnerHTML={{
          __html: `
@keyframes mockIn { from { opacity: 0; transform: translateY(14px); } to { opacity: 1; transform: none; } }
@keyframes mockPulse { 0%,100% { opacity: 1; } 50% { opacity: .35; } }
@media (prefers-reduced-motion: no-preference) {
  .mock-step { animation: mockIn .6s cubic-bezier(.16,1,.3,1) backwards; }
  .mock-dot { animation: mockPulse 2s ease-in-out infinite; }
}`,
        }}
      />

      {/* Lueur sous la fenetre */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-8 -bottom-6 -z-10 h-24 rounded-full bg-emerald-500/20 blur-[60px]"
      />

      <div className="overflow-hidden rounded-2xl border border-white/10 bg-zinc-900/70 shadow-[0_30px_80px_-20px_rgba(0,0,0,0.8)] backdrop-blur-sm">
        {/* Barre de titre */}
        <div className="flex items-center justify-between gap-3 border-b border-white/[0.07] bg-white/[0.02] px-4 py-3">
          <div className="flex items-center gap-2 text-zinc-300">
            <Logo className="h-4 w-4" />
            <span className="text-sm font-medium">{client}</span>
          </div>
          <div className="flex items-center gap-1.5 rounded-full border border-emerald-500/25 bg-emerald-500/10 px-2.5 py-1">
            <span className="mock-dot h-1.5 w-1.5 rounded-full bg-emerald-400" />
            <span className="text-[11px] font-medium text-emerald-300">
              Gridar connecté
            </span>
          </div>
        </div>

        <div className="space-y-4 p-4 md:p-5">
          {/* Question de l'utilisateur */}
          <div className="mock-step flex justify-end" style={{ animationDelay: "0.05s" }}>
            <div className="max-w-[85%] rounded-2xl rounded-br-md bg-white/[0.07] px-4 py-2.5 text-sm text-zinc-100">
              {prompt}
            </div>
          </div>

          {/* Appel de l'outil Gridar */}
          <div className="mock-step" style={{ animationDelay: "0.35s" }}>
            <div className="flex flex-wrap items-center gap-2 rounded-xl border border-white/[0.07] bg-black/30 px-3 py-2.5">
              <Plug className="h-3.5 w-3.5 shrink-0 text-emerald-400" />
              <code className="font-mono text-xs text-zinc-300">
                gridar · {tool}
              </code>
              <code className="font-mono text-xs text-zinc-500">{SITE}</code>
              <span className="ml-auto flex items-center gap-1 text-[11px] text-emerald-400">
                <Check className="h-3 w-3" />
                4,2 s
              </span>
            </div>
          </div>

          {/* Reponse de l'IA */}
          <div className="mock-step space-y-3" style={{ animationDelay: "0.65s" }}>
            <div className="flex items-start gap-3">
              <div className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-white/10 bg-white/[0.04]">
                <Logo className="h-3 w-3 text-zinc-400" />
              </div>
              <div className="min-w-0 flex-1 text-sm leading-relaxed text-zinc-300">
                J&apos;ai audité <span className="font-mono text-zinc-100">{SITE}</span>.
                Score SEO global :{" "}
                <span className="font-semibold text-amber-400">61/100</span>. Voici
                les trois choses à corriger en premier :
              </div>
            </div>

            <div className="ml-9 space-y-2">
              {PRIORITIES.map((p, i) => (
                <div
                  key={p.title}
                  className="mock-step flex items-start gap-3 rounded-xl border border-white/[0.07] bg-white/[0.02] px-3.5 py-2.5"
                  style={{ animationDelay: `${0.85 + i * 0.12}s` }}
                >
                  <span
                    className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${SEV_DOT[p.severity]}`}
                  />
                  <div className="min-w-0">
                    <div className="text-sm font-medium text-zinc-100">
                      {p.title}
                    </div>
                    <div className="text-xs leading-relaxed text-zinc-500">
                      {p.detail}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Champ de saisie (decoratif) */}
          <div
            className="mock-step flex items-center gap-2 rounded-xl border border-white/[0.07] bg-black/30 px-4 py-2.5"
            style={{ animationDelay: "1.3s" }}
            aria-hidden
          >
            <span className="text-sm text-zinc-600">
              Demande autre chose à Gridar…
            </span>
            <span className="ml-auto flex h-6 w-6 items-center justify-center rounded-full bg-white/10">
              <ArrowUp className="h-3.5 w-3.5 text-zinc-400" />
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
