"""Detection of factual claims that carry no nearby source marker.

Ported from claude-seo v2.2.4 `scripts/content_verify.py`.
Copyright (c) 2025 Daniel Agrici (AgriciDaniel). MIT.
https://github.com/AgriciDaniel/claude-seo

Upstream matches English only, so every pattern was rewritten for Quebec
French: percent signs behind a no-break space, decimal commas, "45 000 $"
money, "selon une etude" attributions, proportion words like "la majorite
des" that assert a statistic without a digit, and accent-tolerant letters
throughout since CMS exports and plain-text pastes routinely strip the
diacritics. Three deliberate divergences. Bare years ("en 2025", "in 2025")
stopped being claims because SEO headings are full of them and flagging
every one buries the real findings, so only anchored dates survive ("depuis
2019", "mars 2024"). Absolute superlatives got their own kind instead of
riding along with numeric comparatives, since the repair differs: a
statistic needs a source, a superlative needs a benchmark or a deletion.
And upstream compiles its citation patterns with re.IGNORECASE while asking
them to match a proper noun via [A-Z], which makes "according to a study"
self-citing and hides exactly the claims this module exists to surface;
here the proper-noun patterns are case sensitive and only the keyword
carries an inline (?i:).
"""
from __future__ import annotations

import re

__all__ = [
    'CLAIM_KINDS',
    'extract_claims',
    'find_unsourced_claims',
    'verify_text',
]


CLAIM_KINDS = frozenset({
    'statistic',
    'quantity',
    'authority',
    'temporal',
    'comparative',
    'superlative',
})

_DEFAULT_WINDOW = 200
_CONTEXT_RADIUS = 100


# ---------------------------------------------------------------------------
# Pattern building blocks
# ---------------------------------------------------------------------------
# Patterns are written with {PLACEHOLDER} tokens and expanded by _build.
# str.replace rather than str.format, so the regex quantifiers ({0,3}) can
# stay where they are.
#
# The lowercase vowel tokens accept the bare letter as well as the accented
# ones. Gridar reads text back from client CMS exports and plain-text pastes
# that drop diacritics, and Gridar's own French source strings are written
# unaccented, so a pattern demanding "etude" spelled one exact way would go
# silent on half the corpus.
#
# Every non-ASCII character below is written \uXXXX. The escapes survive any
# re-encoding of this file, and two of the space characters are invisible in
# an editor, which makes the literal form impossible to review.
_PLACEHOLDERS = {
    '{e}': r'[e\u00e9\u00e8\u00ea\u00eb]',
    '{o}': r'[o\u00f4\u00f6]',
    '{u}': r'[u\u00f9\u00fb\u00fc]',

    # Any capital that can open a French or English proper noun.
    '{CAP}': (
        r'[A-Z\u00c0\u00c2\u00c4\u00c7\u00c9\u00c8\u00ca\u00cb'
        r'\u00ce\u00cf\u00d4\u00d6\u00d9\u00db\u00dc\u0152]'
    ),

    # Straight and curly, because generators emit both.
    '{AP}': r"['\u2019]",

    # French typography puts a no-break space before % and $, and the
    # generator emits both U+00A0 and the narrow U+202F. `\s` would cover
    # them, but the thousands groups spell the three characters out on
    # purpose: `\s` also matches a newline, which would let one number
    # swallow a line break and glue itself to an unrelated figure below.
    '{N}': (
        r'(?:\d{1,3}(?:[ \u00a0\u202f]\d{3})+'    # 45 000
        r'|\d{1,3}(?:,\d{3})+'                    # 45,000
        r'|\d+)'
        r'(?:[.,]\d+)?'                           # 1,5 and 1.5
    ),

    # Thousands-grouped only. Used where a bare four-digit run would let a
    # year read as a quantity ("2024 marquait un tournant").
    '{G}': r'\d{1,3}(?:[ \u00a0\u202f,]\d{3})+(?:[.,]\d+)?',

    # Grouped or four digits and up. Only ever used next to a currency
    # symbol, where the symbol removes the ambiguity with a year.
    '{B}': (
        r'(?:\d{1,3}(?:[ \u00a0\u202f]\d{3})+'
        r'|\d{1,3}(?:,\d{3})+'
        r'|\d{4,})(?:[.,]\d+)?'
    ),

    # Dollar, euro, pound.
    '{CUR}': r'[$\u20ac\u00a3]',
}


