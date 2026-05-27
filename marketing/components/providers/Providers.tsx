"use client";

import { QueryProvider } from "./QueryProvider";
import { AuthProvider } from "@/context/AuthContext";

/**
 * Top-level client-side wrapper. Mounts react-query + AuthProvider so any
 * descendant (Server Component or Client Component) can use them via hooks.
 * Wrapping a Server Component subtree is fine - "use client" only marks where
 * client-side React starts running, not where it's allowed to render.
 */
export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <QueryProvider>
      <AuthProvider>{children}</AuthProvider>
    </QueryProvider>
  );
}
