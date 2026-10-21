# Vue multi-sites

Deux pages te montrent tous tes sites d'un coup : **Comparaison multi-sites** (`/compare`) et **Santé de tous mes sites** (`/dashboard/overview`). Elles existent sur tous les plans. Le nombre de sites que tu peux créer dépend de ton plan : 1 en Essai et Solo, 2 en Pro, 5 en Agence. Voir [Plans, crédits et quotas](plans-credits.md).

## Comparaison multi-sites (`/compare`)

### Accès

Page Sites → bouton **Comparer mes sites** (en bas de la page).

### Totaux

Quatre compteurs en haut de page :

- Sites actifs sur le total de tes sites
- Articles publiés
- Vues totales
- Mots-clés suivis

### Tableau par site

Une ligne par site. Un site inactif apparaît grisé.

| Colonne | Contenu |
|---|---|
| Site | Nom + domaine, lien vers le tableau de bord du site |
| Articles | Articles publiés, brouillons entre parenthèses |
| Vues | Total des vues des articles publiés |
| Langues | Nombre d'articles publiés par langue |
| GSC | Google Search Console connectée ou non |
| EEAT | Profil auteur rempli ou non (bio ou rôle) |
| Mots-clés | Mots-clés suivis actifs |
| Redirections | Redirections 301 actives |

L'icône en bout de ligne ouvre le tableau de bord du site.

### Couverture

Deux cartes sous le tableau :

- **Couverture Google Search Console** : combien de tes sites ont GSC connecté.
- **Couverture profil auteur EEAT** : combien de tes sites ont un profil auteur rempli.

### Limite

La page lit les articles des sites hébergés et des sites branchés sur une base de données externe. Un site WordPress, Shopify ou Webflow y apparaît sans statistiques : les zéros et les croix de sa ligne ne reflètent pas l'état réel du site. Pour ces sites, ouvre leur tableau de bord.

## Santé de tous mes sites (`/dashboard/overview`)

### Où la trouver

Sélecteur de sites → bouton **Voir vue multi-sites** (visible dès que tu as plus d'un site).

### Colonnes

| Colonne | Contenu |
|---|---|
| Site | Nom + domaine |
| SEO Score | Score SEO composite du site, de 0 à 100 : vert à partir de 70, ambre de 40 à 69, rouge en dessous |
| Decay | Nombre d'articles en baisse sur 30 jours dans Google Search Console |
| Action | Bouton **Ouvrir** vers le tableau de bord du site |

Sans GSC connecté, la colonne Decay affiche **GSC requis**. Si l'accès GSC a expiré, elle affiche **Reconnecter GSC**. Les deux mènent aux réglages GSC du site. Voir [Google Search Console](gsc.md).

## Automatiser un rapport par site

La page Comparaison n'a pas d'équivalent par jeton API. Pour un rapport automatisé, passe par l'[API REST publique](api.md) (plans Pro et Agence) :

1. `GET /api/v1/sites/` pour la liste de tes sites et leurs `id`.
2. Pour chaque site :
   - `GET /api/v1/sites/<id>/seo-score/` : score composite + actions à mener.
   - `GET /api/v1/sites/<id>/keywords/` : mots-clés suivis + dernière position connue.
   - `GET /api/v1/sites/<id>/proof/summary/` : impressions et clics gagnés d'après GSC.
   - `GET /api/v1/sites/<id>/digest/weekly/` : articles publiés dans la semaine, plus gros mouvements de positions. Sites hébergés et sites à base externe seulement.

```bash
#!/bin/bash
# Rapport mensuel : score SEO de chaque site
# GRIDAR_TOKEN contient ton jeton btb_xxx (variable d'environnement, jamais en dur)
for ID in $(curl -s -H "Authorization: Bearer $GRIDAR_TOKEN" \
    https://api.gridar.app/api/v1/sites/ | jq '.results[].id'); do
  curl -s -H "Authorization: Bearer $GRIDAR_TOKEN" \
    "https://api.gridar.app/api/v1/sites/$ID/seo-score/"
done
```

Chaque appel compte dans ta limite horaire : 30 requêtes/heure en Pro, 200 en Agence.

## Partager les résultats d'un site avec ton client

Chaque site peut avoir une **page de preuve publique** en lecture seule : `https://www.gridar.app/proof/<token>`. Elle montre les impressions et les clics gagnés d'après Google Search Console. Active-la depuis le tableau de bord du site ou par l'API (`POST /api/v1/sites/<id>/proof/share/`). Tu peux la révoquer à tout moment : l'URL répond alors 404.

## Recette : onboarding d'un nouveau client

1. Connecte le site du client. Voir [Connecter un site](connect/README.md).
2. Dans les réglages du site, remplis le **modèle d'affaires** et la **bio de l'auteur** : la génération refuse de partir sans ces deux champs. Voir [Réglages du site](site-settings.md).
3. Connecte Google Search Console. Voir [Google Search Console](gsc.md).
4. Ajoute les mots-clés à suivre, dans la limite de ton plan.
5. Active la page de preuve publique et envoie le lien à ton client.
