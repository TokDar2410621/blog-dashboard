import type { Metadata } from "next";
import { Suspense } from "react";
import { McpAuthorizePage } from "@/components/McpAuthorizePage";

export const metadata: Metadata = {
  title: "Autoriser un client MCP - Gridar",
  robots: { index: false, follow: false },
};

// Public route (no AuthGuard): the page handles its own needs-login phase
// with a /login?next= link, exactly like the SPA. McpAuthorizePage reads
// ?session_id & ?client_name & ?return_to via useSearchParams - Next.js
// requires a Suspense boundary around that for static prerendering.
export default function McpAuthorize() {
  return (
    <Suspense fallback={null}>
      <McpAuthorizePage />
    </Suspense>
  );
}
