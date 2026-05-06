import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import {
  Card,
  CardContent,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Skeleton } from "@/components/ui/skeleton";
import {
  fetchSites,
  createSite,
  deleteSite as apiDeleteSite,
  testSiteConnection,
  initSiteDB,
} from "@/lib/api-client";
import { useAuth } from "@/hooks/useAuth";
import type { Site } from "@/lib/sites";
import {
  Globe,
  Plus,
  Trash2,
  LogIn,
  Loader2,
  Newspaper,
  LogOut,
  CheckCircle,
  Database,
  BarChart3,
  Sparkles,
  CreditCard,
  Key,
  ShoppingBag,
  Layers,
  Code,
} from "lucide-react";
import { WordPressConnectDialog } from "@/components/WordPressConnectDialog";
import { ShopifyConnectDialog } from "@/components/ShopifyConnectDialog";
import { WebflowConnectDialog } from "@/components/WebflowConnectDialog";
import { useConfetti } from "@/hooks/useConfetti";
import ProductMockup3D from "@/components/ProductMockup3D";
import { toast } from "sonner";

export default function SiteSelector() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { logout } = useAuth();
  const qc = useQueryClient();
  const fireConfetti = useConfetti();
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [wpDialogOpen, setWpDialogOpen] = useState(false);
  const [shopifyDialogOpen, setShopifyDialogOpen] = useState(false);
  const [webflowDialogOpen, setWebflowDialogOpen] = useState(false);

  const [name, setName] = useState("");
  const [databaseUrl, setDatabaseUrl] = useState("");
  const [domain, setDomain] = useState("");

  const { data: sites = [], isLoading } = useQuery({
    queryKey: ["sites"],
    queryFn: fetchSites,
  });

  const deleteMutation = useMutation({
    mutationFn: apiDeleteSite,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["sites"] });
      toast.success(t("sites.deleted"));
    },
  });

  const handleConnect = (site: Site) => {
    navigate(`/dashboard/${site.id}`);
  };

  const handleDelete = (id: number) => {
    if (!confirm(t("sites.deleteConfirm"))) return;
    deleteMutation.mutate(id);
  };

  const handleTestConnection = async (id: number) => {
    try {
      const result = await testSiteConnection(id);
      if (result.success) {
        toast.success(t("sites.testSuccess"));
      } else {
        toast.error(t("sites.testFail") + result.message);
      }
    } catch {
      toast.error(t("sites.testError"));
    }
  };

  const handleInitDB = async (id: number) => {
    try {
      const result = await initSiteDB(id);
      if (result.success) {
        toast.success(t("sites.initSuccess"));
      } else {
        toast.error(t("sites.initFail") + result.error);
      }
    } catch {
      toast.error(t("sites.initError"));
    }
  };

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await createSite({
        name: name.trim(),
        database_url: databaseUrl.trim(),
        domain: domain.trim(),
      });
      qc.invalidateQueries({ queryKey: ["sites"] });
      // Celebrate first-ever site creation
      if (sites.length === 0) fireConfetti();
      setOpen(false);
      setName("");
      setDatabaseUrl("");
      setDomain("");
      toast.success(t("sites.added"));
    } catch {
      toast.error(t("sites.addError"));
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <div className="w-full max-w-2xl space-y-6">
        <div className="text-center space-y-2">
          <div className="flex items-center justify-center gap-2 mb-4">
            <Newspaper className="h-8 w-8 text-primary" />
            <h1 className="text-3xl font-bold">{t("sites.title")}</h1>
          </div>
          <p className="text-muted-foreground">
            {t("sites.subtitle")}
          </p>
        </div>

        {isLoading ? (
          <div className="space-y-3">
            {[...Array(2)].map((_, i) => (
              <Skeleton key={i} className="h-20" />
            ))}
          </div>
        ) : sites.length > 0 ? (
          <div className="space-y-3">
            {sites.map((site: Site) => (
              <Card key={site.id} className="hover:border-primary/50 transition-colors">
                <CardContent className="flex items-center justify-between p-4">
                  <div className="flex items-center gap-3">
                    <Globe className="h-5 w-5 text-muted-foreground" />
                    <div>
                      <p className="font-medium">{site.name}</p>
                      <p className="text-sm text-muted-foreground">
                        {site.domain || t("common.noDomain")}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button size="sm" variant="outline" onClick={() => handleTestConnection(site.id)}>
                      <CheckCircle className="h-4 w-4 mr-1" />
                      {t("common.test")}
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => handleInitDB(site.id)}>
                      <Database className="h-4 w-4 mr-1" />
                      {t("common.init")}
                    </Button>
                    <Button size="sm" onClick={() => handleConnect(site)}>
                      <LogIn className="h-4 w-4 mr-2" />
                      {t("common.open")}
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => handleDelete(site.id)}>
                      <Trash2 className="h-4 w-4 text-destructive" />
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        ) : (
          <div className="relative rounded-2xl overflow-hidden border border-border/50 bg-zinc-950">
            {/* Emerald glow background */}
            <div
              aria-hidden
              className="absolute inset-0 pointer-events-none"
              style={{
                background:
                  "radial-gradient(80% 60% at 50% 30%, rgba(16,185,129,0.15), transparent 70%)",
              }}
            />

            {/* Grayed-out mockup preview, scaled down */}
            <div
              className="relative grayscale opacity-50 pointer-events-none"
              style={{
                transform: "scale(0.7)",
                transformOrigin: "50% 30%",
                marginBottom: "-180px",
              }}
            >
              <ProductMockup3D />
            </div>

            {/* Overlay CTA */}
            <div className="absolute inset-0 flex items-center justify-center backdrop-blur-[1px]">
              <div className="relative max-w-md text-center px-6 py-10">
                <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-emerald-400/30 bg-emerald-400/10 text-emerald-300 text-xs font-mono uppercase tracking-wider mb-4">
                  <Sparkles className="h-3 w-3" />
                  Ton dashboard t'attend
                </div>
                <h2 className="text-2xl md:text-3xl font-bold tracking-tight text-white">
                  Connecte ton premier site pour le débloquer
                </h2>
                <p className="text-sm text-zinc-400 mt-2">
                  Articles SEO, audit IA, suivi Google. Tout devient actif dès la première connexion.
                </p>
                <div className="mt-6 flex items-center justify-center gap-2 text-xs text-zinc-500">
                  <span className="inline-block h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
                  Choisis une option ci-dessous
                </div>
              </div>
            </div>
          </div>
        )}

        {/* CMS quick-connect - primary path for non-technical users */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Button
            className="w-full"
            size="lg"
            variant="default"
            onClick={() => setWpDialogOpen(true)}
          >
            <Sparkles className="h-5 w-5 mr-2" />
            WordPress
          </Button>
          <Button
            className="w-full"
            size="lg"
            variant="default"
            onClick={() => setShopifyDialogOpen(true)}
          >
            <ShoppingBag className="h-5 w-5 mr-2" />
            Shopify
          </Button>
          <Button
            className="w-full"
            size="lg"
            variant="default"
            onClick={() => setWebflowDialogOpen(true)}
          >
            <Layers className="h-5 w-5 mr-2" />
            Webflow
          </Button>
          <Button
            className="w-full"
            size="lg"
            variant="outline"
            onClick={() => setOpen(true)}
          >
            <Newspaper className="h-5 w-5 mr-2" />
            {t("sites.hostedBlog", "Blog clé-en-main")}
          </Button>
        </div>

        <p className="text-xs text-muted-foreground text-center -mt-2">
          {t("sites.hostedHint", "Pas encore de blog ? On t'en bâtit un complet en 5 minutes (Next.js, SEO Québec, hébergé chez nous, sur ton sous-domaine).")}
        </p>

        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button className="w-full" size="lg" variant="outline">
              <Plus className="h-5 w-5 mr-2" />
              {t("sites.addSite")}
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>{t("sites.addSiteTitle")}</DialogTitle>
            </DialogHeader>
            <form onSubmit={handleAdd} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="name">{t("sites.siteName")}</Label>
                <Input id="name" placeholder={t("sites.siteNamePlaceholder")} value={name} onChange={(e) => setName(e.target.value)} required />
              </div>
              <div className="space-y-2">
                <Label htmlFor="databaseUrl">{t("sites.databaseUrl")} <span className="text-muted-foreground text-xs">(optionnel)</span></Label>
                <Input id="databaseUrl" placeholder="postgresql://... (vide = stockage hébergé)" value={databaseUrl} onChange={(e) => setDatabaseUrl(e.target.value)} />
                <p className="text-xs text-muted-foreground">
                  Laissez vide pour utiliser le stockage hébergé du dashboard. Vos articles seront accessibles via l'API publique.
                </p>
              </div>
              <div className="space-y-2">
                <Label htmlFor="domain">{t("sites.domain")}</Label>
                <Input id="domain" placeholder={t("sites.domainPlaceholder")} value={domain} onChange={(e) => setDomain(e.target.value)} />
              </div>
              <Button type="submit" className="w-full" disabled={loading}>
                {loading ? (<><Loader2 className="h-4 w-4 mr-2 animate-spin" />{t("sites.adding")}</>) : t("sites.addButton")}
              </Button>
            </form>
          </DialogContent>
        </Dialog>

        <WordPressConnectDialog open={wpDialogOpen} onOpenChange={setWpDialogOpen} />
        <ShopifyConnectDialog open={shopifyDialogOpen} onOpenChange={setShopifyDialogOpen} />
        <WebflowConnectDialog open={webflowDialogOpen} onOpenChange={setWebflowDialogOpen} />

        <div className="text-center flex items-center justify-center gap-2">
          <Button variant="ghost" size="sm" onClick={() => navigate("/compare")}>
            <BarChart3 className="h-4 w-4 mr-2" />
            {t("sites.compare", "Comparer mes sites")}
          </Button>
          <span className="text-muted-foreground">·</span>
          <Button variant="ghost" size="sm" onClick={() => navigate("/billing")}>
            <CreditCard className="h-4 w-4 mr-2" />
            Abonnement
          </Button>
          <span className="text-muted-foreground">·</span>
          <Button variant="ghost" size="sm" onClick={() => navigate("/account/api-keys")}>
            <Key className="h-4 w-4 mr-2" />
            API
          </Button>
          <span className="text-muted-foreground">·</span>
          <Button variant="ghost" size="sm" onClick={() => navigate("/onboarding/external")}>
            <Code className="h-4 w-4 mr-2" />
            Mode externe (React/Next.js)
          </Button>
          <span className="text-muted-foreground">·</span>
          <Button variant="ghost" size="sm" onClick={handleLogout}>
            <LogOut className="h-4 w-4 mr-2" />
            {t("sites.logout")}
          </Button>
        </div>
      </div>
    </div>
  );
}
