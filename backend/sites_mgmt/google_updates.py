"""Date a traffic drop against Google's confirmed update history.

Ported from claude-seo v2.2.4 `scripts/seo_updates.py` (+ `data/google-updates.json`).
Copyright (c) 2025 Daniel Agrici (AgriciDaniel). MIT.
https://github.com/AgriciDaniel/claude-seo

Upstream is a CLI that prints the changelog newest first. Gridar asks the
question backwards: traffic fell on a given day, which confirmed update could
account for it. So the argparse layer is replaced by date arithmetic over
rollout windows, because a core update that starts May 21 and finishes June 2
explains a drop on any of those days. The upstream JSON has no structured
rollout length, so it is read out of the `notes` prose and falls back to a
per-kind default when absent, which keeps the data file re-syncable with
upstream as-is. Labels and verdicts come back in French since Gridar's
interface is French Quebec, while the dict keys stay English like the rest of
the app. The copied data file is verbatim except for one em dash in a `notes`
string, turned into a comma so no foreign typography reaches the UI.
"""
from __future__ import annotations

import json
import re
from collections.abc import Iterable
from datetime import date, datetime, timedelta
from pathlib import Path

__all__ = [
    'GoogleUpdatesError',
    'KIND_LABELS_FR',
    'STALE_AFTER_DAYS',
    'data_freshness',
    'explain_traffic_drop',
    'traffic_drop_report',
    'updates_in_window',
]

_DATA_FILE = Path(__file__).resolve().parent / 'data' / 'google_updates.json'

# Google ships a ranking update roughly every six to ten weeks. Past this many
# days without a re-verification, the odds that something confirmed is missing
# from the file are better than even, so the UI has to say so.
STALE_AFTER_DAYS = 60

# A reported drop date is never exact: GSC lands data two to three days late and
# the operator reads it off a chart. Grace lets an update announced just after
# the reported date still count; the tail lets a drop just after a rollout ends
# still count as "during".
_DEFAULT_GRACE_DAYS = 2
_ROLLOUT_TAIL_DAYS = 3

KIND_LABELS_FR = {
    'core': 'mise à jour principale',
    'core+spam': 'mise à jour principale et anti-spam',
    'spam': 'mise à jour anti-spam',
    'policy': 'changement de politique',
    'qrg': 'consignes des évaluateurs qualité',
    'product': 'changement produit',
    'schema': 'changement de données structurées',
    'cwv': 'changement Core Web Vitals',
    'discover': 'mise à jour Discover',
}

# Kinds that reorder results by themselves. `policy` is deliberately out: the
# recorded date is the announcement, and enforcement can start months later
# (see the back-button-hijacking entry, announced April, enforced June).
_RANKING_KINDS = frozenset({'core', 'core+spam', 'spam', 'discover'})

# A Discover update cannot explain a web-search drop, and the reverse holds too.
_SURFACE_BY_KIND = {'discover': 'discover'}
_DEFAULT_SURFACE = 'web'

# Used only when the notes say nothing about duration. Core updates have run 7
# to 24 days since 2024; spam updates are much tighter (2 days in June 2026).
# Anything else is a single-day announcement until proven otherwise.
_DEFAULT_ROLLOUT_DAYS = {
    'core': 14,
    'core+spam': 14,
    'spam': 5,
    'discover': 14,
}

# Upstream writes rollout length four different ways in free prose. Day forms
# are tried first: "~11d21h rollout" would otherwise match the hour form on its
# "21h" and report a three-week rollout.
_DAY_PATTERNS = (
    re.compile(r'(\d+)[\s-]*day\s+rollout', re.IGNORECASE),
    re.compile(r'rollout\s*\(~?\s*(\d+)\s*days?\)', re.IGNORECASE),
    re.compile(r'~?\s*(\d+)\s*d\s*(?:\d+\s*h)?\s*rollout', re.IGNORECASE),
)
_SUBDAY_PATTERN = re.compile(r'\d+\s*h(?:\s*\d+\s*m)?\s+rollout', re.IGNORECASE)

# Guard against a typo in a future sync turning into a year-long window.
_MAX_ROLLOUT_DAYS = 90

_MONTHS_FR = (
    'janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août',
    'septembre', 'octobre', 'novembre', 'décembre',
)

# What to tell the reader about kinds that do not reorder results. Left out of
# the answer entirely they would hide real causes: the May 2026 FAQ retirement
# cost clicks without touching a single ranking.
_NON_RANKING_HINTS = {
    'schema': "Elle change l'affichage dans la SERP, donc le CTR, sans toucher le classement.",
    'policy': "L'annonce précède souvent l'application, vérifie la date d'entrée en vigueur dans les notes.",
    'qrg': "Les consignes des évaluateurs ne déplacent rien le jour même.",
    'cwv': "Changement de métrique, l'effet est graduel et jamais brutal.",
    'product': "Changement produit, l'effet dépend de la surface touchée.",
}

