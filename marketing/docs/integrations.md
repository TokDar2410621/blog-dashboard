# Intégrations & automatisations

Tu peux auditer, générer, suivre et publier **sans ouvrir le tableau de bord** depuis :

- **ChatGPT, Claude, Claude Code, Cursor, Codex** et tout client MCP, via le connecteur MCP de Gridar
- **n8n, Zapier, Make, GitHub Actions, scripts maison**, via l'[API REST](api.md)

Les deux passent par la même API (`https://api.gridar.app/api/v1`), demandent un plan **Pro ou Agence** et consomment les mêmes quotas que le tableau de bord.

## Comparatif rapide

| | Connecteur MCP | API REST |
|---|---|---|
| Idéal pour | Conversation IA, agents de code | Workflows récurrents, scripts, CI/CD |
| Plan requis | Pro ou Agence | Pro ou Agence |
| Connexion | URL du serveur + OAuth, ou jeton dans l'en-tête | Jeton `btb_` dans l'en-tête |
| Cas type | "Audite mon site et dis-moi quoi corriger en premier" | "Tous les lundis à 6h, relève mes positions" |

## 1. Connecteur MCP

[Model Context Protocol](https://modelcontextprotocol.io) est un standard ouvert pour brancher des outils dans un assistant IA. Le serveur MCP de Gridar expose **69 outils** `gridar_*`.

### Le serveur

| Élément | Valeur |
|---|---|
| URL | `https://mcp.gridar.app/mcp` |
| Transport | Streamable HTTP |
| Authentification | OAuth 2.1 avec PKCE, ou `Authorization: Bearer btb_xxx` |
| Registre officiel MCP | publié sous le nom `app.gridar/gridar` |
| Carte publique (sans jeton) | `https://mcp.gridar.app/.well-known/mcp/server-card.json` : nom, version et liste des outils |
| État du serveur | `https://mcp.gridar.app/health` |

Le serveur tourne chez Gridar : aucun paquet Gridar à installer sur ta machine.

### Plan et limites

- **Plan Pro ou Agence.** La connexion OAuth aboutit sur tous les plans, mais en Essai et en Solo chaque appel d'outil répond une erreur 403 : "Accès API réservé aux plans Pro et Agence".
- **Chaque appel d'outil = 1 requête API.** Il compte dans ta limite horaire : 30 par heure en Pro, 200 en Agence.
- Les outils de génération consomment ton quota d'articles. Voir la section Quotas plus bas.

### Connexion OAuth : ce qui se passe

1. Tu ajoutes l'URL `https://mcp.gridar.app/mcp` dans ton client.
2. Ton client ouvre la page de connexion Gridar. Connecte-toi si besoin, puis clique **Autoriser**.
3. Gridar crée un jeton au nom de ton client (par exemple `MCP - Claude Code`) et le remet à ton client.
4. Ce jeton apparaît dans `/account/api-keys`. Révoque-le là pour couper l'accès.

### Claude (claude.ai et Claude Desktop)

1. Sur claude.ai : **Réglages → Connecteurs** → ajoute un connecteur personnalisé avec l'URL `https://mcp.gridar.app/mcp`.
2. Claude ouvre la page de connexion Gridar (OAuth). Tu autorises, c'est branché.

Option Claude Desktop par fichier de config : Claude Desktop se branche au serveur distant via le pont `mcp-remote`.

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

Le fichier se trouve dans `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) ou `%APPDATA%\Claude\claude_desktop_config.json` (Windows). Redémarre Claude Desktop ensuite.

### ChatGPT

1. Ouvre **Réglages → Connecteurs** (ou active le Developer Mode pour les connecteurs personnalisés).
2. Ajoute un connecteur par URL : `https://mcp.gridar.app/mcp`.
3. ChatGPT ouvre la page de connexion Gridar (OAuth). Tu autorises, c'est branché.

> Les connecteurs personnalisés demandent un compte ChatGPT Pro, Team ou Enterprise, ou le Developer Mode activé.

### Claude Code

```bash
claude mcp add --transport http gridar https://mcp.gridar.app/mcp
```

L'OAuth se lance au premier appel. Pour une session sans navigateur, passe ton jeton en en-tête :

```bash
claude mcp add --transport http gridar https://mcp.gridar.app/mcp \
  --header "Authorization: Bearer btb_ton_token"
```

### Cursor

**Réglages → MCP → Add server** → serveur de type URL : `https://mcp.gridar.app/mcp`.

### Codex CLI, SDK et autres clients

Tout client MCP compatible Streamable HTTP se branche à l'URL `https://mcp.gridar.app/mcp`. Il découvre l'OAuth tout seul : sans jeton, le serveur répond 401 avec un en-tête `WWW-Authenticate` qui pointe vers `/.well-known/oauth-protected-resource`.

Pour un agent sans navigateur, passe l'en-tête `Authorization: Bearer btb_ton_token` avec un jeton créé dans `/account/api-keys`.

### Installation locale (stdio)

Le paquet npm `@gridar/mcp-server` fait tourner le serveur sur ta machine.

> La version publiée sur npm est la **0.4.2** (43 outils). Le serveur hébergé est en **0.7.0** (69 outils). La liste d'outils de cette page correspond au serveur hébergé : préfère-le.

Claude Desktop :

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

Claude Code :

```bash
claude mcp add gridar \
  --env BLOG_DASHBOARD_TOKEN=btb_ton_token \
  -- npx -y @gridar/mcp-server
```

Variables : `BLOG_DASHBOARD_TOKEN` (requis, ton jeton `btb_`) et `BLOG_DASHBOARD_API_BASE` (optionnel, `https://api.gridar.app/api/v1` par défaut).

### Exemples de conversation

> **Toi :** Audite le site 12 et donne-moi les 3 corrections prioritaires.
>
> **Claude :** *(appelle `gridar_site_seo_score`, puis lit ses `action_items`)*

> **Toi :** Récupère les pages à construire pour le site 12 et crée-les dans ce dépôt.
>
> **Claude Code :** *(appelle `gridar_pull_build_queue`, écrit chaque page, déploie, puis appelle `gridar_mark_page_built` avec l'URL en ligne de chaque page)*

### Les 69 outils

#### Compte et sites

| Outil | Ce qu'il fait |
|---|---|
| `gridar_get_me` | Ton plan, ton quota mensuel d'articles et ton usage |
| `gridar_list_sites` | Tes sites : id, domaine, mode d'hébergement, langue par défaut |
| `gridar_get_site` | Configuration complète d'un site : intégrations, langue, base de connaissances, concurrents, GSC, autopilote, profil auteur |
| `gridar_update_site` | Modifie les champs éditables d'un site : nom, description, base de connaissances, concurrents, langue par défaut, bio et titres de l'auteur, domaine du blog public |

#### Articles

| Outil | Ce qu'il fait |
|---|---|
| `gridar_list_articles` | Articles d'un site, filtrables par statut, langue et nombre |
| `gridar_get_article` | Contenu complet (HTML + métadonnées) d'un article |
| `gridar_generate_article` | Génère un article optimisé SEO. Brouillon sur un site hébergé ou à base externe, publié directement sur WordPress, Shopify et Webflow. **1 article du quota (ou 1 crédit)** |
| `gridar_generate_sister_article` | Traduit et adapte un article dans une autre langue, relié au même groupe de traduction (hreflang). Créé en brouillon. Sites hébergés seulement. **1 article du quota (ou 1 crédit)** |
| `gridar_create_article` | Crée un article écrit à la main sur un site hébergé. Aucun quota |
| `gridar_update_article` | Modifie titre, contenu, extrait, statut, image, auteur ou slug d'un article. Tous les modes de site |
| `gridar_delete_article` | **Destructif** : supprime un article. Sur WordPress, Shopify et Webflow, sans corbeille |

#### Audit et contenu

| Outil | Ce qu'il fait |
|---|---|
| `gridar_audit_article` | Audite un contenu brut : score de 0 à 100 + corrections à faire |
| `gridar_get_brief` | Brief de contenu pour un mot-clé : intention, plan, entités, FAQ, signaux E-E-A-T |
| `gridar_bulk_audit` | Audite tous les articles publiés d'un site en parallèle : scores agrégés et principaux problèmes |
| `gridar_check_readability` | Lisibilité d'un texte (Flesch-Kincaid, ARI) |
| `gridar_check_plagiarism` | Détecte le contenu IA et le plagiat d'un texte (Originality.ai) |
| `gridar_check_hreflang` | Vérifie la cohérence des groupes de traduction (hreflang) d'un site. `site_id` requis |
| `gridar_detect_cannibalization` | Paires d'articles qui visent la même intention ou les mêmes mots-clés |
| `gridar_suggest_internal_links` | Liens internes à insérer dans le `content` que tu fournis, choisis parmi les articles du site |
| `gridar_ai_overview_readiness` | Score de 0 à 100 de l'aptitude d'un article à être repris par les réponses IA, sur 5 vérifications : FAQ, structure H2/H3, signaux E-E-A-T, données concrètes, paragraphes extractibles |

#### Santé du site

| Outil | Ce qu'il fait |
|---|---|
| `gridar_site_seo_score` | Score SEO composite du site (0 à 100) sur 9 vérifications pondérées, avec les actions à mener |
| `gridar_check_renderability` | Dit si une URL est rendue côté serveur ou si c'est une coquille JavaScript que Googlebot doit rendre lui-même |
| `gridar_page_speed` | PageSpeed Insights sur une URL : Core Web Vitals + suggestions |
| `gridar_find_broken_links` | Liens sortants des articles en erreur (4xx, 5xx, délai dépassé) |
| `gridar_get_content_decay` | Articles dont les impressions ou clics GSC baissent sur N jours, avec l'action suggérée |

#### Mots-clés, SERP et concurrents

| Outil | Ce qu'il fait |
|---|---|
| `gridar_list_keywords` | Mots-clés suivis d'un site + dernière position relevée |
| `gridar_track_keyword` | Ajoute un mot-clé à suivre, ou réactive un mot-clé retiré |
| `gridar_untrack_keyword` | Arrête le suivi d'un mot-clé. L'historique des positions est conservé |
| `gridar_snapshot_keywords` | Relève maintenant la position de tous les mots-clés suivis d'un site |
| `gridar_suggest_keywords` | Suggère des mots-clés à suivre, à partir de la mémoire du site et de sa page d'accueil |
| `gridar_keyword_research` | Développe un mot-clé de départ en requêtes liées (SERP Google + variantes Gemini), regroupées par famille. Ne donne ni volume ni difficulté |
| `gridar_people_also_ask` | Questions "Autres questions posées" de Google pour un mot-clé |
| `gridar_classify_intent` | Intention de recherche d'un mot-clé (transactionnelle, commerciale, informationnelle, navigationnelle, locale) + niveau de confiance |
| `gridar_analyze_competitors` | Analyse du top 10 Google pour un mot-clé : longueur moyenne, titres communs, entités, manques |
| `gridar_serp_analyze` | Métriques par URL du top 10 (mots, H1/H2/H3, FAQ, vidéo) + moyennes, pour calibrer un article |
| `gridar_suggest_competitors` | Concurrents SEO probables du site |
| `gridar_link_opportunities` | Sites candidats pour des liens entrants sur un mot-clé (domaine, URL, titre, extrait) |

#### Stratégie, landings et clusters

| Outil | Ce qu'il fait |
|---|---|
| `gridar_propose_keyword_strategy` | Propose une structure pour un mot-clé : landing unique, pilier + cluster, comparatif, landing locale ou article |
| `gridar_approve_strategy` | Approuve une stratégie : les landings sont générées en brouillon, les articles restent à générer un par un |
| `gridar_create_landing` | Crée une landing structurée écrite à la main (hero, arguments, preuves, FAQ, appel à l'action). Aucun quota |
| `gridar_generate_landing` | Génère une landing complète par IA à partir d'un mot-clé, en brouillon sur le site hébergé. **1 article du quota (ou 1 crédit)** |
| `gridar_link_pages` | Ajoute un lien contextuel d'une page vers une autre du même site |
| `gridar_cluster_map` | Topic clusters du site : pilier, sous-sujets, pages déjà couvertes et pages manquantes |
| `gridar_build_cluster` | Prompts de construction d'un cluster complet (pilier + sous-sujets), maillage interne inclus. Aucun quota |

#### Opportunités stratégiques

| Outil | Ce qu'il fait |
|---|---|
| `gridar_refresh_strategic_opportunities` | Lance le moteur d'opportunités sur les mots-clés suivis à intention commerciale, transactionnelle ou locale qui n'ont pas encore de landing (8 mots-clés par défaut, 20 au maximum) |
| `gridar_list_strategic_opportunities` | Liste les opportunités : type de page, titre, angle, priorité, estimation de trafic |
| `gridar_action_strategic_opportunity` | `approve` génère la landing, `dismiss` masque l'opportunité, `restore` la remet |
| `gridar_export_page_prompt` | Prompt prêt à coller dans ton propre outil IA (ChatGPT, Lovable, v0, Bolt...) pour intégrer une landing ou créer une page. Aucun quota |

#### Livraison par un agent

Pour un site construit à la main que Gridar ne peut pas publier lui-même. Dans les réglages du site, choisis le mode de livraison **Via un agent**.

| Outil | Ce qu'il fait |
|---|---|
| `gridar_pull_build_queue` | File des pages à créer dans ton dépôt : briefs de landings, articles générés à intégrer tels quels, briefs d'articles. Aucun quota |
| `gridar_mark_page_built` | Signale qu'une page de la file est en ligne, avec son URL. Gridar la retire de la file et la rattache au suivi de positions et à la preuve de résultats |

#### Google Search Console et indexation

| Outil | Ce qu'il fait |
|---|---|
| `gridar_gsc_queries` | Requêtes GSC d'un article (impressions, clics, position). GSC connecté requis |
| `gridar_index_coverage` | Pages que Google a indexées ou non, avec la raison quand GSC est connecté |
| `gridar_submit_sitemap` | Resoumet le sitemap à Google Search Console. Ne force pas l'indexation |
| `gridar_indexnow_setup` | Clé IndexNow du site + fichier à héberger à la racine du domaine |
| `gridar_indexnow_submit` | Soumet des URLs à IndexNow : Bing, Yandex, Seznam, Naver. Pas Google |

#### Visibilité IA

| Outil | Ce qu'il fait |
|---|---|
| `gridar_ai_visibility_summary` | Score de visibilité IA du site (0 à 100), détail par moteur et évolution sur 7 jours |
| `gridar_run_ai_visibility` | Lance une série de vérifications sur les prompts suivis du site |

> `gridar_run_ai_visibility` n'interroge encore aucun moteur IA : ses résultats sont simulés, et le score de `gridar_ai_visibility_summary` se calcule sur ces résultats. Les prompts à suivre s'ajoutent depuis le tableau de bord ou l'[API](api.md).

#### Autopilote

| Outil | Ce qu'il fait |
|---|---|
| `gridar_get_autopilot` | Configuration et état de l'autopilote d'un site |
| `gridar_set_autopilot` | Active ou configure l'autopilote (articles par semaine, publication automatique) |
| `gridar_run_autopilot_now` | Lance un cycle de l'autopilote tout de suite |

#### Mémoire du site

| Outil | Ce qu'il fait |
|---|---|
| `gridar_list_memories` | Morceaux de mémoire du site : articles, base de connaissances, notes, décisions |
| `gridar_add_memory` | Ajoute une note. Les types `manual` et `decision` pèsent plus dans les prochaines générations |
| `gridar_delete_memory` | **Destructif** : supprime un morceau de mémoire |
| `gridar_rebuild_memory` | Recalcule toute la mémoire du site à partir des articles publiés et de la base de connaissances |

#### Preuve de résultats et rapports

| Outil | Ce qu'il fait |
|---|---|
| `gridar_proof_summary` | Impressions et clics gagnés d'après GSC + les 5 articles qui progressent le plus |
| `gridar_proof_attribution` | Relevés par article à J+30, J+60 et J+90, comparés à la situation de départ |
| `gridar_enable_proof_share` | Active la page de preuve publique et renvoie son URL (`rotate` pour changer de lien) |
| `gridar_revoke_proof_share` | **Coupe** la page de preuve publique : l'URL répond 404 tout de suite |
| `gridar_weekly_digest` | Bilan de la semaine d'un site |

Code source : [github.com/TokDar2410621/blog-dashboard/tree/main/mcp-server](https://github.com/TokDar2410621/blog-dashboard/tree/main/mcp-server).

## 2. n8n

Le node communautaire `n8n-nodes-gridar` existe dans le dépôt, mais il n'est pas publié sur npm : **Settings → Community Nodes → Install** ne le trouve pas. Utilise le node **HTTP Request** avec l'[API REST](api.md).

Réglage commun à chaque node HTTP Request :

- URL de base : `https://api.gridar.app/api/v1`
- En-tête : `Authorization` = `Bearer btb_xxx`. Range le jeton dans un credential n8n de type Header Auth, jamais en clair dans le workflow.

### Workflow type : article hebdomadaire automatique

```text
Schedule (lundi 8h)
  ↓
HTTP Request : POST /sites/12/generate/
  body : {"topic": "Tendances SEO Québec {{ $now.format('MMMM yyyy') }}",
          "type": "news", "length": "medium", "language": "fr"}
  ↓
Slack (notifie l'équipe avec le champ output)
```

### Workflow type : audit à la volée

```text
Webhook (POST /audit-incoming)
  ↓
HTTP Request : POST /audit/
  body : {"title": "{{ $json.title }}", "content": "{{ $json.content }}"}
  ↓
IF ({{ $json.score }} < 70)
  → Email "Article à revoir avant publication"
```

### Workflow type : suivi quotidien des positions

```text
Schedule (tous les jours 6h)
  ↓
HTTP Request : POST /sites/12/keywords/snapshot/
  ↓
HTTP Request : GET /sites/12/keywords/
  ↓
Google Sheets (ajoute keyword, latest_position, latest_recorded_at)
```

## 3. Zapier, Make, GitHub Actions, scripts

Le module HTTP de ton outil + l'[API REST publique](api.md). Mêmes jetons, mêmes limites.

## Quotas

Toutes les intégrations consomment ton plan normal :

- Générer un article, un article frère ou une landing par IA = 1 article du quota mensuel, ou 1 crédit si ton quota est épuisé.
- Les autres outils ne touchent pas au quota d'articles. Chaque appel compte dans ta limite horaire.

| Plan | Limite horaire | Articles/mois |
|---|---|---|
| Essai / Solo | pas d'accès par jeton | 1 / 8 |
| Pro | 30 req/h | 60 |
| Agence | 200 req/h | 200 |

Voir [Plans, crédits et quotas](plans-credits.md).

## Sécurité

- Le jeton est privé : traite-le comme un mot de passe.
- Ne le commit jamais dans Git et ne le mets jamais dans une URL. Utilise les **secrets** de n8n, de GitHub Actions ou de ton hébergeur.
- Un jeton donne accès à tous tes sites et à tous les outils, suppression comprise. Il n'existe pas de jeton limité à la lecture.
- Tu peux révoquer un jeton à tout moment dans `/account/api-keys` sans toucher aux autres. Les jetons créés par OAuth y apparaissent aussi.
- Crée un jeton **par intégration** (`n8n-prod`, `claude-desktop-laptop`, `gh-actions-blog`) pour pouvoir en couper un seul.

## Support

- Bug ou question : [GitHub Issues](https://github.com/TokDar2410621/blog-dashboard/issues)
- Un outil ou une opération te manque : ouvre une issue
