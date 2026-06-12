import { authFetch } from "./api-client";

// Billing types mirrored from the SPA (src/pages/Billing.tsx). The backend
// endpoints live under /api/billing/* and are reached through the same
// authFetch helper (same-origin /api base + Bearer/cookie auth + refresh).

export type Subscription = {
  plan: "free" | "solo" | "pro" | "agency";
  status: string;
  is_paid: boolean;
  current_period_end: string | null;
  cancel_at_period_end: boolean;
  limits: {
    sites_max: number;
    articles_per_month: number | null;
    keywords_max: number;
  };
  usage?: {
    articles_this_month: number;
    month_key: string;
  };
  credits?: {
    balance: number;
  };
};

export type CreditPack = {
  key: "small" | "medium" | "large";
  credits: number;
  price_cad: number;
  label: string;
};

export type CreditTransaction = {
  amount: number;
  kind: "purchase" | "spend" | "refund" | "gift";
  description: string;
  created_at: string;
};

export type CreditsResponse = {
  balance: number;
  transactions: CreditTransaction[];
  packs: CreditPack[];
};

/** Current subscription state (plan, status, limits, usage, credit balance). */
export async function fetchBillingMe(): Promise<Subscription> {
  const res = await authFetch("/billing/me/");
  if (!res.ok) throw new Error("billing fetch failed");
  return res.json();
}

/** Credit balance + recent transactions + purchasable packs. */
export async function fetchBillingCredits(): Promise<CreditsResponse> {
  const res = await authFetch("/billing/credits/");
  if (!res.ok) throw new Error("credits fetch failed");
  return res.json();
}

/** Start a Stripe Checkout session for a credits pack. Returns the URL to
 *  redirect the browser to. Throws with the backend `error` message on
 *  failure (or a generic French fallback, same as the SPA). */
export async function buyCreditsPack(pack: CreditPack["key"]): Promise<string> {
  const res = await authFetch("/billing/credits/buy/", {
    method: "POST",
    body: JSON.stringify({ pack }),
  });
  const data = await res.json();
  if (!res.ok || !data.url) {
    throw new Error(data.error || "Erreur achat");
  }
  return data.url as string;
}

/** Start a Stripe Checkout session for a subscription plan. Returns the
 *  redirect URL. */
export async function createCheckoutSession(
  plan: "solo" | "pro" | "agency",
): Promise<string> {
  const res = await authFetch("/billing/checkout/", {
    method: "POST",
    body: JSON.stringify({ plan }),
  });
  const data = await res.json();
  if (!res.ok || !data.url) {
    throw new Error(data.error || "Erreur checkout");
  }
  return data.url as string;
}

/** Open the Stripe customer portal (manage/cancel subscription, invoices).
 *  Returns the redirect URL. */
export async function createPortalSession(): Promise<string> {
  const res = await authFetch("/billing/portal/", { method: "POST" });
  const data = await res.json();
  if (!res.ok || !data.url) {
    throw new Error(data.error || "Erreur portail");
  }
  return data.url as string;
}
