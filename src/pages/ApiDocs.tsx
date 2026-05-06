import { useNavigate } from "react-router-dom";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ArrowLeft, Key, Code2, Zap, ShieldCheck } from "lucide-react";

const BASE = "https://api.blog-dashboard.ca/api/v1";

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
    desc: "Le générateur IA produit un article SEO-ready et le publie. Coûte du temps GPU — utilise avec parcimonie.",
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
    curl: `curl -X POST -H "Authorization: Bearer btb_xxx" \\\n  -H "Content-Type: application/json" \\\n  -d '{"keyword":"meilleur crm pme québec","language":"fr"}' \\\n  ${BASE}/brief/`,
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

const methodColor: Record<string, string> = {
  GET: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/30",
  POST: "bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/30",
  DELETE: "bg-destructive/10 text-destructive border-destructive/30",
};

export default function ApiDocs() {
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-background p-6">
      <div className="max-w-5xl mx-auto space-y-8">
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => navigate(-1)}
            title="Retour"
          >
            <ArrowLeft className="h-5 w-5" />
          </Button>
          <div className="flex-1">
            <h1 className="text-3xl font-bold flex items-center gap-2">
              <Code2 className="h-7 w-7 text-primary" />
              API REST publique
            </h1>
            <p className="text-muted-foreground mt-1">
              Intègre blog-dashboard à n8n, Zapier, Make ou tes propres scripts.
              Authentification par Bearer token.
            </p>
          </div>
          <Button onClick={() => navigate("/account/api-keys")}>
            <Key className="h-4 w-4 mr-2" />
            Mes clés API
          </Button>
        </div>

        {/* Quickstart */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Zap className="h-5 w-5 text-primary" />
              Démarrage rapide
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <ol className="list-decimal list-inside space-y-2 text-sm">
              <li>
                Crée un token sur{" "}
                <button
                  className="text-primary underline hover:opacity-80"
                  onClick={() => navigate("/account/api-keys")}
                >
                  /account/api-keys
                </button>
                . Copie-le immédiatement (il ne sera plus jamais affiché).
              </li>
              <li>
                Envoie-le dans l'en-tête{" "}
                <code className="bg-muted px-1.5 py-0.5 rounded text-xs">
                  Authorization: Bearer btb_xxx
                </code>
                .
              </li>
              <li>
                Toutes les réponses sont en JSON. Erreurs : code HTTP standard +{" "}
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

        {/* Limits */}
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
                  Pas d'accès API.
                </div>
              </div>
              <div className="border border-emerald-500/40 rounded p-4 bg-emerald-500/5">
                <div className="font-semibold">Pro</div>
                <div className="text-muted-foreground mt-1">
                  60 requêtes / heure / utilisateur
                </div>
              </div>
              <div className="border border-border/50 rounded p-4">
                <div className="font-semibold">Agence</div>
                <div className="text-muted-foreground mt-1">
                  600 requêtes / heure / utilisateur
                </div>
              </div>
            </div>
            <p className="text-xs text-muted-foreground mt-3">
              Au-delà de la limite : réponse{" "}
              <code className="bg-muted px-1 py-0.5 rounded">429</code> avec un
              entête <code className="bg-muted px-1 py-0.5 rounded">Retry-After</code>.
            </p>
          </CardContent>
        </Card>

        {/* Endpoints */}
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
                      Réponse exemple
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
            <CardTitle className="text-base">Stabilité & versioning</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground space-y-2">
            <p>
              Cette API est versionnée par préfixe (
              <code className="bg-muted px-1 py-0.5 rounded">/api/v1/</code>).
              Les endpoints existants ne changeront pas de signature sans
              version majeure ; les ajouts (nouveaux champs, nouveaux endpoints)
              peuvent arriver sans préavis.
            </p>
            <p>
              Bug, demande d'endpoint, ou question : écris à{" "}
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
