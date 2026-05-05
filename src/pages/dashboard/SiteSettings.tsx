import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { useSite, useUpdateSite } from "@/hooks/useDashboard";
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
import { Settings, Save, Loader2, BookOpen, Rocket, Code, Copy, Languages, Palette, User as UserIcon, ImageIcon, Award, Linkedin, Twitter, Globe } from "lucide-react";
import { toast } from "sonner";

export default function SiteSettings() {
  const { t } = useTranslation();
  const { data: site, isLoading } = useSite();
  const updateSite = useUpdateSite();

  const [name, setName] = useState("");
  const [domain, setDomain] = useState("");
  const [knowledgeBase, setKnowledgeBase] = useState("");
  const [vercelDeployHook, setVercelDeployHook] = useState("");
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

  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    if (site) {
      setName(site.name || "");
      setDomain(site.domain || "");
      setKnowledgeBase(site.knowledge_base || "");
      setVercelDeployHook(site.vercel_deploy_hook || "");
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
    }
  }, [site]);
  /* eslint-enable react-hooks/set-state-in-effect */

  const toggleLanguage = (code: string) => {
    setAvailableLanguages((prev) =>
      prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code]
    );
  };

  const handleSave = async () => {
    try {
      await updateSite.mutateAsync({
        name,
        domain,
        knowledge_base: knowledgeBase,
        vercel_deploy_hook: vercelDeployHook,
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
      });
      toast.success(t("settings.saved"));
    } catch {
      toast.error(t("settings.saveError"));
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
        <h1 className="text-2xl font-bold">{t("settings.title")}</h1>
        <p className="text-muted-foreground">
          {t("settings.subtitle")}
        </p>
      </div>

      {/* General Settings */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Settings className="h-5 w-5" />
            {t("settings.general")}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label>{t("settings.siteName")}</Label>
            <Input value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div className="space-y-2">
            <Label>{t("settings.domain")}</Label>
            <Input
              value={domain}
              onChange={(e) => setDomain(e.target.value)}
              placeholder={t("settings.domainPlaceholder")}
            />
          </div>
        </CardContent>
      </Card>

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

      {/* Vercel Deploy Hook */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Rocket className="h-5 w-5" />
            Vercel Deploy Hook
          </CardTitle>
          <CardDescription>
            {t("settings.deployHookDesc", "URL du webhook Vercel pour redéployer automatiquement le site après chaque modification d'article.")}
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

      {/* Branding */}
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
              {description.length} caractères {description.length > 160 && "(trop long pour Open Graph — visez ≤160)"}
            </p>
          </div>

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

      {/* EEAT — Author profile (Schema.org Person) */}
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
              placeholder="Ex: Fondateur de Blog Dashboard, j'aide les PME québécoises à atteindre la première page de Google. 10 ans d'expérience SEO."
              rows={3}
              className="resize-y"
            />
            <p className="text-xs text-muted-foreground">
              {authorBio.length} caractères — vise une bio concise qui établit ton expérience pratique.
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
            Ces 3 URLs alimentent <code>sameAs</code> dans le JSON-LD Person — Google les utilise pour vérifier ton identité.
          </p>
        </CardContent>
      </Card>

      {/* Knowledge Base */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <BookOpen className="h-5 w-5" />
            {t("settings.knowledgeBase")}
          </CardTitle>
          <CardDescription>
            {t("settings.knowledgeBaseDesc")}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <Textarea
            value={knowledgeBase}
            onChange={(e) => setKnowledgeBase(e.target.value)}
            placeholder={t("knowledgePlaceholder")}
            className="min-h-[400px] font-mono text-sm"
          />
          <p className="text-xs text-muted-foreground mt-2">
            {knowledgeBase.length} {t("common.characters")}
          </p>
        </CardContent>
      </Card>

      <Button
        size="lg"
        onClick={handleSave}
        disabled={updateSite.isPending}
        className="w-full sm:w-auto"
      >
        {updateSite.isPending ? (
          <>
            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            {t("settings.saving")}
          </>
        ) : (
          <>
            <Save className="h-4 w-4 mr-2" />
            {t("settings.save")}
          </>
        )}
      </Button>
    </div>
  );
}
