"use client";

import { Download } from "lucide-react";

/** Opens the browser print dialog, where "Save as PDF" is a destination.
 *  Kept as a tiny client island so the report page stays a Server Component,
 *  same pattern as CopyLinkButton. */
export function PrintReportButton() {
  return (
    <button
      type="button"
      onClick={() => window.print()}
      className="inline-flex items-center gap-1.5 rounded-md border border-zinc-700 bg-zinc-900/60 px-3 py-1.5 text-xs font-medium text-zinc-300 hover:text-zinc-100 hover:border-zinc-600 transition-colors"
    >
      <Download className="h-3.5 w-3.5" />
      Sauvegarder en PDF
    </button>
  );
}
