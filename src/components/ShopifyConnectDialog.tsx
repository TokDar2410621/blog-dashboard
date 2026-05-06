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
import { ShoppingBag, Loader2, ArrowRight, ExternalLink, AlertCircle } from "lucide-react";
import { toast } from "sonner";
import { BrandingPreview } from "@/components/BrandingPreview";

type ShopifyBlog = { id: string; title: string; handle: string };

type DiscoverResult = {
  valid: boolean;
  normalized_domain?: string;
  shop_name?: string;
  shop_email?: string;
  shop_currency?: string;
  shop_primary_locale?: string;
  custom_domain?: string;
  myshopify_domain?: string;
  blogs?: ShopifyBlog[];
  primary_blog_id?: string;
  error?: string;
};

type ConnectResult = {
  site: { id: number; name: string; domain: string; shopify_domain: string };
  shop: { name: string; email: string; currency: string; custom_domain: string };
  blogs: ShopifyBlog[];
};

type Props = {
  open: boolean;
  onOpenChange: (o: boolean) => void;
};

export function ShopifyConnectDialog({ open, onOpenChange }: Props) {
  const navigate = useNavigate();
  const [step, setStep] = useState<1 | 2>(1);
  const [domain, setDomain] = useState("");
  const [token, setToken] = useState("");
  const [discovery, setDiscovery] = useState<DiscoverResult | null>(null);
  const [selectedBlogId, setSelectedBlogId] = useState<string>("");
  const [themeConfig, setThemeConfig] = useState<Record<string, string> | null>(null);

  const reset = () => {
    setStep(1);
    setDomain("");
    setToken("");
    setDiscovery(null);
    setSelectedBlogId("");
    setThemeConfig(null);
  };

  const handleClose = (o: boolean) => {
    if (!o) reset();
    onOpenChange(o);
  };

  const discoverMutation = useMutation({
    mutationFn: async () => {
      const res = await authFetch("/shopify/discover/", {
        method: "POST",
        body: JSON.stringify({ domain, token }),
      });
      const data = (await res.json()) as DiscoverResult;
      if (!res.ok || !data.valid) {
        throw new Error(data.error || "Boutique Shopify non détectée.");
      }
      return data;
    },
    onSuccess: (d) => {
      setDiscovery(d);
      setSelectedBlogId(d.primary_blog_id || (d.blogs?.[0]?.id ?? ""));
      setStep(2);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const connectMutation = useMutation({
    mutationFn: async (): Promise<ConnectResult> => {
      const res = await authFetch("/shopify/connect/", {
        method: "POST",
        body: JSON.stringify({
          domain,
          token,
          blog_id: selectedBlogId,
          theme_config: themeConfig || undefined,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Erreur de connexion Shopify.");
      return data;
    },
    onSuccess: (data) => {
      toast.success(`Boutique connectée : ${data.shop.name}`);
      handleClose(false);
      navigate(`/dashboard/${data.site.id}/`);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <ShoppingBag className="h-5 w-5 text-primary" />
            Connecter ta boutique Shopify
          </DialogTitle>
          <DialogDescription>
            On publie tes articles directement dans le blog natif de ta boutique
            Shopify, sur ton domaine — SEO 100 % bonifié.
          </DialogDescription>
        </DialogHeader>

        {step === 1 && (
          <div className="space-y-4">
            <div className="rounded-lg border border-amber-500/30 bg-amber-500/5 p-3 text-sm">
              <div className="flex items-start gap-2">
                <AlertCircle className="h-4 w-4 mt-0.5 text-amber-500 shrink-0" />
                <div>
                  <p className="font-medium mb-1">
                    Crée d'abord une "Custom App" Shopify
                  </p>
                  <ol className="list-decimal list-inside text-xs space-y-1 text-muted-foreground">
                    <li>
                      Shopify Admin → Settings → Apps and sales channels →{" "}
                      <strong>Develop apps</strong>
                    </li>
                    <li>
                      <strong>Create an app</strong> → nomme-la "Blog Dashboard"
                    </li>
                    <li>
                      Onglet <strong>Configuration</strong> → Admin API access
                      scopes → coche{" "}
                      <code className="bg-muted px-1 rounded">write_content</code>
                    </li>
                    <li>
                      <strong>Install app</strong> → copie le{" "}
                      <strong>Admin API access token</strong>
                    </li>
                  </ol>
                  <a
                    href="https://help.shopify.com/en/manual/apps/app-types/custom-apps"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-primary text-xs mt-2 hover:underline"
                  >
                    Doc Shopify <ExternalLink className="h-3 w-3" />
                  </a>
                </div>
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="shopify-domain">Domaine .myshopify.com</Label>
              <Input
                id="shopify-domain"
                placeholder="monstore.myshopify.com"
                value={domain}
                onChange={(e) => setDomain(e.target.value)}
                autoFocus
              />
              <p className="text-xs text-muted-foreground">
                Le domaine technique, pas ton domaine custom.
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="shopify-token">Admin API access token</Label>
              <Input
                id="shopify-token"
                type="password"
                placeholder="shpat_••••••••••••••••••••••••••••••••"
                value={token}
                onChange={(e) => setToken(e.target.value)}
                className="font-mono text-xs"
              />
            </div>

            <Button
              className="w-full"
              onClick={() => discoverMutation.mutate()}
              disabled={!domain.trim() || !token.trim() || discoverMutation.isPending}
            >
              {discoverMutation.isPending ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <ArrowRight className="h-4 w-4 mr-2" />
              )}
              Vérifier la connexion
            </Button>
          </div>
        )}

        {step === 2 && discovery && (
          <div className="space-y-4">
            <div className="rounded-lg border border-emerald-500/40 bg-emerald-500/5 p-3 text-sm">
              <div className="font-medium text-emerald-600 dark:text-emerald-400">
                Connecté à {discovery.shop_name}
              </div>
              <div className="text-xs text-muted-foreground mt-1 space-y-0.5">
                {discovery.custom_domain && (
                  <div>Domaine public : {discovery.custom_domain}</div>
                )}
                {discovery.shop_currency && (
                  <div>Devise : {discovery.shop_currency}</div>
                )}
                {discovery.shop_primary_locale && (
                  <div>Locale : {discovery.shop_primary_locale}</div>
                )}
              </div>
            </div>

            <BrandingPreview
              domain={
                discovery.custom_domain ||
                discovery.myshopify_domain ||
                discovery.normalized_domain ||
                domain
              }
              onAppliedChange={(tc) => setThemeConfig(tc)}
            />

            <div className="space-y-2">
              <Label>
                Choisis le blog où publier{" "}
                <span className="text-muted-foreground text-xs">
                  ({discovery.blogs?.length ?? 0}{" "}
                  {(discovery.blogs?.length ?? 0) > 1 ? "blogs trouvés" : "blog trouvé"})
                </span>
              </Label>
              <div className="space-y-2">
                {(discovery.blogs ?? []).map((b) => (
                  <label
                    key={b.id}
                    className={`flex items-center gap-3 rounded border p-3 cursor-pointer transition-colors ${
                      selectedBlogId === b.id
                        ? "border-primary bg-primary/5"
                        : "border-border/50 hover:border-border"
                    }`}
                  >
                    <input
                      type="radio"
                      name="blog"
                      value={b.id}
                      checked={selectedBlogId === b.id}
                      onChange={() => setSelectedBlogId(b.id)}
                      className="accent-primary"
                    />
                    <div className="flex-1">
                      <div className="font-medium text-sm">{b.title}</div>
                      <div className="text-xs text-muted-foreground font-mono">
                        /blogs/{b.handle}
                      </div>
                    </div>
                  </label>
                ))}
              </div>
              {(discovery.blogs?.length ?? 0) === 0 && (
                <p className="text-xs text-amber-500">
                  Aucun blog dans cette boutique. Crée-en un dans Shopify Admin → Online
                  Store → Blog posts → Manage blogs.
                </p>
              )}
            </div>

            <div className="flex gap-2">
              <Button variant="outline" onClick={() => setStep(1)} className="flex-1">
                Retour
              </Button>
              <Button
                className="flex-1"
                onClick={() => connectMutation.mutate()}
                disabled={!selectedBlogId || connectMutation.isPending}
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
