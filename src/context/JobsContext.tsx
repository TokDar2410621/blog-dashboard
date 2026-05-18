/**
 * Global jobs registry: tracks long-running background tasks (article
 * generation, cluster analysis, bulk audit, etc.) so the UI doesn't lose
 * them when the user navigates away from the page that started them.
 *
 * Architecture:
 * - Provider sits at the app root, ABOVE the router, so jobs survive every
 *   route change. The provider state lives in React, so the in-flight
 *   Promise reference stays valid across navigations (component unmount
 *   does NOT abort the fetch).
 * - jobs.start(opts) returns a job id immediately. The caller fires its
 *   async work via opts.run(). The provider awaits it and updates status.
 * - On full page refresh, the Promise dies. Persisted 'running' jobs are
 *   downgraded to 'orphaned' on next mount so the user knows the request
 *   was firing but we lost the in-flight handle (the article may still
 *   exist server-side; check the list).
 * - Persisted to sessionStorage so a page refresh keeps the recent log
 *   visible, but it auto-clears at tab close.
 *
 * Public API (via useJobs() hook):
 *   const jobs = useJobs();
 *   const id = jobs.start({
 *     kind: 'article-generation',
 *     label: 'SEO local pour menuisiers',
 *     siteId: '6',
 *     targetUrl: '/dashboard/6/articles',  // navigated to on click when done
 *     run: () => fetch(...).then(r => r.json()),
 *   });
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

export type JobStatus = "running" | "done" | "error" | "orphaned";

export type Job = {
  id: string;
  /** Tag used to group/icon jobs in the UI. */
  kind: string;
  /** Human-readable summary shown in the dock. */
  label: string;
  siteId?: string;
  status: JobStatus;
  /** Result returned by the run() promise. Available when status === 'done'. */
  result?: unknown;
  /** Stringified error message. Available when status === 'error'. */
  error?: string;
  startedAt: number;
  finishedAt?: number;
  /** Optional route to navigate to when the user clicks the job in the dock. */
  targetUrl?: string;
};

type StartOpts = {
  kind: string;
  label: string;
  siteId?: string;
  targetUrl?: string;
  run: () => Promise<unknown>;
};

type JobsContextValue = {
  jobs: Job[];
  start: (opts: StartOpts) => string;
  dismiss: (id: string) => void;
  clearFinished: () => void;
  /** Live count of jobs currently in the 'running' state. */
  runningCount: number;
};

const JobsContext = createContext<JobsContextValue | null>(null);

const STORAGE_KEY = "gridar:jobs";
/** Auto-dismiss done jobs after this many ms so the dock doesn't grow forever. */
const DONE_TTL_MS = 5 * 60 * 1000; // 5 min

/** Strip non-serializable fields before writing to sessionStorage and replace
 *  any 'running' status with 'orphaned' on restore so we don't pretend the
 *  Promise is still alive after a page refresh. */
function persist(jobs: Job[]) {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(jobs));
  } catch {
    /* quota or disabled, ignore */
  }
}

function restore(): Job[] {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw) as Job[];
    if (!Array.isArray(parsed)) return [];
    return parsed.map((j) =>
      j.status === "running"
        ? { ...j, status: "orphaned" as JobStatus, finishedAt: j.finishedAt ?? Date.now() }
        : j,
    );
  } catch {
    return [];
  }
}

export function JobsProvider({ children }: { children: ReactNode }) {
  const [jobs, setJobs] = useState<Job[]>(() => restore());
  // Stable ref to setJobs so the start() callback closure doesn't go stale.
  const setJobsRef = useRef(setJobs);
  useEffect(() => {
    setJobsRef.current = setJobs;
  }, []);

  // Mirror to sessionStorage whenever jobs changes.
  useEffect(() => {
    persist(jobs);
  }, [jobs]);

  // Periodic GC: drop 'done' jobs older than DONE_TTL_MS so the dock self-cleans.
  useEffect(() => {
    const i = setInterval(() => {
      const now = Date.now();
      setJobs((prev) =>
        prev.filter((j) => {
          if (j.status === "done" && j.finishedAt && now - j.finishedAt > DONE_TTL_MS) {
            return false;
          }
          return true;
        }),
      );
    }, 30_000);
    return () => clearInterval(i);
  }, []);

  const start = useCallback((opts: StartOpts) => {
    const id =
      typeof crypto !== "undefined" && "randomUUID" in crypto
        ? crypto.randomUUID()
        : `job-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    const job: Job = {
      id,
      kind: opts.kind,
      label: opts.label,
      siteId: opts.siteId,
      targetUrl: opts.targetUrl,
      status: "running",
      startedAt: Date.now(),
    };
    setJobsRef.current((prev) => [job, ...prev]);

    opts
      .run()
      .then((result) => {
        setJobsRef.current((prev) =>
          prev.map((j) =>
            j.id === id
              ? { ...j, status: "done", result, finishedAt: Date.now() }
              : j,
          ),
        );
      })
      .catch((err: unknown) => {
        const msg = err instanceof Error ? err.message : String(err);
        setJobsRef.current((prev) =>
          prev.map((j) =>
            j.id === id
              ? { ...j, status: "error", error: msg, finishedAt: Date.now() }
              : j,
          ),
        );
      });

    return id;
  }, []);

  const dismiss = useCallback((id: string) => {
    setJobsRef.current((prev) => prev.filter((j) => j.id !== id));
  }, []);

  const clearFinished = useCallback(() => {
    setJobsRef.current((prev) => prev.filter((j) => j.status === "running"));
  }, []);

  const value = useMemo<JobsContextValue>(
    () => ({
      jobs,
      start,
      dismiss,
      clearFinished,
      runningCount: jobs.filter((j) => j.status === "running").length,
    }),
    [jobs, start, dismiss, clearFinished],
  );

  return <JobsContext.Provider value={value}>{children}</JobsContext.Provider>;
}

export function useJobs(): JobsContextValue {
  const ctx = useContext(JobsContext);
  if (!ctx) {
    throw new Error("useJobs must be used within <JobsProvider>");
  }
  return ctx;
}
