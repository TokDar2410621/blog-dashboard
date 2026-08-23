"use client";

/**
 * Strategic SEO Opportunities.
 *
 * For each non-info-intent keyword without a matching landing, the backend
 * Claude engine produces a structured page concept (hook, capture, conversion
 * path) + traffic estimate. This page renders those concepts as rich cards
 * the user reviews -> approves (creates the landing) or dismisses.
 *
 * /api/v1/sites/<id>/strategic-opportunities/
 */
import { useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  PenLine,
  RefreshCw,
  Loader2,
  AlertTriangle,
  TrendingUp,
  Target,
  ArrowRight,
  ExternalLink,
  X,
  CheckCircle2,
  Copy,
  EyeOff,
  Lightbulb,
  Quote,
  Layers,
  Globe,
  Wrench,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { PageBreadcrumb } from "@/components/PageBreadcrumb";
import { useSite } from "@/hooks/useDashboard";
import {
  ApiError,
  listStrategicOpportunities,
  refreshStrategicOpportunities,
  actionStrategicOpportunity,
  exportOpportunityPrompt,
  exportLandingPrompt,
  type StrategicOpportunity,
} from "@/lib/api-client";

// ---------------------------------------------------------------------------
// Display helpers (kept in this file - they're 100% tied to the card layout)
// ---------------------------------------------------------------------------

function priorityClasses(p: StrategicOpportunity["priority"]) {
  if (p === "high") {
    return "border-emerald-500/40 bg-emerald-500/[0.06]";
  }
  if (p === "medium") {
    return "border-amber-500/30 bg-amber-500/[0.04]";
  }
  return "border-border bg-card";
}

function priorityBadge(p: StrategicOpportunity["priority"]) {
  if (p === "high") {
    return (
      <Badge className="bg-emerald-500/15 text-emerald-400 border-emerald-500/30 border">
        Priorité haute
      </Badge>
    );
  }
  if (p === "medium") {
    return (
      <Badge className="bg-amber-500/15 text-amber-400 border-amber-500/30 border">
        Priorité moyenne
      </Badge>
    );
  }
  return (
    <Badge variant="outline" className="text-muted-foreground">
      Priorité basse
    </Badge>
  );
}

function intentLabel(intent: StrategicOpportunity["intent"]) {
  switch (intent) {
    case "transactional":
      return "Transactionnel";
    case "commercial":
      return "Commercial";
    case "local":
      return "Local";
    default:
      return "Informationnel";
  }
}

const PAGE_TYPE_LABELS: Record<string, string> = {
  tool_landing: "Outil gratuit",
  service_page: "Page service",
  comparison: "Comparatif",
  guide_pillar: "Guide pilier",
  quiz_landing: "Quiz",
  calculator: "Calculateur",
  local_landing: "Landing locale",
  lead_magnet: "Lead magnet",
};

// Page types whose value IS an interactive tool (configurator, calculator,
// quiz, live tool). Gridar generates landing/article COPY, not a working
// widget - so when one of these has no existing asset to lean on
// (asset_match === false), "Créer cette page" would ship a landing that
// promises a tool that doesn't exist. Those are routed to the "à construire"
// section, where the honest deliverable is the build prompt for the user's
// dev / AI (build_opportunity_prompt already asks it to implement the
// mechanism, not just describe it). Content page types (guide, comparatif,
// service, landing locale, lead magnet) stay directly generatable.
const INTERACTIVE_PAGE_TYPES = new Set([
  "tool_landing",
  "calculator",
  "quiz_landing",
]);

function requiresCustomAsset(
  concept: StrategicOpportunity["concept"] | undefined,
): boolean {
  if (!concept) return false;
  return concept.asset_match === false &&
    INTERACTIVE_PAGE_TYPES.has(concept.page_type);
}

function formatRange(range: [number, number]): string {
  const [lo, hi] = range;
  if (lo <= 0 && hi <= 0) return "0";
  if (lo === hi) return String(lo);
  return `${lo}-${hi}`;
}

// ---------------------------------------------------------------------------
// Card
// ---------------------------------------------------------------------------

function OpportunityCard({
  opp,
  siteId,
  needsCustomAsset = false,
  siteIsExternal = false,
}: {
  opp: StrategicOpportunity;
  siteId: number;
  needsCustomAsset?: boolean;
  siteIsExternal?: boolean;
}) {
  const qc = useQueryClient();

  const approveMutation = useMutation({
    mutationFn: () => actionStrategicOpportunity(siteId, opp.id, "approve"),
    onSuccess: (data) => {
      toast.success(
        data.landing_slug
          ? `Landing créée : /${data.landing_slug}`
          : "Landing créée.",
      );
      qc.invalidateQueries({ queryKey: ["opportunities", siteId] });
    },
    onError: (err: Error) =>
      toast.error(err.message || "Création de la landing échouée."),
  });

  const dismissMutation = useMutation({
    mutationFn: () => actionStrategicOpportunity(siteId, opp.id, "dismiss"),
    onSuccess: () => {
      toast("Opportunité écartée.");
      qc.invalidateQueries({ queryKey: ["opportunities", siteId] });
    },
    onError: (err: Error) =>
      toast.error(err.message || "Impossible d'écarter."),
  });

  const restoreMutation = useMutation({
    mutationFn: () => actionStrategicOpportunity(siteId, opp.id, "restore"),
    onSuccess: () => {
      toast("Opportunité restaurée.");
      qc.invalidateQueries({ queryKey: ["opportunities", siteId] });
    },
    onError: (err: Error) =>
      toast.error(err.message || "Restauration échouée."),
  });

  // "Copier le prompt IA" - delivery channel for users who build their site
  // with an AI tool (ChatGPT, Lovable, v0, Bolt) and have no CMS. If a
  // landing was already generated we export the integrate-verbatim prompt
  // (real copy); otherwise the write-from-brief prompt (concept only).
  //
  // Clipboard subtlety: Safari/iOS invalidate the click's user activation
  // as soon as we await a network call, so a plain writeText-after-fetch
  // rejects with NotAllowedError there. The promise-backed ClipboardItem
  // form starts the clipboard write synchronously inside the gesture and
  // lets the payload resolve later - supported by Safari 13.1+, Chrome
  // 127+, Firefox 127+. When the clipboard is still blocked we keep the
  // fetched prompt and surface it for manual copy instead of losing it.
  const [manualPrompt, setManualPrompt] = useState<string | null>(null);
  const promptMutation = useMutation({
    mutationFn: async () => {
      let fetchError: Error | null = null;
      let prompt = "";
      const textPromise = (
        opp.generated_landing_id
          ? exportLandingPrompt(siteId, opp.generated_landing_id)
          : exportOpportunityPrompt(siteId, opp.id)
      )
        .then((res) => {
          prompt = res.prompt;
          return res.prompt;
        })
        .catch((e: Error) => {
          fetchError = e;
          throw e;
        });

      try {
        if (
          typeof ClipboardItem !== "undefined" &&
          navigator.clipboard &&
          "write" in navigator.clipboard
        ) {
          await navigator.clipboard.write([
            new ClipboardItem({
              "text/plain": textPromise.then(
                (p) => new Blob([p], { type: "text/plain" }),
              ),
            }),
          ]);
        } else {
          await navigator.clipboard.writeText(await textPromise);
        }
      } catch (clipErr) {
        // Make sure the fetch settled before deciding what failed.
        await textPromise.catch(() => {});
        if (fetchError) throw fetchError;
        if (prompt) {
          // API succeeded, clipboard refused: hand the text over manually.
          setManualPrompt(prompt);
          throw new Error("CLIPBOARD_BLOCKED");
        }
        throw clipErr;
      }
      return true;
    },
    onSuccess: () => {
      setManualPrompt(null);
      toast.success(
        "Prompt copié. Colle-le dans ChatGPT, Lovable, v0 ou ton IA préférée : elle crée la page dans TON code.",
      );
    },
    onError: (err: Error) => {
      if (err.message === "CLIPBOARD_BLOCKED") {
        toast.warning(
          "Copie automatique bloquée par le navigateur. Le prompt est affiché sous la carte : sélectionne-le et copie-le manuellement.",
        );
        return;
      }
      toast.error(
        err instanceof ApiError ? err.message : "Export du prompt échoué.",
      );
    },
  });

  const concept = opp.concept;
  const estimate = opp.estimate;
  const isDone = opp.status === "done";
  const isDismissed = opp.status === "dismissed";
  const pageTypeLabel = PAGE_TYPE_LABELS[concept?.page_type] || "Page";
  // The build prompt is the primary (and only honest) deliverable when either
  // the concept needs a custom interactive asset, OR the whole site is external
  // (Gridar can't publish a landing on a non-hosted site - "Créer cette page"
  // would only strand a draft in Gridar's DB).
  const needsPrompt = needsCustomAsset || siteIsExternal;

  return (
    <Card className={`relative ${priorityClasses(opp.priority)}`}>
      <CardHeader className="space-y-3">
        <div className="flex items-start justify-between gap-3 flex-wrap">
          <div className="flex items-center gap-2 flex-wrap">
            {priorityBadge(opp.priority)}
            <Badge variant="outline" className="border-primary/30 text-primary">
              <Target className="h-3 w-3 mr-1" />
              {intentLabel(opp.intent)}
            </Badge>
            <Badge variant="outline" className="text-muted-foreground">
              <Layers className="h-3 w-3 mr-1" />
              {pageTypeLabel}
            </Badge>
            {opp.current_position && (
              <Badge variant="outline" className="text-muted-foreground">
                Rang actuel #{opp.current_position}
              </Badge>
            )}
            {!concept?.asset_match && (
              <Badge
                variant="outline"
                className="border-amber-500/30 text-amber-400"
              >
                <AlertTriangle className="h-3 w-3 mr-1" />
                Asset à créer
              </Badge>
            )}
          </div>
          {isDone && (
            <Badge className="bg-emerald-500 text-white border-emerald-500">
              <CheckCircle2 className="h-3 w-3 mr-1" />
              Page créée
            </Badge>
          )}
          {isDismissed && (
            <Badge variant="outline" className="text-muted-foreground">
              <EyeOff className="h-3 w-3 mr-1" />
              Écartée
            </Badge>
          )}
        </div>
        <div>
          <p className="text-xs font-mono uppercase tracking-wider text-muted-foreground mb-1">
            Mot-clé : {opp.keyword}
          </p>
          <CardTitle className="text-xl leading-snug">
            {concept?.page_concept || "Concept non disponible"}
          </CardTitle>
        </div>
      </CardHeader>

      <CardContent className="space-y-5">
        {concept?.suggested_title && (
          <div className="rounded-md border border-border bg-muted/30 p-3 space-y-1">
            <p className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">
              Titre proposé
            </p>
            <p className="font-semibold text-sm">{concept.suggested_title}</p>
            {concept.suggested_url_path && (
              <p className="text-xs text-muted-foreground font-mono">
                {concept.suggested_url_path}
              </p>
            )}
          </div>
        )}

        {concept?.hook && (
          <RecoBlock
            icon={Quote}
            label="Le hook"
            body={concept.hook}
            accent="emerald"
          />
        )}
        {concept?.capture_mechanism && (
          <RecoBlock
            icon={Target}
            label="Capture du lead"
            body={concept.capture_mechanism}
          />
        )}
        {concept?.conversion_path && (
          <RecoBlock
            icon={TrendingUp}
            label="Chemin de conversion"
            body={concept.conversion_path}
          />
        )}
        {concept?.angle && (
          <RecoBlock
            icon={Lightbulb}
            label="L'angle qui bat le SERP"
            body={concept.angle}
          />
        )}
        {concept?.why_this_works && (
          <RecoBlock
            icon={CheckCircle2}
            label="Pourquoi ça va convertir"
            body={concept.why_this_works}
          />
        )}

        {/* Quantitative estimate */}
        {estimate && (
          <div className="rounded-md border border-border bg-background/50 p-4 grid grid-cols-2 md:grid-cols-4 gap-4">
            <EstimateCell
              label="Recherches/mois"
              value={
                estimate.monthly_volume > 0
                  ? estimate.monthly_volume.toLocaleString("fr-CA")
                  : "inconnu"
              }
            />
            <EstimateCell
              label={`Visites (rang ${estimate.target_position})`}
              value={
                estimate.estimated_visits > 0
                  ? estimate.estimated_visits.toLocaleString("fr-CA")
                  : `~ ${estimate.qualitative_traffic}`
              }
            />
            <EstimateCell
              label="Leads/mois"
              value={formatRange(estimate.estimated_leads_range)}
            />
            <EstimateCell
              label="Clients/mois"
              value={formatRange(estimate.estimated_paid_range)}
              highlight
            />
          </div>
        )}

        {/* Asset note */}
        {concept?.asset_used && (
          <p className="text-xs text-muted-foreground">
            Asset exploité : <span className="text-foreground">{concept.asset_used}</span>
          </p>
        )}

        {/* External-site note: tell the user why, and point to the prompt. */}
        {siteIsExternal && (
          <p className="flex items-start gap-2 text-xs text-amber-400/90">
            <AlertTriangle className="h-3.5 w-3.5 shrink-0 mt-0.5" />
            <span>
              Site externe : Gridar ne publie pas cette landing ici. Le prompt de
              création la construit sur ton propre site.
              {isDone &&
                " (Une version brouillon a été générée côté Gridar, non publiée.)"}
            </span>
          </p>
        )}

        {/* Actions */}
        <div className="flex flex-wrap items-center gap-2 pt-2">
          {isDone && opp.generated_landing_slug && !siteIsExternal ? (
            <Button asChild variant="outline">
              <Link href={`/dashboard/${siteId}/parametres/general`}>
                <ExternalLink className="h-4 w-4 mr-2" />
                Voir la landing /{opp.generated_landing_slug}
              </Link>
            </Button>
          ) : isDismissed ? (
            <Button
              variant="outline"
              onClick={() => restoreMutation.mutate()}
              disabled={restoreMutation.isPending}
            >
              {restoreMutation.isPending ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <RefreshCw className="h-4 w-4 mr-2" />
              )}
              Restaurer
            </Button>
          ) : needsPrompt ? (
            // No honest one-click publish here: either the concept needs a
            // custom interactive asset, or the site is external (Gridar can't
            // publish a landing on it). The build prompt is the real deliverable
            // - it constructs the page in the user's own site/codebase.
            <>
              <Button
                onClick={() => promptMutation.mutate()}
                disabled={promptMutation.isPending}
                title="Colle ce prompt à ton dev ou à ton IA de code (Lovable, v0, Cursor...) : il construit la page directement dans ton propre site."
              >
                {promptMutation.isPending ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <Wrench className="h-4 w-4 mr-2" />
                )}
                Obtenir le prompt de création
              </Button>
              {!isDone && (
                <Button
                  variant="outline"
                  onClick={() => dismissMutation.mutate()}
                  disabled={dismissMutation.isPending}
                >
                  <X className="h-4 w-4 mr-2" />
                  Pas pertinent
                </Button>
              )}
            </>
          ) : (
            <>
              <Button
                onClick={() => approveMutation.mutate()}
                disabled={approveMutation.isPending}
              >
                {approveMutation.isPending ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Création en cours...
                  </>
                ) : (
                  <>
                    <PenLine className="h-4 w-4 mr-2" />
                    Créer cette page
                    <ArrowRight className="h-4 w-4 ml-2" />
                  </>
                )}
              </Button>
              <Button
                variant="outline"
                onClick={() => dismissMutation.mutate()}
                disabled={dismissMutation.isPending}
              >
                <X className="h-4 w-4 mr-2" />
                Pas pertinent
              </Button>
            </>
          )}
          {/* Generic prompt-copy button. Suppressed on "à construire" cards that
              are still open - those already show the build prompt as the
              primary action above. Kept for done/actionable cards. */}
          {!isDismissed && !(needsPrompt && !isDone) && (
            <Button
              variant="outline"
              onClick={() => promptMutation.mutate()}
              disabled={promptMutation.isPending}
              title="Pour les sites gérés avec une IA (ChatGPT, Lovable, v0...) : copie un prompt complet que ton IA utilise pour créer la page dans ton propre code."
            >
              {promptMutation.isPending ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <Copy className="h-4 w-4 mr-2" />
              )}
              Copier le prompt IA
            </Button>
          )}
        </div>

        {/* Manual copy fallback when the browser blocks programmatic
            clipboard access (Safari focus rules, permissions). */}
        {manualPrompt && (
          <div className="space-y-2 pt-2">
            <p className="text-xs text-muted-foreground">
              Copie automatique bloquée par le navigateur. Clique dans la zone
              (le texte se sélectionne tout seul) puis Ctrl+C / Cmd+C :
            </p>
            <textarea
              readOnly
              value={manualPrompt}
              rows={10}
              className="w-full rounded-md border border-border bg-muted/30 p-3 text-xs font-mono leading-relaxed"
              onFocus={(e) => e.currentTarget.select()}
            />
            <Button
              size="sm"
              variant="outline"
              onClick={() => setManualPrompt(null)}
            >
              <X className="h-3.5 w-3.5 mr-1.5" />
              Fermer
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Atoms
// ---------------------------------------------------------------------------

function RecoBlock({
  icon: Icon,
  label,
  body,
  accent,
}: {
  icon: typeof Lightbulb;
  label: string;
  body: string;
  accent?: "emerald";
}) {
  const iconColor =
    accent === "emerald" ? "text-emerald-400" : "text-primary";
  return (
    <div className="flex items-start gap-3">
      <span className="mt-0.5 shrink-0 h-7 w-7 rounded-md bg-muted/40 border border-border flex items-center justify-center">
        <Icon className={`h-3.5 w-3.5 ${iconColor}`} />
      </span>
      <div className="flex-1 min-w-0">
        <p className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-0.5">
          {label}
        </p>
        <p className="text-sm leading-relaxed">{body}</p>
      </div>
    </div>
  );
}

function EstimateCell({
  label,
  value,
  highlight,
}: {
  label: string;
  value: string;
  highlight?: boolean;
}) {
  return (
    <div>
      <p className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground mb-1">
        {label}
      </p>
      <p
        className={`font-mono tabular-nums ${
          highlight
            ? "text-emerald-400 text-lg font-bold"
            : "text-sm font-semibold"
        }`}
      >
        {value}
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function OpportunitiesPage() {
  const params = useParams<{ siteId: string }>();
  const siteId = params?.siteId;
  const sid = Number(siteId);
  const qc = useQueryClient();
  const { data: site } = useSite();
  const [showArchived, setShowArchived] = useState(false);

  const opportunitiesQuery = useQuery({
    queryKey: ["opportunities", sid, { archived: showArchived }],
    queryFn: () =>
      listStrategicOpportunities(sid, { includeArchived: showArchived }),
    enabled: !Number.isNaN(sid),
  });

  const refreshMutation = useMutation({
    mutationFn: () => refreshStrategicOpportunities(sid),
    onSuccess: (data) => {
      toast.success(
        `${data.count_refreshed} opportunité(s) régénérée(s) sur ${data.count_candidates} candidat(e)s.`,
      );
      if (data.count_skipped > 0) {
        toast.warning(
          `${data.count_skipped} mot(s)-clé(s) ignorés (LLM indisponible).`,
        );
      }
      qc.invalidateQueries({ queryKey: ["opportunities", sid] });
    },
    onError: (err: Error) =>
      toast.error(err.message || "Régénération échouée."),
  });

  const items = opportunitiesQuery.data?.results || [];
  const isLoading = opportunitiesQuery.isLoading;
  const isEmpty = !isLoading && items.length === 0;

  // is_hosted === false means the site stores content externally (external
  // Postgres or a connected CMS). Gridar can't publish a landing there, so the
  // whole "Créer cette page" one-click path is dishonest for these sites - the
  // prompt is the real deliverable. undefined (site still loading) is treated
  // as hosted to avoid a flash of the external UI.
  const siteIsExternal = site?.is_hosted === false;

  // Split by whether Gridar can actually deliver the page one-click, or whether
  // the concept needs a custom interactive asset built first (see
  // requiresCustomAsset). Keeps the two very different kinds of work honest and
  // visually separate instead of blending "click to generate" with "you need a
  // dev". Only relevant for hosted sites - external sites get one prompt-first
  // section.
  const actionable = items.filter((o) => !requiresCustomAsset(o.concept));
  const needsAsset = items.filter((o) => requiresCustomAsset(o.concept));

  return (
    <div className="space-y-6">
      <PageBreadcrumb trail={[{ label: "Opportunités SEO" }]} />

      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold tracking-tight flex items-center gap-2">
            <Lightbulb className="h-6 w-6 text-amber-400" />
            Opportunités stratégiques
          </h1>
          <p className="text-sm text-muted-foreground mt-1 max-w-2xl">
            Pour chaque mot-clé tracké à intent commercial ou transactionnel,
            Claude propose une page qui capitalise sur tes assets pour ranker
            ET convertir. Approuve celles qui matchent ta stratégie.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowArchived((v) => !v)}
          >
            {showArchived ? "Masquer les archivées" : "Voir les archivées"}
          </Button>
          <Button
            onClick={() => refreshMutation.mutate()}
            disabled={refreshMutation.isPending}
          >
            {refreshMutation.isPending ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Analyse en cours...
              </>
            ) : (
              <>
                <RefreshCw className="h-4 w-4 mr-2" />
                Régénérer
              </>
            )}
          </Button>
        </div>
      </div>

      {isLoading && (
        <div className="space-y-4">
          {[0, 1, 2].map((i) => (
            <Card key={i}>
              <CardHeader>
                <Skeleton className="h-6 w-2/3" />
                <Skeleton className="h-4 w-1/3" />
              </CardHeader>
              <CardContent className="space-y-3">
                <Skeleton className="h-4 w-full" />
                <Skeleton className="h-4 w-5/6" />
                <Skeleton className="h-20 w-full" />
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {isEmpty && (
        <Card className="border-dashed">
          <CardContent className="py-12 text-center space-y-4">
            <Globe className="h-10 w-10 mx-auto text-muted-foreground/50" />
            <div>
              <h3 className="font-semibold">Aucune opportunité encore.</h3>
              <p className="text-sm text-muted-foreground mt-1 max-w-md mx-auto">
                Pour générer des opportunités, tu as besoin d'au moins un
                mot-clé tracké avec un intent <strong>commercial</strong>,{" "}
                <strong>transactionnel</strong> ou <strong>local</strong>.
                Ajoute tes mots-clés dans le tracker puis clique sur Régénérer.
              </p>
            </div>
            <div className="flex flex-wrap justify-center gap-2 pt-2">
              <Button asChild variant="outline">
                <Link href={`/dashboard/${sid}/positions`}>
                  <Target className="h-4 w-4 mr-2" />
                  Aller au tracker de positions
                </Link>
              </Button>
              <Button
                onClick={() => refreshMutation.mutate()}
                disabled={refreshMutation.isPending}
              >
                <RefreshCw className="h-4 w-4 mr-2" />
                Régénérer maintenant
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {!isLoading && items.length > 0 && (siteIsExternal ? (
        <div className="space-y-4">
          <div className="flex items-start gap-3 rounded-lg border border-amber-500/30 bg-amber-500/[0.05] p-4">
            <Globe className="h-5 w-5 shrink-0 text-amber-400 mt-0.5" />
            <div>
              <h2 className="font-semibold text-sm">
                Site externe - livraison par prompt
              </h2>
              <p className="text-xs text-muted-foreground mt-0.5 max-w-2xl">
                Ce site n'est pas hébergé chez Gridar (stockage externe). Gridar
                ne publie pas les landings directement dessus. Pour chaque
                opportunité, clique « Obtenir le prompt de création » : colle-le
                dans ton IA de code ou donne-le à ton dev, et la page se
                construit sur ton propre site.
              </p>
            </div>
          </div>
          {items.map((opp) => (
            <OpportunityCard
              key={opp.id}
              opp={opp}
              siteId={sid}
              siteIsExternal
            />
          ))}
        </div>
      ) : (
        <div className="space-y-10">
          {actionable.length > 0 && (
            <section className="space-y-4">
              <div className="flex items-start gap-3 rounded-lg border border-emerald-500/30 bg-emerald-500/[0.05] p-4">
                <PenLine className="h-5 w-5 shrink-0 text-emerald-400 mt-0.5" />
                <div>
                  <h2 className="font-semibold text-sm flex items-center gap-2">
                    Actionnable avec Gridar
                    <Badge
                      variant="outline"
                      className="border-emerald-500/30 text-emerald-400"
                    >
                      {actionable.length}
                    </Badge>
                  </h2>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Gridar génère ces pages directement. Clique sur « Créer
                    cette page » et la landing est produite dans ton dashboard.
                  </p>
                </div>
              </div>
              {actionable.map((opp) => (
                <OpportunityCard key={opp.id} opp={opp} siteId={sid} />
              ))}
            </section>
          )}

          {needsAsset.length > 0 && (
            <section className="space-y-4">
              <div className="flex items-start gap-3 rounded-lg border border-amber-500/30 bg-amber-500/[0.05] p-4">
                <Wrench className="h-5 w-5 shrink-0 text-amber-400 mt-0.5" />
                <div>
                  <h2 className="font-semibold text-sm flex items-center gap-2">
                    Nécessite un asset à construire
                    <Badge
                      variant="outline"
                      className="border-amber-500/30 text-amber-400"
                    >
                      {needsAsset.length}
                    </Badge>
                  </h2>
                  <p className="text-xs text-muted-foreground mt-0.5 max-w-2xl">
                    Bonnes idées stratégiques, mais le mécanisme (configurateur,
                    calculateur, outil interactif) doit être développé. Gridar
                    ne génère pas l'outil lui-même. Utilise « Obtenir le prompt
                    de création » pour confier la construction à ton dev ou à
                    ton IA de code (Lovable, v0, Cursor…).
                  </p>
                </div>
              </div>
              {needsAsset.map((opp) => (
                <OpportunityCard
                  key={opp.id}
                  opp={opp}
                  siteId={sid}
                  needsCustomAsset
                />
              ))}
            </section>
          )}
        </div>
      ))}
    </div>
  );
}
