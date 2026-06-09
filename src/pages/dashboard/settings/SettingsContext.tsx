import { useEffect, useState, ReactNode } from "react";
import { useParams } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useSite, useUpdateSite } from "@/hooks/useDashboard";
import { authFetch, fetchGSCOAuthUrl, ApiError } from "@/lib/api-client";
import { toast } from "sonner";
import {
  SettingsContext,
  type MemoriesResponse,
  type ProvisionResult,
  type ScannedMeta,
  type SettingsContextValue,
} from "./settingsContext";

export function SettingsProvider({ children }: { children: ReactNode }) {
  const { t } = useTranslation();
  const { siteId } = useParams<{ siteId: string }>();
  const { data: site, isLoading } = useSite();
  const updateSite = useUpdateSite();

  // General
  const [name, setName] = useState("");
  const [domain, setDomain] = useState("");
  const [description, setDescription] = useState("");
  const [businessModel, setBusinessModel] = useState<string>("personal_blog");

  // CTA
  const [primaryCtaText, setPrimaryCtaText] = useState("");
  const [primaryCtaUrl, setPrimaryCtaUrl] = useState("");

  // Languages
  const [availableLanguages, setAvailableLanguages] = useState<string[]>([]);
  const [defaultLanguage, setDefaultLanguage] = useState<string>("fr");

  // Author / default
  const [defaultAuthor, setDefaultAuthor] = useState("");
  const [authorRole, setAuthorRole] = useState("");
  const [authorBio, setAuthorBio] = useState("");
  const [authorCredentials, setAuthorCredentials] = useState("");
  const [authorImageUrl, setAuthorImageUrl] = useState("");
  const [authorLinkedin, setAuthorLinkedin] = useState("");
  const [authorTwitter, setAuthorTwitter] = useState("");
  const [authorWebsite, setAuthorWebsite] = useState("");

  // Branding
  const [ogImageUrl, setOgImageUrl] = useState("");
  const [brandColor, setBrandColor] = useState("");
  const [brandFg, setBrandFg] = useState("");
  const [logoUrl, setLogoUrl] = useState("");
  const [scannedMeta, setScannedMeta] = useState<ScannedMeta>(null);

  // GSC
  const [gscPropertyUrl, setGscPropertyUrl] = useState("");
  const [gscConnecting, setGscConnecting] = useState(false);

  // Integrations
  const [vercelDeployHook, setVercelDeployHook] = useState("");
  const [knowledgeBase, setKnowledgeBase] = useState("");
  const [competitors, setCompetitors] = useState("");

  // Public blog
  const [publicBlogDomain, setPublicBlogDomain] = useState("");
  const [provisionResult, setProvisionResult] = useState<ProvisionResult | null>(null);
  const [domainVerified, setDomainVerified] = useState<boolean>(false);

  // Memory
  const [manualNote, setManualNote] = useState("");
  const [manualNoteTitle, setManualNoteTitle] = useState("");

  useEffect(() => {
    if (site) {
      setName(site.name || "");
      setDomain(site.domain || "");
      setKnowledgeBase(site.knowledge_base || "");
      setCompetitors(site.competitors || "");
      setVercelDeployHook(site.vercel_deploy_hook || "");
      setGscPropertyUrl(site.gsc_property_url || "");
      setAvailableLanguages(site.available_languages || []);
      setDescription(site.description || "");
      setOgImageUrl(site.og_image_url || "");
      setDefaultAuthor(site.default_author || "");
      setDefaultLanguage(site.default_language || "fr");
      setBusinessModel(site.business_model || "personal_blog");
      setAuthorRole(site.author_role || "");
      setAuthorBio(site.author_bio || "");
      setAuthorCredentials(site.author_credentials || "");
      setAuthorImageUrl(site.author_image_url || "");
      setAuthorLinkedin(site.author_linkedin || "");
      setAuthorTwitter(site.author_twitter || "");
      setAuthorWebsite(site.author_website || "");
      setPrimaryCtaText(site.primary_cta_text || "");
      setPrimaryCtaUrl(site.primary_cta_url || "");
      setPublicBlogDomain(site.public_blog_domain || "");
      const tc = (site as { theme_config?: Record<string, string> }).theme_config || {};
      setBrandColor(tc.brand_color || "");
      setBrandFg(tc.brand_fg || "");
      setLogoUrl(tc.logo_url || "");
    }
  }, [site]);

  const toggleLanguage = (code: string) => {
    setAvailableLanguages((prev) =>
      prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code]
    );
  };

  // --- Memory queries / mutations ---
  const memoriesQuery = useQuery<MemoriesResponse>({
    queryKey: ["site-memories", siteId],
    enabled: !!siteId,
    queryFn: async () => {
      const res = await authFetch(`/sites/${siteId}/memories/`);
      if (!res.ok) throw new Error("Erreur chargement memoires");
      return res.json();
    },
  });

  const rebuildMemory = useMutation({
    mutationFn: async (wipe: boolean) => {
      const res = await authFetch(`/sites/${siteId}/memories/rebuild/`, {
        method: "POST",
        body: JSON.stringify({ wipe }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error || "Erreur reindexation");
      }
      return res.json() as Promise<{
        articles_processed: number;
        articles_errors: Array<{ slug: string; error: string }>;
        total_memories: number;
      }>;
    },
    onSuccess: (data) => {
      toast.success(
        `Reindexation OK : ${data.articles_processed} articles, ${data.total_memories} memoires totales`
      );
      if (data.articles_errors?.length) {
        toast.error(`${data.articles_errors.length} erreurs (voir admin)`);
      }
      memoriesQuery.refetch();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const addManualNote = useMutation({
    mutationFn: async () => {
      const res = await authFetch(`/sites/${siteId}/memories/`, {
        method: "POST",
        body: JSON.stringify({
          content: manualNote,
          title: manualNoteTitle,
          kind: "manual",
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error || "Erreur ajout note");
      }
      return res.json();
    },
    onSuccess: () => {
      toast.success("Note ajoutee a la memoire du site.");
      setManualNote("");
      setManualNoteTitle("");
      memoriesQuery.refetch();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const deleteMemory = useMutation({
    mutationFn: async (memoryId: number) => {
      const res = await authFetch(`/sites/${siteId}/memories/${memoryId}/`, {
        method: "DELETE",
      });
      if (!res.ok) throw new Error("Erreur suppression");
    },
    onSuccess: () => {
      toast.success("Memoire supprimee");
      memoriesQuery.refetch();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  // --- Public blog provision ---
  const provisionDomain = useMutation({
    mutationFn: async (d: string) => {
      const res = await authFetch(`/sites/${siteId}/blog-domain/provision/`, {
        method: "POST",
        body: JSON.stringify({ domain: d }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error || "Erreur provision");
      }
      return res.json() as Promise<ProvisionResult>;
    },
    onSuccess: (data) => {
      setProvisionResult(data);
      setDomainVerified(data.verified);
      toast.success(
        data.verified
          ? "Domaine déjà vérifié - blog en ligne."
          : "Domaine enregistré. Suis les instructions DNS ci-dessous."
      );
    },
    onError: (e: Error) => toast.error(e.message),
  });

  useEffect(() => {
    if (!provisionResult || domainVerified) return;
    const interval = setInterval(async () => {
      try {
        const res = await authFetch(`/sites/${siteId}/blog-domain/status/`);
        if (!res.ok) return;
        const data = await res.json();
        if (data.verified) {
          setDomainVerified(true);
          toast.success(`Blog en ligne sur ${data.domain}`);
          clearInterval(interval);
        }
      } catch {
        // Network blip, skip.
      }
    }, 8000);
    return () => clearInterval(interval);
  }, [provisionResult, domainVerified, siteId]);

  const removeDomain = useMutation({
    mutationFn: async () => {
      const res = await authFetch(`/sites/${siteId}/blog-domain/`, {
        method: "DELETE",
      });
      if (!res.ok && res.status !== 204) {
        throw new Error("Erreur retrait");
      }
    },
    onSuccess: () => {
      setProvisionResult(null);
      setDomainVerified(false);
      setPublicBlogDomain("");
      toast.success("Domaine retire");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  // --- Competitors AI suggest ---
  const suggestCompetitors = useMutation({
    mutationFn: async () => {
      const res = await authFetch(`/sites/${siteId}/suggest-competitors/`, {
        method: "POST",
        body: JSON.stringify({}),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error || "Erreur suggestion concurrents");
      }
      return res.json() as Promise<{ competitors: string[] }>;
    },
    onSuccess: (data) => {
      const fresh = (data.competitors || []).filter(Boolean);
      if (fresh.length === 0) {
        toast.info("Aucun concurrent suggere - le contexte du site est trop generique.");
        return;
      }
      const existing = competitors
        .split("\n")
        .map((s) => s.trim())
        .filter(Boolean);
      const merged = Array.from(
        new Set([...existing, ...fresh].map((s) => s.trim()).filter(Boolean))
      );
      setCompetitors(merged.join("\n"));
      toast.success(`${fresh.length} concurrents suggeres. Revois la liste avant d'enregistrer.`);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  // --- Branding scan ---
  const scanBranding = useMutation({
    mutationFn: async () => {
      const res = await authFetch("/branding/scan/", {
        method: "POST",
        body: JSON.stringify({ url: domain }),
      });
      const data = await res.json();
      if (!res.ok || !data.success) {
        throw new Error(data.error || "Scan échoué.");
      }
      return data as {
        success: true;
        theme_config: { brand_color: string; brand_fg: string; logo_url: string; font_sans: string; font_display: string };
        meta: { site_name: string; description: string };
      };
    },
    onSuccess: (data) => {
      const tc = data.theme_config;
      setBrandColor(tc.brand_color || "");
      setBrandFg(tc.brand_fg || "");
      if (tc.logo_url) setLogoUrl(tc.logo_url);
      setScannedMeta({
        site_name: data.meta.site_name,
        brand_color: tc.brand_color,
        font_sans: tc.font_sans,
        logo_url: tc.logo_url,
      });
      toast.success("Branding détecté - n'oublie pas d'enregistrer.");
    },
    onError: (e: Error) => toast.error(e.message),
  });

  // --- GSC connect ---
  const handleConnectGsc = async () => {
    const numericSiteId = Number(siteId);
    if (!numericSiteId) return;
    setGscConnecting(true);
    try {
      const { url } = await fetchGSCOAuthUrl(numericSiteId);
      if (url) {
        window.location.href = url;
      } else {
        throw new Error("URL OAuth manquante");
      }
    } catch (err) {
      const msg =
        err instanceof ApiError
          ? err.message
          : err instanceof Error
            ? err.message
            : "Impossible d'obtenir l'URL OAuth";
      toast.error(msg);
      setGscConnecting(false);
    }
  };

  // --- Centralised save ---
  const handleSave = async () => {
    try {
      await updateSite.mutateAsync({
        name,
        domain,
        knowledge_base: knowledgeBase,
        competitors,
        vercel_deploy_hook: vercelDeployHook,
        gsc_property_url: gscPropertyUrl,
        available_languages: availableLanguages,
        description,
        og_image_url: ogImageUrl,
        default_author: defaultAuthor,
        default_language: defaultLanguage,
        business_model: businessModel,
        author_role: authorRole,
        author_bio: authorBio,
        author_credentials: authorCredentials,
        author_image_url: authorImageUrl,
        author_linkedin: authorLinkedin,
        author_twitter: authorTwitter,
        author_website: authorWebsite,
        primary_cta_text: primaryCtaText.trim(),
        primary_cta_url: primaryCtaUrl.trim(),
        public_blog_domain: publicBlogDomain.trim().toLowerCase(),
        theme_config: {
          ...(brandColor ? { brand_color: brandColor } : {}),
          ...(brandFg ? { brand_fg: brandFg } : {}),
          ...(logoUrl ? { logo_url: logoUrl } : {}),
        },
      });
      toast.success(t("settings.saved"));
    } catch {
      toast.error(t("settings.saveError"));
    }
  };

  const value: SettingsContextValue = {
    siteId,
    site,
    isLoading,
    updateSite,
    name, setName,
    domain, setDomain,
    description, setDescription,
    businessModel, setBusinessModel,
    primaryCtaText, setPrimaryCtaText,
    primaryCtaUrl, setPrimaryCtaUrl,
    availableLanguages, toggleLanguage,
    defaultLanguage, setDefaultLanguage,
    defaultAuthor, setDefaultAuthor,
    authorRole, setAuthorRole,
    authorBio, setAuthorBio,
    authorCredentials, setAuthorCredentials,
    authorImageUrl, setAuthorImageUrl,
    authorLinkedin, setAuthorLinkedin,
    authorTwitter, setAuthorTwitter,
    authorWebsite, setAuthorWebsite,
    ogImageUrl, setOgImageUrl,
    brandColor, setBrandColor,
    brandFg, setBrandFg,
    logoUrl, setLogoUrl,
    scannedMeta,
    scanBranding,
    gscPropertyUrl, setGscPropertyUrl,
    gscConnecting,
    handleConnectGsc,
    vercelDeployHook, setVercelDeployHook,
    knowledgeBase, setKnowledgeBase,
    competitors, setCompetitors,
    suggestCompetitors,
    publicBlogDomain, setPublicBlogDomain,
    provisionResult,
    domainVerified,
    provisionDomain,
    removeDomain,
    manualNote, setManualNote,
    manualNoteTitle, setManualNoteTitle,
    memoriesQuery,
    rebuildMemory,
    addManualNote,
    deleteMemory,
    handleSave,
  };

  return (
    <SettingsContext.Provider value={value}>{children}</SettingsContext.Provider>
  );
}
