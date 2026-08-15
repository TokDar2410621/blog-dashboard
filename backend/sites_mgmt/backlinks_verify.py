"""Backlink verification: go read the source page and confirm the link is still there.

Porte depuis claude-seo v2.2.4 `scripts/verify_backlinks.py` et
`scripts/validate_backlink_report.py`.
Copyright (c) 2025 Daniel Agrici (AgriciDaniel). MIT.
https://github.com/AgriciDaniel/claude-seo

Four things changed for Gridar. Upstream parses with BeautifulSoup, which is
not a dependency here, so the anchors are read with a small `html.parser` pass
that also records the zone the link sits in: a link in the body copy and a link
in the site footer are not worth the same thing and a report that cannot tell
them apart is not defensible in front of a client. Upstream spaces its requests
with a module-global dict of last-hit timestamps, which is fine in a CLI and
wrong inside gunicorn, so the batch partitions the work by host instead, one
worker per domain, and politeness falls out of the partition with no shared
state. Upstream calls any 3xx "moved" and stops, which reports every backlink
of every http-to-https site as lost, so only a redirect that actually changes
the address counts here and the link is checked at the destination anyway.
Finally `validate_report` returns a flat list of findings written in French and
gains the check Gridar needs most: a count of textual mentions presented as a
count of links is refused, because that is exactly the claim the old
`task_backlinks` was making.

Every fetch goes through `url_safety.safe_get`. The source URL comes out of a
third-party report, so it is attacker-controlled by construction: a backlink
verifier is the ideal tool for making someone else's infrastructure crawl an
internal address.
"""
from __future__ import annotations

import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import requests

from .html_parse import count_words
from .url_safety import URLSafetyError, safe_get, validate_url

__all__ = [
    'ETATS',
    'LIBELLES_ETAT',
    'ZONES',
    'LIBELLES_ZONE',
    'SEVERITES',
    'PLATEFORMES_JS',
    'MAX_BYTES',
    'MAX_ANCRES',
    'DELAI_PAR_DOMAINE',
    'TIMEOUT_PAR_PAGE',
    'AGE_MAX_JOURS',
    'USER_AGENT',
    'verify_backlink',
    'verify_batch',
    'validate_report',
]


# --------------------------------------------------------------------------
# Vocabulary
# --------------------------------------------------------------------------

# Ordered from best to worst, which is the order a client reads them in.
# `redirigee` and `disparu` are both losses but they are not the same
# conversation: one says the page moved, the other says the page is still
# there and someone took the link out.
ETATS = (
    ('confirme', 'Lien confirmé'),
    ('redirigee', 'Page redirigée, lien absent de la destination'),
    ('disparu', 'Page en ligne, lien retiré'),
    ('page_absente', 'Page source introuvable'),
    ('non_verifiable', 'Page rendue en JavaScript, impossible de trancher'),
    ('injoignable', 'Page injoignable'),
    ('non_verifie', 'Non vérifié'),
)
LIBELLES_ETAT = dict(ETATS)

# States where we actually saw the page and can answer yes or no. Anything
# outside this set must never be counted as a loss: telling a client a link
# was removed when Cloudflare simply refused us is how a report loses its
# credibility for good.
_ETATS_TRANCHES = frozenset({'confirme', 'redirigee', 'disparu', 'page_absente'})
_ETATS_PERDUS = frozenset({'redirigee', 'disparu', 'page_absente'})

ZONES = (
    ('contenu', 'Contenu principal'),
    ('commentaire', 'Commentaire'),
    ('barre_laterale', 'Barre latérale'),
    ('navigation', 'Navigation'),
    ('entete', 'En-tête'),
    ('pied_de_page', 'Pied de page'),
    ('corps', 'Corps de page, hors zone identifiée'),
)
LIBELLES_ZONE = dict(ZONES)

# Ranking used to pick which link represents the page when several point at
# the target. Body copy first, boilerplate last.
_RANG_ZONE = {
    'contenu': 0,
    'corps': 1,
    'commentaire': 2,
    'barre_laterale': 3,
    'entete': 4,
    'navigation': 5,
    'pied_de_page': 6,
}

# Same vocabulary as `local_seo.SEVERITES` and `sxo.detect_mismatch`, so a
# dashboard can merge findings from all three into one sorted list.
SEVERITES = ('aucune', 'faible', 'moyenne', 'elevee', 'critique')
_RANG_SEVERITE = {nom: i for i, nom in enumerate(SEVERITES)}


# --------------------------------------------------------------------------
# Limits
# --------------------------------------------------------------------------

# A source page is served by a stranger. Three megabytes is far past any real
# article and stops a hostile host from streaming until the worker dies.
MAX_BYTES = 3 * 1024 * 1024

# Only anchors that already mention the target domain are buffered, so this
# ceiling is only reached by a page built to exhaust us.
MAX_ANCRES = 200

# One request per second to the same host. The batch enforces it by giving a
# single worker every URL of a domain, so this delay is a sleep inside one
# thread and never a lock shared between requests.
DELAI_PAR_DOMAINE = 1.0

TIMEOUT_PAR_PAGE = 15

# Past this, a verification is stale enough that showing it without the date
# beside it would be a claim about today made from old evidence.
AGE_MAX_JOURS = 90

USER_AGENT = 'GridarBacklinkVerifier/1.0 (+https://gridar.app)'

_ENTETES = {
    'User-Agent': USER_AGENT,
    'Accept': 'text/html,application/xhtml+xml;q=0.9,*/*;q=0.8',
    # Asking in French matters on Quebec sites that serve a different variant
    # per language: the anchor a client sees is the one on the French page.
    'Accept-Language': 'fr-CA,fr;q=0.9,en;q=0.6',
}

# Hosts whose public pages are assembled in the browser. Their HTML carries no
# outbound anchors, so "link not found" there means "not visible to a crawler",
# never "link removed". Upstream only caught this after the fact, in the report
# validator; it is caught at the source here.
PLATEFORMES_JS = frozenset({
    'instagram.com',
    'facebook.com',
    'twitter.com',
    'x.com',
    'tiktok.com',
    'linkedin.com',
    'pinterest.com',
    'youtube.com',
    'threads.net',
    'reddit.com',
    'notion.site',
})

# Markers of a client-rendered shell. Upstream treats any of them as proof the
# page is unverifiable, which mislabels every server-rendered Next.js blog;
# here a marker only counts when the visible text is genuinely thin.
_MARQUEURS_JS = (
    '<div id="root"',
    "<div id='root'",
    '<div id="app"',
    "<div id='app'",
    '<div id="__next"',
    '__next_data__',
    '__nuxt',
    'ng-app=',
    'ng-version=',
    'data-reactroot',
    'data-svelte',
)
_MOTS_SI_MARQUEUR = 200
_MOTS_SI_COQUILLE = 50
_TAILLE_COQUILLE = 5000


# --------------------------------------------------------------------------
# HTML parsing
# --------------------------------------------------------------------------

