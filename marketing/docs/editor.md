# Éditeur d'articles (écriture manuelle)

L'éditeur sert à relire et corriger un article généré, ou à en écrire un à la main. Tu y accèdes depuis :

- **Articles → Nouvel article** : la fenêtre **Choisir un template** s'ouvre
- **Articles → menu d'un article → Modifier**
- les URL directes `/dashboard/<id>/articles/nouveau` et `/dashboard/<id>/articles/<slug>`

La fenêtre **Choisir un template** propose trois onglets :

- **Contenu** : **Article vierge**, ou un squelette Markdown (Actualité, Tutoriel, Comparaison, Guide, Review, Récit personnel)
- **Visuel** : Hero, Minimal, Sidebar, Magazine. Ces gabarits insèrent un marqueur de mise en page en tête du contenu ; le blog hébergé ne l'applique pas pour l'instant.
- **IA** : Actu rapide, Tuto approfondi, Comparatif, Guide ultime, Récit perso, Annuaire local. Chacun ouvre la page [Générer un article](generate-article.md) avec le type, la longueur et la méthode de recherche préréglés.

## Vue d'ensemble

En haut de l'éditeur :

- **Générer avec IA** : remplit l'éditeur avec un article généré (voir plus bas)
- **Traduire** (article déjà enregistré) : crée la version d'une autre langue, voir [Traduction](translation.md)
- **Brouillon** : enregistre en brouillon
- **Publier** : enregistre et publie

Il n'y a pas de sauvegarde automatique. Clique **Brouillon** ou **Publier** avant de quitter la page, sinon tes modifications sont perdues.

Trois vues se partagent l'écran : **Éditeur**, **SEO**, **Paramètres**.

### Vue Éditeur

Trois panneaux redimensionnables :

- **Gauche** : titre, extrait (méta description), puis la zone Markdown avec sa barre d'outils : Gras, Italique, Titre H2, Titre H3, Lien, Image, Code, Citation, Liste. Glisse-dépose ou colle une image dans la zone : elle est uploadée et insérée.
- **Centre** : **Aperçu en direct** (couverture, titre, extrait, contenu). Clique une image de l'aperçu pour la remplacer.
- **Droite** : **Content Score** de 0 à 100 et ses sous-scores : Mots-clés (25 %), Structure (20 %), Lisibilité (20 %), OQLF (FR-CA) (15 %), E-E-A-T (10 %), Originalité (10 %). Dessous, deux onglets : **Termes** (usage de tes termes cibles dans le texte) et **Term Map**.

Sur mobile, les boutons **Éditeur**, **Aperçu en direct** et **Score** alternent entre les panneaux.

Le Content Score se calcule dans ton navigateur, à partir d'heuristiques, et peut différer du score de la vue SEO. Le **mot-clé principal est le premier tag** de l'article ; les tags suivants (jusqu'à 10 au total) servent de termes secondaires. Sans tags, le score n'a pas de mot-clé à mesurer.

L'onglet **Term Map** n'affiche pas encore de données concurrentes réelles : seule la colonne **Toi** vient de ton texte, les autres colonnes sont simulées. Fie-toi à l'onglet **Termes**.

### Vue SEO

Trois onglets : **Audit**, **Lisibilite**, **Apercu Google**.

**Audit** :

- **Score SEO** de 0 à 100 à partir de contrôles sur ton texte : longueur du titre (50 à 60 caractères), méta description (120 à 160), nombre de mots (1 000 et plus = bon, 600 et plus = à améliorer), mot-clé principal dans le titre, l'introduction et les H2 (ses variantes proches comptent), maillage interne (2 liens internes ou plus), structure (2 H2 ou plus), images et texte alternatif, image de couverture, slug (60 caractères maximum). **Corriger avec IA** traite les contrôles en échec.
- **Core Web Vitals** et **Cannibalisation**.
- **Audit SEO par IA** : **Lancer l'audit** donne un score, un verdict, les **Points forts**, les **Points faibles** (bouton **Corriger** sur chacun), les **Actions à faire** (bouton **Appliquer**) et **Tout corriger en une fois**. L'audit lit les 5 000 premiers caractères. Il repère les chiffres cités sans source et ne les compte jamais comme un point fort.
- **Backlinks**, **Suggestions IA**, **Analyse de la concurrence**, **Recherche de mots-clés**.
- **Suggestions de liens internes** : **Suggerer des liens** propose une ancre, l'article cible, la phrase où l'insérer et la raison. **Copier** copie le lien en Markdown, à coller toi-même.
- **Schema.org JSON-LD** : **Generer le schema** détecte une FAQ ou un pas-à-pas (FAQPage, HowTo), sinon produit un BlogPosting. **Copier** copie la balise `<script>` à coller dans le `<head>` de l'article.
- **Search Console (vraie perf)** : apparaît dès que l'article a un slug. Ses chiffres viennent de ta Search Console, qui doit être connectée (voir [Search Console](gsc.md)).

Les corrections IA (**Corriger avec IA**, **Corriger**, **Appliquer**, **Tout corriger en une fois**) remplacent le titre, l'extrait ou le contenu dans l'éditeur. Rien n'est enregistré tant que tu ne cliques pas **Brouillon** ou **Publier**.

**Lisibilite** :

- **Lisibilité** : score Flesch (adaptation Kandel et Moles pour le français, formule anglaise standard pour l'anglais ; l'espagnol utilise la formule française) et indice ARI, avec un niveau de Très facile à Très difficile. Recalculé pendant que tu écris.
- **Lexique québécois (FR-CA)** : repère les termes de France et propose l'équivalent québécois. Exemples de la liste : shopping → magasinage, week-end → fin de semaine, parking → stationnement, email → courriel, smartphone → téléphone intelligent. La liste compte plus de 50 termes et ne lit pas le contexte (ex : "chat" l'animal) : juge chaque suggestion.
- **Originalité + Détection IA** : **Analyser** envoie le texte (50 caractères minimum) à Originality.ai et affiche le pourcentage de texte détecté comme IA, le pourcentage de plagiat et les sources trouvées. Si le module n'est pas activé, la carte affiche **Module non configuré**.

