# Mode externe (site fait main)

Pour les développeurs qui veulent les articles **sur le domaine principal, en sous-dossier** (`tonsite.com/blog/...`) sans changer de stack. Trois façons de faire :

| Variante | Principe | Pour qui |
|---|---|---|
| **API** (la plus courante) | Gridar stocke les articles, ton frontend les lit via l'API REST | Next.js, React, Vite |
| **Base Postgres externe** | Gridar écrit les articles dans ta base, ton backend les lit | Backend Python ou autre qui lit Postgres |
| **Mode agent** | Un agent de code récupère les articles et les pose dans ton repo | Site statique ou repo que tu fais évoluer avec Claude Code ou un autre agent |

> Ce mode demande du code. Pour un sous-domaine sans rien toucher, voir [Mode hébergé](hosted.md).

## Variante API

### Architecture

```text
Visiteur → tonsite.com/blog/article-slug
            ↓ page rendue par TON frontend
Ton frontend → GET https://api.gridar.app/api/v1/sites/<id>/articles/<slug>/
            ↓ en-tête Authorization: Bearer btb_...
Gridar → JSON {slug, title, excerpt, content, cover_image, language, status, published_at, updated_at}
```

Ton frontend rend l'article avec ton layout, ta typo, ton header. Les pages vivent sur ton domaine.

**Le champ `content` est du Markdown.** Convertis-le en HTML (avec une bibliothèque Markdown) avant de l'injecter. Les extraits générés par Gridar l'injectent tel quel avec `dangerouslySetInnerHTML` : sans conversion, les `#` et `**` s'affichent en clair.

### 1. Crée le site

Sur `/sites`, clique **Blog clé-en-main** (ou **Ajouter un site**). Remplis :

- **Nom du site**
- **DATABASE_URL** : laisse vide
- **Domaine** : ton domaine (ex : `tonsite.com`). Le sitemap de Gridar s'en sert pour construire les URL `https://tonsite.com/blog/<slug>`

L'identifiant du site (`site_id`) se lit dans l'URL du dashboard (`/dashboard/<id>`) et sur la page d'onboarding.

### 2. Crée un token API

Sur `/sites`, lien **API** (ou `/account/api-keys`) → carte **Nouveau token** → donne un nom (ex : `site-prod`) → **Créer le token**. Copie-le tout de suite (il commence par `btb_`) : il ne sera plus affiché.

- Créer un token débloque la génération pour ce site : le bandeau passe à **Livraison non confirmée**, car Gridar ne peut pas vérifier que ton frontend affiche les articles.
- Utiliser le token exige un plan **Pro** ou **Agence**. Avec Essai ou Solo, l'API répond 403 "Accès API réservé aux plans Pro et Agence".
- Limite appliquée par le serveur : 30 requêtes par heure en Pro, 200 en Agence. La page des clés API affiche d'autres chiffres (60 et 600) ; ceux du serveur font foi.

### 3. Récupère le code

Sur `/sites`, lien **Mode externe (React/Next.js)**. La page "Onboarding mode externe" te guide :

