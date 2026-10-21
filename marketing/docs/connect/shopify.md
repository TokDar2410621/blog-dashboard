# Connecter Shopify

Pour les boutiques Shopify. Gridar publie les articles dans le blog natif de ta boutique via l'Admin API, sur ton domaine.

## Pré-requis

- Une boutique Shopify active
- Le droit de créer une app dans l'admin de la boutique
- Au moins un blog dans la boutique (Shopify en crée un par défaut, "News")

## Étapes

### 1. Crée une Custom App dans Shopify

Le dialog Gridar rappelle ces étapes et pointe vers la doc Shopify :

1. Shopify Admin → Settings → **Apps and sales channels** → **Develop apps**
2. **Create an app**, nomme-la `Gridar`
3. Onglet **Configuration** → Admin API access scopes → coche `write_content`
4. **Install app**, puis copie l'**Admin API access token** (il commence par `shpat_`). Copie-le tout de suite : Shopify ne l'affiche qu'une fois.

### 2. Connecte dans Gridar

Sur `/sites`, clique **Shopify**. Le dialog "Connecter ta boutique Shopify" compte deux étapes.

**Étape 1** : remplis

- **Domaine .myshopify.com** : le domaine technique (`monstore.myshopify.com`), pas ton domaine custom. Gridar accepte aussi `https://monstore.myshopify.com/admin` ou `monstore` seul, et en extrait le bon domaine.
- **Admin API access token** : le `shpat_...` collé tel quel.

Clique **Vérifier la connexion**. Gridar appelle `shop.json` pour valider le token, puis `blogs.json` pour lister tes blogs.

**Étape 2** : l'écran affiche "Connecté à {nom de la boutique}" avec le domaine public, la devise et la locale. L'encart **Branding détecté** montre le branding lu sur ton domaine public (ou sur `.myshopify.com` si tu n'en as pas). Décoche **Appliquer** pour le régler plus tard.

Choisis le blog qui reçoit les articles (le premier est présélectionné), puis clique **Connecter**. Tu arrives sur le dashboard du site.

## Ce qui se passe à la génération

Gridar envoie un `POST` à `admin/api/2024-10/blogs/<id>/articles.json`. L'article est **publié tout de suite** (le champ `published_at` est rempli), y compris quand il vient de l'autopilote. Il prend le template Liquid de ta boutique : même typo, mêmes header et footer que ton storefront.

URL finale : `taboutique.com/blogs/<handle-du-blog>/<handle-de-l-article>` (ex : `/blogs/news/...` pour le blog "News"), ou `monstore.myshopify.com/blogs/...` sans domaine custom.

Pour relire avant publication, coche **Aperçu seulement (ne pas publier)** dans le formulaire de génération : rien n'est envoyé à Shopify.

## Champs Shopify utilisés

| Champ Gridar | Champ Shopify | Note |
|---|---|---|
| Titre | `title` | |
| Slug | `handle` | |
| Contenu | `body_html` | Markdown converti en HTML |
| Extrait | `summary_html` | Apparaît dans les listes d'articles |
| Auteur | `author` | **Auteur par défaut** du site (Paramètres → Auteur), sinon "Admin" |
| Tags | `tags` | Liste séparée par des virgules |
| Couverture | `image.src` | URL de l'image de couverture trouvée à la génération |
| Statut | `published_at` | Rempli = publié |

## Limites

- **Pas de catégories** : Shopify n'a que des tags. Les topic clusters restent calculés dans Gridar.
- **Titre en double possible** : le contenu envoyé commence par le titre en H1. Selon ton thème, le titre peut apparaître deux fois.
- **Suppression définitive** : supprimer un article depuis Gridar le supprime dans Shopify, sans corbeille.
- **Domaine custom** : Gridar le lit dans la réponse de Shopify et s'en sert comme domaine du site. Sans domaine custom, il garde `monstore.myshopify.com`.

## Changer le token ou le blog

Refais la connexion depuis `/sites` avec le même domaine `.myshopify.com` : Gridar met à jour le token et le blog choisi sur le site existant.

## Dépannage

| Message | Cause | Solution |
|---|---|---|
| "Token invalide ou révoqué - vérifie le Admin API access token." | Token mal copié ou app désinstallée | Génère un nouveau token dans la custom app et recolle-le |
| "Token Shopify trop court - colle bien le Admin API access token." | Copie tronquée | Recopie le token complet |
| "Domaine Shopify introuvable - vérifie l'orthographe du sous-domaine .myshopify.com." | Faute de frappe ou boutique fermée | Vérifie `monstore.myshopify.com` |
| "Token sans la permission 'write_content' - re-créé la custom app avec le scope write_content." | Scope manquant | Custom App → Configuration → coche `write_content` → Save → réinstalle l'app |
| "Cette boutique n'a aucun blog." | Aucun blog dans la boutique | Shopify Admin → Online Store → Blog posts → Manage blogs → crée un blog |
| "Limite de sites atteinte (x/y)..." | Ton plan est plein | Supprime un site ou change de plan sur `/billing` |
