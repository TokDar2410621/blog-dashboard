# FAQ

## Général

### C'est quoi exactement Gridar ?

Un SaaS SEO qui regroupe dans un même tableau de bord :

- la **génération d'articles par IA**, appuyée sur une recherche Google réelle du sujet ;
- l'**audit SEO** d'un article, de tout le site et de son indexation Google ;
- le **suivi de positions Google** sur tes mots-clés ;
- la **publication** vers WordPress, Shopify, Webflow, un blog hébergé par Gridar ou ta propre base de données ;
- la connexion à **Google Search Console** pour tes vrais clics et impressions ;
- une **API REST** et un **serveur MCP** pour piloter le tout depuis un script ou un assistant IA.

Le produit vise le marché québécois : l'éditeur vérifie le lexique FR-CA, et les positions des mots-clés en français sont relevées sur Google Canada.

### Pour qui ?

- PME et travailleurs autonomes qui veulent publier du contenu SEO sans tout écrire à la main.
- Agences qui gèrent plusieurs sites clients (le plan Agence couvre 5 sites).
- Développeurs qui veulent brancher la génération sur leur propre site, par l'API ou par un agent IA.

### Vous remplacez Surfer / Frase / Ahrefs ?

Gridar couvre la rédaction, l'audit on-page, l'indexation et le suivi de positions. Deux limites à connaître avant de comparer :

- **Pas d'index de backlinks.** Gridar ne mesure pas ton profil de liens. Garde Ahrefs, Majestic ou un équivalent pour ça.
- **Pas de volume de recherche par mot-clé.** La découverte de mots-clés s'appuie sur les suggestions de Google et sur la page de résultats réelle, jamais sur une estimation de trafic.

### Vous êtes québécois ?

