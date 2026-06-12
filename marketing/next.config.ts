import type { NextConfig } from "next";
import path from "node:path";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "https://api.gridar.app";

const nextConfig: NextConfig = {
  // Django's URLs all end with a trailing slash (DRF convention) and its
  // APPEND_SLASH middleware 301s slashless paths back to the slashed form.
  // Next.js' default trailing-slash normalization 308s the slashed form to
  // slashless BEFORE the /api rewrite runs - the two redirects ping-pong
  // forever (ERR_TOO_MANY_REDIRECTS on every /api call). Disable Next's
  // automatic handling; middleware.ts re-applies it for page routes only.
  skipTrailingSlashRedirect: true,

  // Lock turbopack root to this folder. Without this Next picks up the
  // package-lock.json in the parent directory (Vite app) and warns.
  turbopack: {
    root: path.resolve(__dirname),
  },

  // This app IS gridar.app: it serves the whole public surface natively
  // (landing, blog, docs, audit, hosted landings, proof, legal) and proxies
  // two things to keep everything same-origin:
  //
  // 1. The Django backend (/api, /admin, /accounts) -> api.gridar.app.
  //    Same-origin /api/* keeps the httpOnly auth cookie on gridar.app,
  //    kills CORS preflights, and lets the landing AuthContext see the
  //    session the dashboard opened.
  //
  // 2. The Vite SPA (the actual product app) for every app route: /login,
  //    /sites, /dashboard/*, OAuth callbacks, billing... plus the SPA's
  //    own static assets (/assets, /icons, manifest, service worker).
  //    DASHBOARD_INTERNAL_URL points at the SPA's standalone Vercel
  //    deployment (e.g. https://blog-dashboard-ebon.vercel.app). Users
  //    never see that URL - the proxy keeps them on gridar.app.
  //
  // Rewrites returned as a plain array run AFTER filesystem routes (so the
  // native /audit, /blog, app/[slug]... win) but BEFORE dynamic routes -
  // which is what lets /login reach the SPA instead of being swallowed by
  // the app/[slug] hosted-landing catch-all.
  // Every page is native to this app since the full SPA migration
  // (2026-06-11). The only proxying left is the Django backend, kept
  // same-origin so the httpOnly auth cookie lives on gridar.app and no
  // CORS preflight hits the hot path.
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${API_URL}/api/:path*` },
      { source: "/admin/:path*", destination: `${API_URL}/admin/:path*` },
      { source: "/accounts/:path*", destination: `${API_URL}/accounts/:path*` },
    ];
  },

  images: {
    remotePatterns: [
      { protocol: "https", hostname: new URL(API_URL).hostname },
      { protocol: "https", hostname: "images.unsplash.com" },
      { protocol: "https", hostname: "images.pexels.com" },
    ],
  },
};

export default nextConfig;
