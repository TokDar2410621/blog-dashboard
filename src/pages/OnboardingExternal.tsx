import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { authFetch } from "@/lib/api-client";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Code2,
  ArrowLeft,
  Copy,
  Check,
  ExternalLink,
  Sparkles,
  Globe,
} from "lucide-react";
import { toast } from "sonner";

type Site = { id: number; name: string; domain: string };
type Framework =
  | "next-app"
  | "next-pages"
  | "react-router"
  | "vite-spa";

const FRAMEWORKS: { key: Framework; label: string; subtitle: string }[] = [
  { key: "next-app", label: "Next.js (App Router)", subtitle: "app/blog/page.tsx" },
  { key: "next-pages", label: "Next.js (Pages Router)", subtitle: "pages/blog/index.tsx" },
  { key: "react-router", label: "React + react-router-dom", subtitle: "/blog routes" },
  { key: "vite-spa", label: "Vite SPA (sans router)", subtitle: "fetch côté client" },
];

const API_BASE = "https://api.blog-dashboard.ca/api/v1";

// ----- Code templates per framework ----------------------------------------

function blogListCode(framework: Framework, siteId: number) {
  const list = `${API_BASE}/sites/${siteId}/articles/?status=published`;
  if (framework === "next-app") {
    return `// app/blog/page.tsx
async function getArticles() {
  const res = await fetch(
    "${list}",
    {
      headers: { Authorization: \`Bearer \${process.env.BLOG_DASHBOARD_TOKEN}\` },
      next: { revalidate: 600 }, // ISR: 10 min
    }
  );
  if (!res.ok) return { results: [] };
  return res.json();
}

export default async function BlogPage() {
  const { results } = await getArticles();
  return (
    <main className="max-w-3xl mx-auto py-12 px-4">
      <h1 className="text-4xl font-bold mb-8">Blog</h1>
      <ul className="space-y-4">
        {results.map((p: any) => (
          <li key={p.slug} className="border-b pb-4">
            <a href={\`/blog/\${p.slug}\`} className="text-xl font-semibold hover:underline">
              {p.title}
            </a>
            <p className="text-sm text-gray-600 mt-1">{p.excerpt}</p>
            <p className="text-xs text-gray-500 mt-1">{p.published_at}</p>
          </li>
        ))}
      </ul>
    </main>
  );
}
`;
  }
  if (framework === "next-pages") {
    return `// pages/blog/index.tsx
import type { GetStaticProps } from 'next';

export const getStaticProps: GetStaticProps = async () => {
  const res = await fetch("${list}", {
    headers: { Authorization: \`Bearer \${process.env.BLOG_DASHBOARD_TOKEN}\` },
  });
  const data = res.ok ? await res.json() : { results: [] };
  return { props: { articles: data.results }, revalidate: 600 };
};

export default function BlogIndex({ articles }: { articles: any[] }) {
  return (
    <main className="max-w-3xl mx-auto py-12 px-4">
      <h1 className="text-4xl font-bold mb-8">Blog</h1>
      <ul className="space-y-4">
        {articles.map((p) => (
          <li key={p.slug} className="border-b pb-4">
            <a href={\`/blog/\${p.slug}\`} className="text-xl font-semibold hover:underline">{p.title}</a>
            <p className="text-sm text-gray-600 mt-1">{p.excerpt}</p>
          </li>
        ))}
      </ul>
    </main>
  );
}
`;
  }
  if (framework === "react-router") {
    return `// src/pages/BlogList.tsx
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

export default function BlogList() {
  const [articles, setArticles] = useState<any[]>([]);
  useEffect(() => {
    fetch("${list}", {
      headers: { Authorization: \`Bearer \${import.meta.env.VITE_BLOG_DASHBOARD_TOKEN}\` },
    })
      .then(r => r.ok ? r.json() : { results: [] })
      .then(d => setArticles(d.results || []));
  }, []);
  return (
    <main className="max-w-3xl mx-auto py-12 px-4">
      <h1 className="text-4xl font-bold mb-8">Blog</h1>
      <ul className="space-y-4">
        {articles.map(p => (
          <li key={p.slug} className="border-b pb-4">
            <Link to={\`/blog/\${p.slug}\`} className="text-xl font-semibold hover:underline">{p.title}</Link>
            <p className="text-sm text-gray-600 mt-1">{p.excerpt}</p>
          </li>
        ))}
      </ul>
    </main>
  );
}

// In App.tsx — register the route:
// <Route path="/blog" element={<BlogList />} />
// <Route path="/blog/:slug" element={<BlogPost />} />
`;
  }
  // vite-spa
  return `// src/pages/Blog.tsx — Vite SPA, no router (use #/blog hash)
import { useEffect, useState } from "react";

export default function Blog() {
  const [articles, setArticles] = useState<any[]>([]);
  useEffect(() => {
    fetch("${list}", {
      headers: { Authorization: \`Bearer \${import.meta.env.VITE_BLOG_DASHBOARD_TOKEN}\` },
    })
      .then(r => r.json())
      .then(d => setArticles(d.results || []));
  }, []);
  return (
    <main>
      <h1>Blog</h1>
      {articles.map(p => (
        <article key={p.slug}>
          <h2>{p.title}</h2>
          <p>{p.excerpt}</p>
        </article>
      ))}
    </main>
  );
}
`;
}

