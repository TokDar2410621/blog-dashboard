# Recettes pratiques

Scénarios concrets que Gridar permet de bout en bout aujourd'hui, du travailleur autonome à l'agence. Les résultats SEO dépendent de ta niche, de ton site et de ta concurrence : aucune recette ne promet un chiffre de trafic.

## Recette 1 : Lancer un blog SEO de PME

**Profil** : ton site n'a pas encore d'articles. Tu veux commencer à apparaître dans Google sur les questions de tes clients.

**Plan** : Solo (29.99$/mois, 8 articles générés par mois) ou Pro (89.99$/mois, 60 articles).

**Étape 1 - Mise en place**
- Connecte ton site : [WordPress](connect/wordpress.md), [Shopify](connect/shopify.md), [Webflow](connect/webflow.md) ou [hébergé](connect/hosted.md).
- Paramètres → General → **Modèle d'affaires** : il oriente l'angle éditorial des articles.
- Paramètres → **Auteur (EEAT)** : bio, compétences, liens LinkedIn et site personnel.
- Paramètres → Integrations → **Base de connaissances** : tes services, ta zone, ta façon de travailler. L'IA s'appuie sur ces faits plutôt que d'en inventer.
- Paramètres → **Call-to-action** : le texte et l'URL que Gridar place en conclusion de chaque article généré.
- Paramètres → **Search Console** : connecte ta propriété. Voir [Search Console](gsc.md).
- **Suivi des positions** → « Suggerer avec l'IA » pour une première liste, puis garde les mots-clés qui comptent pour ton chiffre d'affaires.

**Étape 2 - Production**
- Page **Générer un article** : prépare le sujet avec le **Brief de contenu**, **People Also Ask + FAQ schema** et **Questions Reddit / Quora**, puis applique le brief au formulaire.
- Site WordPress, Shopify ou Webflow : l'article part en ligne dès la fin de la génération. Lance d'abord avec **Aperçu seulement (ne pas publier)** si tu veux relire.
- Site hébergé : l'article arrive en brouillon. Ouvre-le depuis **Articles**.
- Dans l'éditeur, passe la carte **Lexique FR-CA** et l'audit, corrige les chiffres signalés sans source, change l'image de couverture si elle tombe à côté, puis publie.

**Étape 3 - Indexation et suivi**
- **Audit du site** → **Verifier l'indexation** : compare ton sitemap à ce que Google montre.
- Clique **Snapshot maintenant** dans **Suivi des positions** pour relever tes mots-clés. Une position s'affiche une fois constante sur plusieurs relevés.
- Consulte le **Rapport hebdo** chaque semaine ; il s'imprime en PDF.

Détails de la génération : [Générer un article](generate-article.md).

## Recette 2 : Relancer un site existant qui stagne

**Profil** : tu as déjà beaucoup d'articles publiés. Le trafic stagne ou baisse.

**Prérequis** : Search Console connecté. Sans lui, la détection de déclin n'a pas de données.

**Diagnostic**
1. **Audit global SEO** : la distribution des scores de tous tes articles, pour repérer les plus faibles.
2. **Détection de déclin** : les pages dont les impressions Search Console chutent entre deux périodes.
3. **Topic clusters** : les regroupements thématiques de ton site et les articles qui manquent à chaque groupe.
4. **Liens cassés** et **Maillage interne** : les liens morts et les articles orphelins (sans lien entrant).

**Plan d'action**
- **Articles en déclin** : mets à jour les chiffres et les dates, ajoute une FAQ tirée de People Also Ask, puis demande une réindexation dans Search Console. Sur un site hébergé, l'autopilote en mode « Refresh first » cible les articles dont les impressions baissent et les régénère avec des données à jour : Paramètres → Autopilote, puis **Lancer maintenant (1 article)** pour en traiter un à la demande.
- **Doublons** : garde le meilleur des deux articles et redirige l'autre avec **Redirections 301**.
- **Orphelins** : ajoute des liens depuis les articles proches. Le graphe du **Maillage interne** te montre lesquels.
- **Clusters incomplets** : **Construire tout le cluster** prépare un prompt par page manquante, maillage interne compris. Ces prompts se donnent à un agent IA ; ils ne consomment pas ton quota.

**Ensuite** : relance la détection de déclin chaque mois pour vérifier que les pages remontent.

## Recette 3 : Agence - gérer plusieurs sites clients

