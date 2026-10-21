# Outils SEO

Au-delà de la génération, Gridar inclut des outils pour piloter ton SEO. La plupart ont leur entrée dans la sidebar du site. Les autres sont des cartes de l'éditeur d'article : ouvre un article, clique **SEO**, puis choisis l'onglet **Audit**, **Lisibilite** ou **Apercu Google**. Chaque section dit d'où vient la donnée et ce que l'outil ne mesure pas.

Les outils de recherche (mots-clés, People Also Ask, Google Trends, Reddit/Quora, concurrence, Analyseur SERP) sont décrits dans [Outils de recherche](research.md). La connexion à Search Console est décrite dans [Google Search Console](gsc.md).

## Ce que les outils exigent

- **Search Console connectée** pour la détection de déclin, la composante « fraîcheur » du score d'audit, la carte « Search Console (vraie perf) » de l'éditeur et le statut exact d'indexation. Sans propriété connectée, ces parties restent vides ou approximatives.
- **Articles lisibles par Gridar** pour l'audit global, le maillage interne, les topic clusters, les liens cassés, la cannibalisation, le contrôle hreflang et le rapport hebdo. Ces outils lisent les articles publiés d'un [site hébergé](connect/hosted.md) ou d'une [base externe](connect/external.md). Sur un site branché à WordPress, Shopify ou Webflow, ils répondent « Cette action nécessite une base de données externe configurée pour ce site. »
- **Plan** : dans le dashboard, aucun outil de cette page n'est filtré par plan. Seul le nombre de mots-clés suivis en dépend (voir Suivi des positions plus bas). Par l'API publique avec un token `btb_`, seuls les plans Pro et Agence passent (voir [API](api.md)).

## Audit du site

**Sidebar → Audit du site**

Cette page rassemble l'état du site. Le résultat reste en cache 10 minutes : pendant ce délai, **Actualiser** réaffiche le même résultat.

**Score composite (0-100)**, calculé sur trois composantes :

| Composante | Ce qui est mesuré | Poids relatif |
|---|---|---|
| PageSpeed | Moyenne Performance / SEO / Accessibilité de ta page d'accueil, en mobile (Google PageSpeed Insights) | 30 |
| Positions | Part de tes mots-clés suivis qui tiennent le top 10 de façon stable | 30 |
| Fraîcheur | 100 moins le % de pages en déclin (Search Console requise) | 25 |

Quand une composante manque, son poids se répartit sur les autres. Sans aucune donnée, la page affiche « Aucune donnee mesurable encore » au lieu d'un score. Les mentions du domaine n'entrent pas dans le score.

