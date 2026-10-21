# @gridar/mcp-server

[Model Context Protocol](https://modelcontextprotocol.io) server for [Gridar](https://www.gridar.app).

The server exposes the Gridar REST API (`https://api.gridar.app/api/v1`) as 69 `gridar_*` tools. An MCP client can read and change the sites, articles, landings, tracked keywords, autopilot, site memory and Search Console data of the Gridar account behind the token, and run SEO checks on them.

## Versions

| Distribution | Version | Tools |
| --- | --- | --- |
| Hosted server `https://mcp.gridar.app/mcp` | 0.7.0 | 69 |
| This source (`mcp-server/`) | 0.7.0 | 69 |
| npm package `@gridar/mcp-server` | 0.4.2 | 43 |

Checked on 2026-10-21 with `npm view @gridar/mcp-server version` and the hosted server card. The npm package lags behind: use the hosted server.

## Requirements

- A Gridar account on the **Pro** or **Agency** plan.
- The OAuth login succeeds on every plan, but on Trial and Solo every tool call answers HTTP 403: "Accès API réservé aux plans Pro et Agence".

## Install: hosted server (recommended)

| Item | Value |
| --- | --- |
| URL | `https://mcp.gridar.app/mcp` |
| Transport | Streamable HTTP |
| Authentication | OAuth 2.1 with PKCE, or `Authorization: Bearer btb_xxx` |
| Official MCP registry | `app.gridar/gridar` |
| Public server card (no token) | `https://mcp.gridar.app/.well-known/mcp/server-card.json`: name, version, tool list |
| Health | `https://mcp.gridar.app/health` |

Nothing to install on your machine.

### What the OAuth login does

1. You add `https://mcp.gridar.app/mcp` to your client.
2. Without a token, the server answers 401 with a `WWW-Authenticate` header that points to `/.well-known/oauth-protected-resource`. The client discovers the OAuth endpoints from there.
3. The client opens the Gridar login page. Sign in if needed, then click **Autoriser**.
4. Gridar creates an API token named after the client (for example `MCP - Claude Code`) and hands it to the client.
5. The token shows up at <https://www.gridar.app/account/api-keys>. Revoke it there to cut access.

### Claude (claude.ai and Claude Desktop)

On claude.ai: **Settings > Connectors**, add a custom connector with the URL `https://mcp.gridar.app/mcp`. Claude opens the Gridar login page; authorize and the connector is live.

Claude Desktop through its config file uses the `mcp-remote` bridge:

```json
{
  "mcpServers": {
    "gridar": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "https://mcp.gridar.app/mcp"]
    }
  }
}
```

The file lives at `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows). Restart Claude Desktop afterwards.

### ChatGPT

1. Open **Settings > Connectors**, or turn on Developer Mode for custom connectors.
2. Add a connector by URL: `https://mcp.gridar.app/mcp`.
3. ChatGPT opens the Gridar login page. Authorize.

OpenAI restricts custom connectors by account type. The Gridar page lists ChatGPT Pro, Team, Enterprise, or Developer Mode; check OpenAI's current rules.

### Claude Code

```bash
claude mcp add --transport http gridar https://mcp.gridar.app/mcp
```

OAuth starts on the first call. For a session without a browser, pass a token in a header:

```bash
claude mcp add --transport http gridar https://mcp.gridar.app/mcp \
  --header "Authorization: Bearer btb_xxx"
```

### Cursor

**Settings > MCP > Add server**, server of type URL: `https://mcp.gridar.app/mcp`.

### Codex CLI, SDKs and other clients

Any MCP client that speaks Streamable HTTP connects to `https://mcp.gridar.app/mcp` and finds the OAuth flow on its own (see step 2 above). A headless agent sends `Authorization: Bearer btb_xxx` with a token created at <https://www.gridar.app/account/api-keys>.

## Install: local stdio via npm

> **The npm package is behind.** `@gridar/mcp-server` on npm is 0.4.2 with 43 tools. The hosted server and this source are 0.7.0 with 69 tools. The tool list in this README matches 0.7.0.

The 26 tools missing from npm 0.4.2: `gridar_action_strategic_opportunity`, `gridar_ai_overview_readiness`, `gridar_ai_visibility_summary`, `gridar_approve_strategy`, `gridar_build_cluster`, `gridar_check_renderability`, `gridar_classify_intent`, `gridar_cluster_map`, `gridar_create_landing`, `gridar_export_page_prompt`, `gridar_generate_landing`, `gridar_generate_sister_article`, `gridar_index_coverage`, `gridar_indexnow_setup`, `gridar_indexnow_submit`, `gridar_link_opportunities`, `gridar_link_pages`, `gridar_list_strategic_opportunities`, `gridar_mark_page_built`, `gridar_propose_keyword_strategy`, `gridar_pull_build_queue`, `gridar_refresh_strategic_opportunities`, `gridar_run_ai_visibility`, `gridar_serp_analyze`, `gridar_site_seo_score`, `gridar_submit_sitemap`.

The package installs the `gridar-mcp` binary and reads its token from `BLOG_DASHBOARD_TOKEN`.

Claude Desktop:

```json
{
  "mcpServers": {
    "gridar": {
      "command": "npx",
      "args": ["-y", "@gridar/mcp-server"],
      "env": {
        "BLOG_DASHBOARD_TOKEN": "btb_xxx"
      }
    }
  }
}
```

Claude Code:

```bash
claude mcp add gridar \
  --env BLOG_DASHBOARD_TOKEN=btb_xxx \
  -- npx -y @gridar/mcp-server
```

Any other client: spawn the process over stdio with the token in its environment.

```bash
BLOG_DASHBOARD_TOKEN=btb_xxx npx -y @gridar/mcp-server
```

To get all 69 tools locally, build this source instead (see [Development](#development)).

## Environment variables

Names only. Never commit a real token.

### Stdio (local)

| Variable | Required | Default | Role |
| --- | --- | --- | --- |
| `BLOG_DASHBOARD_TOKEN` | yes | none | Gridar API token (`btb_xxx`) sent as `Authorization: Bearer` |
| `BLOG_DASHBOARD_API_BASE` | no | `https://api.gridar.app/api/v1` | Gridar API base URL |

### Self-hosted HTTP (`node dist/http.js`)

| Variable | Default | Role |
| --- | --- | --- |
| `PORT` | `8080` | Listening port |
| `BLOG_DASHBOARD_API_BASE` | `https://api.gridar.app/api/v1` | Gridar API the server forwards calls to |
| `MCP_PUBLIC_BASE` | `http://localhost:<PORT>` | Public URL of this server, used in the OAuth metadata and redirects |
| `GRIDAR_BASE` | `https://gridar.app` | Gridar app that hosts the OAuth login page (`/oauth/mcp-authorize`) |
| `MCP_REQUIRE_AUTH` | on | Set to `false` to skip the Bearer check (development only) |
| `MCP_ALLOWED_ORIGINS` | `*` | Comma-separated list of allowed CORS origins |
| `OAUTH_CLIENT_ID` | built-in value | Client id returned by dynamic client registration |
| `OAUTH_CLIENT_SECRET` | built-in value | Client secret returned by dynamic client registration |

In HTTP mode the token comes from each request's `Authorization` header and is scoped to that request with `AsyncLocalStorage`. `BLOG_DASHBOARD_TOKEN` stays a fallback: do not set it on a shared server with `MCP_REQUIRE_AUTH=false`, or every caller acts as that account.

HTTP endpoints:

| Method and path | Role |
| --- | --- |
| `POST /mcp` | MCP Streamable HTTP: initialize and tool calls |
| `GET /mcp` | SSE notification stream for an open session |
| `DELETE /mcp` | Closes a session |
| `GET /health` | `{status, name, version, transport, oauth}` |
| `GET /.well-known/mcp/server-card.json` | Public card: server info and tool list, no token needed |
| `GET /.well-known/oauth-protected-resource` | OAuth protected resource metadata (RFC 9728) |
| `GET /.well-known/oauth-authorization-server` | OAuth server metadata (RFC 8414) |
| `POST /register` | Dynamic client registration (RFC 7591) |
| `GET /authorize`, `GET /callback`, `POST /token` | OAuth authorization code flow with PKCE (`S256` or `plain`) |

## Plans and limits

| Plan | API and MCP access | Requests per hour | AI articles per month |
| --- | --- | --- | --- |
| Trial | no (403) | 0 | 1 |
| Solo | no (403) | 0 | 8 |
| Pro | yes | 30 | 60 |
| Agency | yes | 200 | 200 |

Sources: `PLAN_API_LIMITS` in `backend/sites_mgmt/api_v1.py`, `Subscription.get_limits()` in `backend/sites_mgmt/models.py`.

- Each tool call sends one request to the Gridar API and counts against the hourly limit. Past the limit the API answers 429.
- Three tools debit the monthly article quota, or one credit once the quota is used up: `gridar_generate_article`, `gridar_generate_sister_article`, `gridar_generate_landing`.
- An API error comes back as a tool error: `Gridar API error (HTTP <status>): <message>`, followed by the JSON body.

## Tools (69)

The **Effect** column flags what a call changes:

- **destructive**: deletes or disables something; the client should confirm first.
- **publishes**: puts content live or makes a page public.
- **quota**: debits one article from the monthly quota, or one credit.
- writes: changes data in Gridar without putting anything live.
- none: read only.

### Account and sites

| Tool | What it does | Effect |
| --- | --- | --- |
| `gridar_get_me` | Your plan, hourly API limit, monthly article quota and usage | none |
| `gridar_list_sites` | Your sites: id, domain, hosting mode, default language | none |
| `gridar_get_site` | Full config of one site: integrations, default language, knowledge base, competitors, GSC connection, autopilot, author E-E-A-T fields | none |
| `gridar_update_site` | Changes editable site fields: name, description, knowledge base, competitors, default language, author bio and credentials, public blog domain | writes |

### Articles

| Tool | What it does | Effect |
| --- | --- | --- |
| `gridar_list_articles` | Articles of a site, filtered by status, language and count (default 25, max 100) | none |
| `gridar_get_article` | Full content (HTML and metadata) of one article, by `site_id` and `slug` | none |
| `gridar_generate_article` | Generates an SEO article from a `topic` or a `title`. Saved as draft on hosted sites, published live on WordPress, Shopify and Webflow | **quota**, **publishes** on CMS sites |
| `gridar_generate_sister_article` | Translates and adapts an article into another language in the same translation group, so hreflang links up. Created as draft. Hosted sites only | **quota** |
| `gridar_create_article` | Creates a hand-written article on a hosted site. No AI, no quota | writes; **publishes** with `status: published` |
| `gridar_update_article` | Changes title, content, excerpt, status, cover image or author of an article, on every site mode (hosted, external, WordPress, Shopify, Webflow) | writes; **publishes** with `status: published` |
| `gridar_delete_article` | Deletes an article permanently, on every site mode. WordPress, Shopify and Webflow deletes skip the trash | **destructive** |

### Audit and content

| Tool | What it does | Effect |
| --- | --- | --- |
| `gridar_audit_article` | Audits raw content: 0 to 100 score and fixes on length, keyword density, headings, links, meta | none |
| `gridar_get_brief` | Content brief for a keyword: search intent, outline, entities, FAQ candidates, E-E-A-T signals | none |
| `gridar_bulk_audit` | Audits every published article of a site in parallel (Gemini): aggregated scores and top issues | none |
| `gridar_check_readability` | Readability scores of a text (Flesch-Kincaid, ARI) | none |
| `gridar_check_plagiarism` | AI-content and plagiarism check of a text through Originality.ai | none |
| `gridar_check_hreflang` | Checks translation group consistency of a site's published articles. `site_id` required | none |
| `gridar_detect_cannibalization` | Pairs of articles that target the same intent or keywords, across languages and statuses | none |
| `gridar_suggest_internal_links` | Internal links to insert in the `content` you pass, picked from the site's published articles | none |
| `gridar_ai_overview_readiness` | 0 to 100 score of how ready an article is for AI answers, from 5 weighted checks (FAQ, H2/H3 structure, E-E-A-T, concrete data, extractable paragraphs), with suggestions | none |

### Site health

| Tool | What it does | Effect |
| --- | --- | --- |
| `gridar_site_seo_score` | Composite 0 to 100 site score from 9 weighted checks (indexability, author bio, business model, GSC, approved pillar and spokes cluster, hreflang, Core Web Vitals, FAQ schema, transactional intents stuck on blog posts), with `action_items` | none |
| `gridar_check_renderability` | Fetches a URL and says whether the HTML is server-rendered or a JavaScript shell Googlebot must render (100 visible words or fewer flags a suspect SPA) | none |
| `gridar_page_speed` | PageSpeed Insights on a URL, mobile or desktop: Core Web Vitals and suggestions | none |
| `gridar_find_broken_links` | Outgoing links in the site's articles that answer 4xx, 5xx or time out | none |
| `gridar_get_content_decay` | Articles whose GSC impressions or clicks dropped over N days (7 to 90, default 30), with a refresh, expand or redirect suggestion | none |

### Keywords, SERP and competitors

| Tool | What it does | Effect |
| --- | --- | --- |
| `gridar_list_keywords` | Tracked keywords and their latest recorded position | none |
| `gridar_track_keyword` | Adds a keyword to track, or reactivates a removed one. A daily cron records its position | writes |
| `gridar_untrack_keyword` | Stops tracking a keyword (soft delete). Position history is kept; `gridar_track_keyword` brings it back | writes |
| `gridar_snapshot_keywords` | Records the position of every tracked keyword of a site now | writes |
| `gridar_suggest_keywords` | Keywords to track, suggested by Claude from the site memory and homepage | none |
| `gridar_keyword_research` | Expands a seed keyword into related queries (Serper related searches and People Also Ask, Gemini variants), grouped into families, with the status of each provider. No volume, no difficulty | none |
| `gridar_people_also_ask` | Google "People also ask" questions for a keyword | none |
| `gridar_classify_intent` | Search intent of a keyword (transactional, commercial, informational, navigational, local) and a confidence score | none |
| `gridar_analyze_competitors` | Google top 10 for a keyword: average word count, common headings, entity coverage, gaps | none |
| `gridar_serp_analyze` | Per-URL metrics of the top 10 (word count, H1/H2/H3, FAQ, video) and averages, to size a competing article | none |
| `gridar_suggest_competitors` | Likely SEO competitors, from the homepage and tracked keywords | none |
| `gridar_link_opportunities` | Candidate sites for backlink outreach on a keyword: domain, URL, title, snippet, source query | none |

### Strategy, landings and clusters

| Tool | What it does | Effect |
| --- | --- | --- |
| `gridar_propose_keyword_strategy` | Proposes a structure for a keyword: single landing, pillar and cluster, comparison table, local landing or blog post. Re-running refreshes a draft, never an approved strategy | writes |
| `gridar_approve_strategy` | Approves a strategy: landings are AI-generated as drafts, articles wait for `gridar_generate_article` | writes |
| `gridar_create_landing` | Creates a hand-written structured landing (hero, value props, social proof, FAQ, bottom CTA). No AI, no quota. Hosted sites only | writes; **publishes** with `status: published` |
| `gridar_generate_landing` | AI-generates a full landing from a keyword, saved as draft on the hosted site | **quota** |
| `gridar_link_pages` | Adds a contextual link from one page to another on the same site: converts the anchor text in place, or appends a "Voir aussi" line | writes (edits the source page) |
| `gridar_cluster_map` | Topic clusters of the site: pillar, spokes, covered pages, missing pages. No LLM call | none |
| `gridar_build_cluster` | Build prompts for a pillar and its spokes, internal links included. Adds missing keywords to tracking. No LLM call, no quota: the agent writes the copy | writes |

### Strategic opportunities

| Tool | What it does | Effect |
| --- | --- | --- |
| `gridar_refresh_strategic_opportunities` | Runs the opportunity engine on tracked keywords with transactional, commercial or local intent that have no landing yet. One Claude call per keyword, `max_keywords` default 8, cap 20 | writes |
| `gridar_list_strategic_opportunities` | Cached opportunities: page type, title, URL path, hook, capture mechanism, conversion path, angle, priority, traffic estimate (see [Known limits](#known-limits)) | none |
| `gridar_action_strategic_opportunity` | `approve` generates the landing as draft and marks the opportunity done; `dismiss` hides it; `restore` brings it back | writes |
| `gridar_export_page_prompt` | Ready-to-paste prompt for your own AI tool (ChatGPT, Lovable, v0, Bolt...): `landing_id` to integrate an existing landing verbatim, `opportunity_id` to write a page from the brief. Templating only, no quota | none |

### Delivery through an agent

For a custom-built site Gridar cannot publish to. Set the site's delivery mode to agent in the dashboard.

| Tool | What it does | Effect |
| --- | --- | --- |
| `gridar_pull_build_queue` | Queue of pages to build in your own repo: landing briefs, generated articles to integrate verbatim, article briefs. No LLM call, no quota | none |
| `gridar_mark_page_built` | Reports a queued page as live, with its URL. Gridar drops it from the queue and ties it to rank tracking and proof of results | writes |

### Google Search Console and indexing

| Tool | What it does | Effect |
| --- | --- | --- |
| `gridar_gsc_queries` | GSC queries (impressions, clicks, position) for one article over N days (default 28, limit 50). GSC connection required | none |
| `gridar_index_coverage` | Which expected pages Google has indexed: a `site:` query on any site, plus the GSC URL Inspection status and reason when GSC is connected (`max_inspect` default 25) | none |
| `gridar_submit_sitemap` | Re-submits the sitemap to Google Search Console. Needs GSC with write access. Does not force indexing | writes (sent to Google) |
| `gridar_indexnow_setup` | The site's IndexNow key and the key file to host at the domain root. Creates the key on first call | writes |
| `gridar_indexnow_submit` | Submits URLs, or the sitemap URLs, to IndexNow: Bing, Yandex, Seznam, Naver. Not Google | writes (sent to IndexNow) |

### AI visibility

| Tool | What it does | Effect |
| --- | --- | --- |
| `gridar_ai_visibility_summary` | Returns `available: false`, counts at 0 and a `note`: no AI engine is queried from the dashboard yet | none |
| `gridar_run_ai_visibility` | Answers HTTP 501 with code `ai_visibility_unavailable` and writes nothing | none |

### Autopilot

| Tool | What it does | Effect |
| --- | --- | --- |
| `gridar_get_autopilot` | Autopilot config and state: enabled, weekly count, last run, next run, last error | none |
| `gridar_set_autopilot` | Turns on or configures autopilot: `enabled`, `weekly_count` (1 to 7), `auto_publish` | writes; **publishes** from then on with `auto_publish: true` |
| `gridar_run_autopilot_now` | Runs one autopilot cycle now, outside the schedule | writes; **publishes** when `auto_publish` is on |

### Site memory

| Tool | What it does | Effect |
| --- | --- | --- |
| `gridar_list_memories` | The site's memory chunks: articles, knowledge base, manual notes, decisions. Paginated | none |
| `gridar_add_memory` | Adds a note. Kinds `manual` and `decision` weigh more in future generations | writes |
| `gridar_delete_memory` | Deletes one memory chunk | **destructive** |
| `gridar_rebuild_memory` | Re-chunks and re-embeds the knowledge base and published hosted articles (Voyage AI). Existing chunks are not wiped | writes |

### Proof of results and reporting

| Tool | What it does | Effect |
| --- | --- | --- |
| `gridar_proof_summary` | Impressions and clicks gained according to GSC, and the 5 articles that gained the most | none |
| `gridar_proof_attribution` | Per-article snapshots at day 30, 60 and 90 against the baseline; filter with `post_id` | none |
| `gridar_enable_proof_share` | Turns on the public read-only proof page and returns its URL. `rotate: true` issues a new link and kills the old one | **publishes** |
| `gridar_revoke_proof_share` | Turns off the public proof page: the URL answers 404 at once. Data is kept | **destructive** |
| `gridar_weekly_digest` | The last 7 days of a site: traffic, rankings, content decay | none |

## Conversation examples

- "Audit site 12 and give me the 3 fixes to make first." Claude calls `gridar_site_seo_score`, then reads its `action_items`.
- "Pull the pages to build for site 12 and create them in this repo." Claude Code calls `gridar_pull_build_queue`, writes each page, deploys, then calls `gridar_mark_page_built` with each live URL.

Tools take a numeric `site_id`: the site must already exist in your Gridar account. `gridar_list_sites` returns the ids.

## Known limits

- **AI visibility is not wired.** No AI engine is queried from the dashboard. `gridar_run_ai_visibility` answers 501 (`ai_visibility_unavailable`) and stores nothing; `gridar_ai_visibility_summary` returns `available: false` with zero counts, and excludes results from the former simulation. For a one-off check, the tool description points to the free checker at <https://www.gridar.app/tools/ai-visibility-checker>.
- **No search volume, no keyword difficulty.** `gridar_keyword_research` returns neither, and `estimated_intent` is guessed from the words of the keyword. Read its `sources` field: a short list can mean a provider failed or returned nothing.
- **Opportunity estimates often read 0.** `monthly_volume` in strategic opportunities comes from a best-effort read of the Serper search response. When Serper returns no volume field, `monthly_volume`, `estimated_visits` and the lead ranges are 0 and `qualitative_traffic` is `inconnu`.
- **Rank depth.** The daily cron keeps the largest organic result set from up to three Serper calls; `gridar_snapshot_keywords` makes a single call. In both cases a page ranked below the results Serper returns is recorded as not ranked.
- **`gridar_generate_article`** defaults to French when `language` is omitted (the backend reads `language` or falls back to `fr`). It answers 422 until the site has a business model and an author bio, 409 (`delivery_blocked`) when the site has no delivery path, and 402 when quota and credits are used up.
- **`gridar_update_article`** identifies the article by `slug`; there is no field to change the slug.
- **`gridar_check_hreflang`** needs `site_id`. The backend ignores the `html` argument.
- **`gridar_suggest_internal_links`** needs `content`. The backend does not read `article_slug` or `keyword`.
- **`gridar_check_plagiarism`** needs at least 50 characters, and answers 503 when Originality.ai is not configured on Gridar's side.
- **Landings** (`gridar_create_landing`, `gridar_generate_landing`) and `gridar_generate_sister_article` work on hosted sites only.
- **IndexNow** does not reach Google, and re-submitting a sitemap does not force Google to index anything.
- **Tokens.** A token grants every tool on every site of the account, deletions included. There is no read-only token. Each OAuth authorization creates a new token; old ones stay active until you revoke them at <https://www.gridar.app/account/api-keys>.
- **OAuth state lives in memory.** Codes expire after 5 minutes, and a server restart during the login invalidates the pending login: start the connection again.

## Development

```bash
cd mcp-server
npm install
npm run build
BLOG_DASHBOARD_TOKEN=btb_xxx node dist/index.js   # stdio (npm start)
PORT=8080 node dist/http.js                       # HTTP (npm run start:http)
```

Debug with the [MCP Inspector](https://github.com/modelcontextprotocol/inspector):

```bash
BLOG_DASHBOARD_TOKEN=btb_xxx npx @modelcontextprotocol/inspector node dist/index.js
```

Tool definitions (name, description, input schema) live in `src/index.ts`, the API client in `src/api.ts`, the HTTP server and OAuth flow in `src/http.ts`.

## Links

- Integration docs (French): <https://www.gridar.app/docs/integrations>
- Connector page: <https://www.gridar.app/mcp>
- Official MCP registry entry `app.gridar/gridar`: <https://registry.modelcontextprotocol.io/v0.1/servers?search=app.gridar/gridar>
- Source: <https://github.com/TokDar2410621/blog-dashboard/tree/main/mcp-server>

## License

MIT
