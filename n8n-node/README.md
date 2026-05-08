# n8n-nodes-blog-dashboard

n8n community node for [Blog Dashboard](https://blog-dashboard-ebon.vercel.app).

Trigger SEO article generation, run audits, build content briefs and track keywords from any n8n workflow.

## Features

One node, 5 resources:

| Resource | Operations |
|---|---|
| **Article** | Generate, Get, List |
| **Audit** | Run audit |
| **Brief** | Build brief |
| **Keyword** | List, Snapshot |
| **Site** | List, Weekly digest |

## Installation

### Self-hosted n8n

In n8n, go to **Settings -> Community Nodes -> Install** and enter:

```
n8n-nodes-blog-dashboard
```

### Docker / npm

```bash
cd ~/.n8n/custom
npm install n8n-nodes-blog-dashboard
```

Restart n8n. The "Blog Dashboard" node will appear in the node palette.

### n8n Cloud

Community nodes aren't supported on n8n Cloud yet. Use the [MCP server](../mcp-server/) or call our REST API directly via the HTTP Request node.

## Setup

1. In Blog Dashboard, go to **Account -> API keys** and generate a token (`btb_xxx`).
2. In n8n, create new credentials of type "Blog Dashboard API" and paste the token.
3. Drop the "Blog Dashboard" node into a workflow.

## Example workflows

### Generate an article every Monday morning

```
Schedule (Mon 8am)
  -> Blog Dashboard (Article: Generate)
       site_id: 12
       topic: "Tendances SEO Quebec {{ $now.format('MMMM yyyy') }}"
       type: news
       length: medium
  -> Slack (notify team with returned URL)
```

### Audit every new article submitted via webhook

```
Webhook (POST /audit-incoming)
  -> Blog Dashboard (Audit: Run)
       title: {{ $json.title }}
       content: {{ $json.content }}
  -> IF (score < 70)
       -> Email (alert reviewer)
```

### Daily keyword tracking

```
Schedule (every day 6am)
  -> Blog Dashboard (Keyword: Snapshot)
       site_id: 12
  -> Blog Dashboard (Keyword: List)
       site_id: 12
  -> Google Sheets (append rankings)
```

## Quotas

This node uses your existing Blog Dashboard plan. `Article -> Generate` consumes 1 article from your monthly quota (or 1 credit). Read operations are free. See [Plans & Credits](https://blog-dashboard-ebon.vercel.app/docs/plans-credits).

## Development

```bash
cd n8n-node
npm install
npm run build
# Link into local n8n
npm link
cd ~/.n8n/custom
npm link n8n-nodes-blog-dashboard
# Then restart n8n
```

## License

MIT
