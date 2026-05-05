import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { VitePWA } from 'vite-plugin-pwa'
import path from 'path'

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['favicon.ico'],
      manifest: {
        name: 'Blog Dashboard',
        short_name: 'BlogDash',
        description: 'Multi-site blog management dashboard',
        theme_color: '#1a1a2e',
        background_color: '#1a1a2e',
        display: 'standalone',
        start_url: '/',
        icons: [
          {
            src: '/icons/icon-192.svg',
            sizes: '192x192',
            type: 'image/svg+xml',
          },
          {
            src: '/icons/icon-512.svg',
            sizes: '512x512',
            type: 'image/svg+xml',
          },
          {
            src: '/icons/icon-512.svg',
            sizes: '512x512',
            type: 'image/svg+xml',
            purpose: 'any maskable',
          },
        ],
      },
      workbox: {
        globPatterns: ['**/*.{js,css,html,ico,png,svg,woff2}'],
        // Do not cache authenticated API responses in the service worker
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
