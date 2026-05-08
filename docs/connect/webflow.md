# Connecter Webflow

Pour les sites Webflow ayant une CMS Collection pour les articles. On publie directement dans la collection via l'API CMS v2 - articles visibles immédiatement sur ton site live.

## Pré-requis

- Compte Webflow avec un Site auquel tu as accès
- Une CMS Collection pour les articles (le template "Blog" Webflow en crée une par défaut nommée "Blog Posts")
- Un champ Rich Text dans la collection pour le corps de l'article (sans ça, on n'a nulle part où mettre le contenu généré)

## Étapes

### 1. Génère un Site API Token Webflow

1. Webflow → ouvre le projet (Designer ou Editor)
2. Top-left menu (icône W) → **Project settings**
3. Onglet **Apps & Integrations**
4. Section **API access** → **Generate API token**
5. Nom : `Blog Dashboard`
6. Scopes : coche au minimum `CMS: read and write`
7. **Generate** → copie le token (long string)

### 2. Connecte dans Blog Dashboard

Sites → **Connecter Webflow**. 3 étapes :

**Étape 1 - Token**
Colle le token Webflow → "Vérifier le token". On valide en listant tes Webflow sites.

**Étape 2 - Site**
Liste de tes sites Webflow auxquels le token a accès. Clique celui où tu veux publier les articles.

**Étape 3 - Collection**
Liste de toutes les CMS Collections de ce site. Chaque collection a un badge :
- 🟢 **Blog** - détecté comme blog standard (a un champ Rich Text), prêt à recevoir des articles
- 🟠 **Pas de Rich Text** - la collection n'a pas de champ Rich Text, on ne peut pas publier dedans

Choisis une collection 🟢. Le mapping de champs est auto-détecté :
- `name` → titre
- `slug` → URL slug
- `post-body` (ou premier RichText trouvé) → corps
- `post-summary` (ou premier PlainText) → excerpt
- `main-image` (ou premier ImageRef) → cover

Clique **Connecter**.

### 3. Comportement après publication

Article généré → `POST /v2/collections/<id>/items/live` (avec `live=true` pour publier sur le site staging immédiatement). URL finale :
- `tonsite.com/blog/article-slug` (selon le slug de ta collection)
- Webflow rend l'article via la **page template** que tu as configurée dans Designer (généralement `Blog Posts/Blog Post Template`)

Le contenu Markdown est converti en HTML côté nous puis envoyé tel quel dans le champ Rich Text. Webflow rend ce HTML dans le template.

## Champs Webflow utilisés (mapping automatique)

| Notre champ | Webflow slug standard | Type Webflow attendu |
|---|---|---|
| Titre | `name` | PlainText (toujours présent) |
| Slug | `slug` | PlainText (toujours présent) |
| Corps | `post-body` (puis fallback RichText) | RichText - **REQUIS** |
| Excerpt | `post-summary` (puis fallback PlainText) | PlainText (optionnel) |
| Cover | `main-image` (puis fallback ImageRef) | ImageRef (optionnel) |

Si ta collection a des slugs différents (ex : `bodyContent` au lieu de `post-body`), notre auto-detect utilise le **type** comme fallback. Si rien ne marche, le mapping peut être édité dans le code via le champ JSON `webflow_field_map` du Site (Site Settings → Advanced).

## Limites

- **Pas de tags / catégories** : les collections varient trop entre projets. Pour une logique de catégories, utilise un champ Reference dans Webflow et édite manuellement après publication.
- **Pas de scheduling Webflow-natif** : on publie en `live=true` directement. Si tu veux planifier, génère en draft (statut `draft`) puis publie via Webflow Designer.
- **API rate limit** : Webflow limite à 60 req/min/token. À ton échelle (quelques articles/jour), c'est large.

## Dépannage

| Erreur | Cause | Fix |
|---|---|---|
| "Token Webflow invalide ou expiré" | Token révoqué ou mal copié | Re-générer dans Webflow Project settings |
| "Aucun site accessible" | Token sans CMS read/write | Re-créer le token avec scope CMS read+write |
| "Cette collection n'a pas de champ Rich Text" | Collection vide ou mauvais template | Ouvre Designer → Collection → Add field → Rich Text → choisis cette collection au connect |
| Article publié mais 404 | Page template manquante | Webflow Designer → Pages → CMS Pages → assure-toi qu'il y a un Template pour la collection. Re-publish le site |
