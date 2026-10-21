# Générer un article avec l'IA

Tu donnes un sujet. Gridar cherche sur Google, choisit un titre et un angle, rédige l'article dans la langue choisie, puis le livre à ton site selon son mode de connexion. Compte 1 à 2 minutes par article.

La page se trouve dans la barre latérale : **Générer un article**.

## Avant tout : le contrôle de livraison

Gridar vérifie d'abord que le contenu généré peut atteindre ton site. Si ce n'est pas le cas, un encadré s'affiche en haut de la page :

| Encadré | Cause | Effet |
|---|---|---|
| **Aucun chemin de livraison** (rouge) | Aucun CMS connecté, pas de base externe, pas de domaine de blog public, pas de mode agent, aucune clé API active | Le bouton devient **Livraison à configurer** et la génération est bloquée. **Configurer la livraison** ouvre Paramètres → Intégrations. |
| **Livraison non confirmée** (jaune) | Ton compte a une clé API active : ton site lit peut-être les articles par l'API (mode externe), mais Gridar ne peut pas le confirmer | La génération reste possible. Vérifie le rendu du premier article livré. |

Le même contrôle s'applique au bouton **Générer avec IA** de l'éditeur, à l'autopilote, aux traductions par l'API et aux landings. Voir [Connecter ton site](connect/README.md).

## Le formulaire

Carte **Paramètres** :

| Champ | Effet |
|---|---|
| **Sujet** (optionnel) | Sert de requête de recherche Google et de sujet imposé au modèle. Ex : "Comment choisir un CRM pour PME au Québec". Remplis-le toujours (voir Limites plus bas). |
| **Titre forcé** (optionnel) | Titre exact, repris mot pour mot. Désactive le contrôle anti-cannibalisation. |
| **Méthode de recherche** | `Serper` (défaut) : vrais résultats Google (8 résultats organiques, 5 actualités, des images). `Gemini` : synthèse rédigée par un modèle à partir de ses connaissances, sans requête Google en direct. Si Serper ne répond pas, Gridar bascule sur Gemini. |
| **Type d'article** | Actualité / Opinion, Tutoriel, Comparaison, Guide, Review, Récit personnel, Annuaire local. Change la structure demandée au modèle. **Annuaire local** liste les entreprises trouvées dans la recherche, avec leurs liens. |
| **Longueur** | Court (800-1200 mots), Moyen (1500-2000), Long (2500-3500). C'est la cible donnée au modèle, pas un compte garanti. |
| **Langue** | Français, English, Español, limités aux langues activées dans Paramètres → Langues. |
| **Mots-clés SEO** (optionnel) | Liste séparée par des virgules. Le modèle doit les placer dans l'introduction, dans au moins un H2 et 2 à 3 fois dans le corps. Les trois premiers orientent aussi la méta description. |
| **Aperçu seulement (ne pas publier)** | Génère sans rien enregistrer : tu vois le journal de génération, la méta description et le début du contenu. Ne consomme ni quota ni crédit. L'aperçu n'est pas conservé : relancer en mode normal produit un nouvel article. |

Le formulaire garde tes valeurs pour ce site quand tu changes de page.

Clique **Générer**. La génération tourne en arrière-plan : tu peux naviguer ailleurs, le dock en bas à droite suit l'avancement. Le journal de génération s'affiche ensuite dans la carte **Résultat**, avec **Voir les articles** et **Générer un autre**.

## Les outils au-dessus du formulaire

### Brief de contenu (recommandé)

1. Entre un **Mot-clé cible** puis clique **Générer le brief**.
2. Gridar lit le top 10 Google et les questions "Autres questions posées" du mot-clé, puis produit : intention de recherche, titres recommandés, plan H2/H3, longueur cible, FAQ, entités à mentionner, schémas Schema.org suggérés, signaux E-E-A-T.
3. **Voir le brief** l'affiche. **Utiliser ce brief** remplit le formulaire :
   - **Sujet** = le mot-clé
   - **Titre forcé** = le premier titre recommandé
   - **Mots-clés SEO** = les six premières entités
   - le brief (plan, FAQ, entités, signaux E-E-A-T, schémas, longueur cible) part avec la génération

