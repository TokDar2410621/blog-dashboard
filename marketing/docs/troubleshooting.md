# Dépannage

Solutions aux problèmes courants. Si rien ici ne te débloque, écris à `tokamdarius@gmail.com` avec :
- Page où tu étais (URL)
- Action tentée
- Message d'erreur exact (capture si possible)
- Site ID concerné (le nombre dans l'URL `/dashboard/<id>/...`)

## Connexion

### « Identifiants invalides »

- La connexion se fait en deux temps : ton **adresse courriel**, puis ton mot de passe.
- Si tu as créé ton compte avec Google ou GitHub, Gridar n'affiche pas de champ mot de passe : la page dit « Ton compte a été créé via un fournisseur externe » et propose seulement le bon bouton. Utilise-le.
- Vérifie le verrouillage des majuscules et la disposition du clavier (ç, à, é).

### J'ai oublié mon mot de passe

1. Sur [la page de connexion](https://www.gridar.app/login), entre ton courriel et clique **Continuer**.
2. À l'étape du mot de passe, clique **Mot de passe oublié ?**.
3. Gridar affiche toujours le même message : « Si un compte avec mot de passe est associé à cet email, un lien de réinitialisation vient d'être envoyé. »
4. Le lien expire après 24 heures.

Aucun courriel reçu après quelques minutes, même dans les indésirables ? Écris à `tokamdarius@gmail.com`. Un compte créé avec Google ou GitHub n'a pas de mot de passe à réinitialiser : reconnecte-toi avec le même service.

### « lien invalide ou expiré » sur la page de réinitialisation

Le lien a plus de 24 heures, ou il a déjà servi. Refais une demande depuis **Mot de passe oublié ?**.

### Je suis renvoyé vers /login, ou je vois « Votre session a expiré »

- Ta session dure 30 jours et se renouvelle quand tu utilises l'app. Après une longue absence, reconnecte-toi : Gridar te ramène sur la page où tu étais.
- Les cookies doivent être autorisés pour `gridar.app`. Un bloqueur de cookies ou une navigation privée stricte coupe la session.
- Si ça boucle encore : déconnecte-toi, fais un rechargement complet (Ctrl+Shift+R), puis reconnecte-toi.

## Génération d'articles

### Le bouton affiche « Livraison à configurer » (« Aucun chemin de livraison »)

Gridar ne trouve aucun moyen de faire arriver le contenu sur ton site. Le bandeau rouge affiche :

> Le contenu genere resterait dans Gridar sans atteindre ton site. Connecte un CMS (WordPress/Shopify/Webflow), active le mode agent, ajoute une base externe, heberge chez nous, ou branche l'API (mode externe).

Gridar bloque la génération plutôt que de stocker un article que personne ne verra. Solutions :

- Connecte ton CMS : [WordPress](connect/wordpress.md), [Shopify](connect/shopify.md) ou [Webflow](connect/webflow.md).
- Active le blog hébergé : bouton **Configurer la livraison** → Paramètres → Integrations → Blog public. Voir [Mode hébergé](connect/hosted.md).
- Site maison géré par un agent IA : Paramètres → General → Mode de livraison → « Via un agent ».

Par l'API, la même situation renvoie un `409` avec `"code": "delivery_blocked"`.

### Bandeau jaune « Livraison non confirmée »

Ton site n'a ni CMS, ni base externe, ni blog hébergé, mais ton compte a un jeton d'API actif : Gridar suppose le [mode externe](connect/external.md). La génération reste possible. Gridar ne peut pas vérifier que ton frontend affiche les articles : contrôle le rendu d'une page publiée.

### « Quota mensuel atteint » / « Quota épuisé · Achète des crédits »

Le message complet :

> Quota mensuel atteint (X/Y) et aucun crédit disponible. Achète des crédits sur /billing ou attends le début du mois prochain.

Ton quota du mois est utilisé et ton solde de crédits est à zéro. Solutions :

1. Acheter des crédits : le bloc « Génération bloquée » propose **+10 crédits · 25$** et **+50 crédits · 99$**, et [/billing](https://www.gridar.app/billing) offre aussi 200 crédits pour 299$.
2. Passer à un plan supérieur sur [/billing](https://www.gridar.app/billing).
3. Attendre le 1er du mois (heure UTC) : le compteur repart à zéro.

L'option **Aperçu seulement (ne pas publier)** fonctionne même quota épuisé : elle ne consomme rien.

### « Cet article serait trop similaire (NN%) a un article existant »

Protection anti-cannibalisation : le titre prévu ressemble trop au titre d'un de tes articles existants. Soit :
- Précise ton sujet (ex : « CRM pour PME québécoises » → « CRM pour PME québécoises qui facturent à l'heure »).
- Modifie l'article existant au lieu d'en créer un autre (souvent la meilleure option SEO).
- Remplis le champ **Titre forcé (optionnel)** : avec un titre forcé, Gridar saute ce contrôle. Tu prends alors le risque de deux pages en concurrence sur la même requête.

### « Erreur generation: Recherche web indisponible »

Serper (la recherche Google) a échoué, puis Gemini, qui prend le relais automatiquement, a échoué aussi. Réessaie dans quelques minutes. Pas besoin de changer la **Méthode de recherche** à la main : la bascule vers Gemini se fait toute seule.

### « Reponse LLM vide (Anthropic + fallback DeepSeek indisponibles) »

Les deux fournisseurs d'IA de rédaction n'ont pas répondu. Réessaie dans quelques minutes. Si l'erreur persiste, écris-nous.

### « Generation failed », sans autre détail, ou le dock affiche une tâche interrompue

La réponse du serveur n'est pas arrivée jusqu'à ton navigateur (délai dépassé, connexion coupée, page rechargée pendant la génération). L'article a pu être créé quand même : ouvre **Articles** et vérifie avant de relancer, pour ne pas consommer deux fois ton quota.

### « La langue "xx" n'est pas autorisee pour ce site »

La langue choisie n'est pas activée pour ce site. Ajoute-la dans Paramètres → Langues, ou choisis une langue de la liste.

### L'article a été généré mais n'apparaît pas sur mon site

Selon le mode :

**Hébergé ou base de données externe** : l'article généré est enregistré en **brouillon**. Ouvre-le depuis **Articles**, relis-le et publie-le. En mode hébergé, les pages du blog sont gardées en cache jusqu'à 5 minutes : recharge après ce délai.

**Mode agent** : l'article attend en brouillon dans la file de construction. Il apparaît sur ton site quand l'agent l'a posé dans ton dépôt et déployé.

**WordPress** : l'article est publié en ligne directement. S'il renvoie une 404, WP Admin → Réglages → Permaliens → **Enregistrer** (sans rien changer), puis recharge.

**Shopify** : l'article est publié avec une date de publication. Vérifie dans Shopify Admin → Online Store → Blog posts qu'il est **Visible** et qu'il est dans le blog choisi à la connexion.

**Webflow** : Gridar crée l'élément directement sur le site en ligne. Une 404 vient en général de la configuration Webflow : la collection n'a pas de page modèle (Pages → CMS Pages), ou le site n'a jamais été publié. Corrige puis publie le site depuis le Designer.

### Mon article « Planifié » n'est pas passé en ligne à l'heure prévue

- **WordPress** : Gridar envoie le statut « planifié » à WordPress, sans la date choisie. Pour planifier un article WordPress, fixe la date directement dans WP Admin.
- **Autres modes** : si l'heure est passée et que l'article est toujours « Planifié », ouvre-le dans l'éditeur, mets le statut **Publié** et enregistre. Signale-le-nous aussi.

### L'image de couverture ne colle pas au sujet

Gridar choisit une photo Unsplash, et à défaut une image générée par IA (Pollinations). Le résultat peut tomber à côté. Dans l'éditeur, carte **Image de couverture** : colle une URL, ou cherche via **Pexels**, **Google Images** ou **Générer (IA)**.

## Suivi des positions

### Mon mot-clé affiche « Hors top 100 » alors que je sais qu'on classe

- Gridar lit les 100 premiers résultats Google. Au-delà, le mot-clé est « Hors top 100 ».
- Le pays dépend de la **langue du mot-clé** : français → Google Canada, anglais → Google États-Unis, espagnol → Google Espagne. Un mot-clé anglais visé au Canada est donc relevé aux États-Unis.
- Gridar cherche l'URL cible exacte si tu en as indiqué une, sinon le premier résultat qui contient ton domaine. Vérifie que le domaine du site (Paramètres → General) correspond à celui qui apparaît dans Google.
- Ta position perso dans Google (connecté, géolocalisé, historique) diffère souvent de la position neutre que Gridar relève.

### Le mot-clé affiche « A confirmer » au lieu d'une position

Gridar n'affiche un `#X` que si la position est constante : il regarde les 5 derniers relevés, et le mot-clé doit être trouvé dans au moins la moitié. La position affichée est alors la médiane. Sinon, tu vois « A confirmer » et la meilleure position déjà vue (« deja vu #X »). Lance quelques relevés de plus pour stabiliser la mesure.

### « Jamais releve », ou la date « Verifie ... » reste vieille

Clique **Snapshot maintenant** : Gridar relève tous les mots-clés actifs du site et affiche « N mots-clés traités, M positionnés ». Le relevé automatique quotidien dépend d'une tâche planifiée côté serveur : si la date passe en ambre, relance un snapshot à la main.

### « Limite de mots-clés atteinte »

Le message complet :

> Limite de mots-clés atteinte (X/Y). Mets ton plan à niveau sur /billing ou retire un mot-clé pour en suivre un autre.

Limites : Essai 0, Solo 10, Pro 30, Agence 100. Le compte additionne les mots-clés de **tous** tes sites. Soit :
- Retire les mots-clés les moins utiles. Attention : retirer un mot-clé supprime aussi son historique de positions.
- Passe à un plan supérieur.

## Search Console

### Le bouton « Connecter Google Search Console » échoue

Selon le message :

- **« Google a refusé la connexion : access_denied »** : tu as annulé l'écran Google, ou le compte choisi n'a pas accepté l'accès. Relance et accepte.
- **« Réponse OAuth invalide (code ou state manquant). »** : le retour de Google est incomplet. Relance la connexion depuis Paramètres → Search Console.
- **« No refresh token returned. Revoke app access on Google and retry. »** : Google a déjà donné un accès à Gridar par le passé. Retire Gridar des autorisations de ton compte Google, puis reconnecte.
- **« Token exchange failed: ... »** : le code de Google ne sert qu'une fois. Relance la connexion depuis le début.

### « Connecté », mais aucune donnée Search Console

Si la carte Search Console affiche « Ton compte Google est lié. » sans nom de propriété, Gridar n'a trouvé aucune propriété vérifiée qui correspond à ton domaine dans ce compte Google. Solutions :
- Vérifie la propriété dans [Search Console](https://search.google.com/search-console/) avec **le même compte Google**.
- Inscris l'URL exacte dans le champ **Property URL** : `https://tonsite.com/` (avec le slash final) ou `sc-domain:tonsite.com`.
- Clique **Reconnecter un autre compte** pour refaire le lien.

### « Token GSC expiré » / « Reconnecte GSC »

Google a révoqué ou fait expirer l'accès. Paramètres → Search Console → **Reconnecter un autre compte**, avec le compte qui possède la propriété.

### « GSC n'est pas configuré pour ce site »

L'URL de propriété manque. Remplis **Property URL** dans Paramètres → Search Console, enregistre, puis connecte ton compte Google.

## Audit SEO

### « Erreur audit IA » dans l'éditeur

- Le titre et le contenu doivent être remplis (sinon : « Titre et contenu requis »).
- L'audit IA passe par Gemini. Si Gemini ne répond pas, réessaie plus tard.
- L'audit lit les 5000 premiers caractères du contenu. Sur un article long, la fin n'est pas évaluée.

### L'audit du site s'affiche, mais PageSpeed reste en chargement

La page affiche d'abord ce qui vient de ta base (score, mots-clés, déclin), puis complète avec PageSpeed Insights quand Google répond. PageSpeed peut prendre longtemps ou échouer. Recharge plus tard si la carte reste vide.

### « Aucune donnee mesurable encore »

Le score n'a rien à mesurer. Connecte Search Console et ajoute des mots-clés à suivre.

### « Erreur indexation » ou statut d'indexation incomplet

Le bouton **Verifier l'indexation** compare ton sitemap à ce que Google montre, puis inspecte jusqu'à 12 URL via Search Console. Sans Search Console connecté, tu n'as pas le statut exact ni la raison de non-indexation. En cas d'erreur, vérifie que ton sitemap est accessible, puis relance.

## Connect WordPress

### « Identifiants WordPress invalides - vérifie l'username + Application Password. »

- Username = le **nom d'utilisateur** du compte WordPress qui a créé l'Application Password (WP Admin → Profil).
- Application Password : colle-le tel quel, espaces compris. Ton mot de passe habituel de connexion à WordPress ne fonctionne pas ici.
- WordPress antérieur à 5.6 : les Application Passwords n'existent pas. Mets WordPress à jour.

### « WP REST API non disponible » / « Ce site n'expose pas wp/v2 - REST API désactivée ? »

- Un plugin de sécurité (Wordfence, Sucuri, iThemes...) bloque l'API REST : autorise `/wp-json/`.
- Un pare-feu ou Cloudflare bloque les robots : autorise le User-Agent `BlogDashboard/1.0`.
- Vérifie dans ton navigateur que `https://tonsite.ca/wp-json/` répond.

### « Réponse invalide - ce ne semble pas être WordPress. » / « Site injoignable »

L'URL ne mène pas à un WordPress joignable. Entre l'adresse du site sans `/wp-admin` (ex : `https://monsite.ca`), en `https`.

### « Limite de sites atteinte »

Le message complet :

> Limite de sites atteinte (X/Y). Mets ton plan à niveau sur /billing pour ajouter un site supplémentaire.

Chaque nouveau site compte, quel que soit le mode : Essai 1, Solo 1, Pro 2, Agence 5. Reconnecter un site déjà connu ne compte pas.

## Connect Shopify

### « Token sans la permission 'write_content' »

Custom App → Configuration → Admin API → coche `write_content` → Save. Si l'app est déjà installée, réinstalle-la pour obtenir un nouveau jeton avec ce scope.

### « Token invalide ou révoqué » / « Domaine Shopify introuvable »

- Colle le **Admin API access token** de la custom app (un jeton trop court donne « Token Shopify trop court »).
- Le domaine attendu est le domaine technique `monstore.myshopify.com`, pas ton domaine personnalisé.

### « Aucun blog Shopify sélectionné »

Reconnecte la boutique et choisis le blog où publier.

### Les tags ne sortent pas comme prévu

Gridar envoie les tags à Shopify séparés par des virgules. Un tag qui contient lui-même une virgule est donc coupé en deux. Utilise des tags simples, sans virgule.

## Connect Webflow

### « Cette collection n'a pas de champ de type RichText »

La collection choisie n'a aucun champ Rich Text pour le corps de l'article (le sélecteur l'indique par « Pas de Rich Text »). Webflow Designer → ouvre la collection → Add field → Rich Text, puis reconnecte. Ou choisis une autre collection, par exemple « Blog Posts » du modèle Blog de Webflow.

### « Token Webflow invalide ou expiré » / « Token Webflow révoqué »

Crée un nouveau Site Token dans Webflow (Project Settings → Apps & Integrations → API access), puis reconnecte le site.

### Article publié mais 404 sur l'URL

Webflow n'a pas de page modèle pour cette collection. Webflow Designer → Pages → CMS Pages → crée ou lie un modèle à la collection, puis publie le site.

## API REST

### `401` : « Token invalide ou révoqué. » / « Format de token invalide. »

- En-tête attendu : `Authorization: Bearer btb_xxx` (un espace après `Bearer`).
- « Format de token invalide. » : le jeton ne commence pas par `btb_`. Vérifie qu'il n'y a pas d'espace en trop au début ou à la fin.
- Jeton révoqué : sur [/account/api-keys](https://www.gridar.app/account/api-keys), un jeton marqué **Révoqué** ne marche plus. Crées-en un nouveau.
- Sans en-tête du tout, la réponse est « Session ou Bearer token requis. ».

### `403` : « Accès API réservé aux plans Pro et Agence. Mets à niveau sur /billing. »

Ton compte est sur Essai ou Solo. Passe à Pro (89.99$/mois, 30 requêtes/h) ou Agence (199.99$/mois, 200 requêtes/h). Même règle pour le serveur MCP.

### `429 Too Many Requests`

Limite horaire dépassée (fenêtre glissante d'une heure). L'en-tête `Retry-After` donne le nombre de secondes à attendre. Solutions :
- Mets les réponses en cache de ton côté (ex. Next.js `revalidate`).
- Passe à Agence (200 requêtes/h au lieu de 30).
- Besoin de plus : écris-nous, sujet `Plan Enterprise - demande sur mesure`.

### `402` sur `POST /generate/`

Quota mensuel atteint et aucun crédit. Le corps contient `"quota_exceeded": true`. Voir « Quota mensuel atteint » dans la section Génération d'articles, plus haut.

### `409` avec `"code": "delivery_blocked"`

Aucun chemin de livraison pour ce site. Voir « Livraison à configurer » dans la section Génération d'articles, plus haut.

### `422` : « Onboarding incomplet »

La génération par API exige deux champs remplis, listés dans `missing_fields` :
- `business_model` : Paramètres → General → Modèle d'affaires.
- `author_bio` : Paramètres → Auteur (EEAT).

### `409` avec `"code": "gsc_scope_readonly"` sur la soumission de sitemap

Ton site a été connecté à Search Console en lecture seule. Reconnecte Search Console (Paramètres → Search Console) pour autoriser la soumission de sitemap.

## Facturation

### Après le paiement Stripe, je n'arrive pas sur Gridar, ou mon plan n'a pas changé

1. Reviens sur [https://www.gridar.app/billing](https://www.gridar.app/billing) et recharge la page.
2. Ton plan et tes crédits s'appliquent quand Stripe confirme le paiement à Gridar. Vérifie « Ton plan actuel » et « Crédits achetés ».
3. Si rien n'a changé, écris à `tokamdarius@gmail.com` avec le courriel utilisé pour payer : on aligne ton compte sur Stripe.

### Je ne vois pas « Gérer mon abonnement »

Le bouton n'apparaît que sur un plan payant actif. Sur le plan Essai, il n'y a rien à gérer : choisis un plan avec **Souscrire**.
