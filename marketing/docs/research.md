# Outils de recherche

Avant d'écrire un article, tu fais de la recherche : mots-clés à cibler, questions que pose l'audience, tendances, ce que publient les pages qui rankent déjà. Gridar intègre ces outils à trois endroits :

- **Générer un article** : quatre cartes au-dessus du formulaire, « Brief de contenu », « People Also Ask + FAQ schema », « Questions Reddit / Quora » et « Tendances Google Trends ». Elles se pré-remplissent avec le premier mot-clé ou le sujet du formulaire.
- **Éditeur d'article** : ouvre un article, clique **SEO**, onglet **Audit**. Tu y trouves « Recherche de mots-cles » et « Analyse de la concurrence ».
- **Sidebar → Insights → Analyseur SERP**.

Le Suivi des positions propose aussi des mots-clés à suivre (bouton « Suggerer avec l'IA ») : voir [Outils SEO](seo-tools.md).

Aucun de ces outils ne donne de volume de recherche mensuel ni de score de difficulté. Chacun dit d'où vient ce qu'il affiche.

## 1. Recherche de mots-clés

**Articles → un article → SEO → onglet « Audit » → carte « Recherche de mots-cles »**

Entre un mot-clé de départ (ex : « sablage de plancher montréal ») et clique **Rechercher**. Les résultats arrivent en trois groupes :

- **Recherches associees** : les recherches associées que Google affiche pour ce mot-clé (Serper)
- **Les gens demandent aussi** : les questions « People Also Ask » de Google (Serper)
- **Long-tail (IA)** : 10 variantes de 3 à 6 mots écrites par Gemini

Au survol d'un mot-clé, tu vois son intention estimée (informational, commercial, transactional, navigational). Elle vient des mots de la requête (« prix », « commander », « comment »...), pas d'une lecture du SERP. Un badge **+N** relie les variantes d'une même demande (« même requête, autrement formulée ») sans les fusionner. Clique un mot-clé pour le copier.

**Quelle source a répondu** : sous la liste, Gridar affiche chaque source qui n'a pas répondu normalement (Serper ou Gemini) et pourquoi : non configurée, aucun résultat, échec ou délai dépassé. Une liste courte avec une source en échec ne prouve pas qu'il n'existe pas d'autres mots-clés.

**Langue et géographie** : la recherche suit la langue de l'article. Gridar n'ajoute pas de ciblage de pays : mesuré le 2026-09-01, ce ciblage faisait disparaître les recherches associées et les questions. Pour viser une ville, mets-la dans le mot-clé de départ.

Coût : 1 appel Serper et 1 appel Gemini par recherche, dans un budget de 60 secondes. Pas de cache.

Pour suivre un mot-clé trouvé ici, ajoute-le dans **Suivi des positions**.

API : `POST /api/v1/keyword-research/` avec `{seed_keyword, language}`. Outil MCP : `gridar_keyword_research`.

## 2. People Also Ask (PAA)

**Générer un article → carte « People Also Ask + FAQ schema » → bouton « Récupérer »**

Récupère jusqu'à 10 questions « People Also Ask » de Google pour ton mot-clé (Serper, Google.ca pour le français). Pour chaque question :
- le texte exact de la question
- l'extrait que Google affiche
- une réponse courte d'une ou deux phrases écrite par Gemini (l'extrait de Google si Gemini ne répond pas)

Gridar génère aussi un schema **FAQPage** JSON-LD avec ces questions et réponses : bouton **Copier**, puis colle-le dans ton article. Une section FAQ qui reprend ces questions répond à ce que les gens cherchent autour de ton sujet.

Même mot-clé et même langue : résultat en cache 1 h.

```bash
curl -X POST -H "Authorization: Bearer btb_xxx" \
  -H "Content-Type: application/json" \
  -d '{"keyword": "meilleur crm pme québec", "language": "fr"}' \
  https://api.gridar.app/api/v1/paa/
```

Body : `{keyword, language: "fr" | "en" | "es", generate_answers?: true}`. Outil MCP : `gridar_people_also_ask`.

## 3. Tendances Google Trends

**Générer un article → carte « Tendances Google Trends » → bouton « Analyser »**

Données Google Trends pour un terme, via pytrends (bibliothèque non officielle) :
- courbe d'intérêt (0-100) sur 1 mois, 3 mois, 12 mois (par défaut) ou 5 ans
- **Top requêtes connexes**
- **Requêtes qui montent**, avec leur hausse en %

Le pays suit la langue : Canada pour le français, États-Unis pour l'anglais, Espagne pour l'espagnol. Gridar n'interroge pas Google Trends à l'échelle de la province : les tendances en français couvrent tout le Canada, pas seulement le Québec.

Résultat en cache 24 h. Google limite les appels pytrends : en cas de refus, la carte affiche une erreur ; réessaie plus tard.

Use case : repère un sujet en hausse et publie avant le pic.

Pas d'endpoint v1 : `POST /api/trends/ {keyword, language, timeframe}` fonctionne avec la session du dashboard seulement.

## 4. Questions Reddit / Quora

**Générer un article → carte « Questions Reddit / Quora » → bouton « Trouver »**

Gridar lance deux recherches Google via Serper, `site:reddit.com <ton mot-clé>` et `site:quora.com <ton mot-clé>`, 10 résultats chacune. Pour chaque fil trouvé :
- le titre
- l'extrait
- le lien vers le fil
- la source (Reddit ou Quora)

La carte affiche le nombre de fils trouvés sur chaque site. Pas de nombre de votes, de réponses ni de date : Gridar ne lit pas Reddit ni Quora directement.

