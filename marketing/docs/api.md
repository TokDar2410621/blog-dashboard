# API REST publique

Pour automatiser la génération, l'audit ou le suivi depuis n8n, Zapier, Make, GitHub Actions ou tes propres scripts. C'est la même API que le [connecteur MCP](integrations.md) utilise.

> Accès par jeton réservé aux plans **Pro** (30 req/h) et **Agence** (200 req/h). En Essai et en Solo, chaque appel par jeton répond 403.

## Démarrage

### 1. Créer un token

Page Sites → bouton **API** (ou directement `/account/api-keys`) → carte **Nouveau token** → donne-lui un nom (ex : `n8n-prod`, `zapier-marketing`) → **Créer le token**.

Le token complet commence par `btb_` et **s'affiche une seule fois**. Copie-le tout de suite dans un gestionnaire de mots de passe ou ton `.env`. Gridar ne garde que son empreinte SHA-256 et ses 12 premiers caractères, pour te le montrer dans la liste.

Si tu le perds : révoque-le et crées-en un nouveau. Aucune récupération possible.

La création d'un token ne vérifie pas ton plan. Son utilisation, oui : un token créé en Essai ou en Solo répond 403 tant que tu n'es pas en Pro ou en Agence.

### 2. Authentification

Chaque requête porte cet en-tête :

```text
Authorization: Bearer btb_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

Le token passe toujours dans l'en-tête, jamais dans l'URL.

### 3. Première requête

```bash
curl -H "Authorization: Bearer btb_xxx" \
  https://api.gridar.app/api/v1/me/
```

Réponse :

```json
{
  "username": "ton-compte",
  "email": "toi@exemple.com",
  "plan": "pro",
  "rate_limit_per_hour": 30,
  "usage": {
    "articles_this_month": 47,
    "articles_per_month_limit": 60,
    "month_key": "2026-10"
  }
}
```

## Endpoints

URL de base : `https://api.gridar.app/api/v1`. Dans les chemins ci-dessous, `<id>` est l'identifiant numérique d'un de tes sites (voir `GET /sites/`). Un site qui n'est pas à toi, ou qui est inactif, répond 404.

### Compte et sites

| Méthode | Chemin | Rôle |
|---|---|---|
| GET | `/me/` | Ton plan, ta limite horaire, ton usage du mois |
| GET | `/sites/` | Tes sites actifs |
| GET | `/sites/<id>/detail/` | Configuration complète d'un site (langues, base de connaissances, concurrents, GSC, autopilote, profil auteur, mode de livraison) |
| PATCH | `/sites/<id>/update/` | Modifie `name`, `description`, `knowledge_base`, `competitors`, `default_language`, `author_bio`, `author_credentials`, `public_blog_domain`, `business_model`, `primary_cta_text`, `primary_cta_url`. Les autres champs sont ignorés |
| GET | `/sites/<id>/seo-score/` | Score SEO composite du site (0 à 100) + actions à mener |

### Articles

| Méthode | Chemin | Rôle |
|---|---|---|
| GET | `/sites/<id>/articles/` | Liste les articles. Paramètres : `status`, `language`, `limit` (50 par défaut, 200 au maximum) |
| GET | `/sites/<id>/articles/<slug>/` | Un article avec son contenu complet |
| POST | `/sites/<id>/generate/` | Génère un article par IA. **Consomme 1 article du quota** |
| POST | `/sites/<id>/articles/manual/` | Crée un article écrit à la main (sites hébergés seulement, aucun quota) |
| PATCH | `/sites/<id>/articles/<slug>/manual/` | Modifie `title`, `excerpt`, `content`, `status`, `cover_image`, `slug`, `author`. Tous les modes de site |
| DELETE | `/sites/<id>/articles/<slug>/manual/` | Supprime l'article. Sur WordPress, Shopify et Webflow, la suppression est définitive (pas de corbeille) |
| POST | `/sites/<id>/articles/<slug>/generate-sister-article/` | Traduit l'article dans `target_language` (`fr`, `en`, `es`). Sites hébergés seulement. **Consomme 1 article du quota** |
| GET | `/sites/<id>/articles/<slug>/ai-overview-readiness/` | Score 0 à 100 de l'aptitude de l'article à être repris par les réponses IA |