function blogPostCode(framework: Framework, siteId: number) {
  const detail = `${API_BASE}/sites/${siteId}/articles/`;
  if (framework === "next-app") {
    return `// app/blog/[slug]/page.tsx
async function getArticle(slug: string) {
  const res = await fetch(
    "${detail}" + slug + "/",
    {
      headers: { Authorization: \`Bearer \${process.env.BLOG_DASHBOARD_TOKEN}\` },
      next: { revalidate: 600 },
    }
  );
  if (!res.ok) return null;
  return res.json();
}

export default async function ArticlePage({ params }: { params: { slug: string } }) {
  const article = await getArticle(params.slug);
  if (!article) return <main className="py-12 text-center">Article introuvable.</main>;
  return (
    <main className="max-w-3xl mx-auto py-12 px-4">
      {article.cover_image && <img src={article.cover_image} alt="" className="w-full rounded mb-6" />}
      <h1 className="text-4xl font-bold mb-2">{article.title}</h1>
      <p className="text-sm text-gray-500 mb-6">{article.published_at}</p>
      <article className="prose lg:prose-lg" dangerouslySetInnerHTML={{ __html: article.content }} />
    </main>
  );
}
`;
  }
  if (framework === "next-pages") {
    return `// pages/blog/[slug].tsx
import type { GetStaticProps, GetStaticPaths } from 'next';

export const getStaticPaths: GetStaticPaths = async () => {
  const res = await fetch("${API_BASE}/sites/${siteId}/articles/?status=published", {
    headers: { Authorization: \`Bearer \${process.env.BLOG_DASHBOARD_TOKEN}\` },
  });
  const data = res.ok ? await res.json() : { results: [] };
  return {
    paths: data.results.map((p: any) => ({ params: { slug: p.slug } })),
    fallback: 'blocking',
  };
};

export const getStaticProps: GetStaticProps = async ({ params }) => {
  const res = await fetch("${detail}" + params!.slug + "/", {
    headers: { Authorization: \`Bearer \${process.env.BLOG_DASHBOARD_TOKEN}\` },
  });
  if (!res.ok) return { notFound: true };
  return { props: { article: await res.json() }, revalidate: 600 };
};

export default function ArticlePage({ article }: { article: any }) {
  return (
    <main className="max-w-3xl mx-auto py-12 px-4">
      <h1 className="text-4xl font-bold mb-2">{article.title}</h1>
      <article className="prose" dangerouslySetInnerHTML={{ __html: article.content }} />
    </main>
  );
}
`;
  }
  if (framework === "react-router") {
    return `// src/pages/BlogPost.tsx
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

export default function BlogPost() {
  const { slug } = useParams<{ slug: string }>();
  const [article, setArticle] = useState<any>(null);
  useEffect(() => {
    if (!slug) return;
    fetch(\`${detail}\${slug}/\`, {
      headers: { Authorization: \`Bearer \${import.meta.env.VITE_BLOG_DASHBOARD_TOKEN}\` },
    })
      .then(r => r.ok ? r.json() : null)
      .then(setArticle);
  }, [slug]);
  if (!article) return <p>Chargement...</p>;
  return (
    <main className="max-w-3xl mx-auto py-12 px-4">
      <h1 className="text-4xl font-bold mb-2">{article.title}</h1>
      <article className="prose" dangerouslySetInnerHTML={{ __html: article.content }} />
    </main>
  );
}
`;
  }
  return `// src/pages/Article.tsx — Vite SPA
import { useEffect, useState } from "react";

export default function Article({ slug }: { slug: string }) {
  const [article, setArticle] = useState<any>(null);
  useEffect(() => {
    fetch(\`${detail}\${slug}/\`, {
      headers: { Authorization: \`Bearer \${import.meta.env.VITE_BLOG_DASHBOARD_TOKEN}\` },
    })
      .then(r => r.json())
      .then(setArticle);
  }, [slug]);
  if (!article) return <p>...</p>;
  return (
    <article>
      <h1>{article.title}</h1>
      <div dangerouslySetInnerHTML={{ __html: article.content }} />
    </article>
  );
}
`;
}

