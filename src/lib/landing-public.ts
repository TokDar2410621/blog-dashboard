/**
 * Public HostedLanding fetcher for the Vite SPA.
 *
 * Backend: GET /api/public/sites/<id>/landings/<slug>/
 * No auth, IP throttled by AnonRateThrottle on the backend.
 *
 * Used by src/pages/HostedLandingPage.tsx (catch-all route in App.tsx)
 * to render a landing at the site root (e.g. gridar.app/audit-seo-gratuit-quebec).
 */

const API_BASE = import.meta.env.VITE_API_URL || "/api";
const GRIDAR_SITE_ID = Number(import.meta.env.VITE_GRIDAR_SITE_ID || 6);

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

export type SocialProofItem = {
  type?: "testimonial" | "logo" | "stat";
  [key: string]: unknown;
};

export type PublicLanding = {
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
  schema_type:
    | "WebPage"
    | "Service"
    | "Product"
    | "LocalBusiness"
    | "FAQPage"
    | "Article";
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

export async function fetchPublicLanding(
  slug: string,
): Promise<PublicLanding | null> {
  const url = `${API_BASE}/public/sites/${GRIDAR_SITE_ID}/landings/${slug}/`;
  const res = await fetch(url, { credentials: "omit" });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`landing ${slug} failed: HTTP ${res.status}`);
  return (await res.json()) as PublicLanding;
}
