import type { NextConfig } from "next";
import path from "node:path";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "https://api.gridar.app";

const nextConfig: NextConfig = {
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
  async rewrites() {
    const rawDashboardUrl = process.env.DASHBOARD_INTERNAL_URL;
    const apiRewrites = [
      { source: "/api/:path*", destination: `${API_URL}/api/:path*` },
      { source: "/admin/:path*", destination: `${API_URL}/admin/:path*` },
      { source: "/accounts/:path*", destination: `${API_URL}/accounts/:path*` },
    ];
    if (!rawDashboardUrl) {
      // The whole app surface (login, dashboard, OAuth callbacks, the SPA
      // bundles) hangs on this single env var: a silent fallback in
      // production would 404 every one of those routes at once. Fail the
      // build instead so the misconfiguration is caught at deploy time.
      if (process.env.VERCEL_ENV === "production") {
        throw new Error(
          "DASHBOARD_INTERNAL_URL is required in production: set it to the " +
            "full https origin of the Vite SPA deployment (e.g. " +
            "https://blog-dashboard-ebon.vercel.app), no trailing slash.",
        );
      }
      // Local dev: still proxy /api/* so the AuthContext call works against
      // a local Django (NEXT_PUBLIC_API_URL=http://localhost:8888).
      return apiRewrites;
    }
    // Normalize the two classic value mistakes: a trailing slash produces
    // double-slash destinations; a missing protocol makes next build throw
    // a cryptic invalid-rewrite error. Fail fast with a clear message.
    const DASHBOARD_URL = rawDashboardUrl.replace(/\/+$/, "");
    if (!/^https?:\/\//.test(DASHBOARD_URL)) {
      throw new Error(
        `DASHBOARD_INTERNAL_URL must start with http(s)://, got: ${rawDashboardUrl}`,
      );
    }
    // Every SPA surface. Page routes mirror src/App.tsx; asset routes are
    // what the SPA's index.html references (hashed bundles, PWA icons,
    // manifest, self-destroying service worker).
    const SPA_PATHS = [
      "/login",
      "/sites",
      "/compare",
      "/billing",
      "/reset-password",
      "/account/:path*",
      "/auth/:path*",
      "/gsc/:path*",
      "/oauth/:path*",
      "/onboarding/:path*",
      "/dashboard",
      "/dashboard/:path*",
      "/assets/:path*",
      "/icons/:path*",
      "/manifest.webmanifest",
      "/sw.js",
      "/registerSW.js",
    ];
    return [
      ...apiRewrites,
      ...SPA_PATHS.map((p) => ({
        source: p,
        destination: `${DASHBOARD_URL}${p}`,
      })),
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
