"""Honest rank-display helper.

gridar.app tracks brand-new sites that rank on ultra-niche keywords where a
single Serper call can report #1 one minute and "hors classement" the next
(truncated SERPs + real Google volatility). Surfacing the latest raw snapshot as
if it were a stable fact made the dashboard look like it was lying.

`keyword_display_rank` smooths this: a keyword only counts as "classe" when it
shows up in the MAJORITY of the last N snapshots, and every reading carries the
timestamp of its last check so the UI can say "verifie il y a 2 jours" instead
of implying a live truth that isn't there.

Read-only. Never writes a snapshot (that stays in rank_snapshot.py). Tolerates a
keyword with zero snapshots (returns the all-None/false shape).
"""
from __future__ import annotations

from statistics import median

from .models import SerpRank

# Default number of recent snapshots the stability decision looks at. Exposed so
# callers that bulk-fetch snapshots per keyword cap their slice at the same size.
DEFAULT_WINDOW = 5

# Shape returned when a keyword has no snapshot at all. Kept as a factory so
# callers never share/mutate one dict.
def _empty() -> dict:
    return {
        'stable_position': None,
        'is_stable': False,
        'found_ratio': 0.0,
        'last_checked': None,
        'best_seen': None,
        'samples': 0,
    }


def keyword_display_rank(tracked, window=DEFAULT_WINDOW, snapshots=None) -> dict:
    """Return a stability-aware view of a TrackedKeyword's SERP position.

    Looks at the `window` most recent SerpRank snapshots and decides whether the
    keyword is *consistently* ranked, instead of trusting the single latest
    reading (which is noisy on volatile niche SERPs).

    Args:
        tracked: the TrackedKeyword instance (a pk also works).
        window: how many recent snapshots to consider (default DEFAULT_WINDOW).
        snapshots: optional pre-fetched, newest-first iterable of that keyword's
            SerpRank rows. Lets list views pass a slice of one bulk query and
            avoid an N+1. When None, the function queries the DB itself.

    Returns a dict:
        stable_position: median of the ranked positions IF is_stable, else None.
        is_stable:       True when the keyword is ranked in >= 50% of samples.
        found_ratio:     ranked_samples / total_samples (0.0 with no snapshot).
        last_checked:    ISO timestamp of the most recent snapshot, or None.
        best_seen:       best (smallest) position seen in the window, or None.
        samples:         number of snapshots actually considered.
    """
    if snapshots is None:
        snaps = list(
            SerpRank.objects.filter(tracked=tracked)
            .order_by('-recorded_at')[:window]
        )
    else:
        # Caller supplied a newest-first list; honor the same window cap.
        snaps = list(snapshots)[:window]

    samples = len(snaps)
    if samples == 0:
        return _empty()

    found = [s.position for s in snaps if s.position is not None]
    found_ratio = len(found) / samples
    is_stable = found_ratio >= 0.5
    stable_position = int(round(median(found))) if (is_stable and found) else None
    best_seen = min(found) if found else None
    # snaps is newest-first, so snaps[0] is the most recent snapshot.
    last_checked = snaps[0].recorded_at.isoformat()

    return {
        'stable_position': stable_position,
        'is_stable': is_stable,
        'found_ratio': round(found_ratio, 2),
        'last_checked': last_checked,
        'best_seen': best_seen,
        'samples': samples,
    }