# The spec gives these no end tag, so a stray closing form must not unwind the
# stack under them.
_VOID = frozenset({
    'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link',
    'meta', 'param', 'source', 'track', 'wbr',
})

# Text in here never reaches a reader, so it never reaches the word count that
# decides whether the page is a JavaScript shell.
_TAGS_INVISIBLES = frozenset({
    'head', 'title', 'script', 'style', 'noscript', 'template', 'svg',
    'iframe', 'object', 'canvas', 'select', 'option', 'datalist',
})

# Anchors declared in here are markup, not links: a `<template>` is never
# rendered and an `<svg>` `<a>` is an icon.
_TAGS_NON_RENDUS = frozenset({'template', 'svg', 'head'})

# Crossing any other boundary separates two words. Kept local rather than
# imported from html_parse, whose copy is private.
_TAGS_INLINE = frozenset({
    'a', 'abbr', 'b', 'bdi', 'bdo', 'cite', 'code', 'data', 'del', 'dfn',
    'em', 'font', 'i', 'ins', 'kbd', 'label', 'mark', 'q', 'rp', 'rt',
    'ruby', 's', 'samp', 'small', 'span', 'strong', 'sub', 'sup', 'time',
    'tt', 'u', 'var',
})

_TAGS_ZONE = {
    'footer': 'pied_de_page',
    'nav': 'navigation',
    'aside': 'barre_laterale',
    'header': 'entete',
    'main': 'contenu',
    'article': 'contenu',
}
_TAGS_PRINCIPAL = frozenset({'main', 'article'})
_ZONES_CHROME = frozenset({
    'commentaire', 'pied_de_page', 'navigation', 'barre_laterale', 'entete',
})

# Most themes still ship `<div id="footer">` instead of `<footer>`, so the tag
# alone misses the majority of footer links. Tested in order, first match wins,
# chrome before content. French tokens are listed because Quebec agencies hand
# their custom themes French class names.
_MOTS_ZONE = (
    ('commentaire', ('comment', 'commentaire', 'disqus', 'respond', 'avis-client')),
    ('pied_de_page', ('footer', 'pied-de-page', 'pied-page', 'colophon', 'site-info')),
    ('navigation', ('navbar', 'navigation', 'nav-', '-nav', 'menu', 'breadcrumb',
                    'fil-ariane', 'ariane')),
    ('barre_laterale', ('sidebar', 'widget', 'barre-laterale', 'secondary', 'aside')),
    ('entete', ('header', 'masthead', 'en-tete', 'entete', 'banner')),
    ('contenu', ('entry-content', 'post-content', 'article-body', 'article-content',
                 'page-content', 'post-body', 'contenu', 'texte-article')),
)

_TAGS_ATTRS = frozenset({'base', 'a', 'div', 'section', 'article', 'footer',
                         'header', 'nav', 'aside', 'main', 'ul', 'li', 'p'})
_SANS_ATTRS = {}

_MAX_ANCRE = 200
_MAX_TEXTE = 20000
_WS_RE = re.compile(r'\s+')
_SCHEME_RE = re.compile(r'^[a-z][a-z0-9+.\-]*:', re.IGNORECASE)
_META_CHARSET_RE = re.compile(
    rb'''<meta[^>]+charset\s*=\s*["']?\s*([a-zA-Z0-9_\-]+)''', re.IGNORECASE,
)
_ID_SEP_RE = re.compile(r'[\s_]+')


def _premier_gagne(attrs) -> dict:
    """First value wins on a duplicated attribute, like a browser."""
    out = {}
    for nom, valeur in attrs:
        cle = nom.lower()
        if cle not in out:
            out[cle] = valeur if valeur is not None else ''
    return out


def _identifiants(attrs: dict) -> str:
    """Class list and id flattened into one hyphen-separated haystack."""
    brut = f"{attrs.get('class', '') or ''} {attrs.get('id', '') or ''}"
    if not brut.strip():
        return ''
    return _ID_SEP_RE.sub('-', brut.strip().lower())


def _zone_par_classe(attrs: dict):
    ident = _identifiants(attrs)
    if not ident:
        return None
    for zone, mots in _MOTS_ZONE:
        for mot in mots:
            if mot in ident:
                return zone
    return None


def _zone_element(tag: str, attrs: dict):
    """Zone this single element declares, or None when it declares nothing."""
    zone_tag = _TAGS_ZONE.get(tag)
    zone_classe = _zone_par_classe(attrs) if attrs else None
    # A chrome container wraps content containers all the time and the reverse
    # never happens, so chrome wins whenever the two disagree.
    for zone in (zone_classe, zone_tag):
        if zone in _ZONES_CHROME:
            return zone
    return zone_classe or zone_tag


class _Cadre:
    """One open element: what it is, what zone it declares, is its text seen."""

    __slots__ = ('tag', 'zone', 'invisible', 'ancre')

    def __init__(self, tag, zone, invisible):
        self.tag = tag
        self.zone = zone
        self.invisible = invisible
        self.ancre = None


