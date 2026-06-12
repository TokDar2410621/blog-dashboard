import { authFetch } from "./api-client";

// Account API tokens (Bearer btb_ tokens for n8n / Zapier / Make / scripts).
// Mirrors the SPA's inline fetches in src/pages/ApiKeys.tsx, kept in a
// dedicated lib file so api-client.ts stays untouched.

export type ApiToken = {
  id: number;
  name: string;
  prefix: string;
  last_used_at: string | null;
  revoked_at: string | null;
  created_at: string;
  is_active: boolean;
};

export type CreatedApiToken = ApiToken & { token: string; message: string };

export async function listApiTokens(): Promise<{ results: ApiToken[] }> {
  const res = await authFetch("/account/api-tokens/");
  if (!res.ok) throw new Error("Impossible de charger les tokens.");
  return res.json();
}

export async function createApiToken(name: string): Promise<CreatedApiToken> {
  const res = await authFetch("/account/api-tokens/", {
    method: "POST",
    body: JSON.stringify({ name }),
  });
  const data = await res.json();
  if (!res.ok) throw new Error(data.error || "Erreur création.");
  return data;
}

export async function revokeApiToken(id: number): Promise<void> {
  const res = await authFetch(`/account/api-tokens/${id}/`, {
    method: "DELETE",
  });
  if (!res.ok && res.status !== 204) {
    const d = await res.json().catch(() => ({}));
    throw new Error(d.error || "Erreur révocation.");
  }
}
