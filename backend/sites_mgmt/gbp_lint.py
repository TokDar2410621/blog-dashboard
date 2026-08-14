"""Find references to retired Google Business Profile features in a page.

Ported from claude-seo v2.2.4 `scripts/gbp_deprecation_lint.py`.
Copyright (c) 2025 Daniel Agrici (AgriciDaniel). MIT.
https://github.com/AgriciDaniel/claude-seo

Upstream matches four English chat phrases plus one `.business.site` URL,
which finds nothing on a Quebec small-business site where the dead button
reads "Clavardez avec nous sur notre fiche Google". So phrase matching became
a proximity rule over accent-folded visible text, with a veto that keeps the
review CTA ("laissez-nous un avis sur Google") out of the results, and the
rule set grew to the other Google surfaces these sites still link to: the
shut-down site builder, Google+, the retired Google My Business app. Upstream
also hedges on `.business.site` ("shutdown status was not confirmed"); the
redirect to the profile stopped on 2024-06-10, so the finding states that
with its date instead, since the date is what makes a client act.
"""
from __future__ import annotations

import re
import unicodedata
from html.parser import HTMLParser
from urllib.parse import urlparse

__all__ = [
    'lint_gbp_references',
    'summarize_gbp_lint',
    'SEVERITY_RANK',
]


# Findings are ordered by this rank, and the labels match the ones the rest of
# the dashboard already emits ('critical' / 'high' / 'medium' / 'low').
SEVERITY_RANK = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}

# This runs on markup fetched from someone else, inside a request cycle, so
# the scan is bounded rather than trusting the page to be a sane size.
_MAX_HTML = 2_000_000

# One page can carry the same dead link in a header, a footer and a sidebar.
# Distinct matches beyond this per rule add noise without adding a decision.
_MAX_PER_CODE = 5

# Folded characters searched on each side of a Google surface mention when
# looking for a messaging verb, then the widest gap tolerated between the two.
_PROXIMITY_WINDOW = 70
_MAX_GAP = 45


