"use client";

/**
 * Unsubscribe confirmation page (client side).
 *
 * Reached from the footer link of every lead email:
 *   /unsubscribe?email=<addr>&t=<signed token>     (emails sent >= 2026-06-11)
 *   /unsubscribe?email=<addr>                      (legacy emails)
 *
 * Deliberately requires ONE click before opting out: corporate mail
 * scanners prefetch GET links, so auto-unsubscribing on page load would
 * silently opt out every recipient behind such a gateway. The RFC 8058
 * one-click POST endpoint handles the mail-client-native button instead.
 */
import { useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { CheckCircle2, Loader2, MailX } from "lucide-react";
import { Button } from "@/components/ui/button";

export function UnsubscribePage() {
  const params = useSearchParams();
  const email = params?.get("email") || "";
  const token = params?.get("t") || "";

  const [state, setState] = useState<"idle" | "pending" | "done" | "error">(
    "idle",
  );
  const [errorMsg, setErrorMsg] = useState("");

  const confirm = async () => {
    setState("pending");
    try {
      const res = await fetch("/api/public/unsubscribe/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(token ? { token } : { email }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(
          typeof data.error === "string"
            ? data.error
            : "Le lien semble invalide ou expiré.",
        );
      }
      setState("done");
    } catch (e) {
      setErrorMsg(e instanceof Error ? e.message : "Erreur inattendue.");
      setState("error");
    }
  };

  const missingCredentials = !token && !email;

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 flex items-center justify-center px-4">
      <div className="w-full max-w-md rounded-2xl border border-white/10 bg-zinc-900/60 p-8 text-center space-y-6">
        {state === "done" ? (
          <>
            <span className="mx-auto inline-flex h-12 w-12 items-center justify-center rounded-full bg-emerald-500/15 border border-emerald-500/30">
              <CheckCircle2 className="h-6 w-6 text-emerald-400" />
            </span>
            <div>
              <h1 className="text-xl font-bold">C'est fait.</h1>
              <p className="mt-2 text-sm text-zinc-400 leading-relaxed">
                {email ? (
                  <>
                    <span className="font-mono text-zinc-200 break-all">
                      {email}
                    </span>{" "}
                    ne recevra plus nos courriels marketing.
                  </>
                ) : (
                  "Cette adresse ne recevra plus nos courriels marketing."
                )}
              </p>
              <p className="mt-3 text-xs text-zinc-500 leading-relaxed">
                Changé d'idée plus tard ? Relance un audit gratuit sur
                gridar.app/audit et coche la case courriels.
              </p>
            </div>
            <Link href="/" className="inline-block">
              <Button variant="outline" className="border-white/15">
                Retour à l'accueil
              </Button>
            </Link>
          </>
        ) : (
          <>
            <span className="mx-auto inline-flex h-12 w-12 items-center justify-center rounded-full bg-white/5 border border-white/10">
              <MailX className="h-6 w-6 text-zinc-300" />
            </span>
            <div>
              <h1 className="text-xl font-bold">Se désabonner</h1>
              <p className="mt-2 text-sm text-zinc-400 leading-relaxed">
                {missingCredentials ? (
                  "Ce lien est incomplet. Utilise le lien « Se désinscrire » au bas d'un de nos courriels."
                ) : (
                  <>
                    Tu ne recevras plus les courriels de Gridar
                    {email && (
                      <>
                        {" "}
                        envoyés à{" "}
                        <span className="font-mono text-zinc-200 break-all">
                          {email}
                        </span>
                      </>
                    )}
                    . Cette action est immédiate.
                  </>
                )}
              </p>
            </div>
            {state === "error" && (
              <p className="text-sm text-red-400">{errorMsg}</p>
            )}
            {!missingCredentials && (
              <Button
                onClick={confirm}
                disabled={state === "pending"}
                className="w-full bg-white text-zinc-950 hover:bg-zinc-200 h-11"
              >
                {state === "pending" ? (
                  <>
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                    Un instant...
                  </>
                ) : (
                  "Confirmer le désabonnement"
                )}
              </Button>
            )}
          </>
        )}
      </div>
    </div>
  );
}
