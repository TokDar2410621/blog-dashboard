# Articles multilingues + hreflang

Gridar gère trois langues : français, anglais, espagnol. Les versions d'un même article sont reliées par un identifiant commun, le `translation_group`. Ce lien sert au sélecteur de langue, au contrôle **Santé hreflang** et à l'API publique, qui expose les versions de chaque article à ton site.

## Activer les langues sur ton site

**Paramètres → Langues**

1. **Langues disponibles** : clique Français, English ou Español pour les activer. Si aucune n'est cochée, les trois sont autorisées.
2. **Langue par défaut** : la langue principale du site.

Les langues activées limitent le choix dans la page **Générer un article** et dans l'éditeur (**Paramètres → Publication → Langue**). Une génération dans une langue non activée est refusée.

La langue par défaut sert quand une requête API ou une landing ne précise pas de langue. Sur le blog hébergé, la page d'accueil et le sitemap ne listent que les articles de cette langue. Le formulaire de génération et l'éditeur, eux, démarrent sur le français.

## Workflow : article original puis traduction

### 1. Crée l'article original

Par la génération ou à la main. Choisis sa langue.

### 2. Traduis-le depuis l'éditeur

Ouvre l'article enregistré (**Articles → Modifier**), puis **Traduire → Traduire en EN** (ou FR, ES). Le menu propose les deux langues autres que celle de l'article. Il faut un titre et du contenu.

Gridar :

- traduit le titre, l'extrait et le contenu en gardant le Markdown (titres, listes, liens, images) et les blocs de code
- propose un slug dans la langue cible
- crée un nouvel article avec la même catégorie, les mêmes tags, la même couverture et le même `translation_group`
- relie l'article source au groupe s'il ne l'était pas
- t'amène dans l'éditeur de la traduction

La traduction reprend le **statut de l'article source**. Traduire un article publié publie donc la traduction tout de suite. Pour la relire avant qu'elle soit en ligne, traduis l'original pendant qu'il est encore en brouillon. Vérifie surtout les noms propres, les références culturelles et les liens internes : ils pointent encore vers les articles de la langue d'origine.

Dans la liste **Articles**, chaque article affiche ses langues disponibles (ex : FR/EN).

### 3. Ce que voit Google

Sur le **blog hébergé**, chaque article déclare sa langue dans son JSON-LD (`inLanguage`) et affiche en haut de page les autres langues publiées de son groupe. Le blog hébergé n'injecte pas de balises `<link rel="alternate" hreflang>` dans le `<head>`.

Sur un **site en mode externe**, ton frontend récupère les versions par l'API publique et écrit lui-même ses balises hreflang :

```bash
curl https://api.gridar.app/api/public/sites/<id>/posts/<slug>/translations/
```

Réponse : la langue courante, le `translation_group` et la liste des versions publiées (`slug`, `language`, `title`, `url`, `is_current`). Sur un site hébergé, le détail d'un article (`/api/public/sites/<id>/posts/<slug>/`) contient aussi `hreflang_alternates`.

## Santé hreflang

**Tableau de bord du site → carte Santé hreflang multi-langue** (ou `POST /api/hreflang-check/` avec `{site_id}`)

Gridar lit tes articles publiés et compare chaque `translation_group` aux langues activées sur le site :

- **Groupes**, **Complets**, **Incomplets**
- **Langues attendues**
- **Groupes incomplets (langues manquantes)** : chaque article avec les langues présentes et celles qui manquent
- le nombre d'articles publiés dans une seule langue, candidats à traduire

Avec `{site_id, translation_group}`, la réponse détaille un seul groupe. Le contrôle lit la base de Gridar : il ne visite pas tes pages et ne vérifie pas les balises hreflang de ton HTML. Il fonctionne pour les sites hébergés et en base externe ; sur WordPress, Shopify et Webflow, la carte affiche "Impossible de charger l'analyse hreflang".

## Selon le mode du site

| Mode | Liaison des traductions | Hreflang |
|---|---|---|
| Hébergé | Oui | Sélecteur de langue visible, `inLanguage` dans le JSON-LD, pas de balises hreflang dans le `<head>` |
| Base externe | Oui | À écrire par ton frontend, à partir de l'API publique |
| WordPress | Non : la traduction est créée comme un article séparé, sans langue ni groupe | Gridar n'en écrit pas : passe par l'outil multilingue de ton CMS |
| Shopify | Non, comme WordPress | Idem |
| Webflow | Non, comme WordPress | Idem |

Si ton CMS ne gère pas le multilingue, une option : un site Gridar par langue, chacun sur son domaine. Le nombre de sites dépend de ton plan, voir [Plans, crédits et quotas](plans-credits.md).

## Français du Québec ou de France

Gridar n'a pas de réglage FR-CA ou FR-FR. La génération écrit en français sans imposer de variante, et le JSON-LD du blog hébergé déclare `fr`. Pour un public québécois, passe l'article dans la carte **Lexique québécois (FR-CA)** de l'éditeur (onglet **SEO** → **Lisibilite**) : elle repère les termes de France et propose les équivalents. Voir [Éditeur](editor.md).

## Suivi des positions par langue

**Suivi des positions** : chaque mot-clé suivi porte une langue, et Gridar interroge un seul marché Google par langue :

| Langue du mot-clé | Recherche Google |
|---|---|
| Français | Canada, en français |
| Anglais | États-Unis, en anglais |
| Espagnol | Espagne, en espagnol |

Tu peux suivre le même mot-clé dans plusieurs langues. Tu ne peux pas choisir un autre pays pour une langue : pas de suivi France pour le français, ni Canada pour l'anglais.

## Traduction par l'API

Réservée aux plans Pro et Agence, et aux sites hébergés.

```bash
curl -X POST -H "Authorization: Bearer btb_xxx" \
  -H "Content-Type: application/json" \
  -d '{"target_language": "en"}' \
  https://api.gridar.app/api/v1/sites/12/articles/article-fr-original/generate-sister-article/
```

Réponse (201) : `slug`, `id`, `language`, `translation_group`, `status`, `title`.

Différences avec le bouton **Traduire** de l'éditeur :

- l'article est **adapté**, pas traduit mot à mot : idiomes, exemples culturels et références locales sont transposés, à longueur égale
- la traduction arrive toujours en **brouillon**
- Gridar refuse si une version dans cette langue existe déjà dans le groupe
- la traduction consomme **1 article du quota mensuel ou 1 crédit**
- le contrôle de livraison s'applique (erreur 409 si le site n'a aucun chemin de livraison)

Voir [API](api.md).

## Limites

- **Trois langues seulement** : français, anglais, espagnol.
- **Pas de génération simultanée** : tu génères l'original, puis tu traduis.
- **Pas de mise à jour automatique** : modifier l'original ne touche pas ses traductions. Relance une traduction si l'écart devient grand.
- **Pas de garde-fou de doublon dans l'éditeur** : rien n'empêche de créer deux versions de la même langue dans un groupe. Vérifie la liste **Articles** avant de traduire.
- **Liens internes non réécrits** : une traduction garde les liens de l'original.

## Use case : SEO bilingue au Québec

Pour une PME québécoise qui vise aussi un public anglophone :

- écris d'abord en français, la langue de ton marché principal
- traduis en anglais les articles qui performent déjà, repérés dans [Search Console](gsc.md)
- suis tes mots-clés dans les deux langues (le français sur Google Canada, l'anglais sur Google États-Unis)
- contrôle la carte **Santé hreflang** pour repérer les articles encore sans version anglaise
