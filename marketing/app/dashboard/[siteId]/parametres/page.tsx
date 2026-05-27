"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useSite, useUpdateSite } from "@/hooks/useDashboard";
import { authFetch, fetchGSCOAuthUrl, ApiError } from "@/lib/api-client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import { Settings, Save, Loader2, BookOpen, Rocket, Code, Copy, Languages, Palette, User as UserIcon, ImageIcon, Award, Linkedin, Twitter, Globe, MapPin, Check, AlertCircle, ExternalLink, Sparkles, Brain, RefreshCw, Trash2, Plus, Search, BarChart3 } from "lucide-react";
import { toast } from "sonner";
import { AutopilotCard } from "@/components/AutopilotCard";

export default function SiteSettings() {
  const { siteId } = useParams<{ siteId: string }>();
  const { data: site, isLoading } = useSite();
  const updateSite = useUpdateSite();

  // Memory (RAG) state + queries
  const [manualNote, setManualNote] = useState("");
  const [manualNoteTitle, setManualNoteTitle] = useState("");
  type MemoryRow = {
    id: number; kind: string; title: string; content_preview: string;
    token_count: number; source_ref: string; has_embedding: boolean; updated_at: string;
  };
  type MemoriesResponse = {
    memories: MemoryRow[];
    counts_by_kind: Record<string, number>;
    sources_by_kind?: Record<string, number>;
    total: number;
  };
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

  // Phase 2 - Blog subdomain plug-and-play via Vercel API.
  type ProvisionResult = {
    domain: string;
    verified: boolean;
    cname_target: string;
    next_step: string;
  };
  const [provisionResult, setProvisionResult] = useState<ProvisionResult | null>(null);
  const [domainVerified, setDomainVerified] = useState<boolean>(false);

  const provisionDomain = useMutation({
    mutationFn: async (domain: string) => {
      const res = await authFetch(`/sites/${siteId}/blog-domain/provision/`, {
        method: "POST",
        body: JSON.stringify({ domain }),
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
          ? "Domaine deja verifie - blog en ligne."
          : "Domaine enregistre. Suis les instructions DNS ci-dessous."
      );
    },
    onError: (e: Error) => toast.error(e.message),
  });

  // Poll the verify endpoint every 8s while we have a provisioned but
  // unverified domain. Stops when verified or when the user navigates away.
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
        // Network blip, skip this tick.
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

  // LocalBusiness schema form
  const [lbStreet, setLbStreet] = useState("");
  const [lbLocality, setLbLocality] = useState("");
  const [lbPostal, setLbPostal] = useState("");
  const [lbPhone, setLbPhone] = useState("");
  const [lbPriceRange, setLbPriceRange] = useState("");
  const [lbSchema, setLbSchema] = useState<unknown | null>(null);
  const [lbGenerating, setLbGenerating] = useState(false);
  const [lbCopied, setLbCopied] = useState(false);

  const generateLbSchema = async () => {
    setLbGenerating(true);
    try {
      const res = await authFetch(`/sites/${siteId}/local-business-schema/`, {
        method: "POST",
        body: JSON.stringify({
          address: {
            streetAddress: lbStreet || undefined,
            addressLocality: lbLocality || undefined,
            postalCode: lbPostal || undefined,
          },
          phone: lbPhone || undefined,
          price_range: lbPriceRange || undefined,
        }),
      });
      if (!res.ok) throw new Error("schema generation failed");
      const data = await res.json();
      setLbSchema(data.schema);
      toast.success("Schema LocalBusiness genere");
    } catch {
      toast.error("Erreur generation schema");
    } finally {
      setLbGenerating(false);
    }
  };

  const copyLbSchema = () => {
    if (!lbSchema) return;
    const tag = `<script type="application/ld+json">\n${JSON.stringify(lbSchema, null, 2)}\n</script>`;
    navigator.clipboard.writeText(tag);
    setLbCopied(true);
    toast.success("Schema copie dans le presse-papiers");
    setTimeout(() => setLbCopied(false), 1500);
  };

  const [name, setName] = useState("");
  const [domain, setDomain] = useState("");
  const [knowledgeBase, setKnowledgeBase] = useState("");
  const [competitors, setCompetitors] = useState("");
  const [vercelDeployHook, setVercelDeployHook] = useState("");
  const [gscPropertyUrl, setGscPropertyUrl] = useState("");
  const [gscConnecting, setGscConnecting] = useState(false);
  const [availableLanguages, setAvailableLanguages] = useState<string[]>([]);
  const [description, setDescription] = useState("");
  const [ogImageUrl, setOgImageUrl] = useState("");
  const [defaultAuthor, setDefaultAuthor] = useState("");
  const [defaultLanguage, setDefaultLanguage] = useState<string>("fr");
  // EEAT author profile
  const [authorRole, setAuthorRole] = useState("");
  const [authorBio, setAuthorBio] = useState("");
  const [authorCredentials, setAuthorCredentials] = useState("");
  const [authorImageUrl, setAuthorImageUrl] = useState("");
  const [authorLinkedin, setAuthorLinkedin] = useState("");
  const [authorTwitter, setAuthorTwitter] = useState("");
  const [authorWebsite, setAuthorWebsite] = useState("");
  // Public blog (Next.js frontend on our infra)
  const [publicBlogDomain, setPublicBlogDomain] = useState("");
  const [brandColor, setBrandColor] = useState("");
  const [brandFg, setBrandFg] = useState("");
  const [logoUrl, setLogoUrl] = useState("");
  const [scannedMeta, setScannedMeta] = useState<{
    site_name?: string;
    brand_color?: string;
    font_sans?: string;
    logo_url?: string;
  } | null>(null);

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

  /* eslint-disable react-hooks/set-state-in-effect */
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
      setAuthorRole(site.author_role || "");
      setAuthorBio(site.author_bio || "");
      setAuthorCredentials(site.author_credentials || "");
      setAuthorImageUrl(site.author_image_url || "");
      setAuthorLinkedin(site.author_linkedin || "");
      setAuthorTwitter(site.author_twitter || "");
      setAuthorWebsite(site.author_website || "");
      setPublicBlogDomain(site.public_blog_domain || "");
      const tc = (site as { theme_config?: Record<string, string> }).theme_config || {};
      setBrandColor(tc.brand_color || "");
      setBrandFg(tc.brand_fg || "");
      setLogoUrl(tc.logo_url || "");
    }
  }, [site]);
  /* eslint-enable react-hooks/set-state-in-effect */

  const toggleLanguage = (code: string) => {
    setAvailableLanguages((prev) =>
      prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code]
    );
  };

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
        author_role: authorRole,
        author_bio: authorBio,
        author_credentials: authorCredentials,
        author_image_url: authorImageUrl,
        author_linkedin: authorLinkedin,
        author_twitter: authorTwitter,
        author_website: authorWebsite,
        public_blog_domain: publicBlogDomain.trim().toLowerCase(),
        theme_config: {
          ...(brandColor ? { brand_color: brandColor } : {}),
          ...(brandFg ? { brand_fg: brandFg } : {}),
          ...(logoUrl ? { logo_url: logoUrl } : {}),
        },
      });
      toast.success("Parametres sauvegardes !");
    } catch {
      toast.error("Erreur lors de la sauvegarde");
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="text-2xl font-bold">{"Parametres du site"}</h1>
        <p className="text-muted-foreground">
          {"Configurez les informations du site et la base de connaissances pour la generation d'articles"}
        </p>
      </div>

      <Tabs defaultValue="identity" className="w-full">
        <TabsList className="sticky top-0 z-10 bg-background w-full flex-wrap h-auto justify-start gap-1">
          <TabsTrigger value="identity">Identite</TabsTrigger>
          <TabsTrigger value="branding">Branding</TabsTrigger>
          <TabsTrigger value="author">Auteur (EEAT)</TabsTrigger>
          <TabsTrigger value="local">Local SEO</TabsTrigger>
          <TabsTrigger value="integrations">Integrations</TabsTrigger>
          <TabsTrigger value="autopilot">Autopilote</TabsTrigger>
          <TabsTrigger value="advanced">Avance</TabsTrigger>
        </TabsList>

        {/* ===================== IDENTITY ===================== */}
        <TabsContent value="identity" className="space-y-6 mt-4">
          {/* General Settings */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Settings className="h-5 w-5" />
                {"Informations generales"}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label>{"Nom du site"}</Label>
                <Input value={name} onChange={(e) => setName(e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label>{"Domaine"}</Label>
                <Input
                  value={domain}
                  onChange={(e) => setDomain(e.target.value)}
                  placeholder={"https://monsite.com"}
                />
              </div>
              <div className="space-y-2">
                <Label className="flex items-center gap-1.5 text-sm">
                  Description
                </Label>
                <Textarea
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Courte description du site, utilisée pour les meta tags et les partages sociaux"
                  rows={3}
                  className="resize-y"
                />
                <p className="text-xs text-muted-foreground">
                  {description.length} caractères {description.length > 160 && "(trop long pour Open Graph - visez ≤160)"}
                </p>
              </div>
            </CardContent>
          </Card>

          {/* Available Languages */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Languages className="h-5 w-5" />
                Langues disponibles
              </CardTitle>
              <CardDescription>
                Sélectionnez les langues acceptées par le backend de ce site. Si rien n'est coché, toutes les langues sont autorisées (fr/en/es).
              </CardDescription>
            </CardHeader>
            <CardContent className="flex gap-3 flex-wrap">
              {[
                { code: "fr", label: "Français" },
                { code: "en", label: "English" },
                { code: "es", label: "Español" },
              ].map((l) => {
                const active = availableLanguages.includes(l.code);
                return (
                  <Button
                    key={l.code}
                    type="button"
                    variant={active ? "default" : "outline"}
                    size="sm"
                    onClick={() => toggleLanguage(l.code)}
                  >
                    {l.label}
                  </Button>
                );
              })}
            </CardContent>
          </Card>

          {/* Default author + default language */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <UserIcon className="h-5 w-5" />
                Auteur et langue par defaut
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label className="flex items-center gap-1.5 text-sm">
                    <UserIcon className="h-3.5 w-3.5" />
                    Auteur par défaut
                  </Label>
                  <Input
                    value={defaultAuthor}
                    onChange={(e) => setDefaultAuthor(e.target.value)}
                    placeholder="Admin"
                  />
                  <p className="text-xs text-muted-foreground">
                    Nom attribué aux articles générés par l'IA et utilisé dans le Schema.org
                  </p>
                </div>

                <div className="space-y-2">
                  <Label className="flex items-center gap-1.5 text-sm">
                    <Languages className="h-3.5 w-3.5" />
                    Langue par défaut
                  </Label>
                  <select
                    value={defaultLanguage}
                    onChange={(e) => setDefaultLanguage(e.target.value)}
                    className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm"
                  >
                    <option value="fr">Français</option>
                    <option value="en">English</option>
                    <option value="es">Español</option>
                  </select>
                  <p className="text-xs text-muted-foreground">
                    Présélectionnée dans l'éditeur et la génération IA
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ===================== BRANDING ===================== */}
        <TabsContent value="branding" className="space-y-6 mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Palette className="h-5 w-5" />
                Branding
              </CardTitle>
              <CardDescription>
                Identité du site utilisée pour Open Graph (partages sociaux), la page "à propos" et les articles générés.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label className="flex items-center gap-1.5 text-sm">
                  <ImageIcon className="h-3.5 w-3.5" />
                  Image Open Graph par défaut
                </Label>
                <div className="flex gap-2">
                  <Input
                    value={ogImageUrl}
                    onChange={(e) => setOgImageUrl(e.target.value)}
                    placeholder="https://exemple.com/og-image.png"
                    type="url"
                    className="flex-1"
                  />
                  {ogImageUrl && (
                    <img
                      src={ogImageUrl}
                      alt="OG preview"
                      className="h-10 w-16 object-cover rounded border"
                      onError={(e) => {
                        (e.target as HTMLImageElement).style.display = "none";
                      }}
                    />
                  )}
                </div>
                <p className="text-xs text-muted-foreground">
                  Image affichée sur Facebook/Twitter/LinkedIn quand un article n'a pas de cover. Recommandé: 1200×630.
                </p>
              </div>

              {/* Auto-scan branding from the site's domain */}
              <div className="rounded border border-border/50 bg-muted/30 p-3 space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <div className="text-sm">
                    <div className="font-medium">Détecter automatiquement le branding</div>
                    <div className="text-xs text-muted-foreground">
                      Scanne {domain || "ton domaine"} et remplit couleur, logo et fonts.
                    </div>
                  </div>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={!domain.trim() || scanBranding.isPending}
                    onClick={() => scanBranding.mutate()}
                  >
                    {scanBranding.isPending ? (
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    ) : (
                      <Sparkles className="h-4 w-4 mr-2" />
                    )}
                    Scanner
                  </Button>
                </div>
                {scannedMeta && (
                  <div className="text-xs text-muted-foreground border-t border-border/50 pt-2 flex items-center gap-3">
                    {scannedMeta.logo_url && (
                      <img
                        src={scannedMeta.logo_url}
                        alt="logo détecté"
                        className="h-6 w-6 rounded border"
                        onError={(e) => {
                          (e.target as HTMLImageElement).style.display = "none";
                        }}
                      />
                    )}
                    <span>
                      {scannedMeta.site_name || "?"} · couleur {scannedMeta.brand_color}
                      {scannedMeta.font_sans ? ` · ${scannedMeta.font_sans}` : ""}
                    </span>
                  </div>
                )}
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <div className="space-y-1">
                  <Label className="text-xs">Couleur principale</Label>
                  <div className="flex gap-2">
                    <Input
                      value={brandColor}
                      onChange={(e) => setBrandColor(e.target.value)}
                      placeholder="#2563eb"
                      className="font-mono text-sm"
                    />
                    <input
                      type="color"
                      value={brandColor || "#2563eb"}
                      onChange={(e) => setBrandColor(e.target.value)}
                      className="h-9 w-12 rounded border cursor-pointer"
                    />
                  </div>
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">Couleur du texte sur la couleur principale</Label>
                  <div className="flex gap-2">
                    <Input
                      value={brandFg}
                      onChange={(e) => setBrandFg(e.target.value)}
                      placeholder="#ffffff"
                      className="font-mono text-sm"
                    />
                    <input
                      type="color"
                      value={brandFg || "#ffffff"}
                      onChange={(e) => setBrandFg(e.target.value)}
                      className="h-9 w-12 rounded border cursor-pointer"
                    />
                  </div>
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">Logo URL</Label>
                  <Input
                    value={logoUrl}
                    onChange={(e) => setLogoUrl(e.target.value)}
                    placeholder="https://..."
                    type="url"
                    className="text-sm"
                  />
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ===================== AUTHOR (EEAT) ===================== */}
        <TabsContent value="author" className="space-y-6 mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Award className="h-5 w-5" />
                Profil auteur (E-E-A-T)
              </CardTitle>
              <CardDescription>
                Renseigne ces champs pour booster les signaux Experience, Expertise, Authority, Trust de Google. Utilisé en JSON-LD <code className="text-xs">Person</code> sur les articles.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label className="text-sm">Rôle / titre</Label>
                  <Input
                    value={authorRole}
                    onChange={(e) => setAuthorRole(e.target.value)}
                    placeholder="Ex: Fondateur, Consultant SEO, Avocat fiscaliste"
                  />
                  <p className="text-xs text-muted-foreground">
                    JSON-LD <code>jobTitle</code>. Aide Google à classer ton expertise.
                  </p>
                </div>
                <div className="space-y-2">
                  <Label className="text-sm flex items-center gap-1.5">
                    <ImageIcon className="h-3.5 w-3.5" />
                    Photo (URL)
                  </Label>
                  <div className="flex gap-2">
                    <Input
                      value={authorImageUrl}
                      onChange={(e) => setAuthorImageUrl(e.target.value)}
                      placeholder="https://..."
                      type="url"
                      className="flex-1"
                    />
                    {authorImageUrl && (
                      <img
                        src={authorImageUrl}
                        alt="Author preview"
                        className="h-10 w-10 rounded-full object-cover border"
                        onError={(e) => {
                          (e.target as HTMLImageElement).style.display = "none";
                        }}
                      />
                    )}
                  </div>
                </div>
              </div>

              <div className="space-y-2">
                <Label className="text-sm">Bio (2-4 phrases)</Label>
                <Textarea
                  value={authorBio}
                  onChange={(e) => setAuthorBio(e.target.value)}
                  placeholder="Ex: Fondateur de Gridar, j'aide les PME québécoises à atteindre la première page de Google. 10 ans d'expérience SEO."
                  rows={3}
                  className="resize-y"
                />
                <p className="text-xs text-muted-foreground">
                  {authorBio.length} caractères - vise une bio concise qui établit ton expérience pratique.
                </p>
              </div>

              <div className="space-y-2">
                <Label className="text-sm">Credentials / qualifications</Label>
                <Textarea
                  value={authorCredentials}
                  onChange={(e) => setAuthorCredentials(e.target.value)}
                  placeholder="Ex: MBA HEC Montréal, certifié Google Analytics, ancien consultant chez Shopify..."
                  rows={2}
                  className="resize-y"
                />
                <p className="text-xs text-muted-foreground">
                  JSON-LD <code>hasCredential</code>. Diplômes, certifications, expériences pertinentes.
                </p>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <div className="space-y-1">
                  <Label className="text-xs flex items-center gap-1.5">
                    <Linkedin className="h-3.5 w-3.5" />
                    LinkedIn
                  </Label>
                  <Input
                    value={authorLinkedin}
                    onChange={(e) => setAuthorLinkedin(e.target.value)}
                    placeholder="https://linkedin.com/in/..."
                    type="url"
                    className="h-9 text-sm"
                  />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs flex items-center gap-1.5">
                    <Twitter className="h-3.5 w-3.5" />
                    Twitter / X
                  </Label>
                  <Input
                    value={authorTwitter}
                    onChange={(e) => setAuthorTwitter(e.target.value)}
                    placeholder="https://x.com/..."
                    type="url"
                    className="h-9 text-sm"
                  />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs flex items-center gap-1.5">
                    <Globe className="h-3.5 w-3.5" />
                    Site personnel
                  </Label>
                  <Input
                    value={authorWebsite}
                    onChange={(e) => setAuthorWebsite(e.target.value)}
                    placeholder="https://..."
                    type="url"
                    className="h-9 text-sm"
                  />
                </div>
              </div>
              <p className="text-xs text-muted-foreground">
                Ces 3 URLs alimentent <code>sameAs</code> dans le JSON-LD Person - Google les utilise pour vérifier ton identité.
              </p>
            </CardContent>
          </Card>
        </TabsContent>

        {/* ===================== LOCAL SEO ===================== */}
        <TabsContent value="local" className="space-y-6 mt-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <MapPin className="h-5 w-5" />
                Schema LocalBusiness (Québec)
              </CardTitle>
              <CardDescription>
                Génère un JSON-LD <code className="text-xs">LocalBusiness</code> avec <code>addressCountry=CA</code>, <code>addressRegion=QC</code>, <code>areaServed=Québec</code>. À coller dans le <code>&lt;head&gt;</code> de ton site public.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div className="space-y-1">
                  <Label className="text-xs">Rue</Label>
                  <Input
                    value={lbStreet}
                    onChange={(e) => setLbStreet(e.target.value)}
                    placeholder="123 rue Saint-Denis"
                    className="h-9 text-sm"
                  />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">Ville</Label>
                  <Input
                    value={lbLocality}
                    onChange={(e) => setLbLocality(e.target.value)}
                    placeholder="Montréal"
                    className="h-9 text-sm"
                  />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">Code postal</Label>
                  <Input
                    value={lbPostal}
                    onChange={(e) => setLbPostal(e.target.value)}
                    placeholder="H2X 1Y2"
                    className="h-9 text-sm"
                  />
                </div>
                <div className="space-y-1">
                  <Label className="text-xs">Téléphone</Label>
                  <Input
                    value={lbPhone}
                    onChange={(e) => setLbPhone(e.target.value)}
                    placeholder="+1 514 555 0123"
                    className="h-9 text-sm"
                  />
                </div>
                <div className="space-y-1 md:col-span-2">
                  <Label className="text-xs">Gamme de prix (optionnel)</Label>
                  <Input
                    value={lbPriceRange}
                    onChange={(e) => setLbPriceRange(e.target.value)}
                    placeholder="$$ ou 30$ - 80$"
                    className="h-9 text-sm"
                  />
                  <p className="text-xs text-muted-foreground">
                    Convention Schema.org : "$" très accessible, "$$$$" haut de gamme.
                  </p>
                </div>
              </div>

              <Button
                onClick={generateLbSchema}
                disabled={lbGenerating}
                variant="outline"
              >
                {lbGenerating ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Génération...
                  </>
                ) : (
                  <>
                    <Code className="h-4 w-4 mr-2" />
                    Générer le schema
                  </>
                )}
              </Button>

              {lbSchema !== null && (
                <div className="space-y-2 border-t pt-4">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-mono uppercase tracking-wide text-muted-foreground">
                      JSON-LD prêt à coller
                    </span>
                    <Button size="sm" variant="outline" onClick={copyLbSchema}>
                      {lbCopied ? (
                        <Check className="h-3 w-3 mr-1 text-green-600" />
                      ) : (
                        <Copy className="h-3 w-3 mr-1" />
                      )}
                      Copier
                    </Button>
                  </div>
                  <pre className="text-[10px] bg-muted/50 rounded p-3 overflow-x-auto max-h-64 font-mono">
                    {JSON.stringify(lbSchema, null, 2)}
                  </pre>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* ===================== INTEGRATIONS ===================== */}
        <TabsContent value="integrations" className="space-y-6 mt-4">
          {/* Public Blog (hosted Next.js frontend) - wizard */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Globe className="h-5 w-5" />
                Blog public (frontend hébergé)
              </CardTitle>
              <CardDescription>
                Configure le frontend Next.js qu&apos;on héberge pour toi. Le visiteur lit tes articles via une URL dédiée - sous-domaine custom (<code>blog.tonsite.ca</code>) ou inclusion sous-chemin (<code>tonsite.ca/blog</code>).
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <Label className="text-sm">Domaine du blog public</Label>
                <div className="flex gap-2">
                  <Input
                    value={publicBlogDomain}
                    onChange={(e) => setPublicBlogDomain(e.target.value)}
                    placeholder="blog.restaurant.ca"
                    type="text"
                    className="flex-1"
                  />
                  {!provisionResult && publicBlogDomain.trim() && (
                    <Button
                      type="button"
                      size="sm"
                      onClick={() => provisionDomain.mutate(publicBlogDomain.trim())}
                      disabled={provisionDomain.isPending}
                    >
                      {provisionDomain.isPending ? (
                        <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                      ) : (
                        <Globe className="h-4 w-4 mr-2" />
                      )}
                      Activer
                    </Button>
                  )}
                  {provisionResult && (
                    <Button
                      type="button"
                      size="sm"
                      variant="outline"
                      onClick={() => removeDomain.mutate()}
                      disabled={removeDomain.isPending}
                    >
                      Retirer
                    </Button>
                  )}
                </div>
                <p className="text-xs text-muted-foreground">
                  On enregistre automatiquement le domaine sur Vercel et on te donne
                  le CNAME a coller chez ton registrar. SSL auto en moins de 5 min.
                </p>
              </div>

              {/* Wizard step 2 : show DNS instructions + status polling */}
              {provisionResult && !domainVerified && (
                <div className="rounded border border-amber-500/30 bg-amber-500/5 p-3 text-xs space-y-2">
                  <div className="flex items-start gap-2">
                    <Loader2 className="h-4 w-4 text-amber-600 shrink-0 mt-0.5 animate-spin" />
                    <div className="space-y-2 flex-1">
                      <strong>Etape DNS - colle ces valeurs chez ton registrar :</strong>
                      <div className="font-mono bg-background border rounded p-2 space-y-1">
                        <div><span className="text-muted-foreground">Type :</span> CNAME</div>
                        <div><span className="text-muted-foreground">Nom :</span> {provisionResult.domain.split(".")[0] || "blog"}</div>
                        <div><span className="text-muted-foreground">Valeur :</span> {provisionResult.cname_target}</div>
                      </div>
                      <p>{provisionResult.next_step}</p>
                      <p className="italic">
                        On verifie automatiquement toutes les 8 secondes. Cette page se mettra a jour quand le DNS aura propage.
                      </p>
                    </div>
                  </div>
                </div>
              )}

              {/* Wizard step 3 : success */}
              {provisionResult && domainVerified && (
                <div className="rounded border border-emerald-500/40 bg-emerald-500/10 p-3 text-sm flex items-center gap-2">
                  <Check className="h-4 w-4 text-emerald-500" />
                  <span>Blog en ligne sur</span>
                  <a
                    href={`https://${provisionResult.domain}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-mono text-primary hover:underline"
                  >
                    {provisionResult.domain}
                  </a>
                  <ExternalLink className="h-3 w-3 text-primary" />
                </div>
              )}

              {publicBlogDomain && (
                <a
                  href={`https://${publicBlogDomain}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-sm text-primary hover:underline"
                >
                  Visiter le blog public
                  <ExternalLink className="h-3 w-3" />
                </a>
              )}
            </CardContent>
          </Card>

          {/* Vercel Deploy Hook */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Rocket className="h-5 w-5" />
                Vercel Deploy Hook
              </CardTitle>
              <CardDescription>
                URL du webhook Vercel pour redeployer automatiquement le site apres chaque modification d&apos;article.
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Input
                value={vercelDeployHook}
                onChange={(e) => setVercelDeployHook(e.target.value)}
                placeholder="https://api.vercel.com/v1/integrations/deploy/prj_.../..."
                type="url"
              />
            </CardContent>
          </Card>

          {/* Google Search Console - property URL + OAuth connect button */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Search className="h-5 w-5" />
                Google Search Console
              </CardTitle>
              <CardDescription>
                URL exacte de ta property GSC (avec le slash final). Etape requise
                avant de pouvoir voir les positions reelles de tes articles.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="space-y-1">
                <Label className="text-sm">Property URL</Label>
                <Input
                  value={gscPropertyUrl}
                  onChange={(e) => setGscPropertyUrl(e.target.value)}
                  placeholder="https://tonsite.com/  ou  sc-domain:tonsite.com"
                  type="text"
                  className="font-mono text-sm"
                />
                <p className="text-xs text-muted-foreground">
                  Deux formats supportes :
                  <br />
                  - <strong>URL prefix</strong> (couvre exactement un sous-domaine + protocole) :{" "}
                  <code className="text-foreground">https://tonsite.com/</code> (slash final)
                  <br />
                  - <strong>Domain</strong> (couvre tous les sous-domaines + http/https) :{" "}
                  <code className="text-foreground">sc-domain:tonsite.com</code>
                  <br />
                  Copie-colle l&apos;URL exacte affichee dans Search Console.
                </p>
              </div>

              <Button
                type="button"
                variant="outline"
                onClick={handleConnectGsc}
                disabled={gscConnecting || !siteId}
              >
                {gscConnecting ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <BarChart3 className="h-4 w-4 mr-2" />
                )}
                Connecter Google Search Console
              </Button>

              <div className="rounded-md border border-border/50 bg-muted/30 p-3 text-xs space-y-2">
                <p className="font-semibold">Etapes une-fois :</p>
                <ol className="list-decimal list-inside space-y-1 text-muted-foreground">
                  <li>
                    <a
                      href="https://search.google.com/search-console/"
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-primary hover:underline"
                    >
                      search.google.com/search-console
                    </a>{" "}
                    -&gt; Add property -&gt; URL prefix -&gt; <code>https://{domain || "tonsite.com"}/</code>
                  </li>
                  <li>Verify ownership (DNS TXT, balise HTML ou Google Analytics)</li>
                  <li>Copie l&apos;URL exacte ci-dessus, sauvegarde, puis clique &laquo; Connecter Google Search Console &raquo; pour le OAuth.</li>
                </ol>
              </div>
            </CardContent>
          </Card>

          {/* Knowledge Base */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <BookOpen className="h-5 w-5" />
                {"Base de connaissances"}
              </CardTitle>
              <CardDescription>
                {"Ce texte est injecte dans le prompt de Claude lors de la generation d'articles. Il permet a l'IA d'ecrire avec votre voix, vos anecdotes et votre ton personnel. Plus c'est detaille, meilleur sera le resultat."}
              </CardDescription>
            </CardHeader>
            <CardContent>
              <Textarea
                value={knowledgeBase}
                onChange={(e) => setKnowledgeBase(e.target.value)}
                placeholder={"ex: Je suis fondateur d'Arivex Studio. J'ecris pour les PME quebecoises. Mon ton est direct, concret, sans bullshit marketing."}
                className="min-h-[400px] font-mono text-sm"
              />
              <p className="text-xs text-muted-foreground mt-2">
                {knowledgeBase.length} {"caracteres"}
              </p>
            </CardContent>
          </Card>

          {/* Marques a ne PAS citer */}
          <Card>
            <CardHeader>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <CardTitle className="text-lg">Marques a ne PAS citer</CardTitle>
                  <CardDescription>
                    Une marque par ligne. Le generateur evitera de les mentionner et n'y mettra jamais de lien sortant.
                  </CardDescription>
                </div>
                <Button
                  type="button"
                  size="sm"
                  variant="outline"
                  disabled={suggestCompetitors.isPending}
                  onClick={() => suggestCompetitors.mutate()}
                >
                  {suggestCompetitors.isPending ? (
                    <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
                  ) : (
                    <Sparkles className="h-3.5 w-3.5 mr-1.5" />
                  )}
                  Suggerer avec IA
                </Button>
              </div>
            </CardHeader>
            <CardContent>
              <Textarea
                value={competitors}
                onChange={(e) => setCompetitors(e.target.value)}
                placeholder={"Concurrent SARL\nAutre Marque inc.\nProduitX"}
                className="min-h-[140px] font-mono text-sm"
              />
              <p className="text-xs text-muted-foreground mt-2">
                Les suggestions IA s'ajoutent a la liste existante (sans ecraser ce que tu as deja ecrit).
              </p>
            </CardContent>
          </Card>

          {/* Memoire du site (RAG) */}
          <Card>
            <CardHeader>
              <div className="flex items-start justify-between gap-3">
                <div>
                  <CardTitle className="text-lg flex items-center gap-2">
                    <Brain className="h-5 w-5" />
                    Memoire du site (RAG)
                  </CardTitle>
                  <CardDescription>
                    Index vectoriel pgvector + Voyage AI. Chaque generation d'article retrieve les 8 extraits les plus pertinents (articles passes, KB, audits, notes) au lieu de tout balancer en prompt. Permet a l'IA de rester coherente entre les requetes.
                  </CardDescription>
                </div>
                <div className="flex gap-2 shrink-0">
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={() => rebuildMemory.mutate(false)}
                    disabled={rebuildMemory.isPending}
                  >
                    {rebuildMemory.isPending ? (
                      <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
                    ) : (
                      <RefreshCw className="h-3.5 w-3.5 mr-1.5" />
                    )}
                    Reindexer
                  </Button>
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {memoriesQuery.isLoading ? (
                <p className="text-xs text-muted-foreground">Chargement...</p>
              ) : memoriesQuery.data ? (
                <>
                  <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
                    {(["article", "kb", "audit", "decision", "manual"] as const).map((k) => {
                      const chunks = memoriesQuery.data!.counts_by_kind?.[k] || 0;
                      const sources = memoriesQuery.data!.sources_by_kind?.[k] || 0;
                      const showSources = chunks > 0 && sources > 0 && sources !== chunks;
                      return (
                        <div
                          key={k}
                          className="rounded-md border bg-muted/30 p-2 text-center"
                        >
                          <div className="text-xl font-bold">{chunks}</div>
                          <div className="text-[10px] uppercase tracking-wide text-muted-foreground">
                            {k === "article" ? "Extraits"
                              : k === "kb" ? "Extraits KB"
                              : k === "audit" ? "Audits"
                              : k === "decision" ? "Decisions"
                              : "Notes"}
                          </div>
                          {showSources && (
                            <div className="text-[10px] text-muted-foreground mt-0.5">
                              de {sources} source{sources > 1 ? "s" : ""}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                  <p className="text-[11px] text-muted-foreground -mt-2">
                    Chaque article publie est decoupe en plusieurs extraits (chunks) pour la recherche semantique. 1 article ~ 6-10 extraits selon sa longueur.
                  </p>
                </>
              ) : null}

              <div className="space-y-2 border-t pt-4">
                <Label className="text-sm flex items-center gap-1.5">
                  <Plus className="h-3.5 w-3.5" />
                  Ajouter une note manuelle
                </Label>
                <Input
                  value={manualNoteTitle}
                  onChange={(e) => setManualNoteTitle(e.target.value)}
                  placeholder="Titre court (ex: Voix de marque)"
                  className="h-8 text-sm"
                />
                <Textarea
                  value={manualNote}
                  onChange={(e) => setManualNote(e.target.value)}
                  placeholder={"Ex: 'Ne jamais utiliser le tutoiement.' / 'Cibler Montreal, pas Quebec.' / 'Mettre tous les chiffres en majuscule.'"}
                  className="min-h-[100px] text-sm"
                />
                <Button
                  size="sm"
                  onClick={() => addManualNote.mutate()}
                  disabled={!manualNote.trim() || addManualNote.isPending}
                >
                  {addManualNote.isPending ? (
                    <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
                  ) : (
                    <Plus className="h-3.5 w-3.5 mr-1.5" />
                  )}
                  Ajouter
                </Button>
              </div>

              {memoriesQuery.data?.memories && memoriesQuery.data.memories.length > 0 && (
                <div className="border-t pt-4">
                  <Label className="text-sm mb-2 block">Memoires recentes</Label>
                  <div className="space-y-2 max-h-80 overflow-y-auto">
                    {memoriesQuery.data.memories.slice(0, 30).map((m) => (
                      <div
                        key={m.id}
                        className="flex items-start gap-2 p-2 rounded-md border bg-muted/20 text-xs"
                      >
                        <span className="inline-block px-1.5 py-0.5 rounded bg-primary/10 text-primary uppercase text-[10px] font-mono shrink-0">
                          {m.kind}
                        </span>
                        <div className="flex-1 min-w-0">
                          {m.title && <div className="font-medium truncate">{m.title}</div>}
                          <div className="text-muted-foreground truncate">{m.content_preview}</div>
                        </div>
                        <button
                          type="button"
                          onClick={() => deleteMemory.mutate(m.id)}
                          className="text-muted-foreground hover:text-destructive shrink-0"
                          title="Supprimer"
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* ===================== AUTOPILOT ===================== */}
        <TabsContent value="autopilot" className="space-y-6 mt-4">
          {siteId && <AutopilotCard siteId={siteId} />}
        </TabsContent>

        {/* ===================== ADVANCED ===================== */}
        <TabsContent value="advanced" className="space-y-6 mt-4">
          {/* Public API (hosted mode) */}
          {site?.is_hosted && (
            <Card>
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <Code className="h-5 w-5" />
                  API publique (mode hébergé)
                </CardTitle>
                <CardDescription>
                  Ce site utilise le stockage hébergé du dashboard. Votre frontend peut consommer les articles via ces endpoints.
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-3">
                <div>
                  <Label className="text-xs">Endpoints publics</Label>
                  <div className="mt-1 space-y-1 font-mono text-xs bg-muted/50 p-3 rounded">
                    <div>GET /api/public/sites/{site.id}/posts/</div>
                    <div>GET /api/public/sites/{site.id}/posts/&lt;slug&gt;/</div>
                    <div>GET /api/public/sites/{site.id}/categories/</div>
                  </div>
                </div>
                {site.api_key && (
                  <div>
                    <Label className="text-xs">Clé API (en-tête X-Api-Key, optionnel)</Label>
                    <div className="flex gap-2 mt-1">
                      <Input value={site.api_key} readOnly className="font-mono text-xs" />
                      <Button
                        type="button"
                        variant="outline"
                        size="icon"
                        onClick={() => {
                          navigator.clipboard.writeText(site.api_key!);
                          toast.success("Clé copiée");
                        }}
                      >
                        <Copy className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {!site?.is_hosted && (
            <Card>
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <AlertCircle className="h-5 w-5" />
                  Reglages avances
                </CardTitle>
                <CardDescription>
                  Rien a configurer ici pour l'instant. Les futurs reglages techniques (limites API, webhooks, exports) apparaitront dans cet onglet.
                </CardDescription>
              </CardHeader>
            </Card>
          )}
        </TabsContent>
      </Tabs>

      <Button
        size="lg"
        onClick={handleSave}
        disabled={updateSite.isPending}
        className="w-full sm:w-auto"
      >
        {updateSite.isPending ? (
          <>
            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            {"Sauvegarde..."}
          </>
        ) : (
          <>
            <Save className="h-4 w-4 mr-2" />
            {"Sauvegarder"}
          </>
        )}
      </Button>
    </div>
  );
}
