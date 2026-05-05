# Roadmap stratégique

Features ordonnées par **impact ÷ effort**. Cocher `[x]` quand fait. Ajouter des items quand on en découvre.

## Tier 1 — différenciation immédiate

### 1. Content Brief Generator ⏱ 4-6h
- [x] Backend `POST /content-brief/` — combine Serper SERP + PAA + competitor + Gemini synthesis → JSON brief :
  - search_intent (informational/commercial/transactional/navigational)
  - top 5 competitors (titles + headings extraits)
  - recommended_title patterns (3 variantes)
  - outline (H2/H3 suggérés)
  - word_count_target (médiane top 10)
  - faq[] (extraits de PAA)
  - entities[] (LSI keywords à mentionner)
  - schemas[] suggérés (Article, HowTo, FAQ, etc.)
  - eeat_signals[] (auteur expert, sources, dates fraîches)
- [ ] Cache 1h via `_seo_cache_key`.
- [ ] Frontend `src/components/ContentBrief.tsx` + intégration dans `AIGenerator.tsx` (étape 0 "Brief avant article").
- [ ] Wire-up dans `GenerateArticleView` pour consommer le brief si fourni.
- [ ] i18n FR + EN.
- **Pourquoi prio 1** : transforme "audit après écriture" → "guide avant écriture". Différenciation forte vs Ahrefs/Semrush en FR-CA.

### 2. People Also Ask + auto-FAQ schema ⏱ 2h
- [ ] Backend `POST /paa/` — Serper SERP avec `peopleAlsoAsk` → liste questions.
- [ ] Gemini formate en FAQ schema JSON-LD.
- [ ] Frontend : section dans `SEOAnalyzer.tsx`, bouton "Insérer FAQ schema" dans l'éditeur.

### 3. Bulk SEO audit ⏱ 3h
- [ ] Backend `GET /sites/<id>/audit-all/` — itère articles publiés, appelle audit IA, agrège (top issues, score moyen, articles faibles).
- [ ] Pour gros sites : tâche async via `threading.Thread` + endpoint de polling status (MVP simple).
- [ ] Frontend : page `/dashboard/<siteId>/audit-global` avec dashboard agrégé + drill-down article.

### 4. Hreflang validator ⏱ 1h
- [ ] Dans `SEOAuditView` ajouter check : si `translation_group` a 2+ articles publiés, vérifier que chacun déclare les `<link rel="alternate" hreflang>` corrects.
- [ ] Listing dans l'audit des articles dont les translations existent mais ne sont pas annoncées.

## Tier 2 — feedback loop (après Tier 1)

### 5. Rank tracking ⏱ 8-12h
- [ ] DB : nouveau modèle `SerpRank(site, keyword, language, position, date, url)`.
- [ ] Migration.
- [ ] Endpoint `POST /sites/<id>/keywords/track/` (ajouter mot-clé suivi).
- [ ] Cron via `/schedule` quotidien : interroger GSC + Serper pour chaque mot-clé suivi, stocker position.
- [ ] Endpoint `GET /sites/<id>/rank-history/?keyword=X`.
- [ ] Alertes : décay = chute >5 places ou hors top 20.
- [ ] Frontend : graphique recharts évolution + table des décays.

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
