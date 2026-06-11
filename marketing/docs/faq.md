# FAQ

## Général

### C'est quoi exactement Gridar ?

Un SaaS qui combine **génération IA d'articles** + **audit SEO** + **suivi de positions Google** + **publication multi-CMS** dans une seule interface, avec un focus sur le marché québécois (lexique FR-CA, schemas LocalBusiness, géo Google Trends FR-CA).

### Pour qui ?

PME québécoises qui veulent un blog SEO sans engager une agence à 5k$/mois. Solo entrepreneurs qui veulent automatiser leur production de contenu. Agences qui gèrent les blogs de plusieurs clients.

### Vous remplacez Surfer / Frase / Ahrefs ?

Surfer et Frase écrivent en "français de France" (shopping, week-end, parking). Tes lecteurs québécois remarquent. Ahrefs ne génère pas d'articles - c'est un outil de research seul. On combine les 3 fonctions en français-québécois natif.

### Vous êtes québécois ?

Oui. Solo founder à Montréal. Tu peux nous écrire à `tokamdarius@gmail.com`.

## Connecter ton site

### Quelle est la différence entre les 5 modes de connexion ?

- **WordPress / Shopify / Webflow** : on publie DIRECT dans ton CMS via leur API. Articles à `tonsite.ca/...` → SEO 100 % sur ton domaine. Aucun code à coller.
- **Hébergé** : on te crée un sous-domaine `blog.tonsite.ca` qu'on sert avec notre Next.js. 1 CNAME à ajouter chez ton registrar. Aucun code, mais SEO légèrement diminué (sous-domaine vs domaine principal).
- **Externe** : tu as un site React/Next.js custom et veux les articles en subfolder (`tonsite.com/blog/...`). On stocke chez nous, ton frontend les fetch via API. Demande du code (3 fichiers à coller, 1 rewrite hébergeur).

Pour 80 % des users : si tu as un de ces 3 CMS, utilise-le. Sinon hébergé. Sinon externe.

### Et si j'ai Wix / Squarespace / Joomla / Drupal ?

Pas (encore) supportés directement. 2 options :
1. Mode hébergé (sous-domaine) - fonctionne universellement
2. Si tu peux ajouter un widget HTML iframe sur ton site, embed `<iframe src="https://blog.tondomaine.ca">` avec un Wix HTML element

Wix officiel + Squarespace officiel sont sur la roadmap (Q3 2026).

### Mon site WordPress est derrière Cloudflare avec Bot Fight Mode. Ça marche ?

Oui mais tu dois autoriser nos requêtes. Cloudflare → Security → WAF → Custom Rules → autoriser `User-Agent contains BlogDashboard` ou whitelist notre IP (changeante, demande à `tokamdarius@gmail.com` pour la liste).

### Je peux changer de mode après coup ?

Pas directement. Pour passer de hébergé → WordPress par ex., il faut :
1. Créer un nouveau site Gridar en mode WordPress
2. Migrer les articles via export CSV ou export-import API
3. Désactiver l'ancien site hébergé

C'est rare mais on peut t'aider via support.

## Génération d'articles

### Combien de temps pour générer un article ?

60-120 secondes pour un article de longueur Moyen. Plus long pour Long ou si beaucoup d'articles existants à comparer (anti-cannibalisation).

### Les articles sont-ils originaux ?

Oui. On utilise Claude Sonnet 4.6 avec un prompt qui demande explicitement du contenu original. On ne réécrit pas / résume pas un article existant - on génère un nouveau contenu à partir de la SERP + ton brief.

### Les articles passent-ils les détecteurs IA ?

Souvent oui mais on ne le garantit pas. Originality.ai, GPTZero, etc. ont des taux de détection variables. Notre stratégie :
- Style varié (questions rhétoriques, structure non-prévisible, transitions humaines)
- Vocabulaire FR-CA spécifique
- Faits / stats / citations qui ancrent le texte

Pour Google : ce qui compte n'est pas "écrit par humain ou IA" mais "contenu utile, original, expert". Nos articles passent l'algorithme Helpful Content Update parce qu'ils répondent à de vraies questions de manière structurée et expérimentée.

### L'IA peut-elle inventer des faits / citations ?

