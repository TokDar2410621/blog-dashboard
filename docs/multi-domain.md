# Comparaison multi-domaines (Agence)

Vue cross-sites pour les agences qui gèrent plusieurs blogs clients. Disponible **plan Agence et Enterprise** uniquement.

## Accès

Sites → bouton **Comparer mes sites** (en bas de la page Sites) → `/compare`.

## Vue d'ensemble

Tableau comparatif de tous tes sites actifs, avec pour chaque ligne :

| Colonne | Description |
|---|---|
| Site | Nom + domaine |
| Plan | Le plan associé (héritage du compte ou per-site override Enterprise) |
| Articles | Total publiés + articles ce mois |
| Score SEO moyen | Moyenne pondérée sur tous les articles publiés |
| Mots-clés trackés | Combien + position moyenne |
| Top 10 % | Combien de mots-clés en top 10 Google |
| Tendance positions | Variation 30j (📈 +3 / 📉 -7 / ⏸ stable) |
| Trafic estimé / mois | Via GSC si connecté, sinon estimation depuis positions × volume |

Chaque ligne cliquable → ouvre le dashboard du site dans un nouvel onglet.

## Filtres + tris

- **Filtrer par** : plan, langue, statut (actif / inactif), CMS (WP / Shopify / etc.)
- **Trier par** : n'importe quelle colonne, asc/desc
- **Sélectionner** plusieurs sites → actions bulk (voir ci-dessous)

## Actions bulk

Une fois plusieurs sites cochés :

- **Auditer tous** : lance un audit SEO global sur les sites sélectionnés. Résultat agrégé.
- **Snapshot positions** : crawl SERP immédiat pour tous les sites. Compte dans ton quota API.
- **Exporter en CSV** : tableau Excel-friendly avec toutes les métriques. Utile pour rapports clients.
- **Email digest groupé** : envoie un seul email PDF qui couvre tous les sites sélectionnés.

## Comparaison de mots-clés

**Onglet "Mots-clés"** sur la page Compare.

Tableau croisé : ligne = mot-clé, colonne = site, cellule = position du site sur ce mot-clé.

Détecte :
- **Mots-clés communs** : que plusieurs de tes sites ciblent (potentielle cannibalisation cross-domains)
- **Mots-clés exclusifs** : qu'un seul site cible (opportunités de partage de contenu)
- **Gaps** : mots-clés où tu classes top 30 sur 1 site mais pas du tout sur les autres

Utile pour orchestrer ta stratégie de contenu cross-clients.

## Rapport "client" (white-label)

**Sidebar Compare → Rapport client**

Génère un PDF par site sélectionné, avec :
- Page 1 : exec summary (score SEO, articles publiés, top 10 %, trafic estimé)
- Page 2 : top 5 articles (par trafic / par position)
- Page 3 : tendances mots-clés (graphique 90j)
- Page 4 : recommandations (articles en decay, gaps, audits à corriger)
- Page 5 : crédits (ton logo, ton agence, contact)

**White-label** :
- Agence : ton logo en haut + nom de ton agence dans le footer + ton contact
- Le client ne voit pas "Blog Dashboard" sauf en mention discrète "Powered by"
- Customizable dans Site Settings → onglet "White-label" (Agence uniquement)

## API multi-domain

```bash
curl -H "Authorization: Bearer btb_xxx" \
  https://api.blog-dashboard.ca/api/v1/multi-domain-stats/
```

Retourne le JSON équivalent du tableau comparatif. Pratique pour brancher dans un dashboard client custom (Notion / Airtable / Google Sheets via Zapier).

## Limites de plan

| | Agence (199.99$) | Enterprise |
|---|---|---|
| Sites comparables | 5 | sur mesure |
| Bulk audits / mois | 100 | sur mesure |
| Rapports PDF white-label | illimités | illimités |
| Export CSV | ✅ | ✅ |

## Recettes pour agence SEO

### Onboarding d'un nouveau client

1. Connecte le site du client (5 min selon le mode)
2. Configure Site Settings (Knowledge base, EEAT, GSC) - 10 min
3. Génère 5-10 articles de seed pour démarrer le content cluster - 1h IA + 30 min de révision
4. Configure 10-15 mots-clés tracking
5. Envoie le rapport client #1 par email après 7j

Tu factures le client pour ton expertise + setup. Notre coût pour toi : 1 slot site + ~30 articles du quota.

### Reporting mensuel automatisé

1. Crée un script (ou cron / GitHub Action) qui appelle `GET /api/v1/multi-domain-stats/` chaque 1er du mois
2. Filtre les sites du client X
3. Génère le rapport PDF white-label via UI ou via API (endpoint en dev)
4. Email automatique au client

Gain : 1 jour/mois économisé par client. Avec 10 clients = 10 jours/mois récupérés.
