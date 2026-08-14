# Roadmap stratégique

Features ordonnées par **impact ÷ effort**. Cocher `[x]` quand fait. Ajouter des items quand on en découvre.

## Tier 1 - différenciation immédiate

### 1. Content Brief Generator ✅ DONE (sauf wire-up generator)
- [x] Backend `POST /content-brief/` - combine Serper SERP + PAA + competitor + Gemini synthesis → JSON brief :
  - search_intent (informational/commercial/transactional/navigational)
  - top 10 competitors (rank, title, url, snippet)
  - recommended_title patterns (3 variantes)
  - outline (H2/H3 suggérés)
  - word_count_target (suggéré par Gemini selon SERP top 10)
  - faq[] (questions PAA + answer_hint)
  - entities[] (LSI keywords à mentionner)
  - schemas[] suggérés (Article, HowTo, FAQ, etc.)
  - eeat_signals[] (auteur expert, sources, dates fraîches)
- [x] Cache 1h via `_seo_cache_key`.
- [x] Frontend `src/components/ContentBrief.tsx` + intégration dans `AIGenerator.tsx`.
- [ ] (Optionnel, futur) Wire-up dans `GenerateArticleView` pour consommer le brief comme contexte au pipeline Claude - actuellement le brief préfille seulement les champs du formulaire.
- [x] i18n FR + EN.
- **Pourquoi prio 1** : transforme "audit après écriture" → "guide avant écriture". Différenciation forte vs Ahrefs/Semrush en FR-CA.

### 2. People Also Ask + auto-FAQ schema ✅ DONE
- [x] Backend `POST /paa/` - Serper SERP avec `peopleAlsoAsk` → liste questions, Gemini génère réponses courtes.
- [x] Construit JSON-LD FAQPage `mainEntity` avec Question + acceptedAnswer.
- [x] Frontend `PAAPanel.tsx` : intégré dans `AIGenerator.tsx`, copy+insert schema.
- [ ] (Futur) Wire-up dans `PostEditor.tsx` avec prop `onInsertSchema` pour insérer directement dans l'article édité.

### 3. Bulk SEO audit ✅ DONE
- [x] Backend `GET /sites/<id>/audit-all/?limit=N&language=L` - itère articles publiés, appelle `_run_seo_audit` (helper extrait, partagé avec SEOAuditView). Cache 1h par article via cache key existant.
- [x] Agrégation : mean_score, distribution 4 buckets, top_weaknesses Counter, top_actions Counter, weakest_articles top 10.
- [ ] (Futur, gros sites) async via `threading.Thread` + polling.
- [x] Frontend page `BulkAudit.tsx` : KPIs, distribution bar visuelle, top issues, weakest articles cliquables.
- [x] Route + sidebar link.