Risque réel des LLMs. On mitigate en :
1. Recherche SERP réelle (Serper) → l'IA voit les top 10 résultats Google et s'en inspire
2. Knowledge base de ton site (Site Settings) - l'IA respecte tes faits internes
3. Audit post-génération qui flag les claims numériques pour révision manuelle

Recommandation : relis chaque article avant publication. C'est rapide (5 min). On le rappelle dans l'UI.

### Je peux régénérer un article sans le publier ?

Oui. Active **Aperçu seulement (dry_run)** dans le formulaire de génération. L'article est généré et affiché à droite, mais PAS publié et PAS comptabilisé dans ton quota mensuel ni tes crédits.

### Le lexique FR-CA s'applique automatiquement ?

Oui pour les articles générés en FR. Pour les articles que tu écris manuellement dans l'éditeur, il y a un check "Lexique FR-CA" en bas qui flag les termes France à corriger.

## Plans et facturation

### Quelle différence entre Solo et Pro ?

Solo : 1 site, 8 articles/mois, 10 mots-clés, support 72h. Pour un solo-entrepreneur avec 1 blog à entretenir.

Pro : 2 sites, 60 articles/mois, 30 mots-clés, audit bulk + topic clusters + API REST, support 48h. Pour une PME qui veut publier 2-3 fois par semaine et piloter le SEO sérieusement.

Si tu hésites : commence Solo, tu peux upgrader à Pro en 1 clic à n'importe quel moment.

### Que se passe-t-il quand je dépasse mon quota ?

Bouton "Générer" devient désactivé avec un message "Quota épuisé · Achète des crédits". Tu peux :
1. Acheter un pack de crédits (10/50/200) - usage immédiat
2. Upgrade vers un plan supérieur - quota mensuel plus large dès le mois prochain
3. Attendre le 1er du mois - quota reset automatiquement

Tes crédits achetés ne sont consommés QUE quand le quota mensuel est épuisé. Donc tu ne perds rien à acheter des crédits "en avance".

### Les crédits expirent ?

Non, jamais. Tu achètes 200 crédits aujourd'hui, tu les utilises sur 24 mois si tu veux.

### Annulation = perte de mes articles ?

Non. Tes articles publiés sur ton CMS (WordPress / Shopify / Webflow) restent en place - on ne les touche pas. Tu perds juste l'accès au dashboard pour générer / auditer / tracker.

Pour le mode hébergé : tes articles sont chez nous. À la fin de ta période payée, on les conserve 90j (read-only) puis suppression. Tu peux les exporter via `GET /api/v1/sites/<id>/articles/?limit=200` avant.

### Puis-je télécharger mes factures ?

Oui via le portail Stripe : `/billing` → "Gérer mon abonnement" → onglet Factures. Téléchargement PDF.

## Sécurité et données

### Où sont stockés mes credentials de CMS ?

Chiffrés au repos dans notre Postgres (Railway, eu-west). On ne les expose JAMAIS via API ou logs. Seul le service backend a accès, le déchiffrement se fait en mémoire pour chaque requête sortante vers ton CMS.

### Vous avez accès à mes articles ?

Techniquement oui (admin database). Pratiquement non - pas de logs des contenus, pas d'analytics sur ce que tu écris. La seule fois où on lit le contenu, c'est pour l'audit SEO (anonymisé).

### Vous utilisez mes articles pour entraîner un modèle ?

Non. Aucun training, aucun fine-tuning sur tes données. On utilise les API publiques de Claude / Gemini sans sharing.

### RGPD / loi 25 ?

Loi 25 (Québec) compliant : tu peux exporter tes données via API + supprimer ton compte (tout est purgé sous 30j). Pas de transfert vers les US sans ton consentement explicite - Anthropic et Google sont nos sous-traitants documentés.

## Roadmap

### C'est quoi la suite ?

- Q3 2026 : adapter Wix + Squarespace
- Q3 2026 : intégration n8n native (custom node)
- Q4 2026 : multilingue avancé (Polylang/WPML pour WordPress)
- Q4 2026 : Branded reports (Agence) avec ton logo en PDF
- 2027 : analyse concurrentielle automatique (audit du site d'un compétiteur + comparaison)

Suggestions bienvenues : `tokamdarius@gmail.com`.

## Contact

- **Support général** : `tokamdarius@gmail.com`
- **Bug critique** : même email avec sujet `[URGENT]`
- **Demande Enterprise** : sujet `Plan Enterprise - demande sur mesure`
