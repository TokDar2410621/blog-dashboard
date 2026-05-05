# Mission — SEO n°1 au Québec

> **Énoncé verbatim de Darius** (2026-05-04)
>
> "Tu feras de blog dashboard le SaaS n°1 au Québec pour le SEO d'articles de blog. Tu chercheras les stratégies pour l'atteindre, tu implementeras, tu feras des tests, et chaque jour tu t'amélioreras. Tu pourras utiliser des agents schedule. Pas besoin de push. Tu feras d'abord en local puis quand tu verras que tu es sur la voie et que tu as presque accompli ta mission, tu demanderas à l'utilisateur de faire des actions qui demandent d'être un humain."

## Why

Darius est fondateur solo. Il veut un produit différenciant qu'il peut commercialiser à des PME québécoises. Le marché québécois est sous-servi en outils SEO bilingues FR-CA / EN-CA — Ahrefs, Semrush, Surfer ne comprennent ni le marché ni la langue locale. Le créneau : un SaaS SEO **bilingue, abordable, calibré FR-CA**, qui génère ET optimise les articles pour les blogs des PME.

## Critères de succès

Le SaaS est "n°1 au Québec" quand :

1. **Capacités SEO** : 80%+ de la roadmap (`ROADMAP.md`) est en prod et fonctionnelle.
2. **Validation terrain** : les 3 sites de Darius (Arivex, LocaSur, TokamDarius) montrent une amélioration mesurable de leurs positions GSC sur 6+ semaines (impressions, clics, position moyenne).
3. **Onboarding** : un nouveau client peut connecter son blog (hosted ou external DB) et obtenir son premier audit + brief en moins de 10 minutes.
4. **Différenciation FR-CA** : presets et lexique québécois en place (LocalBusiness schema, terminologie québécoise, intégration Bing CA).

## Capacités déjà en place (au 2026-05-04)

Voir `ARCHITECTURE.md` pour le détail des endpoints. Résumé :

- [x] Audit IA actionnable (per-item Fix + Tout corriger)
- [x] Recherche de mots-clés (Serper + Gemini)
- [x] Analyse compétiteurs SERP top 10
- [x] Backlinks
- [x] PageSpeed / Core Web Vitals
- [x] Schema.org JSON-LD
- [x] Alt-text quality
- [x] Cannibalisation (génération + détection cross-articles)
- [x] Cache audit IA (1h)
- [x] Google Search Console OAuth + queries
- [x] Suggestions liens internes IA
- [x] Traduction Gemini avec translation_group
- [x] Dedup public list par translation_group

## Capacités à ajouter (= la roadmap, voir `ROADMAP.md`)

### Tier 1 (différenciation immédiate)
- [x] Content Brief Generator (intent + competitors + outline + FAQ + entités)
- [x] People Also Ask harvester + auto-FAQ schema
- [x] Bulk SEO audit
- [x] Hreflang validator

### Tier 2 (feedback loop)
- [x] Rank tracking (GSC + Serper history, alertes décay) — base + UI ; cron quotidien à brancher
- [x] Content decay detector
- [ ] Topic Cluster Planner

### Tier 3 (qualité produit)
- [ ] Internal link graph viz
- [ ] Broken link checker
- [ ] Auto-redirect 301 sur slug change
- [ ] Image SEO (WebP, srcset)
- [ ] Readability scores FR/EN
- [ ] Quebec lexicon (FR-CA, schema LocalBusiness)
- [ ] Bing Webmaster integration
- [ ] Search trends FR-CA

### Tier 4 (finition / commercialisation)
- [ ] Weekly digest auto
- [ ] EEAT author profile
- [ ] Plagiarism / originality check
- [ ] Multi-domain comparison
- [ ] Pricing + Stripe (action humaine requise)

## Quand "presque accompli"

Tier 1+2+3 done à 80%+. À ce moment, créer une entrée dans `PENDING_HUMAN.md` listant ce que Darius doit faire pour la commercialisation (pricing, copy landing, vidéo demo, configuration Stripe, etc.).