_RULES = {
    'gbp_chat_cta': {
        'severity': 'critical',
        'feature': 'Clavardage / messagerie de la fiche Google',
        'retired_on': '2024-07-31',
        'message': (
            "Google a ferme le clavardage et la messagerie des fiches Google "
            "Business le 31 juillet 2024. Le visiteur qui clique croit vous "
            "ecrire, mais le message ne part nulle part et personne n'y repond."
        ),
        'fix': (
            "Retirez cet appel a l'action ou pointez-le vers un canal qui "
            "repond vraiment : telephone, SMS, formulaire de contact, courriel."
        ),
    },
    'gbp_chat_widget': {
        'severity': 'critical',
        'feature': 'Widget Google Business Messages',
        'retired_on': '2024-07-31',
        'message': (
            "Cette page charge la messagerie Google Business (Business "
            "Messages), arretee par Google le 31 juillet 2024. Le widget "
            "n'affiche plus rien et les messages envoyes d'ici ne sont jamais "
            "recus."
        ),
        'fix': (
            "Supprimez le script et le bouton qui l'ouvre, puis branchez un "
            "canal actif a la place."
        ),
    },
    'gbp_call_history': {
        'severity': 'medium',
        'feature': 'Historique des appels de la fiche Google',
        'retired_on': '2024-07-31',
        'message': (
            "L'historique des appels des fiches Google Business a ete retire "
            "le 31 juillet 2024. Cette page promet un suivi d'appels que "
            "Google ne fournit plus."
        ),
        'fix': (
            "Retirez la mention, ou faites le suivi avec un numero de call "
            "tracking que vous controlez."
        ),
    },
    'gbp_business_site_link': {
        'severity': 'high',
        'feature': 'Lien vers un site .business.site',
        'retired_on': '2024-06-10',
        'message': (
            "Ce lien mene a {host}, un site cree avec le constructeur des "
            "fiches Google Business. Google a ferme ces sites en mars 2024 et "
            "la redirection vers la fiche s'est arretee le 10 juin 2024 : le "
            "lien tombe dans le vide."
        ),
        'fix': (
            "Remplacez-le par l'adresse de votre vrai site, et corrigez le "
            "champ Site Web de votre fiche Google au passage."
        ),
    },
    'gbp_site_on_business_site': {
        'severity': 'critical',
        'feature': 'Page hebergee sur .business.site',
        'retired_on': '2024-06-10',
        'message': (
            "La page analysee est hebergee sur {host}, le constructeur de "
            "sites des fiches Google Business. Google a ferme ces sites en "
            "mars 2024 et la redirection vers la fiche s'est arretee le 10 "
            "juin 2024 : cette adresse ne repond plus a vos clients."
        ),
        'fix': (
            "Republiez le contenu sur un domaine qui vous appartient, puis "
            "pointez la fiche Google et vos reseaux vers la nouvelle adresse."
        ),
    },
    'gbp_website_builder_link': {
        'severity': 'high',
        'feature': 'Lien vers le constructeur de sites Google Business',
        'retired_on': '2024-06-10',
        'message': (
            "Ce lien mene au constructeur de sites des fiches Google Business, "
            "ferme par Google en mars 2024, redirection coupee le 10 juin "
            "2024. Il ne mene plus a une page publique."
        ),
        'fix': "Pointez le lien vers votre site actuel, ou retirez-le.",
    },
    'google_plus_link': {
        'severity': 'medium',
        'feature': 'Lien Google+',
        'retired_on': '2019-04-02',
        'message': (
            "Lien vers Google+, ferme le 2 avril 2019. Il traine encore dans "
            "beaucoup de pieds de page et de balises rel=publisher, et il "
            "mene a une erreur."
        ),
        'fix': (
            "Supprimez le lien et son icone. S'il apparait dans le sameAs de "
            "votre balisage schema.org, retirez-le la aussi."
        ),
    },
    'gmb_app_link': {
        'severity': 'medium',
        'feature': "Lien vers l'application Google My Business",
        'retired_on': '2022',
        'message': (
            "Lien vers l'application Google My Business, retiree des magasins "
            "d'applications en 2022. Google a deplace la gestion des fiches "
            "dans Maps et dans la Recherche."
        ),
        'fix': (
            "Pointez plutot vers votre fiche dans Google Maps, ou retirez le "
            "lien."
        ),
    },
    'gmb_branding': {
        'severity': 'low',
        'feature': 'Ancien nom Google My Business',
        'retired_on': '2021-11',
        'message': (
            "La page parle encore de Google My Business. Le produit s'appelle "
            "Profil d'entreprise Google depuis novembre 2021 et l'application "
            "du meme nom a ete retiree en 2022. Rien n'est casse, mais le "
            "vocabulaire date la page aux yeux du lecteur."
        ),
        'fix': "Ecrivez plutot fiche Google, ou Profil d'entreprise Google.",
    },
}


# Product names and fixed CTAs, matched on their own because they carry the
# link to Google inside the phrase: no proximity check is needed.
_EXPLICIT_CHAT_RE = re.compile(
    r"google\s+(?:my\s+)?business\s+(?:chat|message(?:s|rie)?|messaging)"
    r"|(?:chat|clavardage|messagerie)\s+"
    r"(?:google\s+(?:my\s+)?business"
    r"|(?:de\s+)?(?:la\s+|notre\s+|votre\s+|ma\s+|sa\s+)?fiche\s+google"
    r"|google\b)"
    r"|business\s+messages?\s+(?:by|from|de)\s+google"
    r"|message\s+us\s+(?:on|via|through|at|from)\s+google"
    r"|chat\s+(?:with\s+us\s+)?(?:on|via|through|with)\s+google"
)

# The names a local business gives its Google presence. Google Maps is
# deliberately absent here: a Maps link sitting a few words from a contact
# form is the most common footer in Quebec, and it is not a dead chat button.
# The Maps wording that really is dead ("clavardage Google Maps") is covered
# by the explicit patterns above.
_SURFACE_RE = re.compile(
    r"google\s+(?:my\s+)?business(?:\s+profile)?"
    r"|(?:fiche|profil|page)\s+"
    r"(?:d'entreprise\s+|d'etablissement\s+|de\s+l'etablissement\s+)?google"
)