def _build(pattern: str, flags: int = 0) -> re.Pattern:
    expanded = pattern
    for token, value in _PLACEHOLDERS.items():
        expanded = expanded.replace(token, value)
    return re.compile(expanded, flags)


# ---------------------------------------------------------------------------
# Claim patterns
# ---------------------------------------------------------------------------
# Order is load bearing. The first pattern to cover a span wins and later
# ones skip it, so the specific forms come first: "47 % des PME" must be one
# statistic, not a statistic plus an overlapping bare percentage.

_NEUTRAL_CLAIM_SPECS: tuple[tuple[str, str], ...] = (
    # Amounts under a thousand are usually the site's own price, not a market
    # figure anyone has to back up, so the money forms start at four digits
    # or at an abbreviated magnitude (3 M$, 1,5 k$).
    (r'(?:{B}|{N}\s*[MGk])\s*{CUR}', 'quantity'),
    (r'{CUR}\s?(?:{B}|{N}\s*(?:million|billion|trillion|milliard|k|M|B)\b)',
     'quantity'),
    (r'{N}\s*(?:CAD|USD|EUR|GBP|CHF)\b', 'quantity'),
    (r'{N}\s*(?:millions?|milliards?|billions?|trillions?)\b', 'quantity'),
    (r'{G}\s+\w+', 'quantity'),
    (r'{N}\s*%', 'statistic'),
)

