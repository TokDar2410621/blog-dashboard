"""Extract every SEO signal from a page in one robust pass over the HTML.

Ported from claude-seo v2.2.4 `scripts/parse_html.py`.
Copyright (c) 2025 Daniel Agrici (AgriciDaniel). MIT.
https://github.com/AgriciDaniel/claude-seo

Upstream parses with BeautifulSoup and prefers lxml. Neither is in
backend/requirements.txt and lxml compiles native code, so the extraction is
rebuilt here on `html.parser` from the standard library, keeping the same
output shape and adding the derived views an audit needs (missing-alt images,
schema types, low-signal headings).

What changed for Gridar. The word counter and the low-signal heading test read
French: elision and hyphenated compounds count as one word, and a heading like
"1 500 $" or "99,9 %" is recognized as a stat counter instead of a topic.
Non-breaking spaces survive whitespace collapsing, so reported headings keep
their Quebec typography. `<header>` only counts as site chrome when it sits
outside `<main>` or `<article>`, because most themes wrap the H1 and the
selling copy in a hero `<header>` that upstream deletes before counting words.
URLs resolve against `<base href>` as well as the page URL, hosts compare
without the www prefix so a site linking to both spellings does not look like
it links off-site, and mailto/tel anchors are dropped instead of inflating the
external-link count of every local business page.

Pure data in, pure data out: no network, no ORM, no Django. The caller fetches
the page (with `url_safety.safe_get`, never a bare `requests.get`) and passes
the body here.
"""
from __future__ import annotations

import json
import re
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

__all__ = ['extract_seo_signals', 'count_words']


# Never pushed on the tag stack: the spec gives them no end tag, so treating
# a stray `</img>` as a real close would unwind the stack under it.
_VOID_TAGS = frozenset({
    'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link',
    'meta', 'param', 'source', 'track', 'wbr',
})

# Text in here never reaches a reader, so it must not reach the word count.
# `head` and `title` are listed because the title is reported on its own and
# would otherwise be counted twice on pages that omit `<head>`.
_INVISIBLE_TAGS = frozenset({
    'head', 'title', 'script', 'style', 'noscript', 'template', 'svg',
    'iframe', 'object', 'canvas', 'select', 'option', 'datalist',
})

# Boilerplate repeated on every URL. Counting it would make a thin page look
# thick, since a big menu and a fat footer can add 300 words on their own.
_CHROME_TAGS = frozenset({'nav', 'footer'})
_MAIN_TAGS = frozenset({'main', 'article'})

# Crossing any other tag boundary is a word boundary. Without this list,
# `<h1>Plombier<br>Montreal</h1>` reads as one glued token, and with a naive
# space-everywhere rule `Grid<b>ar</b>` breaks into two.
_INLINE_TAGS = frozenset({
    'a', 'abbr', 'b', 'bdi', 'bdo', 'cite', 'code', 'data', 'del', 'dfn',
    'em', 'font', 'i', 'ins', 'kbd', 'label', 'mark', 'q', 'rp', 'rt',
    'ruby', 's', 'samp', 'small', 'span', 'strong', 'sub', 'sup', 'time',
    'tt', 'u', 'var',
})

# Lazy-loader detection. Covers native loading plus the JS loaders that ship
# on WordPress and WooCommerce sites, which strip `loading="lazy"` and swap
# `src` for a placeholder. A check on `loading` alone reports "not lazy" on a
# page that is in fact lazy-loaded end to end.
_PERFMATTERS_ATTRS = ('data-perfmatters-src', 'data-perfmatters-srcset')
_EWWW_ATTRS = ('data-ewww-src', 'data-eio')
_GENERIC_LAZY_ATTRS = (
    'data-src', 'data-lazy-src', 'data-lazy', 'data-original',
    'data-srcset', 'data-lazy-srcset', 'data-lazyloaded',
)
_PERFMATTERS_CLASSES = frozenset({'perfmatters-lazy', 'perfmatters-lazy-loaded'})
_EWWW_CLASSES = frozenset({'lazyload-eio', 'lazyloaded-eio'})
_GENERIC_LAZY_CLASSES = frozenset({'lazyload', 'lazyloaded', 'lazy', 'lazy-loaded'})

