/**
 * Public landing API client (Server Component).
 *
 * Backend endpoint: GET /api/public/sites/<id>/landings/<slug>/
 *
 * Used by the catch-all marketing route at `app/[slug]/page.tsx` to render
 * a HostedLanding at the site root (e.g. gridar.app/audit-seo-gratuit-quebec).
 * Uses Next.js ISR with a 1h revalidate so editorial updates propagate
 * within the hour without a redeploy.
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || "https://api.gridar.app";
const GRIDAR_SITE_ID = Number(process.env.NEXT_PUBLIC_GRIDAR_SITE_ID || 6);
// Short revalidate so a newly published landing (or a slug fetched as 404
// before it existed) surfaces within minutes instead of staying cached for an
// hour. Landings are pre-rendered via generateStaticParams at build; this only
// governs the between-build refresh window.
const REVALIDATE_SECONDS = 300;

export const LANDING_SITE_ID = GRIDAR_SITE_ID;

export type ValueProp = {
  icon: string;
  title: string;
  description: string;
};

export type FaqItem = {
  question: string;
  answer: string;
};

// A social-proof entry is either a plain string (e.g. "Conçu au Saguenay ...")
// or a structured object. The renderer normalizes both to a display string.
export type SocialProofItem =
  | string
  | {
      type?: "testimonial" | "logo" | "stat";
      text?: string;
      label?: string;
      title?: string;
      value?: string;
      [key: string]: unknown;
    };

export type Landing = {
  id: number;
  title: string;
  slug: string;
  h1: string;
  hero_subtitle: string;
  hero_cta_text: string;
  hero_cta_url: string;
  value_props: ValueProp[];
  social_proof: SocialProofItem[];
  faq: FaqItem[];
  cta_bottom_text: string;
  cta_bottom_url: string;
  body_markdown: string;
  target_keyword: string;
  schema_type: "WebPage" | "Service" | "Product" | "LocalBusiness" | "FAQPage" | "Article";
  page_subtype: string;
  language: string;
  translation_group: string;
  cover_image: string;
  meta_description: string;
  schema_jsonld: Record<string, unknown>;
  published_at: string | null;
  created_at: string;
  updated_at: string;
};

export type LandingListItem = {
  slug: string;
  language: string;
  updated_at: string;
};

export async function getLanding(slug: string): Promise<Landing | null> {
  const url = `${API_URL}/api/public/sites/${GRIDAR_SITE_ID}/landings/${slug}/`;
  const res = await fetch(url, {
    next: { revalidate: REVALIDATE_SECONDS, tags: [`landing:${slug}`] },
  });
  if (res.status === 404) return null;
  if (!res.ok) {
    // Surface non-404 errors so build doesn't silently miss bad responses.
    throw new Error(`getLanding(${slug}) failed: HTTP ${res.status}`);
  }
  return (await res.json()) as Landing;
}

export async function listLandings(): Promise<LandingListItem[]> {
  const url = `${API_URL}/api/public/sites/${GRIDAR_SITE_ID}/landings/`;
  const res = await fetch(url, {
    next: { revalidate: REVALIDATE_SECONDS, tags: ["landings:index"] },
  });
  if (!res.ok) return [];
  const data = (await res.json()) as { results: LandingListItem[]; count: number };
  return data.results || [];
}