_CONFIDENCE_LABELS_FR = {'high': 'élevée', 'medium': 'moyenne', 'low': 'faible'}
_CONFIDENCE_RANK = {'high': 0, 'medium': 1, 'low': 2}

_CACHE = None


class GoogleUpdatesError(RuntimeError):
    """Raised when the bundled changelog cannot be read or parsed."""


def _load() -> dict:
    """Read the changelog once per process.

    Two threads can race into the parse on a cold worker. The assignment is
    atomic and the result identical, so the loser wastes one parse and nothing
    else; a lock here would be more machinery than the problem deserves.
    """
    global _CACHE
    if _CACHE is None:
        try:
            with _DATA_FILE.open(encoding='utf-8') as fh:
                _CACHE = json.load(fh)
        except (OSError, ValueError) as exc:
            raise GoogleUpdatesError(f'Cannot read {_DATA_FILE.name}: {exc}') from exc
    return _CACHE


def _as_date(value, field: str = 'date') -> date:
    """Accept a date, a datetime or an ISO string.

    The API layer receives query strings, so refusing anything but `date` would
    push the same three lines of parsing into every caller.
    """
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value.strip()[:10])
        except ValueError as exc:
            raise ValueError(f'{field} is not an ISO date: {value!r}') from exc
    raise TypeError(f'{field} must be a date or an ISO string, got {type(value).__name__}')


def _fmt_fr(d: date) -> str:
    """French long date, Quebec style: 1er juin 2026, 21 mai 2026."""
    day = '1er' if d.day == 1 else str(d.day)
    return f'{day} {_MONTHS_FR[d.month - 1]} {d.year}'


def _days_fr(n: int) -> str:
    return '1 jour' if n == 1 else f'{n} jours'


def _rollout_days(entry: dict) -> tuple[int, bool]:
    """Return (days, estimated) for one entry.

    Upstream records rollout length in the `notes` sentence only. Parsing it
    back out beats adding a field, because the file then stays a drop-in copy
    of whatever claude-seo ships next.
    """
    notes = entry.get('notes') or ''
    for pattern in _DAY_PATTERNS:
        match = pattern.search(notes)
        if match:
            return min(int(match.group(1)), _MAX_ROLLOUT_DAYS), False
    if _SUBDAY_PATTERN.search(notes):
        return 0, False
    return _DEFAULT_ROLLOUT_DAYS.get(entry.get('kind'), 0), True


def _enrich(entry: dict) -> dict:
    """Turn one raw changelog entry into the shape callers consume."""
    start = _as_date(entry['date'], 'update date')
    days, estimated = _rollout_days(entry)
    kind = entry.get('kind') or 'unknown'
    return {
        'date': start.isoformat(),
        'name': entry.get('name', ''),
        'kind': kind,
        'kind_label': KIND_LABELS_FR.get(kind, kind),
        'source': entry.get('source', ''),
        'notes': entry.get('notes', ''),
        'rollout_days': days,
        'rollout_end': (start + timedelta(days=days)).isoformat(),
        'rollout_days_estimated': estimated,
        'affects_rankings': kind in _RANKING_KINDS,
        'surface': _SURFACE_BY_KIND.get(kind, _DEFAULT_SURFACE),
    }


def _all_enriched() -> list[dict]:
    return [_enrich(e) for e in _load().get('updates', [])]


def updates_in_window(start, end, *, kinds: Iterable[str] | None = None) -> list[dict]:
    """Confirmed Google updates whose rollout overlaps [start, end], newest first.

    Overlap, not announcement date: the November 2024 core update ran 24 days,
    so a one-day window in early December still has to see it.

    Args:
        start: window start, inclusive (date, datetime or ISO string).
        end: window end, inclusive.
        kinds: optional filter over the raw `kind` values (core, spam, policy,
            qrg, product, schema, cwv, discover, core+spam).

    Returns a list of dicts: date, name, kind, kind_label (French), source,
    notes, rollout_days, rollout_end, rollout_days_estimated, affects_rankings,
    surface. Raises ValueError when start is after end.
    """
    start_d = _as_date(start, 'start')
    end_d = _as_date(end, 'end')
    if start_d > end_d:
        raise ValueError(f'start {start_d.isoformat()} is after end {end_d.isoformat()}')

    wanted = set(kinds) if kinds else None
    hits = []
    for item in _all_enriched():
        if wanted is not None and item['kind'] not in wanted:
            continue
        if _as_date(item['date']) <= end_d and _as_date(item['rollout_end']) >= start_d:
            hits.append(item)
    hits.sort(key=lambda u: (u['date'], u['name']), reverse=True)
    return hits


