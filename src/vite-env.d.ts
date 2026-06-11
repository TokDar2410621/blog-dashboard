/// <reference types="vite/client" />

// Injected at build time via vite.config.ts `define`. Short git SHA on
// Vercel (VERCEL_GIT_COMMIT_SHA), "dev" locally.
declare const __BUILD_SHA__: string;
