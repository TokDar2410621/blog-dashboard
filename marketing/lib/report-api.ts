/**
 * Public shareable audit report API client (Server Component).
 *
 * Backend endpoint: GET /api/public/report/<token>/
 * No auth, IP-throttled. Backs the gridar.app/rapport/<token> page - the
 * shareable, permanent version of a public audit (the /audit endpoint itself
 * only caches by domain for 1h).
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || "https://api.gridar.app";
const REVALIDATE_SECONDS = 3600;

export type PublicReport = {
  domain: string;
  audited_at: string | null;
  composite_score: number | null;
  pagespeed: {
    performance?: number;
    seo?: number;
    accessibility?: number;
    avg?: number;
    error?: string;
  };
  crawl: {
    title?: string;
    h1?: string;
    meta_description?: string;
    error?: string;
  };
  top_keywords_estimated: { keyword: string; position: number | null }[];
  recos_partial: { severity: "high" | "medium" | "low"; message: string }[];
  report_token: string;
};

export async function fetchPublicReport(token: string): Promise<PublicReport | null> {
  const res = await fetch(`${API_URL}/api/public/report/${encodeURIComponent(token)}/`, {
    next: { revalidate: REVALIDATE_SECONDS },
  });
  if (res.status === 404 || res.status === 410) return null;
  if (!res.ok) {
    throw new Error(`Public report fetch failed: ${res.status}`);
  }
  return res.json();
}
