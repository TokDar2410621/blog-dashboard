# Migration totale SPA -> Next.js (gridar.app)

Decision Darius 2026-06-11 : "on va supprimer toutes les pages SPA et mettre
toutes les pages en Next". Le Vite SPA disparait a terme; marketing/ devient
LA seule app frontend.

## Regle d'or

**On ne supprime JAMAIS une page SPA avant que sa jumelle Next soit a parite
et verifiee en prod.** L'architecture proxy (next.config.ts rewrites ->
DASHBOARD_INTERNAL_URL) rend la migration incrementale : des qu'une page
native existe dans marketing/app/, elle ecrase silencieusement son rewrite
(filesystem > rewrites). Zero downtime, rollback = supprimer le fichier.

## Conventions de port

- "use client" + next/navigation (useSearchParams => Suspense boundary
  obligatoire dans page.tsx).
- Reutiliser marketing/lib/api-client.ts (surface complete deja portee),
  marketing/context/AuthContext.tsx, marketing/components/ui/*,
  marketing/components/AuthGuard.tsx pour les pages protegees.
- i18n : PAS de react-i18next dans marketing. Resoudre les t('cle') via
  src/i18n/fr.json et hardcoder le francais. (i18n EN = chantier separe
  post-migration si demande.)
- Env vars : VITE_X -> NEXT_PUBLIC_X (a poser sur le projet Vercel
  gridar-marketing).
- Jamais de em-dash dans les strings.

## Batches

| # | Pages | Statut |
|---|---|---|
| 0 | Cutover domaine gridar.app -> gridar-marketing | EN ATTENTE clic Darius (voir PENDING_HUMAN) |
| 1 | /login, /reset-password, /sites, /compare, /billing, /account/api-keys, /auth/[provider]/callback, /gsc/callback, /oauth/mcp-authorize, /onboarding/external | EN COURS 2026-06-11 |
| 2 | Dashboard core : layout + sidebar + /dashboard/[siteId] (Overview), audit-site, /dashboard/overview (MultiSite) | a faire |
| 3 | Tools lecture : positions (KeywordTracker), decay, clusters, link-graph, redirects, broken-links, serp-analyzer, ai-visibility, opportunites, digest, audit-global, images | a faire |
| 4 | Settings (9 sous-pages) | a faire |
| 5 | Les gros : articles (PostList), articles/[slug] (PostEditor ~3000 lignes), generer (AIGenerator) | a faire |
| 6 | Suppression des pages SPA + retrait des rewrites proxy + retrait projet Vercel blog-dashboard + DASHBOARD_INTERNAL_URL | a faire EN DERNIER |

## Notes techniques accumulees

- Le SPA garde /unsubscribe et HostedLandingPage jusqu'au batch 6 (deja
  jumelees dans marketing).
- PostEditor utilise ResizablePanelGroup + mobilePanel switcher (commit
  7cb828a) : porter tel quel.
- JobsContext/JobsDock (SPA) : a porter au batch 2 (le dashboard en depend).
- recharts present dans marketing? NON - npm i recharts au debut du batch 2.
- react-i18next : les pages EN existantes meurent avec le SPA.
