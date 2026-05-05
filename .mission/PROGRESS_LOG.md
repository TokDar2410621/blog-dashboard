# Journal d'avancement

Une entrée par session. Format strict :

```
## Session YYYY-MM-DD — <résumé court>

**Fait** : ...
**Tests** : ...
**Branches/commits** : ...
**Prochain bloc concret** : ...
**Blocages** : ...
```

Garder ce fichier sous **500 lignes** — quand on dépasse, archiver les sessions anciennes dans `PROGRESS_LOG_ARCHIVE.md`.

---

## Session 2026-05-04 — Bootstrap mission + .mission/ + skill /mission

**Fait** :
- Cristallisation de la mission "SEO n°1 au Québec" dans `MISSION.md`.
- Création du dossier `.mission/` et de tous ses fichiers : `README.md`, `MISSION.md`, `WORKFLOW.md`, `ROADMAP.md`, `ARCHITECTURE.md`, `PROGRESS_LOG.md`.
- Création du skill `/mission` dans `~/.claude/skills/mission/SKILL.md` (côté local Darius).
- Permission `Bash(git push:*)` ajoutée à `~/.claude/settings.json`.
- Avant cette session : commit `eb243e7` (dedup translation_group sur public posts list) poussé sur `main`.
- Avant cette session : tentative commit fix markdown image Arivex — perdu lors d'un revert côté Darius (cf `arivex-ignition` repo).

**Tests** : pas d'exécution (cette session est de la doc/mémoire).

**Branches/commits** : commit à venir sur `main` avec le dossier `.mission/` complet (mission docs, workflow, roadmap, architecture, log).

**Prochain bloc concret** :

Implémenter le **Tier 1 #1 — Content Brief Generator**. Étapes :

1. Lire `backend/sites_mgmt/views.py` — chercher `class CompetitorAnalysisView` et `class KeywordResearchView` pour réutiliser leurs patterns Serper/Gemini.
2. Ajouter `class ContentBriefView(APIView)` après `CompetitorAnalysisView`. Body :
   - Reçoit `{keyword: str, language: str ('fr'/'en'), site_id?: int}`
   - Cache key via `_seo_cache_key('content_brief', keyword, language)`
   - Étape A : appelle Serper SERP (top 10 + peopleAlsoAsk) — réutiliser le client Serper de `CompetitorAnalysisView`
   - Étape B : envoie le résultat à Gemini avec prompt qui demande JSON :
     ```
     {
       "search_intent": "...",
       "recommended_titles": ["...", "...", "..."],
       "outline": [{"level": 2, "text": "..."}, ...],
       "word_count_target": int,
       "faq": [{"q": "...", "a": "..."}],
       "entities": ["...", "..."],
       "schemas_suggested": ["Article", "FAQ", ...],
       "eeat_signals": ["...", "..."]
     }
     ```
   - Cache 1h, return.
3. Ajouter route `path('content-brief/', ContentBriefView.as_view(), name='content-brief')` dans `urls.py` et l'import.
4. Tester via curl avec un mot-clé FR : `curl -X POST .../content-brief/ -H "Authorization: Bearer ..." -d '{"keyword":"automatisation pme quebec","language":"fr"}'`.
5. Valider `python backend/manage.py check`.
6. Si OK : créer `src/components/ContentBrief.tsx` consommant l'endpoint via react-query, intégrer dans `AIGenerator.tsx` (étape 0 "Brief avant article").
7. `npm run build` doit passer.
8. Commit local `feat(seo): content brief generator (intent + outline + FAQ + entities)`.

**Pour la session cloud /schedule** : se contenter du backend (étapes 1-5) ; le frontend nécessite de tester visuellement et est mieux fait dans une session locale avec Darius.

**Blocages** : aucun. Toutes les APIs (Serper, Gemini) sont déjà configurées en env Railway.

**Actions humaines en attente** : aucune. Voir `PENDING_HUMAN.md` quand existera.

---

## Session 2026-05-04 (suite) — Content Brief Generator (backend)

