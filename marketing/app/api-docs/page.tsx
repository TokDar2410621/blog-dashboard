import type { Metadata } from "next";
import { Button } from "@/components/ui/button";
import { Key, Code2, Zap, ShieldCheck } from "lucide-react";
import Terminal3D from "@/components/Terminal3D";
import { MarketingHeader } from "@/components/MarketingHeader";
import { MarketingFooter } from "@/components/MarketingFooter";

const BASE = "https://api.gridar.app/api/v1";

const DASHBOARD_URL = process.env.NEXT_PUBLIC_DASHBOARD_URL || "https://gridar.app";

export const metadata: Metadata = {
  title: "API REST Gridar - Documentation",
  description:
    "API REST publique Gridar : Bearer auth, endpoints /me, /sites, /generate, /audit, /brief, /keywords, /digest. Pour n8n, Zapier, Make et scripts.",
  alternates: { canonical: "/api-docs" },
};

type EndpointDoc = {
  method: "GET" | "POST" | "DELETE";
  path: string;
  title: string;
  desc: string;
  curl: string;
  sample?: string;
};

const ENDPOINTS: EndpointDoc[] = [
  {
    method: "GET",
    path: "/me/",
    title: "Identité du compte",
    desc: "Vérifie ton token et récupère ton plan + ta limite horaire.",
    curl: `curl -H "Authorization: Bearer btb_xxx" \\\n  ${BASE}/me/`,
    sample: `{
  "username": "darius",
  "email": "tu@exemple.ca",
  "plan": "pro",
  "rate_limit_per_hour": 60
}`,
  },
  {
    method: "GET",
    path: "/sites/",
    title: "Liste de tes sites",
    desc: "Retourne tous les sites actifs liés à ton compte.",
    curl: `curl -H "Authorization: Bearer btb_xxx" \\\n  ${BASE}/sites/`,
  },
  {
    method: "GET",
    path: "/sites/{id}/articles/",
    title: "Articles d'un site",
    desc: "Filtres : ?status=published&language=fr&limit=50",
    curl: `curl -H "Authorization: Bearer btb_xxx" \\\n  "${BASE}/sites/12/articles/?status=published&language=fr&limit=20"`,
  },
  {
    method: "POST",
    path: "/sites/{id}/generate/",
    title: "Générer un article complet",
    desc: "Le générateur IA produit un article SEO-ready et le publie. Coûte du temps GPU. Utilise avec parcimonie.",
    curl: `curl -X POST -H "Authorization: Bearer btb_xxx" \\\n  -H "Content-Type: application/json" \\\n  -d '{"topic":"Comment choisir un CRM PME au Québec","article_type":"guide","length":"long","language":"fr"}' \\\n  ${BASE}/sites/12/generate/`,
  },
  {
    method: "POST",
    path: "/audit/",
    title: "Audit SEO d'un contenu",
    desc: "Audit IA d'un article (existant ou brouillon). Pas besoin d'un site_id.",
    curl: `curl -X POST -H "Authorization: Bearer btb_xxx" \\\n  -H "Content-Type: application/json" \\\n  -d '{"title":"Mon titre","excerpt":"...","content":"<p>...</p>","keyword":"crm pme","language":"fr"}' \\\n  ${BASE}/audit/`,
  },
  {
    method: "POST",
    path: "/brief/",
    title: "Brief de contenu",
    desc: "Brief structuré (intent, sous-sujets, entités, FAQ) à partir d'un mot-clé cible.",
    curl: `curl -X POST -H "Authorization: Bearer btb_xxx" \\\n  -H "Content-Type: application/json" \\\n  -d '{"keyword":"meilleur crm pme quebec","language":"fr"}' \\\n  ${BASE}/brief/`,
  },
  {
    method: "GET",
    path: "/sites/{id}/keywords/",
    title: "Mots-clés suivis",
    desc: "Liste des mots-clés trackés + dernière position connue.",
    curl: `curl -H "Authorization: Bearer btb_xxx" \\\n  ${BASE}/sites/12/keywords/`,
  },
  {
    method: "POST",
    path: "/sites/{id}/keywords/snapshot/",
    title: "Lancer un snapshot de positions",
    desc: "Crawl SERP immédiat pour mettre à jour les positions. Compte dans ta limite horaire.",
    curl: `curl -X POST -H "Authorization: Bearer btb_xxx" \\\n  ${BASE}/sites/12/keywords/snapshot/`,
  },
  {
    method: "GET",
    path: "/sites/{id}/digest/weekly/",
    title: "Digest hebdomadaire",
    desc: "Snapshot hebdomadaire (publications, audit, mots-clés). Pratique en cron pour Slack/email.",
    curl: `curl -H "Authorization: Bearer btb_xxx" \\\n  ${BASE}/sites/12/digest/weekly/`,
  },
];

