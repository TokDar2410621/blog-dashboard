# Workflow autonome

Règles de fonctionnement pour tout Claude (local OU cloud /schedule) qui poursuit cette mission.

## 1. Démarrage de session

1. Lire `MISSION.md` — pour savoir où on va.
2. Lire la **dernière entrée** de `PROGRESS_LOG.md` — pour savoir où on en est.
3. Lire `ROADMAP.md` — pour savoir ce qui vient après.
4. Lire `PENDING_HUMAN.md` (si existe) — pour ne PAS retravailler sur quelque chose qui attend Darius.

## 2. Pendant la session

- Une seule tâche `in_progress` à la fois (TodoWrite).
- Chaque tâche complétée → marquer `completed` immédiatement, pas en batch.
- Vérifier le code avant de croire la mémoire (un fichier renommé, une fonction supprimée → corriger l'entrée mémoire plutôt que tomber dans le piège).
- **Local-first** :
  - Sessions locales (Darius dans son IDE) : pas de `git push` sauf demande explicite.
  - Sessions cloud `/schedule` : créer une **branche** `mission/<date>-<slug>`, commit, push **la branche**, ouvrir une **PR** vers `main`. **Ne JAMAIS push directement sur `main`.**

## 3. Tests minimaux avant de marquer "done"

- Backend Django modifié → `python backend/manage.py check`
- Frontend modifié → `npm run build` (vite build)
- Si tests existent → les exécuter (`pytest`, `npm test`)
- Au moins un curl ou une trace manuelle pour les nouveaux endpoints

## 4. Avant compact / fin de session (CRITIQUE)

Toujours, **avant que le contexte se compacte ou que la session se termine** :

1. Append une nouvelle entrée à `PROGRESS_LOG.md` :
   ```
   ## Session YYYY-MM-DD — <résumé court>

   **Fait** : <bullets>
   **Tests** : <statut>
   **Branches/commits** : <hash, branche, PR si applicable>
   **Prochain bloc concret** : <fichier à éditer / fonction à écrire / item de roadmap, le plus précis possible>
   **Blocages** : <aucun OU description>
   ```
2. Mettre à jour les checklists `[x]` dans `MISSION.md` et `ROADMAP.md`.
3. Si bloqué par une action humaine, **créer/append** dans `PENDING_HUMAN.md`.

**Si tu sens que la session va se compacter** : checkpoint maintenant, n'attends pas.

## 5. Quoi déléguer à Darius (action humaine)

- Push final sur `main` après merge / déploiement.
- Validation d'une PR ouverte par un agent cloud.
- Configuration d'API tierce (clés Stripe, Google, Bing Webmaster…).
- Choix produit majeur (UX décisive, pricing, naming, positionnement).
- Action légale / financière.
- Test manuel UI sur les vrais sites de prod (Arivex, LocaSur, TokamDarius) si pertinent.

Pour tout le reste : **agir, ne pas demander.**

## 6. Anti-patterns à éviter

- Ne pas refactorer pour le plaisir.
- Ne pas abstraire prématurément.
- Ne pas ajouter de comments verbeux ou de docstrings rituelles.
- Ne pas terminer en "vague" — toujours laisser un "Prochain bloc concret" précis.
- Ne pas accumuler des fichiers mémoire stale.
- Ne pas supprimer/renommer un endpoint existant sans vérifier qu'aucun frontend ne l'utilise.

## 7. RÈGLE D'OR — Pas de backend sans frontend

> **"Le meilleur backend ne vaut rien sans front."** — Darius, 2026-05-04

Aucune feature n'est terminée tant que Darius ne peut pas l'utiliser via l'UI du dashboard. Un endpoint testable seulement par curl est un demi-livrable.

**Comment l'appliquer** :

1. **Ne jamais committer un endpoint backend sans le composant React qui le consomme dans le même cycle de travail** (idéalement même commit, ou commits consécutifs qui se suivent immédiatement). Pas de "je fais le backend aujourd'hui, le frontend demain peut-être".

2. **Si la feature est complexe**, découper en tranches **end-to-end verticales** plutôt qu'en couches horizontales. Tranche 1 = endpoint minimal + UI minimale qui marche bout en bout. Tranche 2 = enrichir les deux.

3. **Si vraiment court en temps**, préférer une **UI minimale et moche** (textarea, table brute, JSON pretty-printed) qui fonctionne, à un backend sophistiqué sans UI. Le polish vient ensuite.

4. **Le `Prochain bloc concret` doit toujours, à terme, déboucher sur un écran utilisateur**. Si une session ne livre que du backend, la session suivante DOIT compléter le frontend correspondant — sans laisser le backend orphelin sur la prochaine roadmap.

5. **Critère "done" mis à jour** : une feature est "done" quand :
   - Endpoint backend OK (`python manage.py check`)
   - **ET** route frontend accessible
   - **ET** composant React qui rend le résultat sans erreur TS
   - **ET** lien sidebar / point d'entrée UI clair pour que Darius trouve la feature
   - **ET** build passe (`npm run build`)
   - **ET** trace dans `PROGRESS_LOG.md` mentionnant l'écran exact où tester

6. **Exception** : seules les **fonctions internes / helpers utilitaires** peuvent rester backend-only. Tout ce qui produit une donnée ou un effet visible pour l'utilisateur final passe par une UI.

## 7. Cloud `/schedule` agent — spécificités

L'agent cloud :
- Clone le repo dans un environnement Anthropic.
- N'a **pas** accès à `c:/Users/Darius/...`, ni aux clés API locales, ni aux secrets `.env`.
- Pour tester un endpoint qui nécessite une clé API tierce : **note le test à faire dans `PROGRESS_LOG.md` "Tests humains à faire"** plutôt que de bidouiller.
- Doit ouvrir une PR vers `main`, pas push directement.
- Si le routine est censé tourner ~10 min/jour : un seul gros bloc concret par run, pas de prétention à finir 5 features.
