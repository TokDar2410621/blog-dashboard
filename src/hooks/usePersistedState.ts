import { useState, useEffect, useRef } from "react";

/**
 * Drop-in replacement for useState that mirrors the value to sessionStorage
 * under `key`. On mount, restores any previously stored value. On every
 * setter call, the new value is written back.
 *
 * Why sessionStorage and not localStorage:
 * - Scoped to the current browser tab. Closing the tab clears it, so we
 *   don't accumulate stale state across sessions or leak between users
 *   on shared machines.
 * - Plenty of capacity (typically 5-10MB) for form values and result blobs.
 *
 * Conventions:
 * - Use a key prefixed by app + site + page, e.g.
 *   `gridar:site:6:topic-clusters:result`. This avoids collisions when the
 *   user switches sites or pages.
 * - The value MUST be JSON-serializable. Functions, Maps, Sets, etc. are
 *   silently lost on restore. Stick to primitives, arrays, plain objects.
 * - If the key changes (e.g. siteId switches), we re-restore from the new
 *   key's slot. The old slot lingers until session ends - that's fine,
 *   sessionStorage capacity is generous.
 */
export function usePersistedState<T>(
  key: string,
  initial: T,
): [T, React.Dispatch<React.SetStateAction<T>>] {
  // Track the key we last restored from, so a key change triggers re-restore.
  const lastKeyRef = useRef<string | null>(null);

  const [value, setValue] = useState<T>(() => {
    try {
      const stored = sessionStorage.getItem(key);
      if (stored !== null) {
        lastKeyRef.current = key;
        return JSON.parse(stored) as T;
      }
    } catch {
      // Corrupted JSON or sessionStorage disabled - fall through to initial.
    }
    lastKeyRef.current = key;
    return initial;
  });

  // If the key changes (e.g. user switched site mid-session), restore from
  // the new slot instead of writing the current value under the new key.
  useEffect(() => {
    if (lastKeyRef.current === key) return;
    lastKeyRef.current = key;
    try {
      const stored = sessionStorage.getItem(key);
      if (stored !== null) {
        setValue(JSON.parse(stored) as T);
      } else {
        setValue(initial);
      }
    } catch {
      setValue(initial);
    }
    // initial is intentionally omitted - we only react to key changes,
    // not to a new initial value (the persisted slot wins).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  // Persist on every value change.
  useEffect(() => {
    try {
      sessionStorage.setItem(key, JSON.stringify(value));
    } catch {
      // Quota exceeded or storage disabled - drop silently. The in-memory
      // state still works, the user just won't get cross-navigation persist.
    }
  }, [key, value]);

  return [value, setValue];
}

/**
 * Explicitly clear a persisted slot. Useful after a "reset form" action or
 * a successful submission where we don't want the old form values to come
 * back on the next visit.
 */
export function clearPersistedState(key: string) {
  try {
    sessionStorage.removeItem(key);
  } catch {
    // ignore
  }
}