### Audit et contenu

| Méthode | Chemin | Rôle |
|---|---|---|
| POST | `/audit/` | Audite un contenu sans le publier |
| POST | `/brief/` | Brief de contenu pour un mot-clé |
| GET | `/sites/<id>/audit-all/` | Audit de tous les articles publiés du site |
| POST | `/readability/` | Lisibilité d'un texte (`content`, `language`) |
| POST | `/plagiarism/` | Détection de contenu IA et de plagiat via Originality.ai (`content`, 50 caractères minimum) |
| POST | `/hreflang-check/` | Cohérence des groupes de traduction d'un site (`site_id` requis, `translation_group` optionnel) |
| GET | `/sites/<id>/cannibalization/` | Paires d'articles qui visent la même intention |
| POST | `/sites/<id>/link-suggestions/` | Liens internes à ajouter dans un texte (`title` ou `content` requis, `current_slug`, `language`) |
| GET | `/sites/<id>/broken-links/` | Liens sortants en erreur |
| GET | `/sites/<id>/content-decay/` | Articles qui perdent des impressions dans GSC (`?days=30`) |
| POST | `/check-renderability/` | Dit si une page est rendue côté serveur ou si c'est une coquille JavaScript (`url`) |
| POST | `/page-speed/` | PageSpeed Insights sur une URL (`url`, `strategy` : `mobile` ou `desktop`) |

### Mots-clés et SERP

| Méthode | Chemin | Rôle |
|---|---|---|
| GET | `/sites/<id>/keywords/` | Mots-clés suivis + dernière position connue |
| POST | `/sites/<id>/keywords/track/` | Suit un nouveau mot-clé (`keyword`, `language`, `target_url`). Compte dans ta limite de mots-clés |
| DELETE | `/sites/<id>/keywords/<pk>/untrack/` | Arrête le suivi. L'historique des positions est conservé |
| POST | `/sites/<id>/keywords/snapshot/` | Relève les positions maintenant |
| POST | `/sites/<id>/suggest-keywords/` | Suggestions de mots-clés pour le site |
| POST | `/sites/<id>/suggest-competitors/` | Concurrents SEO probables du site |
| POST | `/keyword-research/` | Requêtes liées à un mot-clé de départ (`seed_keyword`, `language`). Pas de volume ni de difficulté |
| POST | `/paa/` | Questions "Autres questions posées" de Google (`keyword`, `language`) |
| POST | `/classify-intent/` | Intention de recherche d'un mot-clé (`keyword`, `site_id` optionnel) |
| POST | `/competitors/` | Analyse du top 10 Google pour un mot-clé (`keyword`, `language`) |
| POST | `/sites/<id>/serp-analyze/` | Métriques par URL du top 10 (mots, titres, FAQ, vidéo) + moyennes (`keyword`, `language`) |
| POST | `/link-opportunities/` | Sites candidats pour des liens entrants (`keyword`, `language`) |

### Stratégie, landings et clusters

| Méthode | Chemin | Rôle |
|---|---|---|
| POST | `/sites/<id>/keyword-strategy/` | Propose une structure de pages pour un mot-clé (`keyword`, `language`) |
| POST | `/sites/<id>/keyword-strategy/<strategy_id>/approve/` | Approuve la stratégie : les landings sont générées en brouillon, les articles restent à générer un par un |
| POST | `/sites/<id>/landings/manual/` | Crée une landing écrite à la main (sites hébergés seulement, aucun quota) |
| POST | `/sites/<id>/landings/generate/` | Génère une landing par IA à partir d'un `keyword` (sites hébergés seulement). **Consomme 1 article du quota** |
| GET | `/sites/<id>/landings/<landing_id>/prompt/` | Prompt prêt à coller dans ton outil IA pour intégrer la landing (`?stack=`) |
| POST | `/sites/<id>/link-pages/` | Ajoute un lien d'une page vers une autre (`source_slug`, `target_slug`, `anchor_text`). Sites hébergés seulement |
| GET | `/sites/<id>/clusters/` | Carte des topic clusters du site |
| POST | `/sites/<id>/clusters/build/` | Prompts de construction d'un cluster complet, maillage inclus (`pillar_keyword`, `spokes`) |
| GET | `/sites/<id>/strategic-opportunities/` | Opportunités stratégiques en cache (`?include_dismissed=1`, `?include_archived=1`) |
| POST | `/sites/<id>/strategic-opportunities/refresh/` | Recalcule les opportunités (`max_keywords` : 8 par défaut, 20 au maximum) |
| POST | `/sites/<id>/strategic-opportunities/<op_id>/<action>/` | `approve`, `dismiss` ou `restore` |
| GET | `/sites/<id>/strategic-opportunities/<op_id>/prompt/` | Prompt prêt à coller pour créer la page (`?stack=`) |

