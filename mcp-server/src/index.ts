#!/usr/bin/env node
/**
 * Gridar MCP server.
 *
 * Exposes the Gridar REST API as Model Context Protocol tools so any
 * MCP-compatible client (Claude Desktop, Claude Code, Cursor, Continue, ...)
 * can generate, audit and publish SEO articles inside its own conversation.
 */

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";
import { z } from "zod";

import {
  ApiError,
  actionStrategicOpportunity,
  addMemory,
  exportPagePrompt,
  pullBuildQueue,
  markPageBuilt,
  aiOverviewReadiness,
  aiVisibilitySummary,
  analyzeCompetitors,
  approveStrategy,
  auditArticle,
  bulkAudit,
  checkHreflang,
  checkPlagiarism,
  checkReadability,
  checkRenderability,
  classifyIntent,
  createLanding,
  createManualArticle,
  deleteArticle,
  deleteMemory,
  detectCannibalization,
  enableProofShare,
  generateArticle,
  generateLanding,
  generateSisterArticle,
  getArticle,
  getAutopilotConfig,
  getBrief,
  getBrokenLinks,
  getContentDecay,
  getGscQueries,
  getMe,
  getProofAttribution,
  getProofSummary,
  getSiteDetail,
  getWeeklyDigest,
  keywordResearch,
  linkOpportunities,
  linkPages,
  listArticles,
  listKeywords,
  listMemories,
  listSites,
  listStrategicOpportunities,
  pageSpeed,
  peopleAlsoAsk,
  proposeKeywordStrategy,
  rebuildMemory,
  refreshStrategicOpportunities,
  revokeProofShare,
  runAiVisibility,
  runAutopilotNow,
  serpAnalyze,
  setAutopilotConfig,
  siteSeoScore,
  snapshotKeywords,
  suggestCompetitors,
  suggestInternalLinks,
  suggestKeywords,
  trackKeyword,
  untrackKeyword,
  updateArticle,
  updateSite,
} from "./api.js";

// ---------------------------------------------------------------------------
// Tool schemas (zod -> JSON Schema for the MCP catalog)
// ---------------------------------------------------------------------------

const NoArgs = z.object({}).strict();

const ListArticlesArgs = z
  .object({
    site_id: z.number().int().positive(),
    status: z
      .enum(["draft", "published", "archived"])
      .optional()
      .describe("Filter by article status"),
    language: z
      .enum(["fr", "en", "es"])
      .optional()
      .describe("Filter by content language"),
    limit: z
      .number()
      .int()
      .positive()
      .max(100)
      .optional()
      .describe("Max number of results (default 25)"),
  })
  .strict();

const GetArticleArgs = z
  .object({
    site_id: z.number().int().positive(),
    slug: z.string().min(1),
  })
  .strict();

const GenerateArticleArgs = z
  .object({
    site_id: z.number().int().positive(),
    topic: z
      .string()
      .optional()
      .describe(
        "Free-form topic. Either topic OR title is required. Topic is more SEO-driven (we research keywords from it).",
      ),
    title: z
      .string()
      .optional()
      .describe("Explicit title to write about, bypasses topic research."),
    type: z
      .enum([
        "guide",
        "news",
        "tutorial",
        "comparison",
        "review",
        "story",
        "local",
      ])
      .optional()
      .describe("Article archetype. Default: guide."),
    length: z
      .enum(["short", "medium", "long"])
      .optional()
      .describe(
        "short = ~600 words, medium = ~1200 (default), long = ~2000.",
      ),
    language: z
      .enum(["fr", "en", "es"])
      .optional()
      .describe("Output language. Defaults to the site's default language."),
    keywords: z
      .string()
      .optional()
      .describe("Comma-separated keywords to weave into the article."),
    brief: z
      .record(z.unknown())
      .optional()
      .describe(
        "Pre-built content brief object (intent, outline, entities, faq) returned by get_brief.",
      ),
  })
  .strict()
  .refine((v) => !!v.topic || !!v.title, {
    message: "Provide either 'topic' or 'title'.",
  });

const GenerateSisterArticleArgs = z
  .object({
    site_id: z.number().int().positive(),
    source_slug: z
      .string()
      .min(1)
      .describe("Slug of the source article to translate from."),
    target_language: z
      .enum(["fr", "en", "es"])
      .describe(
        "Target language for the translation. Must differ from the source article's language and be allowed by the site.",
      ),
  })
  .strict();

const AuditArticleArgs = z
  .object({
    title: z.string().min(1),
    excerpt: z.string().optional(),
    content: z.string().min(1),
    keyword: z
      .string()
      .optional()
      .describe("Target keyword the article should rank on."),
    language: z.enum(["fr", "en", "es"]).optional(),
  })
  .strict();

const GetBriefArgs = z
  .object({
    keyword: z.string().min(1),
    language: z.enum(["fr", "en", "es"]).optional(),
  })
  .strict();

const SiteIdOnly = z
  .object({ site_id: z.number().int().positive() })
  .strict();

const UpdateSiteArgs = z
  .object({
    site_id: z.number().int().positive(),
    name: z.string().optional(),
    description: z.string().optional(),
    knowledge_base: z.string().optional().describe("Long-form site brand context / FAQ"),
    competitors: z.string().optional().describe("One brand per line"),
    default_language: z.enum(["fr", "en", "es"]).optional(),
    author_bio: z.string().optional(),
    author_credentials: z.string().optional(),
    public_blog_domain: z.string().optional(),
  })
  .strict();

const CreateArticleArgs = z
  .object({
    site_id: z.number().int().positive(),
    title: z.string().min(1),
    content: z.string().min(1).describe("Markdown body"),
    excerpt: z.string().optional(),
    slug: z.string().optional().describe("Auto-slugified from title if omitted"),
    status: z.enum(["draft", "published", "scheduled"]).optional(),
    author: z.string().optional(),
    language: z.enum(["fr", "en", "es"]).optional(),
    cover_image: z.string().optional(),
  })
  .strict();

