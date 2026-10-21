# Connecter WordPress

Pour les sites WordPress 5.6+. Aucun plugin à installer : Gridar utilise les **Application Passwords** natifs de WordPress et l'API REST.

## Pré-requis

- WordPress 5.6 ou plus récent
- Un compte administrateur sur le site
- L'API REST accessible publiquement à `tonsite.ca/wp-json/` (c'est le défaut, sauf si un plugin de sécurité ou ton hébergeur la bloque)

## Étapes

Sur `/sites`, clique **WordPress**. Le dialog "Connecter ton site WordPress" compte trois étapes.

### 1. URL du site

Entre l'URL (ex : `https://monrestaurant.ca`, sans `/wp-admin`) et valide avec la flèche. Gridar appelle `tonsite.ca/wp-json/` et vérifie que l'API `wp/v2` répond.

Si c'est bon, l'écran affiche **WordPress détecté !** avec le nom du site et le nombre d'articles publiés. L'encart **Branding détecté** montre le logo, les couleurs et les polices lus sur ton site. Décoche **Appliquer** pour les régler plus tard.

### 2. Génère un Application Password dans WordPress

Le dialog te donne un lien direct vers `/wp-admin/profile.php` :

1. Descends jusqu'à la section **Application Passwords**.
2. Donne un nom à l'application. Le dialog suggère `BlogDashboard` ; n'importe quel nom fonctionne (ex : `Gridar`).
3. Clique **Add New Application Password**.
4. WordPress affiche un mot de passe au format `xxxx xxxx xxxx xxxx xxxx xxxx`. **Copie-le tout de suite** : il ne sera plus affiché.

Puis clique **J'ai généré mon Application Password**.

> Tu ne vois pas la section ? Vérifie que ton site est en HTTPS (ou ajoute `define('WP_ENVIRONMENT_TYPE', 'local');` dans `wp-config.php` si tu travailles en HTTP local). WordPress désactive les Application Passwords en HTTP par défaut.

### 3. Identifiants

- **Username WordPress** : le nom d'utilisateur du compte qui a créé l'Application Password.
- **Application Password** : colle la chaîne telle quelle, espaces compris.

Clique **Connecter**. Gridar appelle `tonsite.ca/wp-json/wp/v2/users/me` avec ces identifiants. Si ça passe : "Site WordPress connecté !", confettis, et tu arrives sur le dashboard du site.

## Ce qui se passe à la génération

Quand tu génères un article, Gridar envoie un `POST` à `tonsite.ca/wp-json/wp/v2/posts` avec :

- le titre et le slug ;
- le contenu, converti de Markdown en HTML ;
- l'extrait (excerpt) ;
- le statut `publish`.

L'article est **publié tout de suite** sur ton site, à l'URL que définit ton réglage de permaliens (ex : `tonsite.ca/2026/10/article-slug/`). Il n'y a pas d'étape brouillon pour les articles générés, y compris par l'autopilote. Pour relire avant, coche **Aperçu seulement (ne pas publier)** dans le formulaire de génération : rien n'est envoyé à WordPress.

## Limites du mode WordPress

- **Pas d'image à la une** : Gridar n'envoie pas de `featured_media`. Les images générées sont dans le corps de l'article.
- **Pas de catégories ni de tags** : la génération n'en envoie aucun. Ajoute-les dans WordPress après publication.
- **Titre en double possible** : le contenu envoyé commence par le titre en H1. Selon ton thème, le titre peut apparaître deux fois en haut de l'article.
- **Pas de meta description SEO** : Gridar remplit l'extrait WordPress, pas les champs de Yoast ou Rank Math.
- **Pas de section "À lire aussi"** : ce bloc de liens automatique n'est ajouté qu'en mode hébergé et en base externe.
- **Polylang / WPML** : non supportés. Gridar publie dans une seule langue par site ; avec un setup multilingue avancé, crée un site Gridar par langue.

## Changer les identifiants

Révoque l'ancien Application Password dans WordPress, crée-en un nouveau, puis refais la connexion depuis `/sites` avec la même URL. Gridar met à jour le site existant au lieu d'en créer un autre.

## Dépannage

| Message | Cause | Solution |
|---|---|---|
| "Identifiants WordPress invalides - vérifie l'username + Application Password." | Mauvais nom d'utilisateur ou mot de passe | Vérifie le nom d'utilisateur. Génère un nouvel Application Password |
| "WP REST API non disponible (HTTP ...)" ou "Ce site n'expose pas wp/v2 - REST API désactivée ?" | L'API REST est bloquée | Ton hébergeur ou un plugin de sécurité bloque `/wp-json/`. Demande qu'il soit autorisé |
| "Réponse invalide - ce ne semble pas être WordPress." | L'URL ne pointe pas vers un WordPress | Vérifie l'URL (le domaine principal, pas une sous-page) |
| "Site injoignable : ..." | Erreur DNS, certificat ou site hors ligne | Teste `curl https://tonsite.ca/wp-json/` dans un terminal |
| "Limite de sites atteinte (x/y)..." | Ton plan est plein | Supprime un site ou change de plan sur `/billing` |
| Article publié mais 404 | Permaliens pas régénérés | WordPress Admin → Réglages → Permaliens → **Enregistrer** sans rien changer |