**Profil** : tu es consultant SEO ou agence et tu gères le contenu de plusieurs clients.

**Plan** : Agence (199.99$/mois) : 5 sites, 200 articles générés par mois au total, 100 mots-clés suivis au total, API et MCP à 200 requêtes/h. Au-delà de 5 sites : bouton **Nous contacter** sur [/billing](https://www.gridar.app/billing).

**Onboarding d'un client**
- Ajoute le site et connecte son CMS (chaque site compte dans la limite de 5).
- Remplis pour lui Modèle d'affaires, Auteur (EEAT), Base de connaissances et Call-to-action.
- Search Console : la connexion se fait avec un compte Google qui a accès à la propriété du client. Demande-lui de t'ajouter comme utilisateur dans Search Console.
- Ajoute ses mots-clés au **Suivi des positions**. Les quotas d'articles et de mots-clés se partagent entre tous tes clients : répartis-les.

**Recherche**
- **Audit du site** et **Opportunités SEO** : pour chaque mot-clé à intention commerciale ou transactionnelle, Gridar propose une page à créer.
- **Analyseur SERP** et les outils publics [Comparaison de concurrents](https://www.gridar.app/tools/competitor-compare) et [Competitor Gap Finder](https://www.gridar.app/tools/competitor-gap) pour situer le client face à ses concurrents.

**Suivi**
- **Santé de tous mes sites** (vue multi-sites du tableau de bord) : repère le client qui demande de l'attention.
- **Rapport hebdo** de chaque site : articles de la semaine, mouvements de positions, redirections. Le bouton **Imprimer / PDF** produit le document à envoyer.

**Limites à connaître** : Gridar n'a pas de rapport en marque blanche ni d'envoi automatique de rapports aux clients. Le PDF porte les données du site ; l'envoi reste à faire de ton côté.

## Recette 4 : Boutique Shopify - du contenu qui mène aux produits

**Profil** : tu vends sur Shopify et tu veux des articles qui amènent des visiteurs vers tes fiches produits.

**Stratégie** : couvrir les trois étapes de la décision d'achat.

**Découverte (éducation)**
- Sujets larges liés à ton industrie, intention informationnelle.
- But : faire connaître la marque.

Ex (boutique de café) :
- « Comment infuser un café au pour-over »
- « Différence entre arabica et robusta »
- « Histoire du café au Québec »

**Comparaison**
- Guides d'achat, comparatifs, classements.
- Intention : le visiteur compare avant d'acheter.

Ex :
- « Cafetière à piston ou Aeropress : laquelle choisir ? »
- « Quel café pour quelle préparation »

**Achat**
- Articles qui présentent ton produit face au besoin du client.
- Intention : transactionnelle.

Ex :
- « Comment choisir un café en grains pour une machine espresso »
- « Abonnement café : ce qui est inclus et comment ça marche »

**Mener vers les produits** : Paramètres → **Call-to-action** place ton texte et ton lien (une collection, une fiche produit) en conclusion de chaque article généré. Dans l'éditeur, ajoute à la main les liens vers les produits cités.

**À savoir sur Shopify** : l'article est publié en ligne dès la fin de la génération. Relis en mode **Aperçu seulement** d'abord si tu veux valider le texte avant qu'il soit visible. Les tags sont envoyés séparés par des virgules : évite les virgules dans un tag.

## Recette 5 : SaaS B2B - articles de fond

**Profil** : tu vends un logiciel à des entreprises. Le cycle de vente est long et le décideur s'informe avant de te parler.

**Format** : longueur **Long** (2500 à 3500 mots), un problème précis par article, des données que tu peux sourcer.

**Sources de sujets**
1. **Tes données internes** : ce que tu observes chez tes clients (anonymisé). Mets ces faits dans la **Base de connaissances** pour que l'IA s'en serve.
2. **Questions Reddit / Quora** sur la page **Générer un article** : les mots exacts de tes prospects.
3. **People Also Ask + FAQ schema** : les questions que Google associe au sujet.
4. **[Competitor Gap Finder](https://www.gridar.app/tools/competitor-gap)** : les requêtes où tes concurrents apparaissent et toi non.

**Auteur** : remplis Paramètres → **Auteur (EEAT)** avec soin : bio, compétences, LinkedIn. Pour ce public, l'auteur compte autant que le texte.

**Cadence** : quelques articles par mois suffisent ; Solo couvre 8 articles générés par mois. Relis chaque chiffre : l'audit de l'éditeur signale ceux qui n'ont pas de source.

**Distribution** : un post LinkedIn natif qui résume l'article avec le lien, et l'article envoyé aux prospects qui posent cette question.

## Recette 6 : Blog perso / travailleur autonome

**Profil** : tu es pigiste ou consultant. Ton blog prouve ton expertise et t'amène des demandes.

**Plan** : Essai pour tester (1 article par mois, sans suivi de mots-clés), puis Solo (29.99$/mois).

**Stratégie** :
- Un ou deux articles par mois suffisent.
- Sujets : tes spécialités et des études de cas anonymisées.
- Alterne articles techniques (preuve de compétence) et études de cas (preuve par l'exemple).
- Auteur (EEAT) très soigné : c'est toi qu'on évalue.
- Base de connaissances : ton parcours, tes spécialités, ta façon de travailler.
- Type d'article **Récit personnel** pour les retours d'expérience.

**Conversion** : Paramètres → **Call-to-action** (ex. « Réserve un appel de 20 minutes » + ton lien de prise de rendez-vous). Gridar le place en conclusion de chaque article généré.

**Mots-clés** : longue traîne, très spécifiques. Peu de recherches, mais une intention claire.

Ex (pigiste React) :
- « Comment déboguer une fuite mémoire dans un useEffect React »
- « Mon retour après six mois de TanStack Router en production »
- « Étude de cas : migrer un client de Next.js 12 à 15 »

## Recette 7 : Blog québécois bilingue

**Profil** : tu vises à la fois le Québec (français) et le marché anglophone.

**Mise en place** :
- Paramètres → **Langues** : active `fr` et `en`, avec le français par défaut.
- Search Console vérifiée sur tout le domaine (`sc-domain:tonsite.ca`) pour couvrir les deux langues.

**Workflow** :
1. Génère l'article en français.
2. Passe-le dans la carte **Lexique FR-CA** de l'éditeur : la génération n'applique pas le lexique d'elle-même.
3. Dans l'éditeur, **Traduire** → **Traduire en EN** crée la version anglaise, liée à l'original, avec le même statut que l'original (un brouillon reste brouillon).
4. Relis la version anglaise (noms propres, conventions canadiennes) et publie.
5. Sur le tableau de bord, la carte **Santé hreflang multi-langue** liste les articles dont une traduction manque.

**À savoir** :
- Sur le blog hébergé, les versions sont reliées par un sélecteur de langue visible sur la page. Le blog n'ajoute pas de balises `hreflang` dans l'en-tête HTML.
- Le suivi des positions relève les mots-clés français sur Google Canada et les mots-clés anglais sur Google États-Unis. Tiens-en compte si ta clientèle anglophone est canadienne.

Voir [Traduction](translation.md).

## Recette 8 : Génération en volume par l'API

**Profil** : tu as un jeu de données (villes, produits, services) et tu veux une page par ligne.

**Avant de lire** : générer beaucoup de pages presque identiques expose tout le domaine à une pénalité « contenu mince ». Chaque page doit apporter une information propre à sa ligne. À utiliser avec discernement.

**Prérequis**
- Plan **Pro** (60 articles/mois, 30 requêtes/h) ou **Agence** (200 articles/mois, 200 requêtes/h). Pour plus : bouton **Nous contacter** sur [/billing](https://www.gridar.app/billing).
- Un jeton d'API (voir [API](api.md)).
- Paramètres → General → **Modèle d'affaires** et Paramètres → **Auteur (EEAT)** remplis : sans eux, l'API répond `422 Onboarding incomplet`.
- Un chemin de livraison configuré, sinon l'API répond `409 delivery_blocked`.

**Le piège de l'anti-cannibalisation** : Gridar refuse un titre trop proche d'un article existant. Des titres comme « X à Montréal », « X à Laval » se ressemblent assez pour être refusés. Passe un `title` explicite pour chaque ligne : le contrôle saute, et c'est à toi de rendre chaque page distincte.

```python
import csv
import time

import requests

TOKEN = "btb_xxx"
SITE_ID = 12
URL = f"https://api.gridar.app/api/v1/sites/{SITE_ID}/generate/"

with open("villes_quebec.csv", encoding="utf-8") as f:
    for row in csv.DictReader(f):
        ville = row["nom"]
        payload = {
            "topic": f"installation d'une borne de recharge résidentielle à {ville}",
            "title": f"Installer une borne de recharge à {ville} : étapes et coûts",
            "type": "guide",
            "length": "medium",
            "language": "fr",
            "keywords": f"borne de recharge {ville}, installation borne {ville}",
        }
        while True:
            r = requests.post(
                URL,
                headers={"Authorization": f"Bearer {TOKEN}"},
                json=payload,
                timeout=300,  # une génération prend une à deux minutes
            )
            if r.status_code == 429:
                time.sleep(int(r.headers.get("Retry-After", "60")))
                continue
            break
        if r.status_code == 402:
            print("Quota atteint, arrêt.")
            break
        if not r.ok:
            print(ville, r.status_code, r.text[:200])
```

**Après la génération** : passe l'**Audit global SEO**, supprime les pages faibles et ajoute à chaque page ce qu'elle seule peut dire (données locales réelles, photos du lieu, avis de clients de cette ville).

## Recette 9 : Newsletter à partir des articles

**Profil** : tu as une infolettre et tu veux que tes articles l'alimentent sans double travail.

**Stratégie** : RSS vers infolettre, avec un outil tiers.

1. Repère le flux RSS de ton blog : en mode hébergé, c'est `https://<domaine de ton blog>/rss.xml`. Sur WordPress, Shopify ou Webflow, utilise le flux de ton CMS. En [mode externe](connect/external.md), c'est à ton frontend de le générer.
2. Branche ce flux dans Mailchimp, Substack, Beehiiv ou SendFox via leur intégration RSS.
3. Chaque article publié alimente l'envoi, selon la cadence choisie dans l'outil.

Format conseillé : un résumé hebdomadaire qui regroupe les articles de la semaine, plutôt qu'un courriel par article.

## Recette 10 : Après une chute brutale de trafic

**Profil** : ton trafic a chuté d'un coup après une mise à jour de Google. Pénalité algorithmique probable.

**Diagnostic** :
1. **Audit global SEO** : repère les articles au score le plus bas.
2. **Originalité** : vérifie les articles trop génériques ou trop proches d'autres sources, avec la carte **Originalité + Détection IA** de l'éditeur quand le module est activé, sinon avec un vérificateur externe.
3. **Auteur (EEAT)** : ton profil d'auteur est-il complet et vérifiable ?
4. **Backlinks toxiques** : Gridar n'analyse pas les backlinks. Utilise Ahrefs, Majestic ou un équivalent.

**Plan de relance** :
1. Supprime ou passe en `noindex` les articles sans valeur.
2. Réécris en profondeur tes meilleurs articles : faits vérifiés, exemples vécus, FAQ.
3. Renforce ton profil d'auteur (photo, bio, compétences, liens vers tes profils).
4. Désavoue les backlinks toxiques avec l'outil de désaveu de Google.
5. Demande une réindexation des pages corrigées dans Search Console.
6. Suis la **Détection de déclin** chaque mois. Une relance prend du temps, sans raccourci.

**Si pénalité manuelle** : Search Console → « Actions manuelles », corrige ce qui est signalé, puis demande un réexamen.

## Recette 11 : Site maison livré par un agent IA

**Profil** : ton site est une application maison (Next.js, Astro, React...) sans CMS. Gridar ne peut pas y publier directement. Tu travailles avec un agent de code comme Claude Code.

**Plan** : Pro ou Agence (le MCP et l'API demandent un jeton `btb_`).

**Mise en place** :
1. Paramètres → General → **Mode de livraison** → « Via un agent ».
2. Connecte le serveur MCP de Gridar à ton agent (voir [Intégrations](integrations.md)).

**Boucle de travail** :
1. Génère tes articles dans Gridar. Ils restent en brouillon dans la file de construction, sans être publiés sur une URL Gridar.
2. Les **Opportunités SEO** et les mots-clés informationnels non couverts y ajoutent des briefs de pages.
3. Ton agent récupère la file (`gridar_pull_build_queue`), construit chaque page dans ton dépôt, déploie, puis confirme avec `gridar_mark_page_built` en donnant l'URL en ligne.
4. À cette confirmation, Gridar enregistre l'URL et l'annonce à IndexNow (Bing, Yandex, Seznam, Naver ; Google n'utilise pas IndexNow).