Oui. Gridar est opéré par Arivex Studio, au Québec (voir la [politique de confidentialité](https://www.gridar.app/privacy)). Tu peux nous écrire à `tokamdarius@gmail.com`.

### Je peux essayer sans payer ?

Oui, de deux façons :

- **Le plan Essai** (gratuit) : 1 site, 1 article généré par mois, aucun mot-clé suivi.
- **Les outils publics, sans compte** : l'[audit SEO](https://www.gridar.app/audit) et les [outils](https://www.gridar.app/tools) (visibilité IA, écart concurrentiel, « Can I Rank? », calculateur ROI, etc.). Certains demandent ton courriel pour afficher le résultat complet.

## Connecter ton site

### Quels sont les modes de connexion ?

- **WordPress / Shopify / Webflow** : Gridar publie dans ton CMS via son API. Les articles vivent sur ton domaine. Aucun code à coller. Voir [WordPress](connect/wordpress.md), [Shopify](connect/shopify.md), [Webflow](connect/webflow.md).
- **Hébergé** : Gridar sert ton blog sur un domaine que tu choisis (ex. `blog.tonsite.ca`). Tu ajoutes un CNAME chez ton registrar. Réglage : Paramètres → Integrations → Blog public. Voir [Mode hébergé](connect/hosted.md).
- **Externe (lecture par API)** : ton propre frontend lit les articles avec un jeton d'API `btb_`. L'API est réservée aux plans Pro et Agence. Voir [Mode externe](connect/external.md).
- **Base de données externe** : tu fournis l'adresse PostgreSQL de ton site (champ DATABASE_URL à la création du site) et Gridar y écrit les articles.
- **Mode agent** : pour un site maison que Gridar ne peut pas publier lui-même. Les articles attendent en brouillon dans une file de construction ; un agent IA (Claude Code, par exemple, via le MCP) les pose dans le dépôt de ton site. Réglage : Paramètres → General → Mode de livraison.

Si tu as WordPress, Shopify ou Webflow, utilise le connecteur. Sinon, le mode hébergé ne demande aucun code.

Sans aucun de ces chemins, Gridar bloque la génération : le contenu resterait dans Gridar sans jamais atteindre ton site. Voir [Dépannage](troubleshooting.md).

### Et si j'ai Wix / Squarespace / Joomla / Drupal ?

Gridar n'a pas de connecteur pour ces plateformes. Deux options :

1. **Mode hébergé** sur un sous-domaine (`blog.tonsite.ca`) : il fonctionne quelle que soit la plateforme du site principal.
2. **Mode agent** si un développeur gère ton site et travaille avec un agent IA.

### Mon site WordPress est derrière Cloudflare avec Bot Fight Mode. Ça marche ?

Seulement si tu laisses passer les requêtes de Gridar. Elles s'identifient avec l'en-tête `User-Agent: BlogDashboard/1.0`. Dans Cloudflare : Security → WAF → Custom Rules → règle qui autorise ce User-Agent sur `/wp-json/`. Si ça bloque encore, écris à `tokamdarius@gmail.com`.

### Je peux changer de mode après coup ?

En partie :

- **Dans un même site**, tu peux activer le blog hébergé (Paramètres → Integrations → Blog public) ou passer en mode agent (Paramètres → General → Mode de livraison).
- **Pour WordPress, Shopify ou Webflow**, passe par les boutons de connexion de la page des sites. Gridar met à jour le site qui pointe déjà vers la même adresse, sinon il en crée un nouveau, qui compte dans la limite de sites de ton plan.

Gridar n'a pas d'outil de migration : les articles déjà stockés chez Gridar ne passent pas tout seuls dans ton nouveau CMS. Écris-nous si tu dois en déplacer beaucoup.

## Génération d'articles

### Combien de temps pour générer un article ?

L'écran annonce 1 à 2 minutes. La génération tourne en arrière-plan : tu peux changer de page, le dock en bas à droite suit l'avancement.

Si tu recharges la page, le dock perd le suivi. L'article peut quand même avoir été créé : vérifie la liste **Articles** avant de relancer.

Les longueurs proposées : Court (800 à 1200 mots), Moyen (1500 à 2000 mots), Long (2500 à 3500 mots).

### Quelle IA écrit les articles ?

Claude d'Anthropic (modèle `claude-sonnet-5`). Si Anthropic ne répond pas, Gridar bascule sur DeepSeek pour que la génération continue. La recherche web passe par Serper (résultats Google), avec Gemini en secours si Serper est indisponible.

### Les articles sont-ils originaux ?

Le prompt demande un article neuf, construit à partir des résultats de recherche, de ta base de connaissances et de la mémoire de ton site. Il ne demande jamais de réécrire une page existante. Personne ne peut garantir qu'aucune phrase ne ressemble à une source.

L'éditeur a une carte **Originalité + Détection IA** qui s'appuie sur Originality.ai. Ce service doit être activé côté serveur : si la carte affiche « Module non configuré », passe ton texte dans un vérificateur externe avant de publier.

### Les articles passent-ils les détecteurs IA ?

On ne le garantit pas. Le prompt applique des règles contre les tics d'écriture typiques des IA. Relis et ajoute ton expérience : c'est ce qui distingue ton article des autres.

### L'IA peut-elle inventer des faits ?

Oui, c'est un risque réel des modèles de langage. Ce que Gridar fait pour le réduire :

1. L'IA reçoit les résultats Google réels du sujet (via Serper).
2. Ta **base de connaissances** (Paramètres → Integrations) et la **mémoire du site** (Paramètres → Memoire (RAG)) lui donnent tes faits à toi.
3. L'audit d'article de l'éditeur liste les chiffres et affirmations qui n'ont aucune source à proximité.

Relis chaque article avant publication, surtout les chiffres, les prix et les noms.

### Je peux générer sans publier ?

Oui. Active **Aperçu seulement (ne pas publier)** dans le formulaire. L'article est généré et affiché à droite, rien n'est enregistré et ton quota n'est pas touché. Ce mode reste disponible même quand ton quota est épuisé.

### L'article généré est-il publié tout de suite ?

Ça dépend du mode de ton site :

- **WordPress, Shopify, Webflow** : oui, l'article part en ligne dès la fin de la génération. Utilise l'aperçu si tu veux relire avant.
- **Hébergé et base de données externe** : il est enregistré en **brouillon**. Tu le relis et le publies depuis **Articles**.
- **Mode agent** : il attend en brouillon dans la file de construction jusqu'à ce que l'agent le pose sur ton site.

### Le lexique FR-CA s'applique automatiquement ?

Non. La génération écrit en français sans filtre de lexique. Dans l'éditeur, la carte **Lexique FR-CA** repère les termes de France dans un article en français et propose l'équivalent québécois. Passe chaque article dedans avant de publier.

### Pourquoi le bouton « Générer » est grisé ?

Deux causes possibles :

- **« Livraison à configurer »** : aucun chemin ne mène le contenu jusqu'à ton site. Le bouton **Configurer la livraison** t'amène aux réglages.
- **« Quota épuisé · Achète des crédits »** : ton quota mensuel est atteint et ton solde de crédits est à zéro.

Détails et solutions dans [Dépannage](troubleshooting.md).

## Plans et facturation

### Quelles sont les limites de chaque plan ?

| Plan | Prix | Sites | Articles générés / mois | Mots-clés suivis | API REST et MCP |
|---|---|---|---|---|---|
| Essai | 0$ | 1 | 1 | 0 | non |
| Solo | 29.99$/mois | 1 | 8 | 10 | non |
| Pro | 89.99$/mois | 2 | 60 | 30 | 30 requêtes/h |
| Agence | 199.99$/mois | 5 | 200 | 100 | 200 requêtes/h |

Tarifs en CAD, TPS et TVQ ajoutées au paiement. Les limites s'appliquent au compte entier : les mots-clés suivis s'additionnent sur tous tes sites. Plus de 5 sites ou un volume sur mesure : bouton **Nous contacter** sur [/billing](https://www.gridar.app/billing). Détails dans [Plans et crédits](plans-credits.md).

### Que se passe-t-il quand je dépasse mon quota ?

Le bouton de génération affiche **« Quota épuisé · Achète des crédits »** et se désactive. Par l'API, la réponse est un `402` avec ce message :

```text
Quota mensuel atteint (8/8) et aucun crédit disponible. Achète des crédits sur /billing ou attends le début du mois prochain.
```

Trois options :

1. **Acheter un pack de crédits** : 10 crédits (25$), 50 crédits (99$) ou 200 crédits (299$). 1 crédit = 1 article généré.
2. **Passer à un plan supérieur** : la nouvelle limite compte dès que ton compte affiche le nouveau plan.
3. **Attendre le mois suivant** : le compteur repart à zéro le 1er du mois (heure UTC).

Les crédits ne sont consommés qu'une fois le quota mensuel épuisé. Tu ne perds donc rien à en acheter d'avance.

### Les crédits expirent ?

Non, jamais.

### Annulation = perte de mes articles ?

Tu annules depuis [/billing](https://www.gridar.app/billing) → **Gérer mon abonnement** (portail Stripe). L'accès continue jusqu'à la fin de la période payée ; la page affiche « Annulation effective le ... ». Ensuite, ton compte repasse au plan Essai.

- **WordPress, Shopify, Webflow, base de données externe** : tes articles sont chez toi et y restent.
- **Mode hébergé** : tes articles sont stockés chez Gridar. Récupère leur contenu **avant** la fin de ta période payée : l'API (`GET /api/v1/sites/<id>/articles/<slug>/`) est réservée aux plans Pro et Agence, et l'export CSV/JSON de la page **Articles** ne contient que les métadonnées (titre, slug, statut, catégorie, langue, vues, date). Écris-nous si tu as besoin d'aide pour l'export.

### Puis-je télécharger mes factures ?

Oui, dans le portail Stripe : [/billing](https://www.gridar.app/billing) → **Gérer mon abonnement**. Le bouton n'apparaît que sur un plan payant.

## API et assistants IA

### Gridar fonctionne avec ChatGPT ou Claude ?

Oui, via le serveur MCP de Gridar (`https://mcp.gridar.app/mcp`). Ton assistant peut lister tes sites, générer un article, auditer un texte, lire tes positions ou récupérer la file de construction du mode agent. Le serveur s'authentifie avec un jeton d'API `btb_` : il demande donc un plan Pro ou Agence. Voir [Intégrations](integrations.md).

### Comment obtenir un jeton d'API ?

Sur [/account/api-keys](https://www.gridar.app/account/api-keys). Le jeton complet ne s'affiche qu'une fois : copie-le tout de suite. Utilisation et endpoints : [API](api.md).

## Sécurité et données

### Où sont stockés mes identifiants de CMS ?

Dans la base de données du backend Gridar (`api.gridar.app`, hébergé sur Railway). L'API ne renvoie jamais au navigateur le mot de passe d'application WordPress, le jeton Shopify, le jeton Webflow ni le jeton Search Console : le tableau de bord voit seulement qu'une connexion existe. L'adresse d'une base de données externe fait exception : elle figure dans les données du site que reçoit ton propre compte.

Tu peux couper chaque accès de ton côté (WordPress → Profil → Application Passwords, Shopify → app personnalisée, Webflow → API access, Google → autorisations de ton compte). Search Console se déconnecte aussi depuis Paramètres → Search Console → **Déconnecter**.

### Vous avez accès à mes articles ?

Oui. En mode hébergé et en mode agent, les articles sont dans la base de Gridar, comme tes réglages (base de connaissances, profil d'auteur). Le texte passe aussi par les fournisseurs d'IA au moment de la génération, de la traduction et de l'audit.

### Vous utilisez mes articles pour entraîner un modèle ?

Gridar n'entraîne aucun modèle. Le produit appelle les API de fournisseurs tiers, chacun avec ses propres conditions :

- Anthropic (rédaction) ;
- DeepSeek : secours de la rédaction quand Anthropic ne répond pas, et moteur des outils gratuits sans compte (lecture du secteur et des requêtes à tester d'après ta page d'accueil publique, commentaires des résultats) ;
- Google Gemini (audit d'article, recherche de secours, traduction) ;
- OpenAI et Gemini (outil gratuit de visibilité IA) ;
- Voyage AI (mémoire du site) ;
- Serper (résultats Google) ;
- Originality.ai (détection IA et plagiat, quand le module est activé) ;
- Unsplash, Pexels et Pollinations (images).

### RGPD / Loi 25 ?

Pour exercer tes droits (accès, rectification, suppression du compte), écris à `tokamdarius@gmail.com`. La [politique de confidentialité](https://www.gridar.app/privacy) décrit le traitement et les délais. Le tableau de bord n'a pas de bouton de suppression de compte.

Certains sous-traitants traitent tes données hors du Canada. DeepSeek est une API chinoise. Dans le tableau de bord, il ne prend le relais que lorsqu'Anthropic ne répond pas : ton contenu ne lui est envoyé que dans ce cas. Les outils gratuits sans compte l'appellent à chaque analyse, avec le texte public de la page d'accueil analysée.

## Nouveautés

Ce qui sort est consigné dans le [journal des changements](changelog.md). Une idée ou un besoin : `tokamdarius@gmail.com`.

## Contact

- **Support général** : `tokamdarius@gmail.com`
- **Bug critique** : même email avec sujet `[URGENT]`
- **Demande Enterprise** : sujet `Plan Enterprise - demande sur mesure`