Valeurs de `stack` : `nextjs`, `react`, `html`, `astro`, `wordpress`, `webflow`, `generic`.

### Livraison par un agent (build-queue)

Pour un site construit à la main (Next.js, React...) que Gridar ne peut pas publier lui-même. Dans les réglages du site, choisis le mode de livraison **Via un agent**.

| Méthode | Chemin | Rôle |
|---|---|---|
| GET | `/sites/<id>/build-queue/` | Pages à créer dans ton dépôt : briefs de landings, articles générés à intégrer tels quels, briefs d'articles (`?stack=`) |
| POST | `/sites/<id>/build-queue/mark-built/` | Signale qu'une page est en ligne (`kind`, `id`, `url`) |

### Google Search Console et indexation

| Méthode | Chemin | Rôle |
|---|---|---|
| GET | `/sites/<id>/gsc-queries/` | Requêtes GSC d'un article (`?slug=` requis, `days` : 28 par défaut, 90 au maximum) |
| GET | `/sites/<id>/index-coverage/` | Pages indexées ou non par Google (`?max_inspect=25`, de 0 à 100) |
| POST | `/sites/<id>/sitemap/submit/` | Resoumet le sitemap à Google Search Console (`sitemap_url` optionnel) |
| GET | `/sites/<id>/indexnow/` | Clé IndexNow du site + fichier à héberger |
| POST | `/sites/<id>/indexnow/submit/` | Soumet des URLs à IndexNow : Bing, Yandex, Seznam, Naver. Pas Google (`urls` optionnel, sinon celles du sitemap) |

### Visibilité IA

| Méthode | Chemin | Rôle |
|---|---|---|
| GET | `/sites/<id>/ai-visibility/summary/` | Score agrégé de visibilité IA du site |
| GET | `/sites/<id>/ai-visibility/prompts/` | Prompts suivis |
| POST | `/sites/<id>/ai-visibility/prompts/` | Ajoute un prompt à suivre (`prompt`, `target_intent`, `language`) |
| POST | `/sites/<id>/ai-visibility/suggest/` | Suggestions de prompts à suivre (`count` : 6 par défaut, de 3 à 12) |
| POST | `/sites/<id>/ai-visibility/run/` | Lance une série de vérifications (`prompt_id` optionnel) |

> `POST /ai-visibility/run/` n'interroge encore aucun moteur IA : les résultats sont simulés et la réponse le dit (`"mocked": true`). Le score de `summary/` se calcule sur ces résultats.

### Autopilote

| Méthode | Chemin | Rôle |
|---|---|---|
| GET | `/sites/<id>/autopilot/` | Configuration et état de l'autopilote |
| POST | `/sites/<id>/autopilot/` | Modifie `enabled`, `weekly_count`, `auto_publish`, `mode`, `min_refresh_interval_days` |
| POST | `/sites/<id>/autopilot/run/` | Lance un cycle maintenant |

### Mémoire du site

| Méthode | Chemin | Rôle |
|---|---|---|
| GET | `/sites/<id>/memories/` | Morceaux de mémoire du site (articles, base de connaissances, notes) |
| POST | `/sites/<id>/memories/` | Ajoute une note (`content`, `title`, `kind`) |
| DELETE | `/sites/<id>/memories/<pk>/` | Supprime un morceau de mémoire |
| POST | `/sites/<id>/memories/rebuild/` | Recalcule toute la mémoire du site |

### Preuve de résultats et rapports

