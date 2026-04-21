# Google Search Console (GSC) Integration Setup

This document explains how to wire the dashboard to Google Search Console so
each article can display real impressions / clicks / CTR / position per query,
and how to boost the SEO score based on actual performance.

## 1. Create a Google Cloud OAuth client

1. Open the [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project (or select an existing one), e.g. `blog-dashboard-gsc`.
3. Enable the **Search Console API** for that project:
   `APIs & Services` -> `Library` -> search `Search Console API` -> `Enable`.
4. Configure the OAuth consent screen:
   - `APIs & Services` -> `OAuth consent screen`.
   - User type: **External** (or Internal if you use Google Workspace).
   - App name, support email, developer contact: fill in.
   - Scopes: add
     `https://www.googleapis.com/auth/webmasters.readonly`.
   - Add yourself (and any other owner) as a **test user** while the app is in
     `Testing` mode.
5. Create OAuth2 credentials:
   - `APIs & Services` -> `Credentials` -> `Create credentials` -> `OAuth client ID`.
   - Application type: **Web application**.
   - Authorized redirect URIs: add the URL the dashboard will use to receive
     the OAuth `code`. Example for local dev:
     `http://localhost:5173/gsc/callback`.
     For production, use the deployed dashboard URL, e.g.
     `https://dashboard.tokamdarius.ca/gsc/callback`.
6. Copy the **Client ID** and **Client secret**.

## 2. Set backend environment variables

Add these to your `.env` (or Railway / deployment environment):

```
GSC_CLIENT_ID=xxxxxxxxxxxx.apps.googleusercontent.com
GSC_CLIENT_SECRET=GOCSPX-xxxxxxxxxxxxxxxxx
GSC_REDIRECT_URI=http://localhost:5173/gsc/callback
```

`GSC_REDIRECT_URI` **must exactly match** one of the authorized redirect URIs
configured in the Google Cloud console.

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
  Returns `{ url }` — the Google consent URL. Includes `state` = base64 site id.

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
- Only the `webmasters.readonly` scope is requested — the dashboard cannot
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
