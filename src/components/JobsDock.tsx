/**
 * Floating dock (bottom-right) that shows background jobs tracked by
 * <JobsProvider>. Collapsed = a small button with a spinner + count.
 * Expanded = a card listing each job with status icon, elapsed time,
 * action (view/dismiss).
 *
 * Hidden entirely when there's nothing to show (no running, no recent done).
 */
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useJobs, type Job } from "@/context/JobsContext";
import { Button } from "@/components/ui/button";
import {
  Loader2,
  CheckCircle2,
  XCircle,
  AlertCircle,
  X,
  ChevronDown,
  ChevronUp,
  ExternalLink,
} from "lucide-react";

function formatElapsed(startedAt: number, finishedAt?: number) {
  const ms = (finishedAt ?? Date.now()) - startedAt;
  const sec = Math.floor(ms / 1000);
  if (sec < 60) return `${sec}s`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m ${sec % 60}s`;
  const hr = Math.floor(min / 60);
  return `${hr}h ${min % 60}m`;
}

function statusIcon(status: Job["status"]) {
  switch (status) {
    case "running":
      return <Loader2 className="h-4 w-4 animate-spin text-primary" />;
    case "done":
      return <CheckCircle2 className="h-4 w-4 text-emerald-500" />;
    case "error":
      return <XCircle className="h-4 w-4 text-destructive" />;
    case "orphaned":
      return <AlertCircle className="h-4 w-4 text-amber-500" />;
  }
}

function statusLabel(status: Job["status"]) {
  switch (status) {
    case "running":
      return "En cours";
    case "done":
      return "Termine";
    case "error":
      return "Erreur";
    case "orphaned":
      return "Perdu (refresh)";
  }
}

export function JobsDock() {
  const { jobs, dismiss, clearFinished, runningCount } = useJobs();
  const [expanded, setExpanded] = useState(false);
  const navigate = useNavigate();

  // Sort: running first, then most recent.
  const sorted = useMemo(
    () =>
      [...jobs].sort((a, b) => {
        if (a.status === "running" && b.status !== "running") return -1;
        if (a.status !== "running" && b.status === "running") return 1;
        return b.startedAt - a.startedAt;
      }),
    [jobs],
  );

  if (sorted.length === 0) return null;

  const handleClick = (job: Job) => {
    if (job.status === "running" || !job.targetUrl) return;
    navigate(job.targetUrl);
  };

  return (
    <div className="fixed bottom-4 right-4 z-50 max-w-sm">
      {!expanded && (
        <Button
          type="button"
          variant="default"
          className="shadow-lg flex items-center gap-2"
          onClick={() => setExpanded(true)}
        >
          {runningCount > 0 ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <CheckCircle2 className="h-4 w-4" />
          )}
          <span className="text-sm">
            {runningCount > 0
              ? `${runningCount} tache${runningCount > 1 ? "s" : ""} en cours`
              : `${sorted.length} tache${sorted.length > 1 ? "s" : ""}`}
          </span>
          <ChevronUp className="h-3.5 w-3.5 opacity-70" />
        </Button>
      )}

      {expanded && (
        <div className="bg-card border rounded-lg shadow-xl w-80 max-w-[calc(100vw-2rem)] max-h-[60vh] flex flex-col">
          <div className="flex items-center justify-between px-3 py-2 border-b">
            <div className="text-sm font-semibold">Taches en cours</div>
            <div className="flex items-center gap-1">
              {sorted.some((j) => j.status !== "running") && (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  className="text-xs h-7"
                  onClick={clearFinished}
                  title="Vider les taches terminees"
                >
                  Vider
                </Button>
              )}
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className="h-10 w-10 -my-1.5"
                onClick={() => setExpanded(false)}
                title="Reduire"
              >
                <ChevronDown className="h-4 w-4" />
              </Button>
            </div>
          </div>

          <div className="overflow-y-auto divide-y">
            {sorted.map((job) => (
              <div
                key={job.id}
                className={`p-3 flex items-start gap-2 ${
                  job.status === "done" && job.targetUrl
                    ? "hover:bg-muted/40 cursor-pointer"
                    : ""
                }`}
                onClick={() => handleClick(job)}
              >
                <div className="mt-0.5 shrink-0">{statusIcon(job.status)}</div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium truncate">{job.label}</div>
                  <div className="text-xs text-muted-foreground flex items-center gap-2 mt-0.5">
                    <span className="font-mono uppercase text-[10px]">
                      {job.kind}
                    </span>
                    <span>{statusLabel(job.status)}</span>
                    <span>{formatElapsed(job.startedAt, job.finishedAt)}</span>
                  </div>
                  {job.error && (
                    <div className="text-xs text-destructive mt-1 line-clamp-2">
                      {job.error}
                    </div>
                  )}
                  {job.status === "done" && job.targetUrl && (
                    <div className="flex items-center gap-1 text-xs text-primary mt-1">
                      <ExternalLink className="h-3 w-3" />
                      Voir le resultat
                    </div>
                  )}
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="h-10 w-10 -my-2 -mr-3 shrink-0"
                  onClick={(e) => {
                    e.stopPropagation();
                    dismiss(job.id);
                  }}
                  title="Retirer du dock"
                >
                  <X className="h-3.5 w-3.5" />
                </Button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
