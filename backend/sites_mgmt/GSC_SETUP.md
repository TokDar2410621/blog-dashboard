# Google Search Console (GSC) Integration Setup

This document explains how to wire the dashboard to Google Search Console so
each article can display real impressions / clicks / CTR / position per query,
and how to boost the SEO score based on actual performance.

## 1. Minimal setup (recommended) - reuse the existing Google login client

If you already have Google login configured for Gridar (env vars
`GOOGLE_OAUTH_CLIENT_ID` + `GOOGLE_OAUTH_CLIENT_SECRET`), GSC can piggy-back
on the **same** Google Cloud OAuth client. There are **zero new env vars** to
set. Just update the existing client in Google Cloud Console:

1. Open the [Google Cloud Console](https://console.cloud.google.com/) and
   select the project that holds the OAuth client used for Google login.
2. Enable the **Search Console API** for that project:
   `APIs & Services` -> `Library` -> search `Search Console API` -> `Enable`.
3. Go to `APIs & Services` -> `OAuth consent screen` and **add the scope**
   `https://www.googleapis.com/auth/webmasters.readonly`
   to the list of scopes the app requests.
   While the app is in `Testing` mode, add yourself (and any other owner) as
   a **test user**.
4. Go to `APIs & Services` -> `Credentials`, open the existing OAuth client
   (the one used for login), and under **Authorized redirect URIs** add the
   GSC callback URL for each environment you run:
   - Production: `https://gridar.app/gsc/callback`
   - Local dev:  `http://localhost:5173/gsc/callback`

That's it. The backend will reuse `GOOGLE_OAUTH_CLIENT_ID` /
`GOOGLE_OAUTH_CLIENT_SECRET` and derive the redirect URI from
`GOOGLE_OAUTH_CALLBACK_URL` by swapping `/auth/google/callback` for
`/gsc/callback`.

## 2. Advanced setup (optional) - separate OAuth client just for GSC

Use this if you want isolation between login and Search Console (different
test users, different consent screen, etc.). Create a dedicated OAuth client
following the standard Google Cloud flow (Web application type, enable the
Search Console API, add the `webmasters.readonly` scope, add a redirect URI
ending in `/gsc/callback`), then override with these env vars:

```
GSC_CLIENT_ID=xxxxxxxxxxxx.apps.googleusercontent.com
GSC_CLIENT_SECRET=GOCSPX-xxxxxxxxxxxxxxxxx
GSC_REDIRECT_URI=https://your-dashboard.example.com/gsc/callback
```

When set, these take precedence over the login client. `GSC_REDIRECT_URI`
**must exactly match** one of the authorized redirect URIs configured on
that client in Google Cloud Console. All three vars are optional - leave
them unset to fall back to the minimal-setup path above.

## 3. Verify your site in Search Console

Each Site that wants GSC data must have a verified Search Console property.

1. Go to <https://search.google.com/search-console/>.
2. Add your property (URL-prefix style, e.g. `https://tokamdarius.ca/`).
3. Verify ownership (DNS TXT record, HTML meta tag, Google Analytics, etc.).

Then, in the dashboard, set `gsc_property_url` on the Site (via the Site
settings UI or admin) to the exact property URL, **including the trailing
slash**:

```
https://tokamdarius.ca/
```

## 4. Connect the Site to GSC

1. Open an article in the dashboard editor and switch to the **SEO** view.
2. In the `Search Console (vraie perf)` card, click
   `Connecter Google Search Console`.
3. A new tab opens to Google's consent screen. Pick the account that owns the
   verified property and click `Allow`.
4. Google redirects to `GSC_REDIRECT_URI` with `?code=...&state=...`. The
   frontend `GSC callback` page should POST that payload to
   `POST /api/sites/<id>/gsc/oauth-callback/` with `{code, state}` in the JSON
   body. The backend exchanges the code for tokens and persists the
   `refresh_token` on the Site.
5. Reload the article. The card now shows the top queries (up to 25) with
   clicks, impressions, CTR, and average position.

## 5. How the score is computed

The "Score perf réelle" shown next to the queries table is:

```
score = min(100, clicks * 2 + impressions / 100)
```

Summed across the top 25 queries of the article over the last 28 days. This is
intentionally simple and additive to the usual static SEO score.

## 6. Endpoints

All endpoints require authentication (JWT like the rest of the dashboard).

- `GET  /api/sites/<site_id>/gsc/oauth-url/`
  Returns `{ url }` - the Google consent URL. Includes `state` = base64 site id.

- `POST /api/sites/<site_id>/gsc/oauth-callback/`
  Body: `{ code, state }`. Exchanges and stores the refresh token on the Site.
  State is validated against `site_id`.

- `GET  /api/sites/<site_id>/gsc/queries/?slug=<slug>&days=28`
  Returns `{ page_url, days, queries: [...] }` where each query is
  `{ query, clicks, impressions, ctr, position }`. The page URL filter is
  built as `gsc_property_url + slug/`. On auth failure (no refresh token,
  revoked grant, expired refresh token, 401/403 from Google) the endpoint
  returns `401` with body `{ error: "Reconnecte GSC", code: "gsc_reauth_required" }`;
  the frontend then shows the `Connecter Google Search Console` button again.

## 7. Security notes

- `gsc_refresh_token` is stored as `TextField` on the Site model. The column
  help text says "chiffré"; at-rest encryption is the responsibility of the
  database layer (Postgres TDE, Railway disk encryption, etc.). If you need
  application-level encryption, wrap `save`/property accessors with
  `cryptography.fernet.Fernet` using a key from `GSC_TOKEN_ENCRYPTION_KEY`.
- Only the `webmasters.readonly` scope is requested - the dashboard cannot
  modify Search Console data.
- The refresh token is never exposed in any serializer. Only
  `gsc_property_url` is exposed on the Site API.

## 8. Troubleshooting

- **`No refresh token returned`**: Google only returns a refresh token the
  first time the user authorizes the app. If you re-authorize, revoke access
  at <https://myaccount.google.com/permissions> first, or the backend will
  reject the code exchange.
- **`403: User does not have sufficient permission for site...`**: the
  account used for OAuth is not an owner/user of the Search Console property.
  Add them in GSC -> `Settings` -> `Users and permissions`.
- **Empty queries**: the page URL filter is strict. Make sure the article's
  public URL on the live site matches `gsc_property_url + slug/` exactly
  (trailing slash, protocol, www/non-www).