class _AncreParser(HTMLParser):
    """One pass collecting anchors that may point at the target domain.

    Only anchors whose raw href already mentions the target are buffered, so a
    page with 800 links costs almost nothing. Enough visible text is kept to
    tell a real page from a JavaScript shell, and no more.
    """

    def __init__(self, formes_cible):
        super().__init__(convert_charrefs=True)
        self._formes = tuple(f for f in formes_cible if f)
        self._pile = []
        self._ouvertes = []
        self.base_href = None
        self.ancres = []
        self.texte = []
        self._texte_len = 0

    # -- helpers -----------------------------------------------------------

    def _invisible_now(self) -> bool:
        return self._pile[-1].invisible if self._pile else False

    def _hors_rendu(self) -> bool:
        return any(cadre.tag in _TAGS_NON_RENDUS for cadre in self._pile)

    def _separateur(self, tag: str) -> None:
        if tag in _TAGS_INLINE:
            return
        for cadre in self._ouvertes:
            cadre.ancre['buf'].append(' ')
        if not self._invisible_now() and self._texte_len < _MAX_TEXTE:
            self.texte.append(' ')
            self._texte_len += 1

    def _candidat(self, href: str) -> bool:
        """Cheap pre-filter run before any buffering.

        A relative href can only point at the page's own host, unless a
        `<base href>` on the target domain rewrites it, which is why the base
        is read first and the relative case is kept only then.
        """
        h = href.strip().lower()
        if not h or h.startswith('#'):
            return False
        scheme = _SCHEME_RE.match(h)
        if scheme and scheme.group(0) not in ('http:', 'https:'):
            return False
        if any(forme in h for forme in self._formes):
            return True
        if self.base_href and not scheme and not h.startswith('//'):
            base = self.base_href.lower()
            return any(forme in base for forme in self._formes)
        return False

    def _zone_courante(self) -> str:
        """Nearest labelled ancestor decides, chrome outranking content.

        A `<header>` or `<footer>` nested inside `<main>` or `<article>` is the
        entry header or the tag list of one post, not the site chrome, so it is
        skipped there. Same rule as `html_parse`, which is what keeps the two
        modules from disagreeing about the same page.
        """
        dans_principal = any(c.tag in _TAGS_PRINCIPAL for c in self._pile)
        contenu = False
        for cadre in reversed(self._pile):
            if cadre.zone is None:
                continue
            if cadre.zone in _ZONES_CHROME:
                if dans_principal and cadre.tag in ('header', 'footer'):
                    continue
                return cadre.zone
            contenu = True
        return 'contenu' if contenu else 'corps'

    def _fermer_ancre(self, cadre) -> None:
        ancre = cadre.ancre
        cadre.ancre = None
        try:
            self._ouvertes.remove(cadre)
        except ValueError:
            pass
        texte = _WS_RE.sub(' ', ''.join(ancre['buf'])).strip()
        self.ancres.append({
            'href': ancre['href'],
            'rel': ancre['rel'],
            'zone': ancre['zone'],
            'texte': texte[:_MAX_ANCRE],
        })

    # -- HTMLParser hooks --------------------------------------------------

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        a = _premier_gagne(attrs) if tag in _TAGS_ATTRS else _SANS_ATTRS
        self._separateur(tag)

        if tag == 'base':
            href = (a.get('href') or '').strip()
            if href and not self.base_href:
                self.base_href = href
        if tag in _VOID:
            return

        # A new `<a>` closes the one in scope: nesting anchors is invalid and
        # browsers do the same, so the inner text stops belonging to both.
        if tag == 'a' and self._ouvertes:
            self._fermer_ancre(self._ouvertes[-1])

        invisible = self._invisible_now() or tag in _TAGS_INVISIBLES
        cadre = _Cadre(tag, _zone_element(tag, a), invisible)
        self._pile.append(cadre)

        if tag != 'a' or len(self.ancres) >= MAX_ANCRES:
            return
        href = (a.get('href') or '').strip()
        if not href or not self._candidat(href) or self._hors_rendu():
            return
        cadre.ancre = {
            'href': href,
            'rel': a.get('rel') or '',
            'zone': self._zone_courante(),
            'buf': [],
            'len': 0,
        }
        self._ouvertes.append(cadre)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in _VOID:
            return
        self._separateur(tag)
        for i in range(len(self._pile) - 1, -1, -1):
            if self._pile[i].tag != tag:
                continue
            for cadre in self._pile[i:]:
                if cadre.ancre is not None:
                    self._fermer_ancre(cadre)
            del self._pile[i:]
            return
        # Stray end tag with nothing open to match: ignored, the way a browser
        # ignores it. Unwinding on it would drop the whole document.

    def handle_data(self, data):
        if not data:
            return
        for cadre in self._ouvertes:
            ancre = cadre.ancre
            if ancre['len'] < _MAX_ANCRE * 4:
                ancre['buf'].append(data)
                ancre['len'] += len(data)
        if not self._invisible_now() and self._texte_len < _MAX_TEXTE:
            self.texte.append(data)
            self._texte_len += len(data)

    def finaliser(self):
        """Close what the document left open, then hand back the anchors."""
        for cadre in list(self._ouvertes):
            self._fermer_ancre(cadre)
        self._pile = []


# --------------------------------------------------------------------------
# URL and domain helpers
# --------------------------------------------------------------------------

def _sans_www(hote: str) -> str:
    return hote[4:] if hote.startswith('www.') else hote


def _normalise_domaine(valeur) -> str:
    """Accept a bare domain or a full URL, give back the bare lowercase host."""
    if not isinstance(valeur, str):
        return ''
    texte = valeur.strip().lower()
    if not texte:
        return ''
    if '//' not in texte:
        texte = '//' + texte
    try:
        hote = urlparse(texte).hostname or ''
    except ValueError:
        return ''
    hote = hote.strip().rstrip('.')
    return _sans_www(hote)


def _formes_domaine(domaine: str) -> tuple:
    """The domain plus its punycode form, both lowercase.

    A `.ca` domain written with accents reaches the HTML as `xn--...`, so a
    match on the unicode spelling alone would miss its own backlinks.
    """
    if not domaine:
        return ()
    formes = [domaine]
    try:
        ascii_forme = domaine.encode('idna').decode('ascii').lower()
    except (UnicodeError, ValueError):
        ascii_forme = ''
    if ascii_forme and ascii_forme != domaine:
        formes.append(ascii_forme)
    return tuple(formes)


def _hote(url: str) -> str:
    try:
        return _sans_www((urlparse(url).hostname or '').lower().rstrip('.'))
    except ValueError:
        return ''


def _appartient(hote: str, domaine: str) -> str:
    """'exact', 'sous_domaine' or '' for a host against a target domain."""
    if not hote or not domaine:
        return ''
    for forme in _formes_domaine(domaine):
        if hote == forme:
            return 'exact'
        if hote.endswith('.' + forme):
            return 'sous_domaine'
    return ''


def _cle_url(url: str) -> str:
    """Comparison key: scheme, www, trailing slash and fragment dropped.

    http and https collapse on purpose. A report listing both spellings of one
    page is listing one link twice, and counting it twice is the inflation
    `validate_report` exists to catch.
    """
    try:
        p = urlparse((url or '').strip())
    except ValueError:
        return (url or '').strip().lower()
    hote = _sans_www((p.hostname or '').lower().rstrip('.'))
    chemin = (p.path or '/').rstrip('/') or '/'
    cle = hote + chemin
    if p.query:
        cle += '?' + p.query
    return cle


def _resoudre(href: str, base: str) -> str:
    try:
        return urljoin(base, href.strip())
    except ValueError:
        return ''


def _plateforme_js(hote: str) -> bool:
    return any(
        hote == p or hote.endswith('.' + p) for p in PLATEFORMES_JS
    )


def _maintenant() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _date_iso(valeur):
    """Parse an ISO 8601 stamp, tolerating the trailing Z Python 3.10 refuses."""
    if not isinstance(valeur, str) or not valeur.strip():
        return None
    texte = valeur.strip()
    if texte.endswith('Z'):
        texte = texte[:-1] + '+00:00'
    try:
        moment = datetime.fromisoformat(texte)
    except ValueError:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment


# --------------------------------------------------------------------------
# Fetching
# --------------------------------------------------------------------------

def _lire(reponse, max_bytes: int):
    """Read the body with a ceiling, so a hostile host cannot stream forever."""
    morceaux = []
    taille = 0
    for morceau in reponse.iter_content(chunk_size=65536):
        if not morceau:
            continue
        morceaux.append(morceau)
        taille += len(morceau)
        if taille >= max_bytes:
            return b''.join(morceaux)[:max_bytes], True
    return b''.join(morceaux), False


