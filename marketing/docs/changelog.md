# Changelog

Mises à jour récentes du produit. Format : `YYYY-MM-DD - feature/fix - description`.

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

## Roadmap (Q3+ 2026)

- Q3 - Adapter Wix + Squarespace
- Q3 - n8n custom node officiel
- Q3 - Edge rewrite OAuth (Vercel / Netlify) pour mode subfolder sans toucher le code client
- Q3 - Branded reports PDF (Agence)
- Q4 - Multilingue avancé Polylang/WPML pour WordPress
- Q4 - Image generation custom (Stable Diffusion self-hosted)
- 2027 - Analyse concurrentielle automatique (cron mensuel + alertes)

Suggestions et demandes : `tokamdarius@gmail.com`.