function sitemapCode(framework: Framework, siteId: number, domain: string) {
  // For next-app and next-pages we generate the sitemap via Next.js, but the
  // simplest path is to proxy our /api/sites/<id>/sitemap.xml endpoint.
  // For react-router / vite-spa we tell the user to host a redirect at /sitemap.xml.
  if (framework === "next-app") {
    return `// app/sitemap.xml/route.ts — proxy our sitemap to your domain
export async function GET() {
  const res = await fetch(
    "https://api.blog-dashboard.ca/api/sites/${siteId}/sitemap.xml",
    { next: { revalidate: 3600 } }
  );
  const xml = await res.text();
  return new Response(xml, {
    headers: {
      "Content-Type": "application/xml; charset=utf-8",
      "Cache-Control": "public, max-age=3600",
    },
  });
}

// app/rss.xml/route.ts — same idea
export async function GET() {
  const res = await fetch(
    "https://api.blog-dashboard.ca/api/sites/${siteId}/rss.xml",
    { next: { revalidate: 3600 } }
  );
  const xml = await res.text();
  return new Response(xml, {
    headers: {
      "Content-Type": "application/rss+xml; charset=utf-8",
      "Cache-Control": "public, max-age=3600",
    },
  });
}
`;
  }
  if (framework === "next-pages") {
    return `// pages/sitemap.xml.ts
import type { GetServerSideProps } from 'next';

export const getServerSideProps: GetServerSideProps = async ({ res }) => {
  const upstream = await fetch(
    "https://api.blog-dashboard.ca/api/sites/${siteId}/sitemap.xml"
  );
  const xml = await upstream.text();
  res.setHeader("Content-Type", "application/xml; charset=utf-8");
  res.setHeader("Cache-Control", "public, max-age=3600");
  res.write(xml);
  res.end();
  return { props: {} };
};

export default function Sitemap() { return null; }
`;
  }
  // For SPAs (react-router/vite-spa), the cleanest path is host-level proxy
  // in vercel.json / netlify.toml / nginx.
  return `# Pour exposer le sitemap sur ${domain || "ton-domaine.com"}/sitemap.xml,
# ajoute une rewrite dans la config de ton hébergeur :

# === Si tu es sur Vercel — vercel.json ===
{
  "rewrites": [
    {
      "source": "/sitemap.xml",
      "destination": "https://api.blog-dashboard.ca/api/sites/${siteId}/sitemap.xml"
    },
    {
      "source": "/rss.xml",
      "destination": "https://api.blog-dashboard.ca/api/sites/${siteId}/rss.xml"
    }
  ]
}

# === Si tu es sur Netlify — _redirects ===
/sitemap.xml  https://api.blog-dashboard.ca/api/sites/${siteId}/sitemap.xml  200
/rss.xml      https://api.blog-dashboard.ca/api/sites/${siteId}/rss.xml      200

# === Si tu as un backend Python (Django/FastAPI) qui sert le frontend ===
# Ajoute une route qui proxy notre endpoint, idem.
`;
}