def _distance_days(item: dict, drop: date) -> int:
    """Days between the drop and the rollout window. Zero while inside it."""
    start = _as_date(item['date'])
    end = _as_date(item['rollout_end'])
    if drop < start:
        return (start - drop).days
    if drop > end:
        return (drop - end).days
    return 0


def _confidence(item: dict, drop: date, surface: str, grace_days: int) -> tuple[str, bool]:
    """Return (confidence, during_rollout).

    "During" is stretched by a few days on both ends: a drop reported the day
    before an announcement or three days after a rollout closes is the same
    event, seen through late GSC data.
    """
    start = _as_date(item['date'])
    end = _as_date(item['rollout_end'])
    during = (start - timedelta(days=grace_days)) <= drop <= (end + timedelta(days=_ROLLOUT_TAIL_DAYS))

    if item['surface'] != surface:
        return 'low', during
    if item['affects_rankings']:
        return ('high' if during else 'medium'), during
    if item['kind'] == 'policy':
        return ('medium' if during else 'low'), during
    return 'low', during


def _verdict(item: dict, drop: date, during: bool, surface: str) -> str:
    """One French sentence a non-technical reader can act on.

    Built name-first with a colon rather than as a flowing sentence: the kind
    labels are a mix of masculine and feminine, and any verb phrase would agree
    with the wrong one half the time.
    """
    start = _as_date(item['date'])
    end = _as_date(item['rollout_end'])
    rollout = item['rollout_days']
    head = f"« {item['name']} » ({item['kind_label']})"
    period = (
        f'déploiement du {_fmt_fr(start)} au {_fmt_fr(end)}'
        if rollout else f'annonce le {_fmt_fr(start)}'
    )

    if drop < start:
        line = f'{head} : {period}, soit {_days_fr((start - drop).days)} après ta date de chute.'
    elif during and rollout:
        line = f'{head} : {period}, ta chute tombe pendant.'
    elif drop == end:
        line = f'{head} : {period}, le jour même de ta chute.'
    else:
        line = f'{head} : {period}, soit {_days_fr((drop - end).days)} avant ta chute.'

    if item['rollout_days_estimated'] and rollout:
        line += " Durée de déploiement estimée, Google ne l'a pas publiée."
    if item['surface'] != surface:
        line += (
            ' Elle ne touche que Discover, pas la recherche web.'
            if item['surface'] == 'discover'
            else ' Elle touche la recherche web, pas Discover.'
        )
    elif not item['affects_rankings']:
        hint = _NON_RANKING_HINTS.get(item['kind'])
        if hint:
            line += f' {hint}'
    return line


def explain_traffic_drop(
    drop_date,
    window_days: int = 14,
    *,
    surface: str = 'web',
    grace_days: int = _DEFAULT_GRACE_DAYS,
) -> list[dict]:
    """Confirmed Google updates that could explain a drop dated `drop_date`.

    Candidates are every update whose rollout overlaps
    [drop_date - window_days, drop_date + grace_days], ranked best explanation
    first. Nothing is filtered out on kind: a structured-data retirement costs
    clicks without moving a single ranking, and the reader deserves to see it
    flagged as such rather than hidden.

    Args:
        drop_date: the day traffic fell (date, datetime or ISO string).
        window_days: how far back to look. 14 covers a full core rollout.
        surface: 'web' or 'discover'. A Discover update cannot explain a web
            drop, so a mismatch is downgraded to low confidence, never dropped.
        grace_days: tolerance for a drop reported slightly before the update.

    Returns a list of dicts, each one an `updates_in_window` entry plus:
        days_from_start: drop_date minus the update start, negative if the
            update was announced after the drop.
        distance_days: days between the drop and the rollout window, 0 inside.
        during_rollout: the drop falls inside the rollout, tails included.
        confidence: 'high' | 'medium' | 'low' (stable key for the UI).
        confidence_label: French label for display.
        verdict: one French sentence explaining the link.
    Empty list means no confirmed update lines up, which is itself an answer.
    """
    drop = _as_date(drop_date, 'drop_date')
    if window_days < 0:
        raise ValueError('window_days must be positive')
    if grace_days < 0:
        raise ValueError('grace_days must be positive')

    candidates = updates_in_window(
        drop - timedelta(days=window_days), drop + timedelta(days=grace_days),
    )

    out = []
    for item in candidates:
        confidence, during = _confidence(item, drop, surface, grace_days)
        enriched = dict(item)
        enriched.update({
            'days_from_start': (drop - _as_date(item['date'])).days,
            'distance_days': _distance_days(item, drop),
            'during_rollout': during,
            'confidence': confidence,
            'confidence_label': _CONFIDENCE_LABELS_FR[confidence],
            'verdict': _verdict(item, drop, during, surface),
        })
        out.append(enriched)

    out.sort(key=lambda u: (_CONFIDENCE_RANK[u['confidence']], u['distance_days'], u['date']))
    return out


