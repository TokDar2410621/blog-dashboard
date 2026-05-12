/**
 * Static blog post loader for Gridar.
 *
 * Markdown files live in `/posts/*.md` at the repo root. Each starts with
 * a YAML-style frontmatter block we parse with a tiny regex (no need for
 * gray-matter - the format is under our control). Vite's import.meta.glob
 * bundles every file at build time so the SPA serves them with zero
 * backend round-trip.
 */

const postFiles = import.meta.glob("../../posts/**/*.md", {
  query: "?raw",
  import: "default",
  eager: true,
}) as Record<string, string>;

export type PostMeta = {
  slug: string;
  title: string;
  excerpt: string;
  date: string;
  author?: string;
  tags?: string[];
  cover_image?: string;
};

export type Post = PostMeta & {
  body: string;
};

function parseFrontmatter(raw: string): { meta: Record<string, string | string[]>; body: string } {
  const m = raw.match(/^---\s*\n([\s\S]*?)\n---\s*\n?([\s\S]*)$/);
  if (!m) return { meta: {}, body: raw };
  const meta: Record<string, string | string[]> = {};
  for (const line of m[1].split("\n")) {
    const colonAt = line.indexOf(":");
    if (colonAt === -1) continue;
    const key = line.slice(0, colonAt).trim();
    let value = line.slice(colonAt + 1).trim();
    // Strip surrounding quotes
    if (
      (value.startsWith('"') && value.endsWith('"')) ||
      (value.startsWith("'") && value.endsWith("'"))
    ) {
      value = value.slice(1, -1);
    }
    // YAML-flow arrays: [foo, bar]
    if (value.startsWith("[") && value.endsWith("]")) {
      meta[key] = value
        .slice(1, -1)
        .split(",")
        .map((s) => s.trim().replace(/^["']|["']$/g, ""))
        .filter(Boolean);
    } else {
      meta[key] = value;
    }
  }
  return { meta, body: m[2] };
}

function pathToSlug(p: string): string {
  return p.replace("../../posts/", "").replace(/\.md$/, "");
}

let cache: Post[] | null = null;

export function getAllPosts(): Post[] {
  if (cache) return cache;
  const list: Post[] = [];
  for (const [path, raw] of Object.entries(postFiles)) {
    const slug = pathToSlug(path);
    const { meta, body } = parseFrontmatter(raw);
    list.push({
      slug,
      title: (meta.title as string) || slug,
      excerpt: (meta.excerpt as string) || "",
      date: (meta.date as string) || "",
      author: meta.author as string | undefined,
      tags: meta.tags as string[] | undefined,
      cover_image: meta.cover_image as string | undefined,
      body,
    });
  }
  // Most recent first.
  list.sort((a, b) => (a.date < b.date ? 1 : -1));
  cache = list;
  return list;
}

export function getPost(slug: string): Post | undefined {
  return getAllPosts().find((p) => p.slug === slug);
}

/** Build the markdown reading time (avg 200 wpm). */
export function readingTime(body: string): number {
  const words = body.trim().split(/\s+/).length;
  return Math.max(1, Math.round(words / 200));
}