_DECORATIVE_ROLES = frozenset({'presentation', 'none'})

# The only tags whose attributes are read. Everything else skips the dict.
_ATTR_TAGS = frozenset({'html', 'base', 'meta', 'link', 'img', 'a', 'script'})
_NO_ATTRS = {}

# A word is a run of letters that may be welded by an elision apostrophe or a
# hyphen. French needs both: "l'entreprise" and "rendez-vous" are one word
# each, and splitting on the apostrophe inflates a French page by roughly a
# tenth, which is enough to push a thin page over a thin-content threshold.
_WORD_RE = re.compile(
    r"[^\W\d_]+(?:['’ʼ\-][^\W\d_]+)*"
    r"|\d+(?:[.,]\d+)*"
)

_WS_RE = re.compile(r'\s+')

# A lone non-breaking space survives collapsing. French typography puts one
# before the % and the $ and inside thousands ("1 500,50 $"), and flattening
# it to a plain space quietly rewrites every heading Gridar reports back.
_KEPT_SPACES = frozenset({' ', ' '})

# Ordinal suffixes stripped before asking "is this heading just a number?".
# French writes 1er / 1re / 2e / 2eme, English writes 1st / 2nd / 3rd / 4th.
_ORDINAL_RE = re.compile(
    r'(?<=\d)\s*(?:ers?|res?|i?[eè]mes?|es?|st|nd|rd|th)\b',
    re.IGNORECASE,
)

_MAX_LINK_TEXT = 100
_MAX_SCHEMA_BLOCKS = 200
_MAX_SCHEMA_DEPTH = 8


def count_words(text: str) -> int:
    """Count words the way a French reader would.

    "l'entreprise" and "rendez-vous" each count once, accented letters are
    letters, and a bare number counts as a word.
    """
    if not text:
        return 0
    return len(_WORD_RE.findall(text))


def _collapse(text: str) -> str:
    return _WS_RE.sub(_squeeze, text).strip()


def _squeeze(match) -> str:
    run = match.group(0)
    return run if run in _KEPT_SPACES else ' '


def _first_wins(attrs) -> dict:
    """Fold the parser's attribute pairs into a dict, first occurrence wins.

    html.parser hands back duplicates as separate pairs; the HTML spec says a
    browser keeps the first, and `dict(attrs)` would keep the last.
    """
    out = {}
    for key, value in attrs:
        key = key.lower()
        if key not in out:
            out[key] = value
    return out


def _rel_tokens(raw) -> list:
    """Split a `rel` attribute into lowercase tokens, order preserved.

    BeautifulSoup returns rel pre-split because it knows the multi-valued
    attributes; html.parser hands back the raw string.
    """
    if not raw:
        return []
    seen = []
    for token in raw.lower().split():
        if token not in seen:
            seen.append(token)
    return seen


def _classes(raw) -> set:
    return set((raw or '').lower().split())


def _detect_lazy_method(attrs: dict) -> str:
    """Classify how the image defers loading.

    Order: native, then the named plugins, then the generic bucket. The named
    ones come first so a report can attribute the optimization, which tells us
    which WordPress stack the site runs.

    Returns one of: 'native', 'perfmatters', 'ewww', 'js-generic', 'none'.
    """
    if (attrs.get('loading') or '').strip().lower() == 'lazy':
        return 'native'

    class_list = _classes(attrs.get('class'))

    if any(attrs.get(a) for a in _PERFMATTERS_ATTRS) or class_list & _PERFMATTERS_CLASSES:
        return 'perfmatters'
    if any(attrs.get(a) for a in _EWWW_ATTRS) or class_list & _EWWW_CLASSES:
        return 'ewww'
    if any(attrs.get(a) for a in _GENERIC_LAZY_ATTRS) or class_list & _GENERIC_LAZY_CLASSES:
        return 'js-generic'
    return 'none'


