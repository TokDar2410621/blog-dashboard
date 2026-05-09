# Intégrations & automatisations

Tu peux générer, auditer et publier des articles **sans ouvrir le dashboard** depuis :

- **Claude Desktop / Claude Code / Cursor** via notre serveur MCP (Model Context Protocol)
- **n8n** via notre node communautaire officiel
- **Zapier / Make / GitHub Actions / scripts maison** via l'[API REST](api.md)

Les trois utilisent le même token `btb_xxx` (Account → API keys) et consomment les mêmes quotas que le dashboard.

## Comparatif rapide

| | MCP server | n8n node | API REST |
|---|---|---|---|
| Idéal pour | Conversation IA (Claude, Cursor) | Workflows visuels récurrents | Code custom, CI/CD |
| Plan requis | Pro+ | Pro+ | Pro+ |
| Setup | 1 entrée JSON | 2 clics | curl/fetch |
| Génération auto récurrente | Manuelle (chat) | Oui (Schedule trigger) | Oui (cron côté serveur) |
| Cas type | "Génère un article sur X" | "Tous les lundis 8h, publie une news" | "À chaque commit, audit le markdown" |

## 1. MCP server (Claude Desktop, Cursor, etc.)

[Model Context Protocol](https://modelcontextprotocol.io) est le standard ouvert d'Anthropic pour donner des outils à un LLM. Notre serveur MCP expose 10 tools :

| Tool | Usage |
|---|---|
| `blog_dashboard_get_me` | Plan + quota mensuel restant |
| `blog_dashboard_list_sites` | Tes sites connectés |
| `blog_dashboard_list_articles` | Articles d'un site |
| `blog_dashboard_get_article` | Contenu d'un article |
| `blog_dashboard_generate_article` | **Génère un article (1 quota)** |
| `blog_dashboard_audit_article` | Score SEO + suggestions |
| `blog_dashboard_get_brief` | Brief de contenu (intent, plan, FAQ) |
| `blog_dashboard_list_keywords` | Mots-clés trackés |
| `blog_dashboard_snapshot_keywords` | Snapshot des positions |
| `blog_dashboard_weekly_digest` | Digest hebdo |

### Installation Claude Desktop

Édite `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) ou `%APPDATA%\Claude\claude_desktop_config.json` (Windows) :

```json
{
  "mcpServers": {
    "gridar": {
      "command": "npx",
      "args": ["-y", "@gridar/mcp-server"],
      "env": {
        "BLOG_DASHBOARD_TOKEN": "btb_ton_token_ici"
      }
    }
  }
}
```

Redémarre Claude Desktop. Demande lui : "*liste mes sites Gridar*" → tu vois `blog_dashboard_list_sites` se déclencher.

### Installation Claude Code

```bash
claude mcp add gridar \
  --env BLOG_DASHBOARD_TOKEN=btb_ton_token \
  -- npx -y @gridar/mcp-server
```

### Installation Cursor

Édite `~/.cursor/mcp.json` avec la même config que Claude Desktop ci-dessus.

### Exemple de conversation

> **Toi :** Génère un article guide sur "meilleur CRM pour PME québécoises" pour le site 12, en français, 1500 mots, avec une FAQ.
>
> **Claude :** *(appelle `blog_dashboard_get_brief` pour récupérer un plan, puis `blog_dashboard_generate_article`)*
>
> Article généré ! Score SEO : 87/100. Quota restant ce mois : 47/60.

Code source + détails : [github.com/TokDar2410621/blog-dashboard/tree/main/mcp-server](https://github.com/TokDar2410621/blog-dashboard/tree/main/mcp-server).

## 2. n8n node communautaire

Pour les workflows visuels récurrents (planification, branchements, multi-étapes).

### Installation

n8n self-hosted → **Settings → Community Nodes → Install** :

```
n8n-nodes-gridar
```

Ou via npm :

```bash
cd ~/.n8n/custom
npm install n8n-nodes-gridar
```

Redémarre n8n.

> n8n Cloud ne supporte pas encore les nodes communautaires. Utilise le node HTTP Request avec notre [API REST](api.md) en attendant.

### Configuration credentials

1. Dans Gridar : **Account → API keys** → crée un token.
2. Dans n8n : **Credentials → New → Gridar API** → colle le token. Le bouton "Test" hit `/me/` pour valider.

### Ressources et opérations

| Resource | Operations |
|---|---|
| Article | Generate / Get / List |
| Audit | Run audit |
| Brief | Build brief |
| Keyword | List / Snapshot |
| Site | List / Weekly digest |

### Workflow type : article hebdomadaire automatique

```
Schedule (lundi 8h)
  ↓
Gridar (Article: Generate)
  site_id: 12
  topic: "Tendances SEO Québec {{ $now.format('MMMM yyyy') }}"
  type: news
  length: medium
  language: fr
  ↓
Slack (notifie l'équipe avec l'URL retournée)
```

### Workflow type : audit à la volée

```
Webhook (POST /audit-incoming)
  ↓
Gridar (Audit: Run)
  title: {{ $json.title }}
  content: {{ $json.content }}
  ↓
IF (score < 70)
  → Email "Article à revoir avant publication"
```

### Workflow type : tracking quotidien des positions

```
Schedule (tous les jours 6h)
  ↓
Gridar (Keyword: Snapshot)
  site_id: 12
  ↓
Gridar (Keyword: List)
  site_id: 12
  ↓
Google Sheets (append rows : keyword, position, date)
```

Code source + détails : [github.com/TokDar2410621/blog-dashboard/tree/main/n8n-node](https://github.com/TokDar2410621/blog-dashboard/tree/main/n8n-node).

## 3. API REST directe

Pour tout le reste (Zapier, Make, scripts Python/Node, GitHub Actions, etc.) : voir [API REST publique](api.md).

## Quotas

Les trois intégrations consomment ton plan normal. `generate` = 1 article du quota mensuel (ou 1 crédit si quota épuisé). Les autres endpoints sont gratuits côté quota mais limités par le rate-limit horaire :

| Plan | Rate limit | Articles/mois |
|---|---|---|
| Pro | 30 req/h | 60 |
| Agence | 200 req/h | 200 |

Free et Solo n'ont pas accès aux intégrations (créer un token nécessite Pro+).

## Sécurité

- Le token est privé, traite-le comme un mot de passe.
- Ne le commit jamais dans Git. Utilise les **secrets** de n8n / GitHub Actions / ton hébergeur.
- Tu peux révoquer un token à tout moment depuis **Account → API keys** sans affecter les autres.
- Génère un token **par intégration** (`n8n-prod`, `claude-desktop-laptop`, `gh-actions-blog`) pour pouvoir révoquer chirurgicalement.

## Support

- Bug ou question : [GitHub Issues](https://github.com/TokDar2410621/blog-dashboard/issues)
- Suggestions de tools/ops à ajouter : ouvre une issue, on est preneurs
