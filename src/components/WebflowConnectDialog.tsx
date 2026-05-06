import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { authFetch } from "@/lib/api-client";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Layers,
  Loader2,
  ArrowRight,
  ExternalLink,
  AlertCircle,
  CheckCircle2,
} from "lucide-react";
import { toast } from "sonner";

type WebflowSite = {
  id: string;
  displayName: string;
  shortName: string;
  customDomains: string[];
  previewUrl: string;
};

type WebflowCollection = {
  id: string;
  displayName: string;
  singularName: string;
  slug: string;
  field_map: Record<string, string> | null;
  fields: { slug: string; displayName: string; type: string; required?: boolean }[];
  looks_like_blog: boolean;
};

type DiscoverResult = {
  valid: boolean;
  sites?: WebflowSite[];
  error?: string;
};

type ConnectResult = {
  site: { id: number; name: string; domain: string };
  webflow_site: { displayName: string; shortName: string; customDomains: string[] };
  field_map: Record<string, string>;
};

type Props = {
  open: boolean;
  onOpenChange: (o: boolean) => void;
};

export function WebflowConnectDialog({ open, onOpenChange }: Props) {
  const navigate = useNavigate();
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [token, setToken] = useState("");
  const [sites, setSites] = useState<WebflowSite[]>([]);
  const [chosenSite, setChosenSite] = useState<WebflowSite | null>(null);
  const [collections, setCollections] = useState<WebflowCollection[]>([]);
  const [chosenCollectionId, setChosenCollectionId] = useState<string>("");

  const reset = () => {
    setStep(1);
    setToken("");
    setSites([]);
    setChosenSite(null);
    setCollections([]);
    setChosenCollectionId("");
  };

  const handleClose = (o: boolean) => {
    if (!o) reset();
    onOpenChange(o);
  };

  const discoverMutation = useMutation({
    mutationFn: async () => {
      const res = await authFetch("/webflow/discover/", {
        method: "POST",
        body: JSON.stringify({ token }),
      });
      const data = (await res.json()) as DiscoverResult;
      if (!res.ok || !data.valid) {
        throw new Error(data.error || "Token Webflow invalide.");
      }
      return data;
    },
    onSuccess: (d) => {
      setSites(d.sites || []);
      setStep(2);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const collectionsMutation = useMutation({
    mutationFn: async (siteId: string) => {
      const res = await authFetch("/webflow/collections/", {
        method: "POST",
        body: JSON.stringify({ token, site_id: siteId }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Erreur récupération collections.");
      return data.collections as WebflowCollection[];
    },
    onSuccess: (cols) => {
      setCollections(cols);
      // Pre-select the first blog-looking collection.
      const blogish = cols.find((c) => c.looks_like_blog) || cols[0];
      if (blogish) setChosenCollectionId(blogish.id);
      setStep(3);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const connectMutation = useMutation({
    mutationFn: async (): Promise<ConnectResult> => {
      const collection = collections.find((c) => c.id === chosenCollectionId);
      const res = await authFetch("/webflow/connect/", {
        method: "POST",
        body: JSON.stringify({
          token,
          site_id: chosenSite!.id,
          collection_id: chosenCollectionId,
          field_map: collection?.field_map || undefined,
          name: chosenSite!.displayName,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Erreur connexion Webflow.");
      return data;
    },
    onSuccess: (data) => {
      toast.success(`Site Webflow connecté : ${data.webflow_site.displayName}`);
      handleClose(false);
      navigate(`/dashboard/${data.site.id}/`);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Layers className="h-5 w-5 text-primary" />
            Connecter ton site Webflow
          </DialogTitle>
          <DialogDescription>
            On publie tes articles directement dans le CMS de ton site Webflow,
            sur ton domaine — SEO 100 % bonifié.
          </DialogDescription>
        </DialogHeader>

        {step === 1 && (
          <div className="space-y-4">
            <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-3 text-sm">
              <div className="flex items-start gap-2">
                <AlertCircle className="h-4 w-4 mt-0.5 text-amber-500 shrink-0" />
                <div>
                  <p className="font-medium mb-1">
                    Génère un Site Token Webflow
                  </p>
                  <ol className="list-decimal list-inside text-xs space-y-1 text-muted-foreground">
                    <li>Webflow → ton Project → Project Settings</li>
                    <li>Onglet <strong>Apps & Integrations</strong> → API access</li>
                    <li>
                      <strong>Generate API token</strong> avec scopes{" "}
                      <code className="bg-muted px-1 rounded">CMS:read+write</code>
                    </li>
                    <li>Copie le token (commence par un long string)</li>
                  </ol>
                  <a
                    href="https://help.webflow.com/hc/en-us/articles/33961755031059-Intro-to-the-Webflow-API"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-primary text-xs mt-2 hover:underline"
                  >
                    Doc Webflow <ExternalLink className="h-3 w-3" />
                  </a>
                </div>
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="webflow-token">Site API Token</Label>
              <Input
                id="webflow-token"
                type="password"
                placeholder="••••••••••••••••••••••••••••••••••••••••"
                value={token}
                onChange={(e) => setToken(e.target.value)}
                className="font-mono text-xs"
                autoFocus
              />
            </div>

            <Button
              className="w-full"
              onClick={() => discoverMutation.mutate()}
              disabled={!token.trim() || discoverMutation.isPending}
            >
              {discoverMutation.isPending ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <ArrowRight className="h-4 w-4 mr-2" />
              )}
              Vérifier le token
            </Button>
          </div>
        )}

        {step === 2 && (
          <div className="space-y-4">
            <div>
              <Label className="mb-2 block">Choisis ton site Webflow</Label>
              <div className="space-y-2">
                {sites.length === 0 && (
                  <p className="text-sm text-muted-foreground">
                    Ce token n'a accès à aucun site.
                  </p>
                )}
                {sites.map((s) => (
                  <button
                    key={s.id}
                    onClick={() => {
                      setChosenSite(s);
                      collectionsMutation.mutate(s.id);
                    }}
                    disabled={collectionsMutation.isPending}
                    className="w-full text-left rounded border border-border/50 p-3 hover:border-primary transition-colors disabled:opacity-50"
                  >
                    <div className="font-medium text-sm">{s.displayName}</div>
                    <div className="text-xs text-muted-foreground mt-0.5">
                      {s.customDomains[0] || `${s.shortName}.webflow.io`}
                    </div>
                  </button>
                ))}
              </div>
            </div>
            {collectionsMutation.isPending && (
              <div className="text-sm text-muted-foreground flex items-center gap-2">
                <Loader2 className="h-4 w-4 animate-spin" />
                Récupération des collections CMS...
              </div>
            )}
            <Button variant="outline" onClick={() => setStep(1)} className="w-full">
              Retour
            </Button>
          </div>
        )}

        {step === 3 && chosenSite && (
          <div className="space-y-4">
            <div className="rounded-lg border border-emerald-500/40 bg-emerald-500/5 p-3 text-sm">
              <div className="font-medium text-emerald-600 dark:text-emerald-400 flex items-center gap-2">
                <CheckCircle2 className="h-4 w-4" />
                {chosenSite.displayName}
              </div>
              <div className="text-xs text-muted-foreground mt-1">
                {chosenSite.customDomains[0] || `${chosenSite.shortName}.webflow.io`}
              </div>
            </div>

            <div className="space-y-2">
              <Label>
                Choisis la collection CMS où publier les articles
              </Label>
              {collections.length === 0 ? (
                <p className="text-sm text-amber-500">
                  Aucune collection trouvée. Crée-en une dans Webflow Designer
                  (CMS panel → Create new collection).
                </p>
              ) : (
                <div className="space-y-2">
                  {collections.map((c) => (
                    <label
                      key={c.id}
                      className={`flex items-start gap-3 rounded border p-3 cursor-pointer transition-colors ${
                        chosenCollectionId === c.id
                          ? "border-primary bg-primary/5"
                          : "border-border/50 hover:border-border"
                      }`}
                    >
                      <input
                        type="radio"
                        name="collection"
                        value={c.id}
                        checked={chosenCollectionId === c.id}
                        onChange={() => setChosenCollectionId(c.id)}
                        className="accent-primary mt-1"
                      />
                      <div className="flex-1 min-w-0">
                        <div className="font-medium text-sm flex items-center gap-2">
                          {c.displayName}
                          {c.looks_like_blog && (
                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
                              Blog
                            </span>
                          )}
                          {!c.looks_like_blog && (
                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-600 dark:text-amber-400">
                              Pas de Rich Text
                            </span>
                          )}
                        </div>
                        <div className="text-xs text-muted-foreground font-mono mt-0.5">
                          /{c.slug}
                        </div>
                        {c.field_map && c.looks_like_blog && (
                          <div className="text-[11px] text-muted-foreground mt-1">
                            Mapping détecté : {c.field_map.title} (titre) ·{" "}
                            {c.field_map.body} (corps)
                            {c.field_map.image ? ` · ${c.field_map.image} (image)` : ""}
                          </div>
                        )}
                      </div>
                    </label>
                  ))}
                </div>
              )}
              <p className="text-[11px] text-muted-foreground">
                On a besoin d'une collection avec un champ Rich Text pour le
                corps de l'article. Si la tienne n'en a pas, ajoute-le dans
                Webflow Designer.
              </p>
            </div>

            <div className="flex gap-2">
              <Button variant="outline" onClick={() => setStep(2)} className="flex-1">
                Retour
              </Button>
              <Button
                className="flex-1"
                onClick={() => connectMutation.mutate()}
                disabled={!chosenCollectionId || connectMutation.isPending}
              >
                {connectMutation.isPending ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : null}
                Connecter
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
