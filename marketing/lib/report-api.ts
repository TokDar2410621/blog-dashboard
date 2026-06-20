/**
 * Public shareable audit report API client (Server Component).
 *
 * Backend endpoint: GET /api/public/report/<token>/
 * No auth, IP-throttled. Backs the gridar.app/rapport/<token> page - the
 * shareable, permanent version of a public audit (the /audit endpoint itself
 * only caches by domain for 1h).
 */

import type { FullReport } from "@/components/audit/FullReportSections";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "https://api.gridar.app";

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
  // Present once a lead has been captured for this audit. The enrichment
  // (competitors, untapped keywords, schema, CWV, decay, article plan,
  // backlinks) is persisted on the report payload server-side.
  full_report_gated?: boolean;
  full_report?: FullReport;
};

export async function fetchPublicReport(token: string): Promise<PublicReport | null> {
  // No caching: a report flips from "gated" to "enriched" at lead-capture time,
  // so a cached pre-capture snapshot would leave the share page (and the J+0
  // email link) showing an empty report. Always read the current state.
  const res = await fetch(`${API_URL}/api/public/report/${encodeURIComponent(token)}/`, {
    cache: "no-store",
  });
  if (res.status === 404 || res.status === 410) return null;
  if (!res.ok) {
    throw new Error(`Public report fetch failed: ${res.status}`);
  }
  return res.json();
}
