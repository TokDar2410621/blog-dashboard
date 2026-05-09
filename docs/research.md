# Outils de recherche

Avant d'écrire un article, tu fais de la recherche : sujets pertinents, mots-clés à cibler, questions que pose l'audience, tendances émergentes, ce que font les concurrents. Gridar intègre 5 outils de recherche pour brancher tout ça dans le brief avant génération.

Tous accessibles depuis l'AIGenerator (panneaux à droite ou via la sidebar).

## 1. Keyword research

**Sidebar → Recherche de mots-clés** (ou panneau "Keywords" dans l'éditeur)

Entre un seed keyword (ex : "crm pme québec") → on retourne :

- **Keywords liés** (40-80 résultats) avec :
  - Volume mensuel estimé (recherches/mois)
  - Difficulté SEO (0-100)
  - Trend 12 mois (montant / stable / déclinant)
  - Intent (informational / commercial / navigational / transactional)
- **Long-tail keywords** (3+ mots) plus faciles à cibler
- **Question keywords** (commençant par comment / pourquoi / quel / etc.)

Source : Serper + Gemini (corroboration entre 2 sources réduit les hallucinations de volumes).

Bouton "Ajouter à mes mots-clés trackés" pour push vers le rank tracker en un clic.

Coût : 1 req Serper + 1 req Gemini par recherche (~0.01$).

## 2. People Also Ask (PAA)

**Sidebar Brief de contenu → bouton "PAA"** ou directement panneau dans l'éditeur

Récupère les questions Google "People Also Ask" pour ton mot-clé. Pour chaque question :
- Le texte exact de la question
- Une réponse courte (paragraph snippet style)
- L'URL qui répond actuellement (ta concurrence pour cette question)

Usage : crée une section FAQ dans ton article qui répond à ces questions verbatim → augmente fortement les chances d'apparaître en featured snippet Google.

Bonus : on génère automatiquement un schema **FAQPage** JSON-LD avec ces Q/R, à coller dans ton article.

```bash
curl -X POST -H "Authorization: Bearer btb_xxx" \
  -H "Content-Type: application/json" \
  -d '{"keyword": "meilleur crm pme québec"}' \
  https://api.blog-dashboard.ca/api/v1/paa/
```

## 3. Search Trends (Google Trends FR-CA)

**Sidebar → Tendances de recherche**

Google Trends géo-restreint au Canada (FR/EN) ou à un pays au choix. Pour un terme :

- Graphique 30j / 90j / 12 mois / 5 ans
- Mots-clés associés en hausse (rising queries)
- Top mots-clés du sujet
- Régions où le terme est le plus recherché

Différenciateur Québec : par défaut on filtre `geo=CA-QC` (Québec spécifiquement). Pour FR-CA tu vois les vraies tendances de ton marché, pas Paris.

Use case : repère un sujet en hausse → écris un article en avance de phase → ranque pendant le pic.

Source : pytrends (API non-officielle Google Trends).

## 4. Community Questions (Reddit / Quora)

**Sidebar → Questions Reddit/Quora** ou panneau dans l'éditeur

Cherche les vraies questions que les gens posent sur les forums autour de ton sujet :

- **Reddit** : top posts question/help dans les subreddits pertinents
- **Quora** : questions trending avec le plus de réponses
- **Forum spécialisés** : pour B2B (le code va voir AHQ pour QC, communauté Wix Partners, etc.)

Pour chaque question :
- Le titre exact
- Lien vers le thread original
- Nombre d'upvotes / réponses (popularité)
- Date

Use case : ces questions sont des sujets d'article instantanés. Si 200 personnes ont upvoté la question "Comment lier deux comptes Stripe pour un même OBNL ?", écris l'article - il y a une demande.

## 5. Competitor analysis

**Sidebar → Analyse concurrent**

Entre l'URL d'un concurrent → on crawl :

- **Top 50 articles** par trafic estimé
- **Top mots-clés** sur lesquels il classe (top 30 Google)
- **Topic clusters** détectés (groupes thématiques)
- **Gaps** : mots-clés/sujets où il classe et pas toi
- **Backlinks profile** (top 100 domaines référents)
- **Schema.org coverage** : quels schemas il utilise (Article, FAQPage, HowTo, BreadcrumbList...)

Coût : ~5-10 req Serper + 1 long crawl. Compte 0.10-0.30$ par analyse.

Use case : identifier ce qu'il fait mieux que toi → combler les gaps.

## Combiner les outils dans un brief

Le **brief de contenu** ([Outils SEO](seo-tools.md#brief-de-contenu)) peut puiser dans tous ces outils. Workflow :

1. Brief de contenu, mot-clé cible : "meilleur crm pme québec"
2. Le brief inclut auto :
   - Intent (de keyword research)
   - Outline (généré + augmenté avec entités du SERP)
   - **FAQ** = questions PAA
   - **Trends** : si le sujet est en hausse, mention dans le brief
   - **Concurrents qui rankent** sur ce keyword (top 5 SERP)
3. Tu valides → applique au formulaire de génération
4. L'IA écrit avec TOUTES ces données en contexte → article ultra-pertinent

## Quotas et coûts

Ces outils consomment des **API externes** payées par nous. Pour limiter les abus :

| Outil | Limite par jour (Pro) | Limite par jour (Agence) |
|---|---|---|
| Keyword research | 30 | 100 |
| PAA | 50 | 200 |
| Search Trends | 30 | 100 |
| Community Questions | 30 | 100 |
| Competitor analysis | 5 | 20 |

Free et Solo : pas d'accès aux outils Trends, Community et Competitor (juste keyword research basique + PAA limité).

Limites Enterprise : sur mesure.

## Endpoints API

| Endpoint | Body | Retourne |
|---|---|---|
| `POST /api/v1/keyword-research/` | `{seed: "crm pme"}` | Keywords liés + long-tail + questions |
| `POST /api/v1/paa/` | `{keyword: "..."}` | Questions PAA + réponses |
| `POST /api/v1/trends/` | `{keyword: "...", geo: "CA-QC"}` | Trends graphique + rising |
| `POST /api/v1/community-questions/` | `{keyword: "..."}` | Reddit + Quora |
| `POST /api/v1/competitors/` | `{url: "https://concurrent.ca"}` | Analyse complète |

Tous nécessitent Bearer token + plan Pro+.
