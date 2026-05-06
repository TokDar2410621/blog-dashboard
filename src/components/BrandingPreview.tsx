import { useEffect, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { authFetch } from "@/lib/api-client";
import { Loader2, Palette, Check } from "lucide-react";

type ThemeConfig = {
  brand_color: string;
  brand_fg: string;
  font_sans: string;
  font_display: string;
  logo_url: string;
};

type ScanResult = {
  success: boolean;
  theme_config: ThemeConfig;
  meta: { site_name: string; description: string };
  error?: string;
};

type Props = {
  domain: string;
  onAppliedChange: (themeConfig: ThemeConfig | null) => void;
};

/** Auto-scans a domain when it becomes non-empty, shows logo + colors + sample
 * button preview, and lets the user toggle whether to apply the detected
 * branding to the new site. The parent receives the active themeConfig (or null
 * if the user disabled it) via `onAppliedChange`. */
export function BrandingPreview({ domain, onAppliedChange }: Props) {
  const [result, setResult] = useState<ScanResult | null>(null);
  const [apply, setApply] = useState(true);

  const scan = useMutation({
    mutationFn: async (url: string): Promise<ScanResult> => {
      const res = await authFetch("/branding/scan/", {
        method: "POST",
        body: JSON.stringify({ url }),
      });
      const data = (await res.json()) as ScanResult;
      if (!res.ok || !data.success) throw new Error(data.error || "scan failed");
      return data;
    },
    onSuccess: (data) => {
      setResult(data);
      onAppliedChange(apply ? data.theme_config : null);
    },
    onError: () => {
      // Silent fail — branding is best-effort enhancement, not a blocker.
      setResult(null);
      onAppliedChange(null);
    },
  });

  useEffect(() => {
    const trimmed = domain?.trim();
    if (!trimmed || trimmed.length < 4) {
      setResult(null);
      onAppliedChange(null);
      return;
    }
    scan.mutate(trimmed);
    // Re-scan only when domain changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [domain]);

  // Push toggle change up
  useEffect(() => {
    if (result?.theme_config) {
      onAppliedChange(apply ? result.theme_config : null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [apply]);

  if (scan.isPending) {
    return (
      <div className="rounded border border-border/40 bg-muted/30 p-3 text-xs text-muted-foreground flex items-center gap-2">
        <Loader2 className="h-3.5 w-3.5 animate-spin" />
        Détection du branding sur {domain}...
      </div>
    );
  }

  if (!result) return null;

  const tc = result.theme_config;
  const sample = result.meta.site_name || domain;

  return (
    <div className="rounded border border-emerald-500/30 bg-emerald-500/5 p-3 text-sm space-y-3">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-emerald-600 dark:text-emerald-400">
          <Palette className="h-4 w-4" />
          <span className="font-medium">Branding détecté</span>
        </div>
        <label className="flex items-center gap-1.5 text-xs cursor-pointer select-none">
          <input
            type="checkbox"
            checked={apply}
            onChange={(e) => setApply(e.target.checked)}
            className="accent-primary"
          />
          Appliquer
        </label>
      </div>

      <div className="flex items-center gap-3">
        {tc.logo_url ? (
          <img
            src={tc.logo_url}
            alt="logo"
            className="h-10 w-10 rounded border border-border/50 bg-background object-contain"
            onError={(e) => {
              (e.target as HTMLImageElement).style.display = "none";
            }}
          />
        ) : (
          <div className="h-10 w-10 rounded border border-border/50 bg-background flex items-center justify-center text-xs text-muted-foreground">
            ?
          </div>
        )}

        <div className="flex-1 min-w-0">
          <div className="font-medium truncate text-sm">{sample}</div>
          <div className="text-[11px] text-muted-foreground truncate">
            {tc.font_sans || "—"} {tc.font_display && tc.font_display !== tc.font_sans ? `+ ${tc.font_display}` : ""}
          </div>
        </div>

        {/* Sample button rendered with the detected colors */}
        <div
          className="text-[11px] font-medium px-2.5 py-1 rounded border"
          style={{
            backgroundColor: tc.brand_color,
            color: tc.brand_fg,
            borderColor: tc.brand_color,
          }}
        >
          Bouton
        </div>
      </div>

      {!apply && (
        <p className="text-[11px] text-muted-foreground italic">
          Tu pourras toujours scanner depuis Site Settings après la connexion.
        </p>
      )}
      {apply && (
        <p className="text-[11px] text-muted-foreground flex items-center gap-1">
          <Check className="h-3 w-3 text-emerald-500" />
          Sera appliqué à la connexion. Modifiable dans Site Settings.
        </p>
      )}
    </div>
  );
}
