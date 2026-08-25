import Link from "next/link";
import type { LucideIcon } from "lucide-react";
import { ArrowRight, Check, Plug } from "lucide-react";
import { Button } from "@/components/ui/button";
import { MarketingHeader } from "@/components/MarketingHeader";
import { CinematicFooter } from "@/components/ui/motion-footer";

export const MCP_URL = "https://mcp.gridar.app/mcp";

export type ConnectorStep = {
  title: string;
  body?: string;
  /** Bloc de config a copier-coller (rendu en monospace). */
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
  features: ConnectorFeature[];
  /** Liens vers les autres pages connecteur. */
  related?: { href: string; label: string }[];
  /** Note optionnelle sous les etapes (prerequis, compte, etc.). */
  note?: string;
};

/**
 * Page vitrine reutilisable pour le connecteur MCP de Gridar. Rendu cote
 * serveur (contenu indexable) : hero serif + URL du serveur, etapes d'install,
 * grille d'outils, liens croises. Header/footer unifies.
 */
export function ConnectorPage({
  eyebrow,
  title,
  subtitle,
  steps,
  features,
  related,
  note,
}: ConnectorPageProps) {
  return (
    <>
      <MarketingHeader trail="Connecteur IA" />

      <main className="mx-auto max-w-4xl px-4 pb-20 pt-16 md:pt-24">
        {/* Hero */}
        <section className="text-center">
          <div className="mb-5 inline-flex items-center gap-2 text-xs font-medium uppercase tracking-[0.28em] text-emerald-400/80">
            <Plug className="h-3.5 w-3.5" />
            {eyebrow}
          </div>
          <h1
            style={{ fontFamily: "var(--font-fraunces), Georgia, serif" }}
            className="mx-auto max-w-3xl text-balance text-4xl font-medium leading-[1.05] tracking-tight text-white md:text-6xl"
          >
            {title}
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-base leading-relaxed text-zinc-400 md:text-lg">
            {subtitle}
          </p>

          {/* URL du serveur MCP */}
          <div className="mx-auto mt-10 max-w-xl">
            <div className="mb-2 text-xs uppercase tracking-wider text-zinc-500">
              URL du serveur MCP
            </div>
            <div className="flex items-center justify-center gap-3 rounded-xl border border-white/10 bg-white/[0.03] px-5 py-4">
              <code className="select-all font-mono text-sm text-emerald-300 md:text-base">
                {MCP_URL}
              </code>
            </div>
            <p className="mt-3 text-xs text-zinc-500">
              Connexion par OAuth (tu te connectes à ton compte Gridar), ou par
              jeton <code className="font-mono text-zinc-400">btb_…</code> depuis
              ton tableau de bord.
            </p>
          </div>

          <div className="mt-8 flex flex-col justify-center gap-3 sm:flex-row">
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
        </section>

        {/* Etapes d'installation */}
        <section className="mt-20">
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
          {note && (
            <p className="mt-4 text-center text-sm text-zinc-500">{note}</p>
          )}
        </section>

        {/* Ce que tu peux faire */}
        <section className="mt-20">
          <h2 className="mb-8 text-center text-2xl font-semibold tracking-tight text-white md:text-3xl">
            Ce que ton IA peut faire avec Gridar
          </h2>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {features.map((f) => {
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
                  <p className="mt-1 text-sm leading-relaxed text-zinc-500">
                    {f.desc}
                  </p>
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
      </main>

      <CinematicFooter />
    </>
  );
}
