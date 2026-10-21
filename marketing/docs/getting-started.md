# Démarrage rapide

Du compte créé au premier article sur ton site, en six étapes.

## 1. Créer un compte

Va sur [gridar.app](https://www.gridar.app) et clique **Commencer** (ou **Connexion**). Entre ton email, clique **Continuer** :

- Email inconnu : l'écran **Créer ton compte** te demande un mot de passe (8 caractères minimum) et sa confirmation. Clique **Créer mon compte**.
- Tu peux aussi passer par **Continuer avec Google** ou **Continuer avec GitHub**.

Tu arrives sur `/sites`. Sans site, l'écran affiche "Connecte ton premier site pour le débloquer" par-dessus un aperçu grisé du dashboard.

## 2. Connecter ton site

Quatre boutons sous l'aperçu, choisis selon ta stack :

| Tu utilises | Bouton | Ce que fait Gridar |
|---|---|---|
| WordPress | **WordPress** | Publie via l'API REST avec un Application Password |
| Shopify | **Shopify** | Publie dans un blog de ta boutique via l'Admin API (token de custom app) |
| Webflow | **Webflow** | Publie dans une CMS Collection via l'API CMS (Site API Token) |
| Aucun CMS, ou tu veux qu'on héberge | **Blog clé-en-main** | Crée un site hébergé par Gridar, servi sur ton sous-domaine (`blog.tondomaine.com`, 1 CNAME) |

Tu as un site React ou Next.js et tu veux les articles sous `tonsite.com/blog` ? Utilise le lien **Mode externe (React/Next.js)** en bas de `/sites`.

Détails par mode : [WordPress](connect/wordpress.md) · [Shopify](connect/shopify.md) · [Webflow](connect/webflow.md) · [Hébergé](connect/hosted.md) · [Externe](connect/external.md)

Pour WordPress, Shopify et Webflow, le dialog scanne le branding de ton domaine (logo, couleurs, polices) et l'affiche dans un encart **Branding détecté**. Décoche **Appliquer** si tu préfères le régler après. Le dialog **Blog clé-en-main** ne scanne rien : lance le scan depuis **Paramètres → Branding → Scanner**.

Le nombre de sites dépend de ton plan : voir [Connecter ton site](connect/README.md).

## 3. Vérifier que le contenu peut atteindre ton site

Gridar refuse de générer quand rien ne relie le site à une page en ligne. En haut de **Générer un article** :

- Bandeau rouge **Aucun chemin de livraison** : le bouton devient **Livraison à configurer** et reste grisé. Branche un CMS, active le domaine du blog public (mode hébergé), ajoute une base externe, passe en mode agent ou crée un token API (mode externe). Le bouton **Configurer la livraison** t'amène dans **Paramètres → Intégrations**.
- Bandeau orange **Livraison non confirmée** : ton compte a un token API, donc ton site lit peut-être les articles via l'API, mais Gridar ne peut pas le vérifier. La génération reste possible.

Un site WordPress, Shopify ou Webflow connecté passe ce contrôle d'office. Détails : [Connecter ton site](connect/README.md).

## 4. Générer ton premier article

Dans la sidebar, clique **Générer un article**. Si tu comptes générer via l'API ou le MCP, remplis d'abord **Paramètres → Auteur (EEAT) → Bio** : sans bio, ces canaux refusent la génération.

Le formulaire **Paramètres** :

- **Sujet (optionnel)** : vide = Gridar choisit un sujet.
- **Titre forcé (optionnel)** : le titre exact. Un titre forcé désactive le contrôle anti-doublon.
- **Méthode de recherche** : Serper ou Gemini.
- **Type d'article** : Actualité / Opinion, Tutoriel, Comparaison, Guide, Review, Récit personnel, Annuaire local.
- **Longueur** : Court (800-1200 mots), Moyen (1500-2000 mots), Long (2500-3500 mots).
- **Langue** : seulement les langues activées dans **Paramètres → Langues**.
- **Mots-clés SEO (optionnel)** : séparés par des virgules.
- **Aperçu seulement (ne pas publier)** : génère sans rien enregistrer.

Optionnel : au-dessus du formulaire, le panneau **Brief de contenu** → **Générer le brief** → **Utiliser ce brief** injecte un plan (intention, outline, FAQ, entités) dans la génération.

Clique **Générer**. Compte 1 à 2 minutes. Tu peux quitter la page : le dock en bas à droite suit la génération. Sous le capot : recherche web, choix du sujet, refus si le titre ressemble trop à un article existant, rédaction, images, correction des liens internes cassés, couverture, extrait et tags. Le détail est dans [Générer un article](generate-article.md).

## 5. Retrouver l'article

L'endroit où l'article atterrit dépend du mode :

| Mode | Statut après génération | URL |
|---|---|---|
| WordPress | Publié tout de suite | Selon tes permaliens WordPress (ex : `tonsite.ca/2026/10/article-slug/`) |
| Shopify | Publié tout de suite | `taboutique.com/blogs/<blog>/article-slug` |
| Webflow | Publié tout de suite | Selon le chemin de ta collection (ex : `tonsite.com/blog/article-slug`) |
| Hébergé | **Brouillon** | `blog.tondomaine.com/article-slug` une fois publié |
| Base externe | **Brouillon** dans ta base | Selon ton frontend |
| Mode agent | Brouillon mis en file pour l'agent | L'URL que l'agent rapporte |

En mode hébergé, ouvre **Articles**, clique **Modifier** sur l'article, puis **Publier**. Le blog public ne montre que les articles publiés.

## 6. Suivre les positions Google

Sidebar → **Suivi des positions** → **Ajouter un mot-clé à suivre**. Le bouton **Snapshot maintenant** relève les positions à la demande. Le plan Essai ne permet de suivre aucun mot-clé : voir [Plans, crédits et quotas](plans-credits.md).

Pour piloter la suite : **Audit global SEO** audite tous tes articles d'un coup, **Détection de déclin** repère ceux qui perdent du terrain. Voir [Outils SEO](seo-tools.md).

## Étapes suivantes

- Génère plusieurs articles autour d'un même thème pour bâtir un topic cluster ([Outils SEO](seo-tools.md)).
- Gère ton abonnement et tes crédits depuis le lien **Abonnement** de `/sites` ([Plans, crédits et quotas](plans-credits.md)).
- Branche Google Search Console : **Paramètres → Search Console** ([guide](gsc.md)).
- Règle le reste du site : [Référence des paramètres](site-settings.md).
- Pour automatiser : crée un token sur `/account/api-keys` (lien **API** de `/sites`) et utilise l'[API REST](api.md) ou les [intégrations](integrations.md).