const UpdateArticleArgs = z
  .object({
    site_id: z.number().int().positive(),
    slug: z.string().min(1),
    title: z.string().optional(),
    content: z.string().optional(),
    excerpt: z.string().optional(),
    status: z.enum(["draft", "published", "scheduled"]).optional(),
    cover_image: z.string().optional(),
    author: z.string().optional(),
  })
  .strict();

const SlugRefArgs = z
  .object({
    site_id: z.number().int().positive(),
    slug: z.string().min(1),
  })
  .strict();

const TrackKeywordArgs = z
  .object({
    site_id: z.number().int().positive(),
    keyword: z.string().min(1),
    language: z.enum(["fr", "en", "es"]).optional(),
    target_url: z.string().optional().describe("URL the keyword should rank to"),
  })
  .strict();

const UntrackKeywordArgs = z
  .object({
    site_id: z.number().int().positive(),
    keyword_id: z.number().int().positive(),
  })
  .strict();

const KeywordLangArgs = z
  .object({
    keyword: z.string().min(1),
    language: z.enum(["fr", "en", "es"]).optional(),
  })
  .strict();

const SerpAnalyzeArgs = z
  .object({
    site_id: z.number().int().positive(),
    keyword: z.string().min(1),
    language: z.enum(["fr", "en", "es"]).optional(),
  })
  .strict();

const RunAiVisibilityArgs = z
  .object({
    site_id: z.number().int().positive(),
    prompt_id: z
      .number()
      .int()
      .positive()
      .optional()
      .describe(
        "Optional: only re-check this single tracked prompt. Omit to re-check every prompt on the site.",
      ),
  })
  .strict();

const ContentDecayArgs = z
  .object({
    site_id: z.number().int().positive(),
    days: z
      .number()
      .int()
      .min(7)
      .max(90)
      .optional()
      .describe("Comparison window in days, default 30"),
  })
  .strict();

const HreflangArgs = z
  .object({
    site_id: z.number().int().positive().optional(),
    html: z
      .string()
      .optional()
      .describe("Optional raw HTML to scan instead of crawling a site"),
  })
  .strict();

const LinkSuggestionsArgs = z
  .object({
    site_id: z.number().int().positive(),
    article_slug: z.string().optional(),
    content: z.string().optional(),
    keyword: z.string().optional(),
  })
  .strict();

const ReadabilityArgs = z
  .object({
    content: z.string().min(1),
    language: z.enum(["fr", "en", "es"]).optional(),
  })
  .strict();

const PlagiarismArgs = z
  .object({
    content: z.string().min(1),
  })
  .strict();

const GscQueriesArgs = z
  .object({
    site_id: z.number().int().positive(),
    slug: z
      .string()
      .min(1)
      .describe(
        "Article slug to pull queries for. Required: GSC filters rows to that single page URL.",
      ),
    days: z.number().int().min(1).max(90).optional(),
    limit: z.number().int().min(1).max(500).optional(),
  })
  .strict();

const AutopilotConfigArgs = z
  .object({
    site_id: z.number().int().positive(),
    enabled: z.boolean().optional(),
    weekly_count: z.number().int().min(1).max(7).optional(),
    auto_publish: z
      .boolean()
      .optional()
      .describe("If true, articles auto-publish; if false they stay draft"),
  })
  .strict();

const AddMemoryArgs = z
  .object({
    site_id: z.number().int().positive(),
    content: z.string().min(1),
    title: z.string().optional(),
    kind: z
      .enum(["manual", "decision", "kb", "audit"])
      .optional()
      .describe("Storage kind; default 'manual' carries instruction weight"),
  })
  .strict();

const MemoryIdArgs = z
  .object({
    site_id: z.number().int().positive(),
    memory_id: z.number().int().positive(),
  })
  .strict();

const ProofAttributionArgs = z
  .object({
    site_id: z.number().int().positive(),
    post_id: z.number().int().positive().optional().describe("Filter to one post"),
  })
  .strict();

const ProofShareToggleArgs = z
  .object({
    site_id: z.number().int().positive(),
    rotate: z
      .boolean()
      .optional()
      .describe("Force a new token (revokes the previous one)"),
  })
  .strict();

const KeywordResearchArgs = z
  .object({
    seed: z.string().min(1).describe("Seed keyword to expand from (required)"),
    language: z.enum(["fr", "en", "es"]).optional(),
    country: z
      .string()
      .optional()
      .describe("ISO 3166-1 alpha-2, e.g. 'ca' (reserved; not used by backend yet)"),
  })
  .strict();

const PageSpeedArgs = z
  .object({
    url: z.string().url(),
    strategy: z.enum(["mobile", "desktop"]).optional(),
  })
  .strict();

const CheckRenderabilityArgs = z
  .object({
    url: z
      .string()
      .url()
      .describe(
        "Public URL to fetch and inspect (must include http:// or https://).",
      ),
  })
  .strict();

// --- Topic Cluster Planner (0.5.0) ----------------------------------------

const ClassifyIntentArgs = z
  .object({
    keyword: z.string().min(1),
    site_id: z
      .number()
      .int()
      .positive()
      .optional()
      .describe("Optional - improves brand detection by checking the site name"),
  })
  .strict();

const ProposeKeywordStrategyArgs = z
  .object({
    site_id: z.number().int().positive(),
    keyword: z.string().min(1),
    language: z.enum(["fr", "en", "es"]).optional(),
  })
  .strict();

const ApproveStrategyArgs = z
  .object({
    site_id: z.number().int().positive(),
    strategy_id: z.number().int().positive(),
    customizations: z
      .record(z.unknown())
      .optional()
      .describe(
        "Optional override: {pages: [...]} to replace the proposed pages list",
      ),
  })
  .strict();

// --- Strategic Opportunities ---------------------------------------------

const ListStrategicOpportunitiesArgs = z
  .object({
    site_id: z.number().int().positive(),
    include_dismissed: z
      .boolean()
      .optional()
      .describe("Set true to also return opportunities the user dismissed"),
  })
  .strict();

