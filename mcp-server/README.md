# @gridar/mcp-server

[Model Context Protocol](https://modelcontextprotocol.io) server for [Gridar](https://blog-dashboard-ebon.vercel.app).

Generate, audit and publish SEO articles directly from Claude Desktop, Claude Code, Cursor, Continue or any other MCP-compatible client.

## What it does

Once installed, your AI client gets 10 new tools:

| Tool | Purpose |
|---|---|
| `blog_dashboard_get_me` | Show plan + remaining monthly quota |
| `blog_dashboard_list_sites` | List your connected sites |
| `blog_dashboard_list_articles` | Browse existing articles on a site |
| `blog_dashboard_get_article` | Read full content of one article |
| `blog_dashboard_generate_article` | Generate a new SEO article (consumes 1 quota or credit) |
| `blog_dashboard_audit_article` | Score raw content + get SEO suggestions |
| `blog_dashboard_get_brief` | Build a content brief (intent, outline, FAQ, entities) |
| `blog_dashboard_list_keywords` | List tracked keywords + latest position |
| `blog_dashboard_snapshot_keywords` | Trigger a fresh ranking snapshot |
| `blog_dashboard_weekly_digest` | Get the weekly traffic + ranking digest |

Typical conversation:

> **You:** Generate a guide article on "meilleur CRM PME Quebec" for site 12, in French, with E-E-A-T signals.
>
> **Claude:** *(calls `blog_dashboard_get_brief` then `blog_dashboard_generate_article`)*
> Done. The article was published as a draft. Score: 87/100. View it at...

## Installation

### 1. Get an API token

Sign in at https://blog-dashboard-ebon.vercel.app and visit **Account -> API keys** to create a personal token. Tokens look like `btb_xxxxxxxx` and are only shown once.

### 2. Install the server

The fastest path is `npx`, no install needed:

```bash
npx -y @gridar/mcp-server
```

Or globally:

```bash
npm install -g @gridar/mcp-server
```

### 3. Wire it into your MCP client

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

Restart Claude Desktop. The 10 tools should now appear.

#### Claude Code

```bash
claude mcp add gridar \
  --env BLOG_DASHBOARD_TOKEN=btb_your_token_here \
  -- npx -y @gridar/mcp-server
```

#### Cursor

Add to `~/.cursor/mcp.json`:

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

#### Other clients

Any MCP client supporting stdio transport works. Spawn:

```
BLOG_DASHBOARD_TOKEN=btb_xxx npx -y @gridar/mcp-server
```

## Configuration

| Env var | Default | Description |
|---|---|---|
| `BLOG_DASHBOARD_TOKEN` | required | Your API token (`btb_...`) |
| `BLOG_DASHBOARD_API_BASE` | `https://api.gridar.app/api/v1` | Override for self-hosted backends |

## Quotas & costs

Tools use your existing Gridar plan limits:

- `generate_article` consumes 1 article from your monthly quota (or 1 credit if monthly quota is exhausted)
- `audit_article`, `get_brief` are free
- All other tools are read-only and free

See [Plans & Credits](https://blog-dashboard-ebon.vercel.app/docs/plans-credits) for limits per plan.

## Development

```bash
cd mcp-server
npm install
npm run build
BLOG_DASHBOARD_TOKEN=btb_xxx node dist/index.js
```

The server speaks stdio. To debug, pipe MCP JSON-RPC messages manually or use the [MCP Inspector](https://github.com/modelcontextprotocol/inspector):

```bash
npx @modelcontextprotocol/inspector node dist/index.js
```

## License

MIT
