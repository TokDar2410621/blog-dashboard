# Google Search Console - intégration

Connecte ta propriété GSC pour que Gridar lise les vraies données de Google : impressions, clics, CTR et position moyenne de tes articles, et statut d'indexation de tes pages. La connexion passe par OAuth, sans service account à configurer.

## Pourquoi connecter GSC

Avec GSC connectée, Gridar lit :
- **Les requêtes de chaque article** : clics, impressions, CTR et position moyenne sur 28 jours, requête par requête
- **Le déclin de tes pages** : impressions et clics d'une période comparés à la précédente
- **Le statut d'indexation exact** de tes pages, et la raison quand Google ne les indexe pas
- **La preuve Gridar** : les impressions et clics gagnés par tes articles hébergés depuis leur publication

Et Gridar peut **re-soumettre ton sitemap** à Google.

Ce que GSC ne change pas : le **Suivi des positions** relève toujours Google via Serper, connecté ou non, et le **Rapport hebdo** n'utilise pas les données GSC. Voir [Outils SEO](seo-tools.md).

## Pré-requis

- Une propriété Google Search Console **vérifiée** pour ton domaine (sinon, [vérifie-la d'abord](https://search.google.com/search-console))
- Un compte Google qui a accès à cette propriété. Gridar lit tes données avec un accès propriétaire, complet ou restreint. La soumission de sitemap échoue si Google répond que le compte n'est pas propriétaire de la propriété.

## Connexion

**Paramètres → onglet « Search Console » → bouton « Connecter Google Search Console »**

1. Tu es redirigé vers Google, qui te demande d'autoriser Gridar à accéder à ton Search Console
2. Autorise : retour automatique sur l'onglet Search Console, avec le message « Google Search Console connecté »
3. Gridar cherche seul la propriété qui correspond à ton domaine, dans cet ordre : `sc-domain:tondomaine`, `https://tondomaine/`, `https://www.tondomaine/`, `http://tondomaine/`
4. Si le champ **Property URL** était vide, Gridar y enregistre la propriété trouvée

Une fois connecté, l'onglet affiche le badge **Connecté** et « Ton compte Google est lié pour la property `<url>` ». Le bouton devient **Reconnecter un autre compte**, et **Déconnecter** apparaît.

**Champ « Property URL »** : il attend une URL avec le slash final (`https://tonsite.ca/`). Pour une propriété de domaine (`sc-domain:tonsite.ca`), laisse le champ vide ou mets l'URL de ton site : Gridar retrouve la propriété de domaine à chaque appel. Clique **Sauvegarder** après une modification.

Le badge **Connecté** veut dire qu'un jeton Google est enregistré. Si aucune propriété vérifiée de ce compte ne correspond à ton domaine, les données restent vides : vérifie la propriété dans Search Console avec le même compte Google, puis reconnecte.

## Données affichées dans le dashboard

### Carte « Search Console (vraie perf) » (éditeur d'article)

**Articles → un article → SEO → onglet « Audit »**

Jusqu'à 25 requêtes qui ont affiché l'article dans Google sur les 28 derniers jours, triées par clics : **Requête**, **Clics**, **Impr.**, **CTR**, **Pos.** (position moyenne). En tête, un « Score perf réelle » : clics × 2 + impressions / 100, plafonné à 100.

Sans GSC, la carte affiche « Connecte ton compte Google Search Console pour voir les vraies impressions et clics » et un bouton de connexion. Sans donnée sur la période : « Aucune donnée Search Console pour cet article sur la période. »

### Preuve Gridar (Tableau de bord)

Pour chaque article hébergé, Gridar enregistre une baseline d'impressions et de clics, puis la compare à J+30, J+60 et J+90 après publication. La carte **Preuve Gridar** additionne les impressions et clics gagnés ; les articles publiés avant Gridar sont exclus, les pertes sont comptées. Une baseline est capturée dès la connexion de GSC.

L'interrupteur **Page publique de preuve** crée un lien en lecture seule (`/proof/<token>`) à partager.

Dans **Articles**, un badge résume chaque article hébergé : `+N J+30` (impressions gagnées contre la baseline), **Pas indexe**, ou **J+30** tant que la première mesure n'est pas faite.

La preuve ne concerne que les articles hébergés chez Gridar.

### Détection de déclin

**Sidebar → Détection de déclin** : lit les impressions et clics GSC de chaque page. Sans GSC, la page affiche « GSC n'est pas configuré pour ce site » et te renvoie vers les paramètres. Détails dans [Outils SEO](seo-tools.md).

### Audit du site

- La composante **Fraîcheur** du score (100 moins le % de pages en déclin) n'existe qu'avec GSC ; sans elle, son poids passe aux autres composantes.
- La carte **Indexation Google** utilise l'URL Inspection de GSC pour donner le statut exact et la raison de non-indexation. Sans GSC, elle se contente de la recherche `site:` et se déclare approximative.

### Autopilote

L'autopilote repère les articles hébergés dont les impressions GSC ont baissé de 20 % ou plus sur 30 jours. En mode « Refresh first », il les rafraîchit avant de créer ; en mode « Balanced », il alterne un rafraîchissement pour deux créations.

### Vue multi-sites

La vue multi-sites signale, site par site, quand GSC manque (« GSC requis ») ou quand le jeton a expiré (« Reconnecter GSC »). Voir [Multi-domaines](multi-domain.md).

## Fraîcheur des données

- **Requêtes par article** et **détection de déclin** : lues chez Google à chaque ouverture, sans cache
- **Audit du site** : en cache 10 minutes
- **Latence Google** : Search Console publie ses données avec 2 à 3 jours de retard. Les derniers jours d'une période sont donc incomplets.

## Re-soumettre ton sitemap

Quand tu publies ou modifies beaucoup de pages, re-soumettre ton sitemap demande à Google de le relire au lieu d'attendre son prochain passage.

**API et MCP seulement** (pas de bouton dans le dashboard) :
- `POST /api/v1/sites/<id>/sitemap/submit/` avec `{sitemap_url?}`. Sans `sitemap_url`, Gridar prend `<ton domaine public>/sitemap.xml` et choisit la propriété qui contient vraiment ce sitemap.
- Outil MCP : `gridar_submit_sitemap`

Cette soumission consomme le quota Search Console de Google, pas de crédit Gridar.

Pour Bing et les autres moteurs qui suivent IndexNow, voir IndexNow dans [Outils SEO](seo-tools.md).

## Endpoints API

```bash
curl -H "Authorization: Bearer btb_xxx" \
  "https://api.gridar.app/api/v1/sites/12/gsc-queries/?slug=article-slug&days=28"
```

Paramètres : `slug` (obligatoire, le slug de l'article), `days` (1 à 90, 28 par défaut). Jusqu'à 25 requêtes.

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

Autres endpoints liés à GSC :

| Endpoint | Rôle |
|---|---|
| `GET /api/v1/sites/<id>/gsc-queries/?slug=&days=` | Requêtes GSC d'un article |
| `GET /api/v1/sites/<id>/content-decay/?days=` | Détection de déclin |
| `GET /api/v1/sites/<id>/index-coverage/?max_inspect=` | Couverture d'indexation (URL Inspection si GSC connectée) |
| `POST /api/v1/sites/<id>/sitemap/submit/` | Re-soumission du sitemap |
| `GET /api/v1/sites/<id>/proof/summary/` | Résumé de la preuve Gridar |

Outils MCP : `gridar_gsc_queries`, `gridar_get_content_decay`, `gridar_index_coverage`, `gridar_submit_sitemap`, `gridar_proof_summary`. Détails sur l'authentification : [API](api.md).

## Permissions

On demande le scope `webmasters`. Ce qu'on en fait, et rien d'autre :
- **Lire** tes données Search Console : impressions, clics, CTR, position, statut d'indexation par URL
- **Re-soumettre ton sitemap**, pour que Google le relise au lieu d'attendre son prochain passage

Ce qu'on ne fait pas, même si le scope l'autorise techniquement : supprimer un sitemap, ajouter ou retirer une propriété, toucher à tes utilisateurs GSC. Aucun appel de ce genre n'existe dans le code.

On ne peut pas non plus **demander l'indexation d'une URL** : Google ne fournit aucune API pour ça (l'Indexing API est réservée aux offres d'emploi et aux événements diffusés). Ça reste un geste manuel dans Search Console.

Si ta connexion date d'avant l'élargissement du scope (août 2026), ton autorisation est en lecture seule. La lecture continue de fonctionner ; seule la re-soumission de sitemap répond « Le jeton de ce site est en LECTURE SEULE (connecte avant l'elargissement du scope). Reconnecte Search Console pour autoriser la soumission de sitemap. »

Tu peux révoquer notre accès à n'importe quel moment :
- Côté Gridar : Paramètres → Search Console → **Déconnecter**. Le jeton est effacé ; l'URL de propriété reste enregistrée.
- Côté Google : <https://myaccount.google.com/permissions> → Gridar → Supprimer l'accès

## Refresh token

À la connexion, Gridar stocke un refresh token OAuth côté serveur. Il permet de générer un nouveau jeton d'accès sans te redemander de te connecter. Il n'est jamais renvoyé au navigateur.

Le refresh token reste valide tant que :
- Tu ne révoques pas l'accès
- Le compte Google reste actif
- Google ne l'invalide pas (par exemple après un changement de mot de passe)

Quand le jeton ne marche plus, il n'y a pas de bandeau global : chaque écran qui lit GSC le dit. La détection de déclin affiche « Token GSC expiré. Reconnecte-toi à Google Search Console dans les paramètres. », la carte de l'éditeur propose de nouveau la connexion, la vue multi-sites affiche « Reconnecter GSC ». Reconnecte depuis Paramètres → Search Console.

## Plusieurs sites (Agence)

Chaque site garde sa propre connexion. Pour chaque site : Paramètres → Search Console → **Connecter Google Search Console**. Le même compte Google peut servir pour tous tes sites, s'il a accès à chaque propriété ; Gridar trouve la bonne propriété pour chaque domaine.

## Limites

- **Pas de Bing Webmaster Tools**. Pour signaler tes URLs à Bing, utilise IndexNow (voir [Outils SEO](seo-tools.md)).
- **URL Inspection** : depuis le dashboard, 12 pages inspectées au plus par vérification, dans un budget de 14 secondes ; l'API va jusqu'à 100 (25 par défaut).
- **Les positions du Suivi des positions** ne viennent pas de GSC : la position moyenne GSC d'une requête n'est visible que dans la carte de l'éditeur.

## Dépannage

| Message | Cause | Action |
|---|---|---|
| « Google a refusé la connexion : ... » | Tu as refusé l'accès sur l'écran de Google | Relance la connexion et accepte |
| « Réponse OAuth invalide (code ou state manquant). » ou « State OAuth illisible. Relance la connexion GSC. » | Le retour de Google est incomplet | Relance la connexion depuis Paramètres → Search Console |
| « No refresh token returned. Revoke app access on Google and retry. » | Google n'a pas renvoyé de refresh token (accès déjà accordé) | Supprime l'accès de Gridar sur <https://myaccount.google.com/permissions>, puis reconnecte |
| « Aucune propriete Search Console verifiee ne correspond a ce site... » | Le compte connecté n'a pas de propriété vérifiée pour ce domaine | Vérifie la propriété dans Search Console avec le même compte, ou demande l'accès au propriétaire (souvent ton ancien dev ou ton agence), puis reconnecte |
| « Token GSC expiré » ou code `gsc_reauth_required` | Jeton révoqué ou expiré | Paramètres → Search Console → Reconnecter un autre compte |
| « Le compte Google connecte n'est pas proprietaire de la propriete ... » | La soumission de sitemap exige le rôle propriétaire | Connecte un compte propriétaire de la propriété |
| « Le jeton de ce site est en LECTURE SEULE ... » (code `gsc_scope_readonly`) | Connexion antérieure à l'élargissement du scope | Paramètres → Search Console → Reconnecter un autre compte |
| « Aucune donnée Search Console pour cet article sur la période. » | Article trop récent, pas encore affiché dans Google, ou latence de Google | Patiente, ou vérifie l'indexation dans l'Audit du site |
