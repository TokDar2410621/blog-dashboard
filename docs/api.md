# API REST publique

Pour automatiser la publication, l'audit ou le tracking depuis n8n, Zapier, Make, GitHub Actions, ou tes propres scripts.

> Disponible sur les plans **Pro** (30 req/h) et **Agence** (200 req/h). Pas accessible en Free ou Solo.

## Démarrage

### 1. Créer un token

Dashboard → Sidebar → **API** (ou directement `/account/api-keys`) → bouton **Créer un token**.

Donne-lui un nom descriptif (ex : `n8n-prod`, `zapier-marketing`). Le token complet (commence par `btb_`) **est affiché une seule fois** - copie-le immédiatement dans un password manager ou ton .env.

Si tu le perds : tu dois le révoquer et en créer un nouveau (pas de récupération possible).

### 2. Authentification

Toutes les requêtes prennent un header :

```
Authorization: Bearer btb_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

Il n'y a pas de session, pas de cookie. Stateless.

### 3. Première requête

```bash
curl -H "Authorization: Bearer btb_xxx" \
  https://api.gridar.app/api/v1/me/
```

Réponse :
```json
{
  "username": "darius",
  "email": "tokamdarius@gmail.com",
  "plan": "pro",
  "rate_limit_per_hour": 30,
  "usage": {
    "articles_this_month": 47,
    "articles_per_month_limit": 60,
    "month_key": "2026-05"
  }
}
```

## Endpoints

### `GET /api/v1/me/`

Sanity check : retourne ton plan + ta rate-limit + ton usage du mois.

### `GET /api/v1/sites/`

Liste tes sites actifs.

```json
{
  "results": [
    { "id": 12, "name": "Mon blog", "domain": "monsite.ca", "is_wordpress": true, ... }
  ]
}
```

### `GET /api/v1/sites/<id>/articles/`

Liste les articles d'un site. Query params optionnels : `?status=published&language=fr&limit=50`.

```json
{
  "results": [
    {
      "slug": "guide-crm-pme-2026",
      "title": "Comment choisir un CRM pour PME au Québec",
      "status": "published",
      "language": "fr",
      "published_at": "2026-05-04",
      "view_count": 1247
    },
    ...
  ]
}
```

### `GET /api/v1/sites/<id>/articles/<slug>/`

Détail d'un article avec son `content` complet (HTML).

### `POST /api/v1/sites/<id>/generate/`

Génère un article via IA. Body :

```json
{
  "topic": "Les meilleurs CRM pour PME québécoises en 2026",
  "type": "comparison",
  "length": "long",
  "language": "fr",
  "keywords": "crm pme quebec, crm bilingue, crm canadien"
}
```

Tous les champs sauf `topic` ou `title` sont optionnels. Type accepte : `news`, `tutorial`, `comparison`, `guide`, `review`, `story`, `local`. Length : `short`, `medium`, `long`.

Réponse synchrone (60-120 sec) :
```json
{
  "output": "[OK] Sujet: ... [OK] Audit: 92/100 [OK] Article publié",
  "post_count": 48
}
```

> Consomme 1 quota mensuel ou 1 crédit. Voir [Plans, crédits et quotas](plans-credits.md).

### `POST /api/v1/audit/`

Audite un contenu sans le publier.

```json
{
  "title": "Comment choisir un CRM",
  "excerpt": "...",
  "content": "<p>...</p>",
  "keyword": "crm pme québec",
  "language": "fr"
}
```

Réponse : `{ score: 87, suggestions: [...], cache_hit: false }`.

### `POST /api/v1/brief/`

Génère un brief de contenu.

```json
{
  "keyword": "meilleur crm pme québec",
  "language": "fr"
}
```

Réponse : `{ intent, outline: [...], entities: [...], faq: [...], eeat_signals: [...] }`.

### `GET /api/v1/sites/<id>/keywords/`

Liste les mots-clés trackés + dernière position connue.

### `POST /api/v1/sites/<id>/keywords/snapshot/`

Crawl SERP immédiat pour mettre à jour les positions. Compte dans ta rate-limit horaire.

### `GET /api/v1/sites/<id>/digest/weekly/`

Snapshot hebdomadaire du site (publications, audit moyen, mouvements de positions, alertes). Idéal pour piper dans Slack/email via cron.

## Endpoints publics (no auth)

Pour le SEO de ton site externe :

### `GET /api/sites/<id>/sitemap.xml`

Sitemap XML standard (Googlebot-friendly). Cache 1h CDN. À proxy depuis `tonsite.com/sitemap.xml`.

### `GET /api/sites/<id>/rss.xml`

Flux RSS 2.0 (50 derniers articles). Cache 1h.

## Rate limiting

Sliding window 1h, par utilisateur (pas par token - si tu as 5 tokens, ils partagent la même limite).

| Plan | Limite |
|---|---|
| Pro | 30 req/h |
| Agence | 200 req/h |
| Enterprise | sur mesure |

Headers de réponse :
```
X-RateLimit-Limit: 30
X-RateLimit-Remaining: 24
X-RateLimit-Reset: 1718230000
```

Quand tu dépasses → HTTP 429 + `Retry-After: <seconds>`.

## Codes d'erreur

| Code | Sens | Action |
|---|---|---|
| 401 | Token absent ou format invalide | Vérifie le header `Authorization: Bearer btb_...` |
| 403 | Token valide mais plan insuffisant (Free/Solo) | Upgrade vers Pro ou plus |
| 402 | Quota épuisé (articles ou crédits) | Acheter des crédits ou attendre le 1er du mois |
| 404 | Ressource inexistante (article, site, keyword pas à toi) | Vérifie l'`id` ou le slug |
| 429 | Rate limit horaire dépassé | Attends, ou cache plus côté client, ou upgrade Agence |
| 502 | Problème côté CMS distant (WP/Shopify/Webflow injoignable) | Réessaie + vérifie credentials |

## Exemples concrets

### Cron quotidien : snapshot positions

```bash
#!/bin/bash
curl -X POST -H "Authorization: Bearer $BLOG_DASHBOARD_TOKEN" \
  https://api.gridar.app/api/v1/sites/12/keywords/snapshot/
```

### n8n : générer un article quand on ajoute une row Airtable

Trigger Airtable → HTTP Request node :
- Method : POST
- URL : `https://api.gridar.app/api/v1/sites/12/generate/`
- Auth : Bearer `{{ $env.BLOG_DASHBOARD_TOKEN }}`
- Body : `{"topic": "{{ $json.topic }}", "type": "guide", "language": "fr"}`

### GitHub Action : digest hebdo dans Slack

```yaml
- name: Fetch weekly digest
  run: |
    DIGEST=$(curl -H "Authorization: Bearer ${{ secrets.BLOG_DASHBOARD_TOKEN }}" \
      https://api.gridar.app/api/v1/sites/12/digest/weekly/)
    curl -X POST -H 'Content-type: application/json' \
      --data "{\"text\":\"$DIGEST\"}" ${{ secrets.SLACK_WEBHOOK }}
```

## Versioning

Cette API est versionnée par préfixe (`/api/v1/`). Promesses :
- **v1 endpoints existants** : signature stable. Pas de breaking change sans bump majeur (`/api/v2/`).
- **Ajouts non-breaking** : nouveaux champs dans les réponses, nouveaux endpoints, nouveaux query params optionnels - peuvent arriver sans préavis.

Si tu nous écris à propos d'un endpoint manquant, on peut le prioriser.