# A messaging intent near one of those surfaces. Quebec French says
# "clavarder", which no English pattern would ever catch. Every verb has to
# be aimed at the business ("ecrivez-nous", not "ecrivez"), otherwise advice
# pages get flagged: "ecrivez une description pour votre fiche Google
# Business" is a recommendation, not a dead button.
_MESSAGING_RE = re.compile(
    r"clavard\w*"
    r"|messagerie\w*"
    r"|\bmessage[zr]?[- ]?(?:nous|moi)\b"
    r"|(?:laissez|envoyez|ecrivez|transmettez|adressez)(?:[- ](?:nous|moi))?"
    r"\s+(?:un|une|votre)?\s*(?:message|mot)\b"
    r"|\becri(?:re|s|t|vez|vons)[- ]?(?:nous|moi)\b"
    r"|\bnous\s+ecrire\b"
    r"|\bdiscut(?:er|ez|ons)\s+(?:avec|en\s+direct|en\s+ligne)"
    r"|\bcontactez[- ]nous\s+par\s+(?:message|clavardage|chat)"
    r"|\bchat(?:s|ter|tez|tons)?\b"
    r"|\blive\s+chat\b|\bmessaging\b"
    r"|\bmessage\s+us\b|\btext\s+us\b|\bsend\s+us\s+a\s+message\b"
)

# The reason upstream's matching would misfire here. "Laissez-nous un avis sur
# notre fiche Google" is the single most common local CTA in Quebec and it
# still works, so any window that smells like reviews is dropped.
_VETO_RE = re.compile(
    r"\bavis\b|review\w*|commentaire\w*|temoignage\w*|testimonial\w*"
    r"|\betoiles?\b|\bstars?\b|rating\w*"
    r"|google\s+(?:analytics|ads|adwords|workspace|drive|agenda|calendar"
    r"|forms?|meet|chat|search\s+console|shopping|tag\s+manager|photos)"
)

# A page explaining the shutdown is not a page suffering from it. Without
# this, every blog post about the sunset lands as a critical finding, and
# Gridar publishes local-SEO articles for a living.
_ABOUT_SUNSET_RE = re.compile(
    r"\ba\s+ete\s+(?:ferme|retire|supprime|arrete|desactive|abandonne)\w*"
    r"|\bn'(?:existe|est)\s+plus\b|\bplus\s+disponible\b"
    r"|\bsunset\b|obsolete|deprec\w*"
    r"|\bno\s+longer\s+(?:available|works|supported|exists)\b"
    r"|\bwas\s+(?:shut\s+down|discontinued|retired|sunset)\b"
    r"|31\s+juillet\s+2024|july\s+31,?\s+2024|2024-07-31"
)

# A sentence end, a list bullet or a block boundary between the verb and the
# Google mention means they belong to two different ideas.
_GAP_BREAK_RE = re.compile(r"[\n.!?|>•·]")

_CALL_HISTORY_RE = re.compile(
    r"(?:historique|suivi|journal)\s+(?:des\s+|de\s+|d')?appels\s+"
    r"(?:google|de\s+(?:la\s+|notre\s+|votre\s+)?fiche\s+google)"
    r"|google\s+(?:business\s+)?call\s+history"
    r"|call\s+history\s+(?:on|in|from)\s+google"
)

_GMB_BRANDING_RE = re.compile(r"google\s+my\s+business")


# URL shapes, matched on the raw markup so hrefs, schema.org sameAs and
# JSON-LD blobs are all covered by the same pass.
_TAIL = r"[^\s\"'<>]*"

_BUSINESS_SITE_RE = re.compile(
    r"(?<![\w.-])(?:https?://)?"
    r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+business\.site(?![\w-])"
    r"(?:[/?#]" + _TAIL + r")?",
    re.IGNORECASE,
)

_WEBSITE_BUILDER_RE = re.compile(
    r"https?://business\.google\.com/" + _TAIL + r"website" + _TAIL,
    re.IGNORECASE,
)

_GOOGLE_PLUS_RE = re.compile(
    r"(?<![\w.-])(?:https?://)?plus\.google\.com(?![\w-])(?:/" + _TAIL + r")?",
    re.IGNORECASE,
)

