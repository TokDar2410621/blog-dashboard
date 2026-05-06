"""Branding extractor — given a public URL, scan the page HTML+CSS and infer:
  - logo_url (favicon, og:image, header <img>)
  - brand_color (theme-color meta, accent CSS color, link color)
  - brand_fg (text color)
  - font_sans (body font-family)
  - font_display (heading font-family)
  - site_name (og:site_name, <title>)
  - description (meta description, og:description)

The shape returned is compatible with `Site.theme_config` so callers can save
it directly. This is a best-effort heuristic — not pixel-perfect — but enough
to give a non-coder a "here's how your blog will look on your domain" preview.
"""
from __future__ import annotations

import logging
import re
from collections import Counter
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import requests as http_requests

logger = logging.getLogger(__name__)

USER_AGENT = 'BlogDashboard/1.0 (+https://blog-dashboard.ca; branding-scan)'
TIMEOUT = 10  # seconds


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

_HEX_COLOR_RE = re.compile(r'#(?:[0-9a-fA-F]{3}){1,2}\b')
_RGB_COLOR_RE = re.compile(
    r'rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)(?:\s*,\s*[\d.]+)?\s*\)'
)
_FONT_FAMILY_RE = re.compile(r'font-family\s*:\s*([^;}\n]+)', re.IGNORECASE)
_NEUTRAL_HEX = {
    '#000', '#000000', '#fff', '#ffffff',
    '#fafafa', '#f5f5f5', '#eee', '#eeeeee', '#ddd', '#dddddd',
    '#222', '#222222', '#333', '#333333', '#666', '#666666',
    '#888', '#888888', '#999', '#999999', '#aaa', '#aaaaaa',
}


def _normalize_url(url):
    s = (url or '').strip()
    if not s:
        return ''
    if not s.startswith(('http://', 'https://')):
        s = 'https://' + s
    return s.rstrip('/')


def _hex_to_rgb(hx):
    h = hx.lstrip('#')
    if len(h) == 3:
        h = ''.join(c * 2 for c in h)
    if len(h) != 6:
        return None
    try:
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return None


def _rgb_to_hex(r, g, b):
    return '#{:02x}{:02x}{:02x}'.format(r, g, b)


def _is_neutral_color(hx):
    return hx.lower() in _NEUTRAL_HEX


def _luminance(rgb):
    """Relative luminance (0..1) per WCAG."""
    def chan(v):
        v = v / 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = rgb
    return 0.2126 * chan(r) + 0.7152 * chan(g) + 0.0722 * chan(b)


def _saturation(rgb):
    """HSL saturation (0..1). Higher = more colorful."""
    r, g, b = (v / 255.0 for v in rgb)
    mx = max(r, g, b)
    mn = min(r, g, b)
    l = (mx + mn) / 2
    if mx == mn:
        return 0.0
    d = mx - mn
    return d / (2 - mx - mn) if l > 0.5 else d / (mx + mn)


# --------------------------------------------------------------------------
# HTML parsing
# --------------------------------------------------------------------------

