---
title: 5 workflows n8n pour automatiser ton SEO
slug: n8n-seo-workflows
date: 2026-05-01
author: Darius Tokam
excerpt: n8n est l'outil d'automatisation visuel qui a tué Zapier sur le marché tech. Voici 5 workflows SEO qu'il te permet d'orchestrer en 10 minutes - sans écrire une ligne de code.
tags: [n8n, automatisation, seo]
---

Si tu as déjà essayé Zapier pour automatiser ton SEO, tu sais que ça coûte cher dès que tu dépasses 1000 tâches/mois (~30 $/mois minimum, et l'addition grimpe vite). n8n fait la même chose, en self-hosté, gratuit, sans limite de tâches.

Voici 5 workflows n8n que tu peux mettre en place ce weekend.

## 1. Article hebdomadaire automatique

**Trigger** : Schedule (chaque lundi 8h)

**Steps** :
1. Schedule trigger → `Cron: 0 8 * * 1`
2. **Gridar** node → Article : Generate
   - site_id : 12
   - topic : `"Tendances SEO Québec {{ $now.format('MMMM yyyy') }}"`
   - type : news
   - length : medium
   - language : fr
3. **Slack** → poste le lien dans #marketing

10 minutes de setup, un article par semaine pendant 1 an = 52 articles. À 4h par article manuel × 52 = 208h économisées. Le ROI est immédiat.

## 2. Audit à la volée via webhook

**Trigger** : Webhook (POST /audit-incoming)

**Use case** : un rédacteur soumet un article via Google Forms / Notion → un workflow vérifie son score SEO avant publication.

**Steps** :
1. Webhook reçoit `{title, content}`
2. **Gridar** node → Audit : Run
3. **IF** score < 70
   → Email au rédacteur : "Article à revoir, voici les suggestions : ..."
   → Sinon : approuve + publie

## 3. Snapshot quotidien des positions Google

**Trigger** : Schedule (tous les jours 6h)

**Steps** :
1. **Gridar** → Keyword : Snapshot (site_id 12)
2. **Gridar** → Keyword : List (récupère les positions fraîches)
3. **Google Sheets** → Append row par mot-clé : keyword, position, date

Tu te crées un dashboard SEO maison dans Google Sheets, avec graphiques d'évolution. Gratuit, mieux que n'importe quel outil à 200 $/mois pour le suivi.

## 4. Alerte chute de position

**Trigger** : Schedule (3x par jour)

**Steps** :
1. **Gridar** → Keyword : List
2. Comparer chaque position à la position d'hier (stockée en Google Sheets ou Airtable)
3. **IF** chute > 3 positions
   → **Slack** : "🚨 Le mot-clé `crm pme québec` est passé de la 4e à la 12e position en 24h"

C'est exactement ce que vendent des outils SEO à 100-200 $/mois. Tu le construis en 30 min.

## 5. Republication automatique des articles qui périment

**Trigger** : Schedule (1x par semaine, dimanche soir)

**Steps** :
1. **Gridar** → Site : Weekly digest → récupère la liste des articles en content decay
2. Pour chaque article qui a perdu > 30 % de trafic :
   → **Gridar** → Article : Generate avec `mode: refresh, slug: <l'article>`
   → publie la version refreshée
3. **Slack** : "5 articles refreshés cette semaine"

Le content decay est le voleur de trafic numéro 1 des blogs de plus de 2 ans. L'automatiser tue un problème majeur.

## Installation du node n8n Gridar

```bash
# Dans ton n8n self-hosted
n8n → Settings → Community Nodes → Install
n8n-nodes-gridar
```

Restart n8n, puis dans tes credentials :
- Type : **Gridar API**
- Token : ton `btb_xxx` créé depuis [/account/api-keys](/account/api-keys)

C'est tout. Les 5 workflows ci-dessus prennent ~30 minutes à câbler ensemble.

## Pourquoi n8n vs Zapier pour le SEO

| Critère | n8n self-hosted | Zapier |
|---|---|---|
| Coût mensuel | 0 $ (VPS 5 $/mois) | 30-300 $/mois |
| Tâches illimitées | ✅ | ❌ (paliers) |
| Workflows complexes (boucles, branchements) | ✅ | ⚠️ limité |
| Node Gridar communautaire | ✅ | ❌ (HTTP only) |
| Stockage des credentials chez toi | ✅ | ❌ chez Zapier |

Pour le SEO, où tu fais beaucoup d'opérations répétitives sur des volumes moyens (centaines/jour), n8n te fait économiser 1500-3000 $/an minimum.

## Lectures liées

- [API REST Gridar publique](/api-docs)
- [MCP Claude pour content marketing](/blog/mcp-claude-content-marketing)
- [SEO automatique pour PME](/blog/seo-automatique-pme-quebecoise)