_GMB_APP_RE = re.compile(
    r"com\.google\.android\.apps\.vega(?![\w.])"
    r"|apps\.apple\.com/" + _TAIL + r"google-my-business" + _TAIL,
    re.IGNORECASE,
)

# The separator is restricted to hyphen and underscore on the last branch so
# it only fires on class names, ids and script sources, never on the same
# words written in a sentence.
_CHAT_WIDGET_RE = re.compile(
    r"businessmessages\.googleapis\.com" + _TAIL
    + r"|https?://business\.google\.com/" + _TAIL + r"message" + _TAIL
    + r"|google[-_]business[-_]messages?",
    re.IGNORECASE,
)

_TRAILING_JUNK_RE = re.compile(
    r"(?:&quot;|&apos;|&#0?39;|&gt;|&lt;|[\s.,;:!?)\]}\"'])+$"
)

_WS_RE = re.compile(r"\s+")

_SKIP_TAGS = frozenset({'script', 'style', 'noscript', 'template', 'svg'})

# Text from two different blocks never forms one sentence, so a boundary is
# recorded and the proximity rule refuses to read across it.
_BLOCK_TAGS = frozenset({
    'address', 'article', 'aside', 'blockquote', 'br', 'dd', 'div', 'dl', 'dt',
    'fieldset', 'figcaption', 'figure', 'footer', 'form', 'h1', 'h2', 'h3',
    'h4', 'h5', 'h6', 'header', 'hr', 'li', 'main', 'nav', 'ol', 'p', 'section',
    'table', 'td', 'th', 'tr', 'ul',
})

# Attributes a visitor actually reads. A chat button is often an icon whose
# only wording lives in aria-label.
_TEXT_ATTRS = frozenset({'alt', 'title', 'aria-label', 'placeholder', 'value'})

# NFKD leaves typographic quotes and dashes alone, so they are mapped by
# hand: a page that autocorrected "ecrivez-nous" into a long dash would
# otherwise slip past every pattern here. Written as codepoints because the
# characters themselves are banned from this repository's source.
_QUOTES = {chr(code): "'" for code in (
    0x2018, 0x2019, 0x201A, 0x201B, 0x02BC, 0x2032, 0x0060,
)}
_DASHES = frozenset(chr(code) for code in (
    0x2010, 0x2011, 0x2012, 0x2013, 0x2014, 0x2015, 0x2212,
))