**Apercu Google** : rendu de ton titre, slug, description et couverture dans Google, Facebook et Twitter.

Détails de chaque outil : [Outils SEO](seo-tools.md).

### Vue Paramètres

- **Publication** : **Statut** (Brouillon, Publié, Planifié), **Langue** (langues activées sur le site), **Date de publication** (si Planifié), **Catégorie** (catégories existantes du site), **En vedette**.
- **Slug** : pour un nouvel article, l'interrupteur **Auto** le dérive du titre. Modifier le slug à la main coupe l'automatisme. Un article existant garde son slug tant que tu ne le changes pas.
- **Tags** : séparés par des virgules. **Générer** les propose à partir du titre et du contenu.
- **Image de couverture** : URL directe, ou recherche **Pexels**, **Google Images**, **Générer (IA)**. Voir [Images](images.md).
- Compteur de l'extrait : **Extrait: N/160 car.**

## Générer avec IA dans l'éditeur

Le bouton **Générer avec IA** ouvre une fenêtre :

| Champ | Effet |
|---|---|
| **Sujet** | Sujet de l'article. Sans sujet, le titre de l'éditeur sert de sujet. L'un des deux est obligatoire. |
| **URLs de contexte** | **Ajouter une URL** pour en mettre plusieurs. Gridar lit jusqu'à 5 pages et en garde les 3 000 premiers caractères de texte chacune. |
| **Type** | Actualité, Tutoriel, Guide, Comparatif, Review, Story, Local |
| **Longueur** | Court, Moyen, Long |
| **Mots-clés SEO** | Liste séparée par des virgules |

**Générer l'article** remplit le titre (s'il est vide), l'extrait, le contenu, les tags, la couverture et, pour un nouvel article, le slug. Rien n'est enregistré avant **Brouillon** ou **Publier**. Le moteur est celui de la page [Générer un article](generate-article.md), avec recherche Serper et dans la langue de l'article : mêmes contrôles de livraison et d'anti-cannibalisation, mêmes limites.

Un article généré ici avec la mémoire du site affiche, une fois enregistré, **Article IA** et deux pouces dans l'en-tête. Pouce levé : les extraits de mémoire utilisés remontent dans les prochaines générations. Pouce baissé : ils descendent.

## Workflow recommandé

### Cas 1 - Réviser un article généré

1. **Articles** → menu de l'article → **Modifier**
2. Lis-le en entier. Vérifie en priorité :
   - les chiffres et les anecdotes à la première personne : le modèle peut les inventer
   - la catégorie et les tags, tirés de listes fixes (voir [Générer un article](generate-article.md))
   - les droits des images venues de Google Images
   - le ton, par rapport à ta marque
3. Mets ton mot-clé principal en **premier tag**
4. Vue **SEO** → **Lancer l'audit** et traite les points faibles
5. **Publier**

### Cas 2 - Écrire de zéro

1. **Articles** → **Nouvel article** → **Article vierge** ou un squelette
2. Tape le titre : le slug se remplit tout seul (modifiable dans **Paramètres**)
3. Choisis la langue dans **Paramètres → Publication**
4. Écris en Markdown
5. Ajoute tes tags, le premier étant ton mot-clé principal
6. Vue **SEO** → audit, puis **Brouillon** ou **Publier**

### Cas 3 - Importer du contenu existant

Pas d'import par l'interface. Deux options :

- **Copier-coller** : le texte collé arrive brut dans la zone Markdown. Remets les titres, listes et liens en Markdown.
- **Par l'API** (site hébergé seulement) : `POST https://api.gridar.app/api/v1/sites/<id>/articles/manual/` avec `{title, content}` au minimum, `slug` et `status` en option (brouillon par défaut). Voir [API](api.md).

