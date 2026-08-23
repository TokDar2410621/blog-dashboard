"use client";

import { useRef, useState } from "react";
import {
  FileText,
  ShieldCheck,
  TrendingUp,
  Sparkles,
  ArrowUp,
  ArrowDown,
  Minus,
  Check,
  AlertTriangle,
  Clock,
  Globe,
} from "lucide-react";
import { cn } from "@/lib/utils";

/**
 * DashboardDemo - le produit, jouable, dans la landing.
 *
 * Trois vues reellement cliquables (Articles, Audit, Positions) sur des donnees
 * de demonstration en dur : aucun appel reseau, aucune auth, rien a charger. Le
 * visiteur manipule l'interface avant de creer un compte.
 *
 * Concu pour vivre DANS un ecran contraint (ContainerScroll), donc tout tient
 * en hauteur fixe et scrolle a l'interieur du panneau, pas dans la page.
 *
 * Semantique d'onglets complete : role tablist/tab/tabpanel, tabindex roulant,
 * fleches et Home/End au clavier. Les transitions passent par motion-safe, donc
 * prefers-reduced-motion les coupe sans JavaScript.
 */

const SITE = "boutique-demo.ca";

type ViewId = "articles" | "audit" | "positions";

const VIEWS: { id: ViewId; label: string; icon: typeof FileText }[] = [
  { id: "articles", label: "Articles", icon: FileText },
  { id: "audit", label: "Audit", icon: ShieldCheck },
  { id: "positions", label: "Positions", icon: TrendingUp },
];

const ARTICLES = [
  { titre: "Comment choisir un plancher de bois franc au Québec", statut: "publie", score: 92, date: "12 août" },
  { titre: "Vernis à l'eau ou à l'huile : le vrai comparatif", statut: "publie", score: 87, date: "9 août" },
  { titre: "Plancher flottant ou bois franc pour un sous-sol", statut: "publie", score: 89, date: "7 août", large: true },
  { titre: "Prix d'un sablage de plancher à Montréal en 2026", statut: "brouillon", score: 74, date: "6 août" },
  { titre: "Combien coûte un plancher chauffant au Québec", statut: "brouillon", score: 68, date: "4 août" },
  { titre: "Entretenir son plancher l'hiver sans l'abîmer", statut: "file", score: null, date: "à générer" },
];

const ARTICLES_KPI = [
  { valeur: "12", libelle: "publiés" },
  { valeur: "84", libelle: "score moyen" },
  { valeur: "2", libelle: "en file" },
];

const AUDIT = [
  { libelle: "Indexation", etat: "ok", detail: "38 pages sur 38 connues de Google" },
  { libelle: "Vitesse mobile", etat: "ok", detail: "LCP 1,9 s · INP 140 ms" },
  { libelle: "Balises title", etat: "attention", detail: "4 pages dépassent 60 caractères" },
  { libelle: "Maillage interne", etat: "attention", detail: "6 pages orphelines, aucun lien entrant" },
  { libelle: "Données structurées", etat: "ok", detail: "Article + LocalBusiness valides" },
  { libelle: "Sitemap", etat: "ok", detail: "38 URL déclarées, relu le 21 août", large: true },
];

const POSITIONS = [
  { mot: "sablage plancher montréal", pos: 3, delta: 4, courbe: [11, 10, 9, 9, 7, 6, 5, 4, 4, 3] },
  { mot: "poncer son plancher soi-même", pos: 5, delta: 1, courbe: [8, 8, 7, 7, 6, 6, 6, 5, 5, 5] },
  { mot: "vernis plancher bois franc", pos: 7, delta: 2, courbe: [14, 13, 12, 12, 10, 9, 9, 8, 8, 7] },
  { mot: "bois franc ou plancher d'ingénierie", pos: 9, delta: 6, courbe: [18, 17, 16, 14, 13, 12, 11, 10, 9, 9] },
  { mot: "prix plancher bois franc québec", pos: 12, delta: 0, courbe: [12, 13, 12, 11, 12, 12, 13, 12, 12, 12] },
  { mot: "réparer plancher qui craque", pos: 19, delta: -3, courbe: [15, 15, 16, 16, 17, 17, 18, 18, 19, 19], large: true },
];