1. **Site source** : clique ton site (son `site_id` s'affiche).
2. **Framework du frontend** : Next.js (App Router), Next.js (Pages Router), React + react-router-dom, ou Vite SPA (sans router).
3. **Crée un token API** : rappel de l'étape précédente et nom de la variable d'environnement.
4. Trois blocs de code, chacun avec un bouton **Copier** : **4a. Liste des articles**, **4b. Page article**, **4c. sitemap.xml + rss.xml**.
5. **Tester l'API directement** : une commande `curl` pour vérifier ton token avant de coder.

Un aperçu "Voilà à quoi ton blog ressemblera" reprend ton logo et tes couleurs.

### 4. Colle dans ton repo

| Framework | Liste | Article | Sitemap / RSS |
|---|---|---|---|
| Next.js App Router | `app/blog/page.tsx` | `app/blog/[slug]/page.tsx` | `app/sitemap.xml/route.ts` et `app/rss.xml/route.ts` (le bloc 4c contient les deux : sépare-les en deux fichiers) |
| Next.js Pages Router | `pages/blog/index.tsx` | `pages/blog/[slug].tsx` | `pages/sitemap.xml.ts` |
| React Router | `src/pages/BlogList.tsx` + routes `/blog` et `/blog/:slug` dans `App.tsx` | `src/pages/BlogPost.tsx` | Rewrite chez ton hébergeur |
| Vite SPA | `src/pages/Blog.tsx` | `src/pages/Article.tsx` | Rewrite chez ton hébergeur |

Les extraits Next.js mettent les réponses en cache 10 minutes (`revalidate: 600`).

### 5. Ajoute la variable d'environnement

```bash
# Next.js (fetch côté serveur)
BLOG_DASHBOARD_TOKEN=btb_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

# Vite / React Router (côté client, préfixe VITE_)
VITE_BLOG_DASHBOARD_TOKEN=btb_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

> **Attention** : un token côté client (Vite, React Router) est visible par tout visiteur. En production, préfère Next.js avec fetch côté serveur, ou un backend qui relaie l'API.

### 6. Expose sitemap et RSS sur ton domaine

Pour que Google trouve tes articles, `tonsite.com/sitemap.xml` doit renvoyer le sitemap de Gridar. Pour Next.js, le bloc 4c s'en charge. Sinon :

**Vercel** : dans `vercel.json`

```json
{
  "rewrites": [
    {
      "source": "/sitemap.xml",
      "destination": "https://api.gridar.app/api/sites/<id>/sitemap.xml"
    },
    {
      "source": "/rss.xml",
      "destination": "https://api.gridar.app/api/sites/<id>/rss.xml"
    }
  ]
}
```

**Netlify** : dans `_redirects`

```text
/sitemap.xml  https://api.gridar.app/api/sites/<id>/sitemap.xml  200
/rss.xml      https://api.gridar.app/api/sites/<id>/rss.xml      200
```

**Backend Python (Django, FastAPI) qui sert le frontend** : ajoute une route qui relaie ces deux endpoints.

Le sitemap liste les articles publiés aux URL `https://<Domaine>/blog/<slug>`. Soumets ensuite `tonsite.com/sitemap.xml` dans Google Search Console (Sitemaps → Add a new sitemap).

### 7. Génère, publie, vérifie

Gridar → **Générer un article**. L'article arrive en **brouillon** : les extraits ne lisent que les articles publiés (`?status=published`). Ouvre **Articles**, clique **Modifier**, puis **Publier**. Va ensuite sur `https://tonsite.com/blog/<slug>`.

### Endpoints utilisés

| Endpoint | Usage |
|---|---|
| `GET /api/v1/sites/<id>/articles/?status=published` | Liste des articles. Paramètres `language` et `limit` (50 par défaut, 200 au plus). Bearer requis |
| `GET /api/v1/sites/<id>/articles/<slug>/` | Un article avec son `content` en Markdown. Bearer requis |
| `GET /api/sites/<id>/sitemap.xml` | Sitemap des articles publiés. Public, cache 1 h |
| `GET /api/sites/<id>/rss.xml` | Flux RSS. Public, cache 1 h |

Les endpoints publics `GET /api/public/sites/<id>/posts/` et `GET /api/public/sites/<id>/posts/<slug>/` servent aussi les articles publiés, sans token. Détails : [API REST](../api.md).

## Variante base Postgres externe

Gridar écrit les articles dans **ta** base au lieu de la sienne. Ton backend les lit directement (ORM ou SQL), sans appel HTTP à Gridar au moment d'afficher une page.

1. Sur `/sites`, **Ajouter un site** (ou **Blog clé-en-main**) → colle ton URL dans **DATABASE_URL** (`postgresql://user:pwd@host:5432/dbname`).
2. Sur la carte du site, clique **Test** pour vérifier la connexion, puis **Init** pour créer les tables du blog dans ta base.
3. Génère : l'article est écrit en **brouillon** dans ta base, avec "Admin" comme auteur.

Limites :

- Le serveur de Gridar doit pouvoir joindre ta base depuis Internet.
- DATABASE_URL se renseigne à la création du site. Le champ n'apparaît pas dans les paramètres.
- Le bouton **Voir sur le site** n'existe pas pour ces sites : Gridar ne connaît pas l'URL publique de l'article.

## Variante mode agent

Pour un site que tu modifies avec un agent de code (Claude Code ou autre) : l'agent construit les pages dans ton repo, Gridar fournit le contenu.

1. **Paramètres → Général → Mode de livraison** → **Via un agent - le contenu est construit dans le repo du client** → **Sauvegarder**.
2. Génère tes articles. Ils restent en brouillon chez Gridar : rien n'est poussé vers un CMS, une base externe ni une URL Gridar. Ce réglage l'emporte sur tous les autres chemins.
3. L'agent lit la file avec l'outil MCP `gridar_pull_build_queue`, ou `GET /api/v1/sites/<id>/build-queue/?stack=nextjs` (valeurs : `nextjs`, `react`, `html`, `astro`, `generic`).
4. Une fois la page en ligne, l'agent la déclare avec `gridar_mark_page_built`, ou `POST /api/v1/sites/<id>/build-queue/mark-built/` avec `{kind, id, url}`.

La file contient trois types d'entrées :

| `kind` | Contenu | Ce que fait `mark-built` |
|---|---|---|
| `article` | Un article généré pas encore livré, avec son `content` (Markdown) à intégrer tel quel | Enregistre l'URL en ligne. L'article sort de la file |
| `article_brief` | Un mot-clé suivi d'intention informationnelle sans article, avec un `build_prompt` pour l'écrire | Enregistre l'URL comme page cible du mot-clé, suivie ensuite dans les positions |
| `landing` | Une opportunité stratégique (page commerciale ou locale) à construire, avec un `build_prompt` | Marque l'opportunité comme faite |

Chaque `mark-built` soumet l'URL à IndexNow (Bing, Yandex, Seznam, Naver ; pas Google). Pour que la soumission soit acceptée, ton site doit servir le fichier de clé à sa racine : récupère la clé avec l'outil MCP `gridar_indexnow_setup` ou `GET /api/v1/sites/<id>/indexnow/`, puis publie un fichier texte nommé `<clé>.txt` qui contient la clé.

Ces appels passent par un token API : plan **Pro** ou **Agence** requis. Voir [Intégrations](../integrations.md) pour brancher le MCP.

## Dépannage

| Symptôme | Cause | Solution |
|---|---|---|
| `401` "Token invalide ou révoqué." | Token révoqué ou mal copié | Crée un nouveau token sur `/account/api-keys` |
| `401` "Format de token invalide." | La valeur ne commence pas par `btb_` | Vérifie la variable d'environnement |
| `403` "Accès API réservé aux plans Pro et Agence..." | Plan Essai ou Solo | Passe en Pro ou Agence sur `/billing` |
| `429 Too Many Requests` | Limite horaire atteinte (30/h en Pro, 200/h en Agence) | Cache plus long côté frontend (`revalidate`), ou plan Agence |
| `409` avec `delivery_blocked` à la génération via l'API | Aucun chemin de livraison | Crée un token API, active le mode agent ou renseigne une base externe |
| L'article n'apparaît pas dans la liste | Il est encore en brouillon | **Articles** → **Modifier** → **Publier** |
| Le texte s'affiche avec des `#` et des `**` | `content` injecté sans conversion | Convertis le Markdown en HTML avant de l'afficher |
| `tonsite.com/sitemap.xml` renvoie 404 | Rewrite pas appliquée | Vérifie `vercel.json` ou `_redirects`, puis redéploie |
| Le sitemap contient des URL sans domaine ou avec le mauvais | Champ **Domaine** vide ou erroné | **Paramètres → Général → Domaine** |