| Méthode | Chemin | Rôle |
|---|---|---|
| GET | `/sites/<id>/proof/summary/` | Impressions et clics gagnés d'après GSC + articles qui progressent le plus |
| GET | `/sites/<id>/proof/attribution/` | Relevés par article à J+30, J+60 et J+90 (`?post=<pk>` pour un seul article) |
| GET | `/sites/<id>/proof/share/` | État de la page de preuve publique |
| POST | `/sites/<id>/proof/share/` | Active la page de preuve publique (`rotate: true` pour changer de lien) |
| DELETE | `/sites/<id>/proof/share/` | Désactive la page de preuve publique |
| GET | `/sites/<id>/digest/weekly/` | Bilan de la semaine |

## Détail des endpoints principaux

### `POST /api/v1/sites/<id>/generate/`

Body :

```json
{
  "topic": "Les meilleurs CRM pour PME québécoises en 2026",
  "type": "comparison",
  "length": "long",
  "language": "fr",
  "keywords": "crm pme quebec, crm bilingue, crm canadien"
}
```

| Champ | Valeurs | Par défaut |
|---|---|---|
| `topic` | Sujet libre | aucun |
| `title` | Titre imposé | aucun |
| `type` | `news`, `tutorial`, `comparison`, `guide`, `review`, `story`, `local` | `guide` |
| `length` | `short`, `medium`, `long` | `medium` |
| `language` | `fr`, `en`, `es` (parmi les langues du site) | `fr` |
| `keywords` | Mots-clés séparés par des virgules | aucun |
| `brief` | Objet brief renvoyé par `/brief/` | aucun |

Sans `topic` ni `title`, Gridar choisit le sujet lui-même.

La requête est synchrone : la réponse arrive quand l'article est généré.

```json
{
  "output": "...",
  "post_count": 1
}
```

`output` contient le journal de la génération, avec le slug de l'article. `post_count` vaut 1 quand l'article est enregistré. Le journal finit par "Article publie" même quand l'article part en brouillon : fie-toi à la liste ci-dessous.

Où va l'article :

- **WordPress, Shopify, Webflow** : publié directement sur le CMS.
- **Site hébergé ou à base externe** : enregistré en brouillon. Publie-le depuis le tableau de bord ou avec `PATCH /sites/<id>/articles/<slug>/manual/` et `"status": "published"`.
- **Mode de livraison "Via un agent"** : mis en attente dans la build-queue.

La génération est refusée si :

- le site n'a pas de **modèle d'affaires** ou de **bio d'auteur** : HTTP 422 avec `missing_fields` ;
- aucun chemin de livraison n'existe vers le site : HTTP 409 avec `"code": "delivery_blocked"` ;
- le sujet est trop proche d'un article existant : HTTP 400 avec le titre de l'article en conflit ;
- ton quota et tes crédits sont épuisés : HTTP 402 avec `"quota_exceeded": true`.

> Consomme 1 article du quota mensuel ou 1 crédit. Voir [Plans, crédits et quotas](plans-credits.md).

### `POST /api/v1/audit/`

Audite un contenu sans le publier. `title` et `content` sont requis.

```json
{
  "title": "Comment choisir un CRM",
  "excerpt": "...",
  "content": "<p>...</p>",
  "keyword": "crm pme québec",
  "language": "fr"
}
```

Réponse : `score` (0 à 100), `verdict`, `strengths`, `weaknesses`, `actions`, le rapport de sourçage `sourcing` (chiffres sans source), `sourcing_gate` (`ok`, `warning` ou `hard_stop`) et `cache_hit`. Un même contenu est mis en cache 1 h.

### `POST /api/v1/brief/`

```json
{
  "keyword": "meilleur crm pme québec",
  "language": "fr"
}
```

Réponse : `search_intent`, `intent_explanation`, `recommended_titles`, `outline`, `word_count_target`, `faq`, `entities`, `schemas_suggested`, `eeat_signals`. Mis en cache 1 h.

### `GET /api/v1/sites/<id>/articles/`

```json
{
  "results": [
    {
      "slug": "guide-crm-pme-2026",
      "title": "Comment choisir un CRM pour PME au Québec",
      "excerpt": "...",
      "status": "published",
      "language": "fr",
      "published_at": "2026-05-04",
      "view_count": 1247
    }
  ]
}
```

