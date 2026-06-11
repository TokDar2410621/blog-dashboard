# Google Search Console - intégration

Connecte ta propriété GSC pour récupérer les vraies données d'impressions, clics et positions par article. Branchement en 2 minutes via OAuth, pas de service account à configurer.

## Pourquoi connecter GSC

Sans GSC, on **estime** les positions via crawl SERP (Serper) - c'est précis mais c'est une estimation.

Avec GSC, on a :
- **Impressions réelles** par article par jour
- **Clics réels** + CTR
- **Position moyenne réelle** que Google affiche aux vrais utilisateurs
- **Top queries** : les mots-clés sur lesquels les gens te trouvent (souvent surprenants)
- **CTR par position** pour calibrer ta stratégie

Avantage business : tu sais quels articles convertissent vs ceux qui sont vus sans clic. Indispensable pour optimiser.

## Pré-requis

- Avoir une propriété Google Search Console **vérifiée** pour ton domaine (sinon, [vérifie d'abord](https://search.google.com/search-console))
- Compte Google avec les droits "Owner" ou "Full" sur la propriété

## Connexion (OAuth 2 clics)

**Site Settings → onglet "Search Console" → bouton "Connecter Google Search Console"**

1. Tu es redirigé vers Google : "Gridar demande l'accès à ton Search Console"
2. Coche les permissions demandées : `webmasters.readonly`
3. Autoriser → retour automatique sur Site Settings
4. Le champ "Propriété GSC" devient un select avec tes propriétés disponibles
5. Choisis celle qui matche ton domaine (ex : `https://tonsite.ca/` ou `sc-domain:tonsite.ca`)
6. Sauvegarde

Status indicateur : "✓ Connecté · 47 propriétés disponibles".

## Données affichées dans le dashboard

### Per-article (PostList + PostEditor)

Pour chaque article : ses 30 dernières jours d'impressions/clics. Graphique sur l'éditeur. Détails :

- Top 10 queries qui ramènent du trafic vers cet article
- Position moyenne sur ces queries
- CTR estimé (clics / impressions)
- Pages qui ranquent pour le même keyword (cannibalisation détectée)

### Suivi des positions

Combine : nos crawls Serper (positions exactes du jour) + GSC (positions moyennes 7d/28d). Donne une vue plus complète.

### Multi-domain stats (Agence)

Comparaison cross-sites : quel site/domaine ramène le plus de trafic, lequel a le meilleur CTR moyen, quels mots-clés sont communs entre tes sites.

### Rapport hebdomadaire

Quand GSC est connectée, le rapport email/PDF contient les vraies données GSC au lieu d'estimations.

## Refresh automatique

On rafraîchit les données GSC :
- **Toutes les 24h** : pour les positions / impressions globales
- **À chaque visite** d'un article : si pas de cache < 1h, on re-fetch les data spécifiques à cet article

Latence GSC : Google met 2-3 jours à reporter les données. Donc le 8 mai, tu vois les data jusqu'au 5-6 mai.

## Endpoints API

```bash
curl -H "Authorization: Bearer btb_xxx" \
  "https://api.gridar.app/api/v1/sites/12/gsc/queries/?days=28&page_url=https://tonsite.ca/blog/article-slug"
```

Réponse :
```json
{
  "page_url": "https://tonsite.ca/blog/article-slug",
  "days": 28,
  "queries": [
    { "query": "crm pme québec", "clicks": 47, "impressions": 1284, "ctr": 0.037, "position": 8.2 },
    { "query": "meilleur crm canadien", "clicks": 23, "impressions": 612, "ctr": 0.038, "position": 12.4 },
    ...
  ]
}
```

## Permissions

On demande **uniquement `webmasters.readonly`** (lecture seule). On ne peut pas :
- Modifier ta propriété GSC
- Soumettre / supprimer des sitemaps
- Demander l'indexation d'URLs (use case sur la roadmap mais via une permission séparée)

Tu peux révoquer notre accès à n'importe quel moment :
- Côté nous : Site Settings → Search Console → Déconnecter
- Côté Google : <https://myaccount.google.com/permissions> → Gridar → Supprimer l'accès

## Refresh token

Au connect, on stocke un OAuth refresh token (chiffré au repos). Il permet de re-générer l'access token sans te re-demander de te logger.

Le refresh token reste valide tant que :
- Tu ne révoques pas l'accès
- Le compte Google reste actif
- Pas de changement de mot de passe Google récent (parfois Google invalide les tokens dans ce cas)

Si le refresh token expire, on affiche un bandeau "GSC déconnecté, reconnecte" en haut du dashboard. Reconnecte en 2 clics.

## Setup pour Agence (5+ sites)

Si tu gères plusieurs sites avec un seul compte Google qui a accès à toutes les propriétés :

1. Connecte GSC une première fois (n'importe quel site)
2. Pour chaque autre site → Site Settings → Search Console → "Utiliser la connexion existante" (au lieu de re-OAuth)
3. Choisis la propriété correspondante dans le select

Pas besoin de refaire l'OAuth N fois pour N sites.

## Limites

- **API quota Google** : 1200 req/min/projet (notre projet OAuth). À l'échelle Agence avec 100 sites GSC, on cache agressivement (1h pour les article-level, 24h pour les site-level).
- **Pas de Bing Webmaster Tools** (l'équivalent Bing). Bing ramène ~5 % du trafic search au Québec, donc faible priorité. Sur la roadmap.
- **Pas de Yandex / Baidu** : zéro pertinence pour le marché québécois.

## Dépannage

| Erreur | Cause | Action |
|---|---|---|
| "Propriété non trouvée" | Tu n'es pas Owner/Full sur la propriété | Demande l'accès au vrai propriétaire (souvent ton ancien dev/agence) |
| "Token expiré" en bandeau | Refresh token invalidé | Reconnecte (Site Settings → bouton "Reconnecter") |
| Pas de données affichées | Latence Google (2-3 jours) ou propriété trop récente | Patiente. GSC commence à reporter ~1 semaine après vérification de la propriété |
| `403 insufficient_scope` | OAuth a refusé `webmasters.readonly` | Refait le flow OAuth, coche bien la permission |
