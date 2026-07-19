/**
 * Public proof API client (Server Component).
 *
 * Backend endpoint: GET /api/public/proof/<token>/
 * No auth, IP-throttled (60 req/h on the backend).
 *
 * Uses Next.js ISR with a 1h revalidate window: the page rebuilds at most
 * every hour, which is plenty given the backend cron only refreshes
 * attribution snapshots once per day.
 */

const API_URL = process.env.NEXT_PUBLIC_API_URL || "https://api.gridar.app";
const REVALIDATE_SECONDS = 3600;

export type ProofQueryRow = {
  query: string;
  impressions: number;
  clicks: number;
  position: number | null;
};

export type ProofTopGainer = {
  post_id: number;
  title: string;
  slug: string;
  horizon: 30 | 60 | 90;
  impressions_gained: number;
  clicks_gained: number;
  top_queries: ProofQueryRow[];
};

// Complete per-post row: winners AND flops. The public proof page renders the
// full list, so `impressions_gained` can be zero or negative.
export type ProofPostRow = ProofTopGainer & {
  indexed: boolean;
  published_at: string | null;
};

export type ProofPublicSummary = {
  site_id: number;
  site_name: string;
  domain?: string;
  posts_with_attribution: number;
  total_impressions_gained: number;
  total_clicks_gained: number;
  // Complete list (flops included) - what the public page must show.
  posts: ProofPostRow[];
  // Winners only, for the owner's dashboard highlight.
  top_gainers: ProofTopGainer[];
};

export async function fetchPublicProof(token: string): Promise<ProofPublicSummary | null> {
  const res = await fetch(`${API_URL}/api/public/proof/${encodeURIComponent(token)}/`, {
    next: { revalidate: REVALIDATE_SECONDS },
  });
  if (res.status === 404 || res.status === 410) return null;
  if (!res.ok) {
    throw new Error(`Public proof fetch failed: ${res.status}`);
  }
  return res.json();
}
