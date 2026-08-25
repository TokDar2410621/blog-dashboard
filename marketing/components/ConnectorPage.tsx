"use client";

import { Fragment } from "react";
import Link from "next/link";
import type { LucideIcon } from "lucide-react";
import { ArrowRight, Check, Plug } from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import { Button } from "@/components/ui/button";
import { MarketingHeader } from "@/components/MarketingHeader";
import { CinematicFooter } from "@/components/ui/motion-footer";
import { CLIENT_LOGOS } from "@/components/connector-logos";
import { CONNECTOR_FEATURES } from "@/components/connector-features";

export const MCP_URL = "https://mcp.gridar.app/mcp";

export type ConnectorStep = {
  title: string;
  body?: string;
  code?: string;
};

export type ConnectorFeature = {
  icon: LucideIcon;
  title: string;
  desc: string;
};

type ConnectorPageProps = {
  eyebrow: string;
  title: string;
  subtitle: string;
  steps: ConnectorStep[];
  related?: { href: string; label: string }[];
  note?: string;
};

/**
 * Animation d'entree en CSS pur : le contenu est VISIBLE dans le HTML initial
 * (donc lu par les crawlers qui n'executent pas le JS), l'animation ne fait que
 * le rejouer. Contrairement a motion, aucun opacity:0 n'est serialise en SSR.
 */
const ENTRY_CSS = `
@keyframes connWordIn {
  from { opacity: 0; transform: translateY(20px); filter: blur(10px); }
  to { opacity: 1; transform: none; filter: blur(0); }
}
@media (prefers-reduced-motion: no-preference) {
  .conn-word { display: inline-block; animation: connWordIn 0.6s cubic-bezier(0.16,1,0.3,1) backwards; }
  .conn-in { animation: connWordIn 0.7s cubic-bezier(0.16,1,0.3,1) backwards; }
}
`;

/**
 * Page vitrine reutilisable pour le connecteur MCP de Gridar. Client pour le
 * motion (titre qui s'assemble, aurore animee, revelations au scroll), mais le
 * contenu est rendu cote serveur (SSR) donc indexable. Header/footer unifies.
 */
