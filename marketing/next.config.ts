import type { NextConfig } from "next";
import path from "node:path";

const API_URL = process.env.NEXT_PUBLIC_API_URL || "https://api.gridar.app";

const nextConfig: NextConfig = {
  // Lock turbopack root to this folder. Without this Next picks up the
  // package-lock.json in the parent directory (Vite app) and warns.
  turbopack: {
    root: path.resolve(__dirname),
  },

  // Phase 6 will set these to the actual dashboard URL on Vercel so
  // /dashboard, /login, /onboarding, /sites paths transparently proxy
  // to the Vite SPA without a domain change.
  async rewrites() {
    const DASHBOARD_URL = process.env.DASHBOARD_INTERNAL_URL;
    if (!DASHBOARD_URL) {
      // Local dev: no rewrites, /dashboard/* returns a 404 from Next.
      return [];
    }
    return [
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
