// --- Post statuses ---
export const POST_STATUS = {
  DRAFT: "draft",
  PUBLISHED: "published",
  SCHEDULED: "scheduled",
} as const;

export type PostStatus = (typeof POST_STATUS)[keyof typeof POST_STATUS];

export const POST_STATUS_VARIANT: Record<PostStatus, "default" | "secondary" | "outline" | "destructive"> = {
  [POST_STATUS.PUBLISHED]: "default",
  [POST_STATUS.DRAFT]: "secondary",
  [POST_STATUS.SCHEDULED]: "outline",
};

// --- Article types (AI generator) ---
export const ARTICLE_TYPE = {
  NEWS: "news",
  TUTORIAL: "tutorial",
  COMPARISON: "comparison",
  GUIDE: "guide",
  REVIEW: "review",
  STORY: "story",
  LOCAL: "local",
} as const;

export type ArticleType = (typeof ARTICLE_TYPE)[keyof typeof ARTICLE_TYPE];

// --- Article lengths ---
export const ARTICLE_LENGTH = {
  SHORT: "short",
  MEDIUM: "medium",
  LONG: "long",
} as const;

export type ArticleLength = (typeof ARTICLE_LENGTH)[keyof typeof ARTICLE_LENGTH];

// --- Search methods ---
export const SEARCH_METHOD = {
  SERPER: "serper",
  GEMINI: "gemini",
} as const;

export type SearchMethod = (typeof SEARCH_METHOD)[keyof typeof SEARCH_METHOD];

// --- Template types ---
export const TEMPLATE_TYPE = {
  MARKDOWN: "markdown",
  VISUAL: "visual",
  AI: "ai",
} as const;

export type TemplateType = (typeof TEMPLATE_TYPE)[keyof typeof TEMPLATE_TYPE];

// --- Query params ---
export const QUERY_PARAM = {
  TPL_TYPE: "tpl_type",
  TPL_ID: "tpl_id",
} as const;

// --- React Query keys ---
export const QK = {
  SITES: ["sites"] as const,
  site: (id: number) => ["site", id] as const,
  DASHBOARD: {
    stats: (siteId: number) => ["dashboard", "stats", siteId] as const,
    posts: (siteId: number, page?: number) =>
      page !== undefined
        ? (["dashboard", "posts", siteId, page] as const)
        : (["dashboard", "posts", siteId] as const),
    post: (siteId: number, slug: string) => ["dashboard", "post", siteId, slug] as const,
    categories: (siteId: number) => ["dashboard", "categories", siteId] as const,
    tags: (siteId: number) => ["dashboard", "tags", siteId] as const,
    images: (siteId: number) => ["dashboard", "images", siteId] as const,
  },
} as const;

// --- Stale times ---
export const STALE_TIME = {
  SITES: 1000 * 60 * 5,
  STATS: 1000 * 60 * 2,
  POSTS: 1000 * 60,
  CATEGORIES: 1000 * 60 * 10,
  TAGS: 1000 * 60 * 10,
  IMAGES: 1000 * 60 * 2,
} as const;

// --- Local storage keys ---
export const LS_KEY = {
  TOKEN: "blog_dashboard_token",
  REFRESH: "blog_dashboard_refresh",
  ACTIVE_SITE: "blog_dashboard_active_site_id",
} as const;