export function ConnectorPage({
  eyebrow,
  title,
  subtitle,
  steps,
  related,
  note,
}: ConnectorPageProps) {
  const reduce = useReducedMotion();
  const features = CONNECTOR_FEATURES;

  return (
    <>
      <style dangerouslySetInnerHTML={{ __html: ENTRY_CSS }} />
      <MarketingHeader trail="Connecteur IA" />

      <main className="pb-20">
        {/* Hero avec fond anime */}
        <section className="relative flex min-h-[72vh] w-full flex-col items-center justify-center overflow-hidden px-4 py-20 text-center">
          {/* Aurore vivante */}
          <div aria-hidden className="pointer-events-none absolute inset-0 -z-10">
            <motion.div
              className="absolute left-1/2 top-[-10%] h-[520px] w-[520px] -translate-x-1/2 rounded-full bg-emerald-500/20 blur-[130px]"
              animate={reduce ? undefined : { x: [0, 50, -30, 0], y: [0, 30, -20, 0], scale: [1, 1.12, 0.96, 1] }}
              transition={{ duration: 22, repeat: Infinity, ease: "easeInOut" }}
            />
            <motion.div
              className="absolute left-[22%] top-[12%] h-[340px] w-[340px] rounded-full bg-cyan-500/12 blur-[120px]"
              animate={reduce ? undefined : { x: [0, -40, 30, 0], y: [0, 40, 10, 0], opacity: [0.5, 0.8, 0.55, 0.5] }}
              transition={{ duration: 27, repeat: Infinity, ease: "easeInOut" }}
            />
          </div>
          {/* Grille de profondeur */}
          <div
            aria-hidden
            className="pointer-events-none absolute inset-0 -z-10 opacity-[0.14] [mask-image:radial-gradient(ellipse_at_center,black,transparent_72%)]"
            style={{
              backgroundImage:
                "linear-gradient(to right, rgba(255,255,255,0.06) 1px, transparent 1px), linear-gradient(to bottom, rgba(255,255,255,0.06) 1px, transparent 1px)",
              backgroundSize: "46px 46px",
            }}
          />

          <div
            className="conn-in mb-5 inline-flex items-center gap-2 text-xs font-medium uppercase tracking-[0.28em] text-emerald-400/80"
          >
            <Plug className="h-3.5 w-3.5" />
            {eyebrow}
          </div>

          <h1
            style={{ fontFamily: "var(--font-fraunces), Georgia, serif" }}
            className="mx-auto max-w-3xl text-balance text-4xl font-medium leading-[1.05] tracking-tight text-white md:text-6xl"
          >
            {title.split(" ").map((word, i, arr) => (
              <Fragment key={i}>
                <span
                  className="conn-word"
                  style={{ animationDelay: `${0.1 + i * 0.08}s` }}
                >
                  {word}
                </span>
                {i < arr.length - 1 ? " " : ""}
              </Fragment>
            ))}
          </h1>

          <p
            className="conn-in mx-auto mt-6 max-w-2xl text-base leading-relaxed text-zinc-300 md:text-lg"
            style={{ animationDelay: "0.9s" }}
          >
            {subtitle}
          </p>

          <div
            className="conn-in mx-auto mt-9 w-full max-w-xl"
            style={{ animationDelay: "1.05s" }}
          >
            <div className="mb-2 text-xs uppercase tracking-wider text-zinc-500">
              URL du serveur MCP
            </div>
            <div className="flex items-center justify-center rounded-xl border border-white/10 bg-white/[0.03] px-5 py-4 backdrop-blur-sm">
              <code className="select-all font-mono text-sm text-emerald-300 md:text-base">
                {MCP_URL}
              </code>
            </div>
            <p className="mt-3 text-xs text-zinc-500">
              Connexion OAuth (tu te connectes a ton compte Gridar) ou jeton{" "}
              <code className="font-mono text-zinc-400">btb_…</code> du tableau de bord.
            </p>
          </div>

          <div
            className="conn-in mt-8 flex flex-col justify-center gap-3 sm:flex-row"
            style={{ animationDelay: "1.2s" }}
          >
            <Link href="/login">
              <Button className="h-11 bg-white px-6 font-semibold text-zinc-950 hover:bg-zinc-200">
                Créer un compte gratuit
                <ArrowRight className="ml-2 h-4 w-4" />
              </Button>
            </Link>
            <Link href="/tools">
              <Button
                variant="outline"
                className="h-11 border-white/15 bg-transparent px-6 text-zinc-100 hover:bg-white/5"
              >
                Voir les outils
              </Button>
            </Link>
          </div>

          {/* Compatible avec (logos) */}
          <div className="conn-in mt-14" style={{ animationDelay: "1.4s" }}>
            <div className="mb-4 text-[0.7rem] uppercase tracking-[0.25em] text-zinc-600">
              Compatible avec
            </div>
            <div className="flex flex-wrap items-center justify-center gap-x-8 gap-y-4">
              {CLIENT_LOGOS.map((c) => (
                <div
                  key={c.name}
                  className="flex items-center gap-2 text-zinc-400 transition-colors hover:text-zinc-200"
                >
                  <c.Logo className="h-5 w-5" />
                  <span className="text-sm font-medium">{c.name}</span>
                </div>
              ))}
            </div>
          </div>
        </section>

        <div className="mx-auto max-w-4xl px-4">
          {/* Etapes */}
          <section className="mt-8">
            <h2 className="mb-8 text-center text-2xl font-semibold tracking-tight text-white md:text-3xl">
              Comment le brancher
            </h2>
            <ol className="space-y-4">
              {steps.map((step, i) => (
                <li
                  key={i}
                  className="rounded-2xl border border-white/[0.08] bg-white/[0.02] p-5 md:p-6"
                >
                  <div className="flex items-start gap-4">
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-emerald-500/30 bg-emerald-500/10 text-sm font-semibold text-emerald-300">
                      {i + 1}
                    </span>
                    <div className="min-w-0 flex-1">
                      <h3 className="font-semibold text-zinc-100">{step.title}</h3>
                      {step.body && (
                        <p className="mt-1 text-sm leading-relaxed text-zinc-400">
                          {step.body}
                        </p>
                      )}
                      {step.code && (
                        <pre className="mt-3 overflow-x-auto rounded-lg border border-white/10 bg-black/40 p-4 text-xs leading-relaxed text-zinc-300">
                          <code className="font-mono">{step.code}</code>
                        </pre>
                      )}
                    </div>
                  </div>
                </li>
              ))}
            </ol>
            {note && <p className="mt-4 text-center text-sm text-zinc-500">{note}</p>}
          </section>

          {/* Outils */}
          <section className="mt-20">
            <h2 className="mb-8 text-center text-2xl font-semibold tracking-tight text-white md:text-3xl">
              Ce que ton IA peut faire avec Gridar
            </h2>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              {features.map((f, i) => {
                const Icon = f.icon;
                return (
                  <div
                    key={f.title}
                    className="rounded-2xl border border-white/[0.08] bg-white/[0.02] p-5"
                  >
                    <div className="mb-3 flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-500/10 text-emerald-400">
                      <Icon className="h-5 w-5" />
                    </div>
                    <h3 className="font-semibold text-zinc-100">{f.title}</h3>
                    <p className="mt-1 text-sm leading-relaxed text-zinc-500">{f.desc}</p>
                  </div>
                );
              })}
            </div>
          </section>

          {/* Liens croises */}
          {related && related.length > 0 && (
            <section className="mt-16 text-center">
              <div className="mb-4 text-xs uppercase tracking-wider text-zinc-500">
                Aussi disponible pour
              </div>
              <div className="flex flex-wrap justify-center gap-3">
                {related.map((r) => (
                  <Link
                    key={r.href}
                    href={r.href}
                    className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.03] px-5 py-2.5 text-sm text-zinc-200 hover:border-emerald-500/30 hover:text-white"
                  >
                    <Check className="h-3.5 w-3.5 text-emerald-400" />
                    {r.label}
                  </Link>
                ))}
              </div>
            </section>
          )}
        </div>
      </main>

      <CinematicFooter />
    </>
  );
}