Un bandeau **Brief actif** le rappelle sous le formulaire. **Retirer** le désactive.

Attention : comme le brief remplit le **Titre forcé**, le contrôle anti-cannibalisation ne s'applique pas. Vérifie toi-même que tu n'as pas déjà un article sur ce sujet.

### Autres panneaux de recherche

- **People Also Ask + FAQ schema** : questions Google pour ton mot-clé, réponses courtes et schéma FAQPage à copier.
- **Questions Reddit / Quora** : les formulations réelles de ton audience, utiles pour tes H2 et ta FAQ.
- **Tendances Google Trends** : intérêt dans le temps et requêtes connexes.

Ces panneaux ne modifient pas la génération. Détails : [Recherche](research.md) et [Outils SEO](seo-tools.md).

## Ce qui se passe sous le capot

1. **Contrôles d'entrée** : chemin de livraison, langue autorisée pour le site, puis quota (sauf en aperçu).
2. **Recherche web** sur ton sujet (Serper ou Gemini).
3. **Choix du titre, de l'angle et de 3 points clés.** Le modèle reçoit jusqu'à 30 titres de tes articles existants, avec la consigne de ne pas les paraphraser.
4. **Anti-cannibalisation** (voir plus bas), sauf si le titre est forcé.
5. **Rédaction.** Le modèle reçoit :
   - la marque du site (nom, URL, description), avec la consigne de la mentionner 2 à 3 fois et d'inclure au moins un lien vers ton site
   - la liste des concurrents du site, à ne jamais lier
   - ton call-to-action principal, à placer tel quel en conclusion s'il est configuré
   - jusqu'à 8 extraits de la mémoire du site (voir plus bas) et les passages pertinents de ta knowledge base
   - des règles d'écriture contre les tics de texte IA (formules d'ouverture creuses, tirets longs, adverbes vides, contrastes "pas X, mais Y")
   - le brief, les mots-clés SEO et les résultats de recherche
   - jusqu'à 10 de tes articles existants, avec la consigne d'en lier au moins 2
6. **Images du corps** : photos Unsplash ou images Google trouvées pendant la recherche.
7. **Nettoyage des liens internes** : un lien `/blog/...` vers un article qui n'existe pas redevient du texte simple.
8. **Image de couverture** : photo Unsplash liée au sujet. À défaut, une image générée par IA.
9. **Méta description** : 150 à 160 caractères visés. Si le résultat fait moins de 120 caractères ou échoue, Gridar reprend la première phrase utile de l'article.
10. **Tags, catégorie, temps de lecture** (nombre de mots divisé par 200).
11. **Livraison** selon le mode du site (tableau ci-dessous). Sur un site hébergé ou en base externe, Gridar ajoute une section "A lire aussi" avec jusqu'à 3 articles proches.
12. **Quota ou crédit consommé**, seulement si l'article a été livré et hors aperçu. Une génération qui échoue ne consomme rien.
13. **Deploy hook** : si un deploy hook est configuré sur le site, Gridar l'appelle.

La rédaction passe par un grand modèle de langage. Si le modèle principal atteint sa limite d'usage ou échoue, un modèle de secours d'un autre fournisseur prend le relais.

## Où atterrit l'article

| Mode du site | Statut à la sortie |
|---|---|
| Hébergé | **Brouillon.** Relis-le puis publie-le depuis l'[éditeur](editor.md). |
| Base externe (Postgres) | **Brouillon.** |
| WordPress | **Publié tout de suite.** |
| Shopify | **Publié tout de suite**, avec tags, auteur et image de couverture. |
| Webflow | **Publié tout de suite**, avec image de couverture. |
| Mode agent | **Brouillon en file de construction** : un agent de code l'intègre dans ton propre dépôt. Gridar ne le publie sur aucune URL. |

