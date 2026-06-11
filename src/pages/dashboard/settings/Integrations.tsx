import { useTranslation } from "react-i18next";
import { Globe, Loader2, Check, ExternalLink, Rocket, BookOpen, Sparkles, Code, Copy, AlertCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { toast } from "sonner";
import { useSettings } from "./useSettings";

export default function Integrations() {
  const { t } = useTranslation();
  const {
    site,
    publicBlogDomain, setPublicBlogDomain,
    provisionResult, domainVerified,
    provisionDomain, removeDomain,
    vercelDeployHook, setVercelDeployHook,
    knowledgeBase, setKnowledgeBase,
    competitors, setCompetitors,
    suggestCompetitors,
  } = useSettings();

  return (
    <div className="space-y-6">
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
              le CNAME à coller chez ton registrar. SSL auto en moins de 5 min.
            </p>
          </div>

          {provisionResult && !domainVerified && (
            <div className="rounded border border-amber-500/30 bg-amber-500/5 p-3 text-xs space-y-2">
              <div className="flex items-start gap-2">
                <Loader2 className="h-4 w-4 text-amber-600 shrink-0 mt-0.5 animate-spin" />
                <div className="space-y-2 flex-1">
                  <strong>Étape DNS - colle ces valeurs chez ton registrar :</strong>
                  <div className="font-mono bg-background border rounded p-2 space-y-1 break-all">
                    <div><span className="text-muted-foreground">Type :</span> CNAME</div>
                    <div><span className="text-muted-foreground">Nom :</span> {provisionResult.domain.split(".")[0] || "blog"}</div>
                    <div><span className="text-muted-foreground">Valeur :</span> {provisionResult.cname_target}</div>
                  </div>
                  <p>{provisionResult.next_step}</p>
                  <p className="italic">
                    On vérifie automatiquement toutes les 8 secondes. Cette page se mettra à jour quand le DNS aura propagé.
                  </p>
                </div>
              </div>
            </div>
          )}

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

      {/* Marques a ne PAS citer */}
      <Card>
        <CardHeader>
          <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-3">
            <div>
              <CardTitle className="text-lg">Marques à ne PAS citer</CardTitle>
              <CardDescription>
                Une marque par ligne. Le générateur évitera de les mentionner et n'y mettra jamais de lien sortant.
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
              Suggérer avec IA
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
            Les suggestions IA s'ajoutent à la liste existante (sans écraser ce que tu as déjà écrit).
          </p>
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
              <div className="mt-1 space-y-1 font-mono text-xs bg-muted/50 p-3 rounded overflow-x-auto">
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
              Réglages avancés
            </CardTitle>
            <CardDescription>
              Rien à configurer ici pour l'instant. Les futurs réglages techniques (limites API, webhooks, exports) apparaîtront dans cet onglet.
            </CardDescription>
          </CardHeader>
        </Card>
      )}
    </div>
  );
}
