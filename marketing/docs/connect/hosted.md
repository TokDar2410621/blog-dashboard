# Mode hébergé (Blog clé-en-main)

Pour les sites sans CMS (React, Vue, Astro, Next.js ou autre), ou pour qui ne veut rien toucher chez son dev. Gridar stocke les articles et les sert avec son propre frontend Next.js, sur ton sous-domaine. **Une seule manipulation chez toi** : un CNAME chez ton registrar.

## Comment ça marche

1. Tu crées le site dans Gridar.
2. Tu choisis un sous-domaine pour le blog (ex : `blog.tonsite.ca`) et tu cliques **Activer** : Gridar l'enregistre sur Vercel.
3. Tu ajoutes un CNAME chez ton registrar vers `cname.vercel-dns.com`. Vercel génère le certificat SSL une fois le DNS propagé.
4. Tu génères des articles, tu les publies, et ils apparaissent à `blog.tonsite.ca/article-slug`.

Les articles vivent dans la base de Gridar et sont servis sur ton sous-domaine. Le blog reprend le logo, les couleurs et les polices de **Paramètres → Branding**.

## Étapes

### 1. Crée le site dans Gridar

Sur `/sites`, clique **Blog clé-en-main**. Le dialog "Ajouter un site" demande :

- **Nom du site** (obligatoire) : libellé interne (ex : "Mon blog SaaS").
- **DATABASE_URL** (optionnel) : laisse vide. Le remplir fait passer le site en base externe (voir [Mode externe](external.md)).
- **Domaine** (optionnel) : ton domaine principal (ex : `tonsite.ca`). Lis la limite sur les URL canoniques plus bas avant de le remplir.

Clique **Ajouter le site**. Le site apparaît dans la liste : clique **Ouvrir**.

Ce dialog ne scanne pas ton branding. Lance le scan depuis **Paramètres → Branding → Scanner** (il lit la page du champ Domaine), ou remplis les champs à la main.

Tant que le domaine du blog public n'est pas activé, la génération est bloquée ("Aucun chemin de livraison").

### 2. Active le sous-domaine

**Paramètres → Intégrations**, carte **Blog public (frontend hébergé)**.

Dans **Domaine du blog public**, entre le sous-domaine (ex : `blog.tonsite.ca`) et clique **Activer**. Passe bien par ce bouton : il enregistre le domaine chez Vercel. **Sauvegarder** seul enregistre le champ sans configurer Vercel.

L'écran affiche l'enregistrement à créer :

```text
Type     CNAME
Nom      blog
Valeur   cname.vercel-dns.com
```

Va chez ton registrar (GoDaddy, OVH, Namecheap, Cloudflare DNS, ...) → réglages DNS → ajoute l'enregistrement.

### 3. Vérification

L'écran vérifie le DNS toutes les 8 secondes, tant que la page reste ouverte. Quand c'est bon, il affiche "Blog en ligne sur blog.tonsite.ca". Le message serveur annonce en général 5 à 30 minutes de propagation.

Pour vérifier toi-même :

- `nslookup blog.tonsite.ca` (Windows) ou `dig blog.tonsite.ca` (Mac/Linux) doit renvoyer la cible Vercel.
- `https://blog.tonsite.ca` affiche la page d'accueil du blog avec ton branding.

Pour changer de sous-domaine, clique **Retirer**, puis active le nouveau.

### 4. Génère et publie ton premier article

Sidebar → **Générer un article** → suis le formulaire ([Générer un article](../generate-article.md)).

En mode hébergé, l'article arrive en **brouillon**. Le blog public ne montre que les articles publiés : ouvre **Articles**, clique **Modifier** sur l'article, puis **Publier**. Il est ensuite servi à `https://blog.tonsite.ca/article-slug`.

## Ce que sert le blog hébergé

