# Mode externe (API-pull)

Pour les développeurs qui veulent les articles **sur le domaine principal en subfolder** (`tonsite.com/blog/...`) sans changer leur stack. Articles stockés chez nous, **lus par ton frontend** via notre API REST publique.

> ⚠️ Ce mode demande du code (2-3 routes React + 1 rewrite hébergeur). Pour les marketers/non-codeurs qui veulent un sous-domaine sans rien toucher, voir [Mode hébergé](hosted.md).

## Architecture

```
Visiteur → tonsite.com/blog/article-slug
            ↓ rendu par TON frontend React
            ↓
Ton React → fetch GET https://api.blog-dashboard.ca/api/v1/sites/<id>/articles/<slug>/
            ↓ avec Bearer token
            ↓
Notre Postgres → JSON {title, content_html, ...}
            ↑
Notre dashboard → publie article (write API)
```

Ton frontend rend l'HTML avec **ton** layout, **ta** typo, **ton** header - l'utilisateur voit ton site, le SEO bonifie 100 % ton domaine.

## Étapes

### 1. Crée un site placeholder

Sites → **Blog clé-en-main** (oui même CTA) → laisse Database URL vide → crée. C'est juste pour avoir un `site_id` à utiliser dans l'API.

Note bien le `site_id` (visible dans l'URL `/dashboard/<id>/`).

### 2. Génère un token API

Sidebar → API → **Créer un token**. Nom : `mon-site-prod`. Copie-le immédiatement (commence par `btb_`) - il ne sera plus affiché.

> Le token est lié au PLAN. L'API REST exige Pro ou Agence : Free et Solo n'y ont pas accès.

### 3. Génère les routes React

Dashboard → **Mode externe (React/Next.js)** (en bas de la page Sites).

Tu choisis :
- **Site** : celui que tu viens de créer
- **Framework** : Next.js App Router / Next.js Pages Router / React Router / Vite SPA

On te génère 3 blocs de code prêts à coller :
- **BlogList** - liste des articles publiés
- **BlogPost** - page article individuel
- **sitemap.xml + rss.xml** - proxy vers nos endpoints (essentiel pour le SEO)

### 4. Colle dans ton repo

Pour chaque bloc, clique "Copier" → colle dans le fichier indiqué :

| Framework | BlogList | BlogPost | Sitemap |
|---|---|---|---|
| Next.js App Router | `app/blog/page.tsx` | `app/blog/[slug]/page.tsx` | `app/sitemap.xml/route.ts` |
| Next.js Pages | `pages/blog/index.tsx` | `pages/blog/[slug].tsx` | `pages/sitemap.xml.ts` |
| React Router | `src/pages/BlogList.tsx` + register route | `src/pages/BlogPost.tsx` + `:slug` route | rewrite côté hébergeur |
| Vite SPA | `src/pages/Blog.tsx` | `src/pages/Article.tsx` | rewrite côté hébergeur |

### 5. Ajoute la variable d'environnement

Stocke ton token API dans une env var :

```
# Next.js (server-side fetch)
BLOG_DASHBOARD_TOKEN=btb_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Vite (client-side, expose via VITE_)
VITE_BLOG_DASHBOARD_TOKEN=btb_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

> **Attention** : un token côté client (Vite SPA) est exposé. Pour la production, préfère Next.js avec server-side fetch ou un BFF qui proxy l'API.

### 6. Configure les rewrites (sitemap + rss)

Pour que Google indexe ton blog, il faut que `tonsite.com/sitemap.xml` retourne le sitemap.

**Si tu es sur Vercel** : ajoute dans `vercel.json` :
```json
{
  "rewrites": [
    {
      "source": "/sitemap.xml",
      "destination": "https://api.blog-dashboard.ca/api/sites/<id>/sitemap.xml"
    },
    {
      "source": "/rss.xml",
      "destination": "https://api.blog-dashboard.ca/api/sites/<id>/rss.xml"
    }
  ]
}
```

**Si tu es sur Netlify** : `_redirects` :
```
/sitemap.xml  https://api.blog-dashboard.ca/api/sites/<id>/sitemap.xml  200
/rss.xml      https://api.blog-dashboard.ca/api/sites/<id>/rss.xml      200
```

**Si tu as un backend Python (Django/FastAPI) qui sert le frontend** : ajoute une route qui proxy nos endpoints (cache 1h recommandé).

### 7. Génère un article et teste

Blog Dashboard → Générer un article → publie. Va sur `https://tonsite.com/blog/<slug>` → ton article est rendu avec ton layout.

## Variantes

### Mode "DB partagée"

Si tu préfères ne PAS appeler notre API à chaque page (latence, dépendance externe), tu peux nous donner un `DATABASE_URL` Postgres dédié :
- On écrit les articles dans **TA** base
- Ton backend Python lit la même base directement (avec ton ORM)
- Aucun appel HTTP externe au runtime

Site Settings → champ `database_url` → colle ton URL. Schema initialisé via `python manage.py init_db --site=<id>`.

C'est plus rapide mais plus lourd à brancher (un script de migration côté nous + notre worker doit pouvoir atteindre ta base).

## Endpoints API utilisés

| Endpoint | Usage |
|---|---|
| `GET /api/v1/sites/<id>/articles/?status=published` | BlogList - liste paginée des articles publiés |
| `GET /api/v1/sites/<id>/articles/<slug>/` | BlogPost - détail d'un article avec `content_html` |
| `GET /api/sites/<id>/sitemap.xml` | Sitemap (no auth, public, 1h cache) |
| `GET /api/sites/<id>/rss.xml` | RSS feed (no auth, public, 1h cache) |

Détails complets : [API REST](../api.md).

## Dépannage

| Erreur | Cause | Fix |
|---|---|---|
| `401 Unauthorized` sur `/articles/` | Token Free ou Solo | Upgrade vers Pro (60 req/h) ou Agence (200 req/h) |
| `403 Forbidden` | Token révoqué | Re-générer dans `/account/api-keys` |
| `429 Too Many Requests` | Rate limit dépassé | Cache plus agressif côté toi (Next ISR `revalidate: 600`), ou upgrade Agence |
| Sitemap retourne 404 sur `tonsite.com/sitemap.xml` | Rewrite non appliquée | Vérifie `vercel.json`/`_redirects`, redéploie |