def _decoder(brut: bytes, content_type: str) -> str:
    """Decode using the declared charset, falling back to the meta tag.

    requests defaults `text/*` without a charset to ISO-8859-1, which turns
    every accented anchor into mojibake. The anchor text is half of what this
    module sells, so the charset is resolved here instead.
    """
    charset = ''
    for morceau in (content_type or '').split(';'):
        morceau = morceau.strip()
        if morceau.lower().startswith('charset='):
            charset = morceau.split('=', 1)[1].strip().strip('"\'')
    if not charset:
        trouve = _META_CHARSET_RE.search(brut[:4096])
        if trouve:
            charset = trouve.group(1).decode('ascii', 'ignore')
    for candidat in (charset, 'utf-8'):
        if not candidat:
            continue
        try:
            return brut.decode(candidat, errors='replace')
        except LookupError:
            continue
    return brut.decode('utf-8', errors='replace')


def _redirection(url_demandee: str, url_finale: str):
    """Report a redirect only when it actually changes where the page lives.

    http to https, www to bare and a trailing slash are the same address as
    far as a backlink is concerned. Upstream flags them all, which reports
    every link on every modernised site as moved.
    """
    if not url_finale or _cle_url(url_finale) == _cle_url(url_demandee):
        return None
    return {
        'url_finale': url_finale,
        'meme_domaine': _hote(url_finale) == _hote(url_demandee),
    }


# --------------------------------------------------------------------------
# Result shaping
# --------------------------------------------------------------------------

def _resultat(url_source: str, domaine_cible: str, verifie_le: str,
              etat: str, **extra) -> dict:
    """Every result carries the same keys, whatever went wrong."""
    hote = _hote(url_source)
    out = {
        'url_source': url_source,
        'domaine_source': hote,
        'domaine_cible': domaine_cible,
        'auto_reference': bool(hote and _appartient(hote, domaine_cible)),
        'etat': etat,
        'libelle_etat': LIBELLES_ETAT.get(etat, etat),
        'lien_present': None,
        'statut_http': None,
        'redirection': None,
        'ancre': None,
        'rel': [],
        'nofollow': None,
        'sponsorise': None,
        'ugc': None,
        'suivi': None,
        'zone': None,
        'libelle_zone': None,
        'nb_liens': 0,
        'liens': [],
        'page_tronquee': False,
        'verifie_le': verifie_le,
        'erreur': None,
        'code_erreur': None,
    }
    out.update(extra)
    return out


def _rel_tokens(brut) -> list:
    if isinstance(brut, (list, tuple)):
        valeurs = brut
    else:
        valeurs = str(brut or '').replace(',', ' ').split()
    vus, out = set(), []
    for jeton in valeurs:
        jeton = str(jeton).strip().lower()
        if jeton and jeton not in vus:
            vus.add(jeton)
            out.append(jeton)
    return out


def _liens_vers_cible(ancres: list, base: str, domaine: str) -> list:
    """Keep the anchors that really resolve onto the target domain."""
    out = []
    for ancre in ancres:
        resolu = _resoudre(ancre['href'], base)
        if not resolu:
            continue
        try:
            parsed = urlparse(resolu)
        except ValueError:
            continue
        if (parsed.scheme or '').lower() not in ('http', 'https'):
            continue
        correspondance = _appartient(_sans_www((parsed.hostname or '').lower()), domaine)
        if not correspondance:
            continue
        rel = _rel_tokens(ancre['rel'])
        nofollow = 'nofollow' in rel
        sponsorise = 'sponsored' in rel
        ugc = 'ugc' in rel
        out.append({
            'href': resolu,
            'ancre': ancre['texte'],
            'rel': rel,
            'nofollow': nofollow,
            'sponsorise': sponsorise,
            'ugc': ugc,
            'suivi': not (nofollow or sponsorise or ugc),
            'zone': ancre['zone'],
            'libelle_zone': LIBELLES_ZONE.get(ancre['zone'], ancre['zone']),
            'correspondance': correspondance,
        })
    return out


def _meilleur(liens: list) -> dict:
    """The link that represents the page: body copy first, followed first."""
    return min(
        liens,
        key=lambda l: (_RANG_ZONE.get(l['zone'], 9), 0 if l['suivi'] else 1),
    )


def _coquille_js(doc: str, mots: int, hote: str) -> bool:
    """Is the absence of the link explained by client-side rendering?"""
    if _plateforme_js(hote):
        return True
    if len(doc) > _TAILLE_COQUILLE and mots < _MOTS_SI_COQUILLE:
        return True
    if mots >= _MOTS_SI_MARQUEUR:
        return False
    tete = doc[:200000].lower()
    return any(marqueur in tete for marqueur in _MARQUEURS_JS)


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------

