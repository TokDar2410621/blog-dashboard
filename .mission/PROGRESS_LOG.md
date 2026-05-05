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

**Prochain bloc concret** : (voir entrée suivante — PAA fait dans la même session)

(Roadmap suivante après PAA :)

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

---

## Session 2026-05-04 (suite 3) — PAA harvester + FAQ schema ✅ Tier 1 #2 DONE

**Fait** :
- Backend `PAAView` ajouté dans `views.py` (juste après `ContentBriefView`).
  - Input : `{keyword, language, generate_answers?: bool=true}`.
  - Étape 1 : Serper SERP top 10 → extrait `peopleAlsoAsk` (jusqu'à 10 questions, avec snippet).
  - Étape 2 (si `generate_answers`) : Gemini génère une réponse courte (1-2 phrases) par question, dans la langue cible. Fallback sur le snippet Serper si Gemini échoue.
  - Étape 3 : construit un **schema JSON-LD `FAQPage`** prêt à coller, avec `mainEntity` array de `Question`/`acceptedAnswer`.
  - Cache 1h via `_seo_cache_key('paa:', keyword, language, gen_answers_flag)`.
- Route `path('paa/', PAAView.as_view(), name='paa')` ajoutée dans `urls.py`.
- Composant `src/components/PAAPanel.tsx` :
  - Input mot-clé + bouton "Récupérer".
  - Liste questions/réponses en `<details>` expandables.
  - Section "Schema FAQPage (JSON-LD)" avec preview du JSON, bouton **Copier** (presse-papiers, format `<script type="application/ld+json">…</script>`) et bouton **Insérer dans l'article** (via prop `onInsertSchema`, optionnelle).
- Intégration dans `AIGenerator.tsx` (sous le `ContentBriefPanel`).
- 14 nouvelles clés `paa.*` dans `fr.json` + `en.json`.

**Tests** :
- `python backend/manage.py check` → OK
- JSON i18n valide
- `npm run build` → ✓ built in 13.25s
- **Test live à faire (humain)** : `/dashboard/<siteId>/generer`, dans le panneau "People Also Ask + FAQ schema", taper un mot-clé qui produit du PAA (ex: "tva auto-entrepreneur quebec"), vérifier que les questions arrivent, que les réponses Gemini sont pertinentes en FR-CA, et que le bouton Copier place bien le `<script type="application/ld+json">` dans le presse-papiers.

**Branches/commits** : commit local à venir (pas de push).

**Prochain bloc concret** :

**Tier 1 #4 — Hreflang validator** (estimé 1h, gain rapide) :

1. Ouvrir `backend/sites_mgmt/views.py`, trouver `class SEOAuditView` (~ligne 1163).
2. Dans la méthode `post`, après l'audit Gemini, ajouter une vérification hreflang :
   - Si `request.data.get('translation_group')` est passé : query toutes les translations du même group.
   - Pour chaque translation, vérifier si le contenu HTML/markdown contient `<link rel="alternate" hreflang="<lang>" href="...">`.
   - Retourner dans la réponse un champ `hreflang_check: { has_alternates: bool, missing: [lang], extras: [{lang, href}] }`.
3. Frontend `src/components/SEOAnalyzer.tsx` : trouver l'affichage du résultat audit, ajouter une section "Hreflang" qui montre le statut (vert si correct, rouge si translations existent mais pas annoncées).
4. i18n `audit.hreflang.*`.
5. `python manage.py check` + `npm run build`.

Alternative : **Tier 1 #3 — Bulk SEO audit** (3h, plus impactant). Itère sur tous les articles publiés d'un site, agrège les problèmes, dashboard agrégé. Choisir entre #4 (rapide, pertinent multi-langue) et #3 (gros impact).

**Recommandation pour la prochaine session** : faire #4 d'abord (1h, finit Tier 1) puis #3.

**Blocages** : aucun.

**Actions humaines en attente** : aucune nouvelle.

---

## Session 2026-05-04 (suite 4) — Hreflang validator ✅ Tier 1 #4 DONE

**Fait** :
- Backend `HreflangCheckView` ajouté dans `views.py` (juste avant `PAAView`).
  - Endpoint `POST /hreflang-check/`. Deux modes selon les inputs :
    - **Per-group** : `{site_id, translation_group}` → renvoie les siblings, langues présentes vs attendues, missing list, flag `is_complete`.
    - **Site-wide** : `{site_id}` seul → renvoie agrégat (total_groups, groups_complete, groups_incomplete avec sample title/slug, single_lang_orphans).
  - Pure DB introspection (HostedPost ou BlogPost via `using(alias)`), pas d'appel externe.
  - Cache 5 min via `_seo_cache_key('hreflang:', site_id, translation_group_or_all)`.
  - Utilise `site.effective_languages` (la propriété qui retourne `available_languages` ou défaut fr/en/es).
- Route `path('hreflang-check/', HreflangCheckView.as_view(), name='hreflang-check')` ajoutée dans `urls.py`.
- Composant `src/components/HreflangCard.tsx` (mode site-wide pour Overview) :
  - 3 stats cards : total groups, complete, incomplete (avec icônes CheckCircle2 et AlertTriangle).
  - Liste des langues attendues du site.
  - Liste scrollable des groupes incomplets (jusqu'à 20) : titre + slug → lien vers PostEditor + badges colorés (langues présentes en bleu, langues manquantes en ambre avec "+lang").
  - Footer : compte d'orphelins single-language.
- Intégration dans `Overview.tsx` : `<HreflangCard siteId={siteId} />` placé avant la section "Recent Posts".
- 10 nouvelles clés `hreflang.*` dans fr.json + en.json.

**Tests** :
- `python backend/manage.py check` → OK
- JSON i18n valide
- `npm run build` → ✓ built in 10.88s
- **Test live à faire (humain)** : aller sur `/dashboard/<siteId>` (Overview), voir la nouvelle carte "Santé hreflang multi-langue", vérifier que les stats sont cohérentes avec les articles publiés (pour Arivex qui a des FR/EN traduits, devrait montrer des groupes complets et/ou incomplets).

**Branches/commits** : commit local à venir (pas de push).

**Prochain bloc concret** :

**Tier 1 #3 — Bulk SEO audit** (estimé 3h) :

1. Ouvrir `backend/sites_mgmt/views.py`. Ajouter `class BulkSEOAuditView(APIView)` après `HreflangCheckView`.
2. Endpoint `GET /sites/<site_id>/audit-all/` (ou POST avec body `{site_id, async?: bool}`).
3. Logique :
   - Itérer les articles publiés du site (limite 50 pour MVP, paginer ensuite).
   - Pour chaque, appeler la même logique que `SEOAuditView` (extraire dans une fonction helper `_run_seo_audit(title, excerpt, content, keyword, language)` partagée).
   - Cache par article via `_seo_cache_key`.
   - Agréger : score moyen, distribution scores (excellent/bon/moyen/faible), top 5 weakness les plus fréquentes, top 5 actions les plus fréquentes, articles les plus faibles (top 10 par score asc).
4. Pour gros sites : optionnel `async: true` → spawn `threading.Thread`, retourne immédiatement un job_id, endpoint de polling `GET /audit-jobs/<id>/`. **Skipper l'async pour le MVP** — sites de Darius < 50 articles, OK synchrone.
5. Frontend : nouvelle page `src/pages/dashboard/BulkAudit.tsx` avec :
   - Bouton "Lancer l'audit complet du site" (bloquant, peut prendre 1-2 min).
   - Loader pendant exécution.
   - Résultat : score moyen en gros, donut chart distribution (recharts), liste des top issues, table des articles les plus faibles cliquables.
6. Route React `/dashboard/<siteId>/audit-global` ajoutée dans le router (chercher où sont définies les routes).
7. Lien dans `DashboardSidebar.tsx`.
8. i18n.
9. Tests : check + build.

**Blocages** : aucun. Sites de prod ont des contenus réels donc l'agrégat sera utile.

**Actions humaines en attente** : aucune nouvelle.

---

## Session 2026-05-04 (suite 5) — Bulk SEO audit ✅ Tier 1 #3 DONE — TIER 1 COMPLETED 🎯

**Fait** :
- **Refactor** : extrait la logique d'audit Gemini dans une fonction helper `_run_seo_audit(title, excerpt, content, keyword, language, api_key)` partagée. Renvoie tuple `(result, from_cache)`. `SEOAuditView` simplifié pour l'utiliser.
- Backend `BulkSEOAuditView` ajouté (juste avant `PAAView`) :
  - Endpoint `GET /sites/<int:site_id>/audit-all/?limit=50&language=fr` (synchrone, MVP).
  - Itère sur les articles publiés (HostedPost ou BlogPost via using).
  - Filtre langue optionnel.
  - Pour chaque article : appelle `_run_seo_audit` (cache 1h par article via le helper).
  - Agrège : `mean_score`, `distribution` (excellent ≥85 / good 70-84 / average 50-69 / poor <50), `top_weaknesses` (Counter sur les 80 premiers chars), `top_actions`, `weakest_articles` (top 10 par score asc).
  - Retourne `cache_hits` pour signaler les économies (utile car le cache rend les runs suivants quasi-instantanés).
- Route `path('sites/<int:site_id>/audit-all/', BulkSEOAuditView.as_view(), name='site-audit-all')` ajoutée.
- Frontend `src/pages/dashboard/BulkAudit.tsx` :
  - Bouton "Lancer l'audit" + select limite (10/25/50/100).
  - 4 KPI cards : audited count, mean score, healthy count, poor count.
  - Distribution bar visuelle (4 segments colorés vert/emerald/amber/rouge avec %).
  - Two-column : top weaknesses (×count) + top actions (×count).
  - Liste des weakest articles avec score coloré + lien vers PostEditor.
  - Skeleton pendant chargement.
- Route React `<Route path="audit-global" element={<BulkAudit />} />` ajoutée dans `DashboardLayout.tsx`.
- Lien sidebar "Audit global SEO" avec icône `TrendingUp` ajouté dans `DashboardSidebar.tsx`.
- 21 nouvelles clés `bulkAudit.*` + `sidebar.bulkAudit` dans fr/en.

**Tests** :
- `python backend/manage.py check` → OK
- JSON i18n valide
- `npm run build` → ✓ built in 10.16s
- **Test live à faire (humain)** : aller sur `/dashboard/<siteId>/audit-global`, choisir limite=10 (premier run), cliquer Lancer. Premier run : 1-2 min (paie chaque article via Gemini). Re-lance : instantané (cache). Vérifier l'agrégat, les top weaknesses/actions, et que les weakest articles cliquent bien vers le PostEditor.

**Branches/commits** : commit local à venir (pas de push).

**🎯 Tier 1 de la roadmap COMPLET** :
- [x] #1 Content Brief Generator
- [x] #2 People Also Ask + FAQ schema
- [x] #3 Bulk SEO audit
- [x] #4 Hreflang validator

**Prochain bloc concret** :

**Tier 2 #5 — Rank tracking** (estimé 8-12h, multi-sessions). Planifier l'architecture en premier :

**Étape A (1h, prochaine session)** : Concevoir le modèle DB `SerpRank`, écrire la migration.
1. Modèle `SerpRank(site FK, keyword str, language str(2), position int, url str, source str, recorded_at datetime)`. Index sur (site, keyword, language, recorded_at).
2. Modèle `TrackedKeyword(site FK, keyword str, language str(2), is_active bool, created_at)` pour stocker les mots-clés à suivre par site.
3. `python manage.py makemigrations sites_mgmt`.
4. Endpoint `POST /sites/<id>/keywords/track/` pour ajouter un mot-clé.
5. Endpoint `GET /sites/<id>/keywords/` pour lister.
6. Endpoint `DELETE /sites/<id>/keywords/<id>/` pour retirer.
7. Frontend : nouvelle page `KeywordTracker.tsx` avec table, ajouter dans le sidebar.
8. Tests : check + build.

**Étape B (2h, session suivante)** : Cron + collecte rank.
- Endpoint `POST /sites/<id>/rank-snapshot/` qui itère les TrackedKeyword actifs, query Serper SERP, stocke SerpRank.
- Test manuel.

**Étape C (3-4h)** : UI graphique d'évolution + alerte décay.

**Alternative à Tier 2 #5** : si les 8-12h sont trop long en autonome, attaquer Tier 3 items courts (Readability scores 2h, EEAT author profile 2h, Auto-redirect 301 2h) qui sont indépendants.

**Recommandation pour la prochaine session** : Tier 2 #5 étape A (1h) pour avancer le rank tracking sans bloquer sur tout.

**Blocages** : aucun. Tier 1 fini, l'app a maintenant un parcours SEO complet : brief avant écriture → écriture assistée → audit après écriture (per article + bulk site-wide) → traduction → maillage international (hreflang) → suivi positions (Tier 2 prochain).

**Actions humaines en attente** : aucune nouvelle.