### 4. Hreflang validator ✅ DONE
- [x] Endpoint dédié `POST /hreflang-check/` (mieux que dans audit pour ne pas polluer le cache audit).
- [x] Deux modes : per-group (siblings + missing langs) et site-wide (agrégat groups_complete/incomplete + orphelins).
- [x] Frontend `HreflangCard.tsx` dans Overview avec 3 stats + liste des groupes incomplets cliquables.
- [x] i18n FR + EN.
- (Validation des `<link rel="alternate" hreflang>` HTML serait redondante : c'est le frontend qui les rend depuis `/translations/` endpoint. La consistency DB est ce qui compte.)

## Tier 2 - feedback loop (après Tier 1)

### 5. Rank tracking ⏱ 8-12h - 90% DONE
- [x] DB : modèles `TrackedKeyword(site, keyword, language, target_url, is_active)` + `SerpRank(tracked, position, url, title, is_target_match, source, recorded_at)`.
- [x] Migration `0012_trackedkeyword_serprank_and_more`.
- [x] Endpoint `POST /sites/<id>/keywords/` (ajouter mot-clé suivi). DELETE `/keywords/<pk>/`. GET liste.
- [x] Endpoint `POST /sites/<id>/rank-snapshot/` - itère tracked actifs, query Serper top 100, cherche target_url ou site.domain, stocke SerpRank.
- [x] Endpoint `GET /sites/<id>/rank-history/?tracked_id=X&days=90` avec **decay alert** automatique (warning si chute >5 places vs médiane, critical si hors top 100).
- [x] Frontend `KeywordTracker.tsx` : form d'ajout, table avec position colorée, snapshot button, expand row → historique 90j + decay alert.
- [ ] (Étape C) Cron `/schedule` ou cron Railway pour snapshot quotidien automatique.
- [x] (Étape D) Graphe recharts d'évolution dans la row expansée - Y-axis inversé, reference lines top3/top10, plafond pour positions hors top 100.

### 6. Content decay detector ✅ DONE
- [x] Backend `GET /sites/<id>/content-decay/?days=N` - 2 GSC queries, deltas par page, règles de seuils (-30% imp, -40% clicks), suggested_action (redirect_or_remove / major_refresh / minor_refresh).
- [x] Frontend page `ContentDecay.tsx` mountée sur `/decay` : 3 KPIs, liste cards avec deltas colorés, badge action, bouton Corriger → PostEditor.
- [x] États d'erreur GSC explicites (not_configured, reauth_required) avec liens vers paramètres.
- [x] Sidebar link + i18n FR/EN.

### 7. Topic Cluster Planner ✅ DONE (basic)
- [x] Backend `POST /sites/<id>/topic-clusters/` - Gemini groupe en 3-8 clusters avec pillar + spokes + suggestions de gaps.
- [x] Cache 1h, slugs validés contre la DB (flag `exists: false` si Gemini hallucine).
- [x] Calcul des `unassigned[]`.
- [x] Frontend page `TopicClusters.tsx` avec cartes par cluster, pillar mis en valeur, spokes en grid, suggestions avec bouton Générer.
- [ ] (Futur, étape 2) Visualisation graphe `react-flow` au lieu des cartes simples.
- [ ] (TODO mineur) `AIGenerator.tsx` doit lire `?title=...` query param pour que le bouton "Générer" depuis un cluster gap pré-remplisse le titre.

## Tier 3 - qualité produit (parallélisable)

- [x] **8. Internal link graph viz** ⏱ 4h - endpoint `/link-graph/` parse markdown + HTML pour edges, calcule orphans/hubs/dead_ends. UI 3-cols + top 10 connected.
- [x] **9. Broken link checker** - endpoint `/broken-links/` HEAD+GET probe, cache 24h par URL, groupe par URL avec liste des articles. UI dédiée avec status badge + cliquable.
- [x] **10. Auto-redirect 301 sur slug change** - modèle `Redirect` + migration 0013 + auto-hook dans `SitePostDetailView.patch` + 301 dans `PublicPostDetailView` + CRUD admin + UI `/dashboard/<id>/redirects`.
- [x] **11. Image SEO** (alt text via Gemini Vision) - endpoint `/image-suggest/` analyse l'image (Gemini Vision multimodal), retourne alt text + filename slug + description, contextualisé sur title+keyword+language. UI bouton "IA" dans ImageInsertDialog. (WebP auto + srcset reportés en option future, pas critiques pour SEO direct.)
- [x] **12. Readability scores FR/EN** (Flesch-Kincaid, ARI) - endpoint `/readability/`, helpers FR/EN avec syllable-counter heuristique, ReadabilityCard mounted in PostEditor SEO view, suggestions auto.
- [x] **13. Quebec lexicon** - endpoint `/lexicon-check/` avec dictionnaire ~50 entrées FR-FR→FR-CA + helper `_generate_local_business_schema` adapté Québec (addressCountry CA, addressRegion QC, areaServed Québec). UI `LexiconCard` mounted in PostEditor, conditionné FR uniquement.
- [ ] **14. Bing Webmaster integration** ⏱ 6h (action humaine pour API key)
- [x] **15. Search trends FR-CA** - pytrends ajoute à requirements, endpoint `/trends/` avec interest_over_time + top + rising queries. UI SearchTrendsPanel avec recharts AreaChart, intégré dans AIGenerator.
- [x] **16. Reddit/Quora question harvesting** - endpoint `/community-questions/` deux Serper queries `site:reddit.com` + `site:quora.com`, panel intégré dans AIGenerator.

## Tier 4 - finition / commercialisation

- [x] **17. Weekly digest** (rapport téléchargeable, sans SMTP) - endpoint `/sites/<id>/weekly-digest/` agrège articles publiés cette semaine, top vues, mouvements de positions (top + worst), redirections récentes. Page imprimable `/dashboard/<id>/digest` avec window.print() pour PDF.
- [x] **18. EEAT author profile** - 7 champs ajoutés à Site (role, bio, credentials, image, linkedin, twitter, website), migration 0014, helper `_generate_person_schema`, endpoint `/sites/<id>/person-schema/`, PublicSiteView enrichi avec `author` + `person_schema`. UI complète dans SiteSettings.
- [ ] **19. Plagiarism / originality check** ⏱ 3h (action humaine pour clé API tierce)
- [x] **20. Multi-domain comparison** - endpoint `/multi-domain-stats/` agrège tous les sites de l'owner, page `/compare` avec table cross-site + KPI cards + couverture GSC/EEAT. Lien depuis SiteSelector.
- [ ] **21. Pricing + Stripe** ⏱ 8h (**action humaine** : config compte Stripe)
- [ ] **22. Landing page commerciale** ⏱ 6h
- [ ] **23. Onboarding flow** (connexion blog en <10 min) ⏱ 6h

## Critères "done" pour chaque item

- Endpoint backend fonctionnel (testé curl ou test unit).
- Composant frontend rendu sans erreur TS.
- Build Vite passe (`npm run build`).
- `python manage.py check` passe.
- Au moins une trace dans `PROGRESS_LOG.md`.
- Checklist `[x]` cochée dans ce fichier.

## Découvert en cours de route

(Append ici si on découvre un item manquant qui ne rentre pas dans les tiers ci-dessus.)

---

## Tier 5 - Pivot 2026-05-15 : audit site-level + onboarding wedge

**Pourquoi ce tier** : voir entrée "Pivot 2026-05-15" dans `PROGRESS_LOG.md`. Les Tiers 1-4 ont livré les *capacités*, ce tier livre les *frictions à éliminer* qui empêchent les prospects de convertir.

### Phase 1 - Audit SEO site-level unifié ✅ DONE (commit a7d9ee2)
Page UNIQUE dans le dashboard qui agrège les endpoints existants en un seul tableau de bord :
- [x] Backend `GET /api/sites/<id>/site-audit/` - aggregator parallèle (ThreadPoolExecutor) + composite score 0-100 avec redistribution des poids si composante manque.
- [x] Frontend page `src/pages/dashboard/SiteAudit.tsx` - hero score color-coded + 4 cards detail (keywords, PageSpeed, backlinks, content decay) + 5 recos cliquables.
- [x] Route `/dashboard/<id>/audit-site` + lien sidebar (Gauge icon).

### Phase 2 - Sous-domaine `blog.X` plug-and-play ✅ DONE (commit 1b6e1d6)
- [x] Backend `POST /sites/<id>/blog-domain/provision/` (Vercel API call + persist Site.public_blog_domain).
- [x] Backend `GET /sites/<id>/blog-domain/status/` (idempotent verify + state read).
- [x] Backend `DELETE /sites/<id>/blog-domain/` (best-effort Vercel removal + local clear).
- [x] Frontend wizard dans SiteSettings : input + Activer + instructions CNAME + polling 8s + success state.
- **Action humaine restante** : env vars VERCEL_API_TOKEN + VERCEL_PROJECT_ID sur Railway (voir PENDING_HUMAN.md).

### Phase 3 - Page publique `gridar.app/audit` (lead magnet) ✅ DONE (commit 2cd0825)
- [x] Backend `POST /api/public/audit/` (rate-limited 6/min/IP via AnonRateThrottle) - parallel crawl + PageSpeed + Serper positions sur keywords extraits du title/h1. Cache 1h par domain.
- [x] Backend `POST /api/public/leads/` - capture email + Loi 25/RGPD consent + score_at_capture pour cohort.
- [x] Frontend `/audit` (public, hors AuthGuard) avec hero + form + result + email gate + checkbox consent.
- [x] Nouveau modele `Lead` + LeadAdmin pour le suivi sales.
- [ ] (Plus tard) Tracking event "public_audit_started" / "email_captured" Plausible/Posthog.
- [ ] (Plus tard) SMTP pour envoi de rapport detaille par email (au lieu de deblocage cote SPA uniquement).

### Phase 4 - Plugin WordPress 1-click ✅ DONE (commit 058448b)
Architecture finale plus simple que l'OAuth dance prevu - juste un Bearer API token a coller, le plugin gere le reste :
- [x] Plugin PHP `wordpress-plugin/gridar-connector/gridar-connector.php` + readme.txt - admin page sous Settings, auto-creation App Password via WP_Application_Passwords, POST a Gridar, rollback si fail.
- [x] Backend `POST /api/v1/wp-connector/connect/` (Bearer auth via BaseV1View) - probe creds avant persist + upsert (owner, wp_url).
- [ ] **Action humaine** : soumettre le plugin a wordpress.org/plugins (5-15 jours de validation). Voir PENDING_HUMAN.md.

---

## Tier 6 - Reprise de claude-seo (2026-08-14)

Origine : inventaire complet du plugin open-source claude-seo 2.2.4 (MIT,
Daniel Agrici), confronte au code reel de Gridar. Dossier de reference avec
l'inventaire, la licence et les pieges :
https://claude.ai/code/artifact/061040b0-6605-4dfc-a767-bbbe70f78529

Darius a tranche le 2026-08-14 : « on va faire les 20 ». Ordre impose par
valeur decroissante, chaque rang suppose les precedents traites.

**Regle de licence** : MIT, attribution requise si un extrait sort du SaaS
(paquet mcp-server publie, export telechargeable). Ligne exacte :
`Claude SEO v2.2.4, Daniel Agrici (AgriciDaniel), MIT, github.com/AgriciDaniel/claude-seo`.
Trois exceptions a ne pas toucher : la skill `seo-flow` (CC BY 4.0),
`content_quality.py` et `content_humanize.py` (CC BY-SA heritee de Wikipedia).

**Regle Railway** : ne jamais porter `google_report.py` (WeasyPrint tire
cairo/pango, meme famille que le pycairo qui a tue le PDF en mai) ni rien
qui importe `render_page` (Playwright, +150 Mo).

Etat au 2026-08-14, branche `mission/2026-08-14-tier6-claude-seo`.
Legende : [x] livre et branche, [~] module ecrit et teste mais pas encore
branche (voir `TIER6_INTEGRATION.md`), [ ] pas commence.

**Les 20 modules sont ecrits et testes.** 6 sont branches sur une surface que
l'utilisateur atteint, 14 attendent leur cablage (endpoint, ecran, parfois un
modele) : voir `TIER6_INTEGRATION.md`.

