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
| 0 | Cutover domaine gridar.app -> gridar-marketing | FAIT 2026-06-11 (www primaire, apex 308 -> www) |
| 1 | auth/account surface (10 pages) | FAIT 2026-06-11 |
| 2 | Dashboard core | FAIT 2026-06-11 (fleet 13 agents) |
| 3 | Tools (12 routes) | FAIT 2026-06-11 |
| 4 | Settings (9 sous-pages + context) | FAIT 2026-06-11 |
| 5 | PostList + PostEditor + AIGenerator | FAIT 2026-06-11 |
| 6 | SPA supprime (src/, vite, vercel.json racine), rewrites proxy retires | FAIT 2026-06-11 - MIGRATION TERMINEE |

## Notes techniques accumulees

- Le SPA garde /unsubscribe et HostedLandingPage jusqu'au batch 6 (deja
  jumelees dans marketing).
- PostEditor utilise ResizablePanelGroup + mobilePanel switcher (commit
  7cb828a) : porter tel quel.
- JobsContext/JobsDock (SPA) : a porter au batch 2 (le dashboard en depend).
- recharts present dans marketing? NON - npm i recharts au debut du batch 2.
- react-i18next : les pages EN existantes meurent avec le SPA.

## POST-MIGRATION (2026-06-11, reste a faire)

- CRITIQUE : NEXT_PUBLIC_GOOGLE_OAUTH_CLIENT_ID + NEXT_PUBLIC_GITHUB_OAUTH_CLIENT_ID
  absents du projet gridar-marketing (valeurs perdues avec le projet Vercel
  supprime). Login Google/GitHub INDISPONIBLE (boutons caches) tant que Darius
  ne les recupere pas (Google Cloud Console / GitHub Developer Settings) et ne
  les pose pas + redeploy. Email+password fonctionne.
- Brancher Git sur gridar-marketing (Settings > Git, Root Directory=marketing)
  pour les auto-deploys; sinon deploys via `cd marketing && npx vercel deploy --prod`.
- Supprimer le projet Vercel placeholder `gridar-app-spa` (jamais deploye).
- Optionnel : remettre gridar.app (apex) comme domaine primaire au lieu de www
  (les canonicals du code pointent sur gridar.app sans www).
- Smoke runtime navigateur a faire par Darius : login email, navigation
  dashboard, editeur, un cycle generer/publier.
