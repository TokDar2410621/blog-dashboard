import type { Metadata } from "next";
import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ArrowLeft, Key, Code2, Zap, ShieldCheck } from "lucide-react";
import Terminal3D from "@/components/Terminal3D";

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
    title: "Identite du compte",
    desc: "Verifie ton token et recupere ton plan + ta limite horaire.",
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
    desc: "Retourne tous les sites actifs lies a ton compte.",
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
    title: "Generer un article complet",
    desc: "Le generateur IA produit un article SEO-ready et le publie. Coute du temps GPU. Utilise avec parcimonie.",
    curl: `curl -X POST -H "Authorization: Bearer btb_xxx" \\\n  -H "Content-Type: application/json" \\\n  -d '{"topic":"Comment choisir un CRM PME au Quebec","article_type":"guide","length":"long","language":"fr"}' \\\n  ${BASE}/sites/12/generate/`,
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
    desc: "Brief structure (intent, sous-sujets, entites, FAQ) a partir d'un mot-cle cible.",
    curl: `curl -X POST -H "Authorization: Bearer btb_xxx" \\\n  -H "Content-Type: application/json" \\\n  -d '{"keyword":"meilleur crm pme quebec","language":"fr"}' \\\n  ${BASE}/brief/`,
  },
  {
    method: "GET",
    path: "/sites/{id}/keywords/",
    title: "Mots-cles suivis",
    desc: "Liste des mots-cles trackes + derniere position connue.",
    curl: `curl -H "Authorization: Bearer btb_xxx" \\\n  ${BASE}/sites/12/keywords/`,
  },
  {
    method: "POST",
    path: "/sites/{id}/keywords/snapshot/",
    title: "Lancer un snapshot de positions",
    desc: "Crawl SERP immediat pour mettre a jour les positions. Compte dans ta limite horaire.",
    curl: `curl -X POST -H "Authorization: Bearer btb_xxx" \\\n  ${BASE}/sites/12/keywords/snapshot/`,
  },
  {
    method: "GET",
    path: "/sites/{id}/digest/weekly/",
    title: "Digest hebdomadaire",
    desc: "Snapshot hebdomadaire (publications, audit, mots-cles). Pratique en cron pour Slack/email.",
    curl: `curl -H "Authorization: Bearer btb_xxx" \\\n  ${BASE}/sites/12/digest/weekly/`,
  },
];

const methodColor: Record<string, string> = {
  GET: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/30",
  POST: "bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/30",
  DELETE: "bg-destructive/10 text-destructive border-destructive/30",
};