- [x] 1. `url_safety.py` + fermeture de la SSRF de l'audit public (0d86539, en prod sur main)
- [~] 2. Les 17 regles de derive -> `drift_rules.py` (c383550, 60 tests)
- [x] 3. Data Sufficiency Gate (d6414e4, 10 tests)
- [~] 4. Grille technique reelle -> `technical_grid.py` (54a7242)
- [x] 5. Validation de schema -> `schema_validator.py`, branchee sur la vue de schema (79aecff, 84 tests)
- [x] 6. Affirmations non sourcees -> `content_verify.py`, branchee sur l'audit d'article (5e10de7, 47 tests)
- [~] 7. Profondeur CWV -> `cwv_depth.py` (54a7242)
- [~] 8. Generation de schema -> `schema_builder.py` (c383550, 73 tests)
- [x] 9. Seuils anti-doorway (9a21890, 14 tests)
- [x] 10. Lint Google Business -> `gbp_lint.py`, branche sur l'audit public (b885e77, 42 tests)
- [~] 11. Grille SEO local + coherence NAP -> `local_seo.py` (15ecd6a, 67 tests)
- [~] 12. Garde-fou budgetaire -> `api_budget.py` (54a7242)
- [~] 13. Parsing HTML -> `html_parse.py` (c383550, 49 tests)
- [~] 14. `sitemap_discovery.py` (c383550, 39 tests)
- [~] 15. Updates Google -> `google_updates.py` + `data/` (c383550, 55 tests)
- [~] 16. Chevauchement SERP -> `serp_clustering.py` (54a7242)
- [~] 17. Taxonomie SXO -> `sxo.py` (c383550, 40 tests)
- [~] 18. Rapport HTML autonome -> `report_html.py` (54a7242)
- [~] 19. Recommandations falsifiables -> `thinking_framework.py` (54a7242)
- [x] 20. Lisibilite agent IA -> `agent_ux.py`, branche sur l'audit public (b885e77, 75 tests)

Suite de tests : **1139 tests verts** sur `sites_mgmt`.

### Trous de couverture identifies au passage (hors des 20)

Six territoires que Gridar ne couvre pas du tout : backlinks reels (le
`task_backlinks` actuel compte des mentions Serper, pas des liens, et pese
15 % du score), derive dans le temps, SEO local profond, profondeur CWV,
SEO des images (absent du crawl), SEO e-commerce.

Et une dette sur le score compose : six de ses neuf checks lisent l'etat de
configuration en base, pas l'etat SEO du site. Trois correctifs a cout quasi
nul, detailles dans le dossier de reference.
