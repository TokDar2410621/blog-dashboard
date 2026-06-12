"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Card,
  CardContent,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { GridarMark } from "@/components/GridarMark";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
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
import { useAuth } from "@/context/AuthContext";
import { AuthGuard } from "@/components/AuthGuard";
import type { Site } from "@/lib/schemas";
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
  LayoutDashboard,
} from "lucide-react";
import { WordPressConnectDialog } from "@/components/WordPressConnectDialog";
import { ShopifyConnectDialog } from "@/components/ShopifyConnectDialog";
import { WebflowConnectDialog } from "@/components/WebflowConnectDialog";
import { useConfetti } from "@/hooks/useConfetti";
import ProductMockup3D from "@/components/ProductMockup3D";
import { toast } from "sonner";

function SiteSelectorContent() {
  const router = useRouter();
  const { logout } = useAuth();
  const qc = useQueryClient();
  const fireConfetti = useConfetti();
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [wpDialogOpen, setWpDialogOpen] = useState(false);
  const [shopifyDialogOpen, setShopifyDialogOpen] = useState(false);
  const [webflowDialogOpen, setWebflowDialogOpen] = useState(false);
  const [deleteSiteId, setDeleteSiteId] = useState<number | null>(null);

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
      toast.success("Site supprimé");
    },
  });

  const handleConnect = (site: Site) => {
    router.push(`/dashboard/${site.id}`);
  };

  const handleDelete = (id: number) => {
    setDeleteSiteId(id);
  };

  const confirmDelete = () => {
    if (deleteSiteId !== null) {
      deleteMutation.mutate(deleteSiteId);
      setDeleteSiteId(null);
    }
  };

  const handleTestConnection = async (id: number) => {
    try {
      const result = await testSiteConnection(id);
      if (result.success) {
        toast.success("Connexion réussie!");
      } else {
        toast.error("Échec: " + result.message);
      }
    } catch {
      toast.error("Erreur lors du test");
    }
  };

  const handleInitDB = async (id: number) => {
    try {
      const result = await initSiteDB(id);
      if (result.success) {
        toast.success("Tables blog créées!");
      } else {
        toast.error("Échec: " + result.error);
      }
    } catch {
      toast.error("Erreur lors de l'initialisation");
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
      toast.success("Site ajouté!");
    } catch (err) {
      // Close the dialog so the toast is not occluded by the Radix overlay.
      // Otherwise the user submits, sees nothing change, and the error
      // message stays hidden behind the modal.
      setOpen(false);
      const msg = err instanceof Error ? err.message : "";
      toast.error(msg || "Erreur lors de l'ajout.");
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    logout();
    router.push("/login");
  };

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <div className="w-full max-w-2xl space-y-6">
        {sites.length > 1 && (
          <div className="flex justify-center">
            <Button
              variant="outline"
              size="sm"
              onClick={() => router.push("/dashboard/overview")}
            >
              <LayoutDashboard className="h-4 w-4 mr-2" />
              Voir vue multi-sites
            </Button>
          </div>
        )}

        <div className="text-center space-y-2">
          <div className="flex items-center justify-center gap-2 mb-4">
            <GridarMark className="h-8 w-8 text-primary" />
            <h1 className="text-3xl font-bold">Gridar</h1>
          </div>
          <p className="text-muted-foreground">
            Sélectionnez un site à gérer
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
                <CardContent className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
                  <div className="flex items-center gap-3 min-w-0">
                    <Globe className="h-5 w-5 text-muted-foreground" />
                    <div className="min-w-0">
                      <p className="font-medium">{site.name}</p>
                      <p className="text-sm text-muted-foreground truncate">
                        {site.domain || "Pas de domaine"}
                      </p>
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Button size="sm" variant="outline" onClick={() => handleTestConnection(site.id)}>
                      <CheckCircle className="h-4 w-4 mr-1" />
                      Test
                    </Button>
                    <Button size="sm" variant="outline" onClick={() => handleInitDB(site.id)}>
                      <Database className="h-4 w-4 mr-1" />
                      Init
                    </Button>
                    <Button size="sm" onClick={() => handleConnect(site)}>
                      <LogIn className="h-4 w-4 mr-2" />
                      Ouvrir
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
          <div className="relative min-h-[360px] rounded-2xl overflow-hidden border border-border/50 bg-zinc-950">
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
              className="relative grayscale opacity-50 pointer-events-none -mb-20 md:-mb-44"
              style={{
                transform: "scale(0.7)",
                transformOrigin: "50% 30%",
              }}
            >
              <ProductMockup3D />
            </div>

            {/* Overlay CTA */}
            <div className="absolute inset-0 flex items-center justify-center backdrop-blur-[1px]">
              <div className="relative max-w-md text-center px-6 py-10">
                <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-emerald-400/30 bg-emerald-400/10 text-emerald-300 text-xs font-mono uppercase tracking-wider mb-4">
                  <Sparkles className="h-3 w-3" />
                  Ton dashboard t&apos;attend
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
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
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
            Blog clé-en-main
          </Button>
        </div>

        <p className="text-xs text-muted-foreground text-center -mt-2">
          Pas encore de blog ? On t&apos;en bâtit un complet en 5 minutes (Next.js, SEO Québec, hébergé chez nous, sur ton sous-domaine).
        </p>

        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button className="w-full" size="lg" variant="outline">
              <Plus className="h-5 w-5 mr-2" />
              Ajouter un site
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Ajouter un site</DialogTitle>
            </DialogHeader>
            <form onSubmit={handleAdd} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="name">Nom du site</Label>
                <Input id="name" placeholder="Mon blog" value={name} onChange={(e) => setName(e.target.value)} required />
              </div>
              <div className="space-y-2">
                <Label htmlFor="databaseUrl">DATABASE_URL <span className="text-muted-foreground text-xs">(optionnel)</span></Label>
                <Input id="databaseUrl" placeholder="postgresql://... (vide = stockage hébergé)" value={databaseUrl} onChange={(e) => setDatabaseUrl(e.target.value)} />
                <p className="text-xs text-muted-foreground">
                  Laissez vide pour utiliser le stockage hébergé du dashboard. Vos articles seront accessibles via l&apos;API publique.
                </p>
              </div>
              <div className="space-y-2">
                <Label htmlFor="domain">Domaine (optionnel)</Label>
                <Input id="domain" placeholder="https://monsite.ca" value={domain} onChange={(e) => setDomain(e.target.value)} />
              </div>
              <Button type="submit" className="w-full" disabled={loading}>
                {loading ? (<><Loader2 className="h-4 w-4 mr-2 animate-spin" />Ajout en cours...</>) : "Ajouter le site"}
              </Button>
            </form>
          </DialogContent>
        </Dialog>

        <WordPressConnectDialog open={wpDialogOpen} onOpenChange={setWpDialogOpen} />
        <ShopifyConnectDialog open={shopifyDialogOpen} onOpenChange={setShopifyDialogOpen} />
        <WebflowConnectDialog open={webflowDialogOpen} onOpenChange={setWebflowDialogOpen} />

        {/* Delete confirmation (marketing has no alert-dialog primitive, so we
            rebuild the same confirm UX with the dialog primitive). */}
        <Dialog
          open={deleteSiteId !== null}
          onOpenChange={(o) => !o && setDeleteSiteId(null)}
        >
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Supprimer ce site ?</DialogTitle>
              <DialogDescription>
                Cette action est irréversible. Toutes les données associées seront perdues.
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <Button variant="outline" onClick={() => setDeleteSiteId(null)}>
                Annuler
              </Button>
              <Button variant="destructive" onClick={confirmDelete}>
                Supprimer
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        <div className="text-center flex flex-wrap items-center justify-center gap-2">
          <Button variant="ghost" size="sm" onClick={() => router.push("/compare")}>
            <BarChart3 className="h-4 w-4 mr-2" />
            Comparer mes sites
          </Button>
          <span className="text-muted-foreground hidden sm:inline">·</span>
          <Button variant="ghost" size="sm" onClick={() => router.push("/billing")}>
            <CreditCard className="h-4 w-4 mr-2" />
            Abonnement
          </Button>
          <span className="text-muted-foreground hidden sm:inline">·</span>
          <Button variant="ghost" size="sm" onClick={() => router.push("/account/api-keys")}>
            <Key className="h-4 w-4 mr-2" />
            API
          </Button>
          <span className="text-muted-foreground hidden sm:inline">·</span>
          <Button variant="ghost" size="sm" onClick={() => router.push("/onboarding/external")}>
            <Code className="h-4 w-4 mr-2" />
            Mode externe (React/Next.js)
          </Button>
          <span className="text-muted-foreground hidden sm:inline">·</span>
          <Button variant="ghost" size="sm" onClick={handleLogout}>
            <LogOut className="h-4 w-4 mr-2" />
            Déconnexion
          </Button>
        </div>
      </div>
    </div>
  );
}

export function SiteSelector() {
  return (
    <AuthGuard>
      <SiteSelectorContent />
    </AuthGuard>
  );
}