def verify_backlink(source_url: str, target_domain: str, *,
                    timeout: int = 15) -> dict:
    """Fetch one source page and confirm it still links to the target domain.

    Args:
        source_url: the page a third-party report says holds the link. It comes
            from a stranger, so it is fetched through `url_safety.safe_get` and
            never with a bare `requests.get`.
        target_domain: the domain the link should point at. A full URL works
            too, only its host is kept. Subdomains of the target count as a
            match, and www is ignored on both sides.
        timeout: per-request timeout in seconds.

    Returns:
        {
          'etat': one of ETATS, 'libelle_etat': its French label,
          'lien_present': True / False / None when nobody could look,
          'ancre', 'rel', 'nofollow', 'sponsorise', 'ugc', 'suivi',
          'zone' + 'libelle_zone': where the link sits on the page,
          'liens': every anchor found pointing at the target, document order,
          'nb_liens', 'statut_http', 'redirection', 'auto_reference',
          'page_tronquee', 'verifie_le': the ISO 8601 UTC stamp of this check,
          'erreur', 'code_erreur': French text and a stable code.
        }

    Never raises: a verifier that dies on one hostile page takes the whole
    batch down with it.
    """
    verifie_le = _maintenant()
    cible = _normalise_domaine(target_domain)
    url = source_url.strip() if isinstance(source_url, str) else ''

    if not cible:
        return _resultat(url, '', verifie_le, 'non_verifie',
                         erreur="Domaine cible manquant ou illisible.",
                         code_erreur='domaine_invalide')
    if not url:
        return _resultat(url, cible, verifie_le, 'non_verifie',
                         erreur="URL source manquante.",
                         code_erreur='url_invalide')
    if not validate_url(url):
        return _resultat(
            url, cible, verifie_le, 'injoignable',
            erreur=("URL refusée par le contrôle de sécurité "
                    "(adresse interne, schéma non HTTP ou format suspect)."),
            code_erreur='url_refusee')

    try:
        reponse = safe_get(url, timeout=timeout, headers=_ENTETES, stream=True)
    except URLSafetyError:
        return _resultat(
            url, cible, verifie_le, 'injoignable',
            erreur=("URL refusée par le contrôle de sécurité "
                    "(redirection vers une adresse interne)."),
            code_erreur='url_refusee')
    except requests.exceptions.Timeout:
        return _resultat(url, cible, verifie_le, 'injoignable',
                         erreur=f"Délai de {timeout} s dépassé.",
                         code_erreur='timeout')
    except requests.exceptions.RequestException:
        return _resultat(url, cible, verifie_le, 'injoignable',
                         erreur="Requête impossible (DNS, TLS ou connexion refusée).",
                         code_erreur='reseau')

    try:
        statut = getattr(reponse, 'status_code', None)
        entetes = getattr(reponse, 'headers', None) or {}
        url_finale = getattr(reponse, 'url', url) or url
        brut, tronquee = _lire(reponse, MAX_BYTES)
    except requests.exceptions.RequestException:
        return _resultat(url, cible, verifie_le, 'injoignable',
                         erreur="Lecture de la page interrompue.",
                         code_erreur='reseau')
    finally:
        try:
            reponse.close()
        except Exception:
            pass

    redirection = _redirection(url, url_finale)
    commun = {
        'statut_http': statut,
        'redirection': redirection,
        'page_tronquee': tronquee,
    }

    if statut is None or statut >= 500:
        detail = (f"Le serveur a répondu {statut}." if statut
                  else "Réponse illisible.")
        return _resultat(url, cible, verifie_le, 'injoignable',
                         erreur=detail, code_erreur='serveur', **commun)
    if statut in (401, 403, 429):
        # Blocked, not gone. Reporting this as a lost link is the single most
        # expensive mistake this module can make in front of a client.
        return _resultat(
            url, cible, verifie_le, 'injoignable',
            erreur=("Accès refusé par le site source "
                    f"(HTTP {statut}, protection anti-robot probable)."),
            code_erreur='acces_refuse', **commun)
    if 400 <= statut < 500:
        return _resultat(url, cible, verifie_le, 'page_absente',
                         lien_present=False,
                         erreur=f"La page source répond {statut}.",
                         code_erreur='page_absente', **commun)
    if statut >= 300:
        # safe_get walks redirects itself, so a 3xx surfacing here means the
        # chain broke: no Location header to follow.
        return _resultat(url, cible, verifie_le, 'injoignable',
                         erreur=f"Redirection incomplète (HTTP {statut}).",
                         code_erreur='redirection_cassee', **commun)

    doc = _decoder(brut, entetes.get('Content-Type', '') or '')
    parser = _AncreParser(_formes_domaine(cible))
    try:
        parser.feed(doc)
    except Exception:
        # A malformed page still carries the anchors parsed so far, and those
        # are the evidence; refusing to answer would be worse than partial.
        pass
    finally:
        try:
            parser.close()
        except Exception:
            pass
        parser.finaliser()

    # `<base href>` wins over the fetch URL for resolution, and is itself
    # allowed to be relative to it.
    base = url_finale
    if parser.base_href:
        base = _resoudre(parser.base_href, url_finale) or url_finale
    liens = _liens_vers_cible(parser.ancres, base, cible)

    if liens:
        meilleur = _meilleur(liens)
        etat = 'confirme'
        return _resultat(
            url, cible, verifie_le, etat,
            lien_present=True,
            ancre=meilleur['ancre'] or None,
            rel=meilleur['rel'],
            nofollow=meilleur['nofollow'],
            sponsorise=meilleur['sponsorise'],
            ugc=meilleur['ugc'],
            suivi=meilleur['suivi'],
            zone=meilleur['zone'],
            libelle_zone=meilleur['libelle_zone'],
            nb_liens=len(liens),
            liens=liens,
            **commun)

    mots = count_words(_WS_RE.sub(' ', ''.join(parser.texte)))
    if _coquille_js(doc, mots, _hote(url_finale) or _hote(url)):
        return _resultat(
            url, cible, verifie_le, 'non_verifiable',
            erreur=("Page assemblée en JavaScript: le lien peut exister sans "
                    "figurer dans le HTML servi."),
            code_erreur='rendu_js', **commun)
    if redirection:
        return _resultat(
            url, cible, verifie_le, 'redirigee',
            lien_present=False,
            erreur=("La page source redirige vers "
                    f"{redirection['url_finale']}, qui ne contient aucun lien "
                    "vers le domaine cible."),
            code_erreur='redirigee', **commun)
    return _resultat(url, cible, verifie_le, 'disparu', lien_present=False,
                     **commun)


def _url_de(entree):
    """Pull the source URL out of whatever shape a report uses."""
    if isinstance(entree, str):
        return entree.strip()
    if not isinstance(entree, dict):
        return ''
    for cle in ('url_source', 'source_url', 'url_from', 'referring_page',
                'url', 'from', 'page'):
        valeur = entree.get(cle)
        if isinstance(valeur, str) and valeur.strip():
            return valeur.strip()
    return ''


def verify_batch(links, target_domain, *, max_workers: int = 4,
                 time_budget: float = 120.0) -> dict:
    """Verify a batch of backlinks under a global wall-clock budget.

    Args:
        links: list of source URLs, or of dicts carrying one under any of the
            usual export keys (`url_source`, `source_url`, `url_from`, `url`).
            Ahrefs and Majestic exports both land here without a converter.
        target_domain: the domain every link should point at.
        max_workers: threads. Capped by the number of distinct source domains,
            because the work is partitioned by domain: one worker owns a host
            and walks its URLs one second apart, which is how politeness is
            enforced without a lock shared across web requests.
        time_budget: seconds for the whole batch. Whatever is left over when it
            runs out is returned as `non_verifie` rather than silently dropped,
            since a missing line reads as a lost link.

    Returns:
        {'domaine_cible', 'verifie_le', 'resultats', 'resume', 'doublons',
         'duree_s', 'budget_epuise'}

    Duplicated URLs are verified once and listed in `doublons`: fetching the
    same page twice would inflate the count the same way the report it came
    from probably already does.
    """
    debut = time.monotonic()
    verifie_le = _maintenant()
    cible = _normalise_domaine(target_domain)

    soumis = list(links or [])
    uniques, doublons, vus = [], [], set()
    for entree in soumis:
        url = _url_de(entree)
        if not url:
            continue
        cle = _cle_url(url)
        if cle in vus:
            doublons.append(url)
            continue
        vus.add(cle)
        uniques.append(url)

    if not cible:
        resultats = [
            _resultat(url, '', verifie_le, 'non_verifie',
                      erreur="Domaine cible manquant ou illisible.",
                      code_erreur='domaine_invalide')
            for url in uniques
        ]
        return _rapport_lot(cible, verifie_le, resultats, doublons,
                            len(soumis), debut, False)

    groupes = {}
    for url in uniques:
        groupes.setdefault(_hote(url) or url.lower(), []).append(url)

    echeance = debut + max(0.0, float(time_budget or 0.0))
    epuise = {'oui': False}

    def _traiter(urls):
        out = []
        premier = True
        for url in urls:
            restant = echeance - time.monotonic()
            if restant <= 0:
                epuise['oui'] = True
                out.append(_resultat(
                    url, cible, _maintenant(), 'non_verifie',
                    erreur="Budget de temps du lot épuisé avant cette page.",
                    code_erreur='budget_epuise'))
                continue
            if not premier and DELAI_PAR_DOMAINE > 0:
                # Same host, so we wait rather than hammer it.
                time.sleep(min(DELAI_PAR_DOMAINE, restant))
                restant = echeance - time.monotonic()
                if restant <= 0:
                    epuise['oui'] = True
                    out.append(_resultat(
                        url, cible, _maintenant(), 'non_verifie',
                        erreur="Budget de temps du lot épuisé avant cette page.",
                        code_erreur='budget_epuise'))
                    continue
            premier = False
            timeout = max(1, int(min(TIMEOUT_PAR_PAGE, restant)))
            out.append(verify_backlink(url, cible, timeout=timeout))
        return out

    par_url = {}
    if groupes:
        ouvriers = max(1, min(int(max_workers or 1), len(groupes)))
        with ThreadPoolExecutor(max_workers=ouvriers) as pool:
            for lot in pool.map(_traiter, list(groupes.values())):
                for resultat in lot:
                    par_url[_cle_url(resultat['url_source'])] = resultat

    # Input order is what the caller reads, so the parallel results are put
    # back in it instead of in completion order.
    resultats = [par_url[_cle_url(url)] for url in uniques if _cle_url(url) in par_url]
    return _rapport_lot(cible, verifie_le, resultats, doublons, len(soumis),
                        debut, epuise['oui'])


