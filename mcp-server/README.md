# @gridar/mcp-server

[Model Context Protocol](https://modelcontextprotocol.io) server for [Gridar](https://gridar.app).

Drive most of the Gridar dashboard from Claude Code, Claude Desktop, Cursor, Codex, Continue, or any other MCP-compatible client. Generate articles, edit them, track keywords, audit SEO, configure autopilot, and surface GSC proof of value.

## What it does

Once installed, your AI client gets **43 tools** covering the dashboard surface.

### Discovery & status

| Tool | Purpose |
|---|---|
| `gridar_get_me` | Plan + monthly quota + remaining usage |
| `gridar_list_sites` | List your sites (id, domain, mode, default language) |
| `gridar_get_site` | Full config of one site (KB, competitors, GSC, autopilot, EEAT) |
| `gridar_update_site` | Patch editable site fields (KB, competitors, default_language, etc.) |

### Articles

| Tool | Purpose |
|---|---|
| `gridar_list_articles` | Browse a site's articles (filter status / language / limit) |
| `gridar_get_article` | Read full content of one article |
| `gridar_generate_article` | AI-generated article (consumes 1 quota or credit) |
| `gridar_create_article` | Manual article (no AI, no quota) on a hosted site |
| `gridar_update_article` | Patch title / content / status / cover / slug |
| `gridar_delete_article` | DESTRUCTIVE: delete a hosted article |

### Briefing & audit

| Tool | Purpose |
|---|---|
| `gridar_get_brief` | Content brief (intent, outline, FAQ, entities, EEAT) |
| `gridar_audit_article` | Score raw content + actionable SEO fixes |
| `gridar_bulk_audit` | Run audit across ALL published articles in parallel |
| `gridar_check_readability` | Flesch-Kincaid / ARI scores |
| `gridar_check_plagiarism` | Originality / plagiarism check |
| `gridar_check_hreflang` | Validate hreflang consistency |
| `gridar_detect_cannibalization` | Find articles competing for the same intent |
| `gridar_suggest_internal_links` | AI suggestions for internal linking |

### Keywords

| Tool | Purpose |
|---|---|
| `gridar_list_keywords` | Tracked keywords + latest position |
| `gridar_track_keyword` | Add a new keyword to track |
| `gridar_untrack_keyword` | Soft-delete a tracked keyword |
| `gridar_suggest_keywords` | AI suggestions anchored on RAG + homepage |
| `gridar_snapshot_keywords` | Trigger a fresh SERP snapshot now |
| `gridar_keyword_research` | Expand a seed keyword (volume, difficulty) |
| `gridar_people_also_ask` | Harvest PAA questions for FAQ schema |

### Competitors & SEO

| Tool | Purpose |
|---|---|
| `gridar_suggest_competitors` | Auto-detect SEO competitors |
| `gridar_analyze_competitors` | Analyze SERP top 10 for a keyword |
| `gridar_get_content_decay` | Find articles losing impressions over N days |
| `gridar_find_broken_links` | Crawl + check outgoing links |
| `gridar_page_speed` | Run PageSpeed Insights |
| `gridar_gsc_queries` | Top GSC queries for a site |

### Autopilot

| Tool | Purpose |
|---|---|
| `gridar_get_autopilot` | Read autopilot config + status |
| `gridar_set_autopilot` | Enable / configure (weekly_count, auto_publish) |
| `gridar_run_autopilot_now` | Manually trigger a generation cycle |

### RAG memory (per-site brain)

| Tool | Purpose |
|---|---|
| `gridar_list_memories` | List RAG chunks (articles, KB, manual, decision) |
| `gridar_add_memory` | Add a manual note (carries instruction weight) |
| `gridar_delete_memory` | DESTRUCTIVE: delete a memory chunk |
| `gridar_rebuild_memory` | Re-chunk + re-embed everything (Voyage AI cost) |

### Proof of value (GSC attribution)

| Tool | Purpose |
|---|---|
| `gridar_proof_summary` | Total impressions / clicks gained + top 5 winners |
| `gridar_proof_attribution` | Per-article J+30 / J+60 / J+90 snapshots vs baseline |
| `gridar_enable_proof_share` | Enable public share URL (`/proof/<token>`) |
| `gridar_revoke_proof_share` | Kill the public URL (404 immediately) |

### Reporting

| Tool | Purpose |
|---|---|
| `gridar_weekly_digest` | Weekly traffic + ranking + decay digest |

---

## Conversation patterns

> **You:** Generate a guide article on "meilleur CRM PME Quebec" for site 12, in French, then audit it and publish if it scores above 80.
>
> **Claude:** *(calls `gridar_get_brief` -> `gridar_generate_article` -> `gridar_audit_article` -> `gridar_update_article` with status='published')*
> Done. Score 87/100. Published as /blog/meilleur-crm-pme-quebec.

> **You:** Show me the proof page for site 12 and copy its public URL to share with my client.
>
> **Claude:** *(calls `gridar_proof_summary` then `gridar_enable_proof_share`)*
> +3.2k impressions gained, +118 clicks. Public URL: https://gridar.app/proof/xxxxxxxxxxxxxxxx

> **You:** Add a manual note to site 12's brain so future generation always mentions our 2026 Quebec compliance certification.
>
> **Claude:** *(calls `gridar_add_memory` with kind='decision')*
> Saved.

---

## Installation

### 1. Get an API token

Sign in at https://gridar.app and visit **Account -> API keys** to create a personal token. Tokens look like `btb_xxxxxxxx` and are shown once. **Requires Pro or Agency plan** (`free` and `solo` are blocked).

### 2. Wire it into your MCP client

#### Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "gridar": {
      "command": "npx",
      "args": ["-y", "@gridar/mcp-server"],
      "env": {
        "BLOG_DASHBOARD_TOKEN": "btb_your_token_here"
      }
    }
  }
}
```

Restart Claude Desktop.

#### Claude Code

```bash
claude mcp add gridar --env BLOG_DASHBOARD_TOKEN=btb_xxx -- npx -y @gridar/mcp-server
```

#### Codex CLI

Add to `~/.codex/config.toml`:

```toml
[mcp_servers.gridar]
command = "npx"
args = ["-y", "@gridar/mcp-server"]
env = { BLOG_DASHBOARD_TOKEN = "btb_your_token_here" }
```

#### Cursor

`~/.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "gridar": {
      "command": "npx",
      "args": ["-y", "@gridar/mcp-server"],
      "env": { "BLOG_DASHBOARD_TOKEN": "btb_xxx" }
    }
  }
}
```

#### Any other client

Spawn with stdio transport:

```bash
BLOG_DASHBOARD_TOKEN=btb_xxx npx -y @gridar/mcp-server
```

---

## Configuration

| Env var | Default | Description |
|---|---|---|
| `BLOG_DASHBOARD_TOKEN` | required | Bearer ApiToken (`btb_...`) |
| `BLOG_DASHBOARD_API_BASE` | `https://api.gridar.app/api/v1` | Override for self-hosted backends |

## Costs & quotas

- `generate_article` consumes 1 article from monthly quota (or 1 credit)
- `bulk_audit` and `rebuild_memory` are heavier (Gemini / Voyage tokens billed to your plan)
- All other tools are free under the plan-level rate limit (Pro: 30/h, Agency: 200/h)

## Safety notes

**Destructive tools** (clearly marked in their descriptions):

- `gridar_delete_article` permanently removes a hosted article + cascades attribution
- `gridar_delete_memory` removes a RAG chunk
- `gridar_revoke_proof_share` kills the public proof URL immediately
- `gridar_untrack_keyword` is a soft delete (sets is_active=False)

When a user asks for one of these in chat, the MCP-compatible client will typically ask for confirmation. If you want stricter gating, restrict your API token's scope or use a separate token for read-only sessions.

## Development

```bash
cd mcp-server
npm install
npm run build
BLOG_DASHBOARD_TOKEN=btb_xxx node dist/index.js
```

Debug with the [MCP Inspector](https://github.com/modelcontextprotocol/inspector):

```bash
BLOG_DASHBOARD_TOKEN=btb_xxx npx @modelcontextprotocol/inspector node dist/index.js
```

## License

MIT