_FR_CLAIM_SPECS: tuple[tuple[str, str], ...] = (
    # The trailing run is capped and built from \w only, so a greedy match
    # cannot cross a period into the next sentence. The two-character floor
    # keeps an elision ("n'", "d'") out of the reported claim text.
    (r'{N}\s*%\s+(?:de|des|du|d{AP}|par)\s*\w{2,}(?:\s+\w{2,}){0,3}', 'statistic'),
    (r'\b(?:la\s+(?:grande\s+)?majorit{e}|la\s+plupart|la\s+quasi-totalit{e}'
     r'|une\s+majorit{e}|pr{e}s\s+de\s+la\s+moiti{e}|la\s+moiti{e}'
     r'|un\s+tiers|les\s+trois\s+quarts)\s+(?:de|des|du|d{AP})\s*\w{2,}',
     'statistic'),
    (r'\b(?:{N}|un|une|deux|trois|quatre|cinq|six|sept|huit|neuf)\s+'
     r'(?:\w+\s+){0,2}sur\s+(?:{N}|deux|trois|quatre|cinq|six|dix)\b',
     'statistic'),

    # Authority with nobody's name on it. "selon Statistique Canada" is
    # handled on the citation side and never reaches here.
    (r'\b(?:selon|d{AP}apr{e}s)\s+'
     r'(?:une?|des|de\s+nombreuses?|plusieurs|certaines?|la|les)\s+'
     r'(?:{e}tudes?|recherches?|enqu{e}tes?|sondages?|rapports?|analyses?'
     r'|sources?|experts?|sp{e}cialistes?|statistiques?|donn{e}es)\b',
     'authority'),
    (r'\b(?:une|des|plusieurs|de\s+nombreuses)\s+'
     r'(?:{e}tude|recherche|enqu{e}te|analyse)s?\s+'
     r'(?:r{e}centes?\s+|ind{e}pendantes?\s+|s{e}rieuses?\s+)?'
     r'(?:montrent?|d{e}montrent?|r{e}v{e}lent?|indiquent?|prouvent?'
     r'|confirment?|sugg{e}rent?|a\s+montr{e}|ont\s+montr{e})\b', 'authority'),
    (r'\b(?:les|des|de\s+nombreux|plusieurs|certains)\s+'
     r'(?:experts|chercheurs|sp{e}cialistes|analystes|professionnels)\s+'
     r'(?:s{AP}entendent|estiment|affirment|recommandent|confirment|disent'
     r'|s{AP}accordent)\b', 'authority'),
    (r'\bil\s+(?:est|a\s+{e}t{e})\s+'
     r'(?:prouv{e}|d{e}montr{e}|reconnu|{e}tabli)\s+que\b', 'authority'),
    (r'\b(?:les\s+)?(?:statistiques|donn{e}es|chiffres|{e}tudes)\s+'
     r'(?:montrent|d{e}montrent|r{e}v{e}lent|prouvent|indiquent|confirment)\b',
     'authority'),
    (r'\bon\s+estime\s+qu(?:e\b|{AP})', 'authority'),

    (r'\b(?:{N}|deux|trois|quatre|cinq|six|sept|huit|neuf|dix|vingt)\s*'
     r'(?:x|fois)\s+'
     r'(?:plus|moins|meilleure?|pire|sup{e}rieur|inf{e}rieur|rapide'
     r'|{e}lev{e})\w*', 'comparative'),
    (r'\b(?:le\s+double|le\s+triple|le\s+quadruple|la\s+moiti{e}\s+moins)\b',
     'comparative'),

    (r'\b(?:le\s+)?\d{1,2}(?:er)?\s+'
     r'(?:janvier|f{e}vrier|mars|avril|mai|juin|juillet|ao{u}t|septembre'
     r'|octobre|novembre|d{e}cembre)\s+(?:19|20)\d{2}\b', 'temporal'),
    (r'\b(?:janvier|f{e}vrier|mars|avril|mai|juin|juillet|ao{u}t|septembre'
     r'|octobre|novembre|d{e}cembre)\s+(?:19|20)\d{2}\b', 'temporal'),
    (r'\b(?:depuis|d{AP}ici|d{e}s|jusqu{AP}en|avant|apr{e}s|entre)\s+'
     r'(?:le\s+)?(?:19|20)\d{2}\b', 'temporal'),
    (r'\b(?:premier|deuxi{e}me|troisi{e}me|quatri{e}me|1er|2e|3e|4e)\s+'
     r'trimestre\s+(?:de\s+)?(?:19|20)\d{2}\b', 'temporal'),

    # A ranking is "le plus X" with an adjective for X. Followed by an adverb
    # ("le plus souvent") or a preposition ("ce qui vous apprendra le plus sur
    # eux"), the same three words are ordinary prose. Excluding the
    # prepositions also drops the real "le plus de trafic", which is the
    # cheaper mistake: this list is what keeps the detector off clean copy.
    (r'\b(?:le|la|les)\s+plus\s+'
     r'(?!(?:souvent|t{o}t|tard|vite|possible|rapidement|r{e}cemment|loin'
     r'|proche|de|du|des|sur|dans|en|pour|par|avec|au|aux|chez|sans|vers'
     r'|entre|que|qui)\b)\w+', 'superlative'),
    (r'\b(?:le|la|les)\s+(?:meilleurs?|meilleures?|pires?)\b(?:\s+\w+){0,2}',
     'superlative'),
    (r'\b(?:le|la)\s+(?:seul|seule)\s+\w+', 'superlative'),
    (r'\b(?:le|la|les)\s+(?:premiers?|premi{e}res?)\s+'
     r'(?:au|en|du|de\s+la|des|dans)\b', 'superlative'),
    # A ranking, not the "etape no 1" of a listicle: either a determiner in
    # front or a territory behind.
    (r'\b(?:le|la)\s+(?:num{e}ro\s+(?:un|1)|n[\u00b0o]\s*1|#\s*1)\b',
     'superlative'),
    (r'\b(?:num{e}ro\s+(?:un|1)|n[\u00b0o]\s*1|#\s*1)\s+'
     r'(?:au|en|du|des|dans|sur|mondial|canadien|qu{e}b{e}cois)\b',
     'superlative'),
    (r'\b(?:le|la)\s+(?:leader|r{e}f{e}rence)\s+(?:du|de\s+la|des|au|en|dans)\b',
     'superlative'),
)