class _BrandingHTMLParser(HTMLParser):
    """Best-effort HTML parser to extract metadata, favicon, logo, inline CSS."""

    def __init__(self, base_url):
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.title = ''
        self._in_title = False
        self.og_site_name = ''
        self.og_image = ''
        self.og_description = ''
        self.meta_description = ''
        self.theme_color = ''
        self.icons = []  # list of {href, sizes, rel}
        self.first_img_in_header = ''
        self._in_header = 0  # depth counter
        self.inline_css = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'title':
            self._in_title = True
        elif tag == 'meta':
            name = (a.get('name') or '').lower()
            prop = (a.get('property') or '').lower()
            content = a.get('content') or ''
            if name == 'description':
                self.meta_description = content[:300]
            elif name == 'theme-color' and content:
                self.theme_color = content.strip()
            elif prop == 'og:site_name':
                self.og_site_name = content
            elif prop == 'og:image':
                self.og_image = urljoin(self.base_url + '/', content)
            elif prop == 'og:description':
                self.og_description = content[:300]
        elif tag == 'link':
            rel = (a.get('rel') or '').lower()
            href = a.get('href') or ''
            if href and ('icon' in rel or 'apple-touch-icon' in rel or 'mask-icon' in rel):
                self.icons.append({
                    'href': urljoin(self.base_url + '/', href),
                    'sizes': a.get('sizes') or '',
                    'rel': rel,
                })
        elif tag == 'header':
            self._in_header += 1
        elif tag == 'img' and self._in_header > 0 and not self.first_img_in_header:
            src = a.get('src') or ''
            if src and not src.startswith('data:'):
                self.first_img_in_header = urljoin(self.base_url + '/', src)
        elif tag == 'style':
            self._in_style = True

    def handle_endtag(self, tag):
        if tag == 'title':
            self._in_title = False
        elif tag == 'header' and self._in_header > 0:
            self._in_header -= 1
        elif tag == 'style':
            self._in_style = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif getattr(self, '_in_style', False):
            self.inline_css.append(data)


# --------------------------------------------------------------------------
# Color & font extraction from CSS
# --------------------------------------------------------------------------

def _extract_colors(css_text):
    """Return list of hex colors found in the CSS, preserving order, deduped."""
    colors = []
    for m in _HEX_COLOR_RE.finditer(css_text):
        c = m.group(0).lower()
        if len(c) == 4:
            c = '#' + ''.join(ch * 2 for ch in c[1:])
        colors.append(c)
    for m in _RGB_COLOR_RE.finditer(css_text):
        r, g, b = (int(m.group(i)) for i in (1, 2, 3))
        colors.append(_rgb_to_hex(r, g, b))
    return colors


def _pick_brand_color(colors, theme_color_hint=''):
    """Pick the most likely brand color from a list of CSS color occurrences.
    Heuristic: prefer the most frequent saturated color; fall back to theme-color."""
    if theme_color_hint and _HEX_COLOR_RE.fullmatch(theme_color_hint):
        return theme_color_hint.lower()

    counter = Counter(c for c in colors if not _is_neutral_color(c))
    if not counter:
        return theme_color_hint or '#10b981'  # emerald default

    # Score candidates by frequency * saturation; bias toward mid-luminance.
    best = None
    best_score = -1
    for color, freq in counter.most_common(40):
        rgb = _hex_to_rgb(color)
        if not rgb:
            continue
        lum = _luminance(rgb)
        if lum < 0.05 or lum > 0.95:
            continue  # near-black / near-white
        sat = _saturation(rgb)
        if sat < 0.15:
            continue  # near-grayscale
        # Score: frequency-weighted, with slight saturation bonus
        score = freq * (0.5 + sat) * (0.7 + (1.0 - abs(0.5 - lum)) * 0.6)
        if score > best_score:
            best_score = score
            best = color
    return best or theme_color_hint or '#10b981'


def _pick_brand_fg(brand_color):
    """Given a brand_color, pick contrasting foreground (white or near-black)."""
    rgb = _hex_to_rgb(brand_color or '')
    if not rgb:
        return '#ffffff'
    lum = _luminance(rgb)
    return '#ffffff' if lum < 0.5 else '#0a0a0a'


def _extract_fonts(css_text):
    """Return (sans_font, display_font) — best-effort. Body fonts are sans by
    convention; first non-system font wins."""
    fonts = []
    for m in _FONT_FAMILY_RE.finditer(css_text):
        decl = m.group(1).strip()
        # Take first family
        first = decl.split(',')[0].strip().strip('"').strip("'")
        if not first:
            continue
        if first.lower() in {'inherit', 'initial', 'unset', 'revert', 'sans-serif',
                             'serif', 'monospace', 'system-ui', '-apple-system'}:
            continue
        fonts.append(first)

    # Filter out generic system stacks; pick most frequent custom font.
    counter = Counter(fonts)
    if not counter:
        return ('Inter', 'Inter')
    most = counter.most_common(2)
    sans = most[0][0]
    display = most[1][0] if len(most) > 1 and most[1][0] != sans else sans
    return (sans, display)


