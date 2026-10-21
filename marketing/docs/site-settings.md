# Référence des paramètres du site

Toutes les options par site. Accès : **Sidebar → Paramètres**, ou directement `/dashboard/<id>/parametres` (redirige vers l'onglet Général).

Neuf onglets : Général, Branding, Auteur (EEAT), Call-to-action, Langues, Search Console, Mémoire (RAG), Autopilote, Intégrations.

## Enregistrer

Le bouton **Sauvegarder**, en bas de chaque onglet, enregistre en une fois les champs de **tous** les onglets. Tu peux passer d'un onglet à l'autre puis sauvegarder une seule fois. Si l'enregistrement échoue, un message dit quel champ pose problème.

Ces actions s'appliquent tout de suite, sans **Sauvegarder** :

- les réglages de l'onglet Autopilote ;
- l'ajout et la suppression de notes dans Mémoire, et **Réindexer** ;
- **Connecter Google Search Console** et **Déconnecter** ;
- **Activer** et **Retirer** le domaine du blog public (Intégrations).

Les identifiants WordPress, Shopify et Webflow n'apparaissent dans aucun onglet. Pour les changer, reconnecte le site depuis `/sites` : voir [Connecter ton site](connect/README.md).

## Onglet "Général"

| Champ | Description |
|---|---|
| Nom du site | Libellé interne, affiché dans la liste des sites |
| Domaine | Domaine de ton site (`https://monsite.com` accepté, le `https://` et le slash final sont retirés à l'enregistrement). Sert au scan de branding, au sitemap et au flux RSS publics de Gridar, et aux URL du blog hébergé (voir [Mode hébergé](connect/hosted.md)) |
| Description | Courte description pour Open Graph. Le compteur signale un texte de plus de 160 caractères |
| Modèle d'affaires | Blog personnel (défaut), Agence (services BtoB), SaaS, E-commerce, Marketplace, Média / Édition. Sert aux opportunités SEO, aux landings, aux prompts exportés et au score SEO du site. La génération d'articles ne le lit pas |
| Mode de livraison | **Automatique** (Gridar héberge, ou pousse au CMS / à la base externe) ou **Via un agent** |

**Mode de livraison "Via un agent"** : pour un site fait main (Next.js, React, etc.) que Gridar ne peut pas publier. Les articles générés restent en brouillon chez Gridar, sans passer par le CMS ni la base externe, et attendent dans la build-queue. Un agent de code (Claude Code ou autre) les récupère et les pose dans ton repo. Ce réglage l'emporte sur tous les autres chemins de livraison. Détails : [Mode externe](connect/external.md).

## Onglet "Branding"

| Champ | Description |
|---|---|
| Image Open Graph par défaut | URL de l'image partagée sur Facebook, X ou LinkedIn quand un article n'a pas de couverture. Recommandé : 1200×630 |
| Couleur principale | Hex (ex `#2563eb`), avec sélecteur de couleur |
| Couleur du texte sur la couleur principale | Hex (ex `#ffffff`) |
| Logo URL | URL absolue de ton logo |

**Bouton "Scanner"** (encart "Détecter automatiquement le branding") : lit la page de ton **Domaine** et remplit la couleur principale, la couleur du texte et le logo. Le logo vient en priorité de l'`apple-touch-icon`, puis du plus grand favicon, puis de l'image `og:image`. La couleur retenue est la couleur saturée la plus fréquente du CSS, sinon la balise `theme-color`. Le résultat s'affiche sous le bouton : n'oublie pas de **Sauvegarder**.

Le blog hébergé applique ces couleurs, le logo et les polices. Limite actuelle : l'enregistrement depuis cet onglet ne conserve que la couleur principale, la couleur du texte et le logo. Les polices détectées au moment de la connexion sont effacées à la première sauvegarde des paramètres.

## Onglet "Auteur (EEAT)"

**Auteur et langue par défaut**

| Champ | Description |
|---|---|
| Auteur par défaut | Nom attribué aux articles générés. Vide = "Admin" |
| Langue par défaut | Français, English ou Español. Présélectionnée dans l'éditeur et la génération (même champ que dans l'onglet Langues) |

**Profil auteur (E-E-A-T)**

| Champ | Description |
|---|---|
| Rôle / titre | Ex : "Fondateur, Consultant SEO, Avocat fiscaliste". JSON-LD `jobTitle` |
| Photo (URL) | Photo professionnelle, avec aperçu |
| Bio (2-4 phrases) | Ce qui établit ton expérience. Un compteur de caractères s'affiche |
| Credentials / qualifications | Diplômes, certifications, expériences. JSON-LD `hasCredential` |
| LinkedIn / Twitter / X / Site personnel | Ces trois URL alimentent `sameAs` dans le JSON-LD Person |

Le blog hébergé publie ce profil (JSON-LD Person et signature en pied de page). Sur WordPress, Shopify et Webflow, ces champs ne sont pas envoyés au CMS.

La génération via l'API ou le MCP refuse de démarrer (erreur 422, "Onboarding incomplet") tant que la **Bio** est vide.

## Onglet "Call-to-action"

| Champ | Description |
|---|---|
| Texte du CTA | Texte d'ancre du lien placé en conclusion de chaque article généré. 200 caractères maximum |
| URL du CTA | Destination du lien (contact, formulaire, page produit) |

Les deux champs doivent être remplis pour que le CTA soit injecté. Le générateur reprend le texte et l'URL tels quels. Laisse vide pour désactiver.

## Onglet "Langues"

| Champ | Description |
|---|---|
| Langues disponibles | Boutons Français / English / Español. Rien de coché = les trois sont autorisées |
| Langue par défaut | Présélectionnée dans l'éditeur et la génération |

Une génération dans une langue non autorisée pour le site est refusée. Le formulaire de génération ne propose que les langues autorisées.

## Onglet "Search Console"

Lie ton compte Google pour lire les impressions et les clics réels.

| Élément | Description |
|---|---|
| Property URL | L'URL de ta propriété au format préfixe, avec le slash final : `https://tonsite.com/` |
| Connecter Google Search Console | Lance le consentement Google. Une fois lié, un badge **Connecté** s'affiche et le bouton devient **Reconnecter un autre compte** |
| Déconnecter | Retire la liaison |

Si ta propriété Search Console est de type Domaine, entre quand même l'URL `https://tonsite.com/` : Gridar retrouve la propriété Domaine liée au compte. L'aide de l'écran mentionne le format `sc-domain:tonsite.com`, mais l'enregistrement refuse cette valeur.

Guide complet : [Intégration Google Search Console](gsc.md).

## Onglet "Mémoire (RAG)"

Index des contenus du site que le générateur consulte. À chaque génération d'article, Gridar retrouve les 8 extraits les plus proches du sujet (articles passés, base de connaissances, audits, notes) et les ajoute au contexte, au lieu de tout envoyer.

| Élément | Description |
|---|---|
| Compteurs | Extraits, Extraits KB, Audits, Décisions, Notes. Un article publié est découpé en plusieurs extraits |
| Réindexer | Reconstruit l'index à partir des articles du site |
| Ajouter une note manuelle | Un titre court + un texte (ex : "Cibler Montréal, pas Québec"), puis **Ajouter** |
| Mémoires récentes | Les 30 dernières entrées, chacune supprimable (icône corbeille) |

## Onglet "Autopilote"

Gridar génère des articles selon une cadence, en piochant les sujets parmi tes mots-clés suivis.

| Réglage | Description |
|---|---|
| Activer l'autopilote | Grisé tant qu'aucun mot-clé n'est suivi : ajoute-en dans **Suivi des positions** |
| Cadence | 1, 2, 3 ou 5 articles par semaine, ou 1 article par jour |
| Stratégie | **Balanced** (1 rafraîchissement pour 2 créations, défaut), **Refresh first** (priorité aux articles en perte de trafic), **Create only** (nouveaux articles seulement) |
| Publication automatique | Désactivée : les articles arrivent en brouillon. Activée : ils sont publiés directement |
| Lancer maintenant (1 article) | Lance un run tout de suite, même si l'autopilote est désactivé ou pas encore dû. Selon la stratégie, il crée un article à partir d'un mot-clé suivi ou en rafraîchit un |

L'onglet affiche aussi le nombre de mots-clés disponibles, le prochain run, le dernier run et la dernière erreur.

Limites telles que le code les applique :

- **WordPress, Shopify, Webflow** : l'article est publié en ligne même si **Publication automatique** est désactivée. Le brouillon ne vaut que pour les sites hébergés, en base externe ou en mode agent.
- **Refresh** : ne fonctionne que pour un site hébergé avec Search Console connectée. Il vise les articles dont les impressions baissent d'au moins 20 % sur 30 jours. Sinon, l'autopilote crée un nouvel article.
- **Sans chemin de livraison**, l'autopilote saute son tour au lieu de générer dans le vide.
- La cadence repose sur une tâche planifiée côté serveur. Si aucun article n'apparaît à la date prévue, **Lancer maintenant** reste disponible.

## Onglet "Intégrations"

### Blog public (frontend hébergé)

Pour le mode hébergé. Champ **Domaine du blog public** (ex : `blog.restaurant.ca`) puis **Activer** : Gridar enregistre le domaine sur Vercel et affiche l'enregistrement DNS à créer (type CNAME, valeur `cname.vercel-dns.com`). L'écran vérifie toutes les 8 secondes et affiche "Blog en ligne sur ..." quand le DNS répond. **Retirer** libère le domaine. Pas à pas complet : [Mode hébergé](connect/hosted.md).

### Vercel Deploy Hook

URL d'un Deploy Hook Vercel. Gridar l'appelle après chaque génération et après chaque création, modification ou suppression d'article depuis le dashboard. Utile si ton propre site Vercel se reconstruit à partir des articles.

### Base de connaissances

Texte libre injecté dans le prompt de génération : qui tu es, tes projets, tes anecdotes, ton ton, tes faits clés. Un compteur de caractères s'affiche.

Si le texte dépasse 4 000 caractères, chaque génération n'en garde que la première section et les sections les plus proches du sujet, dans la limite de 4 000 caractères. Découpe ton texte avec des titres `##` : la sélection travaille section par section (sinon paragraphe par paragraphe).

### Marques à ne PAS citer

Une marque par ligne. Le générateur évite de les mentionner et ne met jamais de lien sortant vers elles. **Suggérer avec IA** ajoute des concurrents à la liste sans effacer ce que tu as écrit : relis avant de sauvegarder.

### API publique (mode hébergé)

Affichée seulement pour un site hébergé. Liste les endpoints publics qui servent les articles publiés :

```
GET /api/public/sites/<id>/posts/
GET /api/public/sites/<id>/posts/<slug>/
GET /api/public/sites/<id>/categories/
```

La clé affichée (en-tête `X-Api-Key`) est optionnelle. Pour les autres sites, l'onglet affiche "Réglages avancés : rien à configurer ici pour l'instant".

## Supprimer un site

Pas d'onglet dédié. Sur `/sites`, clique l'icône corbeille de la carte du site, puis confirme **Supprimer** dans "Supprimer ce site ?". L'action est irréversible et efface ce que Gridar stocke pour ce site (articles hébergés, mots-clés, mémoire). Les articles déjà publiés sur WordPress, Shopify, Webflow ou dans ta base externe restent chez toi.

Le dashboard ne propose ni désactivation temporaire, ni transfert de propriété.

## Recette : configurer un nouveau site

1. **Général** : nom, domaine, modèle d'affaires, mode de livraison.
2. **Branding** : **Scanner**, vérifie le résultat, ajoute une image Open Graph 1200×630.
3. **Auteur (EEAT)** : nom, rôle, bio, photo, LinkedIn. La bio est obligatoire pour générer via l'API ou le MCP.
4. **Call-to-action** : texte + URL de ta page de contact.
5. **Langues** : coche les langues du site.
6. **Intégrations** : base de connaissances (découpée en sections `##`) et marques à ne pas citer. En mode hébergé, active le domaine du blog public.
7. **Sauvegarder**.
8. **Search Console** : connecte le compte Google.
9. **Autopilote** : seulement après avoir ajouté des mots-clés dans **Suivi des positions**.
