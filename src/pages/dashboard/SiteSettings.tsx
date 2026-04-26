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
import { Settings, Save, Loader2, BookOpen, Rocket, Code, Copy, Languages } from "lucide-react";
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

  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    if (site) {
      setName(site.name || "");
      setDomain(site.domain || "");
      setKnowledgeBase(site.knowledge_base || "");
      setVercelDeployHook(site.vercel_deploy_hook || "");
      setAvailableLanguages(site.available_languages || []);
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
        available_languages: availableLanguages.length > 0 ? availableLanguages : null,
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
