"""SEO drift watch: snapshot the critical tags of a page, then compare two snapshots.

Porte depuis claude-seo v2.2.4 `scripts/drift_baseline.py` et `scripts/drift_compare.py`.
Copyright (c) 2025 Daniel Agrici (AgriciDaniel). MIT.
https://github.com/AgriciDaniel/claude-seo

Three things changed. Upstream captures a page by spawning `fetch_page.py`,
`parse_html.py` and `pagespeed_check.py` as subprocesses, re-parsing their
stdout and writing SQLite; a Django worker cannot fork a process per page, so
the capture is rewritten on `html.parser` from the standard library and both
functions here stay pure, leaving fetching and storage to the caller. The two
Core Web Vitals rules needed the PageSpeed API and had nothing to read in an
HTML snapshot, so they are replaced by two rules over fields the HTML does
carry and that matter to Gridar: body text amputated, and internal links lost.
Word counting uses a French-aware token regex rather than upstream's plain
word-boundary split, which cuts "aujourd'hui" and "peut-etre" in two and
inflates the count of a Quebec page by roughly a tenth.
"""
from __future__ import annotations

import hashlib
import json
import re
from difflib import SequenceMatcher
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

__all__ = [
    'SNAPSHOT_VERSION',
    'RULE_NAMES',
    'capture_snapshot',
    'compare_snapshots',
    'summarize_findings',
]

# Bumped whenever a stored snapshot stops being comparable with a fresh one,
# so the caller can decide to re-baseline instead of reporting phantom drift.
SNAPSHOT_VERSION = 1

# Text inside these never counts as page copy. Dropping nav, header and footer
# is what keeps the word count stable when only the template moves.
_TEXT_SKIP_TAGS = frozenset({
    'script', 'style', 'noscript', 'template', 'svg', 'nav', 'header', 'footer',
})

# Google no longer renders these as rich results, so losing them is not the
# same emergency as losing a LocalBusiness or a Product block.
_RETIRED_SCHEMA_TYPES = frozenset({'FAQPage', 'HowTo', 'Dataset'})

# French elision and hyphenation hold a token together: "aujourd'hui",
# "peut-etre" and "d'une" are one word each. Digits are kept as tokens so a
# price list does not read as an empty page.
_WORD_RE = re.compile(r"[^\W\d_]+(?:['’\-][^\W\d_]+)*|\d+(?:[.,]\d+)*")

_SEVERITY_RANK = {'critical': 0, 'warning': 1, 'info': 2}

# Below these floors the ratio rules fire on noise: a 40 word landing page that
# loses 9 words is not an amputation, and a page with 3 links is not a hub.
_MIN_WORDS_FOR_CONTENT_RULE = 100
_CONTENT_LOSS_RATIO = 0.20
_MIN_LINKS_FOR_LINK_RULE = 5
_LINK_LOSS_RATIO = 0.30

# Below this similarity the H1 no longer targets the same thing.
_H1_SIMILARITY_FLOOR = 0.5


# ---------------------------------------------------------------------------
# HTML extraction
# ---------------------------------------------------------------------------