class _TextExtractor(HTMLParser):
    """Collect what a visitor reads: text nodes plus user-facing attributes."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag in _BLOCK_TAGS:
            self.parts.append('\n')
        for name, value in attrs:
            if value and name in _TEXT_ATTRS:
                self.parts.append('\n' + value + '\n')

    def handle_endtag(self, tag):
        if tag in _SKIP_TAGS:
            if self._skip_depth:
                self._skip_depth -= 1
            return
        if tag in _BLOCK_TAGS and not self._skip_depth:
            self.parts.append('\n')

    def handle_data(self, data):
        if not self._skip_depth:
            self.parts.append(data)


def _visible_text(markup: str) -> str:
    """Flatten markup to readable text, one space per tag boundary.

    The space matters: without it `Google</b><span>Business` folds into a
    single token and no pattern ever sees the product name.
    """
    parser = _TextExtractor()
    try:
        parser.feed(markup)
        parser.close()
    except Exception:
        # Malformed markup is the normal case on the sites being audited, so
        # whatever was parsed before the break is kept rather than discarded.
        pass
    text = ' '.join(part for part in parser.parts if part)
    if not text.strip() and markup.strip():
        text = re.sub(r'<[^>]*>', ' ', markup)
    return text


def _fold(text: str) -> tuple[str, list[int]]:
    """Lowercase, strip accents, normalize quotes, flatten whitespace.

    Returns the folded string and, for every folded character, the offset it
    came from in `text`. Patterns then stay ASCII while findings still quote
    the page verbatim, accents and all. Newlines survive the fold because the
    proximity rule reads them as block boundaries.
    """
    chars: list[str] = []
    offsets: list[int] = []
    for index, raw in enumerate(text):
        if raw.isspace():
            chars.append('\n' if raw == '\n' else ' ')
            offsets.append(index)
            continue
        char = _QUOTES.get(raw, '-' if raw in _DASHES else raw)
        for piece in unicodedata.normalize('NFKD', char):
            if unicodedata.combining(piece):
                continue
            chars.append(piece.lower())
            offsets.append(index)
    return ''.join(chars), offsets


def _origin_span(offsets: list[int], start: int, end: int) -> tuple[int, int]:
    """Map a span on the folded copy back onto the original text."""
    if not offsets:
        return 0, 0
    start = max(0, min(start, len(offsets) - 1))
    end = max(start + 1, min(end, len(offsets)))
    return offsets[start], offsets[end - 1] + 1


def _tidy(fragment: str, limit: int = 200) -> str:
    return _WS_RE.sub(' ', fragment).strip()[:limit].strip()


def _excerpt(source: str, start: int, end: int, radius: int = 60) -> str:
    low = max(0, start - radius)
    high = min(len(source), end + radius)
    body = _WS_RE.sub(' ', source[low:high]).strip()
    prefix = '...' if low > 0 else ''
    suffix = '...' if high < len(source) else ''
    return _tidy(prefix + body + suffix, 260)


def _clean_url(candidate: str) -> str:
    return _TRAILING_JUNK_RE.sub('', candidate.strip())


def _host_of(candidate: str) -> str:
    """Host of a URL that may have no scheme, without a second parse pass."""
    rest = candidate.split('://', 1)[-1]
    for separator in ('/', '?', '#'):
        rest = rest.split(separator, 1)[0]
    return rest.strip().strip('.').lower()


def _overlaps(span: tuple[int, int], claimed: list[tuple[int, int]]) -> bool:
    return any(span[0] < end and start < span[1] for start, end in claimed)


def _about_the_sunset(folded: str, start: int, end: int) -> bool:
    """True when the surrounding sentence discusses the retirement itself."""
    low = max(0, start - _PROXIMITY_WINDOW)
    high = min(len(folded), end + _PROXIMITY_WINDOW)
    return bool(_ABOUT_SUNSET_RE.search(folded[low:high]))


def _linked_messaging(folded: str, surface: re.Match) -> tuple[int, int] | None:
    """Span of a messaging CTA tied to this Google mention, if there is one.

    "Tied" means close, on the same side of any sentence end, and not part of
    a review CTA. A page saying "trouvez notre fiche Google" in one block and
    "envoyez-nous un message" in the next is not a dead chat button.
    """
    low = max(0, surface.start() - _PROXIMITY_WINDOW)
    high = min(len(folded), surface.end() + _PROXIMITY_WINDOW)
    if _VETO_RE.search(folded[low:high]):
        return None

    for verb in _MESSAGING_RE.finditer(folded, low, high):
        if verb.end() <= surface.start():
            gap = folded[verb.end():surface.start()]
        elif verb.start() >= surface.end():
            gap = folded[surface.end():verb.start()]
        else:
            gap = ''
        if len(gap) > _MAX_GAP or _GAP_BREAK_RE.search(gap):
            continue
        return min(verb.start(), surface.start()), max(verb.end(), surface.end())
    return None


def lint_gbp_references(html: str, url: str = '') -> list[dict]:
    """Report every retired Google Business feature this page still references.

    `html` is raw page source, `url` the address it came from. The URL is
    optional and only read, never fetched: it stamps each finding and catches
    the worst case, a page whose own host is a shut-down `.business.site`.
    Findings come back sorted, most severe first.
    """
    if not isinstance(html, str) or not html.strip():
        return []
    page_url = url.strip() if isinstance(url, str) else ''
    markup = html[:_MAX_HTML]

    collected: dict[tuple[str, str], dict] = {}
    per_code: dict[str, int] = {}

    def record(code, match, excerpt, source, key=None, **fields):
        match = _tidy(match)
        if not match:
            return
        index = (code, (key or match).lower())
        seen = collected.get(index)
        if seen is not None:
            seen['occurrences'] += 1
            return
        if per_code.get(code, 0) >= _MAX_PER_CODE:
            return
        per_code[code] = per_code.get(code, 0) + 1
        rule = _RULES[code]
        collected[index] = {
            'code': code,
            'severity': rule['severity'],
            'feature': rule['feature'],
            'retired_on': rule['retired_on'],
            'match': match,
            'excerpt': excerpt,
            'occurrences': 1,
            'message': rule['message'].format(**fields) if fields else rule['message'],
            'fix': rule['fix'],
            'source': source,
            'page_url': page_url,
        }

    try:
        page_host = (urlparse(page_url).hostname or '').lower()
    except ValueError:
        page_host = ''
    if page_host.endswith('.business.site'):
        record('gbp_site_on_business_site', page_host, _tidy(page_url), 'url',
               host=page_host)

    # Visible text first: these are the findings a client can check himself.
    text = _visible_text(markup)
    folded, offsets = _fold(text)
    claimed: list[tuple[int, int]] = []

    for hit in _EXPLICIT_CHAT_RE.finditer(folded):
        if _about_the_sunset(folded, *hit.span()):
            continue
        claimed.append(hit.span())
        start, end = _origin_span(offsets, *hit.span())
        record('gbp_chat_cta', text[start:end], _excerpt(text, start, end), 'texte')

    for surface in _SURFACE_RE.finditer(folded):
        span = _linked_messaging(folded, surface)
        if span is None or _overlaps(span, claimed):
            continue
        if _about_the_sunset(folded, *span):
            continue
        claimed.append(span)
        start, end = _origin_span(offsets, *span)
        record('gbp_chat_cta', text[start:end],
               _excerpt(text, start, end, radius=30), 'texte')

    for hit in _CALL_HISTORY_RE.finditer(folded):
        if _overlaps(hit.span(), claimed) or _about_the_sunset(folded, *hit.span()):
            continue
        claimed.append(hit.span())
        start, end = _origin_span(offsets, *hit.span())
        record('gbp_call_history', text[start:end], _excerpt(text, start, end),
               'texte')

    for hit in _GMB_BRANDING_RE.finditer(folded):
        # Stale wording is only worth reporting where nothing worse was found:
        # inside "Google My Business chat", the chat finding already says it.
        if _overlaps(hit.span(), claimed) or _about_the_sunset(folded, *hit.span()):
            continue
        claimed.append(hit.span())
        start, end = _origin_span(offsets, *hit.span())
        record('gmb_branding', text[start:end], _excerpt(text, start, end), 'texte')

    # Then the markup, where the dead destinations live.
    for hit in _BUSINESS_SITE_RE.finditer(markup):
        target = _clean_url(hit.group(0))
        host = _host_of(target)
        if not host or host == page_host:
            continue  # the page's own address, already reported as critical
        record('gbp_business_site_link', target, _excerpt(markup, *hit.span()),
               'html', key=host, host=host)

    for hit in _WEBSITE_BUILDER_RE.finditer(markup):
        record('gbp_website_builder_link', _clean_url(hit.group(0)),
               _excerpt(markup, *hit.span()), 'html')

    for hit in _GOOGLE_PLUS_RE.finditer(markup):
        record('google_plus_link', _clean_url(hit.group(0)),
               _excerpt(markup, *hit.span()), 'html')

    for hit in _GMB_APP_RE.finditer(markup):
        record('gmb_app_link', _clean_url(hit.group(0)),
               _excerpt(markup, *hit.span()), 'html')

    for hit in _CHAT_WIDGET_RE.finditer(markup):
        record('gbp_chat_widget', _clean_url(hit.group(0)),
               _excerpt(markup, *hit.span()), 'html')

    findings = list(collected.values())
    findings.sort(key=lambda item: SEVERITY_RANK.get(item['severity'], 9))
    return findings


def summarize_gbp_lint(findings: list[dict]) -> dict:
    """Counts per severity, for a score card or an audit header."""
    findings = findings or []
    counts = {level: 0 for level in SEVERITY_RANK}
    for finding in findings:
        level = finding.get('severity')
        if level in counts:
            counts[level] += 1
    return {
        'ok': not findings,
        'total': len(findings),
        'blocking': counts['critical'] + counts['high'],
        'counts': counts,
    }
