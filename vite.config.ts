import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { VitePWA } from 'vite-plugin-pwa'
import path from 'path'

export default defineConfig({
  // Compile-time deploy marker (see src/main.tsx). Vercel injects the
  // commit SHA; local dev builds show "dev".
  define: {
    __BUILD_SHA__: JSON.stringify(
      (process.env.VERCEL_GIT_COMMIT_SHA || 'dev').slice(0, 7),
    ),
  },
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      // SELF-DESTROYING SERVICE WORKER.
      // The previous PWA setup cached aggressively and served stale JS bundles
      // to users after every backend/frontend change, requiring manual SW
      // unregister + Clear site data. We aren't shipping a real offline app
      // yet, so the PWA features aren't worth the cache-debug pain.
      // selfDestroying: true publishes a NEW service worker that, on first
      // run, unregisters itself AND clears every cache it owned. After every
      // existing user has been served this version once (~1 visit), no more
      // SW. Future deploys go live instantly with no cache layer in between.
      // ref: https://vite-pwa-org.netlify.app/guide/auto-update.html#self-destroying-service-worker
      selfDestroying: true,
      registerType: 'autoUpdate',
      includeAssets: ['favicon.ico', 'apple-touch-icon.png', 'favicon-16.png', 'favicon-32.png'],
      manifest: {
        name: 'Gridar',
        short_name: 'Gridar',
        description: 'SEO content on autopilot for Quebec PMEs',
        theme_color: '#10b981',
        background_color: '#0a0a0a',
        display: 'standalone',
        start_url: '/',
        icons: [
          {
            src: '/icons/icon-192.png',
            sizes: '192x192',
            type: 'image/png',
          },
          {
            src: '/icons/icon-512.png',
            sizes: '512x512',
            type: 'image/png',
          },
          {
            src: '/icons/icon-512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'any maskable',
          },
        ],
      },
    }),
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: (id) => {
          if (id.includes('node_modules')) {
            // Heavy single-purpose libraries get their own chunk so they're
            // cached independently and don't bloat the route bundles that
            // don't use them.
            if (id.includes('recharts') || id.includes('d3-')) {
              return 'recharts';
            }
            if (id.includes('@tanstack/react-query')) {
              return 'react-query';
            }
            if (id.includes('react-router')) {
              return 'react-router';
            }
            if (id.includes('lucide-react')) {
              return 'icons';
            }
            if (
              id.includes('@radix-ui') ||
              id.includes('class-variance-authority') ||
              id.includes('cmdk')
            ) {
              return 'ui';
            }
          }
        },
      },
    },
  },
})