class _SnapshotParser(HTMLParser):
    """Best-effort SEO extraction on the standard library parser.

    Upstream leans on BeautifulSoup plus lxml. Neither is installed here and
    lxml compiles, so this walks the tag stream instead. Depth counters are
    clamped at zero because real pages close tags they never opened.
    """

    def __init__(self, base_url: str):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.base_host = (urlparse(base_url).hostname or '').lower().removeprefix('www.')

        self.title = ''
        self.meta_description = ''
        self.meta_robots = ''
        self.meta_googlebot = ''
        self.viewport = ''
        self.canonical = ''
        self.open_graph: dict[str, str] = {}
        self.hreflang: dict[str, str] = {}
        self.h1: list[str] = []
        self.schema_blocks: list[dict] = []
        self.internal_links = 0
        self.external_links = 0

        self._skip_depth = 0
        self._in_title = False
        self._title_parts: list[str] = []
        self._h1_depth = 0
        self._h1_parts: list[str] = []
        self._ld_parts: list[str] | None = None
        self._text_parts: list[str] = []

    # -- element handlers ---------------------------------------------------

    def handle_starttag(self, tag, attrs):
        attributes = {name.lower(): (value or '') for name, value in attrs}

        # A title holds text and nothing else. Closing it on the next opening
        # tag is what stops an unclosed <title> from swallowing the whole page,
        # which happens on hand written pages and leaves both the title and the
        # word count empty.
        if self._in_title and tag != 'title':
            self._finish_title()

        if tag in _TEXT_SKIP_TAGS:
            self._skip_depth += 1

        if tag == 'title':
            # An SVG icon can carry its own <title>; the skip depth is what
            # keeps it out of the page title.
            if not self.title and self._skip_depth == 0:
                self._in_title = True
                self._title_parts = []
        elif tag == 'meta':
            self._handle_meta(attributes)
        elif tag == 'link':
            self._handle_link(attributes)
        elif tag == 'h1':
            self._h1_depth += 1
            if self._h1_depth == 1:
                self._h1_parts = []
        elif tag == 'a':
            self._handle_anchor(attributes)
        elif tag == 'script':
            if attributes.get('type', '').strip().lower() == 'application/ld+json':
                self._ld_parts = []

    def handle_endtag(self, tag):
        if tag in _TEXT_SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1

        if tag == 'title' and self._in_title:
            self._finish_title()
        elif tag == 'h1' and self._h1_depth > 0:
            self._h1_depth -= 1
            if self._h1_depth == 0:
                text = _collapse(''.join(self._h1_parts))
                if text:
                    self.h1.append(text)
        elif tag == 'script' and self._ld_parts is not None:
            self._consume_json_ld(''.join(self._ld_parts))
            self._ld_parts = None

    def handle_data(self, data):
        if self._in_title:
            self._title_parts.append(data)
            return
        if self._ld_parts is not None:
            self._ld_parts.append(data)
            return
        if self._h1_depth > 0:
            # An H1 sitting inside <header> is still the page H1, so this does
            # not go through the skip depth.
            self._h1_parts.append(data)
        if self._skip_depth == 0:
            self._text_parts.append(data)

    # -- attribute readers --------------------------------------------------

    def _handle_meta(self, attributes):
        name = attributes.get('name', '').strip().lower()
        prop = attributes.get('property', '').strip().lower()
        content = attributes.get('content', '')

        if name == 'description' and not self.meta_description:
            self.meta_description = _collapse(content)
        elif name == 'robots' and not self.meta_robots:
            self.meta_robots = _collapse(content)
        elif name in ('googlebot', 'googlebot-news') and not self.meta_googlebot:
            self.meta_googlebot = _collapse(content)
        elif name == 'viewport' and not self.viewport:
            self.viewport = _collapse(content)

        if prop.startswith('og:') and prop not in self.open_graph:
            self.open_graph[prop] = _collapse(content)

    def _handle_link(self, attributes):
        rels = attributes.get('rel', '').lower().split()
        href = attributes.get('href', '').strip()
        if not href:
            return
        if 'canonical' in rels and not self.canonical:
            self.canonical = self._absolute(href)
        if 'alternate' in rels:
            lang = attributes.get('hreflang', '').strip().lower()
            if lang:
                self.hreflang.setdefault(lang, self._absolute(href))

    def _handle_anchor(self, attributes):
        href = attributes.get('href', '').strip()
        if not href or href.startswith('#'):
            return
        absolute = self._absolute(href)
        parsed = urlparse(absolute)
        if parsed.scheme and parsed.scheme not in ('http', 'https'):
            return
        host = (parsed.hostname or '').lower().removeprefix('www.')
        if not host or host == self.base_host:
            self.internal_links += 1
        else:
            self.external_links += 1

    def _absolute(self, href):
        if not self.base_url:
            return href
        try:
            return urljoin(self.base_url, href)
        except ValueError:
            return href

    def _consume_json_ld(self, raw):
        raw = raw.strip()
        if not raw:
            return
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            # A broken JSON-LD block is itself an SEO problem, but reporting it
            # belongs to the audit, not to drift detection.
            return
        self.schema_blocks.extend(_flatten_schema(data))

    # -- results ------------------------------------------------------------

    def _finish_title(self):
        self._in_title = False
        self.title = _collapse(''.join(self._title_parts))

    def finalize(self):
        """Flush what a truncated document left open."""
        if self._in_title:
            self._finish_title()

    def visible_text(self):
        return ' '.join(self._text_parts)


