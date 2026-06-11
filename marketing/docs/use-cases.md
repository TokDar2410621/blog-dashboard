# Recettes pratiques

Scénarios concrets pour utiliser Gridar. Du débutant à l'agence, du B2C au B2B, du court terme au long terme.

## Recette 1 : Lancer un blog SEO PME en 30 jours

**Profil** : tu as un site avec 0 article. Tu veux que dans 1 mois, tu commences à recevoir des visites depuis Google.

**Plan** : Solo (29.99$/mois) ou Pro (89.99$/mois) selon volume.

**Semaine 1 - Setup (3-4 heures total)**
- Connecte ton site (mode WordPress / Shopify / Webflow / hébergé selon stack)
- Configure Site Settings : Knowledge base (300 mots qui résument ton entreprise), EEAT (auteur), Branding scan
- Connecte Google Search Console
- Identifie 5-10 mots-clés cibles via Recherche de mots-clés
- Active le tracking pour ces mots-clés

**Semaine 2-3 - Production (1-2 articles/jour)**
- Pour chaque mot-clé : Brief de contenu → Génère article → Audit → Ajustements manuels (10 min) → Publie
- Insère les articles dans ton sitemap (auto en mode hébergé / WP / Shopify / Webflow)
- Crée un Topic cluster naturel : 1 pillar page (long, ex 2500 mots) + 5-8 cluster articles (moyens, 1000-1500 mots) qui linkent vers la pillar

**Semaine 4 - Indexation + monitoring**
- Soumets ton sitemap à Google Search Console (Settings → Sitemaps → Add)
- Crée un compte Bing Webmaster (5 min, ramène 5-10 % de trafic)
- Monitor les positions chaque jour (auto via le rank tracker)
- Patiente 2-4 semaines pour les premiers indexations

**Résultats attendus** :
- 15-25 articles publiés
- 50-200 visiteurs Google par mois (bas si niche très compétitive, plus élevé si niche locale Québec)
- 2-5 mots-clés en top 30 Google
- Premier article featured snippet possible si tu as bien suivi le PAA workflow

## Recette 2 : Sortir d'un content slump (site existant qui chute)

**Profil** : tu as 100+ articles publiés depuis des années. Le trafic stagne ou baisse.

**Diagnostic (Day 1)**
1. Connecte GSC → vois le déclin précisément
2. **Audit global** : score moyen + articles avec < 70/100
3. **Content decay** : articles qui perdent du trafic
4. **Topic clusters** : identifie ceux désorganisés
5. **Liens cassés** + **Cannibalisation** : nettoie d'abord ces hygiène SEO

**Action plan (Week 1-2)**
- **Top 10 articles en decay** (ceux qui perdaient le plus de trafic) :
  - Ré-écris l'introduction (l'IA peut générer une nouvelle intro à partir du contenu existant)
  - Ajoute une section FAQ depuis PAA actuel
  - Mets à jour les chiffres / dates
  - Réindexe via GSC ("Demander une indexation")
- **5 articles en cannibalisation** : merge les paires en gardant le meilleur, redirige l'autre via Redirection 301

**Long terme (mois 2-3)**
- Identifie 3 topic clusters incomplets → écris les articles de comblement
- Améliore le maillage interne (tool Link Graph) → boost les articles orphelins
- Si possible, gagne 5-10 backlinks de qualité (HARO, partenariats, podcast invité)

**Résultats attendus** : retournement de trend en 2-3 mois. Souvent +30-60 % de trafic vs creux.

## Recette 3 : Agence SEO - onboarding nouveau client

**Profil** : tu es consultant SEO ou agence. Tu signes un client à 2000-5000$/mois pour gérer son SEO.

