# n8n-nodes-gridar

n8n node for [Gridar](https://www.gridar.app).

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

`n8n-nodes-gridar` is **not published on npm yet** (the registry answers 404, checked on 2026-10-21), so **Settings -> Community Nodes -> Install** cannot find it.

Until it is published:

- **Any n8n (self-hosted or Cloud)**: call the Gridar REST API with the built-in **HTTP Request** node and the header `Authorization: Bearer btb_xxx`. Ready-made workflows: <https://www.gridar.app/docs/integrations>.
- **Self-hosted n8n, from source**: see [Development](#development).

## Setup

The API, and so this node, needs a Gridar **Pro** or **Agency** plan (30 and 200 requests per hour). Essai and Solo tokens get a 403.

1. In Gridar, go to **Account -> API keys** and generate a token (`btb_xxx`).
2. In n8n, create new credentials of type "Gridar API" and paste the token.
3. Drop the "Gridar" node into a workflow.

## Example workflows

### Generate an article every Monday morning

```
Schedule (Mon 8am)
  -> Gridar (Article: Generate)
       site_id: 12
       topic: "Tendances SEO Quebec {{ $now.format('MMMM yyyy') }}"
       type: news
       length: medium
  -> Slack (notify team with returned URL)
```

### Audit every new article submitted via webhook

```
Webhook (POST /audit-incoming)
  -> Gridar (Audit: Run)
       title: {{ $json.title }}
       content: {{ $json.content }}
  -> IF (score < 70)
       -> Email (alert reviewer)
```

### Daily keyword tracking

```
Schedule (every day 6am)
  -> Gridar (Keyword: Snapshot)
       site_id: 12
  -> Gridar (Keyword: List)
       site_id: 12
  -> Google Sheets (append rankings)
```

## Quotas

This node uses your existing Gridar plan. `Article -> Generate` consumes 1 article from your monthly quota (or 1 credit). Read operations are free. See [Plans & Credits](https://www.gridar.app/docs/plans-credits).

## Development

`npm run build` runs `tsc && gulp build:icons`, and the repo has no gulpfile yet, so the gulp step fails. Compile with `npx tsc` until it is added.

```bash
cd n8n-node
npm install
npx tsc
# Link into local n8n
npm link
cd ~/.n8n/custom
npm link n8n-nodes-gridar
# Then restart n8n
```

## License

MIT