const RefreshStrategicOpportunitiesArgs = z
  .object({
    site_id: z.number().int().positive(),
    max_keywords: z
      .number()
      .int()
      .positive()
      .max(20)
      .optional()
      .describe(
        "Cap on how many tracked keywords the engine runs Claude against (default 8, max 20). Each one is one Claude call - keep this small unless you want a costly refresh.",
      ),
  })
  .strict();

const StrategicOpportunityActionArgs = z
  .object({
    site_id: z.number().int().positive(),
    opportunity_id: z.number().int().positive(),
    action: z
      .enum(["approve", "dismiss", "restore"])
      .describe(
        "approve = generate the landing now and mark done; dismiss = hide it from the proposed list; restore = un-dismiss a previously dismissed opportunity.",
      ),
  })
  .strict();

const ExportPagePromptArgs = z
  .object({
    site_id: z.number().int().positive(),
    landing_id: z
      .number()
      .int()
      .positive()
      .optional()
      .describe(
        "Export an INTEGRATE prompt from an existing HostedLanding (copy already written, must be reproduced verbatim).",
      ),
    opportunity_id: z
      .number()
      .int()
      .positive()
      .optional()
      .describe(
        "Export a CREATE prompt from a StrategicOpportunity (only the concept exists, the target AI writes the copy following the brief).",
      ),
    stack: z
      .enum([
        "nextjs",
        "react",
        "html",
        "astro",
        "wordpress",
        "webflow",
        "generic",
      ])
      .optional()
      .describe(
        "Adapts the final integration instructions to the user's tech stack. Default: generic.",
      ),
  })
  .strict()
  .refine(
    (d) => (d.landing_id != null) !== (d.opportunity_id != null),
    {
      message:
        "Provide exactly one of landing_id or opportunity_id, not both, not neither.",
    },
  );

const PullBuildQueueArgs = z
  .object({
    site_id: z.number().int().positive(),
    stack: z
      .enum([
        "nextjs",
        "react",
        "html",
        "astro",
        "wordpress",
        "webflow",
        "generic",
      ])
      .optional()
      .describe(
        "Adapts the landing build prompts to the target stack. Default: generic.",
      ),
  })
  .strict();

const MarkPageBuiltArgs = z
  .object({
    site_id: z.number().int().positive(),
    kind: z
      .enum(["landing", "article", "article_brief"])
      .describe(
        "What was built, matching the queue entry: 'landing' (a landing brief), " +
          "'article' (a mode=ready article with generated copy), or " +
          "'article_brief' (a mode=brief article you wrote yourself).",
      ),
    id: z
      .number()
      .int()
      .positive()
      .describe(
        "The queue entry's id: opportunity_id for 'landing' and 'article_brief', " +
          "post_id for 'article'.",
      ),
    url: z
      .string()
      .url()
      .describe("The live URL of the page you built in the client's site."),
  })
  .strict();

const CreateLandingArgs = z
  .object({
    site_id: z.number().int().positive(),
    title: z.string().min(1),
    h1: z.string().optional(),
    slug: z.string().optional(),
    hero_subtitle: z.string().optional(),
    hero_cta_text: z.string().optional(),
    hero_cta_url: z.string().optional(),
    value_props: z.array(z.record(z.unknown())).optional(),
    social_proof: z.array(z.record(z.unknown())).optional(),
    faq: z.array(z.record(z.unknown())).optional(),
    cta_bottom_text: z.string().optional(),
    cta_bottom_url: z.string().optional(),
    body_markdown: z.string().optional(),
    target_keyword: z.string().optional(),
    schema_type: z
      .enum([
        "WebPage",
        "Service",
        "Product",
        "LocalBusiness",
        "FAQPage",
        "Article",
      ])
      .optional(),
    page_subtype: z
      .enum([
        "service",
        "product",
        "pillar",
        "comparison",
        "local",
        "about",
        "contact",
        "generic",
      ])
      .optional(),
    language: z.enum(["fr", "en", "es"]).optional(),
    status: z.enum(["draft", "published"]).optional(),
    cover_image: z.string().optional(),
    meta_description: z.string().optional(),
  })
  .strict();

const GenerateLandingArgs = z
  .object({
    site_id: z.number().int().positive(),
    keyword: z.string().min(1),
    primary_cta_text: z.string().optional(),
    primary_cta_url: z.string().optional(),
    value_props: z
      .array(z.record(z.unknown()))
      .optional()
      .describe("Optional seed value-props the LLM will keep + expand"),
    page_subtype: z
      .enum(["service", "product", "pillar", "comparison", "local"])
      .optional(),
    language: z.enum(["fr", "en", "es"]).optional(),
  })
  .strict();

const LinkPagesArgs = z
  .object({
    site_id: z.number().int().positive(),
    source_slug: z.string().min(1),
    target_slug: z.string().min(1),
    anchor_text: z.string().min(1),
  })
  .strict();

// ---------------------------------------------------------------------------
// Tool registry
// ---------------------------------------------------------------------------

interface ToolDef<S extends z.ZodTypeAny = z.ZodTypeAny> {
  name: string;
  description: string;
  schema: S;
  handler: (input: z.infer<S>) => Promise<unknown>;
}