def _is_low_signal_heading(text: str) -> bool:
    """True for a heading that carries no topic: a stat counter or a stub.

    Marketing pages wrap their counters in headings ("500+", "24/7", "1 500 $",
    "99,9 %"), and Gridar reads the first H1 as the page topic. One counter at
    the top of the DOM and the whole audit keys off nothing.

    Upstream flags any heading of three characters or less, which condemns
    legitimate short ones like "Nos" or "SEO". The test here is digits without
    letters instead, so it survives the Quebec number format (comma decimal,
    non-breaking thousands separator, currency sign trailing) and the French
    ordinals that upstream's English-only reading would leave standing.
    """
    stripped = text.strip()
    if not stripped:
        return False
    if len(stripped) <= 2:
        return True
    core = _ORDINAL_RE.sub('', stripped)
    return (
        any(char.isdigit() for char in core)
        and not any(char.isalpha() for char in core)
    )


class _Frame:
    """One open element: what it is, whether its text is visible, what it captures."""

    __slots__ = ('tag', 'invisible', 'kind', 'buf', 'attrs')

    def __init__(self, tag, invisible, kind=None, attrs=None):
        self.tag = tag
        self.invisible = invisible
        self.kind = kind
        self.buf = [] if kind else None
        # Shared empty dict, never written to, so untouched tags cost nothing.
        self.attrs = _NO_ATTRS if attrs is None else attrs