**Cartes affichées** :
- **Opportunités stratégiques détectées** (seulement s'il y en a)
- **Recommandations prioritaires** : 5 au maximum, tirées de règles fixes (ex : Search Console non connectée, aucun mot-clé suivi)
- **Mots-cles suivis** : combien sont dans le top 10 stable, et la date de la dernière vérification
- **Performance mobile (PageSpeed)** : Performance, SEO, Accessibilité, avec un lien vers le rapport complet de Google. La page s'affiche d'abord sans elle, avec le message « Analyse PageSpeed en cours (~20-30s) ».
- **Mentions du domaine** : nombre de domaines qui écrivent ton nom de domaine, liés ou non. C'est une recherche Google `"tondomaine" -site:tondomaine` (10 résultats au plus) : ce n'est pas une mesure de tes liens entrants.
- **Detection de declin (GSC)** : résumé de la détection de déclin
- **Indexation Google** : voir la section suivante

## Couverture d'indexation

**Audit du site → carte « Indexation Google » → bouton « Verifier l'indexation »**

Répond à la question : combien de tes pages Google a-t-il indexées ?

1. **Pages attendues** : les URLs de ton `sitemap.xml` (un niveau d'index de sitemap, 500 URLs au plus). Sans sitemap, les articles et landings publiés que Gridar connaît.
2. **Ce que Google montre** : une recherche `site:tondomaine` via Serper, 8 pages de 10 résultats.
3. **Statut exact** (si Search Console est connectée) : l'URL Inspection de Google donne, page par page, si elle est indexée et pourquoi elle ne l'est pas. Les pages douteuses passent en premier. Le dashboard en inspecte 12 au plus, dans un budget de 14 secondes ; ce qui n'est pas inspecté garde le verdict `site:`.

Affichage : **Couverture** (%), **Indexees**, **Pas indexees**, **Vues par Google**, puis la liste des pages pas indexées avec leur raison.

Sans Search Console, le rapport se déclare approximatif (`site:` sous-compte les pages indexées) et propose le bouton « Connecter GSC pour le statut exact + la raison ». Si l'inspection échoue alors que GSC est connectée, le rapport le dit et ne tire aucun verdict de cette partie.

Aucun appel IA, aucun crédit consommé.

API : `GET /api/v1/sites/<id>/index-coverage/?max_inspect=25` (25 par défaut, 100 au plus). Outil MCP : `gridar_index_coverage`.

## IndexNow (Bing, Yandex, Seznam, Naver)

**API et MCP seulement, pas d'écran dans le dashboard**

IndexNow prévient Bing, Yandex, Seznam et Naver qu'une URL est nouvelle ou modifiée, par un seul appel à `api.indexnow.org`. Google ne participe pas à IndexNow.

- `GET /api/v1/sites/<id>/indexnow/` : ta clé IndexNow (générée au premier appel) et les instructions
- `POST /api/v1/sites/<id>/indexnow/submit/` avec `{urls: [...]}` ; sans `urls`, Gridar soumet les URLs de ton sitemap
- Outils MCP : `gridar_indexnow_setup`, `gridar_indexnow_submit`

**Fichier de clé** :
- Site hébergé chez Gridar : le fichier est servi automatiquement.
- Autre site : publie à la racine un fichier `<cle>.txt` qui contient seulement la clé, sur le host qui répond 200 sans redirection (avec ou sans `www`, selon ton site). Sans ce fichier, la soumission répond 403.

**Soumission automatique** : quand un article passe en publié par l'API v1, et quand un agent marque une page construite (`gridar_mark_page_built`). Publier depuis l'éditeur du dashboard ne déclenche pas IndexNow.

Pour Google, la voie équivalente est la re-soumission du sitemap dans Search Console : voir [Google Search Console](gsc.md).

## Opportunités SEO

**Sidebar → Opportunités SEO** (page « Opportunités stratégiques »)

Pour chaque mot-clé suivi d'intention commerciale, transactionnelle ou locale qui n'a pas encore de page, Claude propose un concept de page (angle, structure, pourquoi elle peut convertir). Il s'appuie sur le top 5 Google du mot-clé (Serper). Sans mot-clé de ce type, la page reste vide et te renvoie vers le Suivi des positions.

- **Estimation chiffrée** : visites = volume mensuel × CTR de la position 5. Gridar ne reçoit pas toujours de volume de recherche ; quand il manque, les cases affichent « inconnu ».
- **Actionnable avec Gridar** : bouton **Créer cette page**, qui génère une landing sur ton site hébergé. Pour les pages locales, un garde-fou refuse, au-delà d'un seuil, une série de pages qui ne diffèrent que par le nom de ville.
- **Nécessite un asset à construire** (un outil, un calculateur) : bouton **Obtenir le prompt de création**. Gridar ne génère pas l'outil lui-même.
- **Pas pertinent** archive une opportunité ; **Voir les archivées** puis **Restaurer** la ramène. **Régénérer** relance l'analyse.
- **Site externe** : Gridar ne publie pas de landing dessus. Chaque opportunité passe par **Obtenir le prompt de création** ou **Copier le prompt IA**, à coller dans ton IA de code ou à donner à ton dev.

API : `GET /api/v1/sites/<id>/strategic-opportunities/`, `POST .../refresh/` (8 mots-clés par défaut, 20 au plus), `POST .../<op_id>/approve/` | `dismiss/` | `restore/`, `GET .../<op_id>/prompt/`. Un agent de code peut aussi récupérer les pages à construire : `GET /api/v1/sites/<id>/build-queue/` puis `POST .../build-queue/mark-built/` (outils MCP `gridar_pull_build_queue`, `gridar_mark_page_built`).

## Visibilité IA

**Sidebar → AI ERA → Visibilite IA**

Tu y listes les prompts à suivre, c'est-à-dire les questions qu'un client poserait à un assistant IA. Le bouton **Suggerer des prompts** en fait proposer par Claude (6 par défaut) d'après le nom, le domaine, la description et les mots-clés suivis de ton site ; rien n'est ajouté sans ton choix.

**Limite actuelle** : les résultats de cette page sont simulés. Aucun moteur IA n'est interrogé depuis le dashboard ; l'écran l'indique (« Les resultats sont mockes en V1 »). Le score, les citations et les courbes ne mesurent donc pas encore ta présence dans ChatGPT, Perplexity, Gemini, SearchGPT ou Claude.

Pour une mesure réelle, utilise l'outil gratuit AI Visibility Checker décrit plus bas : il interroge Gemini et, si sa clé est configurée, ChatGPT.

API : `GET/POST /api/v1/sites/<id>/ai-visibility/prompts/`, `POST .../ai-visibility/suggest/`, `POST .../ai-visibility/run/`, `GET .../ai-visibility/summary/`. La réponse de `run` porte `mocked: true`.

## Brief de contenu

**Sidebar → Générer un article → carte « Brief de contenu » en haut**

Entre ton mot-clé cible et clique **Générer le brief**. Gridar lit le top 10 Google, les questions « People Also Ask » et les recherches associées (Serper), puis Gemini en tire un brief :

- **Intention de recherche** : informational / commercial / transactional / navigational, avec une explication
- **Titres recommandés** : 3 titres de moins de 60 caractères
- **Plan d'article** : 6 à 12 H2 avec leurs H3, et un nombre de mots cible
- **FAQ (prêtes pour schema)** : 4 à 8 questions, chacune avec une piste de réponse
- **Entités à mentionner** : 8 à 15 termes
- **Schemas suggérés**
- **Signaux EEAT à inclure** : 3 à 6
- **Concurrents SERP** : les 5 premiers résultats

Clique **Utiliser ce brief** : le mot-clé devient le sujet, le premier titre recommandé remplit le titre, les 6 premières entités remplissent les mots-clés, et le brief complet part avec la génération suivante.

Disponible en FR / EN / ES. Même mot-clé et même langue : résultat en cache 1 h.

## Audit SEO (par article)

**Articles → un article → bouton « SEO » → onglet « Audit »**

L'onglet contient deux audits différents.

**Score SEO** : calculé dans ton navigateur, mis à jour pendant que tu écris. Le mot-clé principal est le premier tag de l'article ; Gemini fournit ses synonymes pour reconnaître les variantes.

| Critère | Bon état | Points max |
|---|---|---|
| Mot-clé principal | Trouvé au moins 3 fois parmi : le titre, l'intro, 2 H2 | 25 |
| Longueur du texte | 1 000 mots ou plus | 15 |
| Longueur du titre | 50 à 60 caractères | 15 |
| Texte alternatif des images | Toutes les images ont un alt de qualité | 15 |
| Sous-titres | 2 H2 ou plus | 12 |
| Liens internes | 2 ou plus | 10 |
| Méta description | 120 à 160 caractères | 8 |
| Image de couverture | Présente | 4 |
| Slug | 60 caractères au plus | 3 |

Le total est plafonné à 100.

Bouton **Corriger avec IA** : Gemini reçoit les points faibles et renvoie un nouveau titre, une nouvelle méta description et, si besoin, un contenu réécrit, que l'éditeur applique. Le modèle ne lit que les 3 000 premiers caractères de l'article : sur un article long, relis le contenu renvoyé avant de sauvegarder.

**Audit SEO par IA** : carte du même nom, bouton **Lancer l'audit**. Gemini lit les 5 000 premiers caractères et rend un score sur 100, un verdict, des points forts, des points faibles et des actions. Avant l'appel, une passe sans IA repère les chiffres présentés sans source et les signale au modèle. Même contenu : résultat en cache 1 h.

Les autres cartes de l'onglet Audit :
- **Core Web Vitals** : PageSpeed de l'article, voir plus bas
- **Cannibalisation** : les articles du site trop proches de celui-ci, voir plus bas
- **Backlinks** : voir plus bas
- **Suggestions IA** : 3 méta descriptions, 3 titres et 8 à 12 mots-clés proposés par Gemini
- **Analyse de la concurrence** et **Recherche de mots-cles** : voir [Outils de recherche](research.md)
- **Suggestions de liens internes** : Gemini propose 5 liens au plus vers tes articles publiés de même langue
- **Schema.org JSON-LD** : voir Schemas plus bas
- **Search Console (vraie perf)** : les requêtes GSC de l'article, voir [Google Search Console](gsc.md)

## Audit global

**Sidebar → Audit global SEO**

Lance l'audit SEO par IA (le même que dans l'éditeur) sur tes 10, 25, 50 ou 100 derniers articles publiés. Résultat :
- **Score moyen**
- **Distribution** : Excellent (85 et plus), Bon (70-84), Moyen (50-69), Faible (moins de 50)
- **Les 10 articles les plus faibles**, à corriger en priorité
- **Faiblesses et actions récurrentes** : les formulations qui reviennent le plus souvent dans les audits

## Suivi des positions Google

**Sidebar → Suivi des positions**

Ajoute des mots-clés cibles, puis clique **Snapshot maintenant** : Gridar lit la page de résultats Google via Serper (`gl=ca` / `hl=fr` pour un mot-clé en français, États-Unis pour l'anglais, Espagne pour l'espagnol) et note la position de ton site.

**Position affichée** : la médiane des 5 derniers relevés, et seulement si ton site apparaît dans au moins la moitié d'entre eux. Sinon la cellule affiche :
- **A confirmer** (avec « deja vu #X », la meilleure position observée) si ton site apparaît dans moins de la moitié des relevés
- **Hors top 100** s'il n'apparaît dans aucun des 5 derniers relevés
- **Jamais releve** si aucun relevé n'existe encore

La colonne **Derniere verif.** donne la date du dernier relevé. Une ligne dépliée montre l'historique du mot-clé sur 90 jours. À partir de 3 relevés, une alerte apparaît quand le dernier chute de 5 places ou plus sous la médiane des précédents, ou sort des résultats.

**Limite de profondeur** : Gridar demande 100 résultats à Serper, mais Serper plafonne ce paramètre sans le signaler. « Hors top 100 » veut donc dire « absent des résultats que Serper a rendus », pas forcément au-delà de la 100e place.

Autres actions de la page :
- **Suggerer avec l'IA** : 12 à 18 mots-clés proposés par Claude d'après la mémoire de ton site, ta page d'accueil et des recherches Google sur ton nom et ta description. Les mots-clés déjà suivis sont exclus. Coche ceux à suivre, puis **Ajouter la selection**. Aucun volume de recherche n'est fourni.
- **Intention** éditable par mot-clé (info, commercial, transactional, local), et **Reclasser avec l'IA** pour reclasser les mots-clés encore marqués « info ». Les opportunités SEO partent des intentions commerciale, transactionnelle et locale.
- **Export** de la liste

Limites par plan (mots-clés suivis, tous sites confondus) :
- Essai gratuit : 0 mot-clé
- Solo : 10 mots-clés
- Pro : 30 mots-clés
- Agence : 100 mots-clés

Au-delà, l'ajout est refusé. Voir [Plans et crédits](plans-credits.md).

Cette page n'utilise pas Search Console : les clics et impressions réels d'un article sont dans la carte « Search Console (vraie perf) » de l'éditeur.

## Détection de déclin

**Sidebar → Détection de déclin** (Search Console requise)

Repère les pages qui perdent de la visibilité dans Google. Pour chaque page que Search Console rapporte, Gridar compare les impressions et les clics de la période choisie (7, 14, 30, 60 ou 90 jours ; 30 par défaut) à la période précédente de même durée.

- **Déclin** : impressions en baisse de 30 % ou plus, ou clics en baisse de 40 % ou plus quand la page en avait
- **Action proposée** :
  - **Redirect/Suppr** : plus aucune impression, ou impressions en baisse de 80 % ou plus
  - **Refresh majeur** : impressions en baisse de 50 % ou plus, ou clics en baisse de 60 % ou plus
  - **Refresh mineur** : les autres cas

L'outil affiche les 50 pages en déclin. Search Console publie ses données avec 2 à 3 jours de retard et la période en cours finit aujourd'hui : les derniers jours tirent les chiffres récents vers le bas.

Si Search Console n'est pas configurée ou si le jeton a expiré, la page le dit et te renvoie vers les paramètres.

## Topic clusters

**Sidebar → Topic clusters**

Clique **Analyser** : Gemini groupe tes articles publiés (80 par défaut) en 3 à 8 clusters thématiques à partir de leurs titres, extraits et débuts de texte. Il faut au moins 3 articles publiés. Pour chaque cluster :
- **Pilier** : l'article qui résume le mieux le thème, à étoffer en page pilier
- **Articles satellites** : les autres articles du groupe
- **Nouveaux articles suggérés** : 2 à 4 titres proposés par le modèle, avec la raison

La carte distingue les sujets couverts et manquants. Les suggestions viennent du modèle, pas d'une lecture de la SERP.

**Construire un cluster complet** : `POST /api/v1/sites/<id>/clusters/build/` (outil MCP `gridar_build_cluster`) rend un lot de prompts coordonnés, la page pilier plus chaque satellite, avec le maillage déjà écrit (pilier vers satellites, chaque satellite vers le pilier). Aucun appel IA à cette étape. Chaque page est liée à un mot-clé suivi pour qu'un agent ferme la boucle avec `gridar_mark_page_built`.

**Carte par mots-clés** : `GET /api/v1/sites/<id>/clusters/` (outil MCP `gridar_cluster_map`) groupe tes mots-clés suivis et tes opportunités en clusters sans appel IA, et marque ceux qui ont déjà une page.

## Maillage interne

**Sidebar → Maillage interne** (page « Graphe de maillage interne »)

Analyse les liens entre tes articles publiés et liste :
- **Orphelins** : aucun article ne pointe vers eux
- **Hubs** : 5 liens entrants ou plus
- **Culs-de-sac** : aucun lien sortant
- **Top 10 des articles les mieux connectés**

Pour ajouter des liens à un article, utilise la carte « Suggestions de liens internes » de l'éditeur (onglet Audit).

## Redirections 301

**Sidebar → Redirections 301**

Quand tu changes le slug d'un article, Gridar crée une redirection de l'ancien slug vers le nouveau. Tu peux aussi en ajouter à la main (migration depuis un autre CMS, restructuration d'URL) et en supprimer. Un compteur indique combien de fois chaque redirection a servi.

Gridar sert ces redirections à travers son API publique : elles s'appliquent au blog hébergé et à un frontend qui lit cette API. Sur WordPress, Shopify ou Webflow, Gridar ne crée pas la redirection dans ton CMS.

## Liens cassés

**Sidebar → Liens cassés** (page « Détecteur de liens cassés »)

Clique **Scanner** : Gridar vérifie les liens externes de tes articles publiés (100 articles par défaut, 200 au plus). Chaque lien reçoit une requête HEAD, puis GET si le serveur refuse HEAD. Le résultat de chaque URL reste en cache 24 h.

Les liens internes ne sont pas vérifiés. Le scan se lance à la demande, sans passage automatique, et ne propose pas de lien de remplacement.

## Rapport hebdomadaire

**Sidebar → Rapport hebdo**

Résumé des 7 derniers jours :
- **Articles publiés cette semaine**
- **Top 5 articles vus (tout temps)** : le compteur de vues de Gridar, pas Search Console
- **Top mouvements de positions (en hausse)** et **Mouvements en baisse (à surveiller)** : 5 de chaque, d'après tes mots-clés suivis
- **Redirections cette semaine** : le nombre de redirections créées ou modifiées

Le bouton **Imprimer / PDF** passe par l'impression de ton navigateur. Gridar n'envoie pas ce rapport par courriel.

API : `GET /api/v1/sites/<id>/digest/weekly/`. Outil MCP : `gridar_weekly_digest`.

## Schemas Schema.org

- **Articles hébergés** : chaque article porte un JSON-LD `BlogPosting` avec l'auteur (`Person`) et l'éditeur (`Organization`). Le blog injecte aussi le schema `Person` de l'auteur, construit depuis **Paramètres → Auteur (EEAT)**.
- **Dans l'éditeur** : onglet Audit → carte **Schema.org JSON-LD** → **Generer le schema**, puis **Copier**. La base est un `BlogPosting` ; Gemini y ajoute `FAQPage` si l'article contient une FAQ, ou `HowTo` si c'est un guide par étapes.
- **LocalBusiness** (API seulement) : `POST /api/sites/<id>/local-business-schema/` avec `{address, hours, phone, price_range, area_served}`. Le pays est fixé à CA et la région à QC ; `area_served` vaut Québec par défaut. Colle le résultat dans le `<head>` de ton site.
- **Person** (API seulement) : `GET /api/sites/<id>/person-schema/`, à partir des champs Auteur.

## Lexique FR-CA

**Articles → un article → SEO → onglet « Lisibilite » → carte « Lexique québécois (FR-CA) »**

Repère dans ton article les termes de France qui ont un équivalent québécois (55 entrées), avec la suggestion, une explication quand elle existe et le nombre d'occurrences. La carte s'affiche pour les articles en français.

| France | Québec |
|---|---|
| shopping | magasinage |
| email | courriel |
| parking | stationnement |
| week-end | fin de semaine |
| smartphone | téléphone intelligent |
| ... | ... |

La carte signale ; elle ne remplace rien. La liste n'est pas modifiable depuis les paramètres.

## Cannibalisation

**Articles → un article → SEO → onglet « Audit » → carte « Cannibalisation »**

Repère les articles publiés du site qui risquent de viser la même requête que l'article ouvert. Pour chaque paire de même langue, la similarité est la plus haute des deux mesures :
- **Titres** : mots communs (indice de Jaccard sur les mots de 3 lettres et plus, hors mots vides)
- **Slugs** : ressemblance des deux slugs

Seuil : 55 %. L'outil donne la raison (« Titres similaires » ou « Slugs similaires ») ; à toi de fusionner les deux articles ou de les différencier.

À la génération, un garde-fou utilise le même seuil et refuse un sujet trop proche d'un article existant, sauf si tu imposes le titre.

API : `GET /api/sites/<id>/cannibalization/` (30 paires au plus, tout le site). Outil MCP : `gridar_detect_cannibalization`.

## Hreflang

**Tableau de bord → carte « Santé hreflang multi-langue »**

Utile si ton site publie en plusieurs langues. Vérifie dans la base de Gridar que chaque groupe de traductions couvre les langues de ton site : groupes complets, groupes incomplets avec les langues manquantes, articles publiés dans une seule langue. Aucun crawl de tes pages : l'outil ne contrôle pas les balises hreflang servies, ni `x-default`. Résultat en cache 5 minutes.

Pour les détails sur le multilingue : [Articles multilingues + hreflang](translation.md).

## PageSpeed (Core Web Vitals)

**Articles → un article → SEO → onglet « Audit » → carte « Core Web Vitals » → « Tester mobile » ou « Tester desktop »**, et la carte PageSpeed de l'Audit du site (page d'accueil, mobile)

Gridar interroge l'API Google PageSpeed Insights (mesure de laboratoire Lighthouse) et rend :
- les scores **Performance**, **SEO** et **Accessibilité** (0-100)
- **LCP**, **CLS** et **FCP**

Une stratégie par test (mobile ou desktop). Résultat en cache 30 minutes. Pas d'INP, pas de liste de recommandations Lighthouse : pour le détail, ouvre le lien « Rapport complet Google » de l'Audit du site.

**Limite** : PageSpeed Insights est erratique. Mesuré le 2026-08-25, la même URL a répondu en 9 secondes puis en plus de 75, et Lighthouse renvoie par moments une erreur 500. Gridar coupe à 120 secondes et affiche alors une erreur ; relance le test.

API : `POST /api/page-speed/ {url, strategy}` ou `POST /api/v1/page-speed/`. Outil MCP : `gridar_page_speed`.

## Backlinks (mentions)

**Articles → un article → SEO → onglet « Audit » → carte « Backlinks » → « Verifier les backlinks »**

La carte lance une recherche Google `link:<url de l'article>` via Serper (20 résultats) et compte les domaines distincts qui en sortent. Google ne prend plus en charge l'opérateur `link:` : ces résultats sont des pages qui mentionnent l'URL, pas un relevé de tes liens entrants. Pas de texte d'ancre, pas de date, pas d'autorité de domaine.

Gridar n'a pas de source de backlinks. Pour un vrai profil de liens, utilise un outil qui crawle le web (Ahrefs, Majestic, Semrush) ou les liens externes de Search Console.

## Originalité et détection IA (Originality.ai)

**Articles → un article → SEO → onglet « Lisibilite » → carte « Originalité + Détection IA » → « Analyser »**

Envoie ton contenu à Originality.ai et rend :
- **Score IA** : probabilité que le texte soit généré par une IA
- **Score de plagiat**, avec jusqu'à 5 sources (URL, %, extrait)
- un verdict en français

Si le module n'est pas configuré sur le serveur, la carte affiche « Module non configuré ». Même contenu : résultat en cache 1 h.

Le score IA d'Originality n'est pas un critère de Google, qui ne pénalise pas un texte parce qu'une IA l'a écrit. Un score IA très haut signale souvent un texte trop générique : retravaille-le.

## Lisibilité

**Articles → un article → SEO → onglet « Lisibilite » → carte « Lisibilité »**

Score de lisibilité recalculé pendant que tu écris :
- **Français** : formule de Kandel et Moles (adaptation française de Flesch)
- **Anglais** : Flesch Reading Ease
- **Espagnol** : formule française, faute de formule dédiée

Le calcul repose sur la longueur moyenne des phrases (mots par phrase) et des mots (syllabes par mot). La carte affiche aussi l'indice ARI.

| Score | Niveau |
|---|---|
| 80 et plus | Très facile |
| 70-79 | Facile |
| 60-69 | Standard |
| 50-59 | Assez difficile |
| 30-49 | Difficile |
| moins de 30 | Très difficile |

Sous 50, la carte te conseille de simplifier le style. Elle ne réécrit rien.

## Tags auto

**Articles → un article → vue « Paramètres » → carte Tags → bouton « Générer »**

Gemini propose 5 à 8 tags courts (1 à 3 mots) d'après le titre, l'extrait et le contenu. Les tags sortent en français. Le premier tag sert de mot-clé principal au Score SEO.

## Synonymes du mot-clé

**Automatique dans l'onglet Audit**

Gemini fournit 5 à 8 variantes du mot-clé principal (synonymes, pluriels, sigles, traductions FR/EN). Le Score SEO s'en sert pour reconnaître le mot-clé sous ses autres formes. Langues : français et anglais.

API : `POST /api/seo-synonyms/ {keyword, language}`.

## Outils gratuits sans compte

Ces outils sont publics, sans inscription. Liste complète : <https://www.gridar.app/tools>. Une adresse IP peut lancer 3 analyses par minute sur les outils `/tools`, 6 par minute sur l'audit et le suivi de position. L'audit, AI Visibility, AI Citation, Can I Rank, Competitor Gap et la comparaison gardent leur résultat 1 h en cache ; le suivi de position, 10 minutes.

Les requêtes testées par AI Visibility, AI Citation et Competitor Gap sont écrites par un modèle de langage (DeepSeek) d'après ta page d'accueil, avec un repli sur des gabarits par secteur si la lecture échoue.

### Audit SEO gratuit

<https://www.gridar.app/audit> : entre ton domaine.
- **Page d'accueil** (crawl) : title, meta description, H1, H2, JSON-LD. Huit contrôles on-page.
- **PageSpeed** mobile (Google PageSpeed Insights)
- **Positions** : 5 à 10 requêtes de client proposées par DeepSeek, vérifiées sur Google.ca via Serper. Une requête que la vérification n'a pas pu lire s'affiche « non vérifié » et ne compte pas.
- **Score** : PageSpeed 40 %, on-page 35 %, part des requêtes dans le top 10 : 25 %. Quand une composante manque, les poids se répartissent sur les autres et le score est marqué partiel.
- **Verdict de ta fiche Google Business** : Gridar cherche ta fiche sur Google Maps (Serper) et la compare à 3 fiches du pack local sur les avis, la note, les photos et les heures.
- Après ton courriel : concurrents sur tes requêtes, questions « People Also Ask » et recherches associées, schema, comparaison desktop / mobile, idées d'articles, et un décompte des sites qui mentionnent ton domaine (des mentions, pas des liens).

Chaque audit a un lien partageable `/rapport/<token>`. Le bouton PDF passe par l'impression du navigateur.

### AI Visibility Checker

<https://www.gridar.app/tools/ai-visibility-checker> : entre ton domaine. 15 requêtes commerciales sont posées à chaque moteur IA configuré sur le serveur : Gemini (`gemini-flash-latest`) et ChatGPT (`gpt-5-mini`, si sa clé est présente). Gemini répond sans recherche Google : l'outil mesure la réponse du modèle, pas les AI Overviews.

Gridar compte les réponses qui nomment ton domaine, la position de la mention et les autres domaines cités. Score : taux de mention 50 %, position 30 %, part de voix 20 %. Un moteur en panne sort du calcul au lieu de compter comme zéro.

### AI Citation Checker

<https://www.gridar.app/tools/ai-citation-checker> : entre ton domaine. 8 requêtes posées à Gemini seul, avec la consigne de citer 3 domaines sources. Score = part des réponses où ton domaine figure parmi ces sources. Les sources sont celles que le modèle écrit, pas des liens vérifiés.

### Can I Rank?

<https://www.gridar.app/tools/keyword-difficulty> : entre ton domaine et un mot-clé. Gridar lit le vrai top 10 Google.ca (Serper) et ta page d'accueil, puis calcule :
- **Position** (45 %) : ta place actuelle dans le top 10, 0 si tu en es absent
- **Pertinence** (30 %) : le mot-clé apparaît-il dans ton title, ton H1, ta meta description, ton contenu
- **Technique** (25 %) : les huit contrôles on-page de l'audit

Verdict : Facile, Possible, Difficile ou Très difficile, selon le score. L'outil affiche les 5 premiers résultats réels. Il ne mesure ni l'autorité de ton domaine, ni tes liens.

### Competitor Gap Finder

<https://www.gridar.app/tools/competitor-gap> : entre ton domaine, et jusqu'à 2 concurrents si tu les connais. 12 requêtes commerciales, lues sur le vrai top 10 Google (Serper). DeepSeek écarte les requêtes dont le SERP n'est pas commercial ; l'outil nomme celles qu'il a retirées. Sans concurrents fournis, Gridar retient les domaines qui reviennent le plus dans ces SERP (des annuaires et des sites d'emploi peuvent en faire partie).

Un écart = une requête où un concurrent sort et pas toi, sur un SERP réellement lu. Aucun volume de recherche n'est fourni.

### Comparaison de concurrents

<https://www.gridar.app/tools/competitor-compare> : entre ton site et celui d'un concurrent. Six catégories, mesurées des deux côtés :

| Catégorie | Mesure |
|---|---|
| SEO technique | Contrôles on-page, plus le score SEO Lighthouse s'il existe pour les deux |
| Contenu | Présence et positions sur les requêtes des deux sites (12 au plus) |
| Autorité perçue | Part des positions dans le top 3, plus le nombre de domaines qui mentionnent la marque (mentions, pas liens entrants) |
| UX et design | PageSpeed mobile : performance et accessibilité |
| Présence IA | Taux de mention dans les réponses des moteurs IA configurés |
| Stratégie locale | Données schema.org : localité, téléphone, heures, coordonnées |

Une catégorie impossible à mesurer s'affiche sans note, avec la raison. Sous 15 points d'écart, l'outil ne désigne pas de gagnant. Les commentaires sont rédigés par DeepSeek, les notes viennent des mesures. Le résultat PageSpeed reste en cache 24 h.

### Calculateur ROI SEO

<https://www.gridar.app/tools/seo-roi-calculator> : entre ton trafic mensuel, ton taux de conversion ou ton nombre de demandes par mois, la valeur d'un client et ton budget SEO mensuel. Trois scénarios de croissance du trafic sur 12 mois : +30 %, +70 % et +150 %, sur une courbe lente au départ. Seul le revenu supplémentaire compte (trafic gagné × conversion × valeur client) ; le calculateur dit le mois où le budget est remboursé, ou qu'il ne l'est pas. Ce sont des hypothèses, pas une prévision. Aucun appel IA.

### Suivi de position Google

<https://www.gridar.app/suivi-position-google-canada> : entre une URL, un mot-clé et une ville du Québec. Recherche Google géolocalisée via Serper, jusqu'à 3 essais quand la réponse revient tronquée, comparaison exacte du domaine. « Hors du top 100 » veut dire absent des résultats que Serper a rendus (voir la limite de profondeur dans Suivi des positions).

## Endpoints API liste complète

Les endpoints `/api/...` hors `v1` utilisent la session du dashboard (JWT). Les endpoints `/api/v1/...` acceptent la session ou un token `btb_` ; le token exige un plan Pro ou Agence. Détails : [API](api.md).

| Outil | Endpoint |
|---|---|
| Audit du site | `GET /api/sites/<id>/site-audit/` |
| Score SEO du site | `GET /api/v1/sites/<id>/seo-score/` |
| Couverture d'indexation | `GET /api/v1/sites/<id>/index-coverage/` |
| IndexNow (clé) | `GET /api/v1/sites/<id>/indexnow/` |
| IndexNow (soumission) | `POST /api/v1/sites/<id>/indexnow/submit/` |
| Re-soumission du sitemap | `POST /api/v1/sites/<id>/sitemap/submit/` |
| Opportunités | `GET /api/v1/sites/<id>/strategic-opportunities/` |
| Audit par article | `POST /api/seo-audit/` ou `POST /api/v1/audit/` |
| Correction d'audit | `POST /api/seo-fix/` |
| Suggestions SEO | `POST /api/seo-suggest/` |
| Audit global | `GET /api/sites/<id>/audit-all/` ou `GET /api/v1/sites/<id>/audit-all/` |
| Brief de contenu | `POST /api/v1/brief/` |
| Mots-clés suivis | `GET /api/v1/sites/<id>/keywords/`, `POST /api/v1/sites/<id>/keywords/track/` |
| Relevé de positions | `POST /api/v1/sites/<id>/keywords/snapshot/` |
| Cannibalisation | `GET /api/sites/<id>/cannibalization/` ou `GET /api/v1/sites/<id>/cannibalization/` |
| Hreflang | `POST /api/hreflang-check/` ou `POST /api/v1/hreflang-check/` |
| PageSpeed | `POST /api/page-speed/` ou `POST /api/v1/page-speed/` |
| Backlinks (mentions) | `POST /api/backlinks/` |
| Originalité | `POST /api/plagiarism-check/` ou `POST /api/v1/plagiarism/` |
| Lisibilité | `POST /api/readability/` ou `POST /api/v1/readability/` |
| Schema d'article | `POST /api/seo-schema/` |
| Schema LocalBusiness | `POST /api/sites/<id>/local-business-schema/` |
| Schema Person | `GET /api/sites/<id>/person-schema/` |
| Tags | `POST /api/generate-tags/` |
| Synonymes | `POST /api/seo-synonyms/` |
| Lexique FR-CA | `POST /api/lexicon-check/` |
| Image SEO (alt + nom de fichier) | `POST /api/image-suggest/` |
| Suggestions de liens | `POST /api/sites/<id>/link-suggestions/` ou `/api/v1/sites/<id>/link-suggestions/` |
| Détection de déclin | `GET /api/sites/<id>/content-decay/` ou `GET /api/v1/sites/<id>/content-decay/` |
| Topic clusters (IA) | `POST /api/sites/<id>/topic-clusters/` |
| Carte des clusters | `GET /api/v1/sites/<id>/clusters/` |
| Construction de cluster | `POST /api/v1/sites/<id>/clusters/build/` |
| Maillage interne | `GET /api/sites/<id>/link-graph/` |
| Liens cassés | `GET /api/sites/<id>/broken-links/` ou `GET /api/v1/sites/<id>/broken-links/` |
| Redirections | `GET/POST /api/sites/<id>/redirects/`, `DELETE /api/sites/<id>/redirects/<pk>/` |
| Rapport hebdo | `GET /api/sites/<id>/weekly-digest/` ou `GET /api/v1/sites/<id>/digest/weekly/` |

Le sitemap et le flux RSS d'un site hébergé (`/api/sites/<id>/sitemap.xml`, `/api/sites/<id>/rss.xml`) sont publics.