_EN_CLAIM_SPECS: tuple[tuple[str, str], ...] = (
    (r'{N}\s*%\s+of\s+\w{2,}(?:\s+\w{2,}){0,3}', 'statistic'),
    (r'\b(?:most|the\s+majority|a\s+majority|two\s+thirds|three\s+quarters'
     r'|half)\s+of\s+\w{2,}', 'statistic'),
    (r'\b(?:{N}|one|two|three|four|five|six|seven|eight|nine)\s+(?:\w+\s+){0,2}'
     r'out\s+of\s+(?:{N}|two|three|four|five|ten)\b', 'statistic'),
    (r'\b(?:one|two|three|four)\s+in\s+(?:two|three|four|five|ten)\b',
     'statistic'),

    (r'\baccording\s+to\s+(?:an?|one|several|many|some|recent)\s+(?:\w+\s+){0,2}'
     r'(?:study|studies|report|survey|analysis|paper|source)\b', 'authority'),
    (r'\b(?:studies|research|experts|analysts|scientists|surveys)\s+'
     r'(?:show|shows|suggest|suggests|agree|agrees|found|indicate|indicates'
     r'|confirm|confirms|reveal|reveals)\b', 'authority'),
    (r'\bit\s+(?:is|has\s+been)\s+(?:proven|shown|established|widely\s+known)\s+'
     r'that\b', 'authority'),
    (r'\b(?:the\s+)?(?:data|statistics|numbers|figures)\s+'
     r'(?:show|shows|prove|proves|indicate|indicates|reveal|reveals)\b',
     'authority'),

    (r'\b(?:{N}|two|three|four|five|ten)\s*(?:x|times)\s+'
     r'(?:more|less|faster|slower|higher|lower|better|worse|cheaper)\b',
     'comparative'),
    (r'\b(?:twice|thrice|half)\s+as\s+\w+', 'comparative'),

    (r'\b(?:january|february|march|april|may|june|july|august|september'
     r'|october|november|december)\s+\d{1,2},?\s+(?:19|20)\d{2}\b', 'temporal'),
    (r'\b(?:since|by|as\s+of|until|between)\s+(?:19|20)\d{2}\b', 'temporal'),

    (r'\bthe\s+(?:best|worst|only|leading|largest|biggest|fastest|cheapest'
     r'|most\s+\w+)\b(?:\s+\w+){0,2}', 'superlative'),
    (r'\bthe\s+(?:number\s+one|#\s*1)\b', 'superlative'),
    (r'\b(?:number\s+one|#\s*1)\s+(?:in|for|on)\b', 'superlative'),
)


# ---------------------------------------------------------------------------
# Citation patterns
# ---------------------------------------------------------------------------
# A hit anywhere in the window counts. The module never checks that the
# source says what the claim says: the signal is whether the writer bothered
# to anchor the number at all.

_NEUTRAL_CITATION_SPECS: tuple[tuple[str, int], ...] = (
    (r'\[[^\]]+\]\(https?://[^)]+\)', 0),                       # markdown link
    (r"""<a\s+[^>]*href=["']https?://[^"']+["']""", re.I),      # HTML link
    (r'\[\^?\d+\]', 0),                                          # footnote [1] / [^1]
    # The closing quote of the JSON key sits between @type and the colon,
    # which upstream's version of this pattern does not allow for.
    (r'@type["\']?\s*:\s*["\']Citation["\']', re.I),             # schema.org Citation
    (r"""https?://[^\s)>\]"']+""", 0),                           # bare URL
    # Author-year, the shape government and academic sources get pasted in as.
    (r'\({CAP}[\w.\u2019\'-]+(?:\s+[\w.\u2019\'-]+){0,4},\s*(?:19|20)\d{2}\)', 0),
)