**Setup (jour 1, ~2h)**
- Plan Agence (199.99$/mois) - jusqu'à 5 clients
- Crée un site Gridar pour le client (slot #N/5)
- Connecte le CMS du client (WP / Shopify / Webflow selon)
- Configure Site Settings avec leurs infos (nom, EEAT auteur, knowledge base)
- Connecte leur GSC (demande accès au client)
- White-label : remplace le branding par le tien dans les rapports clients

**Recherche initiale (jour 2-3, ~6h)**
- Analyse de leur site actuel (Audit global)
- Analyse 3 concurrents directs (Outils → Analyse concurrent)
- Identifie 30-50 mots-clés cibles (Keyword research + PAA + Trends Québec)
- Active rank tracking sur ces 30-50 keywords
- Map leur catalogue de produits/services aux clusters de keywords

**Plan editorial (mois 1)**
- Pillar pages : 5-8 sur leurs services principaux
- Cluster pages : 30-50 articles supports
- Calendrier : 8-12 articles/mois (Pro = 60/mois si tu génères tout ; Agence = 200/mois pour absorber 5 clients)
- Brief chaque article via Content Brief → review humaine 10 min → publication

**Reporting client (mensuel)**
- Génère le rapport white-label PDF avec ton logo
- Envoie aux clients par email automatisé (cron + webhook)
- Inclut : exec summary, top 5 articles, mouvement de positions, recommandations

**Marges**
- Coût Gridar : 199.99$ + crédits éventuels (~50-100$)
- Tu factures le client : 2000-5000$ minimum
- Marge : 90 %+ après ton temps

## Recette 4 : E-commerce Shopify - SEO produits

**Profil** : tu vends sur Shopify, tu veux du contenu blog qui drive du trafic vers tes pages produits.

**Stratégie** : "TOFU/MOFU/BOFU" content pyramid

**TOFU (Top of Funnel) - éducation**
- 60 % de tes articles
- Sujets génériques liés à ton industrie
- Volume keyword fort, intent informationnel
- But : faire connaître la marque, trafic Google

Ex (boutique de café) :
- "Comment infuser un café au pour-over"
- "Différence entre arabica et robusta"
- "Histoire du café au Québec"

**MOFU (Middle of Funnel) - comparaison**
- 30 % de tes articles
- Comparaisons, guides d'achat, classements
- Intent : commercial investigation

Ex :
- "Top 10 cafés bio au Québec en 2026"
- "Cafetière à piston vs Aeropress : laquelle choisir ?"
- "Quel café pour quelle préparation"

**BOFU (Bottom of Funnel) - conversion**
- 10 % de tes articles
- Articles commerciaux ciblant ton produit
- Intent : transactionnel

Ex :
- "Pourquoi notre café X est noté 95/100 par les juges"
- "Comparatif : café X vs café Y, quelle différence"

**Maillage** : chaque article TOFU/MOFU link vers les produits Shopify pertinents (CTA dans le contenu, encart sticky en bas, related products). L'IA fait ça automatiquement via le maillage interne si tu lui dis dans la knowledge base "lier subtilement vers /products/[X] quand pertinent".

**Volume** : 8-15 articles/mois suffit pour démarrer. 6 mois = 60-90 articles → couverture topique sérieuse.

## Recette 5 : SaaS B2B - thought leadership

**Profil** : tu vends un SaaS à des PME. Long sales cycle, décideur = lead à éduquer.

**Stratégie** : positionnement de leader d'opinion

**Format** : articles longs (2500-4000 mots), data-driven, citations d'experts.

**Sources de contenus** :
1. **Données internes** : analyses de tes propres data (anonymisées). Ex : "Étude : combien de PME québécoises automatisent leur facturation en 2026 ?"
2. **Keyword research** sur problèmes de tes prospects
3. **Community questions** (Reddit / Quora / forums B2B)
4. **Competitor gap analysis** : ce dont les concurrents ne parlent pas

**EEAT critique** : ton EEAT auteur (Site Settings) doit être SOLIDE. Bio, credentials, LinkedIn vérifiable, posts originaux, citation par d'autres sites du domaine.

**Publication cadence** : 4-6 articles/mois (qualité > quantité). Plan Pro suffit.

**Distribution** : LinkedIn (post natif qui résume + lien), newsletter mensuelle de tes derniers articles, email aux prospects qualifiés.

## Recette 6 : Blog perso / freelance

**Profil** : tu es freelance, ton blog est ton CV + ta machine à leads.

**Plan** : Solo (29.99$/mois) ou Free pour tester.

**Stratégie** :
- 1-2 articles par mois suffit
- Sujets : tes spécialités + études de cas anonymisées
- 50-50 : articles techniques (preuve de compétence) et études de cas (preuve sociale)
- EEAT auteur ULTRA important : c'est TOI qu'on évalue
- Knowledge base : 500 mots sur ton parcours, ta zone d'expertise, tes valeurs

**Conversion** : chaque article inclut un CTA discret en fin pour book un call ou télécharger un freebie. Pas de pop-up agressif.

**Mots-clés** : long-tail + très spécifiques. Volume bas mais intent ultra-qualifié.

Ex (freelance dev React) :
- "Comment déboguer une fuite mémoire dans un useEffect React"
- "Mon retour après 6 mois de Tanstack Router en prod"
- "Étude de cas : comment j'ai migré un client Next.js 12 → 15"

## Recette 7 : Blog québécois bilingue

**Profil** : tu cibles à la fois le marché québécois (FR-CA) et le marché anglo-canadien / US (EN).

**Stratégie** : 1 site avec 2 langues activées + traduction automatique.

**Setup** :
- Site Settings → Langues : `[fr, en]`, default = fr
- Lexique FR-CA activé pour FR (terms québécois auto-appliqués)
- GSC vérifiée à la racine du domaine (couvre les 2 langues)

**Workflow** :
1. Génère l'article en FR-CA (audience principale Québec)
2. Bouton "Traduire" → version EN générée en draft
3. Révise rapidement (les noms propres, conventions canadiennes vs américaines)
4. Publie EN
5. Hreflang auto déclare les 2 versions à Google

**Volume idéal** :
- 70 % articles FR-CA (40-50/mois sur Pro)
- 30 % articles EN (10-15/mois sur Pro)

**Tracking** : `KeywordTracker` permet de tracker des mots-clés différents par langue (`gl=ca&hl=fr` pour FR, `gl=ca&hl=en` pour EN).

## Recette 8 : Programmatic SEO

**Profil** : tu as un dataset (annuaire de villes, catalogue de produits, base de données). Tu veux générer 1000+ articles automatiquement.

**Avant de lire** : programmatic SEO = générer beaucoup de pages similaires à partir d'un template + données. Risque Google "thin content" si fait sans valeur. À utiliser avec discernement.

**Workflow** :
1. Plan Agence (200 articles/mois) ou Enterprise (volume sur mesure)
2. Préparer ton dataset : CSV / JSON avec les variations (1 row = 1 article)
3. Générer via API REST en boucle :

```python
import requests, csv

token = "btb_xxx"
site_id = 12

with open("villes_quebec.csv") as f:
    for row in csv.DictReader(f):
        ville = row["nom"]
        requests.post(
            f"https://api.gridar.app/api/v1/sites/{site_id}/generate/",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "topic": f"Meilleur électricien à {ville} en 2026",
                "type": "local",
                "language": "fr",
                "keywords": f"électricien {ville}, électricien {ville} pas cher",
            },
            timeout=120,
        )
```

4. Modère les résultats : audit global, supprime les articles low-quality, ajoute du contenu unique (témoignages clients par ville).

**Risques** :
- Google peut deindex en bulk si trop de "near-duplicates" (mêmes paragraphes répétés ville par ville)
- Solution : injecte du contenu unique par row (vraies données locales : population, climat, témoignages, photos différentes)

**Gain** : un site programmatique bien fait = des dizaines de milliers de visiteurs/mois sur des keywords low-volume mais cumulés.

## Recette 9 : Newsletter from articles

**Profil** : tu as une newsletter, tu veux que tes articles servent aussi à la newsletter sans double-travail.

**Stratégie** : RSS-to-newsletter via outil tiers.

1. Active RSS sur ton site (auto en mode hébergé, configure pour autres modes via [external.md](connect/external.md))
2. Branche le RSS dans Mailchimp / Substack / Beehiiv / SendFox via leur intégration RSS
3. Tes articles publiés = email envoyé automatiquement (selon ta cadence)

Format Beehiiv recommandé : digest hebdomadaire ("This week's articles") qui regroupe les 3-5 articles publiés. Évite l'email spam.

## Recette 10 : Recovery après pénalité Google

**Profil** : tu as eu une chute soudaine de trafic après un Google Update. Pénalité algorithmique probable.

**Diagnostic** :
1. **Audit global** : repère les articles avec score < 60/100
2. **Plagiarism check** : si tu as scrapé ou si l'IA a généré du contenu trop générique
3. **EEAT** : signal expertise faible ?
4. **Backlinks toxiques** : audit via Ahrefs / Majestic (outil tiers)

**Plan de recovery (3-6 mois)**
1. Supprime / désindexe les articles low-quality (`<meta name="robots" content="noindex">`)
2. Re-écris en profondeur tes top 10 articles (300+ ajouts, restructuration, FAQ)
3. Renforce ton EEAT (auteur identifié, photo, bio, credentials, sameAs vers profils sociaux)
4. Schema.org Article + Person + Organization sur tout le site
5. Désavoue les backlinks toxiques via Google Disavow Tool
6. Demande une réindexation via GSC
7. Patiente. Recovery = lent (3-6 mois). Pas de quick win.

**Si pénalité manuelle** : contestation via "Manual actions" dans GSC. Réponse Google sous 2-4 semaines.