Use case : une question posée sur un forum est un sujet d'article. Lis le fil pour voir ce que les gens demandent vraiment.

Même mot-clé et même langue : résultat en cache 1 h. Pas d'endpoint v1 : `POST /api/community-questions/ {keyword, language}` fonctionne avec la session du dashboard seulement.

## 5. Analyse de la concurrence

**Articles → un article → SEO → onglet « Audit » → carte « Analyse de la concurrence » → bouton « Analyser le top 10 »**

L'analyse porte sur le mot-clé principal de l'article, c'est-à-dire son premier tag. Sans tag, la carte te demande d'en définir un.

Gridar lit le top 10 Google du mot-clé (Serper), puis ouvre chaque page (6 secondes au plus par page) et compte ses mots et ses H2. Tu obtiens :
- un tableau : position, titre, nombre de mots, nombre de H2
- la médiane de mots et de H2 du top 10, comparée à la longueur de ton article

Si tu lances ensuite **Corriger avec IA**, ces chiffres entrent dans la correction.

Gridar ne mesure ni le trafic de ces pages, ni leurs mots-clés, ni leurs liens. Pour voir sur quelles requêtes un concurrent passe devant toi, utilise l'outil gratuit [Competitor Gap Finder](https://www.gridar.app/tools/competitor-gap).

API : `POST /api/v1/competitors/` avec `{keyword, language}`. Outil MCP : `gridar_analyze_competitors`.

## 6. Analyseur SERP

**Sidebar → Insights → Analyseur SERP**

Entre un mot-clé cible et sa langue (fr, en, es), puis clique **Analyser**. Gridar lit le top 10 Google (Serper ; Google.ca pour le français) et ouvre chaque page pour mesurer :
- le nombre de mots du texte visible
- le nombre de titres H1, H2 et H3
- la présence d'une FAQ (le mot « FAQ » ou un schema FAQPage)
- la présence d'une vidéo (balise `<video>` ou vidéo YouTube intégrée)

Cartes affichées : **Mots moyens**, **Headings moyens**, **Avec FAQ**, **Avec video**, puis « Word count par position », « Top 10 SERP detaille » et « Facteurs SEO : moyennes du top 10 ».

Le bouton **Generer un article qui bat ce SERP** ouvre Générer un article avec ce mot-clé comme sujet et lance la génération (un article de ton quota). Les mesures du SERP ne sont pas transmises au générateur ; pour qu'il en tienne compte, passe d'abord par le Brief de contenu.

Cette page appelle l'API v1 : sur les plans Pro et Agence, chaque analyse compte dans la limite horaire de l'API (voir plus bas).

API : `POST /api/v1/sites/<id>/serp-analyze/` avec `{keyword, language}`. Outil MCP : `gridar_serp_analyze`.

## Combiner les outils dans un brief

Le **brief de contenu** ([Outils SEO](seo-tools.md)) fait sa propre lecture du SERP. Workflow :

1. **Générer un article → Brief de contenu**, mot-clé cible : « meilleur crm pme québec »
2. Gridar lit le top 10 Google, les questions People Also Ask et les recherches associées (Serper)
3. Gemini en tire l'intention, les titres, le plan, la FAQ (4 à 8 questions, tirées des PAA ou rédigées), les entités et les signaux EEAT ; les 5 premiers concurrents SERP s'affichent
4. **Utiliser ce brief** remplit le formulaire, et le brief part avec la génération

Le brief n'appelle ni Google Trends, ni Reddit/Quora, ni l'analyse de la concurrence. Lance ces cartes à côté si tu en as besoin, et reporte ce qui t'intéresse dans le sujet ou les mots-clés.

## Limites et coûts

- **Crédits** : ces outils de recherche ne consomment pas de crédits. Seule la génération d'un article compte dans ton quota (voir [Plans et crédits](plans-credits.md)).
- **Plan** : dans le dashboard, ces outils ne sont pas filtrés par plan.
- **Limite de débit** : 300 requêtes par minute par compte sur les routes du dashboard (hors `/api/v1/`).
- **API v1** : un token `btb_` exige un plan Pro ou Agence. Les routes `/api/v1/` sont limitées à 30 requêtes par heure en Pro et 200 en Agence, toutes routes confondues, y compris quand une page du dashboard les appelle.
- **Données externes** : Serper, Gemini et Google Trends peuvent répondre vide ou échouer. La recherche de mots-clés dit quelle source n'a pas répondu.

## Endpoints API

| Endpoint | Auth | Body | Retourne |
|---|---|---|---|
| `POST /api/v1/keyword-research/` | session ou token `btb_` | `{seed_keyword, language}` | Mots-clés (`keyword`, `source`, `estimated_intent`, familles de variantes) + état de chaque source |
| `POST /api/v1/paa/` | session ou token `btb_` | `{keyword, language}` | Questions PAA, réponses, schema FAQPage |
| `POST /api/v1/competitors/` | session ou token `btb_` | `{keyword, language}` | Top 10 avec mots et H2 par page, médianes |
| `POST /api/v1/sites/<id>/serp-analyze/` | session ou token `btb_` | `{keyword, language}` | Top 10 avec mots, headings, FAQ, vidéo, moyennes |
| `POST /api/v1/brief/` | session ou token `btb_` | `{keyword, language}` | Brief de contenu complet |
| `POST /api/trends/` | session du dashboard | `{keyword, language, timeframe}` | Courbe d'intérêt, requêtes connexes et montantes |
| `POST /api/community-questions/` | session du dashboard | `{keyword, language}` | Fils Reddit et Quora |

Détails sur l'authentification : [API](api.md).
