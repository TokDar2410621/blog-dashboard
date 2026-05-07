import { useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { authFetch } from "@/lib/api-client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  CheckCircle2,
  Sparkles,
  ArrowLeft,
  CreditCard,
  Loader2,
  AlertCircle,
} from "lucide-react";
import { toast } from "sonner";

type Subscription = {
  plan: "free" | "solo" | "pro" | "agency";
  status: string;
  is_paid: boolean;
  current_period_end: string | null;
  cancel_at_period_end: boolean;
  limits: {
    sites_max: number;
    articles_per_month: number | null;
    keywords_max: number;
  };
  usage?: {
    articles_this_month: number;
    month_key: string;
  };
};

const PLANS = [
  {
    key: "free" as const,
    name: "Essai",
    price: "0$",
    period: "pour toujours",
    features: [
      "1 site",
      "1 article généré/mois",
      "Audit IA basique",
      "Pas de suivi de mots-clés",
      "Support communauté",
    ],
  },
  {
    key: "solo" as const,
    name: "Solo",
    price: "29.99$",
    period: "/mois",
    features: [
      "1 site",
      "8 articles générés/mois",
      "Audit IA + brief de contenu",
      "Suivi 10 mots-clés + GSC",
      "Lexique FR-CA",
      "Rapport mensuel PDF",
      "Support email <72h",
    ],
  },
  {
    key: "pro" as const,
    name: "Pro",
    price: "89.99$",
    period: "/mois",
    highlighted: true,
    features: [
      "2 sites",
      "60 articles générés/mois",
      "24 outils SEO",
      "Suivi 30 mots-clés + GSC + alertes",
      "Audit bulk + topic clusters",
      "Lexique FR-CA + EEAT",
      "Rapport hebdomadaire PDF",
      "API REST (30 req/h)",
      "Support email <48h",
    ],
  },
  {
    key: "agency" as const,
    name: "Agence",
    price: "199.99$",
    period: "/mois",
    features: [
      "5 sites",
      "200 articles générés/mois",
      "Tout du plan Pro",
      "Comparaison multi-domaines",
      "Suivi 100 mots-clés",
      "API REST (200 req/h)",
      "White-label optionnel",
      "Onboarding personnalisé",
      "Support prioritaire <8h",
    ],
  },
];

