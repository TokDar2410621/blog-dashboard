import { useTranslation } from "react-i18next";
import { Settings, Rocket } from "lucide-react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useSettings } from "./useSettings";

export default function General() {
  const { t } = useTranslation();
  const {
    name, setName,
    domain, setDomain,
    description, setDescription,
    businessModel, setBusinessModel,
  } = useSettings();

  return (
    <div className="space-y-6">
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
          <div className="space-y-2">
            <Label className="flex items-center gap-1.5 text-sm">Description</Label>
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

      <Card>
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Rocket className="h-5 w-5" />
            Modèle d'affaires
          </CardTitle>
          <CardDescription>
            Détermine l'angle éditorial des articles générés. Champ obligatoire
            avant la première génération - sans ça, le LLM produit du contenu
            générique.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-2">
          <Label className="text-sm">Type de business</Label>
          <select
            value={businessModel}
            onChange={(e) => setBusinessModel(e.target.value)}
            className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm"
          >
            <option value="personal_blog">Blog personnel</option>
            <option value="agency">Agence (services BtoB)</option>
            <option value="saas">SaaS</option>
            <option value="ecommerce">E-commerce</option>
            <option value="marketplace">Marketplace</option>
            <option value="media">Media / Édition</option>
          </select>
          <p className="text-xs text-muted-foreground">
            SaaS pousse comparatifs + use-cases. E-commerce pousse buying guides.
            Agence pousse case studies. Média pousse evergreen long-form.
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
