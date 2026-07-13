/**
 * Helpers d'affichage honnete des positions de mots-cles.
 *
 * Le backend (rank_display.py) renvoie par mot-cle un bloc de "position stable"
 * calcule sur une fenetre glissante de snapshots :
 *   stable_position, is_stable, found_ratio, last_checked, best_seen, samples.
 *
 * gridar.app ranke de facon fragile sur des mots-cles ultra-niche : un seul
 * releve Serper peut donner #1 puis "non classe" la minute suivante. On
 * n'affiche donc une position que si elle est CONSISTANTE, et on montre
 * toujours la date de derniere verification.
 */

/** Un mot-cle qui vaut plus de STALE_DAYS jours est signale en ambre. */
export const STALE_DAYS = 3;

export type RankDisplay = {
  stable_position: number | null;
  is_stable: boolean;
  found_ratio: number;
  last_checked: string | null;
  best_seen: number | null;
  samples: number;
};

export type LastCheckedInfo = {
  /** Libelle court, ex "il y a 3 jours" ou "le 13 juil.". */
  label: string;
  /** Chaine locale complete pour un title/tooltip. */
  full: string;
  /** Age en jours (arrondi bas), ou null si jamais verifie. */
  ageDays: number | null;
  /** true si jamais verifie ou plus vieux que STALE_DAYS. */
  isStale: boolean;
};

/**
 * Decrit la fraicheur d'un last_checked ISO pour l'UI.
 * Retourne un libelle quebecois + un drapeau "vieux" (ambre).
 */
export function describeLastChecked(iso: string | null): LastCheckedInfo {
  if (!iso) {
    return { label: "jamais", full: "", ageDays: null, isStale: true };
  }
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) {
    return { label: "jamais", full: "", ageDays: null, isStale: true };
  }
  const ageDays = Math.max(0, Math.floor((Date.now() - then) / 86_400_000));
  const isStale = ageDays > STALE_DAYS;

  let label: string;
  if (ageDays <= 0) label = "aujourd'hui";
  else if (ageDays === 1) label = "hier";
  else if (ageDays < 7) label = `il y a ${ageDays} jours`;
  else
    label =
      "le " +
      new Date(iso).toLocaleDateString("fr-CA", {
        day: "numeric",
        month: "short",
      });

  const full = new Date(iso).toLocaleString("fr-CA");
  return { label, full, ageDays, isStale };
}

export type RankState =
  | { kind: "none" } // aucun releve
  | { kind: "stable"; position: number } // classe de facon consistante
  | { kind: "unranked" } // vu mais jamais dans le top 100
  | { kind: "unstable"; bestSeen: number | null }; // vacille

/**
 * Traduit le bloc de position stable en un etat d'affichage sans equivoque.
 * On ne montre un "#X" que si is_stable. Sinon on avoue l'instabilite.
 */
export function rankState(d: RankDisplay): RankState {
  if (d.samples === 0) return { kind: "none" };
  if (d.is_stable && d.stable_position != null) {
    return { kind: "stable", position: d.stable_position };
  }
  if (d.best_seen == null) return { kind: "unranked" };
  return { kind: "unstable", bestSeen: d.best_seen };
}

/** Classe tailwind de couleur selon la profondeur de la position. */
export function positionColor(position: number): string {
  if (position <= 3) return "text-green-600";
  if (position <= 10) return "text-emerald-600";
  if (position <= 30) return "text-amber-600";
  return "text-muted-foreground";
}