export default function Billing() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [searchParams] = useSearchParams();
  const [busyPlan, setBusyPlan] = useState<string | null>(null);

  const { data: sub, isLoading } = useQuery<Subscription>({
    queryKey: ["billing-me"],
    queryFn: async () => {
      const res = await authFetch("/billing/me/");
      if (!res.ok) throw new Error("billing fetch failed");
      return res.json();
    },
  });

  // Show toast on success/cancel return from Stripe
  useEffect(() => {
    const status = searchParams.get("status");
    if (status === "success") {
      toast.success("Abonnement confirmé. Bienvenue !");
      qc.invalidateQueries({ queryKey: ["billing-me"] });
    } else if (status === "cancel") {
      toast("Paiement annulé.");
    }
  }, [searchParams, qc]);

  const checkout = useMutation({
    mutationFn: async (plan: "solo" | "pro" | "agency") => {
      setBusyPlan(plan);
      const res = await authFetch("/billing/checkout/", {
        method: "POST",
        body: JSON.stringify({ plan }),
      });
      const data = await res.json();
      if (!res.ok || !data.url) {
        throw new Error(data.error || "Erreur checkout");
      }
      return data.url as string;
    },
    onSuccess: (url) => {
      window.location.href = url;
    },
    onError: (err: Error) => {
      toast.error(err.message);
      setBusyPlan(null);
    },
  });

  const portal = useMutation({
    mutationFn: async () => {
      const res = await authFetch("/billing/portal/", { method: "POST" });
      const data = await res.json();
      if (!res.ok || !data.url) {
        throw new Error(data.error || "Erreur portail");
      }
      return data.url as string;
    },
    onSuccess: (url) => {
      window.location.href = url;
    },
    onError: (err: Error) => toast.error(err.message),
  });

  const formatDate = (iso: string | null) =>
    iso
      ? new Date(iso).toLocaleDateString("fr-CA", {
          year: "numeric",
          month: "long",
          day: "numeric",
        })
      : "";

  return (
    <div className="min-h-screen bg-background p-6">
      <div className="max-w-5xl mx-auto space-y-8">
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => navigate("/sites")}
            title="Retour"
          >
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <div>
            <h1 className="text-2xl font-bold">Abonnement</h1>
            <p className="text-muted-foreground">
              Gère ton plan, tes paiements et tes factures.
            </p>
          </div>
        </div>

        {/* Current plan */}
        {isLoading ? (
          <Skeleton className="h-32" />
        ) : sub ? (
          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <CreditCard className="h-5 w-5 text-primary" />
                Ton plan actuel
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div>
                  <div className="flex items-center gap-3">
                    <div className="text-3xl font-bold capitalize">{sub.plan}</div>
                    <span
                      className={`text-xs px-2 py-1 rounded font-mono uppercase ${
                        sub.is_paid
                          ? "bg-green-500/10 text-green-700 dark:text-green-400"
                          : "bg-muted text-muted-foreground"
                      }`}
                    >
                      {sub.status}
                    </span>
                  </div>
                  <div className="text-sm text-muted-foreground mt-2">
                    Limites :{" "}
                    {sub.limits.sites_max} site
                    {sub.limits.sites_max > 1 ? "s" : ""},{" "}
                    {sub.limits.articles_per_month
                      ? `${sub.limits.articles_per_month} articles/mois`
                      : "articles illimités"},{" "}
                    {sub.limits.keywords_max} mots-clés.
                  </div>
                  {sub.usage && sub.limits.articles_per_month != null && (() => {
                    const used = sub.usage.articles_this_month;
                    const limit = sub.limits.articles_per_month;
                    const pct = Math.min(100, Math.round((used / limit) * 100));
                    const danger = pct >= 90;
                    return (
                      <div className="mt-3 max-w-xs">
                        <div className="flex justify-between text-xs mb-1">
                          <span className="text-muted-foreground">
                            Articles ce mois-ci
                          </span>
                          <span
                            className={`font-mono font-semibold ${
                              danger
                                ? "text-destructive"
                                : "text-foreground"
                            }`}
                          >
                            {used} / {limit}
                          </span>
                        </div>
                        <div className="h-1.5 rounded-full bg-muted overflow-hidden">
                          <div
                            className={`h-full transition-all ${
                              danger ? "bg-destructive" : "bg-primary"
                            }`}
                            style={{ width: `${pct}%` }}
                          />
                        </div>
                      </div>
                    );
                  })()}
                  {sub.current_period_end && (
                    <div className="text-xs text-muted-foreground mt-1">
                      {sub.cancel_at_period_end
                        ? `Annulation effective le ${formatDate(sub.current_period_end)}`
                        : `Prochain renouvellement : ${formatDate(sub.current_period_end)}`}
                    </div>
                  )}
                </div>
                {sub.is_paid && (
                  <Button
                    variant="outline"
                    onClick={() => portal.mutate()}
                    disabled={portal.isPending}
                  >
                    {portal.isPending ? (
                      <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    ) : (
                      <CreditCard className="h-4 w-4 mr-2" />
                    )}
                    Gérer mon abonnement
                  </Button>
                )}
              </div>
            </CardContent>
          </Card>
        ) : null}

        {/* Plans */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          {PLANS.map((plan) => {
            const isCurrent = sub?.plan === plan.key;
            const canSubscribe = plan.key !== "free";
            return (
              <Card
                key={plan.key}
                className={
                  plan.highlighted
                    ? "border-primary border-2 relative"
                    : ""
                }
              >
                {plan.highlighted && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2 px-3 py-1 rounded-full bg-primary text-primary-foreground text-xs font-mono uppercase tracking-wider">
                    Recommandé
                  </div>
                )}
                <CardContent className="pt-6 space-y-4">
                  <div>
                    <h3 className="font-bold text-lg">{plan.name}</h3>
                  </div>
                  <div>
                    <div className="text-4xl font-bold">{plan.price}</div>
                    <div className="text-sm text-muted-foreground">{plan.period}</div>
                  </div>
                  <ul className="space-y-2 text-sm">
                    {plan.features.map((f) => (
                      <li key={f} className="flex items-start gap-2">
                        <CheckCircle2
                          className={`h-4 w-4 shrink-0 mt-0.5 ${
                            plan.highlighted
                              ? "text-primary"
                              : "text-muted-foreground"
                          }`}
                        />
                        <span>{f}</span>
                      </li>
                    ))}
                  </ul>
                  {isCurrent ? (
                    <Button variant="outline" className="w-full" disabled>
                      Plan actuel
                    </Button>
                  ) : canSubscribe ? (
                    <Button
                      className="w-full"
                      variant={plan.highlighted ? "default" : "outline"}
                      onClick={() => checkout.mutate(plan.key)}
                      disabled={busyPlan !== null}
                    >
                      {busyPlan === plan.key ? (
                        <>
                          <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                          Redirection...
                        </>
                      ) : (
                        <>
                          <Sparkles className="h-4 w-4 mr-2" />
                          {sub?.is_paid ? `Passer à ${plan.name}` : "Souscrire"}
                        </>
                      )}
                    </Button>
                  ) : (
                    <Button variant="ghost" className="w-full" disabled>
                      Plan par défaut
                    </Button>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>

        {/* Enterprise contact CTA */}
        <Card className="border-emerald-500/20 bg-emerald-500/5">
          <CardContent className="py-5 flex flex-col md:flex-row items-start md:items-center gap-4 justify-between">
            <div>
              <div className="font-semibold flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-emerald-500" />
                Plus de 5 sites ou besoin sur mesure ?
              </div>
              <div className="text-sm text-muted-foreground mt-1">
                Volume custom, intégrations, SLA, comptable dédié. On en jase.
              </div>
            </div>
            <a
              href="mailto:tokamdarius@gmail.com?subject=Plan%20Enterprise%20-%20demande%20sur%20mesure"
              className="shrink-0"
            >
              <Button variant="outline">Nous contacter</Button>
            </a>
          </CardContent>
        </Card>

        {/* Stripe note */}
        <Card>
          <CardContent className="py-4 text-xs text-muted-foreground flex items-start gap-2">
            <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
            <div>
              Paiement sécurisé via Stripe. Annulation en un clic depuis &quot;Gérer mon abonnement&quot;.
              Tarifs en CAD, taxes québécoises (TPS+TVQ) appliquées au checkout.
              Tu gardes l&apos;accès à tes articles publiés même si tu annules.
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