def _rapport_lot(cible, verifie_le, resultats, doublons, soumis, debut,
                 epuise) -> dict:
    par_etat = {cle: 0 for cle, _ in ETATS}
    domaines = set()
    suivis = nofollow = contenu = 0
    for r in resultats:
        etat = r.get('etat', 'non_verifie')
        par_etat[etat] = par_etat.get(etat, 0) + 1
        if etat != 'confirme':
            continue
        if r.get('domaine_source'):
            domaines.add(r['domaine_source'])
        if r.get('suivi'):
            suivis += 1
        else:
            nofollow += 1
        if r.get('zone') == 'contenu':
            contenu += 1

    total = len(resultats)
    confirmes = par_etat.get('confirme', 0)
    perdus = sum(par_etat.get(e, 0) for e in _ETATS_PERDUS)
    tranches = confirmes + perdus
    return {
        'domaine_cible': cible,
        'verifie_le': verifie_le,
        'resultats': resultats,
        'doublons': doublons,
        'duree_s': round(time.monotonic() - debut, 2),
        'budget_epuise': bool(epuise),
        'resume': {
            'soumis': soumis,
            'total': total,
            'doublons_ignores': len(doublons),
            'confirmes': confirmes,
            'perdus': perdus,
            'injoignables': par_etat.get('injoignable', 0),
            'non_verifiables': par_etat.get('non_verifiable', 0),
            'non_verifies': par_etat.get('non_verifie', 0),
            'par_etat': par_etat,
            'domaines_referents': len(domaines),
            'liens_suivis': suivis,
            'liens_nofollow': nofollow,
            'liens_contenu': contenu,
            # Share of the links we could actually look at that are still
            # there. None when nothing was verifiable, because 0 % would read
            # as "everything is gone" when the truth is "nobody could look".
            'taux_confirmation': (
                round(confirmes * 100.0 / tranches, 1) if tranches else None
            ),
            'couverture': round(tranches * 100.0 / total, 1) if total else 0.0,
        },
    }


# --------------------------------------------------------------------------
# Report validation
# --------------------------------------------------------------------------

_CLES_LISTE = ('resultats', 'liens', 'backlinks', 'results', 'links')
_CLES_RESUME = ('resume', 'summary')
_CLES_CIBLE = ('domaine_cible', 'target_domain', 'domain', 'domaine', 'site')
_CLES_TOTAL = ('total', 'total_backlinks', 'total_liens', 'nb_backlinks',
               'nb_liens', 'total_links')
_CLES_DOMAINES = ('domaines_referents', 'total_referring_domains',
                  'referring_domains', 'nb_domaines_referents')
_CLES_SCORE = ('score', 'note', 'sous_score', 'health_score', 'autorite',
               'verdict', 'score_backlinks')


def _signalement(code, severite, champ, constat, correction, **donnees) -> dict:
    return {
        'code': code,
        'severite': severite,
        'champ': champ,
        'constat': constat,
        'correction': correction,
        'donnees': donnees,
    }


def _liste_du_rapport(rapport: dict):
    for cle in _CLES_LISTE:
        valeur = rapport.get(cle)
        if isinstance(valeur, list):
            entrees = []
            for element in valeur:
                if isinstance(element, dict):
                    entrees.append(element)
                elif isinstance(element, str):
                    entrees.append({'url_source': element})
            return cle, entrees, len(valeur)
    return '', [], None


def _premier(rapport: dict, cles):
    for cle in cles:
        if cle in rapport and rapport[cle] is not None:
            return cle, rapport[cle]
    return '', None


def _entier(valeur):
    if isinstance(valeur, bool) or not isinstance(valeur, (int, float)):
        return None
    return int(valeur)


def validate_report(report) -> list:
    """Read a backlink report before it is shown and return what is wrong with it.

    Takes the output of `verify_batch` or any third-party report carrying a
    list of links, and catches the findings that would embarrass whoever
    presents it: the same link counted twice, a referring domain that is the
    audited domain itself, a total that does not match its own list, a summary
    that contradicts its own results, a stale or missing verification date, and
    a claim with no per-link evidence under it.

    Returns:
        A list of {'code', 'severite' (see SEVERITES), 'champ', 'constat',
        'correction', 'donnees'}, most severe first. Empty means the report can
        be shown as it stands.

    Never raises, whatever shape the input has: this runs on the presentation
    path, and a validator that crashes takes down the report it was protecting.
    """
    if not isinstance(report, dict):
        return [_signalement(
            'rapport_illisible', 'critique', '',
            "Le rapport n'est pas un objet exploitable, aucune vérification n'a pu être faite.",
            "Fournir un rapport sous forme de dictionnaire avec sa liste de liens.",
            type_recu=type(report).__name__)]

    cle_liste, entrees, longueur = _liste_du_rapport(report)
    _, cible_brute = _premier(report, _CLES_CIBLE)
    cible = _normalise_domaine(cible_brute)
    resume = None
    for cle in _CLES_RESUME:
        if isinstance(report.get(cle), dict):
            resume = report[cle]
            break

    signalements = []
    signalements += _c_doublons(entrees, cle_liste)
    signalements += _c_auto_reference(entrees, cle_liste, cible)
    signalements += _c_urls_refusees(entrees, cle_liste)
    signalements += _c_totaux(report, entrees, longueur, cle_liste)
    signalements += _c_resume(report, entrees, resume)
    signalements += _c_coherence_etats(entrees, cle_liste)
    signalements += _c_dates(entrees, cle_liste)
    signalements += _c_mentions(report)
    signalements += _c_sans_preuve(report, entrees, cible)

    signalements.sort(
        key=lambda s: (-_RANG_SEVERITE.get(s['severite'], 0), s['code'], s['champ'])
    )
    return signalements


