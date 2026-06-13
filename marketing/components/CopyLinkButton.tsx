"use client";

import { useState } from "react";
import { Check, Link2 } from "lucide-react";

/** Copies the current page URL to the clipboard - the share mechanism for the
 *  public report page. Kept as a tiny client island so the page stays a Server
 *  Component (for OG tags + ISR). */
export function CopyLinkButton() {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard blocked (insecure context / permissions) - no-op.
    }
  };

  return (
    <button
      type="button"
      onClick={copy}
      className="inline-flex items-center gap-1.5 rounded-md border border-zinc-700 bg-zinc-900/60 px-3 py-1.5 text-xs font-medium text-zinc-300 hover:text-zinc-100 hover:border-zinc-600 transition-colors"
    >
      {copied ? (
        <Check className="h-3.5 w-3.5 text-emerald-400" />
      ) : (
        <Link2 className="h-3.5 w-3.5" />
      )}
      {copied ? "Lien copie" : "Copier le lien"}
    </button>
  );
}