À l'ouverture d'un article existant stocké en HTML, l'éditeur le convertit en Markdown.

## Champs

| Champ | Requis | Note |
|---|---|---|
| Titre | Oui | 200 caractères maximum. Pour le SEO, vise 50 à 60. |
| Contenu | Oui | Markdown |
| Extrait | Oui sur un site hébergé ou en base externe | Méta description, 120 à 160 caractères |
| Slug | Non | Dérivé du titre s'il est vide |
| Langue | Non | Français par défaut |
| Statut | Non | Brouillon, Publié ou Planifié |
| Catégorie | Non | Une seule par article |
| Tags | Non | Le premier sert de mot-clé principal à l'audit et au Content Score |
| Image de couverture | Non | Image en haut de l'article et image Open Graph sur le blog hébergé |
| En vedette | Non | Marque l'article comme mis en avant |

L'auteur et le temps de lecture ne se règlent pas dans l'éditeur. Sur un site hébergé ou en base externe, un article écrit à la main reçoit un temps de lecture par défaut de 5 minutes ; un article généré reçoit son nombre de mots divisé par 200.

## Brouillon, Planifié, Publié

- **Brouillon** : non affiché sur le blog public.
- **Planifié** : choisis la **Date de publication**. Sur un site en base externe, une tâche planifiée vérifie toutes les 15 minutes et passe en Publié les articles dont l'heure est passée. Sur un site hébergé, aucune tâche ne publie un article Planifié : publie-le à la main le jour venu.
- **Publié** : visible publiquement.

Si tu changes le slug d'un article, Gridar enregistre une redirection 301 de l'ancien slug vers le nouveau, quel que soit le statut. Elle apparaît dans [Redirections 301](seo-tools.md). Le blog hébergé et les sites qui lisent l'API l'appliquent ; WordPress, Shopify et Webflow ne la reçoivent pas.

## Markdown et rendu

Tu écris en Markdown : titres `#` `##` `###`, gras, italique, listes, liens, images, blocs de code, citations. Le rendu final dépend du mode du site :

| Mode | Ce qui est envoyé |
|---|---|
| Hébergé | Le Markdown, rendu par le blog hébergé. Il gère titres, gras, italique, code, citations, listes à puces, liens et images. Les tableaux et les listes numérotées ne sont pas rendus. |
| Base externe | Le Markdown, ou du HTML si ton site est configuré en format HTML (tableaux et blocs de code convertis) |
| WordPress, Shopify, Webflow | Le Markdown tel quel, sans conversion |

L'aperçu en direct de l'éditeur ne rend pas non plus les tableaux.

## Insertion d'images

Le bouton **Image** de la barre d'outils ouvre **Insérer une image** : **Pexels**, **Upload** ou **URL**. Le champ **Texte alternatif** se remplit avec la description Pexels ou ta recherche ; le bouton **IA** propose un texte alternatif à partir de l'image, du titre et du mot-clé principal. **Insérer dans l'article** place l'image au curseur.

Détails, formats et limites : [Images](images.md).

## Limites

- **Pas de sauvegarde automatique** ni d'historique de versions. Une fois enregistré, l'ancien contenu n'est pas récupérable.
- **Pas d'édition à plusieurs** : si deux personnes enregistrent le même article, le dernier enregistrement écrase l'autre.
- **Corrections IA sur articles longs** : les corrections ne lisent que le début de l'article (environ les 3 000 premiers caractères). Quand elles réécrivent le contenu, la fin de l'article peut disparaître. Relis toute la page avant d'enregistrer.
- **WordPress, Shopify, Webflow** : l'éditeur envoie le Markdown sans le convertir en HTML. N'édite pas dans Gridar un article déjà publié sur ces CMS : à l'ouverture, son HTML devient du Markdown, et l'enregistrement renvoie ce Markdown brut au CMS.
- **Pas d'import** WordPress XML ni d'archive Markdown. Passe par l'API, article par article.

## Dépannage

| Problème | Cause | Action |
|---|---|---|
| L'article ne s'enregistre pas | Session expirée ou champ requis vide (titre, contenu, extrait) | Remplis les champs requis. Recharge la page et reconnecte-toi si besoin. |
| Modifications perdues | Page quittée sans **Brouillon** ni **Publier** | Enregistre avant de quitter : il n'y a pas de sauvegarde automatique |
| Le Content Score ne bouge pas avec le mot-clé | Aucun tag, ou mot-clé placé en second | Mets le mot-clé principal en premier tag |
| La fin de l'article a disparu après une correction IA | La correction n'a lu que le début du texte | Ne l'enregistre pas : recharge la page pour retrouver la dernière version enregistrée |
| "Erreur upload image" | Fichier de plus de 5 Mo ou format non accepté | Compresse l'image, ou convertis-la en JPEG, PNG, GIF ou WebP |
| **Module non configuré** sur Originalité + Détection IA | Le service de détection n'est pas activé | Signale-le au support |