class _SeoParser(HTMLParser):
    """Single pass over the document, collecting raw signals.

    Everything stays raw here: URLs are not resolved and nothing is derived,
    because `<base href>` can appear after the canonical link and would change
    how earlier URLs resolve. `extract_seo_signals` does that afterwards.
    """

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._stack = []
        self.lang = None
        self.base_href = None
        self.title = None
        self.meta_description = None
        self.meta_robots = None
        self.meta_keywords = None
        self.open_graph = {}
        self.twitter_card = {}
        self.canonical = None
        self.hreflang = []
        self.headings = {'h1': [], 'h2': [], 'h3': []}
        self.images = []
        self.links = []
        self.jsonld = []
        self.text_parts = []
        # Open frames that are buffering text, and whether one of them is the
        # title. Both are shortcuts around scanning the stack on every single
        # tag, which on a 500 KB page is the difference that matters.
        self._captures = []
        self._title_open = False

    # -- state helpers -----------------------------------------------------

    def _invisible_now(self) -> bool:
        return self._stack[-1].invisible if self._stack else False

    def _inside_main(self) -> bool:
        return any(frame.tag in _MAIN_TAGS for frame in self._stack)

    def _inside(self, tag) -> bool:
        return any(frame.tag == tag for frame in self._stack)

    def _implicit_close(self, tag):
        """Close elements a browser would close here, and this parser cannot see.

        Without this, one missing `</title>` makes the title swallow the whole
        document, and a missing `</head>` marks the entire body invisible, so
        the page reports zero words. Both are common on hand-edited templates.
        `<title>` holds text only, so any start tag ends it; a heading ends the
        heading above it; `<body>` ends the head.
        """
        if self._title_open and tag != 'title':
            self._close_element('title')
        if tag == 'body' and self._inside('head'):
            self._close_element('head')
        if tag in self.headings:
            for frame in reversed(self._stack):
                if frame.tag in self.headings:
                    self._close_element(frame.tag)
                    break

    def _note_break(self, tag):
        """Record that a non-inline boundary separates two runs of text."""
        if tag in _INLINE_TAGS:
            return
        for frame in self._captures:
            frame.buf.append(' ')
        if not self._invisible_now():
            self.text_parts.append(' ')

    # -- HTMLParser hooks --------------------------------------------------

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        # Most tags on a page are layout containers whose attributes nothing
        # here reads, and folding them into a dict is the single most expensive
        # thing this parser would otherwise do per tag.
        a = _first_wins(attrs) if tag in _ATTR_TAGS else _NO_ATTRS
        self._implicit_close(tag)
        self._note_break(tag)

        if tag == 'html':
            lang = (a.get('lang') or a.get('xml:lang') or '').strip()
            if lang and not self.lang:
                self.lang = lang
        elif tag == 'base':
            href = (a.get('href') or '').strip()
            if href and not self.base_href:
                self.base_href = href
        elif tag == 'meta':
            self._handle_meta(a)
        elif tag == 'link':
            self._handle_link(a)
        elif tag == 'img':
            self.images.append(_image_record(a))

        if tag in _VOID_TAGS:
            return

        kind = None
        if tag == 'title' and self.title is None and not self._inside('svg'):
            # SVG has a <title> element of its own, holding an icon label.
            kind = 'title'
        elif tag in self.headings:
            kind = tag
        elif tag == 'a' and a.get('href'):
            kind = 'a'
        elif tag == 'script' and _is_jsonld(a):
            kind = 'jsonld'

        parent_invisible = self._stack[-1].invisible if self._stack else False
        invisible = (
            parent_invisible
            or tag in _INVISIBLE_TAGS
            or tag in _CHROME_TAGS
            or (tag == 'header' and not self._inside_main())
        )
        frame = _Frame(tag, invisible, kind, a)
        self._stack.append(frame)
        if kind:
            self._captures.append(frame)
            if kind == 'title':
                self._title_open = True

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in _VOID_TAGS:
            return
        self._note_break(tag)
        self._close_element(tag)

    def _close_element(self, tag):
        """Close the innermost `tag` and everything left open inside it.

        A stray end tag with no match is dropped. That is what keeps a page
        full of unclosed <p> and <li>, or one `</div>` too many, from shredding
        the stack and losing every signal below the mistake.
        """
        for i in range(len(self._stack) - 1, -1, -1):
            if self._stack[i].tag == tag:
                for frame in reversed(self._stack[i:]):
                    self._flush(frame)
                del self._stack[i:]
                return

    def handle_data(self, data):
        if not data:
            return
        for frame in self._captures:
            frame.buf.append(data)
        if not self._invisible_now():
            self.text_parts.append(data)

    def finish(self):
        """Flush elements the document never closed."""
        for frame in reversed(self._stack):
            self._flush(frame)
        self._stack = []
        self._captures = []
        self._title_open = False

    # -- collection --------------------------------------------------------

    def _flush(self, frame):
        if frame.buf is None:
            return
        raw = ''.join(frame.buf)
        frame.buf = None
        self._captures.remove(frame)
        if frame.kind == 'title':
            self._title_open = False

        if frame.kind == 'jsonld':
            self.jsonld.append(raw)
            return

        text = _collapse(raw)
        if frame.kind == 'title':
            if text and self.title is None:
                self.title = text
        elif frame.kind in self.headings:
            if text:
                self.headings[frame.kind].append(text)
        elif frame.kind == 'a':
            self.links.append({
                'href': frame.attrs.get('href') or '',
                'text': text[:_MAX_LINK_TEXT],
                'rel': frame.attrs.get('rel'),
            })

    def _handle_meta(self, a):
        name = (a.get('name') or '').strip().lower()
        prop = (a.get('property') or '').strip().lower()
        content = (a.get('content') or '').strip()

        # First occurrence wins, empty included: an empty description is a
        # finding of its own, so it must stay distinguishable from no tag.
        if name == 'description' and self.meta_description is None:
            self.meta_description = content
        elif name == 'robots' and self.meta_robots is None:
            self.meta_robots = content
        elif name == 'keywords' and self.meta_keywords is None:
            self.meta_keywords = content

        # Both attributes are read for both namespaces. The spec says og goes
        # in `property` and twitter in `name`, and enough real pages do the
        # opposite that honouring only the spec loses cards on live sites.
        for key in (prop, name):
            if key.startswith('og:'):
                self.open_graph.setdefault(key, content)
            elif key.startswith('twitter:'):
                self.twitter_card.setdefault(key, content)

    def _handle_link(self, a):
        rels = _rel_tokens(a.get('rel'))
        href = (a.get('href') or '').strip()
        if 'canonical' in rels and href and self.canonical is None:
            self.canonical = href
        if 'alternate' in rels:
            lang = (a.get('hreflang') or '').strip()
            if lang:
                self.hreflang.append({'lang': lang, 'href': href})


def _is_jsonld(attrs: dict) -> bool:
    mime = (attrs.get('type') or '').strip().lower()
    return mime.startswith('application/ld+json')


