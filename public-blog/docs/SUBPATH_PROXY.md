# Servir le blog sous `tonsite.ca/blog`

Trois patterns de proxy reverse selon ton hébergeur. Le plus SEO-optimal : tout
le jus de domaine reste sur ton site principal — Google traite `/blog` comme
une section de ton domaine, pas un site externe.

## Pattern A — Cloudflare Worker (recommandé, gratuit, marche partout)

Pré-requis : ton DNS pointe vers Cloudflare (passage gratuit avec son plan
gratuit).

1. Cloudflare Dashboard → ton domaine → **Workers Routes** → **Create Worker**.
2. Colle ce code dans le Worker :

```javascript
// blog-proxy.js — proxy /blog/* du site principal vers blog-dashboard-public
const BLOG_HOST = 'blog-dashboard-public.vercel.app'; // remplace si custom Vercel

export default {
  async fetch(request) {
    const url = new URL(request.url);

    // On ne proxy que /blog et /blog/...
    if (!url.pathname.startsWith('/blog')) {
      return fetch(request);
    }

    // Réécrit /blog/foo → /foo (la home Next.js est sur /, pas /blog)
    let upstreamPath = url.pathname.replace(/^\/blog/, '') || '/';
    const upstream = new URL(`https://${BLOG_HOST}${upstreamPath}${url.search}`);

    // Forward avec le Host original pour que le Next.js identifie bien le site
    const proxyReq = new Request(upstream, {
      method: request.method,
      headers: {
        ...Object.fromEntries(request.headers),
        host: url.hostname, // ← critique : passe ton domaine, pas celui de Vercel
        'x-forwarded-host': url.hostname,
        'x-forwarded-proto': 'https',
      },
      body: request.body,
    });

    const resp = await fetch(proxyReq);

    // Réécrit les liens absolus dans le HTML pour qu'ils restent sur ton domaine
    const ct = resp.headers.get('content-type') || '';
    if (!ct.includes('text/html')) return resp;

    let html = await resp.text();
    // Réécrit href="/foo" → href="/blog/foo" pour les liens internes du blog
    html = html.replace(/href="\/(?!blog\/|blog$|http)/g, 'href="/blog/');
    html = html.replace(/src="\/(?!_next\/|http|static\/)/g, 'src="/blog/');

    return new Response(html, {
      status: resp.status,
      headers: resp.headers,
    });
  },
};
```

3. Onglet **Triggers** du Worker → ajouter une route :
   - Route : `tonsite.ca/blog*`
   - Worker : (le worker que tu viens de créer)

4. Backend dashboard : dans Settings du site, mets `tonsite.ca` comme
   `public_blog_domain` (pas `blog.tonsite.ca`). Le Worker forward le Host à
   `blog-dashboard-public.vercel.app`, qui interroge l'API avec ce host, qui
   te retrouve.

5. Test : visite `https://tonsite.ca/blog` → devrait afficher la liste
   d'articles.

---

## Pattern B — Vercel rewrites (si ton site principal est sur Vercel)

Si ton site principal `tonsite.ca` est déjà sur Vercel, ajoute dans son
`vercel.json` :

```json
{
  "rewrites": [
    {
      "source": "/blog",
      "destination": "https://blog-dashboard-public.vercel.app/"
    },
    {
      "source": "/blog/:path*",
      "destination": "https://blog-dashboard-public.vercel.app/:path*"
    }
  ]
}
```

Pareil pour `next.config.js` Next.js 14+ :

```javascript
module.exports = {
  async rewrites() {
    return [
      { source: '/blog', destination: 'https://blog-dashboard-public.vercel.app' },
      { source: '/blog/:path*', destination: 'https://blog-dashboard-public.vercel.app/:path*' },
    ];
  },
};
```

Limitation : Vercel rewrites passe le Host de l'upstream (Vercel), pas le tien.
Pour résoudre proprement le site, il faut soit utiliser Pattern A
(Cloudflare), soit définir `NEXT_PUBLIC_SITE_ID=<ton-id>` dans les env vars
Vercel du projet `blog-dashboard-public` (mode mono-tenant).

---

## Pattern C — Nginx reverse proxy (VPS / hébergeur custom)

Dans ta config Nginx :

```nginx
location /blog {
  proxy_pass https://blog-dashboard-public.vercel.app/;
  proxy_set_header Host tonsite.ca;
  proxy_set_header X-Forwarded-Host tonsite.ca;
  proxy_set_header X-Forwarded-Proto https;
  proxy_ssl_server_name on;
}

location /blog/ {
  proxy_pass https://blog-dashboard-public.vercel.app/;
  proxy_set_header Host tonsite.ca;
  proxy_set_header X-Forwarded-Host tonsite.ca;
  proxy_set_header X-Forwarded-Proto https;
  proxy_ssl_server_name on;
}
```

Reload Nginx : `sudo nginx -s reload`.

---

## Pattern D — Apache .htaccess (cPanel / hébergement mutualisé)

```apacheconf
RewriteEngine On
RewriteRule ^blog$ https://blog-dashboard-public.vercel.app/ [P,L]
RewriteRule ^blog/(.*)$ https://blog-dashboard-public.vercel.app/$1 [P,L]
```

Nécessite que `mod_proxy` et `mod_rewrite` soient activés (la plupart le sont).

---

## SEO impact (le pourquoi de tout ça)

| Pattern | Domaine SEO du blog | Jus partagé avec site principal |
|---|---|---|
| Sous-domaine séparé `blog.tonsite.ca` | Sous-domaine | Partiel (Google les rapproche) |
| Sous-chemin `tonsite.ca/blog` (proxy) | Domaine principal | **Complet** ✅ |
| Domaine externe `monsite.blog-quebec.ca` | Domaine externe | Aucun ❌ |

Pour un blog SEO en 2026, le **sous-chemin** est le standard. Tous les
gros sites (HubSpot, Stripe, Shopify) font comme ça.

---

## Aide

Si ton hébergeur ne permet aucun de ces 4 patterns, tu peux toujours utiliser
le mode sous-domaine custom (`blog.tonsite.ca`) qui ne demande qu'un CNAME
DNS.

Si tu bloques sur la config DNS / Worker, contacte Darius — il a vécu chaque
hébergeur québécois (Hostinger, OVH, GoDaddy, Cloudflare, Vercel) et peut
te débloquer en 15 minutes.
