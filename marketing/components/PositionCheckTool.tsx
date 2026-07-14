"use client";

import { useState } from "react";
import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  MapPin,
  Search,
  Loader2,
  Trophy,
  ArrowRight,
  Gauge,
  CheckCircle2,
  XCircle,
} from "lucide-react";
import { toast } from "sonner";

// Empty base = same-origin via Next.js rewrites (see next.config.ts).
// Keeps requests on gridar.app so /api/public/* stays same-origin.
const API_BASE = "";

// Villes quebecoises supportees par le backend (_resolve_qc_location).
// Les accents et la casse sont toleres cote serveur.
const QC_CITIES = [
  "Montréal",
  "Québec",
  "Gatineau",
  "Laval",
  "Longueuil",
  "Sherbrooke",
  "Trois-Rivières",
  "Saguenay",
  "Lévis",
  "Terrebonne",
];

type Top3Row = {
  position: number;
  domain: string;
  url: string;
  title: string;
};

type PositionResult = {
  found: boolean;
  position: number | null;
  keyword: string;
  city: string;
  checked_domain: string;
  matched_url: string;
  total_results: number;
  top3: Top3Row[];
};

export function PositionCheckTool() {
  const [url, setUrl] = useState("");
  const [keyword, setKeyword] = useState("");
  const [city, setCity] = useState("Montréal");
  const [checking, setChecking] = useState(false);
  const [result, setResult] = useState<PositionResult | null>(null);
  // Ville affichee dans le resultat : on garde notre propre libelle accentue
  // plutot que de dependre de l'echo serveur.
  const [resultCity, setResultCity] = useState("Montréal");

  const runCheck = async (e: React.FormEvent) => {
    e.preventDefault();
    const cleanUrl = url.trim();
    const cleanKeyword = keyword.trim();
    if (!cleanUrl || !cleanKeyword) return;
    setChecking(true);
    setResult(null);
    try {
      const res = await fetch(`${API_BASE}/api/public/position-check/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url: cleanUrl,
          keyword: cleanKeyword,
          city,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(
          err.error || "Verification impossible pour le moment, reessaie."
        );
      }
      const data = (await res.json()) as PositionResult;
      setResult(data);
      setResultCity(city);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Une erreur est survenue.");
    } finally {
      setChecking(false);
    }
  };

  return (
    <div className="w-full max-w-2xl mx-auto">
      <Card className="border-white/10 bg-white/[0.02]">
        <CardContent className="p-5 md:p-6">
          <form onSubmit={runCheck} className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="pc-url" className="text-zinc-300">
                Ton adresse web (URL ou domaine)
              </Label>
              <Input
                id="pc-url"
                type="text"
                inputMode="url"
                placeholder="tondomaine.com ou https://tondomaine.com/blog"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                disabled={checking}
                required
              />
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label htmlFor="pc-keyword" className="text-zinc-300">
                  Mot-cle a verifier
                </Label>
                <Input
                  id="pc-keyword"
                  type="text"
                  placeholder="plombier urgence, dentiste, etc."
                  value={keyword}
                  onChange={(e) => setKeyword(e.target.value)}
                  disabled={checking}
                  required
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="pc-city" className="text-zinc-300">
                  Ville quebecoise
                </Label>
                <Select value={city} onValueChange={setCity} disabled={checking}>
                  <SelectTrigger id="pc-city" className="w-full">
                    <span className="flex items-center gap-2">
                      <MapPin className="h-4 w-4 text-emerald-400" />
                      <SelectValue placeholder="Choisis une ville" />
                    </span>
                  </SelectTrigger>
                  <SelectContent>
                    {QC_CITIES.map((c) => (
                      <SelectItem key={c} value={c}>
                        {c}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <Button
              type="submit"
              disabled={checking || !url.trim() || !keyword.trim()}
              className="w-full bg-emerald-500 text-zinc-950 hover:bg-emerald-400 font-semibold"
            >
              {checking ? (
                <>
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  Verification sur Google.ca...
                </>
              ) : (
                <>
                  <Search className="h-4 w-4 mr-2" />
                  Verifier ma position gratuitement
                </>
              )}
            </Button>
            <p className="text-center text-xs text-zinc-500">
              Aucune inscription. Resultat geolocalise au Quebec en 30 secondes.
            </p>
          </form>
        </CardContent>
      </Card>

      {result && (
        <div className="mt-6 space-y-5">
          {/* Bloc resultat principal */}
          <Card
            className={
              result.found
                ? "border-emerald-500/40 bg-emerald-500/[0.06]"
                : "border-amber-500/40 bg-amber-500/[0.06]"
            }
          >
            <CardContent className="p-6 text-center">
              {result.found ? (
                <>
                  <div className="flex items-center justify-center gap-2 text-emerald-400 mb-2">
                    <CheckCircle2 className="h-5 w-5" />
                    <span className="text-sm font-medium uppercase tracking-wide">
                      Trouve sur Google.ca
                    </span>
                  </div>
                  <div className="text-6xl font-bold text-emerald-400 tabular-nums leading-none mb-3">
                    #{result.position}
                  </div>
                  <p className="text-zinc-200 text-base">
                    Ton site{" "}
                    <span className="font-mono text-emerald-300">
                      {result.checked_domain}
                    </span>{" "}
                    est <strong>#{result.position}</strong> sur Google.ca a{" "}
                    <strong>{resultCity}</strong> pour{" "}
                    <span className="text-zinc-100">« {result.keyword} »</span>.
                  </p>
                  {result.matched_url && (
                    <p className="mt-2 text-xs text-zinc-500 break-all">
                      Page classee : {result.matched_url}
                    </p>
                  )}
                </>
              ) : (
                <>
                  <div className="flex items-center justify-center gap-2 text-amber-400 mb-2">
                    <XCircle className="h-5 w-5" />
                    <span className="text-sm font-medium uppercase tracking-wide">
                      Hors du top 100
                    </span>
                  </div>
                  <p className="text-zinc-200 text-base">
                    Ton site{" "}
                    <span className="font-mono text-amber-300">
                      {result.checked_domain}
                    </span>{" "}
                    n&apos;apparait pas dans le top 100 sur Google.ca a{" "}
                    <strong>{resultCity}</strong> pour{" "}
                    <span className="text-zinc-100">« {result.keyword} »</span>.
                  </p>
                  <p className="mt-2 text-sm text-zinc-400">
                    Il y a du travail, mais c&apos;est exactement ce que Gridar
                    corrige : contenu, structure et suivi quotidien pour te faire
                    grimper.
                  </p>
                </>
              )}
            </CardContent>
          </Card>

          {/* Top 3 qui te devance */}
          {result.top3.length > 0 && (
            <Card className="border-white/10 bg-white/[0.02]">
              <CardContent className="p-5">
                <div className="flex items-center gap-2 mb-3 text-zinc-200">
                  <Trophy className="h-4 w-4 text-emerald-400" />
                  <h3 className="text-sm font-semibold uppercase tracking-wide">
                    {result.found
                      ? `Le top 3 a ${resultCity}`
                      : `Le top 3 qui te devance a ${resultCity}`}
                  </h3>
                </div>
                <div className="space-y-2">
                  {result.top3.map((row) => (
                    <div
                      key={row.position}
                      className="flex items-start gap-3 rounded-md border border-white/5 bg-white/[0.02] p-3"
                    >
                      <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-emerald-500/15 text-xs font-bold text-emerald-400 tabular-nums">
                        {row.position}
                      </span>
                      <div className="min-w-0">
                        <p className="truncate text-sm text-zinc-100">
                          {row.title || row.domain}
                        </p>
                        <p className="truncate text-xs text-zinc-500 font-mono">
                          {row.domain}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Chemin de conversion apres le check gratuit */}
          <Card className="border-emerald-500/30 bg-emerald-500/[0.04]">
            <CardContent className="p-5 md:p-6 text-center space-y-4">
              <div className="flex items-center justify-center gap-2 text-zinc-100">
                <Gauge className="h-5 w-5 text-emerald-400" />
                <h3 className="text-lg font-semibold">
                  Passe du check ponctuel au suivi serieux
                </h3>
              </div>
              <p className="text-sm text-zinc-400 max-w-xl mx-auto">
                Une position, c&apos;est une photo. Pour savoir si tu montes ou tu
                descends, il faut la suivre dans le temps. Gridar audite ton site
                au complet et suit tes positions Google.ca chaque jour.
              </p>
              <div className="flex flex-col sm:flex-row gap-3 justify-center">
                <Link href="/audit" className="sm:w-auto w-full">
                  <Button className="w-full bg-white text-zinc-950 hover:bg-zinc-200 font-semibold">
                    Audit SEO complet gratuit
                    <ArrowRight className="h-4 w-4 ml-2" />
                  </Button>
                </Link>
                <Link href="/login" className="sm:w-auto w-full">
                  <Button
                    variant="outline"
                    className="w-full border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/10 hover:text-emerald-200"
                  >
                    Essayer le suivi quotidien automatique
                  </Button>
                </Link>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
