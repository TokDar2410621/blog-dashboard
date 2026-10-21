# Connecter ton site

Gridar doit savoir comment un article généré arrive sur ton site. Choisis le chemin selon ta stack, depuis `/sites`.

| Mode | Idéal pour | Ce qu'il faut | Où vit l'article |
|---|---|---|---|
| [WordPress](wordpress.md) | Sites WordPress 5.6+ | 1 Application Password | Ton WordPress, sur ton domaine |
| [Shopify](shopify.md) | Boutiques Shopify | 1 token de custom app | Le blog de ta boutique, sur ton domaine |
| [Webflow](webflow.md) | Sites Webflow avec CMS | 1 Site API Token | Ta CMS Collection, sur ton domaine |
| [Hébergé](hosted.md) | Pas de CMS, rien à coder | 1 CNAME DNS | Chez Gridar, servi sur ton sous-domaine |
| [Externe](external.md) | Site React / Next.js maison | Un token API + du code (fourni) | Chez Gridar, lu par ton frontend sous `tonsite.com/blog` |

Deux variantes pour les sites faits main, décrites dans [Mode externe](external.md) :

- **Base Postgres externe** : Gridar écrit les articles dans ta propre base (champ DATABASE_URL à la création du site).
- **Mode agent** : un agent de code (Claude Code ou autre) récupère les articles et les pose dans ton repo. Se règle dans **Paramètres → Général → Mode de livraison**.

## Ce que fait le dialog de connexion

Pour **WordPress**, **Shopify** et **Webflow** :

1. **Validation** : Gridar joint ton CMS et vérifie les identifiants avant d'enregistrer quoi que ce soit.
2. **Scan du branding** : logo, couleurs et polices sont lus sur ta page d'accueil et affichés dans l'encart **Branding détecté**, avec un bouton témoin aux couleurs trouvées. Si le scan échoue, l'encart n'apparaît pas et la connexion continue.
3. **Appliquer** : case cochée par défaut. Décoche-la pour régler le branding plus tard dans **Paramètres → Branding**.
4. **Connecter** : Gridar crée le site dans ton compte, lance les confettis et t'amène sur son dashboard.

Pour **Blog clé-en-main** (et le bouton **Ajouter un site**, qui ouvre le même dialog) : trois champs, **Nom du site**, **DATABASE_URL** (optionnel) et **Domaine** (optionnel), puis **Ajouter le site**. Pas de scan de branding. Le dialog se ferme sur "Site ajouté!" et le site apparaît dans la liste : clique **Ouvrir** pour entrer dans son dashboard.

## Quand rien n'est branché

Gridar vérifie qu'un chemin relie le site à une page en ligne. Le résultat s'affiche en haut de **Générer un article** :

| État | Quand | Effet |
|---|---|---|
| Prêt (aucun bandeau) | CMS connecté, base externe, domaine du blog public activé, ou mode agent | Génération possible |
| **Livraison non confirmée** (orange) | Aucun de ces chemins, mais ton compte a un token API actif | Génération possible. Gridar ne peut pas vérifier que ton site affiche l'article |
| **Aucun chemin de livraison** (rouge) | Rien de tout ça | Bouton **Livraison à configurer**, grisé. **Configurer la livraison** ouvre **Paramètres → Intégrations** |

Le même contrôle bloque la génération via l'API et le MCP (réponse 409, code `delivery_blocked`) et fait sauter son tour à l'autopilote. Un site créé avec **Blog clé-en-main** sans DATABASE_URL démarre dans l'état rouge, jusqu'à ce que tu actives le domaine du blog public, passes en mode agent ou crées un token API.

## Limites par plan

Le nombre de sites actifs dépend de ton plan :

- **Essai** : 1 site
- **Solo** : 1 site
- **Pro** : 2 sites
- **Agence** : 5 sites

Au-delà, la création renvoie "Limite de sites atteinte (x/y). Mets ton plan à niveau sur /billing pour ajouter un site supplémentaire." Détails : [Plans, crédits et quotas](../plans-credits.md).

## Reconnecter / changer les identifiants

Les identifiants WordPress, Shopify et Webflow ne se modifient pas dans les paramètres du site. Refais la connexion depuis `/sites` avec le même CMS : Gridar reconnaît le site existant (même `wp_url` pour WordPress, même domaine `.myshopify.com` pour Shopify, même site + même collection pour Webflow), **met à jour** les identifiants et ne consomme pas de place supplémentaire dans ton plan. Utile après la révocation d'un Application Password ou d'un token.

Pour Webflow, choisir une autre collection crée un nouveau site.

## Boutons de la liste des sites

Chaque carte de `/sites` propose :

- **Ouvrir** : entre dans le dashboard du site.
- **Test** et **Init** : réservés aux sites avec base externe (DATABASE_URL). **Test** vérifie la connexion à ta base, **Init** y crée les tables du blog. Sur les autres sites, ils renvoient une erreur.
- **Corbeille** : supprime le site après confirmation.

## Supprimer

Icône corbeille sur la carte du site, puis **Supprimer** dans "Supprimer ce site ?". L'action est irréversible et efface ce que Gridar stocke pour ce site. Les articles déjà publiés sur ton CMS ou écrits dans ta base externe restent chez toi. Le dashboard ne propose pas de désactivation temporaire.
