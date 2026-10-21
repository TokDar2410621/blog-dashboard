# Gridar

> SEO content for Quebec SMBs, bilingual FR-CA.
> Generate, audit and deliver articles to WordPress, Shopify, Webflow, a blog hosted by Gridar, or your own site.

**Made by [Arivex Studio](https://arivex.ca).** App: <https://www.gridar.app> · API: <https://api.gridar.app> · Docs: <https://www.gridar.app/docs>

## What it does

- **Article generation** (FR / EN / ES, 7 article types): SERP research, writing, images, internal links, delivered to the site's CMS or stored as a draft for hosted and external sites.
- **Delivery check**: Gridar detects how each site receives content (CMS, external database, hosted blog, agent mode) and blocks generation when nothing would reach the site.
- **Audits**: per-article SEO audit, bulk audit, site audit with Google indexation coverage, PageSpeed.
- **Keywords and SERP**: keyword research (related searches + People Also Ask, no search volume), rank tracking on manual snapshots, SERP analyzer, content briefs.
- **Content health**: content decay (Google Search Console), topic clusters, internal link map, broken links, redirects.
- **Search Console**: OAuth connection, real queries, proof page, sitemap resubmission (API / MCP).
- **IndexNow** submission (Bing and participating engines) through the API and MCP.
- **Integrations**: public REST API (Pro and Agency plans), hosted MCP server with 69 tools, n8n workflows over HTTP.
- **Free public tools** (no account) under [/tools](https://www.gridar.app/tools) and [/audit](https://www.gridar.app/audit).

Known gaps are listed in the docs: no scheduled jobs run in production yet, and dashboard AI visibility is not wired to any AI engine (the free checker is).

## Architecture

| Layer | Stack | Hosted on |
|---|---|---|
| Backend | Django 5.2 + DRF + Postgres | Railway (`api.gridar.app`) |
| App + marketing site + docs | Next.js 16 + React 19 + TypeScript + Tailwind | Vercel (`www.gridar.app`) |
| Hosted customer blogs | Next.js 14 (`public-blog/`) | Vercel |
| MCP server | Node + `@modelcontextprotocol/sdk`, Streamable HTTP + OAuth 2.1 | Railway (`mcp.gridar.app`) |
| AI and data | Anthropic Claude (DeepSeek fallback), Gemini, OpenAI (free AI visibility tool), Serper, Google PageSpeed, Voyage AI | Pay-per-use |
| Payments | Stripe subscriptions + one-time credit packs | Stripe |

## Repo layout

```
backend/                  Django project (API, generation, audits, billing)
marketing/                Next.js app: dashboard, marketing pages, free tools
marketing/docs/           User-facing product documentation (FR-CA), served at /docs
public-blog/              Next.js blog for hosted-mode customers
mcp-server/               Model Context Protocol server (hosted + npm package)
n8n-node/                 n8n node (not published on npm)
wordpress-plugin/         WordPress connector plugin (not published)
e2e/                      Playwright tests against production
cypress/                  Cypress E2E tests
```

## Local development

```bash
# Backend
cd backend
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver

# App (separate terminal)
cd marketing
npm install
npm run dev
```

Tests: `cd backend && python manage.py test sites_mgmt` for the backend. The root `package.json` keeps the Cypress and brand-asset scripts.

## Deployment

- Backend: Railway deploys on push to `main`.
- App (`marketing/`): manual deploy with `npx vercel --prod --cwd marketing`. A push alone does not update production.

## Documentation

User-facing docs live in [marketing/docs/](marketing/docs/) and are served at <https://www.gridar.app/docs>.

## License

Proprietary. © Arivex Studio. All rights reserved.
