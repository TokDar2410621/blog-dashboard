"use client";

import { Loader2, Sparkles, Palette, ImageIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useSettings } from "./useSettings";

export default function Branding() {
  const {
    domain,
    ogImageUrl, setOgImageUrl,
    brandColor, setBrandColor,
    brandFg, setBrandFg,
    logoUrl, setLogoUrl,
    scannedMeta,
    scanBranding,
  } = useSettings();

  return (
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

        <div className="rounded border border-border/50 bg-muted/30 p-3 space-y-2">
          <div className="flex items-center justify-between gap-2">
            <div className="text-sm">
              <div className="font-medium">Détecter automatiquement le branding</div>
              <div className="text-xs text-muted-foreground">
                Scanne {domain || "ton domaine"} et remplit couleur, logo et fonts.
              </div>
            </div>
            <Button
              size="sm"
              variant="outline"
              disabled={!domain.trim() || scanBranding.isPending}
              onClick={() => scanBranding.mutate()}
            >
              {scanBranding.isPending ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <Sparkles className="h-4 w-4 mr-2" />
              )}
              Scanner
            </Button>
          </div>
          {scannedMeta && (
            <div className="text-xs text-muted-foreground border-t border-border/50 pt-2 flex items-center gap-3">
              {scannedMeta.logo_url && (
                <img
                  src={scannedMeta.logo_url}
                  alt="logo détecté"
                  className="h-6 w-6 rounded border"
                  onError={(e) => {
                    (e.target as HTMLImageElement).style.display = "none";
                  }}
                />
              )}
              <span>
                {scannedMeta.site_name || "?"} · couleur {scannedMeta.brand_color}
                {scannedMeta.font_sans ? ` · ${scannedMeta.font_sans}` : ""}
              </span>
            </div>
          )}
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div className="space-y-1">
            <Label className="text-xs">Couleur principale</Label>
            <div className="flex gap-2">
              <Input
                value={brandColor}
                onChange={(e) => setBrandColor(e.target.value)}
                placeholder="#2563eb"
                className="font-mono text-sm"
              />
              <input
                type="color"
                value={brandColor || "#2563eb"}
                onChange={(e) => setBrandColor(e.target.value)}
                className="h-9 w-12 rounded border cursor-pointer"
              />
            </div>
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Couleur du texte sur la couleur principale</Label>
            <div className="flex gap-2">
              <Input
                value={brandFg}
                onChange={(e) => setBrandFg(e.target.value)}
                placeholder="#ffffff"
                className="font-mono text-sm"
              />
              <input
                type="color"
                value={brandFg || "#ffffff"}
                onChange={(e) => setBrandFg(e.target.value)}
                className="h-9 w-12 rounded border cursor-pointer"
              />
            </div>
          </div>
          <div className="space-y-1">
            <Label className="text-xs">Logo URL</Label>
            <Input
              value={logoUrl}
              onChange={(e) => setLogoUrl(e.target.value)}
              placeholder="https://..."
              type="url"
              className="text-sm"
            />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
