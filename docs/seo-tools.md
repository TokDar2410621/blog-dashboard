# Outils SEO

Au-delà de la génération, Blog Dashboard inclut une suite d'outils pour piloter ton SEO en continu. Tous accessibles depuis la sidebar du site.

## Brief de contenu

**Sidebar : Générer un article → carte "Brief de contenu" en haut**

Avant d'écrire, génère un plan stratégique pour ton mot-clé cible. Ce que ça produit :

- **Intent** - informational / transactional / navigational / commercial investigation
- **Outline** - H2/H3 suggérés, ordre logique, transitions
- **Entités** à mentionner (people, places, organizations, concepts) pour signal d'expertise à Google
- **FAQ** - questions Google "People Also Ask" + réponses courtes
- **Signaux EEAT** à mettre en avant (expertise, expérience, autorité, trust)

Clique **Appliquer** → le brief se branche dans la génération suivante. Article × 2 plus structuré, mieux aligné sur l'intent.

Disponible en FR / EN / ES.

## Audit SEO (par article)

**PostList → un article → bouton "Audit"**

Score sur 100 + checklist détaillée :

- **Titre** : longueur (idéal 50-60 caractères), présence du keyword principal, capitalisation
- **Méta description** : longueur (140-155), keyword, call-to-action
- **Structure** : 1 seul H1, hiérarchie H2/H3 cohérente, paragraphes < 4 phrases
- **Mots-clés** : densité 1-2 %, semantic terms, LSI keywords
- **Liens** : internes (≥ 2), externes (≥ 1 vers source autoritaire), pas de broken links
- **Images** : alt text, lazy loading, format optimisé
- **Lecture** : reading time, Flesch score
- **Schema.org** : Article + Person + Organization présents
- **EEAT** : auteur identifié, biographie, credentials

Bouton **Corriger automatiquement** → l'IA applique les fixes sans toucher au contenu narratif (titre, méta, structure, schema).

Cache : 24h pour le même contenu (anti-spam d'API).

## Audit global

**Sidebar → Audit global**

Audite tous tes articles d'un coup. Output :
- Score moyen
- Distribution (combien d'articles 90+, 80-89, 70-79, < 70)
- Top 10 articles avec le score le plus bas (priorité de fix)
- Issues récurrentes (ex : "12 articles n'ont pas de méta description")

Pour les plans Pro et Agence uniquement (Solo n'a pas l'audit bulk).

## Suivi des positions Google (Rank tracking)

**Sidebar → Suivi des positions**

Ajoute des mots-clés cibles → on crawl la SERP Google chaque jour pour voir où ton site classe.

Pour chaque mot-clé tu vois :
- **Position courante** (1-100, ou "non classé" si > 100)
- **Variation** depuis la dernière mesure
- **Historique** : graph 30j / 90j / 1an
- **URL classante** : quelle page de ton site Google montre pour ce keyword
- **CTR estimé** + impressions (si GSC connecté)

Combine avec **Google Search Console** (Site Settings → GSC) pour avoir des données réelles d'impressions/clics au lieu d'estimations.

Limites par plan :
- Free : 0 mot-clé
- Solo : 10 mots-clés
- Pro : 30 mots-clés
- Agence : 100 mots-clés
- Enterprise : sur mesure

## Content Decay

**Sidebar → Détection de déclin**

Identifie les articles qui PERDENT du trafic / des positions au fil du temps. Algorithme :
- Pour chaque article publié il y a > 30j, on compare les vues / positions sur les 30 derniers jours vs la moyenne historique
- Si chute > 30 % → flag "decay"
- On suggère une stratégie : republier (avec date mise à jour), ajouter du contenu, ou rediriger vers un article plus récent

Très utile : 70 % des articles SEO perdent du trafic après 6-12 mois sans entretien. Le content decay détecte ça automatiquement et te guide sur quoi mettre à jour.

## Topic Clusters

**Sidebar → Topic clusters**

Détecte automatiquement les "groupes thématiques" de tes articles (clustering par embeddings + topic modeling). Pour chaque cluster :
- **Pillar page** suggérée - l'article le plus complet du groupe (à promouvoir comme hub)
- **Cluster pages** - les articles supports (à lier vers la pillar)
- **Gaps** - sujets manquants détectés depuis la SERP qu'il faudrait écrire pour compléter le cluster

Stratégie SEO 2026 : les topic clusters dominent les keyword stuffing. Google récompense la couverture topique cohérente.

## Maillage interne (Link graph)

**Sidebar → Graphe de liens**

Visualise tes articles + leurs liens internes en graphe interactif. Détecte :
- **Articles orphelins** - aucun autre article ne les link, mauvais signal Google
- **Liens unidirectionnels** vs réciproques
- **Hubs** - articles avec beaucoup de liens entrants (pillars naturelles)
- **Gaps** - articles qui devraient se lier mais ne le font pas (suggéré par similarité sémantique)

## Redirections 301

**Sidebar → Redirections 301**

Quand tu changes le slug d'un article, on crée automatiquement un 301 de l'ancien vers le nouveau (préserve le SEO). Tu peux aussi en ajouter manuellement (migration depuis un autre CMS, restructuration de URL).

## Liens cassés

**Sidebar → Liens cassés**

Crawl périodique de tes articles pour détecter les liens morts (interne ou externe). Liste les 404, les domaines disparus, les redirections en chaîne. Suggestions de remplacement.

## Rapport hebdomadaire

**Sidebar → Rapport hebdo**

Email + PDF chaque lundi matin. Contient :
- Articles publiés cette semaine
- Score SEO moyen + variation
- Top 10 articles par trafic (si GSC connecté)
- Mots-clés qui ont gagné/perdu des positions
- Articles en decay détectés
- TODO : audits à corriger, articles orphelins, gaps à combler

Format : Markdown rendu en HTML email + PDF attaché. Désactivable dans Site Settings → Notifications.

Disponible : Solo (mensuel), Pro (hebdo), Agence (hebdo + custom format).

## Schemas Schema.org

**Site Settings → onglet "Schema"**

Génère du JSON-LD à coller dans le `<head>` de tes pages :

- **LocalBusiness** - pour les commerces québécois (addressRegion=QC, geo, opening hours, prix)
- **Person** - auteur du blog (E-E-A-T : credentials, expertise, social profiles)
- **Organization** - entreprise (logo, sameAs vers réseaux sociaux)

Article + Person + Organization sont injectés automatiquement dans tes articles générés. LocalBusiness, c'est à toi de le coller dans le `<head>` global de ton site.

## Lexique FR-CA

**Auto-appliqué dans tous les articles générés en FR**

Détecte et remplace en live ~50 termes France-spécifiques par leurs équivalents québécois :

| France | Québec |
|---|---|
| shopping | magasiner |
| email | courriel |
| parking | stationnement |
| week-end | fin de semaine |
| smartphone | téléphone intelligent |
| ... | ... |

Tes lecteurs québécois remarquent IMMÉDIATEMENT les termes France-spécifiques (effet "site touriste"). Le lexique élimine ce signal.

Liste éditable + extensible : Site Settings → Lexique → ajouter tes termes propres au métier.
