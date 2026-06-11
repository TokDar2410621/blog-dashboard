# Outils SEO

Au-delà de la génération, Gridar inclut une suite d'outils pour piloter ton SEO en continu. Tous accessibles depuis la sidebar du site.

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

## Détection de cannibalisation (standalone)

**Sidebar → Cannibalisation** (ou `POST /api/sites/<id>/cannibalization/`)

Détecte les paires d'articles publiés qui se cannibalisent (rivalisent pour le même mot-clé Google). L'algo combine :

- **Jaccard** sur les tokens du titre (similarité 0-1)
- **SequenceMatcher** sur les slugs (similarité 0-1)
- **Same language filter** : seuls les articles dans la même langue sont comparés

Output : liste de paires avec score > 50 % de similarité, classées par sévérité. Pour chaque paire :
- Choix recommandé : merge (garder le plus performant + 301 l'autre) ou différencier (réécrire un des deux pour cibler un keyword distinct)

Différent de l'anti-cannibalisation **PRÉ-génération** qui empêche d'écrire un nouvel article trop similaire. Celui-ci nettoie l'historique.

## Hreflang check

**Sidebar → Hreflang check** (sites avec multilingue activé)

Crawl tes articles publiés et vérifie l'intégrité des liens hreflang :
- Toutes les pages d'un `translation_group` se réfèrent les unes les autres ?
- Les codes hreflang sont valides (`fr-CA`, `en`, `es`...) ?
- `x-default` défini ?
- Pas de boucle / référence morte ?

Score 0-100 + liste des erreurs avec correctifs suggérés.

Pour les détails sur le multilingue : [Articles multilingues + hreflang](translation.md).

## Page Speed Insights

**Sidebar → Page Speed** ou `POST /api/page-speed/ {url}`

Hit Google PageSpeed Insights API pour une URL de ton site. Récupère :
- Score Performance (0-100, mobile + desktop)
- Core Web Vitals : LCP, FID/INP, CLS
- Suggestions d'optimisation Google : compress images, defer JS, reduce server response time, etc.
- Lighthouse audits détaillés

Coût : gratuit (Google PageSpeed API n'a pas de quota à notre échelle).

Use case : audit hebdomadaire de ta home + 5-10 articles top-trafic. Repère les régressions de perf.

## Backlinks

**Sidebar → Backlinks** ou `POST /api/backlinks/ {url}`

Découverte des backlinks vers ton site via :
- Bing Webmaster API (si compte connecté)
- Common Crawl Index (free, mais latence 1-3 mois)
- Source agrégée Serper "site:" + "link:" queries

Pour chaque backlink détecté :
- Domaine source
- URL exacte
- Anchor text
- Date de crawl
- DR estimé (Domain Rating, basé sur ouvert source si pas Ahrefs)

**Limite** : pas aussi exhaustif qu'Ahrefs / Majestic / SEMrush (qui crawlent eux-mêmes le web). Pour un audit backlinks pro, utilise Ahrefs en complément.

Use case principal : surveillance des nouveaux backlinks (alertes quand un nouveau domaine link vers toi → opportunité de remerciement / partenariat).

## Plagiarism check (Originality.ai)

**Articles → un article → bouton "Vérifier originalité"** ou `POST /api/plagiarism-check/ {content}`

Pousse ton contenu vers Originality.ai et récupère :
- **Score originalité** (0-100, 100 = unique)
- **AI detection** (probabilité que le texte soit IA-généré)
- **Plagiat trouvé** : sources qui matchent (URL + % de similarité)

Coût : ~0.01$/1000 mots. Désactivable dans Site Settings → Editor → "Disable plagiarism check".

Important : le seuil "AI detection" donné par Originality est NON déterminant pour Google. Google ne pénalise pas l'IA en soi (Helpful Content Update). Mais si Originality flag > 80 % AI, c'est souvent un signal que ton contenu est trop générique → réécriture recommandée.

## Readability check

**Articles → un article → onglet "Lisibilité"** ou `POST /api/readability/ {content, language}`

Score de lisibilité :
- **Français** : Kandel-Moles (équivalent Flesch pour le FR)
- **Anglais** : Flesch Reading Ease

Échelle :
- 90-100 : très facile (5e année primaire)
- 60-69 : facile (12-14 ans)
- 30-49 : moyen (universitaire)
- 0-29 : difficile (académique)

Cible idéale pour blog grand public : 60-80. Pour B2B technique : 30-50 acceptable.

Le score est calculé sur :
- Longueur moyenne des phrases
- Longueur moyenne des mots
- Complexité lexicale (mots > 3 syllabes)

Suggestions : si score < 30, l'IA peut reformuler les paragraphes les plus complexes pour les simplifier sans perdre le sens.

## Tags generation auto

**PostEditor → bouton "Générer les tags"** ou `POST /api/generate-tags/ {content}`

L'IA suggère 4-6 tags pertinents pour l'article basé sur son contenu. Évite les tags trop génériques ("blog", "article") et privilégie les concepts spécifiques.

Use case : workflow d'écriture rapide où tu écris l'article puis fais générer titre + excerpt + tags + cover image en 30 sec total.

## SEO synonymes

**PostEditor → sélection texte → bouton "Synonymes"** ou `POST /api/seo-synonyms/ {term, language}`

Suggère 5-10 synonymes pour un mot-clé donné, dans le contexte de ton article. Préserve l'intent SEO :
- Variations sémantiques proches
- Termes connexes / LSI keywords
- Évite la répétition mécanique

Use case : tu remarques que tu utilises "CRM" 47 fois dans ton article. Sélectionne CRM → synonymes → propose "logiciel client", "gestion relation client", "outil de pipeline ventes" pour varier.

## Endpoints API liste complète

Pour automatisation, tous les outils SEO ont leur endpoint :

| Tool | Endpoint |
|---|---|
| Audit per article | `POST /api/seo-audit/` |
| Audit fix | `POST /api/seo-fix/` |
| Audit bulk | `POST /api/sites/<id>/audit-all/` |
| Brief de contenu | `POST /api/v1/brief/` |
| Cannibalisation | `POST /api/sites/<id>/cannibalization/` |
| Hreflang check | `POST /api/hreflang-check/` |
| Page speed | `POST /api/page-speed/` |
| Backlinks | `POST /api/backlinks/` |
| Plagiarism | `POST /api/plagiarism-check/` |
| Readability | `POST /api/readability/` |
| Generate tags | `POST /api/generate-tags/` |
| SEO synonyms | `POST /api/seo-synonyms/` |
| Lexicon check | `POST /api/lexicon-check/` |
| Image SEO suggest | `POST /api/image-suggest/` |
| Link suggestions | `POST /api/sites/<id>/link-suggestions/` |
| Content decay | `GET /api/sites/<id>/content-decay/` |
| Topic clusters | `GET /api/sites/<id>/topic-clusters/` |
| Link graph | `GET /api/sites/<id>/link-graph/` |
| Broken links | `GET /api/sites/<id>/broken-links/` |
| Redirects CRUD | `GET/POST /api/sites/<id>/redirects/` |
| Weekly digest | `GET /api/v1/sites/<id>/digest/weekly/` |

Tous nécessitent JWT (interne) ou Bearer (API publique pour les v1) sauf sitemap/rss.
