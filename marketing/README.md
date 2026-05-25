# Gridar Marketing (Next.js 16)

Public-facing pages of gridar.app, served by Next.js for SSG/SSR. The
auth-walled dashboard lives in the parent repo (Vite SPA at `/`) and is
proxied transparently from this app via Next.js rewrites.

## Pages shipped

| Route | Mode | Source |
|---|---|---|
| `/` | Static (client component) | `components/LandingPage.tsx` |
| `/blog` | ISR 1h | `app/blog/page.tsx` |
| `/blog/[slug]` | SSG via generateStaticParams + ISR 1h | Fetches HostedPost site 6 from Django |
| `/docs` | Static | Reads `../docs/README.md` at build time |
| `/docs/[...slug]` | SSG | Reads `../docs/*.md` at build time |
| `/api-docs` | Static | Hardcoded endpoint list |
| `/audit` | Static shell + client form | Hits `api.gridar.app/api/public/audit/` |
| `/privacy` | Static | Inline content |
| `/terms` | Static | Inline content |
| `/sitemap.xml` | ISR 1h | Lists all routes + every blog slug |

## Dev

```
npm install
npm run dev    # http://localhost:3000
```

The marketing site reads:
- `NEXT_PUBLIC_API_URL` (default `https://api.gridar.app`)
- `NEXT_PUBLIC_BLOG_SITE_ID` (default `6`)
- `NEXT_PUBLIC_DASHBOARD_URL` (default `https://gridar.app`)
- `DASHBOARD_INTERNAL_URL` (Phase 6 - the Vite Vercel preview URL the
  rewrites point at, e.g. `https://gridar-dashboard.vercel.app`)

## Deploy on Vercel (Phase 6 handoff)

The marketing site keeps the `gridar.app` domain. The dashboard (Vite
SPA) moves to a Vercel-only URL and is proxied via rewrites.

### Step 1: deploy the marketing project (new)

1. Vercel dashboard > Add New > Project
2. Import `TokDar2410621/blog-dashboard`
3. Framework: **Next.js** (auto-detected)
4. **Root Directory**: `marketing`
5. Build command: leave default (`next build`)
6. Environment variables (Production):
   - `NEXT_PUBLIC_API_URL` = `https://api.gridar.app`
   - `NEXT_PUBLIC_BLOG_SITE_ID` = `6`
   - `NEXT_PUBLIC_DASHBOARD_URL` = `https://gridar.app`
   - **Leave `DASHBOARD_INTERNAL_URL` empty for now** (we'll set it
     after step 2)
7. Deploy

Note the preview URL Vercel assigns, e.g. `gridar-marketing.vercel.app`.

### Step 2: detach the dashboard from gridar.app

The current "Gridar" Vercel project (Vite, root `/`) currently owns
`gridar.app`. To make room for the new marketing project:

1. Project > Settings > Domains
2. Remove `gridar.app` and `www.gridar.app` from this project
3. Note the project's Vercel-only URL, e.g. `gridar.vercel.app` or
   `blog-dashboard-XXX.vercel.app`

This project is now reachable only at its `.vercel.app` URL. Don't
delete it. The rewrites will forward to it.

### Step 3: attach gridar.app to the marketing project

1. Open the **marketing** project (the new one from step 1)
2. Settings > Domains > Add domain
3. Add `gridar.app` and `www.gridar.app`
4. Vercel will assign them (no DNS change needed since they already
   point at Vercel)

### Step 4: wire the proxy

Back in the **marketing** project:

1. Settings > Environment Variables (Production)
2. Set `DASHBOARD_INTERNAL_URL` = `https://<vite-vercel-url>` from
   step 2 (no trailing slash)
3. Redeploy (Deployments tab > latest > Redeploy)

The `next.config.ts` rewrites read `DASHBOARD_INTERNAL_URL` and
transparently proxy `/dashboard/*`, `/login`, `/onboarding/*`, `/sites/*`
to the Vite project. Users keep seeing `gridar.app/dashboard/...` in
their address bar.

### Step 5: smoke test

- `curl -s https://gridar.app/ | grep "Gridar"` -> the new Next.js HTML
- `curl -sI https://gridar.app/dashboard/6/articles` -> 200 (proxied to
  Vite via the rewrite)
- `curl -s https://gridar.app/sitemap.xml` -> XML listing every blog
  slug
- `curl -s https://gridar.app/blog/comment-ranker-google-quebec-2026`
  -> the article HTML (Googlebot test)
- Open `https://gridar.app/audit` in a browser and submit a domain.
  Should hit `api.gridar.app/api/public/audit/`.

### Step 6 (later, when stable): cleanup

After 1-2 weeks of stable marketing in prod:

- Delete the old marketing pages from the Vite project (`src/pages/
  Landing.tsx`, `Blog.tsx`, `BlogPost.tsx`, `Privacy.tsx`, `Terms.tsx`,
  `ApiDocs.tsx`, `Docs.tsx`, `PublicAudit.tsx`) and their routes in
  `src/App.tsx`
- Remove `MarketingSitemapView` from `backend/sites_mgmt/views.py` +
  its URL + the Vercel rewrite (Next.js serves `/sitemap.xml` now)
- Remove `vercel.json` headers/rewrites that referenced the marketing
  surface (now handled in `next.config.ts`)

## Rollback

If anything breaks:

1. Vercel marketing project > Settings > Domains > remove `gridar.app`
2. Vercel Vite project > Settings > Domains > add `gridar.app` back

Total downtime: 30-60 seconds (DNS at Vercel propagates fast).
The marketing pages still exist in the Vite project until Step 6
cleanup, so users see the old version while you investigate.

## Architecture notes

The Vite dashboard and the Next.js marketing share **zero runtime
code**. Components were copied (Button, Card, Input, Label, GridarMark,
ProductMockup3D, WorkflowIA3D, Terminal3D) not symlinked. If you edit
a dashboard component, the marketing version doesn't change, and vice
versa. Intentional: marketing copy changes shouldn't risk a dashboard
regression.

Shared types (BlogPost, etc.) are duplicated in `marketing/lib/blog-api.ts`.
The Django API is the contract; both apps consume it via `fetch()`.
