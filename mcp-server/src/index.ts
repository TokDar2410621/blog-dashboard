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
  auditArticle,
  generateArticle,
  getArticle,
  getBrief,
  getMe,
  getWeeklyDigest,
  listArticles,
  listKeywords,
  listSites,
  snapshotKeywords,
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
// Server wiring
// ---------------------------------------------------------------------------

const server = new Server(
  {
    name: "gridar-mcp",
    version: "0.1.0",
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

const transport = new StdioServerTransport();
await server.connect(transport);

// eslint-disable-next-line no-console
console.error("[gridar-mcp] connected (stdio)");