def _flatten_schema(data):
    """Unwrap @graph containers and arrays so every @type is its own block."""
    blocks = []
    if isinstance(data, list):
        for item in data:
            blocks.extend(_flatten_schema(item))
    elif isinstance(data, dict):
        graph = data.get('@graph')
        if isinstance(graph, list):
            for item in graph:
                blocks.extend(_flatten_schema(item))
        else:
            blocks.append(data)
    return blocks


def _schema_types(blocks):
    types = set()
    for block in blocks:
        if not isinstance(block, dict):
            continue
        value = block.get('@type')
        for item in (value if isinstance(value, list) else [value]):
            if isinstance(item, str) and item:
                types.add(item.rsplit('/', 1)[-1].rsplit('#', 1)[-1])
    return sorted(types)


def _schema_hash(blocks):
    """Fingerprint of the JSON-LD payload, key order made irrelevant."""
    if not blocks:
        return ''
    try:
        payload = json.dumps(blocks, sort_keys=True, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        payload = repr(blocks)
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def _collapse(value):
    return ' '.join((value or '').split())


def _count_words(text):
    return len(_WORD_RE.findall(text or ''))


def capture_snapshot(html: str, url: str) -> dict:
    """Extract the SEO fields the rules compare. No network, no ORM, no I/O.

    `status_code` is left at None on purpose: it lives in the HTTP response,
    not in the HTML. A caller holding the response should set it before
    storing the snapshot, otherwise the `code_http_erreur` rule stays silent.

    Every value is JSON-safe and survives a round trip through a JSONField
    unchanged, which is what lets two snapshots taken weeks apart compare.
    """
    parser = _SnapshotParser(url or '')
    try:
        parser.feed(html or '')
        parser.close()
        parser.finalize()
    except Exception:
        # Third-party HTML is hostile by nature. A page that breaks the parser
        # must degrade to a partial snapshot, never take the worker down.
        pass

    blocks = parser.schema_blocks
    return {
        'snapshot_version': SNAPSHOT_VERSION,
        'url': url or '',
        'status_code': None,
        'title': parser.title,
        'meta_description': parser.meta_description,
        'meta_robots': parser.meta_robots,
        'meta_googlebot': parser.meta_googlebot,
        'viewport': parser.viewport,
        'canonical': parser.canonical,
        'h1': list(parser.h1),
        'open_graph': dict(parser.open_graph),
        'hreflang': dict(parser.hreflang),
        'schema_types': _schema_types(blocks),
        'schema_count': len(blocks),
        'schema_hash': _schema_hash(blocks),
        'word_count': _count_words(parser.visible_text()),
        'internal_links': parser.internal_links,
        'external_links': parser.external_links,
    }


# ---------------------------------------------------------------------------
# Snapshot readers, tolerant of an older or truncated snapshot
# ---------------------------------------------------------------------------

def _finding(rule, severity, field, before, after, message):
    return {
        'rule': rule,
        'severity': severity,
        'field': field,
        'before': before,
        'after': after,
        'message': message,
    }


def _text(snapshot, key):
    value = snapshot.get(key)
    return value.strip() if isinstance(value, str) else ''


def _count(snapshot, key):
    value = snapshot.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return value


def _status(snapshot):
    value = snapshot.get('status_code')
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _mapping(snapshot, key):
    value = snapshot.get(key)
    return value if isinstance(value, dict) else {}


def _types(snapshot):
    value = snapshot.get('schema_types')
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _headings(snapshot):
    value = snapshot.get('h1')
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _directives(value):
    """Split a robots meta into comparable tokens."""
    return [token.strip().lower() for token in value.replace(';', ',').split(',') if token.strip()]


def _has_noindex(snapshot):
    """True when robots or googlebot blocks indexing.

    Upstream only looks for the substring "noindex" and misses
    `content="none"`, which Google reads as noindex plus nofollow.
    """
    for key in ('meta_robots', 'meta_googlebot'):
        for token in _directives(_text(snapshot, key)):
            if token in ('noindex', 'none'):
                return True
    return False


def _robots_summary(snapshot):
    parts = [_text(snapshot, 'meta_robots'), _text(snapshot, 'meta_googlebot')]
    return ' / '.join(part for part in parts if part)


def _truncate(value, limit=160):
    if len(value) <= limit:
        return value
    return value[:limit].rstrip() + '...'


def _listing(values):
    return ', '.join(values) if values else 'aucun'


# ---------------------------------------------------------------------------
# Rules. Function name after the `_rule_` prefix is the published rule name.
# ---------------------------------------------------------------------------

def _rule_schema_supprime(before, after):
    if _count(before, 'schema_count') == 0 or _count(after, 'schema_count') > 0:
        return None
    types = _types(before)
    retired_only = bool(types) and all(item in _RETIRED_SCHEMA_TYPES for item in types)
    if retired_only:
        message = (
            f"Les données structurées retirées ({_listing(types)}) ne donnent plus de "
            "résultats enrichis chez Google. La page ne perd rien en référencement."
        )
    else:
        message = (
            f"Toutes les données structurées ont disparu ({_listing(types)}). Les "
            "résultats enrichis vont tomber, vérifiez le gabarit de la page."
        )
    return _finding(
        'schema_supprime', 'warning' if retired_only else 'critical', 'schema',
        types, [], message,
    )


def _rule_canonical_modifie(before, after):
    old = _text(before, 'canonical')
    new = _text(after, 'canonical')
    if not old or not new or old == new:
        return None
    return _finding(
        'canonical_modifie', 'critical', 'canonical', old, new,
        f"L'URL canonique pointe maintenant vers {new}, alors qu'elle pointait vers "
        f"{old}. Si ce n'est pas voulu, Google va indexer l'autre page à la place.",
    )


def _rule_canonical_supprime(before, after):
    old = _text(before, 'canonical')
    if not old or _text(after, 'canonical'):
        return None
    return _finding(
        'canonical_supprime', 'critical', 'canonical', old, '',
        "La balise canonique a disparu. Google va choisir lui-même la version à "
        "indexer, souvent la mauvaise.",
    )


def _rule_noindex_ajoute(before, after):
    if _has_noindex(before) or not _has_noindex(after):
        return None
    return _finding(
        'noindex_ajoute', 'critical', 'meta_robots',
        _robots_summary(before), _robots_summary(after),
        f"Une directive noindex a été ajoutée ({_robots_summary(after)}). La page va "
        "sortir de l'index de Google en quelques jours.",
    )


def _rule_h1_supprime(before, after):
    old = _headings(before)
    if not old or _headings(after):
        return None
    return _finding(
        'h1_supprime', 'critical', 'h1', old[0], '',
        "Le H1 a disparu. Google perd le signal principal du sujet de la page.",
    )


def _rule_h1_modifie(before, after):
    old = _headings(before)
    new = _headings(after)
    if not old or not new or old[0] == new[0]:
        return None
    # Compared casefolded so a pure capitalization change stays quiet.
    ratio = SequenceMatcher(None, old[0].casefold(), new[0].casefold()).ratio()
    if ratio >= _H1_SIMILARITY_FLOOR:
        return None
    return _finding(
        'h1_modifie', 'critical', 'h1', old[0], new[0],
        f"Le H1 a changé en profondeur (similarité de {round(ratio * 100)} %). "
        "Vérifiez que le mot-clé ciblé est encore dedans.",
    )


def _rule_title_supprime(before, after):
    old = _text(before, 'title')
    if not old or _text(after, 'title'):
        return None
    return _finding(
        'title_supprime', 'critical', 'title', _truncate(old), '',
        "La balise title a disparu. Google va en fabriquer une à votre place, "
        "souvent moins bonne que la vôtre.",
    )


def _rule_code_http_erreur(before, after):
    old = _status(before)
    new = _status(after)
    if old is None or new is None:
        return None
    if not (200 <= old < 400) or new < 400:
        return None
    return _finding(
        'code_http_erreur', 'critical', 'status_code', old, new,
        f"La page répond maintenant HTTP {new}, alors qu'elle répondait {old}. Les "
        "positions vont chuter en quelques jours.",
    )


def _rule_title_modifie(before, after):
    old = _text(before, 'title')
    new = _text(after, 'title')
    if not old or not new or old == new:
        return None
    return _finding(
        'title_modifie', 'warning', 'title', _truncate(old), _truncate(new),
        "La balise title a changé. Surveillez le taux de clic dans Search Console "
        "pendant deux semaines.",
    )


def _rule_meta_description_modifiee(before, after):
    old = _text(before, 'meta_description')
    new = _text(after, 'meta_description')
    if not old or old == new:
        return None
    if new:
        message = (
            "La méta description a changé. Vérifiez qu'elle contient le mot-clé ciblé "
            "et une raison de cliquer."
        )
    else:
        message = (
            "La méta description a disparu. Google va découper un bout de texte au "
            "hasard pour le résumé affiché dans les résultats."
        )
    return _finding(
        'meta_description_modifiee', 'warning', 'meta_description',
        _truncate(old), _truncate(new), message,
    )


def _rule_contenu_ampute(before, after):
    old = _count(before, 'word_count')
    new = _count(after, 'word_count')
    if old < _MIN_WORDS_FOR_CONTENT_RULE:
        return None
    lost = old - new
    if lost <= 0 or lost / old < _CONTENT_LOSS_RATIO:
        return None
    return _finding(
        'contenu_ampute', 'warning', 'word_count', old, new,
        f"Le texte de la page a perdu {round(lost / old * 100)} % de ses mots, il passe "
        f"de {old} à {new}. Vérifiez que le gabarit n'a pas coupé le corps de la page.",
    )


def _rule_liens_internes_perdus(before, after):
    old = _count(before, 'internal_links')
    new = _count(after, 'internal_links')
    if old < _MIN_LINKS_FOR_LINK_RULE:
        return None
    lost = old - new
    if lost <= 0 or lost / old < _LINK_LOSS_RATIO:
        return None
    return _finding(
        'liens_internes_perdus', 'warning', 'internal_links', old, new,
        f"La page a perdu {lost} liens internes, elle passe de {old} à {new}. Le "
        "maillage qui poussait vos autres pages est cassé.",
    )


def _rule_og_supprimes(before, after):
    old = _mapping(before, 'open_graph')
    if not old or _mapping(after, 'open_graph'):
        return None
    return _finding(
        'og_supprimes', 'warning', 'open_graph', sorted(old), [],
        "Toutes les balises Open Graph ont disparu. Les partages sur Facebook et "
        "LinkedIn vont afficher un aperçu générique.",
    )


def _rule_schema_modifie(before, after):
    if _count(before, 'schema_count') == 0 or _count(after, 'schema_count') == 0:
        return None
    old_hash = _text(before, 'schema_hash')
    new_hash = _text(after, 'schema_hash')
    if not old_hash or not new_hash or old_hash == new_hash:
        return None
    old_types = _types(before)
    new_types = _types(after)
    if old_types != new_types:
        message = (
            f"Les types de données structurées ont changé : {_listing(old_types)} avant, "
            f"{_listing(new_types)} maintenant. Revalidez le JSON-LD."
        )
    else:
        message = (
            f"Le contenu des données structurées a changé alors que les types restent "
            f"les mêmes ({_listing(old_types)}). Revalidez le JSON-LD avant que Google "
            "signale une erreur."
        )
    return _finding(
        'schema_modifie', 'warning', 'schema', old_types, new_types, message,
    )


def _rule_viewport_supprime(before, after):
    old = _text(before, 'viewport')
    if not old or _text(after, 'viewport'):
        return None
    return _finding(
        'viewport_supprime', 'warning', 'viewport', old, '',
        "La balise viewport a disparu. Google indexe la version mobile en premier, il "
        "va juger la page inadaptée au mobile.",
    )


def _rule_schema_ajoute(before, after):
    new_count = _count(after, 'schema_count')
    if _count(before, 'schema_count') > 0 or new_count == 0:
        return None
    new_types = _types(after)
    return _finding(
        'schema_ajoute', 'info', 'schema', [], new_types,
        f"De nouvelles données structurées ont été ajoutées ({_listing(new_types)}). "
        "Bon signal, validez-les avec le test des résultats enrichis.",
    )


def _rule_hreflang_modifie(before, after):
    old = sorted(_mapping(before, 'hreflang'))
    new = sorted(_mapping(after, 'hreflang'))
    if not old or old == new:
        return None
    if new:
        severity = 'info'
        message = (
            f"Les balises hreflang ont changé : {_listing(old)} avant, {_listing(new)} "
            "maintenant."
        )
    else:
        severity = 'warning'
        message = (
            f"Les balises hreflang ont disparu (avant : {_listing(old)}). Les versions "
            "linguistiques ne sont plus reliées, Google peut servir la mauvaise langue "
            "à un visiteur du Québec."
        )
    return _finding('hreflang_modifie', severity, 'hreflang', old, new, message)


# Order matters twice: it is the tie-breaker inside a severity level, and it is
# the order the 17 rule names are published in.
_RULES = (
    _rule_schema_supprime,
    _rule_canonical_modifie,
    _rule_canonical_supprime,
    _rule_noindex_ajoute,
    _rule_h1_supprime,
    _rule_h1_modifie,
    _rule_title_supprime,
    _rule_code_http_erreur,
    _rule_title_modifie,
    _rule_meta_description_modifiee,
    _rule_contenu_ampute,
    _rule_liens_internes_perdus,
    _rule_og_supprimes,
    _rule_schema_modifie,
    _rule_viewport_supprime,
    _rule_schema_ajoute,
    _rule_hreflang_modifie,
)

RULE_NAMES = tuple(rule.__name__[len('_rule_'):] for rule in _RULES)


def compare_snapshots(before: dict, after: dict) -> list[dict]:
    """Run the 17 rules and return only what fired, worst first.

    Upstream returns every rule with a `triggered` flag. Here a finding is
    reported only when it fires, because the list goes straight into a client
    facing report where 14 lines of "unchanged" are noise.

    An empty or missing snapshot on either side returns no finding rather than
    a wall of false alarms: a first capture has nothing to drift from.
    """
    if not isinstance(before, dict) or not isinstance(after, dict):
        return []
    if not before or not after:
        return []

    ranked = []
    for index, rule in enumerate(_RULES):
        finding = rule(before, after)
        if finding is not None:
            ranked.append((_SEVERITY_RANK.get(finding['severity'], 9), index, finding))

    ranked.sort(key=lambda row: (row[0], row[1]))
    return [row[2] for row in ranked]


def summarize_findings(findings) -> dict:
    """Counts per severity, for a badge or an alert threshold."""
    summary = {'critical': 0, 'warning': 0, 'info': 0}
    for finding in findings or []:
        if isinstance(finding, dict):
            severity = finding.get('severity')
            if severity in summary:
                summary[severity] += 1
    summary['total'] = summary['critical'] + summary['warning'] + summary['info']
    summary['rules_checked'] = len(RULE_NAMES)
    return summary
