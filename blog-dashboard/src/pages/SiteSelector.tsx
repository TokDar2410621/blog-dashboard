import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
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
import {
  getSites,
  addSite,
  removeSite,
  setActiveSite,
  generateSiteId,
  type SavedSite,
} from "@/lib/sites";
import { login } from "@/lib/api-client";
import {
  Globe,
  Plus,
  Trash2,
  LogIn,
  Loader2,
  Newspaper,
} from "lucide-react";
import { toast } from "sonner";

export default function SiteSelector() {
  const navigate = useNavigate();
  const [sites, setSites] = useState<SavedSite[]>(getSites());
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);

  // Form state
  const [name, setName] = useState("");
  const [apiUrl, setApiUrl] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  const handleConnect = (site: SavedSite) => {
    setActiveSite(site.id);
    navigate("/dashboard");
  };

  const handleDelete = (id: string) => {
    removeSite(id);
    setSites(getSites());
    toast.success("Site supprime");
  };

  const handleAdd = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    // Normalize URL
    let url = apiUrl.trim();
    if (url.endsWith("/")) url = url.slice(0, -1);
    if (!url.endsWith("/api")) url += "/api";

    try {
      // Test connection with login
      const tokens = await login(url, username, password);

      const site: SavedSite = {
        id: generateSiteId(),
        name: name.trim(),
        apiUrl: url,
        token: tokens.access,
        refreshToken: tokens.refresh,
      };

      addSite(site);
      setSites(getSites());
      setOpen(false);
      setName("");
      setApiUrl("");
      setUsername("");
      setPassword("");
      toast.success("Site ajoute avec succes!");
    } catch {
      toast.error("Impossible de se connecter. Verifiez l'URL et les identifiants.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-background flex items-center justify-center p-4">
      <div className="w-full max-w-2xl space-y-6">
        {/* Header */}
        <div className="text-center space-y-2">
          <div className="flex items-center justify-center gap-2 mb-4">
            <Newspaper className="h-8 w-8 text-primary" />
            <h1 className="text-3xl font-bold">Blog Dashboard</h1>
          </div>
          <p className="text-muted-foreground">
            Gerez vos blogs Django depuis une seule interface
          </p>
        </div>

        {/* Sites List */}
        {sites.length > 0 && (
          <div className="space-y-3">
            {sites.map((site) => (
              <Card
                key={site.id}
                className="hover:border-primary/50 transition-colors"
              >
                <CardContent className="flex items-center justify-between p-4">
                  <div className="flex items-center gap-3">
                    <Globe className="h-5 w-5 text-muted-foreground" />
                    <div>
                      <p className="font-medium">{site.name}</p>
                      <p className="text-sm text-muted-foreground">
                        {site.apiUrl}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      size="sm"
                      onClick={() => handleConnect(site)}
                    >
                      <LogIn className="h-4 w-4 mr-2" />
                      Ouvrir
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => handleDelete(site.id)}
                    >
                      <Trash2 className="h-4 w-4 text-destructive" />
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}

        {/* Empty State */}
        {sites.length === 0 && (
          <Card>
            <CardContent className="py-12 text-center">
              <Globe className="h-12 w-12 mx-auto text-muted-foreground mb-4" />
              <p className="text-muted-foreground">
                Aucun site configure. Ajoutez votre premier blog!
              </p>
            </CardContent>
          </Card>
        )}

        {/* Add Site Dialog */}
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button className="w-full" size="lg">
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
                <Input
                  id="name"
                  placeholder="Mon blog"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="apiUrl">URL de l'API</Label>
                <Input
                  id="apiUrl"
                  placeholder="https://monsite.railway.app/api"
                  value={apiUrl}
                  onChange={(e) => setApiUrl(e.target.value)}
                  required
                />
                <p className="text-xs text-muted-foreground">
                  L'URL de base de l'API Django REST
                </p>
              </div>
              <div className="space-y-2">
                <Label htmlFor="username">Nom d'utilisateur</Label>
                <Input
                  id="username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  required
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="password">Mot de passe</Label>
                <Input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
              </div>
              <Button type="submit" className="w-full" disabled={loading}>
                {loading ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Connexion en cours...
                  </>
                ) : (
                  "Se connecter et sauvegarder"
                )}
              </Button>
            </form>
          </DialogContent>
        </Dialog>

        <p className="text-center text-xs text-muted-foreground">
          Compatible avec tout backend Django Blog avec JWT
        </p>
      </div>
    </div>
  );
}
