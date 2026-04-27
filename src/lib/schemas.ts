import { z } from "zod/v4";

// --- Auth ---
export const loginResponseSchema = z.object({
  access: z.string(),
  refresh: z.string(),
});
export type LoginResponse = z.infer<typeof loginResponseSchema>;

export const userSchema = z.object({
  username: z.string(),
  email: z.string(),
});
export type User = z.infer<typeof userSchema>;

// --- Site ---
export const siteSchema = z.object({
  id: z.number(),
  name: z.string(),
  domain: z.string(),
  database_url: z.string().optional(),
  knowledge_base: z.string().optional(),
  vercel_deploy_hook: z.string().optional(),
  gsc_property_url: z.string().optional(),
  api_key: z.string().optional(),
  is_hosted: z.boolean().optional(),
  is_active: z.boolean().optional(),
  description: z.string().optional(),
  og_image_url: z.string().optional(),
  default_author: z.string().optional(),
  default_language: z.string().optional(),
  available_languages: z.array(z.string()).nullable().optional(),
  blog_config: z.record(z.string(), z.unknown()).nullable().optional(),
  created_at: z.string(),
  updated_at: z.string().optional(),
});
export type Site = z.infer<typeof siteSchema>;

// --- Post ---
export const postListItemSchema = z.object({
  slug: z.string(),
  title: z.string(),
  status: z.string(),
  category: z.string().nullable().optional(),
  view_count: z.number().optional().default(0),
  created_at: z.string(),
  cover_image: z.string().nullable().optional(),
  featured: z.boolean().optional().default(false),
  language: z.string().optional().default("fr"),
  translation_group: z.string().optional(),
});
export type PostListItem = z.infer<typeof postListItemSchema>;

export const postDetailSchema = postListItemSchema.extend({
  excerpt: z.string().optional().default(""),
  content: z.string().optional().default(""),
  tags: z.array(z.string()).optional().default([]),
  author: z.string().nullable().optional(),
  reading_time: z.number().nullable().optional(),
  scheduled_at: z.string().nullable().optional(),
  published_at: z.string().nullable().optional(),
});
export type PostDetail = z.infer<typeof postDetailSchema>;

export const paginatedPostsSchema = z.object({
  count: z.number(),
  results: z.array(postListItemSchema),
  next: z.number().nullable(),
  previous: z.number().nullable(),
});
export type PaginatedPosts = z.infer<typeof paginatedPostsSchema>;

// --- Category ---
export const categorySchema = z.object({
  slug: z.string(),
  name: z.string(),
});
export type Category = z.infer<typeof categorySchema>;

// --- Tag ---
export const tagSchema = z.object({
  name: z.string(),
});
export type Tag = z.infer<typeof tagSchema>;

// --- Dashboard Stats ---
export const dashboardStatsSchema = z.object({
  total_posts: z.number(),
  total_views: z.number(),
  drafts: z.number(),
  scheduled: z.number(),
  published: z.number(),
  categories: z.array(z.object({ name: z.string(), count: z.number() })),
  recent_posts: z.array(postListItemSchema),
});
export type DashboardStats = z.infer<typeof dashboardStatsSchema>;

// --- Images ---
export const imageSchema = z.object({
  uid: z.string(),
  filename: z.string(),
  mime_type: z.string(),
  url: z.string().optional(),
  created_at: z.string().optional(),
});
export type Image = z.infer<typeof imageSchema>;

// --- AI Generation ---
export const generateArticleResponseSchema = z.object({
  output: z.string(),
  post_count: z.number(),
});
export type GenerateArticleResponse = z.infer<typeof generateArticleResponseSchema>;

export const generateImageResponseSchema = z.object({
  image: z.string(),
  mime_type: z.string(),
  image_url: z.string(),
});
export type GenerateImageResponse = z.infer<typeof generateImageResponseSchema>;

// --- SEO ---
export const seoSuggestionsSchema = z.object({
  meta_descriptions: z.array(z.string()),
  title_suggestions: z.array(z.string()),
  keywords: z.array(z.string()),
});
export type SEOSuggestions = z.infer<typeof seoSuggestionsSchema>;

// --- Pexels ---
export const pexelsPhotoSchema = z.object({
  id: z.number(),
  url: z.string(),
  thumb: z.string(),
  alt: z.string(),
  photographer: z.string(),
});
export type PexelsPhoto = z.infer<typeof pexelsPhotoSchema>;

export const pexelsResponseSchema = z.object({
  photos: z.array(pexelsPhotoSchema),
  total_results: z.number(),
  page: z.number().optional(),
  per_page: z.number().optional(),
});
export type PexelsResponse = z.infer<typeof pexelsResponseSchema>;