Sur WordPress, Shopify et Webflow, le Markdown est converti en HTML avant l'envoi. WordPress ne reçoit ni l'image de couverture, ni la catégorie, ni les tags.

## Contrôles appliqués et contrôles absents

Appliqués à chaque génération :

- **Chemin de livraison** : aucun article ne part vers un site qui ne peut pas l'afficher.
- **Langue** : refus si la langue n'est pas activée sur le site.
- **Anti-cannibalisation** sur le titre.
- **Liens internes cassés** retirés.

Consignes données au modèle, sans vérification après coup : règles d'écriture anti-tics IA, mentions de marque, concurrents à ne pas lier, call-to-action.

Pas fait pendant la génération : aucun audit SEO, aucune correction automatique, aucune vérification des chiffres. Ouvre l'article dans l'[éditeur](editor.md), onglet **SEO**, et lance l'audit : il signale les chiffres cités sans source.

## Anti-cannibalisation

Avant la rédaction, Gridar compare le titre proposé aux titres de tes articles existants : jusqu'à 60 titres, ou les 50 derniers articles publiés sur WordPress, Shopify et Webflow. La mesure est la part de mots communs entre les deux titres (mots de 3 lettres et plus, sans accents ni mots vides). À 55 % de similarité ou plus, la génération s'arrête avec ce message :

> Cet article serait trop similaire (XX%) a un article existant: "Titre de l'article existant". Reformule le sujet ou modifie l'article existant.

Le **Titre forcé** saute ce contrôle. Utilise-le seulement quand le recoupement est voulu.

## Mémoire du site

Avant d'écrire, Gridar cherche dans la mémoire du site les passages les plus proches du sujet : articles publiés du site hébergé, knowledge base, audits, notes manuelles. Il en injecte jusqu'à 8 dans la consigne, dans la limite d'environ 4 000 caractères.

Tu gères cette mémoire dans **Paramètres → Mémoire (RAG)** : **Réindexer**, **Ajouter une note manuelle** (ex : "Ne jamais utiliser le tutoiement"), suppression d'une entrée. Voir [Paramètres du site](site-settings.md).

## Français québécois

La génération écrit dans la langue choisie sans imposer de variante régionale : aucun lexique FR-CA n'est injecté dans la rédaction. Pour repérer les termes de France (shopping, week-end, parking...), ouvre l'article dans l'éditeur, onglet **SEO** → **Lisibilite**, carte **Lexique québécois (FR-CA)**. Voir [Éditeur](editor.md).

## Quota et crédits

Chaque génération lancée depuis cette page, hors aperçu, consomme 1 unité :

1. d'abord le quota mensuel du plan : 1, 8, 60 ou 200 articles (Free, Solo, Pro, Agence)
2. ensuite les crédits achetés
3. sans quota ni crédit, le bouton devient **Quota épuisé · Achète des crédits** et la génération est refusée (erreur 402, encadré **Génération bloquée** avec achat de crédits)

Le compteur repart le premier jour de chaque mois (heure UTC). Détails : [Plans, crédits et quotas](plans-credits.md).

## Autopilote

**Paramètres → Autopilote**, carte **Mode autopilote**. Gridar génère des articles sans intervention, en piochant les sujets parmi tes mots-clés suivis.

- **Prérequis** : au moins un mot-clé dans **Suivi des positions**. Sans mot-clé, l'interrupteur reste grisé.
- **Activer l'autopilote** : interrupteur principal.
- **Cadence** : 1, 2, 3 ou 5 articles par semaine, ou 1 par jour. Gridar espace les passages de 7 jours divisés par la cadence.
- **Stratégie** :
  - **Balanced** (défaut) : 1 rafraîchissement pour 2 créations
  - **Refresh first** : rafraîchit d'abord les articles qui perdent du trafic
  - **Create only** : crée uniquement de nouveaux articles
- **Publication automatique** : désactivée, les articles arrivent en brouillon. Activée, ils sont publiés directement et le deploy hook est appelé.
- **Lancer maintenant (1 article)** : déclenche un passage tout de suite.