- **Page d'accueil** avec la liste des articles publiés, et une page par article à `/article-slug`.
- **`/sitemap.xml`**, **`/rss.xml`** et **`/robots.txt`** générés à la volée.
- **Cache de 5 minutes** sur les données des articles (ISR Next.js) : une modification peut mettre jusqu'à 5 minutes à apparaître.
- **Mode sombre** selon le réglage du système du visiteur.
- **Profil auteur** (JSON-LD Person et signature en pied de page) tiré de **Paramètres → Auteur (EEAT)**.
- **Fichier de clé IndexNow** servi automatiquement à la racine du sous-domaine : rien à héberger. Quand un article passe en publié via l'API ou le MCP, Gridar soumet son URL à IndexNow (Bing, Yandex, Seznam, Naver ; Google ne participe pas à IndexNow). La publication depuis l'éditeur du dashboard ne déclenche pas cette soumission.

## Limites

**Sous-domaine.** Google traite un sous-domaine comme un site distinct :

- le sous-domaine est indexé et peut recevoir du trafic de recherche ;
- les liens du blog vers ton site principal transmettent de la valeur ;
- les articles ne renforcent pas directement ton domaine racine sur leurs mots-clés.

Pour des articles sur le domaine racine (`tonsite.com/blog/...`), passe par le [mode externe](external.md) ou par un CMS connecté ([WordPress](wordpress.md), [Shopify](shopify.md), [Webflow](webflow.md)).

**URL canoniques.** Le blog hébergé construit ses URL canoniques, son sitemap, son flux RSS et la ligne `Sitemap:` de son `robots.txt` à partir du champ **Domaine** (Paramètres → Général), pas du domaine du blog public. Si ce champ contient `tonsite.ca` alors que le blog vit sur `blog.tonsite.ca`, ces URL pointent vers `https://tonsite.ca/article-slug`, une adresse que ton site principal ne sert pas. Après ta première publication, ouvre le code source d'un article et vérifie la balise `<link rel="canonical">`.

**Lien "Voir sur le site".** Dans **Articles**, cette option du menu d'un article n'existe que pour les sites hébergés. Elle ouvre `https://blog.tonsite.ca/blog/article-slug`, alors que le blog hébergé sert les articles à `https://blog.tonsite.ca/article-slug` : retire `/blog` de l'adresse ouverte.

**Pas de sous-chemin.** La carte des Intégrations mentionne une "inclusion sous-chemin (`tonsite.ca/blog`)", mais l'activation n'accepte qu'un nom d'hôte. Pour `tonsite.ca/blog`, vois le [mode externe](external.md).

## Dépannage

| Symptôme | Cause | Solution |
|---|---|---|
| Bouton **Livraison à configurer** grisé sur la page de génération | Domaine du blog public pas activé | Paramètres → Intégrations → **Activer** |
| `https://blog.tonsite.ca` renvoie 404 ou "Domain not configured" | DNS pas encore propagé | Attends, puis reteste avec `nslookup` ou `dig` |
| "VERCEL_API_TOKEN ou VERCEL_PROJECT_ID non configure sur le serveur. Contacte le support." | Configuration côté Gridar | Écris au support |
| "Domaine invalide. Ex: blog.tondomaine.com" | Saisie avec espace ou sans point | Entre un nom d'hôte seul, sans `https://` ni chemin |
| Erreur de configuration chez Vercel | CNAME mal saisi | Vérifie : type CNAME, nom = juste le sous-domaine (`blog`, pas `blog.tonsite.ca`), valeur = `cname.vercel-dns.com` |
| L'article n'apparaît pas sur le blog | Article encore en brouillon, ou cache de 5 minutes | Publie-le depuis **Articles**, puis attends quelques minutes |
| Logo ou couleurs absents | Pas de scan, ou scan sans résultat | Paramètres → Branding → **Scanner**, ou remplis les champs à la main |
| Articles pas indexés par Google | Sitemap pas soumis | Soumets `https://blog.tonsite.ca/sitemap.xml` dans Google Search Console, après avoir vérifié les URL qu'il contient (voir Limites) |