Cette forme vaut pour les sites hébergés et les sites à base externe. Sur un site WordPress, Shopify ou Webflow, la liste vient du CMS et suit la forme de son connecteur.

### `GET /api/v1/sites/<id>/digest/weekly/`

Bilan des 7 derniers jours : articles publiés dans la semaine, articles les plus vus, plus fortes hausses et baisses de positions, compteurs de redirections. Disponible pour les sites hébergés et les sites à base externe. Un site WordPress, Shopify ou Webflow répond 400.

## Endpoints publics (sans auth)

Pour le SEO de ton site :

### `GET https://api.gridar.app/api/sites/<id>/sitemap.xml`

Sitemap XML des articles publiés. Cache 1 h. À servir depuis `tonsite.com/sitemap.xml`.

### `GET https://api.gridar.app/api/sites/<id>/rss.xml`

Flux RSS 2.0 des 50 derniers articles. Cache 1 h.

Un site inactif répond 404 sur ces deux URLs.

## Rate limiting

Fenêtre glissante d'une heure, **par utilisateur** : si tu as 5 tokens, ils partagent la même limite.

| Plan | Limite |
|---|---|
| Essai / Solo | aucun accès (403) |
| Pro | 30 req/h |
| Agence | 200 req/h |

Quand tu dépasses → HTTP 429 avec l'en-tête `Retry-After` (en secondes).

L'API ne renvoie pas d'en-têtes `X-RateLimit-*`. Ta limite se lit dans `rate_limit_per_hour` de `GET /me/`.

## Codes d'erreur

| Code | Sens | Action |
|---|---|---|
| 400 | Paramètre manquant ou invalide, sujet trop proche d'un article existant | Lis le champ `error` |
| 401 | Token absent, mal formé ou révoqué | Vérifie l'en-tête `Authorization: Bearer btb_...` |
| 402 | Quota d'articles et crédits épuisés (`quota_exceeded`) ou limite de mots-clés atteinte (`limit_exceeded`) | Achète des crédits, attends le 1er du mois ou libère une place |
| 403 | Token valide mais plan Essai ou Solo | Passe en Pro ou en Agence |
| 404 | Site, article ou mot-clé introuvable, ou qui n'est pas à toi | Vérifie l'`id` ou le slug |
| 409 | Aucun chemin de livraison vers le site (`delivery_blocked`), ou slug déjà pris | Vérifie la connexion du site ou change le slug |
| 422 | Modèle d'affaires ou bio d'auteur manquant (`missing_fields`) | Remplis-les dans les réglages du site |
| 429 | Limite horaire dépassée | Attends le délai de `Retry-After` |
| 502 | Le CMS distant (WordPress, Shopify, Webflow) ou un service externe n'a pas répondu | Réessaie, puis vérifie la connexion du site |

## Exemples concrets

### Cron quotidien : relevé des positions

```bash
#!/bin/bash
# GRIDAR_TOKEN contient ton jeton btb_xxx
curl -X POST -H "Authorization: Bearer $GRIDAR_TOKEN" \
  https://api.gridar.app/api/v1/sites/12/keywords/snapshot/
```

### n8n : générer un article quand on ajoute une ligne Airtable

Trigger Airtable → node **HTTP Request** :

- Method : POST
- URL : `https://api.gridar.app/api/v1/sites/12/generate/`
- En-tête : `Authorization` = `Bearer btb_xxx` (range le jeton dans un credential n8n de type Header Auth)
- Body (JSON) : `{"topic": "{{ $json.topic }}", "type": "guide", "language": "fr"}`

### GitHub Action : bilan hebdo dans Slack

```yaml
- name: Bilan hebdo Gridar
  run: |
    DIGEST=$(curl -s -H "Authorization: Bearer ${{ secrets.GRIDAR_TOKEN }}" \
      https://api.gridar.app/api/v1/sites/12/digest/weekly/)
    jq -n --arg t "$DIGEST" '{text: $t}' | \
      curl -X POST -H 'Content-type: application/json' --data @- ${{ secrets.SLACK_WEBHOOK }}
```

## Versioning

L'API est versionnée par préfixe : `/api/v1/`.

Il te manque un endpoint ? Ouvre une [issue GitHub](https://github.com/TokDar2410621/blog-dashboard/issues).