def _c_doublons(entrees, cle_liste) -> list:
    """The same source page listed twice is the same link counted twice."""
    compte = {}
    for entree in entrees:
        url = _url_de(entree)
        if not url:
            continue
        compte.setdefault(_cle_url(url), []).append(url)

    out = []
    for cle, urls in compte.items():
        if len(urls) < 2:
            continue
        formes = sorted(set(urls))
        detail = (" (deux écritures de la même adresse: "
                  + ", ".join(formes[:3]) + ")") if len(formes) > 1 else ""
        out.append(_signalement(
            'doublon', 'elevee', f'{cle_liste}[{cle}]',
            f"L'adresse {urls[0]} figure {len(urls)} fois dans la liste{detail}: "
            f"le total est gonflé de {len(urls) - 1} lien(s).",
            "Dédupliquer sur l'URL normalisée (sans schéma, sans www, sans "
            "barre finale) avant de compter.",
            occurrences=len(urls), formes=formes))
    return out


def _c_auto_reference(entrees, cle_liste, cible) -> list:
    """A link from the audited domain to itself is an internal link."""
    if not cible:
        return []
    out = []
    vus = set()
    for i, entree in enumerate(entrees):
        url = _url_de(entree)
        hote = _hote(url) if url else _normalise_domaine(
            entree.get('domaine_source') or entree.get('source_domain') or '')
        if not hote or hote in vus:
            continue
        if not _appartient(hote, cible):
            continue
        vus.add(hote)
        out.append(_signalement(
            'auto_reference', 'critique', f'{cle_liste}[{i}]',
            f"Le domaine référent {hote} est le domaine analysé lui-même: "
            "c'est un lien interne, pas un backlink.",
            "Retirer ces lignes de la liste et recalculer le nombre de "
            "domaines référents.",
            domaine=hote, url=url))
    return out


def _c_urls_refusees(entrees, cle_liste) -> list:
    """A source URL that points inside the network is garbage or a probe.

    `validate_url` is the parse-time half of the SSRF guard: no DNS, no socket,
    so this stays safe to run on the presentation path.
    """
    out = []
    for i, entree in enumerate(entrees):
        url = _url_de(entree)
        if not url or validate_url(url):
            continue
        out.append(_signalement(
            'url_source_refusee', 'elevee', f'{cle_liste}[{i}]',
            f"L'adresse source {url[:120]} n'est pas vérifiable: schéma non "
            "HTTP, adresse interne ou format suspect.",
            "Retirer la ligne du rapport. Une source invérifiable ne peut pas "
            "soutenir un constat devant un client.",
            url=url))
    return out


def _c_totaux(report, entrees, longueur, cle_liste) -> list:
    """A declared total that its own list does not support."""
    out = []
    if longueur is None:
        return out

    cle_total, total = _premier(report, _CLES_TOTAL)
    total = _entier(total)
    if total is not None and total != longueur:
        out.append(_signalement(
            'total_incoherent', 'elevee', cle_total,
            f"Le rapport annonce {total} lien(s) alors que sa liste "
            f"« {cle_liste} » en contient {longueur}.",
            "Recalculer le total à partir de la liste, ou expliquer dans le "
            "rapport pourquoi la liste est partielle.",
            annonce=total, reel=longueur))

    cle_dom, declares = _premier(report, _CLES_DOMAINES)
    declares = _entier(declares)
    if declares is None:
        return out
    hotes = {_hote(_url_de(e)) for e in entrees}
    hotes.discard('')
    if declares != len(hotes):
        out.append(_signalement(
            'domaines_incoherents', 'elevee', cle_dom,
            f"Le rapport annonce {declares} domaine(s) référent(s) alors que "
            f"sa liste en contient {len(hotes)} distinct(s).",
            "Compter les domaines référents sur les hôtes distincts de la "
            "liste, pas sur le nombre de liens.",
            annonce=declares, reel=len(hotes)))
    return out


def _c_resume(report, entrees, resume) -> list:
    """The summary must agree with the results it summarises."""
    if not isinstance(resume, dict) or not entrees:
        return []
    reel = {}
    for entree in entrees:
        etat = entree.get('etat') or entree.get('status')
        if isinstance(etat, str) and etat:
            reel[etat] = reel.get(etat, 0) + 1
    if not reel:
        return []

    par_etat = resume.get('par_etat')
    par_etat = par_etat if isinstance(par_etat, dict) else {}
    out = []
    for etat, compte in sorted(reel.items()):
        annonce = _entier(par_etat.get(etat, resume.get(etat)))
        if annonce is None or annonce == compte:
            continue
        out.append(_signalement(
            'resume_incoherent', 'elevee', f'resume.{etat}',
            f"Le résumé annonce {annonce} ligne(s) « {etat} » alors que la "
            f"liste en contient {compte}.",
            "Recalculer le résumé à partir des résultats plutôt que de le "
            "tenir à jour à la main.",
            etat=etat, annonce=annonce, reel=compte))

    confirmes = _entier(resume.get('confirmes'))
    total = _entier(resume.get('total'))
    if confirmes is not None and total is not None and confirmes > total:
        out.append(_signalement(
            'resume_impossible', 'elevee', 'resume.confirmes',
            f"Le résumé annonce {confirmes} lien(s) confirmé(s) pour "
            f"{total} vérifié(s).",
            "Corriger le compte: un lien confirmé est forcément un lien vérifié.",
            confirmes=confirmes, total=total))

    taux = resume.get('taux_confirmation')
    if isinstance(taux, (int, float)) and not isinstance(taux, bool):
        if taux < 0 or taux > 100:
            out.append(_signalement(
                'taux_impossible', 'moyenne', 'resume.taux_confirmation',
                f"Le taux de confirmation annoncé est {taux}, hors de l'échelle 0 à 100.",
                "Recalculer le taux sur les liens réellement tranchés.",
                taux=taux))
    return out


