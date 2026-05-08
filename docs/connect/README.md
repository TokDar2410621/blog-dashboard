# Connecter ton site

5 modes selon ta stack. Tous publient les articles directement chez toi (ton domaine, ton CMS, ta base) - on ne te force jamais à utiliser notre infrastructure de publication.

| Mode | Idéal pour | Friction | SEO sur ton domaine |
|---|---|---|---|
| [WordPress](wordpress.md) | Sites WordPress 5.6+ | 1 Application Password | 100 % |
| [Shopify](shopify.md) | Boutiques Shopify | 1 custom app token | 100 % |
| [Webflow](webflow.md) | Sites Webflow avec CMS | 1 Site API Token | 100 % |
| [Hébergé](hosted.md) | Site custom sans CMS, marketers | 1 CNAME DNS | ~90 % (sous-domaine) |
| [Externe](external.md) | Devs avec stack React/Next custom | API REST + scaffolder | 100 % |

## Flow commun

Pour chaque mode, le dialog de connexion fait :

1. **Validation** - on tente de joindre ton CMS/domaine et confirmer les credentials
2. **Auto-scan branding** - on extrait logo, couleur primaire, fonts depuis ta home page (extracteur HTML+CSS, ~2 sec)
3. **Preview** - card en bas du dialog : "voilà ton blog avec ton branding". Tu peux décocher pour configurer manuellement après.
4. **Connexion** - création de la `Site` row dans ton compte avec les credentials chiffrés et le `theme_config` détecté
5. **Confetti emerald** - premier connect d'un compte = animation de bienvenue
6. **Redirection** - on t'amène direct dans le dashboard du nouveau site

## Limites par plan

Le nombre de sites connectables dépend de ton plan :

- **Essai** : 1 site
- **Solo** : 1 site
- **Pro** : 2 sites
- **Agence** : 5 sites
- **Enterprise** : sur mesure

Détails : [Plans, crédits et quotas](../plans-credits.md).

## Re-connecter / changer un site

Tu peux re-connecter le même CMS/domaine plus tard sans consommer un slot supplémentaire - on détecte que le site existe déjà (par `wp_url`, `shopify_domain`, ou `webflow_site_id + collection_id`) et on **met à jour** les credentials. Utile si ton Application Password a expiré ou si tu veux changer la collection Webflow.

## Désactiver / supprimer

Site Settings → onglet "Compte" → "Désactiver le site" ou "Supprimer". La désactivation conserve les articles mais les rend invisibles ; la suppression efface tout (irréversible).
