"""Quality gates for generated pages, doorway-page thresholds included.

Ported from claude-seo v2.2.4 `skills/seo/references/quality-gates.md` and
`skills/seo-programmatic/SKILL.md`.
Copyright (c) 2025 Daniel Agrici (AgriciDaniel). MIT.
https://github.com/AgriciDaniel/claude-seo

The thresholds are the source's; the uniqueness measure is ours. The source
defines unique content as "words unique to this page over total words" without
saying how to compute it, so this uses word shingles: a page whose sentences
are the template with the city swapped scores near zero, which is exactly the
doorway pattern Google penalizes, while a page that merely reuses vocabulary
still scores high.

Messages are French: they surface to a Quebec client in the dashboard.
"""
from __future__ import annotations

import re

__all__ = [
    'LOCATION_WARNING_AT',
    'LOCATION_HARD_STOP_AT',
    'PAGE_TYPE_RULES',
    'check_location_volume',
    'uniqueness_ratio',
    'check_page_quality',
]


# Google's doorway-page algorithm targets programmatic location pages whose
# only difference is the city name. The source sets the alarm well before the
# penalty, so there is room to fix rather than to recover.
LOCATION_WARNING_AT = 30
LOCATION_HARD_STOP_AT = 50
LOCATION_UNIQUE_PCT = 60

# Floors per page type: minimum words, and how much of the text must be unique
# against the other pages of the same set.
PAGE_TYPE_RULES = {
    'homepage':          {'min_words': 500,  'unique_pct': 100},
    'service':           {'min_words': 800,  'unique_pct': 100},
    'location_primary':  {'min_words': 600,  'unique_pct': 60},
    'location':          {'min_words': 500,  'unique_pct': 40},
    'blog_post':         {'min_words': 1500, 'unique_pct': 100},
    'product':           {'min_words': 400,  'unique_pct': 80},
    'category':          {'min_words': 400,  'unique_pct': 100},
    'about':             {'min_words': 400,  'unique_pct': 100},
    'landing':           {'min_words': 600,  'unique_pct': 100},
    'faq':               {'min_words': 800,  'unique_pct': 100},
}

TITLE_MIN, TITLE_MAX = 30, 60
META_MIN, META_MAX = 120, 160

_SHINGLE = 5
_WORD_RE = re.compile(r"[0-9a-zà-öø-ÿ']+", re.IGNORECASE)


def _words(text: str) -> list[str]:
    return _WORD_RE.findall((text or '').lower())


def _shingles(text: str, n: int = _SHINGLE) -> set[str]:
    w = _words(text)
    if len(w) < n:
        return {' '.join(w)} if w else set()
    return {' '.join(w[i:i + n]) for i in range(len(w) - n + 1)}


def uniqueness_ratio(text: str, peers) -> float:
    """Share of this page's phrasing that appears on none of its peers, 0..1.

    Peers are the other pages of the same programmatic set. Returns 1.0 when
    there are no peers: a single page cannot duplicate anything.
    """
    mine = _shingles(text)
    if not mine:
        return 0.0
    seen = set()
    for p in peers or []:
        seen |= _shingles(p)
    if not seen:
        return 1.0
    return len(mine - seen) / len(mine)


def check_location_volume(existing: int, adding: int = 1) -> dict:
    """Gate the number of location pages on a site.

    `level` is 'ok', 'warning' or 'hard_stop'. A hard stop is meant to be
    refused by the caller unless the user explicitly justifies it.
    """
    total = max(0, existing) + max(0, adding)

    if total >= LOCATION_HARD_STOP_AT:
        return {
            'level': 'hard_stop',
            'total': total,
            'threshold': LOCATION_HARD_STOP_AT,
            'message': (
                f'{total} pages de localite sur ce site. Au-dela de '
                f'{LOCATION_HARD_STOP_AT}, Google traite le lot comme des pages '
                'tremplin si rien ne prouve une presence reelle dans chaque ville.'
            ),
            'requirements': [
                'Une presence commerciale reelle et verifiable dans chaque ville',
                'Une strategie de contenu propre a chaque page, pas un gabarit',
                'Des signaux locaux : fiche Google Business, avis locaux',
            ],
        }

    if total >= LOCATION_WARNING_AT:
        return {
            'level': 'warning',
            'total': total,
            'threshold': LOCATION_WARNING_AT,
            'message': (
                f'{total} pages de localite sur ce site. A partir de '
                f'{LOCATION_WARNING_AT}, il faut {LOCATION_UNIQUE_PCT} % de '
                'contenu unique par page pour rester hors du motif page tremplin.'
            ),
            'requirements': [
                'Une information locale reelle : reperes, quartiers desservis',
                'Des services ou offres propres a cette localite',
                'L equipe ou le personnel de cette localite',
                'De vrais temoignages de clients de ce secteur',
            ],
        }

    return {'level': 'ok', 'total': total, 'threshold': LOCATION_WARNING_AT,
            'message': '', 'requirements': []}


def check_page_quality(page_type: str, *, text: str = '', title: str = '',
                       meta_description: str = '', peers=None) -> list[dict]:
    """Findings for one page against its type's floors.

    Each finding is {level, check, message}, level in 'error' / 'warning'.
    """
    rules = PAGE_TYPE_RULES.get(page_type, PAGE_TYPE_RULES['landing'])
    out = []

    word_count = len(_words(text))
    if word_count < rules['min_words']:
        out.append({
            'level': 'warning',
            'check': 'word_count',
            'message': (
                f'{word_count} mots pour un type "{page_type}" qui en demande '
                f'au moins {rules["min_words"]}. Une page trop courte passe pour '
                'du contenu mince.'
            ),
        })

    if peers:
        ratio = uniqueness_ratio(text, peers)
        required = rules['unique_pct'] / 100
        if ratio < required:
            # Below 30 % the source treats it as scaled content abuse, not a
            # quality warning, so it stops being negotiable.
            level = 'error' if ratio < 0.30 else 'warning'
            out.append({
                'level': level,
                'check': 'uniqueness',
                'message': (
                    f'{round(ratio * 100)} % de contenu unique face aux '
                    f'{len(peers)} autres pages du meme lot, il en faut '
                    f'{rules["unique_pct"]} %. Une page dont seul le nom de '
                    'ville change est une page tremplin.'
                ),
            })

    t = (title or '').strip()
    if t and not (TITLE_MIN <= len(t) <= TITLE_MAX):
        out.append({
            'level': 'warning',
            'check': 'title_length',
            'message': (
                f'Titre de {len(t)} caracteres, la cible est {TITLE_MIN} a '
                f'{TITLE_MAX} : Google tronque au-dela.'
            ),
        })

    m = (meta_description or '').strip()
    if m and not (META_MIN <= len(m) <= META_MAX):
        out.append({
            'level': 'warning',
            'check': 'meta_length',
            'message': (
                f'Meta description de {len(m)} caracteres, la cible est '
                f'{META_MIN} a {META_MAX}.'
            ),
        })

    return out