**Fait** :
- Backend `ContentBriefView` ajouté dans `backend/sites_mgmt/views.py` (entre `CompetitorAnalysisView` et la section public API).
  - Input : `{keyword, language: 'fr'|'en'|'es'}` (`site_id` optionnel mais ignoré pour l'instant — réservé pour usages futurs comme contextualiser sur un site).
  - Étape 1 : Serper SERP top 10 + `peopleAlsoAsk` + `relatedSearches` (best-effort, l'absence de `SERPER_API_KEY` n'est pas bloquante).
  - Étape 2 : Gemini 2.5 flash avec un prompt structuré qui demande JSON :
    `search_intent`, `intent_explanation`, `recommended_titles[3]`, `outline[]` (level 2/3),
    `word_count_target`, `faq[{question, answer_hint}]`, `entities[]`,
    `schemas_suggested[]`, `eeat_signals[]`.
  - Cache 1h via `_seo_cache_key('content-brief:', keyword, language)`.
  - Retour : `{keyword, language, serp_competitors, people_also_ask, related_searches, brief}`.
- Route `path('content-brief/', ContentBriefView.as_view(), name='content-brief')` ajoutée dans `urls.py` (juste après `keyword-research/`).
- Import `ContentBriefView` ajouté.

**Tests** :
- `python backend/manage.py check` → "System check identified no issues (0 silenced)". OK.
- AST parse OK pour `views.py` et `urls.py`.
- **Test live à faire (humain)** : `curl -X POST .../content-brief/ -H "Authorization: Bearer ..." -d '{"keyword":"automatisation pme quebec","language":"fr"}'` quand le backend tournera (nécessite GEMINI_API_KEY + idéalement SERPER_API_KEY déjà configurées sur Railway).

**Branches/commits** : commit local à venir, **pas de push** (cf workflow local-first).

**Prochain bloc concret** : (voir entrée suivante — frontend fait dans la même session)

**Blocages** : aucun.

**Actions humaines en attente** : aucune.

---

## Session 2026-05-04 (suite 2) — Content Brief Generator (frontend) ✅ Tier 1 #1 DONE

**Fait** :
- Composant `src/components/ContentBrief.tsx` (`ContentBriefPanel`) — UI complète :
  - Input mot-clé + bouton générer (mutation react-query → `POST /content-brief/`).
  - Skeleton pendant chargement.
  - Brief reçu : sections collapsibles (search intent badge, 3 titres cliquables → clipboard, outline H2/H3 indenté, word count target, FAQ expandable details, entities en tags, schemas en badges, EEAT en checklist verte, top 5 concurrents SERP).
  - Prop `onApply` pour auto-remplir un formulaire parent.
- Intégration dans `src/pages/dashboard/AIGenerator.tsx` :
  - `<ContentBriefPanel>` placé au-dessus du grid form/result.
  - `onApply` rempli : `topic`, `title` (premier titre recommandé), `keywords` (6 premières entities) → préfille les champs du générateur quand l'utilisateur clique "Utiliser ce brief".
- i18n FR + EN : 21 nouvelles clés `brief.*` dans `src/i18n/fr.json` et `src/i18n/en.json`.

**Tests** :
- `python backend/manage.py check` → OK
- JSON i18n valide (parse OK)
- `npm install` → OK
- `npm run build` → ✓ built in 11.45s, 2256 modules transformed, sortie complète dans `dist/`. Warning chunk size > 500KB sur DashboardLayout (déjà présent avant cette session, hors scope).
- **Test live à faire (humain)** : aller sur `/dashboard/<siteId>/generer`, voir le panneau "Brief de contenu" en haut, taper un mot-clé FR, cliquer Générer, vérifier que le brief s'affiche correctement et que "Utiliser ce brief" préfille les champs en bas.

**Branches/commits** : commit local à venir (pas de push).

**Prochain bloc concret** :

**Tier 1 #2 — People Also Ask harvester + auto-FAQ schema** (estimé 2h) :

1. Lire dans `backend/sites_mgmt/views.py` la classe `KeywordResearchView` (~ligne 1574) qui appelle déjà Serper avec `peopleAlsoAsk`. Réutiliser le pattern.
2. Ajouter `class PAAView(APIView)` après `ContentBriefView`. Body :
   - Input : `{keyword, language}`.
   - Cache key `_seo_cache_key('paa:', keyword, language)`.
   - Étape A : Serper SERP → `peopleAlsoAsk` array.
   - Étape B (optionnel mais utile) : pour chaque question, demander à Gemini une réponse courte (1-2 phrases) factuelle, prête pour le schema FAQPage.
   - Retour : `{questions: [{question, answer}], faq_schema: {…JSON-LD FAQPage…}}`.
3. Ajouter route `path('paa/', PAAView.as_view(), name='paa')` dans `urls.py`.
4. Frontend : ajouter une section dans `src/components/SEOAnalyzer.tsx` (le hub SEO) — ou un nouveau composant `PAAPanel.tsx` — avec champ mot-clé, bouton "Récupérer PAA", liste questions/réponses, bouton "Insérer FAQ schema dans l'article courant" (insère le JSON-LD dans `<script type="application/ld+json">`).
5. i18n `paa.*` keys.
6. `python manage.py check` + `npm run build` doivent passer.

**Alternative** (si tu veux varier) : Tier 1 #4 — Hreflang validator (1h, plus rapide) ou Tier 1 #3 — Bulk SEO audit (3h, plus impactant).

**Blocages** : aucun.

**Actions humaines en attente** : aucune (la PR éventuellement ouverte par le run cloud déclenché plus tôt peut être ignorée/fermée — la feature est faite en local).