def _image_record(a: dict) -> dict:
    alt = a.get('alt')
    role = (a.get('role') or '').strip().lower()
    aria_hidden = (a.get('aria-hidden') or '').strip().lower()
    return {
        'src': (a.get('src') or '').strip(),
        'alt': alt,
        'width': a.get('width'),
        'height': a.get('height'),
        'loading': (a.get('loading') or '').strip().lower() or None,
        'lazy_method': _detect_lazy_method(a),
        # alt="" is the declared way to say "decorative", so it is not a defect.
        'decorative': alt == '' or role in _DECORATIVE_ROLES or aria_hidden == 'true',
    }


def _is_missing_alt(image: dict) -> bool:
    """No alt attribute at all, or one holding nothing but whitespace.

    A blank-but-present `alt=""` is excluded on purpose: that is the standard
    marker for a decorative image, and flagging it buries the real defects.
    """
    alt = image['alt']
    if alt is None:
        return True
    return alt.strip() == '' and alt != ''


def _resolve(href: str, base: str) -> str:
    href = (href or '').strip()
    if not href or not base:
        return href
    try:
        return urljoin(base, href)
    except ValueError:
        return href


def _strip_www(host: str) -> str:
    """Comparable host: no leading www.

    Upstream compares `netloc` verbatim, so a site that links to both
    example.com and www.example.com sees half its internal links reported as
    external, and the internal-linking audit built on that is wrong.
    """
    return host[4:] if host.startswith('www.') else host


def _hostname(parsed) -> str:
    # urlsplit already refuses the bracket forms that would break here, but
    # which of the two raises has moved between Python versions, and prod runs
    # 3.13 while this file is exercised on 3.10.
    try:
        return (parsed.hostname or '').lower()
    except ValueError:
        return ''


def _site_host(url: str) -> str:
    try:
        parsed = urlparse(url)
    except ValueError:
        return ''
    return _strip_www(_hostname(parsed))


def _parse_jsonld_block(raw: str):
    """Decode one <script type="application/ld+json"> body, or None."""
    text = raw.strip()
    if not text:
        return None
    # Some CMS templates wrap the payload for XHTML compatibility.
    for prefix in ('//<![CDATA[', '/*<![CDATA[*/', '<![CDATA['):
        if text.startswith(prefix):
            text = text[len(prefix):]
            break
    for suffix in ('//]]>', '/*]]>*/', ']]>'):
        if text.endswith(suffix):
            text = text[:-len(suffix)]
            break
    text = text.strip()
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        pass
    # html.parser leaves script bodies raw, so a template that HTML-escaped
    # its JSON arrives with &quot; intact. Worth one retry before giving up.
    try:
        return json.loads(unescape(text))
    except (ValueError, TypeError):
        return None


def _flatten_jsonld(node, out: list, context=None, depth: int = 0) -> None:
    """Append every schema entity in `node`, unwrapping @graph containers.

    Yoast and RankMath emit one script holding a @graph of a dozen entities,
    so a consumer looking for `@type` on the top-level object finds nothing.
    The container's @context is pushed down onto children that lack one,
    otherwise every unwrapped entity looks context-less to a validator.
    """
    if depth > _MAX_SCHEMA_DEPTH or len(out) >= _MAX_SCHEMA_BLOCKS:
        return
    if isinstance(node, list):
        for item in node:
            _flatten_jsonld(item, out, context, depth + 1)
        return
    if not isinstance(node, dict):
        return

    ctx = node.get('@context', context)
    if '@graph' in node:
        _flatten_jsonld(node['@graph'], out, ctx, depth + 1)
        # A wrapper that also declares its own @type is an entity in its own right.
        rest = {k: v for k, v in node.items() if k != '@graph'}
        if rest.get('@type'):
            out.append(rest)
        return

    if ctx is not None and '@context' not in node:
        node = dict(node)
        node['@context'] = ctx
    out.append(node)


def _schema_types(blocks: list) -> list:
    types = []
    for block in blocks:
        value = block.get('@type')
        candidates = value if isinstance(value, list) else [value]
        for candidate in candidates:
            if isinstance(candidate, str) and candidate and candidate not in types:
                types.append(candidate)
    return types


