# public-blog — frontend public générique

App Next.js 14 (App Router) qui sert le blog public d'un site géré par
blog-dashboard. Une seule app pour TOUS les clients : la résolution se
fait au runtime via le header `Host`.

## Comment ça marche

1. Le visiteur arrive sur `blog.restaurant.ca` (ou `restofoo.blog-quebec.ca`).
2. Next.js lit le `Host` de la requête.
3. `getCurrentSite()` (`src/lib/site-context.ts`) appelle l'API du dashboard :
   `GET /api/public/site-by-domain/?domain=blog.restaurant.ca`.
4. Le dashboard retourne le `Site` (id, name, theme, EEAT, etc.).
5. Pages rendues avec ce site : home liste les articles, `/slug` rend l'article.

## Variables d'environnement

| Variable | Défaut | Rôle |
|---|---|---|
| `NEXT_PUBLIC_API_BASE` | `https://blog-dashboard-production-6480.up.railway.app/api` | URL du backend |
| `NEXT_PUBLIC_SITE_ID` | (non défini) | Forcer un site_id pour test mono-tenant local |

## Local dev

```bash
cd public-blog
npm install
NEXT_PUBLIC_SITE_ID=3 npm run dev
# Ouvre http://localhost:3001 — affiche le blog du site #3 (TokamDarius)
```

Sans `NEXT_PUBLIC_SITE_ID`, l'app fait un lookup par `Host`. En local le host
est `localhost:3001`, donc aucun site ne match et l'app affiche la page
"Site non configuré".

## Déploiement Vercel

1. Créer un nouveau projet Vercel pointant sur ce dossier (`public-blog/`).
2. Pas de variable d'env nécessaire si le backend est en prod.
3. Configurer les domaines clients : pour chaque `blog.client.ca`, ajouter le
   domaine au projet Vercel. Le client ajoute un CNAME chez son registrar.
4. La route catch-all par Host fait le reste.

## Routes

- `/` — liste des articles
- `/[slug]` — article (gère 301 si redirect dans le dashboard)
- `/sitemap.xml` — sitemap dynamique pour Google
- `/rss.xml` — flux RSS
- `/robots.txt` — pointe vers le sitemap

## SEO inclus

- Meta tags `<title>`, `<description>`, OG, Twitter Card.
- Schema.org BlogPosting JSON-LD par article.
- Schema.org Person JSON-LD du site (auteur EEAT) dans le layout.
- hreflang via le composant translations switcher (visible).
- Sitemap + RSS + robots.txt automatiques.