def _c_coherence_etats(entrees, cle_liste) -> list:
    """A line that contradicts itself, and a loss claimed on a JS platform."""
    out = []
    for i, entree in enumerate(entrees):
        etat = entree.get('etat') or entree.get('status')
        if not isinstance(etat, str):
            continue
        url = _url_de(entree)
        liens = entree.get('liens')
        nb = _entier(entree.get('nb_liens'))
        if nb is None and isinstance(liens, list):
            nb = len(liens)

        if etat == 'confirme':
            if entree.get('lien_present') is False:
                out.append(_signalement(
                    'etat_incoherent', 'elevee', f'{cle_liste}[{i}]',
                    f"La ligne {url or i} est marquée « confirmé » alors "
                    "qu'elle déclare aussi que le lien est absent.",
                    "Trancher: sans lien trouvé dans le HTML, l'état ne peut "
                    "pas être « confirmé »."))
            elif nb == 0:
                out.append(_signalement(
                    'confirme_sans_lien', 'elevee', f'{cle_liste}[{i}]',
                    f"La ligne {url or i} est marquée « confirmé » sans aucun "
                    "lien listé derrière.",
                    "Joindre l'ancre et l'URL du lien trouvé, ou retirer "
                    "l'affirmation."))
        elif etat in _ETATS_PERDUS and nb:
            out.append(_signalement(
                'perte_incoherente', 'elevee', f'{cle_liste}[{i}]',
                f"La ligne {url or i} est donnée pour perdue alors qu'elle "
                f"liste {nb} lien(s) vers la cible.",
                "Vérifier la ligne: un lien listé contredit la perte annoncée."))

        if etat in ('disparu', 'link_removed'):
            statut = _entier(entree.get('statut_http') or entree.get('http_status'))
            hote = _hote(url)
            if statut == 200 and _plateforme_js(hote):
                out.append(_signalement(
                    'perte_sur_plateforme_js', 'moyenne', f'{cle_liste}[{i}]',
                    f"{hote} répond 200 mais assemble ses pages en JavaScript: "
                    "annoncer le lien retiré est un faux négatif.",
                    "Classer la ligne « non vérifiable » et le dire au client, "
                    "plutôt que de compter une perte.",
                    domaine=hote))
    return out


def _c_dates(entrees, cle_liste) -> list:
    """Undated, post-dated or stale verifications."""
    maintenant = datetime.now(timezone.utc)
    limite = maintenant - timedelta(days=AGE_MAX_JOURS)
    sans_date = []
    plus_vieille = None
    out = []

    for i, entree in enumerate(entrees):
        etat = entree.get('etat') or entree.get('status')
        if etat not in ('confirme', 'verified'):
            continue
        brut = entree.get('verifie_le') or entree.get('verified_at') or \
            entree.get('checked_at')
        moment = _date_iso(brut)
        if moment is None:
            sans_date.append(_url_de(entree) or f'{cle_liste}[{i}]')
            continue
        if moment > maintenant + timedelta(minutes=5):
            out.append(_signalement(
                'date_future', 'moyenne', f'{cle_liste}[{i}]',
                f"La date de vérification {brut} est dans le futur.",
                "Horodater les vérifications en UTC au moment du crawl.",
                date=brut))
            continue
        if plus_vieille is None or moment < plus_vieille:
            plus_vieille = moment

    if sans_date:
        out.append(_signalement(
            'date_manquante', 'moyenne', cle_liste,
            f"{len(sans_date)} lien(s) confirmé(s) sans date de vérification.",
            "Horodater chaque vérification: c'est la date qui rend le constat "
            "défendable devant un client qui doute.",
            exemples=sans_date[:5]))
    if plus_vieille is not None and plus_vieille < limite:
        age = (maintenant - plus_vieille).days
        out.append(_signalement(
            'verification_perimee', 'faible', cle_liste,
            f"La vérification la plus ancienne du rapport date de {age} jours.",
            f"Recrawler les liens vérifiés il y a plus de {AGE_MAX_JOURS} jours "
            "avant de présenter le rapport.",
            age_jours=age))
    return out


def _c_mentions(report) -> list:
    """Textual mentions presented as links, and counts capped by the API.

    This is the exact claim `views.task_backlinks` used to make: a Serper query
    for the bare domain counts pages that name the site, linked or not, and the
    plan caps the answer at ten results.
    """
    out = []
    est_lien = report.get('is_link_data')
    a_mentions = 'total_mentioning_domains' in report or \
        (isinstance(report.get('source'), str) and 'mention' in report['source'].lower())
    cle_dom, declares = _premier(report, _CLES_DOMAINES)
    cle_total, total = _premier(report, _CLES_TOTAL)

    if est_lien is False or a_mentions:
        if cle_dom or cle_total:
            out.append(_signalement(
                'mentions_presentees_comme_liens', 'critique',
                cle_dom or cle_total,
                "Le rapport compte des mentions textuelles du domaine et les "
                f"présente sous « {cle_dom or cle_total} »: une mention n'est "
                "pas un lien.",
                "Renommer la mesure en mentions, ou la remplacer par une "
                "vérification page par page qui confirme les liens.",
                cle=cle_dom or cle_total))

    plafond = _entier(report.get('saturates_at'))
    if plafond:
        for cle, valeur in ((cle_total, total), (cle_dom, declares)):
            compte = _entier(valeur)
            if compte is not None and compte >= plafond:
                out.append(_signalement(
                    'mesure_plafonnee', 'elevee', cle,
                    f"« {cle} » vaut {compte} pour un plafond de mesure de "
                    f"{plafond}: c'est la limite de l'outil, pas le profil du site.",
                    "Présenter la valeur comme un minimum, ou paginer la "
                    "source jusqu'à sortir du plafond.",
                    valeur=compte, plafond=plafond))
    return out


def _c_sans_preuve(report, entrees, cible) -> list:
    """A number nobody can trace back to a verified link."""
    out = []
    cle_score, score = _premier(report, _CLES_SCORE)
    cle_total, total = _premier(report, _CLES_TOTAL)
    cle_dom, declares = _premier(report, _CLES_DOMAINES)

    tranches = 0
    for entree in entrees:
        etat = entree.get('etat') or entree.get('status')
        if etat in _ETATS_TRANCHES or etat in ('verified', 'link_removed', 'lost'):
            tranches += 1

    if cle_score and score is not None and tranches == 0:
        out.append(_signalement(
            'affirmation_sans_donnee', 'critique', cle_score,
            f"Le rapport publie « {cle_score} » = {score} alors qu'aucun lien "
            "n'a été vérifié.",
            "Ne pas afficher de note tant qu'aucune page source n'a été lue. "
            "Afficher « données insuffisantes ».",
            cle=cle_score, valeur=score))

    if not entrees and (cle_total or cle_dom):
        annonce = _entier(total) or _entier(declares)
        if annonce:
            out.append(_signalement(
                'total_sans_liste', 'elevee', cle_total or cle_dom,
                f"Le rapport annonce {annonce} lien(s) sans joindre la liste "
                "des pages sources.",
                "Joindre la liste des sources vérifiées: un total sans liste "
                "ne se défend pas.",
                annonce=annonce))
    elif entrees and tranches == 0 and (cle_total or cle_dom):
        out.append(_signalement(
            'liste_sans_verification', 'elevee', _cle_liste(report),
            "Aucune ligne du rapport ne porte d'état de vérification: les "
            "liens sont annoncés sans qu'une page source ait été lue.",
            "Passer la liste dans `verify_batch` avant de la présenter.",
            lignes=len(entrees)))

    if not cible and (entrees or cle_total):
        out.append(_signalement(
            'cible_absente', 'moyenne', 'domaine_cible',
            "Le rapport ne dit pas de quel domaine ces liens sont les backlinks.",
            "Nommer le domaine cible dans le rapport.",))
    return out


def _cle_liste(report) -> str:
    """Name of the list key this report used, for pointing a finding at it."""
    for cle in _CLES_LISTE:
        if isinstance(report.get(cle), list):
            return cle
    return 'liens'