La carte affiche aussi **Mots-clés dispo**, **Prochain run**, **Dernier run** et la dernière erreur.

Comment l'autopilote choisit :

- **Création** : un mot-clé suivi pris au hasard parmi ceux qui n'ont pas encore d'article. Le type d'article suit l'intention du mot-clé (commercial → Comparaison, transactionnel → Review, local → Annuaire local, informationnel → Guide ou Tutoriel). La longueur est Moyen ou Long. La langue est celle du mot-clé.
- **Rafraîchissement** : un article publié du site hébergé dont les impressions Search Console baissent d'au moins 20 % sur 30 jours par rapport aux 30 jours précédents, et non mis à jour depuis 30 jours. Gridar réécrit son contenu en gardant le slug. S'il était publié, sa date de publication passe à aujourd'hui. Sans Search Console connectée, ou hors site hébergé, l'autopilote crée au lieu de rafraîchir.

Limites :

- Sur WordPress, Shopify et Webflow, l'autopilote publie tout de suite, même avec **Publication automatique** désactivée.
- Un site sans chemin de livraison est sauté, même avec **Lancer maintenant**.
- Le déclenchement automatique dépend d'une tâche planifiée horaire. Si aucun brouillon n'arrive à la cadence prévue, utilise **Lancer maintenant** et préviens le support.

## Opportunités SEO et landings

**Barre latérale → Opportunités SEO** (page **Opportunités stratégiques**). Pour chaque mot-clé suivi dont l'intention est commerciale, transactionnelle ou locale, et qui n'a pas encore de landing, Gridar propose une page pensée pour ranker et convertir.

**Régénérer** analyse jusqu'à 8 mots-clés par clic. Chaque carte montre :

- le type de page : Outil gratuit, Page service, Comparatif, Guide pilier, Quiz, Calculateur, Landing locale, Lead magnet
- **Le hook**, **Capture du lead**, **Chemin de conversion**, **L'angle qui bat le SERP**, **Pourquoi ça va convertir**
- une estimation : **Recherches/mois**, **Visites**, **Leads/mois**, **Clients/mois**. Elle multiplie le volume de recherche par un taux de clic moyen selon la position visée, puis par des taux de conversion types de ton modèle d'affaires. C'est un ordre de grandeur, pas une prévision.

Sur un site hébergé, les cartes se répartissent en deux sections :

- **Actionnable avec Gridar** : **Créer cette page** génère une landing en brouillon (titre, méta description, H1, sous-titre, bénéfices, preuves, FAQ, texte, call-to-action).
- **Nécessite un asset à construire** : calculateurs, quiz et outils interactifs que ton site n'a pas encore. Gridar écrit du texte, il ne développe pas l'outil. **Obtenir le prompt de création** donne la consigne de construction à ton dev ou à ton IA de code.

Sur un site non hébergé (base externe ou CMS), Gridar ne publie pas de landing. La page affiche **Site externe - livraison par prompt** et chaque carte propose **Obtenir le prompt de création**.

**Pas pertinent** archive une opportunité. **Voir les archivées** affiche les opportunités écartées et celles déjà créées. **Restaurer** remet une opportunité écartée dans la liste.

Garde-fou contre les pages tremplin : Gridar refuse de créer la 50e landing locale d'un site depuis une opportunité. Le message explique pourquoi (Google pénalise les lots de pages qui ne diffèrent que par le nom de ville) et liste ce qu'il faut prouver : présence réelle dans chaque ville, contenu propre à chaque page, signaux locaux.

Limites des landings :

- Le tableau de bord n'a pas d'écran pour relire, modifier ou publier une landing créée, et le blog hébergé ne sert pas les landings. Pour la mettre en ligne, utilise **Copier le prompt IA** : il contient le texte de la landing, à intégrer tel quel sur ton site.
- Le bloc de preuves sociales peut contenir des chiffres proposés par l'IA. Remplace-les par tes vrais chiffres, ou retire-les, avant toute publication.