const tools: ToolDef[] = [
  {
    name: "gridar_get_me",
    description:
      "Return the authenticated user's plan, current monthly article quota and remaining usage.",
    schema: NoArgs,
    handler: () => getMe(),
  },
  {
    name: "gridar_list_sites",
    description:
      "List the sites belonging to the user (id, domain, hosting mode, default language).",
    schema: NoArgs,
    handler: () => listSites(),
  },
  {
    name: "gridar_list_articles",
    description:
      "List articles on a given site. Optional filters: status, language, limit.",
    schema: ListArticlesArgs,
    handler: (input) =>
      listArticles(input.site_id, {
        status: input.status,
        language: input.language,
        limit: input.limit,
      }),
  },
  {
    name: "gridar_get_article",
    description:
      "Return the full content (HTML + metadata) of a single article identified by site_id and slug.",
    schema: GetArticleArgs,
    handler: (input) => getArticle(input.site_id, input.slug),
  },
  {
    name: "gridar_generate_article",
    description:
      "Generate a new SEO-optimized article on the given site. Consumes one article from the user's monthly quota (or one credit). Returns the generated content and the new total post count.",
    schema: GenerateArticleArgs,
    handler: (input) => {
      const { site_id, ...body } = input;
      return generateArticle(site_id, body);
    },
  },
  {
    name: "gridar_generate_sister_article",
    description:
      "Translate + adapt an existing article into another language and publish it as a sibling sharing the same translation_group (so hreflang alternates wire up automatically). Costs one article from the user's monthly quota (or one credit). Only available on hosted-mode sites. The new post is created with status='draft' for review.",
    schema: GenerateSisterArticleArgs,
    handler: (input) =>
      generateSisterArticle(input.site_id, input.source_slug, {
        target_language: input.target_language,
      }),
  },
  {
    name: "gridar_audit_article",
    description:
      "Run the SEO auditor on raw content. Returns a 0-100 score plus actionable suggestions (length, keyword density, headings, links, meta).",
    schema: AuditArticleArgs,
    handler: (input) => auditArticle(input),
  },
  {
    name: "gridar_get_brief",
    description:
      "Build a content brief for a target keyword: search intent, outline, entities to cover, FAQ candidates, E-E-A-T signals.",
    schema: GetBriefArgs,
    handler: (input) => getBrief(input),
  },
  {
    name: "gridar_list_keywords",
    description:
      "List the tracked keywords for a site with their latest recorded ranking.",
    schema: SiteIdOnly,
    handler: (input) => listKeywords(input.site_id),
  },
  {
    name: "gridar_snapshot_keywords",
    description:
      "Trigger a fresh ranking snapshot for all tracked keywords on a site. Returns the count of positions recorded.",
    schema: SiteIdOnly,
    handler: (input) => snapshotKeywords(input.site_id),
  },
  {
    name: "gridar_weekly_digest",
    description:
      "Return the weekly digest for a site (traffic, ranking, content decay) over the last 7 days.",
    schema: SiteIdOnly,
    handler: (input) => getWeeklyDigest(input.site_id),
  },
  // --- Site management ----------------------------------------------------
  {
    name: "gridar_get_site",
    description:
      "Return full configuration of one site: integrations status, default language, knowledge base, competitors, GSC connection, autopilot config, author E-E-A-T fields.",
    schema: SiteIdOnly,
    handler: (input) => getSiteDetail(input.site_id),
  },
  {
    name: "gridar_update_site",
    description:
      "Update editable site fields (name, description, knowledge_base, competitors, default_language, author_bio, author_credentials, public_blog_domain). Pass only the fields you want to change.",
    schema: UpdateSiteArgs,
    handler: (input) => {
      const { site_id, ...fields } = input;
      return updateSite(site_id, fields);
    },
  },
  // --- Article CRUD (manual writes) --------------------------------------
  {
    name: "gridar_create_article",
    description:
      "Create a manually-authored article on a hosted site (no AI generation, no quota consumed). Use this when the user already has content to publish via the dashboard.",
    schema: CreateArticleArgs,
    handler: (input) => {
      const { site_id, ...body } = input;
      return createManualArticle(site_id, body);
    },
  },
  {
    name: "gridar_update_article",
    description:
      "Patch fields of an existing article (title, content, excerpt, status, cover_image, author, slug). Works on all site modes: hosted, external (Postgres), WordPress, Shopify, and Webflow. The CMS adapter is selected automatically from the site's mode. Status=published auto-sets published_at on hosted/external; CMS-specific status mapping happens for WP/Shopify/Webflow.",
    schema: UpdateArticleArgs,
    handler: (input) => {
      const { site_id, slug, ...fields } = input;
      return updateArticle(site_id, slug, fields);
    },
  },
  {
    name: "gridar_delete_article",
    description:
      "DESTRUCTIVE: permanently delete an article. Works on all site modes: hosted, external, WordPress, Shopify, and Webflow. CMS-side deletes are forced (no trash). Cascades attribution rows on hosted.",
    schema: SlugRefArgs,
    handler: (input) => deleteArticle(input.site_id, input.slug),
  },
  // --- Keyword tracking ---------------------------------------------------
  {
    name: "gridar_track_keyword",
    description:
      "Add a keyword to track on a site. SERP position is snapshotted daily by the rank_snapshot cron. Reactivates the row if it was previously soft-deleted.",
    schema: TrackKeywordArgs,
    handler: (input) => {
      const { site_id, ...body } = input;
      return trackKeyword(site_id, body);
    },
  },
  {
    name: "gridar_untrack_keyword",
    description:
      "Soft-delete a tracked keyword (sets is_active=False). Historical SerpRank snapshots are preserved.",
    schema: UntrackKeywordArgs,
    handler: (input) => untrackKeyword(input.site_id, input.keyword_id),
  },
  {
    name: "gridar_suggest_keywords",
    description:
      "Ask Claude to suggest new tracked keywords for the site, anchored on RAG memory + homepage scrape (not just brand name).",
    schema: SiteIdOnly,
    handler: (input) => suggestKeywords(input.site_id),
  },
  {
    name: "gridar_suggest_competitors",
    description:
      "Auto-detect likely SEO competitors for the site based on homepage + tracked keywords.",
    schema: SiteIdOnly,
    handler: (input) => suggestCompetitors(input.site_id),
  },
  // --- SEO analysis -------------------------------------------------------
  {
    name: "gridar_analyze_competitors",
    description:
      "Analyze the SERP top 10 for a keyword: average word count, common headings, entity coverage, gap analysis.",
    schema: KeywordLangArgs,
    handler: (input) => analyzeCompetitors(input),
  },
  {
    name: "gridar_serp_analyze",
    description:
      "SERP Analyzer: fetch the top 10 organic results for a keyword and compute per-URL metrics (word count, h1/h2/h3 count, FAQ presence, video embed) plus averages. Lightweight Surfer-style benchmark used to size a competing article.",
    schema: SerpAnalyzeArgs,
    handler: (input) => {
      const { site_id, ...body } = input;
      return serpAnalyze(site_id, body);
    },
  },
  {
    name: "gridar_ai_visibility_summary",
    description:
      "AI Visibility tracker: returns aggregated metrics describing how often the site is cited in LLM responses (ChatGPT, Perplexity, Gemini, SearchGPT, Claude). Output: {score (weighted 0-100), total_mentions, cited_pages_count, total_checks, total_prompts, breakdown_by_engine: {engine: {total_checks, cited_count, cite_rate}}, delta_7d}. Use this to show users their AI-search visibility (the next-gen SEO metric).",
    schema: SiteIdOnly,
    handler: (input) => aiVisibilitySummary(input.site_id),
  },
  {
    name: "gridar_run_ai_visibility",
    description:
      "Trigger an AI Visibility check series for a site's tracked prompts. Creates one AiVisibilityResult per (prompt, engine) pair across all 5 engines (ChatGPT, Perplexity, Gemini, SearchGPT, Claude). V1: results are mocked plausibly so the user can validate the UI before external LLM APIs are wired. Pass prompt_id to re-check only a single prompt.",
    schema: RunAiVisibilityArgs,
    handler: (input) => {
      const { site_id, ...body } = input;
      return runAiVisibility(site_id, body);
    },
  },
  {
    name: "gridar_get_content_decay",
    description:
      "Find articles whose GSC impressions / clicks dropped significantly over the last N days. Suggests refresh / expand / redirect actions.",
    schema: ContentDecayArgs,
    handler: (input) => getContentDecay(input.site_id, input.days ?? 30),
  },
  {
    name: "gridar_find_broken_links",
    description:
      "Crawl the site articles + check outgoing links. Returns list of 4xx/5xx/timeouts.",
    schema: SiteIdOnly,
    handler: (input) => getBrokenLinks(input.site_id),
  },
  {
    name: "gridar_check_hreflang",
    description:
      "Validate hreflang tags on a site (translation_group consistency) OR on a raw HTML payload.",
    schema: HreflangArgs,
    handler: (input) => checkHreflang(input),
  },
  {
    name: "gridar_detect_cannibalization",
    description:
      "Find pairs of articles on a site that compete for the same intent / keywords. Cross-language and cross-status aware.",
    schema: SiteIdOnly,
    handler: (input) => detectCannibalization(input.site_id),
  },
  {
    name: "gridar_suggest_internal_links",
    description:
      "AI suggestions for internal-link insertions on a target article, anchored on the site's content corpus.",
    schema: LinkSuggestionsArgs,
    handler: (input) => {
      const { site_id, ...body } = input;
      return suggestInternalLinks(site_id, body);
    },
  },
  {
    name: "gridar_bulk_audit",
    description:
      "Run the SEO audit across ALL published articles of a site in parallel (Gemini). Returns aggregated scores + top issues. Can take 30-60s on large sites.",
    schema: SiteIdOnly,
    handler: (input) => bulkAudit(input.site_id),
  },
  {
    name: "gridar_check_readability",
    description:
      "Score content readability (Flesch-Kincaid, ARI) in FR or EN.",
    schema: ReadabilityArgs,
    handler: (input) => checkReadability(input),
  },
  {
    name: "gridar_check_plagiarism",
    description:
      "Run originality / plagiarism check on the content (Tier 4 plan).",
    schema: PlagiarismArgs,
    handler: (input) => checkPlagiarism(input),
  },
  {
    name: "gridar_keyword_research",
    description:
      "Discover related keywords + monthly volumes + difficulty from a seed. Uses Serper + Gemini.",
    schema: KeywordResearchArgs,
    handler: (input) => keywordResearch(input),
  },
  {
    name: "gridar_page_speed",
    description:
      "Run PageSpeed Insights on a URL. Returns Core Web Vitals + suggestions.",
    schema: PageSpeedArgs,
    handler: (input) => pageSpeed(input),
  },
  {
    name: "gridar_people_also_ask",
    description:
      "Harvest People-Also-Ask questions from Google SERP for a keyword. Useful to seed FAQ schemas.",
    schema: KeywordLangArgs,
    handler: (input) => peopleAlsoAsk(input),
  },
  {
    name: "gridar_link_opportunities",
    description:
      "Surface candidate sites for backlink outreach on a keyword. Queries Serper for 'best <keyword> sites' + resources / blogs variants, de-duplicates by domain, filters out social/marketplace giants, and returns the top targets (domain + url + title + snippet + source_query).",
    schema: KeywordLangArgs,
    handler: (input) => linkOpportunities(input),
  },
  // --- GSC ----------------------------------------------------------------
  {
    name: "gridar_gsc_queries",
    description:
      "Pull top GSC queries (impressions / clicks / position) for a single article page over the last N days. Requires the article `slug`; the site must have GSC connected.",
    schema: GscQueriesArgs,
    handler: (input) =>
      getGscQueries(
        input.site_id,
        input.slug,
        input.days ?? 28,
        input.limit ?? 50,
      ),
  },
  // --- Autopilot ----------------------------------------------------------
  {
    name: "gridar_get_autopilot",
    description:
      "Return autopilot config for a site: enabled flag, weekly_count, last_run_at, next_run_at, last_error.",
    schema: SiteIdOnly,
    handler: (input) => getAutopilotConfig(input.site_id),
  },
  {
    name: "gridar_set_autopilot",
    description:
      "Configure autopilot. Pass only the fields you want to change.",
    schema: AutopilotConfigArgs,
    handler: (input) => {
      const { site_id, ...body } = input;
      return setAutopilotConfig(site_id, body);
    },
  },
  {
    name: "gridar_run_autopilot_now",
    description:
      "Manually trigger one autopilot generation cycle for a site, ignoring the cron schedule. Useful for debugging or one-off generation.",
    schema: SiteIdOnly,
    handler: (input) => runAutopilotNow(input.site_id),
  },
  // --- RAG memory ---------------------------------------------------------
  {
    name: "gridar_list_memories",
    description:
      "List the site's RAG memory chunks (articles + KB + manual notes + audit decisions). Paginated.",
    schema: SiteIdOnly,
    handler: (input) => listMemories(input.site_id),
  },
  {
    name: "gridar_add_memory",
    description:
      "Add a manual note to a site's RAG memory. 'manual' and 'decision' kinds carry stronger instruction weight in future generations.",
    schema: AddMemoryArgs,
    handler: (input) => {
      const { site_id, ...body } = input;
      return addMemory(site_id, body);
    },
  },
  {
    name: "gridar_delete_memory",
    description:
      "DESTRUCTIVE: delete a memory chunk from a site's RAG.",
    schema: MemoryIdArgs,
    handler: (input) => deleteMemory(input.site_id, input.memory_id),
  },
  {
    name: "gridar_rebuild_memory",
    description:
      "Re-chunk and re-embed all published articles + KB into the RAG memory. Costs Voyage AI tokens (~$0.001 per 100 chunks).",
    schema: SiteIdOnly,
    handler: (input) => rebuildMemory(input.site_id),
  },
  // --- Proof loop ---------------------------------------------------------
  {
    name: "gridar_proof_summary",
    description:
      "Aggregated site-level proof of value: total impressions gained, clicks gained, top 5 article gainers.",
    schema: SiteIdOnly,
    handler: (input) => getProofSummary(input.site_id),
  },
  {
    name: "gridar_proof_attribution",
    description:
      "List per-article attribution rows (J+30 / J+60 / J+90 snapshots vs baseline). Optionally filter by post_id.",
    schema: ProofAttributionArgs,
    handler: (input) => getProofAttribution(input.site_id, input.post_id),
  },
  {
    name: "gridar_enable_proof_share",
    description:
      "Enable the public proof page for a site. Returns a public_url that anyone can visit (read-only). Pass rotate=true to revoke the previous token.",
    schema: ProofShareToggleArgs,
    handler: (input) => enableProofShare(input.site_id, input.rotate ?? false),
  },
  {
    name: "gridar_revoke_proof_share",
    description:
      "Disable the public proof page. The URL returns 404 immediately. Historical attribution data is preserved internally.",
    schema: SiteIdOnly,
    handler: (input) => revokeProofShare(input.site_id),
  },
  // --- Topic Cluster Planner (0.5.0) -------------------------------------
  {
    name: "gridar_classify_intent",
    description:
      "Classify the search intent of a keyword (transactional, commercial, informational, navigational, local) with a confidence score. Step 1 of the topic cluster workflow. Pass site_id for brand-aware detection.",
    schema: ClassifyIntentArgs,
    handler: (input) => classifyIntent(input),
  },
  {
    name: "gridar_propose_keyword_strategy",
    description:
      "Propose a site structure for a target keyword: classifies intent, analyzes the SERP, then proposes single-landing OR pillar+cluster OR comparison-table OR local-landing OR blog post. Returns a KeywordStrategy.id the user can approve. Idempotent on (site, keyword): re-running refreshes a draft, never overwrites an approved strategy.",
    schema: ProposeKeywordStrategyArgs,
    handler: (input) =>
      proposeKeywordStrategy(input.site_id, {
        keyword: input.keyword,
        language: input.language,
      }),
  },
  {
    name: "gridar_approve_strategy",
    description:
      "Approve a proposed keyword strategy and generate every proposed_page. Landings are AI-generated and saved as drafts; articles are queued (the user runs gridar_generate_article on each one to control quota). Pass customizations.pages to override the proposed pages list before generation.",
    schema: ApproveStrategyArgs,
    handler: (input) =>
      approveStrategy(input.site_id, input.strategy_id, {
        customizations: input.customizations,
      }),
  },
  {
    name: "gridar_create_landing",
    description:
      "Create a structured landing page manually (no AI, no quota). Body is composed of structured blocks: hero (h1 + subtitle + CTA), value_props, social_proof, FAQ, bottom CTA. Use this when the user already has the copy.",
    schema: CreateLandingArgs,
    handler: (input) => {
      const { site_id, ...body } = input;
      return createLanding(site_id, body);
    },
  },
  {
    name: "gridar_generate_landing",
    description:
      "AI-generate a complete landing page payload from a target keyword (H1, hero subtitle, 3-5 value props, social proof, 4-6 FAQ, bottom CTA, body markdown). Consumes one article from the user's monthly quota (or one credit). Saved as draft on the hosted site.",
    schema: GenerateLandingArgs,
    handler: (input) => {
      const { site_id, ...body } = input;
      return generateLanding(site_id, body);
    },
  },
  {
    name: "gridar_link_pages",
    description:
      "Insert an inline contextual link from one page to another on the same site. Works between landings, articles, or any mix. If the anchor text is found in the source body it's converted in-place; otherwise a 'Voir aussi' line is appended. No-op when already linked. Use to build topic cluster internal linking.",
    schema: LinkPagesArgs,
    handler: (input) =>
      linkPages(input.site_id, {
        source_slug: input.source_slug,
        target_slug: input.target_slug,
        anchor_text: input.anchor_text,
      }),
  },
  {
    name: "gridar_site_seo_score",
    description:
      "Composite SEO health score (0-100) for a site, computed from 9 weighted checks: indexability, author bio, business model declared, GSC connection, presence of an approved pillar+spokes cluster, hreflang validity (if multilingual), Core Web Vitals, FAQ schema coverage, and absence of transactional intents stuck on blog posts. Returns {score, breakdown, action_items: [{issue, fix_url}]} so the UI / agent can surface concrete next steps.",
    schema: SiteIdOnly,
    handler: (input) => siteSeoScore(input.site_id),
  },
  {
    name: "gridar_ai_overview_readiness",
    description:
      "Score how AI-Overview-ready a single article is (0-100). Computed from 5 weighted checks: FAQ density (25%), H2/H3 structure (20%), E-E-A-T signals - author bio + sources/dates (20%), concrete data - numbers + dates (20%), and extractible quotes - short paragraphs right after ## headings (15%). Returns {score, breakdown, suggestions: string[]} so the agent can advise the user where to improve the article for Google SGE / Bing Copilot / Perplexity pickup.",
    schema: SlugRefArgs,
    handler: (input) => aiOverviewReadiness(input.site_id, input.slug),
  },
  {
    name: "gridar_check_renderability",
    description:
      "Fetch a URL and detect whether it's server-rendered (SSR/SSG/prerendered) or a JavaScript SPA shell that Googlebot has to render itself. Inspects the raw HTML body and counts visible text words after stripping scripts and styles - >100 words = OK, less = suspect SPA. Returns {url, is_prerendered, html_contains_main_text, word_count, warning, suggestion}. Use this to quickly tell a user whether their site is Googlebot-friendly or needs prerendering / SSR (Next.js, Nuxt, Astro, prerender.io).",
    schema: CheckRenderabilityArgs,
    handler: (input) => checkRenderability({ url: input.url }),
  },
  {
    name: "gridar_list_strategic_opportunities",
    description:
      "List the cached strategic opportunities for a site. Each one ties a tracked keyword (transactional / commercial / local intent, no landing yet) to a structured page concept: page_type (tool_landing | service_page | comparison | guide_pillar | quiz_landing | calculator | local_landing | lead_magnet), suggested_title, suggested_url_path, the hook (the specific thing that gets the click), capture_mechanism (how the lead is captured), conversion_path (how the lead becomes a customer), the angle vs the current SERP top 5, asset_match (whether the site already has the product/feature to power the hook), asset_used name, why_this_works rationale, and a priority bucket. Each opportunity also carries a quantitative estimate: monthly_volume (Serper), estimated_visits at SERP rank 5 (CTR table * volume), estimated_leads_range and estimated_paid_range computed from the site's business_model conversion table. Status flow: proposed (waiting) -> approved (landing being generated) -> done (HostedLanding live). Call gridar_refresh_strategic_opportunities first to populate, then this to enumerate.",
    schema: ListStrategicOpportunitiesArgs,
    handler: (input) =>
      listStrategicOpportunities(input.site_id, {
        include_dismissed: input.include_dismissed,
      }),
  },
  {
    name: "gridar_refresh_strategic_opportunities",
    description:
      "Run the strategic opportunity engine for a site. For each tracked keyword whose intent is non-info (transactional / commercial / local) AND that doesn't already have a matching landing, the engine builds a structured Claude prompt with the site's business_model + description + knowledge_base + CTA + SERP top 5 + existing pages list + Niveau-2 quantitative estimate, then asks Claude to propose ONE page that capitalises on the site's existing assets to capture and convert that keyword's intent. Each accepted concept is upserted as a StrategicOpportunity row. Bounded by max_keywords (default 8, cap 20) to keep Claude cost predictable. Idempotent: re-running refreshes concepts, preserves dismissed / done statuses. Returns counts + per-keyword refresh status.",
    schema: RefreshStrategicOpportunitiesArgs,
    handler: (input) =>
      refreshStrategicOpportunities(input.site_id, {
        max_keywords: input.max_keywords,
      }),
  },
  {
    name: "gridar_action_strategic_opportunity",
    description:
      "Take action on a single strategic opportunity. 'approve' triggers the LandingGenerator to AI-generate a full HostedLanding from the concept (mapping page_type -> page_subtype, honoring the suggested_url_path slug, dedup-ing against existing slugs) and marks the opportunity done with a forward link to the new landing. 'dismiss' hides the opportunity from the proposed list (won't reappear on refresh until restored). 'restore' un-dismisses. Use approve as the natural 'just go build it' command when an opportunity looks good.",
    schema: StrategicOpportunityActionArgs,
    handler: (input) =>
      actionStrategicOpportunity(
        input.site_id,
        input.opportunity_id,
        input.action,
      ),
  },
  {
    name: "gridar_export_page_prompt",
    description:
      "Export a ready-to-paste prompt for the USER'S OWN AI coding assistant (ChatGPT, Lovable, v0, Bolt, Copilot, Gemini...). This is the delivery channel for clients who build their site with an AI tool and have no CMS Gridar can push into - their AI does the integration in their codebase, Gridar never touches their repo. Two modes: pass landing_id for an INTEGRATE prompt (the copy already exists and was keyword-calibrated - the prompt instructs the target AI to reproduce it verbatim, with exact slug, SEO meta, section structure and both JSON-LD blocks to inject as-is); or pass opportunity_id for a CREATE prompt (only the strategic concept exists - the prompt instructs the target AI to write the copy following the binding brief: hook, capture mechanism, conversion path, angle, FR-CA Quebec lexicon when the content language is French). Optional `stack` adapts the final integration instructions (nextjs, react, html, astro, wordpress, webflow, generic). Pure server-side templating: no LLM call, no quota consumed, instant. Returns {prompt, source, stack, char_count}. Typical flow: gridar_list_strategic_opportunities -> user picks one -> gridar_export_page_prompt(opportunity_id) -> hand the prompt text to the user to paste in their AI tool.",
    schema: ExportPagePromptArgs,
    handler: (input) =>
      exportPagePrompt(input.site_id, {
        landing_id: input.landing_id,
        opportunity_id: input.opportunity_id,
        stack: input.stack,
      }),
  },
  {
    name: "gridar_pull_build_queue",
    description:
      "Pull the QUEUE of pages a coding agent should create in the client's OWN repo, for a dev-built / external site Gridar cannot publish to directly (e.g. a custom Next.js app). `landings` = BRIEFS from strategic opportunities: each carries the strategic concept plus a ready-to-use `build_prompt`; YOU write the landing copy from that brief (C1). `articles` come in two modes (field `mode`): mode=`ready` = GENERATED COPY (post_id, finished keyword-calibrated title/slug/excerpt/content) that you integrate VERBATIM (C2); mode=`brief` = an informational-article BRIEF (opportunity_id, `build_prompt`) that YOU write the article from, used as a fallback when Gridar has no generated copy yet. Pure read, no LLM call, no quota. Optional `stack` (nextjs, react, html, astro, wordpress, webflow, generic) adapts the build prompts. Loop: gridar_pull_build_queue -> build each page -> gridar_mark_page_built (kind 'article' for a ready article via post_id, 'article_brief' for a brief article via opportunity_id, 'landing' for a landing). Returns {delivery_mode, landings, articles, counts, note}.",
    schema: PullBuildQueueArgs,
    handler: (input) => pullBuildQueue(input.site_id, { stack: input.stack }),
  },
  {
    name: "gridar_mark_page_built",
    description:
      "Report that a queued page from gridar_pull_build_queue is now LIVE in the client's site, so Gridar can close the delivery loop. Pass `kind`, the matching `id`, and the live `url`. kind='landing' (id=opportunity_id) and kind='article_brief' (id=opportunity_id, an article you wrote from a brief) mark the opportunity done so it archives out. kind='article' (id=post_id, a mode=ready article) stamps the delivered URL so the proof loop can attribute positions. Call it once per page after you deploy it.",
    schema: MarkPageBuiltArgs,
    handler: (input) =>
      markPageBuilt(input.site_id, {
        kind: input.kind,
        id: input.id,
        url: input.url,
      }),
  },
];

