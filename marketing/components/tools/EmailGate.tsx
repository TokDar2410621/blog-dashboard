"use client";

import { useState } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Lock,
  Mail,
  ArrowRight,
  Loader2,
  CheckCircle2,
  Shield,
} from "lucide-react";
import { toast } from "sonner";

const API_BASE = "";

type EmailGateProps = {
  /** Headline above the email form */
  headline: string;
  /** Bullet points showing what the report includes */
  bulletPoints: string[];
  /** The domain that was analyzed */
  domain: string;
  /** Which tool captured this lead */
  tool: string;
  /** Callback when email is submitted successfully, receives the response */
  onSuccess?: (response: unknown) => void;
  /** Number of hidden items to highlight (e.g. "17 requetes") */
  hiddenCount?: number;
  /** Custom label for the hidden items */
  hiddenLabel?: string;
};

export function EmailGate({
  headline,
  bulletPoints,
  domain,
  tool,
  onSuccess,
  hiddenCount,
  hiddenLabel,
}: EmailGateProps) {
  const [email, setEmail] = useState("");
  const [consented, setConsented] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [captured, setCaptured] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim()) return;
    setSubmitting(true);
    try {
      const res = await fetch(`${API_BASE}/api/public/leads/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: email.trim(),
          domain,
          source: tool,
          consented_marketing: consented,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error || "Erreur");
      }
      const body = await res.json().catch(() => ({}));
      setCaptured(true);
      toast.success("Rapport complet envoye par courriel.");
      onSuccess?.(body);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Erreur");
    } finally {
      setSubmitting(false);
    }
  };

  if (captured) {
    return (
      <Card className="border-emerald-500/30 bg-emerald-500/[0.04]">
        <CardContent className="p-6 text-center space-y-3">
          <CheckCircle2 className="h-8 w-8 text-emerald-400 mx-auto" />
          <p className="text-lg font-semibold text-zinc-100">
            Rapport envoye!
          </p>
          <p className="text-sm text-zinc-400">
            Verifie ta boite courriel. Le rapport complet de{" "}
            <span className="font-mono text-zinc-300">{domain}</span> est en
            route.
          </p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="border-emerald-500/30 bg-emerald-500/[0.04]">
      <CardContent className="p-6 space-y-4">
        <div className="flex items-start gap-3">
          <Lock className="h-5 w-5 text-emerald-400 mt-0.5 shrink-0" />
          <div>
            {hiddenCount != null && hiddenLabel && (
              <p className="text-sm text-emerald-300 font-medium mb-1">
                {hiddenCount} {hiddenLabel}
              </p>
            )}
            <p className="text-base font-semibold text-zinc-100">
              {headline}
            </p>
          </div>
        </div>

        <ul className="space-y-1.5 text-sm text-zinc-300">
          {bulletPoints.map((bp, i) => (
            <li key={i} className="flex items-start gap-2">
              <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400 mt-0.5 shrink-0" />
              <span>{bp}</span>
            </li>
          ))}
        </ul>

        <form onSubmit={submit} className="space-y-3">
          <div className="flex flex-col sm:flex-row gap-2">
            <Input
              type="email"
              placeholder="ton@courriel.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={submitting}
              required
              className="flex-1"
            />
            <Button
              type="submit"
              disabled={submitting || !email.trim()}
              className="bg-white text-zinc-950 hover:bg-zinc-200 font-semibold shrink-0"
            >
              {submitting ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Envoi...
                </>
              ) : (
                <>
                  <Mail className="h-4 w-4 mr-2" />
                  Recevoir gratuitement
                </>
              )}
            </Button>
          </div>
          <label className="flex items-start gap-2 cursor-pointer">
            <input
              type="checkbox"
              checked={consented}
              onChange={(e) => setConsented(e.target.checked)}
              className="mt-0.5 rounded border-zinc-700"
            />
            <span className="text-xs text-zinc-500">
              J'accepte de recevoir des conseils SEO par courriel.
              Desabonnement en un clic. Conforme a la Loi 25.
            </span>
          </label>
        </form>

        <div className="flex items-center gap-1.5 text-xs text-zinc-500">
          <Shield className="h-3 w-3" />
          <span>Tes donnees ne seront jamais partagees.</span>
        </div>
      </CardContent>
    </Card>
  );
}