def extract_seo_signals(html: str, base_url: str = '') -> dict:
    """Pull the SEO signals out of an HTML document.

    Args:
        html: the raw response body.
        base_url: the URL the body came from, used to resolve relative links
            and to tell internal links from external ones. Optional: without
            it, links are split on whether they carry a host.

    Returns a dict with these keys, always present:
        title, lang, meta_description, meta_robots, meta_keywords, canonical
            strings, or None when the element is absent. An empty string means
            the element exists and is empty, which is a different finding.
        h1, h2, h3                list of heading texts, document order.
        suspicious_headings       same keys, holding the headings that read as
                                  stat counters rather than topics.
        open_graph, twitter_card  dicts keyed by the full property name.
        hreflang                  list of {'lang', 'href'}, href resolved.
        schema                    JSON-LD entities, @graph containers unwrapped.
        schema_types              the distinct @type values found.
        images                    list of {'src', 'alt', 'width', 'height',
                                  'loading', 'lazy_method', 'decorative'}.
        images_missing_alt        the subset whose alt is absent or blank.
        links                     {'internal': [...], 'external': [...]}, each
                                  entry {'href', 'text', 'rel'}.
        word_count                words of visible text, French-aware.
        text                      that visible text, whitespace collapsed.

    Never raises on malformed input: a broken page still carries signals, and
    an audit that dies on one bad document is worse than a partial reading.
    """
    parser = _SeoParser()
    if html:
        try:
            parser.feed(html)
        except Exception:
            pass
        finally:
            try:
                parser.close()
            except Exception:
                pass
            parser.finish()

    # <base href> wins over the fetch URL for resolution, and is itself allowed
    # to be relative to the fetch URL.
    page_url = (base_url or '').strip()
    effective_base = page_url
    if parser.base_href:
        effective_base = _resolve(parser.base_href, page_url) or parser.base_href

    text = _collapse(''.join(parser.text_parts))

    schema = []
    for raw in parser.jsonld:
        decoded = _parse_jsonld_block(raw)
        if decoded is not None:
            _flatten_jsonld(decoded, schema)

    images = parser.images
    for image in images:
        image['src'] = _resolve(image['src'], effective_base)

    return {
        'title': parser.title,
        'lang': parser.lang,
        'meta_description': parser.meta_description,
        'meta_robots': parser.meta_robots,
        'meta_keywords': parser.meta_keywords,
        'canonical': _resolve(parser.canonical, effective_base) if parser.canonical else None,
        'h1': parser.headings['h1'],
        'h2': parser.headings['h2'],
        'h3': parser.headings['h3'],
        'suspicious_headings': {
            level: [h for h in items if _is_low_signal_heading(h)]
            for level, items in parser.headings.items()
        },
        'open_graph': parser.open_graph,
        'twitter_card': parser.twitter_card,
        'hreflang': [
            {'lang': item['lang'], 'href': _resolve(item['href'], effective_base)}
            for item in parser.hreflang
        ],
        'schema': schema,
        'schema_types': _schema_types(schema),
        'images': images,
        'images_missing_alt': [img for img in images if _is_missing_alt(img)],
        'links': _split_links(parser.links, effective_base),
        'word_count': count_words(text),
        'text': text,
    }


def _split_links(raw_links: list, base: str) -> dict:
    """Sort anchors into internal and external, dropping the non-navigational.

    Upstream keeps only `#` and `javascript:` out; mailto: and tel: then land
    in the external bucket, and on a local business homepage that is most of
    the count. They are dropped here instead.
    """
    base_host = _site_host(base) if base else ''
    internal, external = [], []

    for raw in raw_links:
        href = (raw['href'] or '').strip()
        if not href or href.startswith('#'):
            continue
        try:
            parsed = urlparse(href)
        except ValueError:
            continue
        scheme = (parsed.scheme or '').lower()
        if scheme and scheme not in ('http', 'https'):
            continue

        entry = {
            'href': _resolve(href, base),
            'text': raw['text'],
            'rel': _rel_tokens(raw['rel']),
        }
        if not parsed.netloc:
            # A relative href lands on the page's own host by construction, so
            # it needs no comparison and no second parse.
            bucket = internal
        elif not base_host:
            # No page URL to compare against, so a link carrying a host is the
            # only kind we can call external.
            bucket = external
        else:
            bucket = internal if _strip_www(_hostname(parsed)) == base_host else external
        bucket.append(entry)

    return {'internal': internal, 'external': external}