// Convert a zod schema to a JSON Schema object for the MCP tools/list response.
// We hand-roll a tiny converter to avoid pulling in zod-to-json-schema for a
// schema set this small. Each top-level schema is a strict object.
function toolToJsonSchema(schema: z.ZodTypeAny): Record<string, unknown> {
  const def = (schema as { _def: { typeName: string } })._def;
  if (def.typeName === "ZodEffects") {
    return toolToJsonSchema(
      (schema as unknown as { _def: { schema: z.ZodTypeAny } })._def.schema,
    );
  }
  if (def.typeName !== "ZodObject") {
    return { type: "object" };
  }
  const shape = (schema as z.ZodObject<z.ZodRawShape>).shape;
  const properties: Record<string, unknown> = {};
  const required: string[] = [];
  for (const [key, value] of Object.entries(shape)) {
    const field = value as z.ZodTypeAny;
    properties[key] = zodFieldToJsonSchema(field);
    if (!field.isOptional()) required.push(key);
  }
  const result: Record<string, unknown> = {
    type: "object",
    properties,
    additionalProperties: false,
  };
  if (required.length) result.required = required;
  return result;
}

function zodFieldToJsonSchema(field: z.ZodTypeAny): Record<string, unknown> {
  const def = (field as { _def: { typeName: string } })._def;
  const description = (field as { description?: string }).description;
  let base: Record<string, unknown>;

  switch (def.typeName) {
    case "ZodOptional":
      base = zodFieldToJsonSchema(
        (field as unknown as { _def: { innerType: z.ZodTypeAny } })._def
          .innerType,
      );
      break;
    case "ZodNumber":
      base = { type: "number" };
      break;
    case "ZodString":
      base = { type: "string" };
      break;
    case "ZodBoolean":
      base = { type: "boolean" };
      break;
    case "ZodEnum":
      base = {
        type: "string",
        enum: (field as unknown as { _def: { values: string[] } })._def.values,
      };
      break;
    case "ZodRecord":
      base = { type: "object" };
      break;
    case "ZodArray":
      base = {
        type: "array",
        items: zodFieldToJsonSchema(
          (field as unknown as { _def: { type: z.ZodTypeAny } })._def.type,
        ),
      };
      break;
    case "ZodObject":
      base = toolToJsonSchema(field);
      break;
    default:
      base = {};
  }
  if (description) base.description = description;
  return base;
}