// ---------------------------------------------------------------------------

export default function OnboardingExternal() {
  const navigate = useNavigate();
  const [framework, setFramework] = useState<Framework>("next-app");
  const [siteId, setSiteId] = useState<number | null>(null);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  const { data: sitesData } = useQuery<{ results: Site[] }>({
    queryKey: ["v1-sites"],
    queryFn: async () => {
      const res = await authFetch("/sites/");
      if (!res.ok) throw new Error("sites fetch failed");
      const data = await res.json();
      // sites endpoint returns array directly — normalize
      const sites = Array.isArray(data) ? data : data.results || [];
      return { results: sites };
    },
  });

  const sites = sitesData?.results || [];
  const selectedSite = useMemo(
    () => sites.find((s) => s.id === siteId) || null,
    [sites, siteId]
  );

  const copy = async (key: string, text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedKey(key);
      setTimeout(() => setCopiedKey(null), 1800);
      toast.success("Copié dans le presse-papier");
    } catch {
      toast.error("Copie échouée");
    }
  };

  const blocks = useMemo(() => {
    if (!siteId) return null;
    return {
      list: blogListCode(framework, siteId),
      detail: blogPostCode(framework, siteId),
      sitemap: sitemapCode(framework, siteId, selectedSite?.domain || ""),
    };
  }, [framework, siteId, selectedSite]);

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
          <div className="flex-1">
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <Code2 className="h-6 w-6 text-primary" />
              Onboarding mode externe
            </h1>
            <p className="text-muted-foreground">
              Tu as déjà un site React ou Next.js. On te génère le code à coller
              pour afficher tes articles sur ton domaine — SEO 100 % bonifié.
            </p>
          </div>
        </div>

        {/* Step 1: Pick a site */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Globe className="h-5 w-5 text-primary" />
              1. Site source
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {sites.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                Aucun site dans ton compte. Connecte-en un d'abord (WordPress,
                Shopify, Webflow, ou crée un blog hébergé).
              </p>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                {sites.map((s) => (
                  <button
                    key={s.id}
                    onClick={() => setSiteId(s.id)}
                    className={`text-left rounded border p-3 transition-colors ${
                      siteId === s.id
                        ? "border-primary bg-primary/5"
                        : "border-border/50 hover:border-border"
                    }`}
                  >
                    <div className="font-medium text-sm">{s.name}</div>
                    <div className="text-xs text-muted-foreground">
                      site_id: <code className="font-mono">{s.id}</code>
                      {s.domain ? ` · ${s.domain}` : ""}
                    </div>
                  </button>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Step 2: Pick a framework */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Sparkles className="h-5 w-5 text-primary" />
              2. Framework du frontend
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              {FRAMEWORKS.map((f) => (
                <button
                  key={f.key}
                  onClick={() => setFramework(f.key)}
                  className={`rounded border p-3 text-left transition-colors ${
                    framework === f.key
                      ? "border-primary bg-primary/5"
                      : "border-border/50 hover:border-border"
                  }`}
                >
                  <div className="font-medium text-sm">{f.label}</div>
                  <div className="text-[11px] text-muted-foreground mt-1">
                    {f.subtitle}
                  </div>
                </button>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Step 3: Token reminder */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">
              3. Crée un token API
            </CardTitle>
          </CardHeader>
          <CardContent className="text-sm space-y-3">
            <p>
              Va sur{" "}
              <button
                className="text-primary underline hover:opacity-80"
                onClick={() => navigate("/account/api-keys")}
              >
                /account/api-keys
              </button>{" "}
              et crée un token (par ex. "site-prod"). Copie-le tout de suite —
              tu ne pourras plus le voir après.
            </p>
            <p>
              Stocke-le dans une variable d'environnement :
            </p>
            <pre className="bg-muted/50 border border-border/50 rounded p-3 text-xs overflow-x-auto">
              <code>
                {framework.startsWith("next")
                  ? "BLOG_DASHBOARD_TOKEN=btb_xxxxxxxxxxxxxxxxx"
                  : "VITE_BLOG_DASHBOARD_TOKEN=btb_xxxxxxxxxxxxxxxxx"}
              </code>
            </pre>
          </CardContent>
        </Card>

        {/* Step 4: Generated code */}
        {siteId && blocks && (
          <>
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="text-lg">
                    4a. Liste des articles
                  </CardTitle>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => copy("list", blocks.list)}
                  >
                    {copiedKey === "list" ? (
                      <>
                        <Check className="h-4 w-4 mr-1" /> Copié
                      </>
                    ) : (
                      <>
                        <Copy className="h-4 w-4 mr-1" /> Copier
                      </>
                    )}
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                <pre className="bg-muted/50 border border-border/50 rounded p-3 text-xs overflow-x-auto max-h-96">
                  <code>{blocks.list}</code>
                </pre>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="text-lg">
                    4b. Page article
                  </CardTitle>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => copy("detail", blocks.detail)}
                  >
                    {copiedKey === "detail" ? (
                      <>
                        <Check className="h-4 w-4 mr-1" /> Copié
                      </>
                    ) : (
                      <>
                        <Copy className="h-4 w-4 mr-1" /> Copier
                      </>
                    )}
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                <pre className="bg-muted/50 border border-border/50 rounded p-3 text-xs overflow-x-auto max-h-96">
                  <code>{blocks.detail}</code>
                </pre>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle className="text-lg">
                    4c. sitemap.xml + rss.xml (essentiel SEO)
                  </CardTitle>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => copy("sitemap", blocks.sitemap)}
                  >
                    {copiedKey === "sitemap" ? (
                      <>
                        <Check className="h-4 w-4 mr-1" /> Copié
                      </>
                    ) : (
                      <>
                        <Copy className="h-4 w-4 mr-1" /> Copier
                      </>
                    )}
                  </Button>
                </div>
              </CardHeader>
              <CardContent>
                <pre className="bg-muted/50 border border-border/50 rounded p-3 text-xs overflow-x-auto max-h-96">
                  <code>{blocks.sitemap}</code>
                </pre>
                <p className="text-xs text-muted-foreground mt-3">
                  Une fois en place, soumets{" "}
                  <code className="bg-muted px-1 rounded">
                    {selectedSite?.domain || "ton-domaine.com"}/sitemap.xml
                  </code>{" "}
                  à Google Search Console (Sitemaps → Add a new sitemap).
                </p>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-lg">5. Tester l'API directement</CardTitle>
              </CardHeader>
              <CardContent className="space-y-2">
                <p className="text-sm text-muted-foreground">
                  Avant de coder, vérifie que ton token marche :
                </p>
                <pre className="bg-muted/50 border border-border/50 rounded p-3 text-xs overflow-x-auto">
                  <code>{`curl -H "Authorization: Bearer btb_xxx" \\
  ${API_BASE}/sites/${siteId}/articles/`}</code>
                </pre>
                <a
                  href="/api-docs"
                  className="inline-flex items-center gap-1 text-sm text-primary hover:underline"
                >
                  Voir la doc API complète{" "}
                  <ExternalLink className="h-3 w-3" />
                </a>
              </CardContent>
            </Card>
          </>
        )}
      </div>
    </div>
  );
}
