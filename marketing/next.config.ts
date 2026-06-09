import type { NextConfig } from "next";
import path from "node:path";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "https://api.gridar.app";

const nextConfig: NextConfig = {
  // Lock turbopack root to this folder. Without this Next picks up the
  // package-lock.json in the parent directory (Vite app) and warns.
  turbopack: {
    root: path.resolve(__dirname),
  },

  // Same-origin proxy for the Django backend. Client-side fetches in this
  // app use relative `/api/*` URLs so the browser sees them as same-origin
  // (gridar.app), which means:
  //   - the httpOnly access_token cookie set by the backend is stored on
  //     gridar.app and re-sent automatically on every /api/* call
  //   - no CORS preflight on the hot path
  //   - the AuthContext on the landing picks up a session that was opened
  //     on /sites/login (same-origin, same cookie jar)
  // Without this, the marketing page sat on gridar.app and called
  // api.gridar.app directly: the cookie set by /sites was scoped to
  // gridar.app and was never sent, so the navbar stayed in "Connexion"
  // state even when the user was authenticated.
  async rewrites() {
    const DASHBOARD_URL = process.env.DASHBOARD_INTERNAL_URL;
    const apiRewrites = [
      { source: "/api/:path*", destination: `${API_URL}/api/:path*` },
      { source: "/admin/:path*", destination: `${API_URL}/admin/:path*` },
      { source: "/accounts/:path*", destination: `${API_URL}/accounts/:path*` },
    ];
    if (!DASHBOARD_URL) {
      // Local dev: still proxy /api/* so the AuthContext call works against
      // a local Django (NEXT_PUBLIC_API_URL=http://localhost:8888).
      return apiRewrites;
    }
    return [
      ...apiRewrites,
      { source: "/dashboard", destination: `${DASHBOARD_URL}/dashboard` },
      { source: "/dashboard/:path*", destination: `${DASHBOARD_URL}/dashboard/:path*` },
      { source: "/login", destination: `${DASHBOARD_URL}/login` },
      { source: "/login/:path*", destination: `${DASHBOARD_URL}/login/:path*` },
      { source: "/onboarding/:path*", destination: `${DASHBOARD_URL}/onboarding/:path*` },
      { source: "/sites", destination: `${DASHBOARD_URL}/sites` },
      { source: "/sites/:path*", destination: `${DASHBOARD_URL}/sites/:path*` },
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