_FR_CITATION_SPECS: tuple[tuple[str, int], ...] = (
    # The \b keeps "ressources :" from reading as "sources :", and something
    # has to follow the colon for it to be a reference rather than a heading.
    (r'\b(?i:sources?|via|voir\s+aussi|r{e}f{e}rences?|r{e}f|tir{e}\s+de'
     r'|extrait\s+de|cr{e}dit)\s*:\s*\S', 0),
    # A named source. Case sensitivity is the whole point: "selon une etude"
    # names nobody and stays a claim, "selon Leger" anchors it.
    (r'\b(?i:selon|d{AP}apr{e}s|tel\s+que\s+rapport{e}\s+par|rapport{e}\s+par'
     r'|publi{e}e?\s+par|r{e}alis{e}e?\s+par|men{e}e?\s+par|cit{e}e?\s+par'
     r'|donn{e}es\s+de|chiffres\s+de)'
     r'\s+(?:l{AP}|le\s+|la\s+|les\s+|du\s+|des\s+|de\s+la\s+)?{CAP}', 0),
    (r'\b(?i:{e}tude|rapport|enqu{e}te|sondage|analyse|recherche|donn{e}es'
     r'|statistiques|chiffres|bilan)\s+'
     r'(?:de\s+l{AP}|d{AP}|de\s+|du\s+|des\s+|par\s+)\s*{CAP}', 0),
    # Quebec and international institutions carry their own authority: naming
    # one anchors the number even without an attribution verb.
    (r'\b(?:Statistique\s+Canada|StatCan|Institut\s+de\s+la\s+statistique'
     r'|Revenu\s+Qu{e}bec|Banque\s+du\s+Canada|INSPQ|OQLF|ISQ|CEFRIO|L{e}ger'
     r'|Ipsos|Gartner|Forrester|McKinsey|Nielsen|Statista|Deloitte|OCDE'
     r'|Google\s+Search\s+Central)\b', 0),
)

_EN_CITATION_SPECS: tuple[tuple[str, int], ...] = (
    (r'\b(?i:sources?|via|see\s+also|references?|credit|citation)\s*:\s*\S', 0),
    (r'\b(?i:according\s+to|per|reported\s+by|published\s+by|cited\s+(?:in|by)'
     r'|study\s+by|report\s+by|survey\s+by|data\s+from|research\s+from)'
     r'\s+(?:the\s+)?{CAP}', 0),
    (r'\b(?:Gartner|Forrester|McKinsey|Nielsen|Statista|Deloitte|Pew|Edelman'
     r'|MIT|Stanford|Harvard|Wharton|Ahrefs|Semrush|Moz)\b', 0),
)


def _compile_claims(specs) -> tuple:
    return tuple((_build(pattern, re.IGNORECASE), kind) for pattern, kind in specs)


def _compile_citations(specs) -> tuple:
    return tuple(_build(pattern, flags) for pattern, flags in specs)


_CLAIM_SETS = {
    'fr': _compile_claims(_FR_CLAIM_SPECS + _NEUTRAL_CLAIM_SPECS),
    'en': _compile_claims(_EN_CLAIM_SPECS + _NEUTRAL_CLAIM_SPECS),
    '': _compile_claims(_NEUTRAL_CLAIM_SPECS),
}

# An unknown language gets the narrowest claim set and the widest citation
# set on purpose: when the module cannot read the prose, it should fail
# toward saying nothing rather than toward accusing an author of inventing a
# number they did source.
_CITATION_SETS = {
    'fr': _compile_citations(_NEUTRAL_CITATION_SPECS + _FR_CITATION_SPECS),
    'en': _compile_citations(_NEUTRAL_CITATION_SPECS + _EN_CITATION_SPECS),
    '': _compile_citations(
        _NEUTRAL_CITATION_SPECS + _FR_CITATION_SPECS + _EN_CITATION_SPECS
    ),
}


def _normalize_lang(lang) -> str:
    if not isinstance(lang, str):
        return ''
    key = lang.strip().lower().replace('_', '-').split('-')[0]
    return key if key in ('fr', 'en') else ''


_PARAGRAPH_BREAK = re.compile(r'\n[ \t]*\r?\n')


def _block_bounds(breaks, length: int, position: int) -> tuple[int, int]:
    """Offsets of the paragraph containing `position`."""
    low, high = 0, length
    for break_start, break_end in breaks:
        if break_end <= position:
            low = break_end
        elif break_start >= position:
            high = break_start
            break
    return low, high