## Export de prompt

**Copier le prompt IA** et **Obtenir le prompt de création** copient une consigne prête à coller dans ton IA de code (ChatGPT, Lovable, v0, Cursor...) ou à transmettre à ton dev. La page se construit dans ton propre site ; Gridar ne touche pas à ton code.

- Si la landing existe déjà : la consigne demande d'intégrer le texte tel quel (méta, structure, JSON-LD, slug exact).
- Sinon : la consigne demande d'écrire la page à partir du concept (hook, capture, conversion, angle).

L'export ne fait aucun appel IA et ne consomme pas de quota. Les instructions sont en français si le contenu est en français, en anglais sinon. Si le navigateur bloque la copie, le prompt s'affiche sous la carte pour une copie manuelle.

Par l'API, `GET /api/v1/sites/<id>/strategic-opportunities/<op_id>/prompt/` et `GET /api/v1/sites/<id>/landings/<landing_id>/prompt/` acceptent `?stack=` : `nextjs`, `react`, `html`, `astro`, `wordpress`, `webflow` ou `generic` (défaut, celui du tableau de bord).

## Par l'API et le connecteur MCP

La génération d'articles, de landings et de traductions existe aussi dans l'API v1 (`https://api.gridar.app/api/v1/`), réservée aux plans Pro et Agence. Voir [API](api.md) et [Intégrations](integrations.md).

## Limites

- **Sujet vide** : Gridar tire un sujet au hasard dans une liste interne orientée startups et SaaS, sans lien avec ton site. Avec un **Titre forcé** seul, la recherche part aussi de ce sujet tiré au hasard. Remplis toujours le **Sujet**.
- **Catégorie et tags** : la catégorie vient de quatre catégories fixes (Produit & Strategie, Croissance & Acquisition, Lecons & Erreurs, Productivite & Outils ; Ressources Locales pour l'annuaire). Les tags viennent d'une liste fixe de termes tech et entrepreneuriat, avec "Entrepreneuriat" par défaut. Corrige-les dans l'éditeur.
- **Faits et anecdotes** : la consigne demande la première personne, des opinions tranchées et des exemples personnels. Le modèle peut inventer une anecdote ou un chiffre. Relis avant de publier.
- **Recherche localisée** : la recherche Serper de la génération interroge Google France en français, quelle que soit la langue de l'article.
- **Images** : les images du corps et de couverture sont liées à leur adresse d'origine (Unsplash, sites trouvés par Google Images). Vérifie les droits des images Google avant publication.
- **Publication directe sur les CMS** : sur WordPress, Shopify et Webflow, l'article est en ligne dès la fin de la génération.

## Erreurs courantes

| Message | Cause | Action |
|---|---|---|
| "Cet article serait trop similaire (XX%) a un article existant" | Anti-cannibalisation | Reformule le sujet, ou utilise **Titre forcé** si le recoupement est voulu |
| "Quota mensuel atteint (...) et aucun crédit disponible" | Quota du mois et crédits épuisés | Achète des crédits ou attends le mois suivant |
| "La langue "xx" n'est pas autorisee pour ce site" | Langue non activée sur le site | Paramètres → Langues → active la langue |
| Encadré **Aucun chemin de livraison** | Aucun moyen de livrer le contenu au site | **Configurer la livraison** |
| "Recherche web indisponible. Serper: ... Gemini: ..." | Les deux méthodes de recherche ont échoué | Réessaie plus tard. Si ça persiste, signale-le au support |
| "Erreur generation: Reponse LLM vide (...)" | Le modèle principal et le modèle de secours n'ont pas répondu | Réessaie dans quelques minutes |
| "Erreur generation: ..." | Autre erreur pendant la génération | Réessaie. Si récurrent, signale-le au support |
| "WP unreachable: ..." (mode WordPress) | Site WordPress injoignable ou API REST désactivée | Voir [Connexion WordPress](connect/wordpress.md) |
