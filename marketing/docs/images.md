# Gestion des images

Quatre façons de mettre une image dans un article : recherche Pexels, recherche Google Images, génération par IA (couverture seulement) et upload. Le texte alternatif peut être proposé par l'IA, à la demande. Les fichiers que tu uploades et les images que tu génères vont dans ta bibliothèque **Images**.

## Bibliothèque d'images

**Barre latérale → Images**

La bibliothèque contient les images uploadées et les images générées par IA. Elle appartient à ton compte : tu y retrouves les mêmes images depuis chacun de tes sites. Elle affiche les 500 plus récentes.

- zone d'upload : glisse-dépose ou **parcourez**, plusieurs fichiers à la fois
- **Rechercher une image...** : filtre par nom de fichier
- pour chaque image : aperçu, nom de fichier, bouton **Copier URL** (l'adresse à coller dans un article ou une page)

La bibliothèque n'a pas de suppression, pas de filtre par source, pas de texte alternatif et ne montre pas les articles qui utilisent une image. Les photos choisies sur Pexels ou Google Images n'y figurent pas : Gridar ne les copie pas (voir plus bas).

## Où ajouter une image

| Endroit | Sources |
|---|---|
| Éditeur → **Paramètres** → **Image de couverture** | URL, **Pexels**, **Google Images**, **Générer (IA)** |
| Éditeur → barre d'outils → **Image** (fenêtre **Insérer une image**) | **Pexels**, **Upload**, **URL** |
| Éditeur → glisser-déposer ou coller dans la zone Markdown | Upload direct à l'endroit du curseur |
| Bibliothèque **Images** | Upload, puis **Copier URL** |

Dans l'**Aperçu en direct** de l'éditeur, clique une image pour la remplacer : **Insérer une image** s'ouvre avec une recherche Pexels sur son texte alternatif.

## 1. Pexels

Recherche dans la banque de photos Pexels, 15 résultats par recherche, avec le nom du photographe. Disponible sans réglage, pour la couverture et dans le corps de l'article.

Gridar insère l'adresse de la photo chez Pexels : l'image reste hébergée par Pexels et n'est pas copiée chez Gridar. Vérifie que la licence Pexels couvre ton usage.

## 2. Google Images

Onglet **Google Images** de l'image de couverture : 20 résultats Google Images, avec le site source.

- Plus de choix que Pexels.
- **Attention aux droits** : ces images appartiennent aux sites qui les publient. Vérifie la licence de chaque image avant un usage commercial.
- Comme pour Pexels, Gridar insère l'adresse d'origine : si le site source retire l'image, elle disparaît de ton article.

## 3. Génération par IA

Onglet **Générer (IA)** de l'image de couverture :

1. **Décrivez l'image souhaitée...**
2. Lance la génération : l'aperçu s'affiche
3. **Utiliser cette image** l'applique en couverture

Gridar ajoute à ta description des consignes fixes : image de couverture de blog de qualité, style professionnel et moderne, sans texte, lettres, filigrane ni typographie. Le format est fixe (16:9, une image PNG). Il n'y a pas de choix de style ni de proportions. L'image générée rejoint ta bibliothèque avec une adresse permanente.

Si la génération renvoie une erreur, prends une photo Pexels, une image Google ou un upload.

## 4. Upload

Glisse-dépose dans l'éditeur ou dans la bibliothèque, colle une image dans la zone Markdown, ou passe par l'onglet **Upload** d'**Insérer une image**.

- Formats acceptés : JPEG, PNG, GIF, WebP
- Taille maximale : 5 Mo par image
- Le fichier est stocké tel quel par Gridar, sans compression ni redimensionnement
- Adresse permanente de la forme `/api/images/<uuid>/`, servie avec un cache navigateur long

Une image uploadée est publique : toute personne qui a son adresse peut l'afficher.

## Texte alternatif (alt)

Dans **Insérer une image**, le champ **Texte alternatif** :

- se remplit avec la description Pexels ou, à défaut, ta recherche
- pour un upload, reprend le nom du fichier ; pour une URL, vaut "image"
- laissé vide, il devient "image", que l'audit SEO compte comme générique : remplace-le
- bouton **IA** : un modèle de vision regarde l'image et propose un texte alternatif de moins de 125 caractères, dans la langue de l'article, en tenant compte du titre et du mot-clé principal (le premier tag) quand il s'intègre sans forcer. Il ajoute une description d'une phrase sous le champ.

La suggestion IA se déclenche seulement quand tu cliques **IA** : rien n'est automatique. Une image glissée-déposée ou collée dans la zone Markdown prend elle aussi le nom du fichier comme texte alternatif. L'image de couverture n'a pas de champ de texte alternatif.

## Images des articles générés

Quand Gridar génère un article :

- **Couverture** : une photo Unsplash liée au sujet ; à défaut, une image générée par IA via un service externe.
- **Images du corps** : photos Unsplash ou images Google trouvées pendant la recherche. Leur texte alternatif reprend la description demandée ou le titre de l'image Google.

Ces images sont liées à leur adresse d'origine, pas copiées. Vérifie les droits des images Google avant publication.

Selon le mode du site, la couverture part avec l'article sur Shopify et Webflow. WordPress ne la reçoit pas : ajoute l'image mise en avant dans WordPress.

## Image Open Graph (partages sociaux)

L'image qui apparaît quand ton article est partagé sur Facebook, X, LinkedIn ou Slack.

- **Par article** : l'**Image de couverture**. Sur le blog hébergé, elle devient l'image Open Graph de la page de l'article.
- **Par défaut** : **Paramètres → Branding → Image Open Graph par défaut**. Format recommandé : 1200×630. Sur le blog hébergé, elle sert aux pages du blog qui ne déclarent pas leur propre image, comme la page d'accueil.

Sur le blog hébergé, une page d'article sans couverture ne déclare pas d'image Open Graph : mets une couverture sur chaque article. Sur les autres modes, c'est ton site ou ton CMS qui écrit les balises Open Graph.

## Images dans l'audit SEO

Éditeur → vue **SEO** → **Audit** :

- **Images & alt-text** : nombre d'images, images sans alt, alts génériques ("image", "photo", moins de 5 caractères), alts en double, alts de plus de 125 caractères
- **Image de couverture** : présente ou manquante

L'audit signale. Il ne compresse pas, ne redimensionne pas et ne réécrit pas les alts : corrige-les toi-même ou avec le bouton **IA** d'**Insérer une image**.

## Endpoints API

Pour l'automatisation, sur `https://api.gridar.app` :

| Endpoint | Entrée | Usage |
|---|---|---|
| `POST /api/upload-image/` | multipart, champ `image` | Upload, renvoie `url` |
| `GET /api/sites/<id>/images/` | | Liste la bibliothèque (500 plus récentes) |
| `POST /api/sites/<id>/images/upload/` | multipart, champ `image` | Upload dans la bibliothèque |
| `GET /api/pexels/search/?query=...` | `page`, `per_page` (30 maximum) | Recherche Pexels |
| `GET /api/serper/images/?query=...` | | Recherche Google Images (20 résultats) |
| `POST /api/generate-image/` | JSON `{prompt}` | Génère une image 16:9, renvoie `image` (base64), `mime_type`, `image_url` |
| `GET /api/images/<uuid>/` | | Sert une image stockée (public) |
| `POST /api/image-suggest/` | JSON `{image_url, article_title, keyword, language}` | Renvoie `alt_text`, `filename_slug`, `description` |

Ces routes demandent une session connectée au tableau de bord (JWT), sauf `GET /api/images/<uuid>/` qui est public. La clé API `btb_` de l'[API v1](api.md) n'y donne pas accès.

## Limites

- Pas d'éditeur d'image intégré (recadrage, filtres, texte sur image). Prépare tes images avant l'upload.
- Pas de compression ni de redimensionnement automatique : optimise tes fichiers avant l'upload.
- Pas de suppression d'image depuis la bibliothèque.
- Pas de bibliothèque de gabarits ni de mockups.
- Pas de filigrane automatique.

## Dépannage

| Erreur | Cause | Action |
|---|---|---|
| "Type de fichier non supporte (JPEG, PNG, GIF, WebP uniquement)" | Format refusé (SVG, HEIC...) | Convertis en JPEG, PNG ou WebP |
| "Fichier trop volumineux (max 5 Mo)" | Image de plus de 5 Mo | Compresse-la (TinyPNG, Squoosh) |
| "Limite de requetes Pexels atteinte, reessayez plus tard" | Trop de recherches Pexels en peu de temps | Attends quelques minutes |
| "PEXELS_API_KEY non configuree" ou "SERPER_API_KEY non configuree" | Service de recherche non configuré côté Gridar | Signale-le au support |
| "Impossible de telecharger l'image" (bouton **IA**) | L'adresse de l'image ne répond pas ou bloque Gridar | Vérifie l'URL, ou écris le texte alternatif toi-même |
| Erreur de génération d'image ou quota épuisé | Le service de génération ne répond pas | Réessaie plus tard, ou utilise une autre source |
| L'image n'apparaît pas au partage social | Article sans image de couverture | Ajoute une couverture (sur le blog hébergé, l'image par défaut ne s'applique pas aux articles) |
