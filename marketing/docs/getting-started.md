# Démarrage rapide

De zéro à premier article publié en 5 minutes.

## 1. Créer un compte

Va sur l'app, clique **Se connecter** → **Créer un compte**. Email + mot de passe, c'est tout.

À l'arrivée, tu atterris sur `/sites` avec une page d'accueil "Connecte ton premier site pour le débloquer". Le mockup grayscale en arrière-plan, c'est ton dashboard une fois actif.

## 2. Connecter ton site

4 boutons en haut, choisis selon ta stack :

| Tu utilises | Choisis | Ce qu'on fait |
|---|---|---|
| WordPress | **WordPress** | Publie via REST API + ton Application Password. Articles à `tonsite.ca/blog/article` |
| Shopify | **Shopify** | Publie dans `/blogs/news/` via Admin API. Custom-app token (5 min de setup chez Shopify) |
| Webflow | **Webflow** | Publie dans une CMS Collection (généralement "Blog Posts"). Site Token Webflow |
| Site custom (React, Vue, Astro, ...) ou aucune des options | **Blog clé-en-main** | On t'héberge le blog à `blog.tondomaine.com` (sous-domaine, 1 CNAME) |

Détails par mode : [WordPress](connect/wordpress.md) · [Shopify](connect/shopify.md) · [Webflow](connect/webflow.md) · [Hébergé](connect/hosted.md) · [Externe](connect/external.md)

**Au moment du connect**, on scanne automatiquement le branding de ton domaine (logo, couleur, fonts) - preview live dans le dialog avant de cliquer "Connecter". Tu peux décocher si tu veux configurer manuellement après.

## 3. Générer ton premier article

Une fois connecté, tu arrives sur le dashboard du site. Dans la sidebar, clique **Générer un article**.

Champs minimaux :
- **Sujet** : ce que tu veux qu'on couvre. Ex : "Comment choisir un CRM pour PME au Québec en 2026".
- **Langue** : FR par défaut (ou EN/ES selon ce que tu as activé sur le site).
- **Longueur** : Court (~600 mots), Moyen (~1500 mots), Long (~2500 mots).
- **Type** : Guide, Tutoriel, Actualité, Comparaison, Histoire, Local.

Optionnel mais recommandé : commence par **Brief de contenu** au-dessus du formulaire - ça génère un plan stratégique (intent, outline, FAQ, entités) qui se branche automatiquement dans ton article.

Clique **Générer**. Sous le capot :
1. Recherche SERP sur Serper pour le sujet
2. Analyse + sélection du sujet final
3. Anti-cannibalisation (refuse si trop similaire à un article existant)
4. Rédaction Claude avec ton lexique FR-CA, ton EEAT, ton schema
5. Maillage interne automatique vers tes articles existants
6. Audit SEO inline + corrections automatiques
7. Publication directe dans ton CMS

Compte ~90 secondes. Le résultat apparaît à droite.

## 4. Confirmer la publication

L'article est maintenant visible sur **ton domaine** (pas le nôtre). URL exacte selon le mode :
- WordPress : `tonsite.ca/2026/05/article-slug/` (selon ton permalink)
- Shopify : `taboutique.com/blogs/news/article-slug`
- Webflow : `tonsite.com/blog/article-slug`
- Hébergé : `blog.tondomaine.com/article-slug`

Va sur l'URL → ton article est en ligne, indexable par Google.

## 5. Suivre les positions Google

Dashboard → **Suivi des positions** → ajoute 5-10 mots-clés cibles. On crawl la SERP chaque jour pour mesurer où ton site classe sur ces requêtes.

Combine avec **Audit global** (audite tous tes articles d'un coup) et **Content decay** (détecte les articles qui chutent) pour piloter ta stratégie SEO.

## Étapes suivantes

- Génère 5-10 articles autour d'un thème pour créer un **topic cluster** ([guide](seo-tools.md#topic-clusters))
- Configure ta page Stripe : profil, mode paiement, [acheter des crédits](plans-credits.md) si ton quota mensuel est insuffisant
- Branche **Google Search Console** pour des données réelles d'impressions/clics (Site Settings → GSC)
- Pour de l'automatisation : crée un token API et utilise le [SDK REST](api.md) avec n8n/Zapier/Make