def data_freshness(today=None) -> dict:
    """How old the bundled changelog is, so the UI can admit it.

    The file carries a `last_verified` date and nothing auto-updates it. Any
    screen that answers "was it a Google update" has to show this next to the
    answer, otherwise silence about a recent update reads as "no update".

    Args:
        today: reference date, defaults to the system date. Injectable so tests
            and reports stay deterministic.

    Returns: last_verified, age_days, is_stale, stale_after_days,
    source_of_truth, updates_count, latest_update_date, message (French).
    """
    data = _load()
    now = _as_date(today, 'today') if today is not None else date.today()
    verified_raw = data.get('last_verified')
    verified = _as_date(verified_raw, 'last_verified') if verified_raw else None

    # A reference date before last_verified means a clock problem, not negative
    # age; clamping keeps the message readable instead of saying "il y a -3 jours".
    age = max(0, (now - verified).days) if verified else None
    is_stale = bool(age is not None and age > STALE_AFTER_DAYS)

    dates = sorted(u['date'] for u in data.get('updates', []))
    latest = dates[-1] if dates else None

    if verified is None:
        message = "Date de vérification absente du fichier, considère la liste comme non fiable."
    elif is_stale:
        message = (
            f'Liste vérifiée le {_fmt_fr(verified)}, il y a {_days_fr(age)}. '
            f"Une mise à jour annoncée depuis n'y figure pas, confirme sur le tableau de bord Google."
        )
    else:
        message = f'Liste vérifiée le {_fmt_fr(verified)}, il y a {_days_fr(age)}.'

    return {
        'last_verified': verified.isoformat() if verified else None,
        'age_days': age,
        'is_stale': is_stale,
        'stale_after_days': STALE_AFTER_DAYS,
        'source_of_truth': data.get('source_of_truth', ''),
        'updates_count': len(data.get('updates', [])),
        'latest_update_date': latest,
        'message': message,
    }


def traffic_drop_report(
    drop_date,
    window_days: int = 14,
    *,
    surface: str = 'web',
    today=None,
) -> dict:
    """`explain_traffic_drop` wrapped with the freshness caveat attached.

    An empty candidate list means two very different things depending on
    whether the changelog even reaches the drop date. Splitting them here keeps
    every caller from having to remember the difference.

    Returns: drop_date, window_days, surface, candidates, freshness,
    data_covers_drop_date, verdict (French summary).
    """
    drop = _as_date(drop_date, 'drop_date')
    candidates = explain_traffic_drop(drop, window_days, surface=surface)
    freshness = data_freshness(today=today)
    verified = freshness['last_verified']
    covers = bool(verified and drop <= _as_date(verified))

    if candidates:
        verdict = candidates[0]['verdict']
        others = len(candidates) - 1
        if others:
            verdict += f' {others} autre changement confirmé dans la fenêtre.' if others == 1 \
                else f' {others} autres changements confirmés dans la fenêtre.'
        if not covers:
            verdict += f" {freshness['message']}"
    elif covers:
        verdict = (
            f'Aucune mise à jour Google confirmée dans les {_days_fr(window_days)} '
            f'avant le {_fmt_fr(drop)}. Cherche ailleurs : technique, saisonnalité, '
            f'perte de liens, refonte de contenu.'
        )
    elif verified:
        verdict = (
            f'Impossible de conclure : la liste vérifiée des mises à jour '
            f"s'arrête au {_fmt_fr(_as_date(verified))} et ta chute est datée du "
            f'{_fmt_fr(drop)}. Vérifie {freshness["source_of_truth"]}.'
        )
    else:
        verdict = (
            'Impossible de conclure : la date de vérification de la liste des '
            'mises à jour est inconnue.'
        )

    return {
        'drop_date': drop.isoformat(),
        'window_days': window_days,
        'surface': surface,
        'candidates': candidates,
        'freshness': freshness,
        'data_covers_drop_date': covers,
        'verdict': verdict,
    }
