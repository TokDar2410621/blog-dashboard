"use client";

import { Component, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { AlertTriangle, RefreshCw } from "lucide-react";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
  isChunkLoadError: boolean;
}

/**
 * Detects errors thrown when lazy() can't fetch a JS chunk.
 *
 * Happens after a Vercel deploy: the user's tab has an old index.html
 * cached that references PostList-DKd-_akW.js, but the new deploy emitted
 * PostList-<NEW-HASH>.js so the old URL is now a 404. React Suspense
 * unwraps the error as "Failed to fetch dynamically imported module".
 *
 * Vite + Webpack agree on roughly the same set of error messages here.
 */
function isChunkLoadError(error: Error | null): boolean {
  if (!error) return false;
  const msg = error.message || String(error);
  return (
    msg.includes("Failed to fetch dynamically imported module") ||
    msg.includes("Loading chunk") ||
    msg.includes("Importing a module script failed") ||
    error.name === "ChunkLoadError"
  );
}

/** Session-scoped flag so we don't loop-reload if the new deploy itself
 *  ships a broken chunk. After one auto-reload attempt this turn, we fall
 *  back to showing the manual "Reessayer" button. */
const RELOAD_FLAG = "gridar-er-chunk-reload-fired";

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null, isChunkLoadError: false };
  }

  static getDerivedStateFromError(error: Error): State {
    return {
      hasError: true,
      error,
      isChunkLoadError: isChunkLoadError(error),
    };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error("[ErrorBoundary]", error, info.componentStack);

    // If it's a stale-bundle chunk-load error, auto-reload ONCE per
    // session. Reloading fetches a fresh index.html with the new chunk
    // hashes - usually invisible to the user (~1s flicker).
    if (isChunkLoadError(error)) {
      try {
        if (!sessionStorage.getItem(RELOAD_FLAG)) {
          sessionStorage.setItem(RELOAD_FLAG, "1");
          window.location.reload();
        }
      } catch {
        // sessionStorage disabled - skip auto-reload, user gets manual button
      }
    }
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;

      // Tailored message for chunk-load errors - more helpful than a
      // generic "unexpected error" since the user can act on it (reload).
      if (this.state.isChunkLoadError) {
        return (
          <div className="min-h-[400px] flex flex-col items-center justify-center gap-4 p-8">
            <RefreshCw className="h-12 w-12 text-primary animate-spin" />
            <h2 className="text-lg font-semibold">
              Nouvelle version disponible
            </h2>
            <p className="text-sm text-muted-foreground max-w-md text-center">
              On recharge la page pour recuperer la derniere version. Si rien
              ne se passe d&apos;ici 3 secondes, clique ci-dessous.
            </p>
            <Button
              variant="outline"
              onClick={() => window.location.reload()}
            >
              Recharger
            </Button>
          </div>
        );
      }

      return (
        <div className="min-h-[400px] flex flex-col items-center justify-center gap-4 p-8">
          <AlertTriangle className="h-12 w-12 text-destructive" />
          <h2 className="text-lg font-semibold">
            Une erreur est survenue
          </h2>
          <p className="text-sm text-muted-foreground max-w-md text-center">
            {this.state.error?.message || "Une erreur inattendue s'est produite."}
          </p>
          <Button
            variant="outline"
            onClick={() => this.setState({ hasError: false, error: null, isChunkLoadError: false })}
          >
            Réessayer
          </Button>
        </div>
      );
    }

    return this.props.children;
  }
}
