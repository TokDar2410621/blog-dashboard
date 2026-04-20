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
} from "lucide-react";
import { toast } from "sonner";

export default function SiteSelector() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { logout } = useAuth();
  const qc = useQueryClient();
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);

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
          <Card>
            <CardContent className="py-12 text-center">
              <Globe className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
              <p className="text-muted-foreground">
                {t("sites.empty")}
              </p>
            </CardContent>
          </Card>
        )}

        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button className="w-full" size="lg">
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

        <div className="text-center">
          <Button variant="ghost" size="sm" onClick={handleLogout}>
            <LogOut className="h-4 w-4 mr-2" />
            {t("sites.logout")}
          </Button>
        </div>
      </div>
    </div>
  );
}