// ---------------------------------------------------------------------------
// Server factory (exported so the HTTP transport in src/http.ts can reuse it)
// ---------------------------------------------------------------------------

export { tools, toolToJsonSchema };

/** Build a fresh MCP Server wired with the Gridar tools. */
export function createMcpServer(): Server {
  const server = new Server(
    {
      name: "gridar-mcp",
      version: "0.7.0",
    },
    {
      capabilities: { tools: {} },
    },
  );

  server.setRequestHandler(ListToolsRequestSchema, async () => ({
    tools: tools.map((t) => ({
      name: t.name,
      description: t.description,
      inputSchema: toolToJsonSchema(t.schema),
    })),
  }));

  server.setRequestHandler(CallToolRequestSchema, async (req) => {
    const tool = tools.find((t) => t.name === req.params.name);
    if (!tool) {
      return {
        content: [
          { type: "text", text: `Unknown tool: ${req.params.name}` },
        ],
        isError: true,
      };
    }

    const parsed = tool.schema.safeParse(req.params.arguments ?? {});
    if (!parsed.success) {
      return {
        content: [
          {
            type: "text",
            text: `Invalid arguments for ${tool.name}:\n${parsed.error.issues
              .map((i) => `- ${i.path.join(".") || "(root)"}: ${i.message}`)
              .join("\n")}`,
          },
        ],
        isError: true,
      };
    }

    try {
      const result = await tool.handler(parsed.data);
      return {
        content: [
          {
            type: "text",
            text: JSON.stringify(result, null, 2),
          },
        ],
      };
    } catch (err) {
      if (err instanceof ApiError) {
        return {
          content: [
            {
              type: "text",
              text: `Gridar API error (HTTP ${err.status}): ${err.message}\n\n${JSON.stringify(err.body ?? {}, null, 2)}`,
            },
          ],
          isError: true,
        };
      }
      const message = err instanceof Error ? err.message : String(err);
      return {
        content: [{ type: "text", text: `Unexpected error: ${message}` }],
        isError: true,
      };
    }
  });

  return server;
}

// ---------------------------------------------------------------------------
// Stdio entry: runs when this file is invoked directly (npx, node dist/index.js).
// Guarded so http.ts can `import` from this module without triggering stdio.
// ---------------------------------------------------------------------------
const invokedPath = (process.argv[1] ?? "").replace(/\\/g, "/");
const isStdioEntry =
  invokedPath.endsWith("/dist/index.js") ||
  invokedPath.endsWith("/src/index.ts") ||
  invokedPath.endsWith("/gridar-mcp") ||
  invokedPath.endsWith("\\gridar-mcp");

if (isStdioEntry) {
  const server = createMcpServer();
  const transport = new StdioServerTransport();
  await server.connect(transport);
  // eslint-disable-next-line no-console
  console.error("[gridar-mcp] connected (stdio)");
}