export function DashboardDemo() {
  const [view, setView] = useState<ViewId>("articles");
  const tabsRef = useRef<(HTMLButtonElement | null)[]>([]);

  // Fleches, Home et End deplacent le focus ET la selection, comme un vrai
  // groupe d'onglets. Sans ca le clavier ne peut atteindre que le premier.
  const onKeyDown = (e: React.KeyboardEvent) => {
    const i = VIEWS.findIndex((v) => v.id === view);
    const next =
      e.key === "ArrowDown" || e.key === "ArrowRight" ? (i + 1) % VIEWS.length
      : e.key === "ArrowUp" || e.key === "ArrowLeft" ? (i - 1 + VIEWS.length) % VIEWS.length
      : e.key === "Home" ? 0
      : e.key === "End" ? VIEWS.length - 1
      : -1;
    if (next < 0) return;
    e.preventDefault();
    setView(VIEWS[next].id);
    tabsRef.current[next]?.focus();
  };

  return (
    <div className="flex h-full w-full flex-col bg-zinc-950 text-left text-zinc-200">
      {/* Barre du haut : quel site, et l'action qui compte */}
      <div className="flex shrink-0 items-center justify-between gap-3 border-b border-white/5 px-3 py-2.5 md:px-4">
        <div className="flex min-w-0 items-center gap-2">
          <Globe aria-hidden="true" className="h-3.5 w-3.5 shrink-0 text-emerald-400" />
          <span className="truncate text-xs font-medium text-zinc-300 md:text-sm">{SITE}</span>
          <span className="hidden shrink-0 rounded-full border border-white/10 px-1.5 py-0.5 text-xs font-mono uppercase tracking-wider text-zinc-400 sm:inline">
            Démo
          </span>
        </div>
        <span className="flex shrink-0 items-center gap-1.5 rounded-md bg-emerald-500/10 px-2.5 py-1.5 text-xs font-medium text-emerald-300">
          <Sparkles aria-hidden="true" className="h-3.5 w-3.5" />
          Générer
        </span>
      </div>

      <div className="flex min-h-0 flex-1">
        {/* Navigation : colonne d'icones sur mobile, libelles a partir de md.
            Le pied de colonne vit HORS du tablist, dont les enfants doivent
            tous etre des onglets. */}
        <div className="flex shrink-0 flex-col justify-between border-r border-white/5 p-2 md:w-44 md:p-3">
        <div
          role="tablist"
          aria-label="Sections du tableau de bord"
          onKeyDown={onKeyDown}
          className="flex flex-col gap-0.5"
        >
          {VIEWS.map((v, i) => {
            const Icon = v.icon;
            const actif = view === v.id;
            return (
              <button
                key={v.id}
                ref={(el) => { tabsRef.current[i] = el; }}
                role="tab"
                id={`demo-tab-${v.id}`}
                // Le libelle visible disparait sous md : sans aria-label, les
                // onglets n'ont plus AUCUN nom accessible sur mobile.
                aria-label={v.label}
                aria-selected={actif}
                aria-controls={`demo-panel-${v.id}`}
                tabIndex={actif ? 0 : -1}
                onClick={() => setView(v.id)}
                className={cn(
                  "flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-xs font-medium outline-hidden md:text-sm",
                  "motion-safe:transition-colors motion-safe:duration-200 motion-safe:ease-[cubic-bezier(0.16,1,0.3,1)]",
                  "focus-visible:ring-2 focus-visible:ring-emerald-400/70",
                  actif
                    ? "bg-emerald-500/10 text-emerald-300"
                    : "text-zinc-400 hover:bg-white/5 hover:text-zinc-200",
                )}
              >
                <Icon aria-hidden="true" className="h-4 w-4 shrink-0" />
                <span aria-hidden="true" className="hidden md:inline">{v.label}</span>
              </button>
            );
          })}
        </div>

          {/* Ancre le bas de la colonne et dit ce que le produit fait tout seul */}
          <div className="mt-3 hidden items-center gap-2 rounded-lg border border-white/5 px-2.5 py-2 md:flex">
            <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-400" />
            <span className="text-xs leading-tight text-zinc-400">
              Autopilote
              <span className="block text-xs text-zinc-400">2 articles / semaine</span>
            </span>
          </div>
        </div>

        {/* Panneau : scrolle a l'interieur de l'ecran, jamais dans la page.
            Seule la vue active est montee, et la cle la remonte a chaque
            bascule : c'est ce qui redeclenche l'animation d'entree. */}
        <div className="demo-panel-scroll min-w-0 flex-1 overflow-y-auto p-3 md:p-5">
          <div
            key={view}
            role="tabpanel"
            id={`demo-panel-${view}`}
            aria-labelledby={`demo-tab-${view}`}
            tabIndex={0}
            className="demo-panel-in outline-hidden focus-visible:ring-2 focus-visible:ring-emerald-400/70"
          >
            {view === "articles" && <VueArticles />}
            {view === "audit" && <VueAudit />}
            {view === "positions" && <VuePositions />}
          </div>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------

function TitrePanneau({ children, note }: { children: string; note: string }) {
  return (
    <div className="mb-3 flex items-baseline justify-between gap-3">
      <h3 className="text-sm font-semibold text-zinc-100 md:text-base">{children}</h3>
      <span className="shrink-0 text-xs font-mono uppercase tracking-wider text-zinc-400">{note}</span>
    </div>
  );
}

function VueArticles() {
  return (
    <>
      <TitrePanneau note="Derniers articles">Contenu</TitrePanneau>
      {/* Les compteurs sont un bonus : sous md, la place va aux articles. */}
      <div className="mb-2 hidden grid-cols-3 gap-1.5 md:grid">
        {ARTICLES_KPI.map((k) => (
          <div key={k.libelle} className="rounded-lg border border-white/5 bg-white/[0.02] px-3 py-2">
            <p className="text-lg font-semibold tabular-nums leading-none text-zinc-100 md:text-xl">{k.valeur}</p>
            <p className="mt-1 text-xs text-zinc-400 md:text-xs">{k.libelle}</p>
          </div>
        ))}
      </div>
      <ul className="space-y-1.5">
        {ARTICLES.map((a) => (
          <li
            key={a.titre}
            className={cn(
              "flex items-center gap-3 rounded-lg border border-white/5 bg-white/[0.02] px-3 py-2.5",
              "large" in a && a.large && "hidden md:flex",
            )}
          >
            <StatutPastille statut={a.statut} />
            <div className="min-w-0 flex-1">
              <p className="line-clamp-2 text-xs text-zinc-200 md:truncate md:text-sm">{a.titre}</p>
              <p className="mt-0.5 text-xs text-zinc-400 md:text-xs">{a.date}</p>
            </div>
            {a.score !== null ? (
              <span
                className={cn(
                  "shrink-0 rounded px-1.5 py-0.5 text-xs font-mono font-medium",
                  a.score >= 85 ? "bg-emerald-500/10 text-emerald-300" : "bg-amber-500/10 text-amber-300",
                )}
              >
                {a.score}
              </span>
            ) : (
              <Clock aria-hidden="true" className="h-3.5 w-3.5 shrink-0 text-zinc-400" />
            )}
          </li>
        ))}
      </ul>
    </>
  );
}

function StatutPastille({ statut }: { statut: string }) {
  const map: Record<string, { couleur: string; titre: string }> = {
    publie: { couleur: "bg-emerald-400", titre: "Publié" },
    brouillon: { couleur: "bg-amber-400", titre: "Brouillon" },
    file: { couleur: "bg-zinc-600", titre: "En file" },
  };
  const s = map[statut] ?? map.file;
  // La couleur seule ne dit rien a un lecteur d'ecran ni a un daltonien.
  return (
    <span className="flex shrink-0 items-center">
      <span aria-hidden="true" className={cn("h-1.5 w-1.5 rounded-full", s.couleur)} />
      <span className="sr-only">{s.titre}</span>
    </span>
  );
}

function VueAudit() {
  const alertes = AUDIT.filter((l) => l.etat !== "ok").length;
  return (
    <>
      <TitrePanneau note={`${alertes} à corriger`}>Audit technique</TitrePanneau>
      <div className="mb-3 flex items-center gap-4 rounded-lg border border-emerald-500/20 bg-emerald-500/[0.06] px-4 py-3">
        <span className="text-3xl font-bold tabular-nums text-emerald-300 md:text-4xl">82</span>
        <div className="min-w-0">
          <p className="text-xs font-medium text-zinc-200 md:text-sm">Score global</p>
          <p className="text-xs text-zinc-400 md:text-xs">+7 depuis le dernier passage</p>
        </div>
      </div>
      <ul className="space-y-1.5">
        {AUDIT.map((l) => (
          <li
            key={l.libelle}
            className={cn(
              "flex items-start gap-3 rounded-lg border border-white/5 bg-white/[0.02] px-3 py-2",
              "large" in l && l.large && "hidden md:flex",
            )}
          >
            {l.etat === "ok" ? (
              <Check aria-hidden="true" className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-400" />
            ) : (
              <AlertTriangle aria-hidden="true" className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-400" />
            )}
            <span className="sr-only">{l.etat === "ok" ? "Conforme :" : "À corriger :"}</span>
            <div className="min-w-0">
              <p className="text-xs text-zinc-200 md:text-sm">{l.libelle}</p>
              <p className="mt-0.5 text-xs text-zinc-400 md:text-xs">{l.detail}</p>
            </div>
          </li>
        ))}
      </ul>
    </>
  );
}

function VuePositions() {
  return (
    <>
      <TitrePanneau note="30 derniers jours">Positions Google</TitrePanneau>
      <ul className="space-y-1.5">
        {POSITIONS.map((p) => (
          <li
            key={p.mot}
            className={cn(
              "flex items-center gap-3 rounded-lg border border-white/5 bg-white/[0.02] px-3 py-2.5",
              "large" in p && p.large && "hidden md:flex",
            )}
          >
            <div className="min-w-0 flex-1">
              <p className="line-clamp-2 text-xs text-zinc-200 md:truncate md:text-sm">{p.mot}</p>
              <Courbe points={p.courbe} monte={p.delta >= 0} />
            </div>
            <span className="shrink-0 text-base font-semibold tabular-nums text-zinc-100 md:text-lg">
              <span className="sr-only">position </span>
              {p.pos}
            </span>
            <Delta valeur={p.delta} />
          </li>
        ))}
      </ul>
    </>
  );
}

function Delta({ valeur }: { valeur: number }) {
  if (valeur === 0) {
    return (
      <span className="flex w-10 shrink-0 items-center justify-end gap-0.5 text-xs font-mono text-zinc-400">
        <Minus aria-hidden="true" className="h-3 w-3" />
        <span className="sr-only">stable</span>
      </span>
    );
  }
  const monte = valeur > 0;
  const Fleche = monte ? ArrowUp : ArrowDown;
  return (
    <span
      className={cn(
        "flex w-10 shrink-0 items-center justify-end gap-0.5 text-xs font-mono",
        monte ? "text-emerald-400" : "text-red-400",
      )}
    >
      <Fleche aria-hidden="true" className="h-3 w-3" />
      <span className="sr-only">{monte ? "en hausse de" : "en baisse de"}</span>
      {Math.abs(valeur)}
      <span className="sr-only">places</span>
    </span>
  );
}

/** Courbe de rang : l'axe est inverse, une position basse doit monter a l'ecran. */
function Courbe({ points, monte }: { points: number[]; monte: boolean }) {
  const max = Math.max(...points);
  const min = Math.min(...points);
  const amplitude = max - min || 1;
  const d = points
    .map((v, i) => {
      const x = (i / (points.length - 1)) * 100;
      const y = ((v - min) / amplitude) * 16;
      return `${i === 0 ? "M" : "L"} ${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <svg
      viewBox="0 0 100 16"
      preserveAspectRatio="none"
      aria-hidden="true"
      className="mt-1.5 h-4 w-full max-w-[180px]"
    >
      <path
        d={d}
        fill="none"
        strokeWidth={1.5}
        vectorEffect="non-scaling-stroke"
        className={monte ? "stroke-emerald-400/70" : "stroke-red-400/70"}
      />
    </svg>
  );
}
