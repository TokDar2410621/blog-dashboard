# Connecter Shopify

Pour les boutiques Shopify (tous plans). Articles publiés directement dans `taboutique.com/blogs/news/article-slug` via l'Admin API.

## Pré-requis

- Boutique Shopify active
- Accès admin (`Manage apps`)
- Au moins un blog créé (Shopify en crée un par défaut intitulé "News")

## Étapes

### 1. Crée une Custom App dans Shopify

1. Shopify Admin → Settings → **Apps and sales channels**
2. **Develop apps** (en haut à droite, peut nécessiter d'activer le développement d'app - clique le toggle si demandé)
3. **Create an app** → nomme-la `Blog Dashboard`
4. Onglet **Configuration** → **Admin API integration** → **Configure**
5. Cherche et coche le scope `write_content` (et/ou `read_content`)
6. **Save**
7. Onglet **API credentials** → **Install app**
8. Une fenêtre montre le **Admin API access token** (commence par `shpat_`)
9. **Copie-le immédiatement** - il ne sera plus affiché

### 2. Connecte dans Blog Dashboard

Sites → **Connecter Shopify**. Tu remplis :

- **Domaine** : `monstore.myshopify.com` (le sous-domaine technique, pas le custom domain). Si tu colles `https://monstore.myshopify.com/admin`, on extrait le bon hostname automatiquement.
- **Token** : le `shpat_xxx` collé tel quel.

Étape 2 du dialog : on liste tes blogs Shopify (généralement "News"). Choisis lequel reçoit les articles.

### 3. Ce qu'on fait sous le capot

1. `GET admin/api/.../shop.json` → valide le token + récupère le shop name + custom_domain
2. `GET admin/api/.../blogs.json` → liste les blogs disponibles
3. Tu choisis un blog → on stocke `shopify_blog_id`
4. Scan branding sur ton custom domain (ou `monstore.myshopify.com` si pas de custom)
5. Création de la `Site` row, redirection

### 4. Comportement après publication

Article généré via Blog Dashboard → `POST admin/api/.../blogs/<id>/articles.json`. URL finale :
- Si tu as un custom domain : `taboutique.com/blogs/news/article-slug`
- Sinon : `monstore.myshopify.com/blogs/news/article-slug`

L'article respecte le template Liquid de ta boutique - même typo, mêmes header/footer que ton storefront.

## Champs Shopify utilisés

| Notre champ | Shopify | Note |
|---|---|---|
| Titre | `title` | |
| Slug | `handle` | URL-safe, on slug-ifie si besoin |
| Contenu | `body_html` | Markdown converti en HTML |
| Excerpt | `summary_html` | Apparaît dans listings |
| Auteur | `author` | Hérite du `default_author` du Site |
| Tags | `tags` | CSV |
| Cover | `image.src` | URL externe (Pexels par défaut) |
| Statut | `published_at` | Set = published, null = draft |

## Limites

- **Pas de catégories** : Shopify a `tags` uniquement (pas de hiérarchie). Notre topic clusters reste calculé en interne mais ne mappe pas à Shopify.
- **Suppression définitive** : Shopify ne fait pas de soft-delete. Si tu supprimes un article via Blog Dashboard, c'est irréversible côté Shopify.
- **Custom domain** : on lit le custom domain depuis l'API Shopify et l'utilise pour le branding scan. Si Shopify ne le reporte pas (rare), on utilise `myshopify.com`.

## Dépannage

| Erreur | Cause | Fix |
|---|---|---|
| "Token invalide ou révoqué" | `shpat_` mal copié ou app désinstallée | Re-générer le token côté Shopify, re-coller |
| "Domaine Shopify introuvable" | Faute de frappe ou store fermé | Confirme l'orthographe `monstore.myshopify.com` |
| "Token sans permission write_content" | Scope manquant | Custom App → Configuration → Admin API → coche `write_content` → Save → re-installer |
| "Cette boutique n'a aucun blog" | Tu as supprimé tous les blogs | Shopify Admin → Online Store → Blog posts → Manage blogs → New blog |
