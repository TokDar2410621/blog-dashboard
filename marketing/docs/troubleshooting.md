# Dépannage

Solutions aux problèmes courants. Si rien ici ne te débloque, écris à `tokamdarius@gmail.com` avec :
- Page où tu étais (URL)
- Action tentée
- Message d'erreur exact (capture si possible)
- Site ID concerné

## Connexion

### Je ne peux pas me connecter - "Identifiants invalides"

- Vérifie que tu utilises ton **email**, pas ton username (sauf si tu as créé le compte avec un username spécifique)
- Reset du mot de passe : pas encore d'UI, écris-nous, on reset à la main
- Vérifie le caps lock / clavier (ç, à, é peuvent perturber)

### Après login, je suis redirigé vers /login

- Token JWT expiré : déconnecte-toi explicitement (sidebar → Déconnexion) puis re-login
- Cache navigateur : Ctrl+Shift+R pour hard reload
- Cookies bloqués : autoriser les cookies pour `*.blog-dashboard.ca`

## Génération d'articles

### "Quota mensuel atteint"

Tu as épuisé ton quota mensuel + tu n'as pas de crédits. Solutions :

1. Acheter des crédits sur `/billing` (10/50/200 packs)
2. Upgrade ton plan (`/billing` → choisir un plan supérieur)
3. Attendre le 1er du mois (quota reset auto)

### "Cet article serait trop similaire à 'XYZ'"

Anti-cannibalisation. Soit :
- Reformule ton sujet pour être plus spécifique (ex : "CRM PME québécoises 2026" → "CRM PME québécoises avec intégration Bouygues 2026")
- Modifie l'article existant au lieu d'en créer un autre (souvent meilleure stratégie SEO)
- Utilise le champ **Titre forcé** (verbatim) qui skip l'anti-cannibalisation

### "Erreur génération: timeout"

L'IA a pris trop de temps (> 90 sec). Causes :
- Sujet trop large (réessayer avec un sujet plus précis)
- Anthropic surchargé (rare, réessaie dans 5 min)
- Serper down (re-sélectionne Méthode = Gemini comme fallback)

### L'article a été généré mais n'apparaît pas sur mon site

Selon le mode :

**WordPress** : permalink pas flushé. WP Admin → Réglages → Permalinks → "Save" (sans rien changer) → re-vérifie.

**Shopify** : article peut être en `draft` si Shopify a refusé `published_at`. Shopify Admin → Online Store → Blog posts → Manage articles → cherche ton article → set "Visible" si en Hidden.

**Webflow** : l'article est dans la collection mais le site n'a pas été republié. Webflow → Designer → "Publish" en haut à droite (publier le site live). Notre `?live=true` publie l'article ITEM mais Webflow exige aussi un publish manuel parfois pour certaines configs.

**Hébergé** : peut prendre 5-10 sec pour la régénération ISR. Recharge avec Ctrl+Shift+R.

### L'article publie OK mais pas de cover image

Pexels n'a pas trouvé d'image pour le sujet. Solutions :
- Modifie l'article via le PostEditor → ajoute une image manuellement (upload ou Pexels search)
- Active "Serper images" dans Site Settings (résultats Google Images au lieu de Pexels)

## Suivi des positions

### Mes mots-clés montrent "non classé" alors que je sais qu'on classe

- Position 1-100 seulement. Si on classe en page 11+ (position 101+), on ne crawl pas plus loin.
- Géo : on crawl depuis IP Canada par défaut. Si tu cibles France/Belgique, demande-nous d'ajuster
- Cache 24h : la position d'aujourd'hui n'est pas refresh à chaque visite. Force avec bouton "Snapshot maintenant"

### Mes mots-clés ne s'enregistrent pas - "Limite atteinte"

Tu as atteint la limite de mots-clés de ton plan (Free=0, Solo=10, Pro=30, Agence=100). Soit :
- Désactive les mots-clés moins importants (toggle dans la liste)
- Upgrade ton plan

## Audit SEO

### Le score d'audit reste à "0" / "calcul en cours"

Cache busting : ajoute `?force=1` à l'URL d'audit. Si toujours 0 après 60 sec, c'est probablement un timeout côté IA. Re-tente.

### L'audit dit "Pas de schema.org" mais j'en ai un

L'audit lit le `<head>` rendu de ton article. Si ton CMS rend le schema en client-side (JS), on ne le voit pas. Solutions :
- Ajoute le schema en server-side (recommandé pour le SEO de toute façon)
- Désactive le check schema dans Site Settings → Audit (skip)

## Connect WordPress

### "Identifiants WordPress invalides" mais ils marchent

- Username = ton **slug** WordPress, pas l'email. Trouvable dans WP Admin → Profil → en bas, "Username".
- Application Password : copie/colle SANS espaces (notre form les enlève auto, mais re-vérifie)
- WP version < 5.6 : Application Passwords pas supporté. Upgrade WP ou utilise un plugin tiers.

### "Site WordPress non détecté"

- REST API désactivée par un plugin de sécurité (Wordfence, Sucuri, iThemes...) → autoriser l'endpoint `/wp-json/`
- Hébergeur qui bloque les requêtes API → demander whitelist (ou changer d'hébergeur, recommandé : Kinsta, WP Engine, OVH)

## Connect Shopify

### "Token sans permission write_content"

Custom App → Configuration → Admin API → coche `write_content` → Save → si déjà installée, désinstalle + réinstalle pour générer un nouveau token avec le scope correct.

### Articles publient mais sans tags

`tags` doit être un array dans Shopify. Si tu envoies un string CSV, on le split mais Shopify peut le rejeter. Vérifie que tes tags sont des mots simples sans virgules internes.

## Connect Webflow

### "Cette collection n'a pas de champ Rich Text"

La collection que tu as choisie n'a aucun champ Rich Text. Webflow Designer → ouvre la collection → Add field → Rich Text. Reconnect.

Ou choisis une autre collection (par ex. la collection "Blog Posts" du template Blog Webflow standard qui en a un).

### Article publié mais 404 sur l'URL

Webflow n'a pas de page Template pour cette collection. Webflow Designer → Pages → CMS Pages → assure-toi qu'il y a un Template lié à la collection. Re-publish le site.

## API REST

### `401 Unauthorized` même avec mon token

- Format du header : `Authorization: Bearer btb_xxx` (avec espace après Bearer)
- Token révoqué : vérifie sur `/account/api-keys` → si `Révoqué`, créer un nouveau
- Token invalide : vérifie pas d'espace en trop au début/fin

### `403 Forbidden` - "Accès API réservé aux plans Pro et Agence"

Tu es sur Free ou Solo. Upgrade vers Pro (89.99$/mois) pour 30 req/h.

### `429 Too Many Requests`

Rate limit horaire dépassé. Header `Retry-After` indique en secondes quand tu peux réessayer. Solutions :
- Cache plus agressif côté toi (Next.js `revalidate: 600` ou Redis)
- Upgrade Agence (200 req/h au lieu de 30)
- Demande Enterprise pour rate-limit custom

## Bug rapporté souvent

### Le toast "Limite de sites atteinte" est invisible mais tu sais qu'il a fired

Ça arrivait sur la version < `2250372` à cause du Radix Dialog overlay qui occludait le toast. Fixé en mai 2026 - si tu vois encore le bug, fais un hard reload du dashboard (Ctrl+Shift+R) pour load la version corrigée.

### Sur mobile, je ne peux pas accéder à la sidebar

Une top bar avec hamburger a été ajoutée mai 2026. Si tu ne la vois pas → hard reload pour charger la dernière version.
