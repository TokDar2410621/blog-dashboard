# Roadmap stratégique

Features ordonnées par **impact ÷ effort**. Cocher `[x]` quand fait. Ajouter des items quand on en découvre.

## Tier 1 — différenciation immédiate

### 1. Content Brief Generator ✅ DONE (sauf wire-up generator)
- [x] Backend `POST /content-brief/` — combine Serper SERP + PAA + competitor + Gemini synthesis → JSON brief :
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
- [ ] (Optionnel, futur) Wire-up dans `GenerateArticleView` pour consommer le brief comme contexte au pipeline Claude — actuellement le brief préfille seulement les champs du formulaire.
- [x] i18n FR + EN.
- **Pourquoi prio 1** : transforme "audit après écriture" → "guide avant écriture". Différenciation forte vs Ahrefs/Semrush en FR-CA.

### 2. People Also Ask + auto-FAQ schema ✅ DONE
- [x] Backend `POST /paa/` — Serper SERP avec `peopleAlsoAsk` → liste questions, Gemini génère réponses courtes.
- [x] Construit JSON-LD FAQPage `mainEntity` avec Question + acceptedAnswer.
- [x] Frontend `PAAPanel.tsx` : intégré dans `AIGenerator.tsx`, copy+insert schema.
- [ ] (Futur) Wire-up dans `PostEditor.tsx` avec prop `onInsertSchema` pour insérer directement dans l'article édité.

### 3. Bulk SEO audit ✅ DONE
- [x] Backend `GET /sites/<id>/audit-all/?limit=N&language=L` — itère articles publiés, appelle `_run_seo_audit` (helper extrait, partagé avec SEOAuditView). Cache 1h par article via cache key existant.
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

## Tier 2 — feedback loop (après Tier 1)

### 5. Rank tracking ⏱ 8-12h — 90% DONE
- [x] DB : modèles `TrackedKeyword(site, keyword, language, target_url, is_active)` + `SerpRank(tracked, position, url, title, is_target_match, source, recorded_at)`.
- [x] Migration `0012_trackedkeyword_serprank_and_more`.
- [x] Endpoint `POST /sites/<id>/keywords/` (ajouter mot-clé suivi). DELETE `/keywords/<pk>/`. GET liste.
- [x] Endpoint `POST /sites/<id>/rank-snapshot/` — itère tracked actifs, query Serper top 100, cherche target_url ou site.domain, stocke SerpRank.
- [x] Endpoint `GET /sites/<id>/rank-history/?tracked_id=X&days=90` avec **decay alert** automatique (warning si chute >5 places vs médiane, critical si hors top 100).
- [x] Frontend `KeywordTracker.tsx` : form d'ajout, table avec position colorée, snapshot button, expand row → historique 90j + decay alert.
- [ ] (Étape C) Cron `/schedule` ou cron Railway pour snapshot quotidien automatique.
- [ ] (Étape D) Graphe recharts d'évolution dans la row expansée (à la place / en plus de la liste texte).

### 6. Content decay detector ⏱ 3h
- [ ] Articles dont impressions/clics GSC chutent sur 30 jours glissants (utiliser `GSCQueriesView` data).
- [ ] Suggestion auto : refresh, expansion, ou redirect.

### 7. Topic Cluster Planner ⏱ 6-8h
- [ ] Gemini analyse articles existants → propose pillars + spokes.
- [ ] Suggère liens internes pour densifier maillage.
- [ ] Visu graphe (`react-flow` ou SVG simple).

## Tier 3 — qualité produit (parallélisable)

- [ ] **8. Internal link graph viz** ⏱ 4h
- [ ] **9. Broken link checker** (sortants + internes) ⏱ 3h
- [ ] **10. Auto-redirect 301 sur slug change** ⏱ 2h (modèle Redirect + middleware)
- [ ] **11. Image SEO** (WebP auto, srcset, descriptive filenames) ⏱ 4h
- [ ] **12. Readability scores FR/EN** (Flesch-Kincaid, ARI) ⏱ 2h, branche dans audit
- [ ] **13. Quebec lexicon** (FR-CA dictionnaire, schema LocalBusiness) ⏱ 4h
- [ ] **14. Bing Webmaster integration** ⏱ 6h (action humaine pour API key)
- [ ] **15. Search trends FR-CA** (Google Trends via pytrends) ⏱ 3h
- [ ] **16. Reddit/Quora question harvesting** ⏱ 2h

## Tier 4 — finition / commercialisation

- [ ] **17. Weekly digest auto** (rapport email/PDF par site) ⏱ 4h
- [ ] **18. EEAT author profile** ⏱ 2h
- [ ] **19. Plagiarism / originality check** ⏱ 3h (action humaine pour clé API tierce)
- [ ] **20. Multi-domain comparison** ⏱ 4h
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