def _find_citation_near(text: str, position: int, patterns, window: int,
                        bounds: tuple[int, int]) -> str | None:
    """Return the citation text found within `window` chars of `position`.

    The window is clamped to the paragraph holding the claim. Upstream lets
    it run over any 200 characters, which means one "selon Statistique
    Canada" in a closing paragraph vouches for every invented figure in the
    one above it. A source anchors the claim it sits with, so a marker two
    paragraphs away buys nothing here. The cost is a genuine reference
    stranded on its own line right after the paragraph, which now reads as
    unsourced.
    """
    block_low, block_high = bounds
    start = max(block_low, position - window)
    end = min(block_high, position + window)
    snippet = text[start:end]
    for pattern in patterns:
        match = pattern.search(snippet)
        if match:
            return match.group(0)[:80]
    return None


def _context_around(text: str, start: int, end: int,
                    radius: int = _CONTEXT_RADIUS) -> str:
    """Readable snippet around a claim, whitespace collapsed onto one line.

    Boundaries snap to the nearest space so the editor is never handed half a
    word, and a leading or trailing '...' says the sentence carries on
    outside the snippet.
    """
    low = max(0, start - radius)
    high = min(len(text), end + radius)

    if low > 0:
        space = text.find(' ', low, start)
        if space != -1:
            low = space + 1
    if high < len(text):
        space = text.rfind(' ', end, high)
        if space != -1:
            high = space

    snippet = ' '.join(text[low:high].split())
    if low > 0:
        snippet = '... ' + snippet
    if high < len(text):
        snippet = snippet + ' ...'
    return snippet


def extract_claims(text: str, lang: str = 'fr', *,
                   window: int = _DEFAULT_WINDOW) -> list[dict]:
    """Every claim-like span in `text`, each marked sourced or not.

    Returns dicts of {claim, kind, position, context, has_citation, citation}
    sorted by position. Anything that is not a non-empty string returns [],
    since callers hand this raw article bodies that may still be null.
    """
    if not isinstance(text, str) or not text.strip():
        return []

    key = _normalize_lang(lang)
    claim_patterns = _CLAIM_SETS[key]
    citation_patterns = _CITATION_SETS[key]

    spans: list[tuple[int, int, str]] = []
    for pattern, kind in claim_patterns:
        for match in pattern.finditer(text):
            if any(match.start() < end and start < match.end()
                   for start, end, _ in spans):
                continue
            spans.append((match.start(), match.end(), kind))

    breaks = [(match.start(), match.end())
              for match in _PARAGRAPH_BREAK.finditer(text)]

    claims: list[dict] = []
    for start, end, kind in sorted(spans):
        citation = _find_citation_near(
            text, start, citation_patterns, window,
            _block_bounds(breaks, len(text), start),
        )
        claims.append({
            'claim': text[start:end].strip(),
            'kind': kind,
            'position': start,
            'context': _context_around(text, start, end),
            'has_citation': citation is not None,
            'citation': citation,
        })
    return claims


def find_unsourced_claims(text: str, lang: str = 'fr', *,
                          window: int = _DEFAULT_WINDOW) -> list[dict]:
    """Claims with no source marker within `window` chars, sorted by position.

    Each entry is {claim, kind, position, context}. `position` is the offset
    into the original `text`, so a caller can highlight the span in place.
    """
    return [
        {key: claim[key] for key in ('claim', 'kind', 'position', 'context')}
        for claim in extract_claims(text, lang, window=window)
        if not claim['has_citation']
    ]


def verify_text(text: str, lang: str = 'fr', *,
                window: int = _DEFAULT_WINDOW) -> dict:
    """Claim inventory plus the counts an audit score can be built from."""
    claims = extract_claims(text, lang, window=window)
    unsourced = [claim for claim in claims if not claim['has_citation']]

    by_kind: dict[str, int] = {}
    for claim in unsourced:
        by_kind[claim['kind']] = by_kind.get(claim['kind'], 0) + 1

    return {
        'claims': claims,
        'claim_count': len(claims),
        'unsourced_count': len(unsourced),
        'unsourced_ratio': round(len(unsourced) / len(claims), 3) if claims else 0.0,
        'unsourced_by_kind': by_kind,
    }
