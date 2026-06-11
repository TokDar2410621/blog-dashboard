# Référence Site Settings

Toutes les options par site. Accessibles via **Sidebar → Paramètres** ou directement à `/dashboard/<id>/parametres`.

## Onglet "Général"

| Champ | Description |
|---|---|
| Nom du site | Libellé interne. Apparaît dans le sélecteur de site et le bandeau du dashboard |
| Domaine | Domaine canonique de ton site. Utilisé pour les liens absolus, l'OG image fallback, le lien depuis le dashboard |
| Auteur par défaut | Nom attribué aux articles générés par l'IA. Hérité par per-article (modifiable en édition) |
| Langue par défaut | Présélectionnée dans l'éditeur et la génération IA |
| Langues disponibles | Coche les langues activées : FR / EN / ES. Si vide = toutes |

## Onglet "Branding"

Pour le mode hébergé : ces couleurs/fonts s'appliquent au blog public Next.js. Pour les autres modes : utilisé pour les schemas Open Graph et l'OG image fallback.

| Champ | Description |
|---|---|
| Description | Courte description du site (Open Graph, schema Organization). 140-160 caractères idéal |
| Image OG par défaut | URL de l'image utilisée si un article n'a pas de cover. 1200×630 idéal |
| Couleur principale | Hex (ex `#10b981`). Utilisé pour les CTAs sur le blog public |
| Couleur du texte | Hex foreground sur la couleur principale (ex `#ffffff`) |
| Logo URL | URL absolue de ton logo. Apparaît dans le header du blog public + schema Organization |

**Bouton "Scanner"** : crawl ton domaine et auto-remplit ces champs. Détecte ta couleur primaire (theme-color meta + couleur saturée dominante), ton logo (apple-touch-icon → favicon → first header img), tes fonts.

## Onglet "EEAT" (auteur)

Signaux d'expertise pour Google. Apparaissent dans le schema Person + dans la signature des articles générés.

| Champ | Description |
|---|---|
| Rôle / titre | Ex : "Fondateur, consultant SEO, avocat fiscaliste" |
| Bio | 2-4 phrases qui établissent l'expertise (E-E-A-T) |
| Crédentials | Diplômes, certifications, expérience pertinente |
| Photo URL | Photo professionnelle (JSON-LD Person.image) |
| LinkedIn / Twitter / Site personnel | Profils sociaux pour `sameAs` |

**Pourquoi c'est important** : Google Helpful Content Update et Author rankings (2024+) prennent en compte fortement l'auteur identifié vs un blog anonyme. Sites avec auteur EEAT bien rempli ranquent +30 % en moyenne.

## Onglet "WordPress" (si mode WP)