export default function ApiDocs() {
  return (
    <div className="min-h-screen bg-background p-6">
      <div className="max-w-5xl mx-auto space-y-8">
        <div className="flex items-center gap-3">
          <Link href="/">
            <Button variant="ghost" size="icon" title="Retour">
              <ArrowLeft className="h-5 w-5" />
            </Button>
          </Link>
          <div className="flex-1">
            <h1 className="text-3xl font-bold flex items-center gap-2">
              <Code2 className="h-7 w-7 text-primary" />
              API REST publique
            </h1>
            <p className="text-muted-foreground mt-1">
              Integre Gridar a n8n, Zapier, Make ou tes propres scripts.
              Authentification par Bearer token.
            </p>
          </div>
          <a href={`${DASHBOARD_URL}/account/api-keys`}>
            <Button>
              <Key className="h-4 w-4 mr-2" />
              Mes cles API
            </Button>
          </a>
        </div>

        <div className="rounded-2xl border border-border/50 bg-zinc-950 overflow-hidden">
          <div
            className="relative"
            style={{
              background:
                "radial-gradient(50% 80% at 50% 0%, rgba(16,185,129,0.10), transparent 70%)",
            }}
          >
            <Terminal3D />
          </div>
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Zap className="h-5 w-5 text-primary" />
              Demarrage rapide
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <ol className="list-decimal list-inside space-y-2 text-sm">
              <li>
                Cree un token sur{" "}
                <a
                  href={`${DASHBOARD_URL}/account/api-keys`}
                  className="text-primary underline hover:opacity-80"
                >
                  /account/api-keys
                </a>
                . Copie-le immediatement (il ne sera plus jamais affiche).
              </li>
              <li>
                Envoie-le dans l&apos;en-tete{" "}
                <code className="bg-muted px-1.5 py-0.5 rounded text-xs">
                  Authorization: Bearer btb_xxx
                </code>
                .
              </li>
              <li>
                Toutes les reponses sont en JSON. Erreurs : code HTTP standard +{" "}
                <code className="bg-muted px-1.5 py-0.5 rounded text-xs">
                  {`{"error": "..."}`}
                </code>
                .
              </li>
            </ol>
            <pre className="bg-muted/50 border border-border/50 rounded p-3 text-xs overflow-x-auto">
              <code>{`curl -H "Authorization: Bearer btb_xxx" ${BASE}/me/`}</code>
            </pre>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ShieldCheck className="h-5 w-5 text-primary" />
              Limites par plan
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
              <div className="border border-border/50 rounded p-4">
                <div className="font-semibold">Essai (gratuit)</div>
                <div className="text-muted-foreground mt-1">
                  Pas d&apos;acces API.
                </div>
              </div>
              <div className="border border-emerald-500/40 rounded p-4 bg-emerald-500/5">
                <div className="font-semibold">Pro</div>
                <div className="text-muted-foreground mt-1">
                  60 requetes / heure / utilisateur
                </div>
              </div>
              <div className="border border-border/50 rounded p-4">
                <div className="font-semibold">Agence</div>
                <div className="text-muted-foreground mt-1">
                  600 requetes / heure / utilisateur
                </div>
              </div>
            </div>
            <p className="text-xs text-muted-foreground mt-3">
              Au-dela de la limite : reponse{" "}
              <code className="bg-muted px-1 py-0.5 rounded">429</code> avec un
              entete <code className="bg-muted px-1 py-0.5 rounded">Retry-After</code>.
            </p>
          </CardContent>
        </Card>

        <div className="space-y-4">
          <h2 className="text-xl font-bold">Endpoints</h2>
          {ENDPOINTS.map((ep) => (
            <Card key={ep.method + ep.path}>
              <CardHeader>
                <div className="flex flex-wrap items-center gap-3">
                  <span
                    className={`text-xs font-mono px-2 py-1 rounded border ${methodColor[ep.method]}`}
                  >
                    {ep.method}
                  </span>
                  <code className="text-sm font-mono">{ep.path}</code>
                </div>
                <CardTitle className="text-base mt-2">{ep.title}</CardTitle>
                <p className="text-sm text-muted-foreground">{ep.desc}</p>
              </CardHeader>
              <CardContent className="space-y-3">
                <div>
                  <div className="text-xs uppercase tracking-wide text-muted-foreground mb-1">
                    Exemple curl
                  </div>
                  <pre className="bg-muted/50 border border-border/50 rounded p-3 text-xs overflow-x-auto">
                    <code>{ep.curl}</code>
                  </pre>
                </div>
                {ep.sample && (
                  <div>
                    <div className="text-xs uppercase tracking-wide text-muted-foreground mb-1">
                      Reponse exemple
                    </div>
                    <pre className="bg-muted/50 border border-border/50 rounded p-3 text-xs overflow-x-auto">
                      <code>{ep.sample}</code>
                    </pre>
                  </div>
                )}
              </CardContent>
            </Card>
          ))}
        </div>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Stabilite et versioning</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground space-y-2">
            <p>
              Cette API est versionnee par prefixe (
              <code className="bg-muted px-1 py-0.5 rounded">/api/v1/</code>).
              Les endpoints existants ne changeront pas de signature sans
              version majeure ; les ajouts (nouveaux champs, nouveaux endpoints)
              peuvent arriver sans preavis.
            </p>
            <p>
              Bug, demande d&apos;endpoint, ou question : ecris a{" "}
              <a
                href="mailto:tokamdarius@gmail.com"
                className="text-primary underline hover:opacity-80"
              >
                tokamdarius@gmail.com
              </a>
              .
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
