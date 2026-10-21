# Connecter Webflow

Pour les sites Webflow qui ont une CMS Collection pour les articles. Gridar écrit dans la collection via l'API CMS v2 et publie l'item sur ton site en ligne.

## Pré-requis

- Un compte Webflow avec accès au site
- Une CMS Collection pour les articles (le template "Blog" de Webflow en crée une, "Blog Posts")
- Un champ **Rich Text** dans cette collection pour le corps de l'article. Sans lui, Gridar n'a nulle part où mettre le contenu et refuse la connexion

## Étapes

### 1. Génère un Site API Token Webflow

1. Webflow → ton projet → **Project Settings**
2. Onglet **Apps & Integrations** → section **API access**
3. **Generate API token**, avec au minimum les scopes CMS en lecture et écriture
4. Copie le token

### 2. Connecte dans Gridar

Sur `/sites`, clique **Webflow**. Le dialog "Connecter ton site Webflow" compte trois étapes.

**Étape 1 : token**
Colle le token dans **Site API Token**, puis clique **Vérifier le token**. Gridar liste les sites Webflow accessibles avec ce token.

**Étape 2 : site**
Clique le site où publier. Chaque ligne montre son domaine custom, ou `<nom>.webflow.io` à défaut.

**Étape 3 : collection**
L'encart **Branding détecté** montre le branding lu sur le domaine du site. Décoche **Appliquer** pour le régler plus tard.

Gridar liste les CMS Collections du site, avec un badge :

- **Blog** : un champ de corps a été trouvé, la collection peut recevoir des articles.
- **Pas de Rich Text** : aucun champ de corps trouvé, la connexion sera refusée.

La première collection marquée **Blog** est présélectionnée. Sous chaque collection **Blog**, une ligne "Mapping détecté" indique les champs retenus pour le titre, le corps et l'image. Clique **Connecter** : "Site Webflow connecté", confettis, puis le dashboard du site.

## Mapping des champs (automatique)

| Champ Gridar | Slugs Webflow essayés, dans l'ordre | Sinon |
|---|---|---|
| Titre | `name` | (toujours présent) |
| Slug | `slug` | (toujours présent) |
| Corps | `post-body`, `body`, `content`, `article-body`, `rich-text` | Premier champ Rich Text. **Requis** |
| Extrait | `post-summary`, `summary`, `excerpt`, `description` | Premier champ texte simple (hors `name` et `slug`) |
| Couverture | `main-image`, `thumbnail-image`, `cover-image`, `featured-image`, `image` | Premier champ Image |

Le mapping ne se modifie pas depuis le dashboard. Si un champ est mal choisi, renomme ou ajoute le champ dans Webflow, puis refais la connexion.

## Ce qui se passe à la génération

Gridar envoie un `POST` à `/v2/collections/<id>/items/live` avec `isDraft: false` : l'item est **publié tout de suite** sur ton site en ligne, y compris quand il vient de l'autopilote. Le contenu Markdown est converti en HTML et placé dans le champ Rich Text. Webflow l'affiche via la page template de la collection (souvent `Blog Posts Template`).

URL finale : selon le chemin de ta collection (ex : `tonsite.com/blog/article-slug`).

Pour relire avant publication, coche **Aperçu seulement (ne pas publier)** dans le formulaire de génération : rien n'est envoyé à Webflow.

## Limites

- **Pas de tags ni de catégories** : les collections varient trop d'un projet à l'autre. Pour des catégories, utilise un champ Reference dans Webflow et remplis-le après publication.
- **Pas de brouillon à la génération** : l'article part en ligne directement. Pas de planification Webflow non plus.
- **Titre en double possible** : le contenu envoyé commence par le titre en H1. Si ton template affiche déjà le champ `name` en titre, il apparaît deux fois.
- **Une collection par site Gridar** : connecter une autre collection du même site Webflow crée un second site dans Gridar (et occupe une place de ton plan).

## Changer le token

Refais la connexion depuis `/sites` avec le même site et la même collection : Gridar met à jour le token sur le site existant.

## Dépannage

| Message | Cause | Solution |
|---|---|---|
| "Token Webflow invalide ou expiré." | Token révoqué ou mal copié | Génère un nouveau token dans Project Settings |
| "Token Webflow trop court - colle bien le Site Token." | Copie tronquée | Recopie le token complet |
| "Ce token n'a accès à aucun site." | Le token ne voit aucun site | Recrée le token depuis le bon projet, avec les scopes CMS |
| "Cette collection n'a pas de champ de type RichText pour le corps de l'article..." | Aucun champ Rich Text | Designer → ta collection → ajoute un champ Rich Text, puis reconnecte |
| "Aucune collection trouvée." | Le site n'a pas de CMS Collection | Designer → CMS → crée une collection |
| "Limite de sites atteinte (x/y)..." | Ton plan est plein | Supprime un site ou change de plan sur `/billing` |
| Article publié mais 404 | Pas de page template pour la collection | Designer → Pages → CMS Collection Pages : crée le template, puis republie le site |