| Champ | Description |
|---|---|
| URL WordPress | `https://tonsite.ca` (sans `/wp-admin`) |
| Username | Slug du compte WP (pas l'email) |
| Application Password | Le mot de passe sans espaces |
| Re-tester la connexion | Bouton qui hit `/wp-json/wp/v2/users/me` |

## Onglet "Shopify" (si mode Shopify)

| Champ | Description |
|---|---|
| Domaine .myshopify.com | `monstore.myshopify.com` |
| Admin API token | `shpat_xxx` |
| Blog ID | Le blog où on publie (auto-détecté à la connexion) |

Bouton "Re-détecter les blogs" pour changer le blog cible.

## Onglet "Webflow" (si mode Webflow)

| Champ | Description |
|---|---|
| Site Token | Long string Webflow |
| Site ID | ID du Webflow site (auto-rempli) |
| Collection ID | CMS Collection où publier |
| Field map | JSON mapping de nos champs vers les slugs Webflow (auto-détecté) |

## Onglet "Hébergé" (si mode hosted)

| Champ | Description |
|---|---|
| Public blog domain | Le sous-domaine où tu sers le blog (`blog.tonsite.ca`) |
| Vercel Deploy Hook | URL du Deploy Hook Vercel pour rebuild après chaque article (optionnel) |
| Theme config | Couleur, fonts, logo (synchronisé avec onglet Branding) |

## Onglet "Knowledge base"

Texte libre que l'IA voit en tant que **contexte** lors de la génération d'articles. Très utile pour :

- **Description de ton entreprise** ("On vend des CRM aux PME québécoises depuis 2018")
- **Ton de voix** ("Direct, technique, sans jargon corporate, adresse à 'tu'")
- **Faits clés** ("Notre service principal : 79$/mois, 30j d'essai")
- **Concurrents à mentionner ou pas** ("Évite de citer Salesforce")
- **Glossaire interne** ("On utilise 'consultant' pas 'expert' pour notre rôle")

L'IA respecte cette knowledge base dans tous les articles générés. Mise à jour à n'importe quel moment.

Limite : 4000 tokens (~3000 mots). Au-delà, on tronque.

## Onglet "Schema.org"

Génère du JSON-LD prêt à coller :

### LocalBusiness (commerce local québécois)

Champs :
- Adresse (rue, ville, code postal)
- Téléphone
- Heures d'ouverture
- Prix range (`$`, `$$`, `$$$`, `$$$$`)
- Géo coordinates

Bouton "Générer" → JSON-LD copy-pasteable. À coller dans le `<head>` de ta home (ou via un plugin schema sur ton CMS).

### Person (auteur EEAT)

Auto-rempli depuis l'onglet EEAT. Bouton "Copier" pour récupérer le JSON-LD.

### Organization

Auto-rempli depuis Branding (logo, description, sameAs). Bouton "Copier".

## Onglet "Search Console"

Connexion Google Search Console pour récupérer les vraies impressions/clics par article et keyword.

Voir : [Intégration Google Search Console](gsc.md).

## Onglet "Notifications"

| Option | Default | Description |
|---|---|---|
| Email rapport hebdomadaire | ✅ Pro+ | Lundi matin, digest de la semaine |
| Email content decay | ✅ | Quand un article perd > 30 % de trafic |
| Email rank drop | ✅ Pro+ | Quand un mot-clé tracké chute > 5 positions |
| Email broken link detected | ✅ | Crawl périodique trouve un 404 dans tes articles |
| Email quota approchant | ✅ | À 80 % et 95 % de ton quota mensuel |

Désactivable per-type. Tu peux aussi ajouter un **webhook Slack** ou **Discord** dans le champ "Webhook URL" pour recevoir les alertes en chat au lieu d'email.

## Onglet "Avancé"

### Database URL (mode externe Postgres)

Si tu veux que les articles soient stockés dans **TA** base au lieu de la nôtre :

```
postgresql://user:pwd@host:5432/dbname
```

À l'enregistrement, on initialise les tables `blog_*` dans ta base et on bascule en mode externe Postgres. Permet à ton backend Python de lire les articles directement (ORM, raw SQL).

### Blog config (mapping de tables custom)

Si ta base existante a déjà des tables blog avec des noms non-standard, on peut mapper. JSON :

```json
{
  "posts_table": "tbl_articles",
  "categories_table": "tbl_categories",
  "post_columns": { "title": "headline", "slug": "url_slug", ... }
}
```

Pour la plupart, laisse vide (on utilise les noms par défaut).

### Templates visuels

Pour le blog public (mode hébergé). Choisis :
- **Hero classique** : grande image, titre centré, contenu sous
- **Magazine** : image à droite, contenu à gauche, sidebar
- **Minimaliste** : texte centré, pas d'image hero
- **Sidebar** : 2 colonnes avec sidebar de related posts

Aperçu live à droite. Sauvegarde → applique sur tous les nouveaux articles. Articles existants gardent leur template (changeable per-article).

### Cache audit

Bouton "Vider le cache d'audit SEO". Force une réévaluation à la prochaine demande. À utiliser après un changement majeur de ton contenu si l'audit ne reflète pas.

## Onglet "Compte"

| Action | Effet |
|---|---|
| **Désactiver le site** | `is_active=False`. Articles invisibles publiquement. Réversible (réactiver = re-rend le site fonctionnel) |
| **Supprimer le site** | Confirmation requise. Supprime le site + tous ses articles + ses keywords. **Irréversible**. Articles publiés sur CMS natif (WP/Shopify/Webflow) **ne sont PAS** supprimés (ils restent chez toi) |
| **Transférer la propriété** | À un autre user du compte (Agence) |

## Recettes

### Configurer un nouveau site PME québécois

1. **Général** : nom, domaine, default_author = ton nom, langue par défaut FR, langues `[fr, en]`
2. **Branding** : Scanner ton domaine → vérifie + ajuste, ajoute une OG image 1200×630
3. **EEAT** : remplis tout (rôle, bio, photo, LinkedIn) - gain SEO immédiat
4. **Schema Organization** : génère + colle dans ton head (ou WP plugin schema)
5. **Schema LocalBusiness** : génère avec ton adresse → colle sur la page de contact / footer
6. **Knowledge base** : 200-300 mots qui résument qui tu es, ton ton, tes services
7. **Search Console** : connecte (OAuth en 2 clics)
8. **Notifications** : laisse les défauts, ajoute un webhook Slack si tu veux
9. **Branche le mode** (WordPress / Shopify / hébergé selon ton stack)

15-20 minutes total. Tu es prêt à générer.
