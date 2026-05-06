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
  plan: "free" | "pro" | "agency";
  status: string;
  is_paid: boolean;
  current_period_end: string | null;
  cancel_at_period_end: boolean;
  limits: {
    sites_max: number;
    articles_per_month: number | null;
    keywords_max: number;
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
      "5 articles générés/mois",
      "Audit IA basique",
      "Brief de contenu",
      "Suivi 5 mots-clés",
    ],
  },
  {
    key: "pro" as const,
    name: "Pro",
    price: "79$",
    period: "/mois",
    highlighted: true,
    features: [
      "3 sites",
      "Articles illimités",
      "Tous les outils SEO",
      "Suivi 50 mots-clés + GSC + alertes",
      "Audit bulk + topic clusters",
      "Lexique FR-CA + EEAT",
      "Rapport hebdomadaire PDF",
      "API REST (60 req/h)",
      "Support email <24h",
    ],
  },
  {
    key: "agency" as const,
    name: "Agence",
    price: "199$",
    period: "/mois",
    features: [
      "10 sites",
      "Tout du plan Pro",
      "Comparaison multi-domaines",
      "Suivi 200 mots-clés",
      "API REST (600 req/h)",
      "White-label optionnel",
      "Onboarding personnalisé",
      "Support prioritaire <4h",
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
    mutationFn: async (plan: "pro" | "agency") => {
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
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
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
