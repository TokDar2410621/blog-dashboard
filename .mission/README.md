# `.mission/` — Mémoire long-terme partagée

Ce dossier contient l'état persistant d'une **mission** au sens du skill Claude Code `/mission` (voir `~/.claude/skills/mission/SKILL.md` chez Darius).

Il est **commité dans le repo** pour que :
1. Les sessions Claude Code locales puissent y reprendre.
2. Les agents `/schedule` distants (cloud Anthropic) qui clonent le repo aient accès aux mêmes fichiers.

## Fichiers

| Fichier | Type | Rôle |
|---|---|---|
| `MISSION.md` | direction | énoncé de la mission, why, critères de succès, checklist |
| `PROGRESS_LOG.md` | journal | une entrée par session, avec "Prochain bloc concret" en bas |
| `ROADMAP.md` | plan | features à venir, ordonnées par tier d'impact |
| `WORKFLOW.md` | règles | local-first, checkpoint avant compact, etc. |
| `ARCHITECTURE.md` | snapshot | inventaire de l'état actuel pour les nouveaux Claude |
| `PENDING_HUMAN.md` | suivi | actions qui requièrent Darius (push, choix produit, clé API…) |

## Convention

- **Avant chaque compact / fin de session** : mettre à jour `PROGRESS_LOG.md` avec une nouvelle "Session YYYY-MM-DD" et la ligne "Prochain bloc concret".
- **Vérifier avant d'agir sur un fait mémoire** : la mémoire peut être stale (un fichier renommé, une fonction supprimée). Lire/grep le code actuel avant de baser une décision dessus.
- **Pas de duplication** : si on découvre qu'une info est fausse, corriger l'entrée existante plutôt qu'en ajouter une qui contredit.

## Pour un humain qui tombe ici

Ce n'est pas de la doc projet. C'est l'état mental d'un agent IA qui poursuit une mission long-terme. Tu peux :
- Lire `MISSION.md` pour comprendre l'objectif.
- Lire `PROGRESS_LOG.md` pour voir où ça en est.
- Lire `PENDING_HUMAN.md` si tu es Darius et que tu veux savoir ce qui attend ton action.

La doc produit reste dans `README.md` (à la racine) ou ailleurs, pas ici.