// Method pill colors aligned with landing's badge palette.
const methodColor: Record<string, string> = {
  GET: "bg-emerald-500/10 text-emerald-300 border-emerald-500/30",
  POST: "bg-cyan-500/10 text-cyan-300 border-cyan-500/30",
  DELETE: "bg-rose-500/10 text-rose-300 border-rose-500/30",
};

// Reusable panel wrapper, mirrors the landing `MockupFrame` style without a window chrome.
function Panel({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`rounded-2xl border border-white/10 bg-zinc-900/60 backdrop-blur-sm ${className}`}
    >
      {children}
    </div>
  );
}

export default function ApiDocs() {
  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      <MarketingHeader trail="API" />

      {/* Top emerald wash, same hero recipe as landing. */}
      <div className="fixed inset-x-0 top-0 h-[40vh] z-0 pointer-events-none bg-gradient-to-b from-emerald-500/[0.05] via-transparent to-transparent" />

      <main className="relative z-10 max-w-5xl mx-auto px-4 md:px-6 py-12 space-y-8">
        {/* Page title block */}
        <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-6">
          <div>
            <p className="text-xs font-mono uppercase tracking-wider text-emerald-400/80 mb-3">
              Référence API v1
            </p>
            <h1 className="text-4xl md:text-5xl font-bold tracking-tight flex items-center gap-3">
              <Code2 className="h-8 w-8 text-emerald-400" />
              API REST publique
            </h1>
            <p className="text-zinc-400 mt-3 max-w-2xl">
              Intègre Gridar à n8n, Zapier, Make ou tes propres scripts.
              Authentification par Bearer token, réponses JSON, versionnée par préfixe.
            </p>
          </div>
          <a href={`${DASHBOARD_URL}/account/api-keys`} className="shrink-0">
            <Button className="bg-white text-zinc-950 hover:bg-zinc-200">
              <Key className="h-4 w-4 mr-2" />
              Mes clés API
            </Button>
          </a>
        </div>

        {/* Terminal hero, kept as-is (already dark-themed) but framed with our border. */}
        <div className="rounded-2xl border border-white/10 bg-zinc-950 overflow-hidden">
          <div
            className="relative"
            style={{
              background:
                "radial-gradient(50% 80% at 50% 0%, rgba(16,185,129,0.12), transparent 70%)",
            }}
          >
            <Terminal3D />
          </div>
        </div>

        {/* Quickstart */}
        <Panel className="p-6">
          <div className="flex items-center gap-2 mb-4">
            <Zap className="h-5 w-5 text-emerald-400" />
            <h2 className="text-lg font-semibold text-zinc-100">Démarrage rapide</h2>
          </div>
          <ol className="list-decimal list-inside space-y-2 text-sm text-zinc-300">
            <li>
              Crée un token sur{" "}
              <a
                href={`${DASHBOARD_URL}/account/api-keys`}
                className="text-emerald-400 hover:text-emerald-300 hover:underline"
              >
                /account/api-keys
              </a>
              . Copie-le immédiatement (il ne sera plus jamais affiché).
            </li>
            <li>
              Envoie-le dans l&apos;en-tête{" "}
              <code className="bg-zinc-900 border border-white/10 text-emerald-300 px-1.5 py-0.5 rounded text-xs font-mono">
                Authorization: Bearer btb_xxx
              </code>
              .
            </li>
            <li>
              Toutes les réponses sont en JSON. Erreurs : code HTTP standard +{" "}
              <code className="bg-zinc-900 border border-white/10 text-emerald-300 px-1.5 py-0.5 rounded text-xs font-mono">
                {`{"error": "..."}`}
              </code>
              .
            </li>
          </ol>
          <pre className="bg-zinc-950/80 border border-white/10 rounded-lg p-3 text-xs overflow-x-auto mt-4 text-zinc-300">
            <code>{`curl -H "Authorization: Bearer btb_xxx" ${BASE}/me/`}</code>
          </pre>
        </Panel>

        {/* Plan limits */}
        <Panel className="p-6">
          <div className="flex items-center gap-2 mb-4">
            <ShieldCheck className="h-5 w-5 text-emerald-400" />
            <h2 className="text-lg font-semibold text-zinc-100">Limites par plan</h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-sm">
            <div className="border border-white/10 rounded-lg p-4 bg-zinc-950/40">
              <div className="font-semibold text-zinc-100">Essai (gratuit)</div>
              <div className="text-zinc-400 mt-1">Pas d&apos;accès API.</div>
            </div>
            <div className="border border-emerald-500/30 rounded-lg p-4 bg-emerald-500/[0.06]">
              <div className="font-semibold text-zinc-100">Pro</div>
              <div className="text-zinc-400 mt-1">
                60 requêtes / heure / utilisateur
              </div>
            </div>
            <div className="border border-white/10 rounded-lg p-4 bg-zinc-950/40">
              <div className="font-semibold text-zinc-100">Agence</div>
              <div className="text-zinc-400 mt-1">
                600 requêtes / heure / utilisateur
              </div>
            </div>
          </div>
          <p className="text-xs text-zinc-500 mt-4">
            Au-delà de la limite : réponse{" "}
            <code className="bg-zinc-900 border border-white/10 text-emerald-300 px-1 py-0.5 rounded font-mono">
              429
            </code>{" "}
            avec un en-tête{" "}
            <code className="bg-zinc-900 border border-white/10 text-emerald-300 px-1 py-0.5 rounded font-mono">
              Retry-After
            </code>
            .
          </p>
        </Panel>

        {/* Endpoints */}
        <div className="space-y-4">
          <h2 className="text-2xl font-bold tracking-tight">Endpoints</h2>
          {ENDPOINTS.map((ep) => (
            <Panel key={ep.method + ep.path} className="p-6 space-y-4">
              <div className="space-y-2">
                <div className="flex flex-wrap items-center gap-3">
                  <span
                    className={`text-xs font-mono px-2 py-1 rounded border ${methodColor[ep.method]}`}
                  >
                    {ep.method}
                  </span>
                  <code className="text-sm font-mono text-zinc-200">{ep.path}</code>
                </div>
                <h3 className="text-base font-semibold text-zinc-100">{ep.title}</h3>
                <p className="text-sm text-zinc-400">{ep.desc}</p>
              </div>
              <div>
                <div className="text-xs uppercase tracking-wide text-zinc-500 mb-1 font-mono">
                  Exemple curl
                </div>
                <pre className="bg-zinc-950/80 border border-white/10 rounded-lg p-3 text-xs overflow-x-auto text-zinc-300">
                  <code>{ep.curl}</code>
                </pre>
              </div>
              {ep.sample && (
                <div>
                  <div className="text-xs uppercase tracking-wide text-zinc-500 mb-1 font-mono">
                    Réponse exemple
                  </div>
                  <pre className="bg-zinc-950/80 border border-white/10 rounded-lg p-3 text-xs overflow-x-auto text-zinc-300">
                    <code>{ep.sample}</code>
                  </pre>
                </div>
              )}
            </Panel>
          ))}
        </div>

        {/* Footer card */}
        <Panel className="p-6">
          <h2 className="text-base font-semibold text-zinc-100 mb-3">
            Stabilité et versioning
          </h2>
          <div className="text-sm text-zinc-400 space-y-2">
            <p>
              Cette API est versionnée par préfixe (
              <code className="bg-zinc-900 border border-white/10 text-emerald-300 px-1 py-0.5 rounded font-mono">
                /api/v1/
              </code>
              ). Les endpoints existants ne changeront pas de signature sans
              version majeure ; les ajouts (nouveaux champs, nouveaux endpoints)
              peuvent arriver sans préavis.
            </p>
            <p>
              Bug, demande d&apos;endpoint, ou question : écris à{" "}
              <a
                href="mailto:tokamdarius@gmail.com"
                className="text-emerald-400 hover:text-emerald-300 hover:underline"
              >
                tokamdarius@gmail.com
              </a>
              .
            </p>
          </div>
        </Panel>
      </main>

      <MarketingFooter />
    </div>
  );
}