def _pick_logo_url(parser):
    """Prefer apple-touch-icon (largest), then largest favicon, then og:image,
    then first header img. Fallback: empty string."""
    icons = parser.icons or []
    apple = [i for i in icons if 'apple-touch-icon' in i['rel']]
    if apple:
        return apple[0]['href']
    # Pick the largest declared icon
    def _icon_size(i):
        s = (i.get('sizes') or '').lower()
        m = re.match(r'(\d+)x(\d+)', s)
        if m:
            return int(m.group(1))
        return 16
    if icons:
        return max(icons, key=_icon_size)['href']
    if parser.first_img_in_header:
        return parser.first_img_in_header
    if parser.og_image:
        return parser.og_image
    return ''


# --------------------------------------------------------------------------
# Public entry point
# --------------------------------------------------------------------------

def scan(url):
    """Scan a domain and return a theme_config-shaped dict.

    Returns:
      {
        'success': True,
        'normalized_url': 'https://...',
        'theme_config': {
          brand_color, brand_fg, font_sans, font_display, logo_url,
        },
        'meta': {
          site_name, description,
        },
      }
    or on failure: {'success': False, 'error': '...'}
    """
    target = _normalize_url(url)
    if not target:
        return {'success': False, 'error': 'URL invalide.'}
    parsed = urlparse(target)
    if not parsed.netloc:
        return {'success': False, 'error': 'URL sans hostname.'}

    try:
        resp = http_requests.get(
            target,
            headers={'User-Agent': USER_AGENT, 'Accept': 'text/html,*/*;q=0.8'},
            timeout=TIMEOUT,
            allow_redirects=True,
        )
    except http_requests.RequestException as e:
        return {'success': False, 'error': f'Site injoignable : {str(e)[:120]}'}

    if not resp.ok:
        return {'success': False, 'error': f'HTTP {resp.status_code} sur la home page.'}

    base = resp.url.rstrip('/')
    html = resp.text

    parser = _BrandingHTMLParser(base)
    try:
        parser.feed(html)
    except Exception as e:
        # HTML can be malformed; degrade gracefully on parse errors.
        logger.warning('HTML parse warning for %s: %s', target, e)

    # Extract from inline <style> blocks and any visible inline CSS.
    inline_css_combined = '\n'.join(parser.inline_css)
    # Also scan inline style="" attributes — quick pattern match.
    inline_attr_css = ''
    for m in re.finditer(r'style\s*=\s*"([^"]*)"', html, flags=re.IGNORECASE):
        inline_attr_css += m.group(1) + ';'

    css_blob = inline_css_combined + '\n' + inline_attr_css
    colors = _extract_colors(css_blob)
    brand_color = _pick_brand_color(colors, theme_color_hint=parser.theme_color)
    brand_fg = _pick_brand_fg(brand_color)
    sans, display = _extract_fonts(css_blob)
    logo_url = _pick_logo_url(parser)

    site_name = (parser.og_site_name or parser.title or parsed.netloc).strip()[:100]
    description = (parser.og_description or parser.meta_description or '').strip()[:300]

    return {
        'success': True,
        'normalized_url': base,
        'theme_config': {
            'brand_color': brand_color,
            'brand_fg': brand_fg,
            'font_sans': sans,
            'font_display': display,
            'logo_url': logo_url,
        },
        'meta': {
            'site_name': site_name,
            'description': description,
        },
        'debug': {
            'colors_sample': list(dict.fromkeys(colors))[:10],
            'icons_count': len(parser.icons),
            'theme_color': parser.theme_color,
        },
    }
