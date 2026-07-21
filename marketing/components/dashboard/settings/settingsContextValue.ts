import { createContext } from "react";
import type { useMutation, useQuery } from "@tanstack/react-query";
import type { useSite, useUpdateSite } from "@/hooks/useDashboard";

export type MemoryRow = {
  id: number;
  kind: string;
  title: string;
  content_preview: string;
  token_count: number;
  source_ref: string;
  has_embedding: boolean;
  updated_at: string;
};
export type MemoriesResponse = {
  memories: MemoryRow[];
  counts_by_kind: Record<string, number>;
  sources_by_kind?: Record<string, number>;
  total: number;
};
export type ProvisionResult = {
  domain: string;
  verified: boolean;
  cname_target: string;
  next_step: string;
};

export type ScannedMeta = {
  site_name?: string;
  brand_color?: string;
  font_sans?: string;
  logo_url?: string;
} | null;

export type SettingsContextValue = {
  siteId: string | undefined;
  site: ReturnType<typeof useSite>["data"];
  isLoading: boolean;
  updateSite: ReturnType<typeof useUpdateSite>;

  // General
  name: string; setName: (v: string) => void;
  domain: string; setDomain: (v: string) => void;
  description: string; setDescription: (v: string) => void;
  businessModel: string; setBusinessModel: (v: string) => void;
  deliveryMode: string; setDeliveryMode: (v: string) => void;

  // CTA
  primaryCtaText: string; setPrimaryCtaText: (v: string) => void;
  primaryCtaUrl: string; setPrimaryCtaUrl: (v: string) => void;

  // Languages
  availableLanguages: string[]; toggleLanguage: (code: string) => void;
  defaultLanguage: string; setDefaultLanguage: (v: string) => void;

  // Author / default
  defaultAuthor: string; setDefaultAuthor: (v: string) => void;
  authorRole: string; setAuthorRole: (v: string) => void;
  authorBio: string; setAuthorBio: (v: string) => void;
  authorCredentials: string; setAuthorCredentials: (v: string) => void;
  authorImageUrl: string; setAuthorImageUrl: (v: string) => void;
  authorLinkedin: string; setAuthorLinkedin: (v: string) => void;
  authorTwitter: string; setAuthorTwitter: (v: string) => void;
  authorWebsite: string; setAuthorWebsite: (v: string) => void;

  // Branding
  ogImageUrl: string; setOgImageUrl: (v: string) => void;
  brandColor: string; setBrandColor: (v: string) => void;
  brandFg: string; setBrandFg: (v: string) => void;
  logoUrl: string; setLogoUrl: (v: string) => void;
  scannedMeta: ScannedMeta;
  scanBranding: ReturnType<typeof useMutation<unknown, Error, void>>;

  // GSC
  gscPropertyUrl: string; setGscPropertyUrl: (v: string) => void;
  gscConnecting: boolean;
  gscConnected: boolean;
  gscDisconnecting: boolean;
  handleConnectGsc: () => Promise<void>;
  handleDisconnectGsc: () => Promise<void>;

  // Integrations
  vercelDeployHook: string; setVercelDeployHook: (v: string) => void;
  knowledgeBase: string; setKnowledgeBase: (v: string) => void;
  competitors: string; setCompetitors: (v: string) => void;
  suggestCompetitors: ReturnType<typeof useMutation<{ competitors: string[] }, Error, void>>;

  // Public blog
  publicBlogDomain: string; setPublicBlogDomain: (v: string) => void;
  provisionResult: ProvisionResult | null;
  domainVerified: boolean;
  provisionDomain: ReturnType<typeof useMutation<ProvisionResult, Error, string>>;
  removeDomain: ReturnType<typeof useMutation<void, Error, void>>;

  // Memory
  manualNote: string; setManualNote: (v: string) => void;
  manualNoteTitle: string; setManualNoteTitle: (v: string) => void;
  memoriesQuery: ReturnType<typeof useQuery<MemoriesResponse>>;
  rebuildMemory: ReturnType<typeof useMutation<{ articles_processed: number; articles_errors: Array<{ slug: string; error: string }>; total_memories: number }, Error, boolean>>;
  addManualNote: ReturnType<typeof useMutation<unknown, Error, void>>;
  deleteMemory: ReturnType<typeof useMutation<void, Error, number>>;

  // Save
  handleSave: () => Promise<void>;
};

export const SettingsContext = createContext<SettingsContextValue | null>(null);
