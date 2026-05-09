# Gridar

> SEO content on autopilot for Quebec PMEs.
> 12 SEO agents in one product. Generate, audit and publish articles to WordPress, Shopify, Webflow or a hosted blog — without touching your code.

**Made by [Arivex Studio](https://arivex.ca).**

## What it does

Gridar bundles 12 specialized SEO agents into one SaaS:

- **ArticleGenerator** — Claude + Serper, FR/EN/ES, 7 archetypes
- **AuditEngine** — 0-100 SEO score + actionable suggestions
- **BriefBuilder** — search intent, outline, FAQ, entities
- **KeywordResearch** — Serper + Gemini cross-checked volumes
- **RankTracker** — daily SERP snapshots, geo-restricted to Quebec by default
- **ContentDecay** — flags articles losing >30% traffic
- **TopicClusters** — semantic grouping of your content
- **LinkGraph** — internal linking opportunities
- **BrokenLinkChecker** — periodic 404 crawl
- **PlagiarismChecker** — detect copy-paste with the wider web
- **ReadabilityScorer** — Flesch + lexical complexity
- **PageSpeedAuditor** — Core Web Vitals via Google PSI

Plus: GSC OAuth, hreflang for multilingual, weekly digests, multi-domain dashboards, Stripe billing with credits, public REST API, MCP server, n8n community node.

## Architecture

| Layer | Stack | Hosted on |
|---|---|---|
| Backend | Django 5 + DRF + Postgres | Render |
| Frontend | React 19 + Vite + TypeScript + Tailwind v4 + shadcn/ui | Vercel |
| AI | Anthropic Claude, Gemini, Serper, Google PSI | Pay-per-use |
| Payments | Stripe Subscriptions + one-time credits | Stripe |
| Integrations | MCP server (`@gridar/mcp-server`), n8n node (`n8n-nodes-gridar`), public REST API | npm + self-hosted |

## Repo layout

```
backend/                  Django project
src/                      React frontend
public-blog/              Next.js public blog (hosted-mode customers)
docs/                     User-facing product documentation (FR-CA)
mcp-server/               Model Context Protocol server (npm package)
n8n-node/                 n8n community node (npm package)
cypress/                  E2E tests
```

## Local development

```bash
# Backend
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver

# Frontend (separate terminal)
npm install
npm run dev

# Visit http://localhost:5173
```

## Documentation

User-facing docs live in [docs/](docs/) and are served at [/docs/*](https://gridar.app/docs).

## License

Proprietary. © Arivex Studio. All rights reserved.
