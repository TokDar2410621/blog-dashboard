---
title: MCP et content marketing — Claude qui écrit tes articles depuis ton chat
slug: mcp-claude-content-marketing
date: 2026-04-28
author: Darius Tokam
excerpt: Le Model Context Protocol d'Anthropic est en train de changer la façon dont les marketers utilisent l'IA. Tu n'as plus à copier-coller entre 5 outils — tu parles à Claude, et Claude exécute.
tags: [mcp, claude, ia]
---

Si tu utilises ChatGPT ou Claude pour ton content marketing en 2026, tu connais le rituel : tu demandes un article, Claude le rédige, tu copies dans Notion, tu copies dans WordPress, tu copies dans Buffer pour la promo. Trois copy-pastes minimum. Souvent six.

Le **Model Context Protocol (MCP)** d'Anthropic, lancé fin 2024 et désormais supporté par Claude Desktop, Claude Code, Cursor et Continue, élimine cette friction.

## Ce que MCP fait vraiment

MCP est un standard ouvert qui permet à un LLM d'**appeler des outils externes** depuis sa conversation. Tu ouvres Claude Desktop, tu écris :

> Génère un article guide sur "meilleur CRM PME québécoises" pour mon site Gridar (id 12), 1500 mots, en français, et publie-le directement en brouillon WordPress.

Claude :
1. Reconnaît qu'il a accès au tool `gridar_get_brief`
2. L'appelle avec ton mot-clé → reçoit l'outline + l'intent + les FAQ
3. Appelle `gridar_generate_article` avec le brief → l'article est généré, audité SEO, et publié sur ton WP en brouillon
4. Te répond : "Fait. Score SEO : 87/100. Brouillon créé : monsite.ca/?p=4321"

**Zéro copy-paste.** Tu n'as même pas ouvert ton dashboard.

## La différence avec un plugin ChatGPT classique

Les plugins GPT (et les actions ChatGPT) sont liés à **leur** marketplace, fermés à OpenAI, et il faut payer Plus (20 $/mois) pour y accéder.

MCP est :
- **Ouvert** : tout LLM peut implémenter le protocole (Anthropic, Open Source, etc.)
- **Local** : le serveur MCP tourne sur ta machine via stdio, pas dans le cloud
- **Multi-client** : un seul serveur fonctionne dans Claude Desktop, Claude Code, Cursor, Continue, Zed simultanément

## Installer le serveur MCP Gridar

Pré-requis : Claude Desktop (Mac/Windows/Linux), un compte Gridar Pro+ avec un token API.

### Config

Édite `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) ou `%APPDATA%\Claude\claude_desktop_config.json` (Windows) :

```json
{
  "mcpServers": {
    "gridar": {
      "command": "npx",
      "args": ["-y", "@gridar/mcp-server"],
      "env": {
        "BLOG_DASHBOARD_TOKEN": "btb_ton_token"
      }
    }
  }
}
```

Restart Claude Desktop. Demande : "*Liste mes sites Gridar*". Tu vois Claude appeler le tool `gridar_list_sites`. Aucun setup réseau, aucun port à exposer.

## Les 10 tools Gridar disponibles

| Tool | Usage |
|---|---|
| `gridar_get_me` | Plan + quota restant |
| `gridar_list_sites` | Tes sites connectés |
| `gridar_list_articles` | Articles d'un site |
| `gridar_get_article` | Contenu d'un article |
| `gridar_generate_article` | **Génère un article** |
| `gridar_audit_article` | Score SEO + suggestions |
| `gridar_get_brief` | Brief de contenu (intent, outline, FAQ) |
| `gridar_list_keywords` | Mots-clés trackés |
| `gridar_snapshot_keywords` | Snapshot positions |
| `gridar_weekly_digest` | Digest hebdo |

## Le pattern qui change tout : la conversation comme dashboard

Au lieu d'apprendre l'interface d'un nouvel outil SaaS, tu **parles à ton outil**. Ce changement est gros pour les marketers non-techniques :

- "Combien il me reste d'articles ce mois-ci ?" → Claude appelle `gridar_get_me`
- "Audite mon dernier article sur les CRM" → `gridar_list_articles` + `gridar_audit_article`
- "Mon mot-clé 'crm pme québec' a baissé ?" → `gridar_list_keywords` + comparaison

Tu n'as plus à savoir où trouver l'info. Claude la trouve.

## Le futur immédiat : MCP partout

D'ici fin 2026, on s'attend à ce que tous les SaaS sérieux exposent un serveur MCP. C'est le nouveau standard d'interopérabilité, qui remplace la complexité de "intégrations Zapier" par "outils dans Claude".

Gridar a été parmi les premiers SaaS SEO à publier son MCP server (mars 2026). [Code source](https://github.com/TokDar2410621/blog-dashboard/tree/main/mcp-server), licence MIT.

## Lectures liées

- [API REST publique](/api-docs)
- [5 workflows n8n pour le SEO](/blog/n8n-seo-workflows)
- [Automatiser ton blog WordPress avec l'IA](/blog/automatiser-blog-wordpress-ia)
