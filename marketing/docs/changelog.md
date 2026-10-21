# Changelog

Mises à jour récentes du produit. Format : `YYYY-MM-DD - feature/fix - description`.

## 2026-09

- **2026-09-01** - feature - Connecteur MCP publié sur le registre officiel MCP (namespace `app.gridar`, serveur distant). Une server card publique décrit le transport, l'authentification et les 69 outils, pour que les annuaires MCP puissent l'indexer sans jeton.
- **2026-09-01** - fix - Recherche de mots-clés : les suggestions et les questions « Les gens demandent aussi » sortent dans la langue demandée (elles sortaient en anglais pour une recherche en français). Le français accentué est reconnu et les variantes d'un même mot-clé sont reliées.
- **2026-09-01** - feature - Recherche de mots-clés : la pertinence métier est triée avant de dépenser des crédits de SERP, et le résultat dit quelle source a répondu.
- **2026-09-01** - fix - Recherche de mots-clés : un paramètre envoyé à la source SERP supprimait deux sources de suggestions sur trois. Retiré.

## 2026-08

- **2026-08-30** - fix - Connexion Google Search Console : le code OAuth n'est plus perdu au retour de Google (la redirection de connexion supprimait les paramètres d'URL).
- **2026-08-27** - feature - Outil gratuit de visibilité IA : ChatGPT (OpenAI) mesuré en plus de Gemini. Un moteur en panne ou hors quota s'affiche comme indisponible au lieu de compter comme « ne te cite pas ».
- **2026-08-27** - fix - Outils gratuits : « Can I Rank? » lit le vrai SERP au lieu de deviner les concurrents ; l'intention d'une requête se juge sur son SERP ; un site classé #1 n'est plus déclaré hors sujet à cause des accents ; le verdict ne contredit plus le score qu'il résume.
- **2026-08-26** - fix - Calculateur ROI : il demande le nombre de demandes reçues par mois (appels, formulaires, courriels) et en dérive le taux de conversion. Le taux reste saisissable pour ceux qui le mesurent.
- **2026-08-25** - fix - Calculateur ROI : il ne compte plus le chiffre d'affaires déjà acquis. Competitor Gap trouve de vrais concurrents (il n'en trouvait aucun). La stratégie locale se lit dans le schema.org du site.
- **2026-08-24** - feature - Pages du connecteur MCP : `/mcp`, `/gridar-pour-claude`, `/gridar-pour-chatgpt`, `/gridar-pour-agent`.
- **2026-08-24** - fix - Comparaison de concurrents : les deux domaines sont mesurés sur les mêmes composantes au lieu d'estimations. Les résultats PageSpeed sont mis en cache 24 h. Un site qui répond en brotli n'est plus lu comme une page sans titre ni H1.
- **2026-08-23** - fix - Audit public : le score dit sur quoi il repose et intègre les signaux on-page. Les mots-clés proposés ne viennent plus du menu ou du pied de page du site.
- **2026-08-23** - fix - Audit d'article : un chiffre sans source ne compte plus comme un point fort.
- **2026-08-23** - design - Refonte de l'accueil et des pages d'outils (héros, navigation unifiée, menu mobile, pied de page).
- **2026-08-22** - fix - Les outils gratuits de visibilité IA disent quels moteurs ils testent vraiment.
- **2026-08-18** - feature - 7 outils gratuits sans compte sous [/tools](https://www.gridar.app/tools) : audit SEO, visibilité IA, citation IA, Competitor Gap, comparaison de concurrents, « Can I Rank? », calculateur ROI.
- **2026-08-15** - fix - Audit public : ce qui compte des mentions ne s'appelle plus « backlinks » ; « hors top 50 » ne s'affiche plus quand la vérification a échoué.
- **2026-08-14** - feature - Score SEO : une vérification sans donnée ne compte plus comme un échec ; son poids passe aux vérifications mesurées. Le JSON-LD généré est validé avant livraison. Garde-fou contre les landings tremplin sans contenu propre.
- **2026-08-14** - fix - Sécurité de l'audit public (requêtes vers des adresses internes bloquées). Le PDF du rapport sort lisible.
- **2026-08-13** - feature - Les landings « outil » exécutent leur outil (audit, suivi de position, calculateur de prix) au lieu de le décrire.
- **2026-08-07** - fix - Inspection d'indexation GSC bornée dans le temps (plus de timeout). Corrections de l'audit (« Erreur indexation »).
- **2026-08-03** - feature - Re-soumettre un sitemap à Google Search Console par l'API ou le connecteur MCP.
- **2026-08-02** - feature - Galerie d'images branchée. « Voir sur le site » apparaît seulement pour les sites hébergés par Gridar. 13 correctifs du dashboard (plantages, liens 404, états manquants).
- **2026-08-01** - fix - Topic clusters : plus de plantage quand le site a moins de 3 articles.

## 2026-07

- **2026-07-29** - fix - Connexion GSC : la propriété est remplie à la connexion (un site « connecté » restait inerte). Un échec GSC de l'audit d'indexation n'est plus jamais silencieux. Sitemap, canonical et Open Graph alignés sur le host canonique.
- **2026-07-28** - feature - Gridar détecte le chemin de livraison de chaque site (CMS, base externe, mode agent, hébergé). Sans chemin, la génération est grisée avec la raison affichée, l'API renvoie `409 delivery_blocked` et l'autopilote saute le site au lieu d'écrire dans le vide.
- **2026-07-26** - feature - IndexNow : soumission des URLs à Bing et aux moteurs participants (Google n'utilise pas IndexNow), par l'API ou le connecteur MCP. Gridar soumet seul l'URL quand un article hébergé passe en publié par l'API ou quand un agent marque une page construite. Fichier de clé servi automatiquement pour les sites hébergés.
- **2026-07-25** - fix - Gridar résout la vraie propriété Search Console (y compris les propriétés de domaine) partout : preuve, decay, positions, inspection d'URL.
- **2026-07-24** - feature - Couverture d'indexation Google dans « Audit du site » : pages indexées, non indexées et vues par Google, avec la raison de chaque page non indexée.
- **2026-07-22** - feature - Carte des topic clusters du site et construction d'un cluster complet (pilier + articles satellites) par l'API ou le connecteur MCP, avec le maillage interne prévu dans chaque brief.
- **2026-07-21** - feature - Mode de livraison « agent » : un agent IA reçoit les pages à créer via la build-queue MCP, puis Gridar suit l'URL live de chaque page construite. Suggestions de prompts à suivre pour la visibilité IA. Archivage des opportunités déjà créées.
- **2026-07-19** - fix - Preuve honnête : la page de preuve publique liste tous les articles suivis (en baisse et à plat inclus) et ne compte plus les pages antérieures à Gridar. Sur un blog hébergé ou une base externe, un article généré part en brouillon par défaut. Sur WordPress, Shopify et Webflow, il reste publié dès sa création.
- **2026-07-18** - feature - Verdict de ta fiche Google Business dans l'audit.
- **2026-07-16** - fix - Export de prompt de page : langue adaptée au marché visé, animations cohérentes avec le site.
- **2026-07-15** - fix - Opportunités sur un site externe : plus d'échec silencieux, Gridar dit ce qui bloque et propose la suite.
- **2026-07-14** - feature - Opportunités séparées en deux : celles que Gridar peut générer et celles qui demandent un asset à construire. Sauvegarde des réglages fiable, avec des erreurs lisibles.
- **2026-07-13** - fix - Positions : correspondance exacte du domaine (plus de positions gonflées), position calculée sur plusieurs relevés cohérents et date de dernière vérification affichée. Génération : modèles IA mis à jour, recherche de repli quand la source SERP ne répond pas.
- **2026-07-13** - feature - Outil de suivi de position géolocalisé sur [/suivi-position-google-canada](https://www.gridar.app/suivi-position-google-canada).
- **2026-07-04** - fix - Les landings hébergées se mettent à jour en 5 minutes au lieu d'une heure.

## 2026-06

- **2026-06-20** - fix - Audit public : la page de partage montre le rapport complet, avec les vraies données après capture de l'e-mail ; le PDF n'affiche plus de contenu masqué.
- **2026-06-13** - feature - Rapport d'audit partageable sur `/rapport/<token>`. L'audit du site s'affiche en 1 seconde environ au lieu d'attendre PageSpeed. Les réglages GSC montrent l'état connecté.
- **2026-06-12** - fix - Boucle de redirection et 403 sur les appels API corrigés ; connexion OAuth réparée.
- **2026-06-11** - feature - Le dashboard tourne dans la même application que le site, sur [www.gridar.app](https://www.gridar.app).

## 2026-05

- **2026-05-08** - feature - Documentation produit complète : 14+ pages couvrant tous les workflows (getting-started, 5 modes de connexion, génération IA, outils SEO, plans + crédits, API, recettes pratiques)
- **2026-05-07** - feature - Système de crédits à la pièce (10/50/200 crédits à 25$/99$/299$) consommés après quota mensuel épuisé. Stripe one-time payments, idempotent webhook
- **2026-05-07** - feature - Nouveau plan **Solo** à 29.99$/mois (1 site, 8 articles/mois, 10 mots-clés). Renumérotation des plans : Essai → Solo → Pro (89.99$) → Agence (199.99$) → Enterprise (contact). Quotas serrés.
- **2026-05-07** - fix - Mobile sidebar trigger : un hamburger apparaît sur les écrans < 768px pour ouvrir l'offcanvas sidebar (avant : sidebar inaccessible sur mobile)
- **2026-05-07** - fix - Toast d'erreur occulté par l'overlay Radix Dialog : SiteSelector ferme maintenant le dialog avant d'afficher le toast pour qu'il soit visible
- **2026-05-07** - feature - Enforcement des limites de plan : sites_max + keywords_max maintenant bloqués au backend (avant : limites définies mais jamais enforcées). Articles_per_month enforcé via MonthlyArticleQuota (atomic)
- **2026-05-07** - feature - QuotaBanner + sidebar quota indicator + inline error card sur AIGenerator. UX progressive : vert / amber / rouge selon usage
- **2026-05-07** - test - 19 tests Cypress E2E (5 specs : quota-banner, sidebar-indicator, generate-blocked, credits/purchase, limits/sites-keywords). Backend Django : 20 tests unitaires sur la logique quota
- **2026-05-06** - feature - Auto-scan branding pendant le connect (logo, couleur, fonts) avec preview live dans les 3 dialogs (WordPress / Shopify / Webflow)
- **2026-05-06** - feature - Sitemap.xml + RSS.xml publics par site (`GET /api/sites/<id>/sitemap.xml`). Cache 1h CDN. Pour mode externe surtout.
- **2026-05-06** - feature - Page /onboarding/external avec scaffolder de routes React/Next.js (4 frameworks supportés : Next App Router, Next Pages, React Router, Vite SPA)
- **2026-05-06** - feature - Endpoint `GET /api/v1/sites/<id>/articles/<slug>/` (détail article avec content) - manquait avant
- **2026-05-06** - feature - Adapter Webflow CMS API v2 + dialog 3-étapes (token → site → collection) avec auto-détection des champs (post-body, post-summary, main-image)
- **2026-05-06** - feature - Adapter Shopify Admin API + dialog 2-étapes (creds → blog selection). Custom App tokens
- **2026-05-06** - feature - Branding extractor : `POST /api/branding/scan/` extrait theme-color, logo, fonts d'un domaine via crawl HTML+CSS
- **2026-05-05** - feature - API REST publique `/api/v1/*` avec Bearer auth et rate limit par plan. 9 endpoints curés. Page /api-docs avec exemples curl. Page /account/api-keys pour manage tokens (sha256 hash, plain shown once)
- **2026-05-05** - design - Landing refondue style Linear/Vercel : reveal-on-scroll, marquee tech stack, theme emerald cohérent, em-dashes éliminés
- **2026-05-05** - feature - Redesign hero Landing : ProductMockup3D animé, Workflow IA en 4 étapes, Terminal3D animé sur ApiDocs, Login split-screen, BrowserBlogPreview3D dans OnboardingExternal
- **2026-05-05** - feature - Confetti emerald au connect d'un premier site

## 2026-04 et avant

- Outils SEO : Brief de contenu, Audit IA, Suivi positions GSC, Topic clusters, Content decay, Link graph, Redirections, Liens cassés
- Lexique FR-CA + EEAT + LocalBusiness schemas
- Multi-domaines (Agence)
- Génération IA Claude Sonnet avec recherche Serper + maillage interne automatique + anti-cannibalisation

Suggestions et demandes : `tokamdarius@gmail.com`.
