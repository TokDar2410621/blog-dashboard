"""Agent readability audit: what an AI agent can understand from served HTML.

Ported from claude-seo v2.2.4 `scripts/agent_ux_check.py`.
Copyright (c) 2025 Daniel Agrici (AgriciDaniel). MIT.
https://github.com/AgriciDaniel/claude-seo

Upstream renders every page with Playwright and scores mostly from the
Chromium accessibility tree. Railway cannot carry Chromium, so this port
keeps the raw-HTML half only and rebuilds the missing signal from what a
served document already exposes: landmarks, heading order, accessible names
derived from labels and ARIA, and image alt text. Dropping the renderer buys
back one check upstream could never make, because it always looked at the
page after JavaScript ran: whether the content exists in the served HTML at
all. That is the view an agent gets when it fetches a URL without a browser.
Price formats, generic link labels and the language check are Quebec French
first, since that is the content Gridar audits.
"""
from __future__ import annotations

import json
import re
import unicodedata
from html.parser import HTMLParser

__all__ = [
    'CRITERIA',
    'check_agent_readability',
]


# Ordered (key, French label, points). The weights sum to 100. Keys stay
# unaccented ASCII: they are API field names, not display text.
CRITERIA = (
    ('semantique', 'HTML sémantique et repères de page', 20),
    ('hierarchie_titres', 'Hiérarchie des titres', 20),
    ('elements_interactifs', 'Éléments interactifs étiquetés', 20),
    ('images_alt', 'Textes alternatifs des images', 15),
    ('contenu_sans_js', 'Contenu lisible sans exécuter le JavaScript', 15),
    ('infos_cles', 'Informations clés lisibles', 10),
)

# Never pushed on the tag stack: the parser reports no end tag for them, and
# an unbalanced stack would misplace every landmark that follows.
_VOID_TAGS = frozenset({
    'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link',
    'meta', 'param', 'source', 'track', 'wbr',
})

_HEADING_TAGS = frozenset({'h1', 'h2', 'h3', 'h4', 'h5', 'h6'})

# Elements whose text content forms an accessible name we need to read back.
_CAPTURED_TAGS = _HEADING_TAGS | {'a', 'button'}

_LANDMARK_TAGS = frozenset({
    'main', 'nav', 'header', 'footer', 'article', 'section', 'aside',
})

# ARIA roles that stand in for the matching landmark tag.
_ROLE_TO_LANDMARK = {
    'main': 'main',
    'navigation': 'nav',
    'banner': 'header',
    'contentinfo': 'footer',
    'article': 'article',
    'region': 'section',
    'complementary': 'aside',
}

# Mount points of the usual SPA frameworks. An empty one is the signature of
# a page whose content only exists once JavaScript has run.
_APP_ROOT_IDS = frozenset({
    'root', 'app', '__next', '__nuxt', '___gatsby', 'q-app', 'svelte',
    'application', 'main-app',
})

# Tags that already carry click semantics, so an onclick on them is fine.
_NATIVE_INTERACTIVE = frozenset({
    'a', 'button', 'input', 'select', 'textarea', 'label', 'summary',
    'details', 'option', 'form',
})

# Link and button texts that name no destination. Compared after accents and
# typographic apostrophes are normalized away, so every entry stays plain.
# The French half is the addition: upstream shipped no label list at all.
_GENERIC_LABELS = frozenset({
    'cliquez ici', 'cliquer ici', 'clique ici', 'cliquez', 'ici',
    'en savoir plus', 'savoir plus', 'en savoir +', 'lire la suite',
    'lire plus', 'voir plus', 'voir', 'plus', 'suite', 'details',
    'detail', 'suivant', 'continuer', 'soumettre', 'envoyer', 'go',
    'ok', 'lien', 'ce lien', 'ce document', 'telecharger', 'acceder',
    'click here', 'read more', 'learn more', 'more', 'here', 'this link',
    'link', 'submit', 'view', 'download', 'see more', 'find out more',
})

_LABEL_TRIM = ' \t\n.:;,!?«»"\'()[]<>→…·|'

# Quebec writes the sign after the amount with a no-break space (19,99 $) and
# uses the comma as decimal separator. Upstream never looked at prices.
_THIN_SPACE = '[   ]'
_AMOUNT = (
    r'\d{1,3}(?:' + _THIN_SPACE + r'\d{3})+(?:[.,]\d{1,2})?'
    r'|\d+(?:[.,]\d{1,2})?'
)
_PRICE_RE = re.compile(
    r'\$' + _THIN_SPACE + r'?(?:' + _AMOUNT + r')'
    r'|(?:' + _AMOUNT + r')' + _THIN_SPACE + r'?'
    r'(?:\$|€|(?:CAD|CAN|USD|EUR|dollars?|piastres?)\b)',
    re.IGNORECASE,
)

# A separator is required so a 10-digit order number is not read as a phone.
_SEP = r'[\s.‐‑-]'
_PHONE_RE = re.compile(
    r'(?<!\d)(?:\+?1' + _SEP + r'?)?'
    r'\(?\d{3}\)?' + _SEP + r'\d{3}' + _SEP + r'\d{4}(?!\d)'
)
_POSTAL_CODE_RE = re.compile(r'\b[A-Za-z]\d[A-Za-z][\s-]?\d[A-Za-z]\d\b')
_STREET_RE = re.compile(
    r'\b(?:rue|boulevard|boul\.|av\.|avenue|chemin|montee|rang|autoroute|'
    r'street|road|drive)\b',
    re.IGNORECASE,
)

# Matched against normalized text, so "cout" also catches "cout" spelled with
# a circumflex and "coordonnees" catches the accented spelling.
_PRICE_INTENT = (
    'prix', 'tarif', 'tarification', 'forfait', 'cout ', 'couts',
    'a partir de', 'soumission', 'devis', 'acheter', 'achetez', 'commander',
    'panier', 'abonnement', 'rabais', 'promotion', 'pricing', 'price',
    'add to cart', 'checkout', 'buy now',
)
# Only the strong forms trigger the contact check: a bare "contact" sits in
# the menu of every page of a site and would fire on all of them.
_CONTACT_INTENT = (
    'nous joindre', 'coordonnees', 'telephone', "heures d'ouverture",
    'appelez', 'prendre rendez-vous', 'sans frais', 'nous rejoindre',
    'contactez-nous', 'contact us',
)

_ALT_FILENAME_RE = re.compile(
    r'^(?:[\w\s-]+\.(?:jpe?g|png|gif|webp|svg|avif)'
    r'|(?:img|image|photo|dsc|screenshot|capture|logo|icon|banner)'
    r'[\s_-]?\d*)$',
    re.IGNORECASE,
)

_FR_STOPWORDS = (
    ' le ', ' la ', ' les ', ' des ', ' une ', ' est ', ' pour ', ' vous ',
    ' nous ', ' avec ', ' dans ', ' sur ', ' qui ', ' que ', ' plus ',
    ' votre ', ' notre ', ' cette ', ' aux ', ' sont ',
)

_TEXT_BUDGET = 400_000  # cap on stored page text, keeps memory bounded
_MAX_EXAMPLES = 5
_MAX_FIELDS = 800
_MAX_HEADINGS = 400


def _normalize(text: str) -> str:
    """Lowercase, strip accents, fold typographic apostrophes.

    The comparison lists in this module are written in that same plain form,
    so three spellings of one word land on a single key.
    """
    decomposed = unicodedata.normalize('NFD', text or '')
    stripped = ''.join(c for c in decomposed if not unicodedata.combining(c))
    return stripped.lower().replace('’', "'").replace('ʼ', "'")


def _looks_french(text: str) -> bool:
    """Cheap language guess, used only to flag a wrong `lang` attribute."""
    if len(text) < 200:
        return False
    padded = ' ' + re.sub(r'\s+', ' ', text.lower()) + ' '
    return sum(1 for word in _FR_STOPWORDS if word in padded) >= 5


class _Budget:
    """Deduction accumulator for one criterion.

    Deductions apply in the order the checks run, so the points recorded on a
    problem are the points actually taken, never a nominal weight. Once a
    criterion bottoms out the remaining problems are still reported with a
    gain of zero: they are real defects that simply recover nothing more here.

    A criterion that had nothing to measure sets `applicable` to False and
    leaves the aggregate, the way Lighthouse drops a non-applicable audit
    instead of scoring it as a pass. Without that, a page serving nothing at
    all would collect full marks for having no image without alt text.
    """

    def __init__(self, maximum: int):
        self.maximum = maximum
        self.left = maximum
        self.applicable = True
        self.problems: list[dict] = []

    def hit(self, points: int, message: str) -> None:
        applied = max(0, min(int(points), self.left))
        self.left -= applied
        self.problems.append({'message': message, 'gain': applied})


class _DocumentScan(HTMLParser):
    """One pass over served HTML, collecting everything an agent could read."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack: list[str] = []
        self.elem_count = 0
        self.text_chars = 0
        self.script_chars = 0
        self.script_tags = 0
        self.script_src = 0
        self.title = ''
        self.lang = ''
        self.landmarks: set[str] = set()
        self.jsonld: list[str] = []
        self.noscript_text: list[str] = []
        self.headings: list[dict] = []
        self.fields: list[dict] = []
        self.label_for: set[str] = set()
        self.app_roots: list[dict] = []
        self.counts = {
            'links': 0, 'links_unnamed': 0, 'links_generic': 0, 'links_dead': 0,
            'buttons': 0, 'buttons_unnamed': 0,
            'images': 0, 'images_no_alt': 0, 'images_weak_alt': 0,
            'click_widgets': 0, 'click_widgets_aria': 0,
        }
        self.examples: dict[str, list[str]] = {}
        self._text_parts: list[str] = []
        self._text_budget = _TEXT_BUDGET
        self._captures: list[dict] = []
        self._open_roots: list[dict] = []
        self._jsonld_buf: list[str] | None = None

    # -- collection ------------------------------------------------------

    def _example(self, key: str, value: str) -> None:
        bucket = self.examples.setdefault(key, [])
        value = (value or '').strip()
        if value and len(bucket) < _MAX_EXAMPLES:
            bucket.append(value[:120])

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        a = {k.lower(): (v or '') for k, v in attrs}
        self.elem_count += 1
        if tag not in _VOID_TAGS:
            self.stack.append(tag)

        role = a.get('role', '').strip().lower()
        if tag in _LANDMARK_TAGS:
            self.landmarks.add(tag)
        if role in _ROLE_TO_LANDMARK:
            self.landmarks.add(_ROLE_TO_LANDMARK[role])

        if tag == 'html':
            self.lang = a.get('lang', '').strip()
        elif tag == 'script':
            self.script_tags += 1
            if a.get('src'):
                self.script_src += 1
            if 'ld+json' in a.get('type', '').lower():
                self._jsonld_buf = []
        elif tag == 'label':
            target = a.get('for', '').strip()
            if target:
                self.label_for.add(target)
        elif tag == 'img':
            self._handle_img(a)
        elif tag in ('input', 'select', 'textarea'):
            self._handle_field(tag, a)

        if tag in _CAPTURED_TAGS:
            self._captures.append({'tag': tag, 'attrs': a, 'buf': []})

        if 'onclick' in a and tag not in _NATIVE_INTERACTIVE:
            if role or 'tabindex' in a:
                self.counts['click_widgets_aria'] += 1
            else:
                self.counts['click_widgets'] += 1
                self._example('click_widgets', a.get('class') or tag)

        node_id = a.get('id', '').strip().lower()
        if node_id in _APP_ROOT_IDS and tag not in _VOID_TAGS:
            self._open_roots.append({
                'id': node_id,
                'depth': len(self.stack),
                'text_at': self.text_chars,
                'elem_at': self.elem_count,
            })

    def _handle_img(self, a: dict) -> None:
        self.counts['images'] += 1
        alt = a.get('alt')
        if alt is None:
            decorative = (
                a.get('aria-hidden', '').lower() == 'true'
                or a.get('role', '').lower() in ('presentation', 'none')
            )
            if not decorative:
                self.counts['images_no_alt'] += 1
                self._example('images_no_alt', a.get('src', ''))
            return
        alt = alt.strip()
        if not alt:
            return
        if _ALT_FILENAME_RE.match(alt):
            self.counts['images_weak_alt'] += 1
            self._example('images_weak_alt', alt)
        # An image inside a link or a button lends its alt to that name.
        for cap in self._captures:
            cap['buf'].append(alt)

    def _handle_field(self, tag: str, a: dict) -> None:
        if len(self.fields) >= _MAX_FIELDS:
            return
        self.fields.append({
            'tag': tag,
            'type': a.get('type', '').strip().lower(),
            'id': a.get('id', '').strip(),
            'name': a.get('name', '').strip(),
            'aria_label': a.get('aria-label', '').strip(),
            'aria_labelledby': a.get('aria-labelledby', '').strip(),
            'title': a.get('title', '').strip(),
            'placeholder': a.get('placeholder', '').strip(),
            'value': a.get('value', '').strip(),
            'wrapped': 'label' in self.stack,
        })

    def handle_data(self, data):
        if not data:
            return
        top = self.stack[-1] if self.stack else ''
        if top == 'script':
            self.script_chars += len(data)
            if self._jsonld_buf is not None:
                self._jsonld_buf.append(data)
            return
        if top == 'style':
            return
        stripped = data.strip()
        if not stripped:
            return
        if top == 'title':
            # An <svg><title> names its control, it is not the document title.
            if 'svg' in self.stack:
                for cap in self._captures:
                    cap['buf'].append(stripped)
            else:
                self.title = (self.title + ' ' + stripped).strip()
            return
        if 'noscript' in self.stack:
            self.noscript_text.append(stripped)
            return
        if 'template' in self.stack:
            # Browsers never render template content, so agents cannot use it.
            return

        self.text_chars += len(stripped)
        if self._text_budget > 0:
            self._text_parts.append(stripped)
            self._text_budget -= len(stripped)
        for cap in self._captures:
            cap['buf'].append(stripped)

    def handle_endtag(self, tag):
        tag = tag.lower()
        for i in range(len(self._captures) - 1, -1, -1):
            if self._captures[i]['tag'] == tag:
                self._finish_capture(self._captures.pop(i))
                break
        if tag == 'script':
            self._flush_jsonld()
        if tag in _VOID_TAGS:
            return
        if tag in self.stack:
            while self.stack:
                if self.stack.pop() == tag:
                    break
            self._close_roots(len(self.stack))

    def _flush_jsonld(self) -> None:
        if self._jsonld_buf is not None:
            raw = ''.join(self._jsonld_buf).strip()
            if raw:
                self.jsonld.append(raw)
            self._jsonld_buf = None

    def _close_roots(self, depth: int) -> None:
        while self._open_roots and self._open_roots[-1]['depth'] > depth:
            root = self._open_roots.pop()
            self.app_roots.append({
                'id': root['id'],
                'text_chars': self.text_chars - root['text_at'],
                'elements': self.elem_count - root['elem_at'],
            })

    def _finish_capture(self, cap: dict) -> None:
        a = cap['attrs']
        tag = cap['tag']
        text = ' '.join(cap['buf']).strip()
        name = text or a.get('aria-label', '').strip() or a.get('title', '').strip()

        if tag in _HEADING_TAGS:
            if len(self.headings) < _MAX_HEADINGS:
                self.headings.append({'level': int(tag[1]), 'text': text[:200]})
            return

        hidden = a.get('aria-hidden', '').lower() == 'true'
        if tag == 'a':
            href = a.get('href')
            if href is None or hidden:
                return
            self.counts['links'] += 1
            if not name:
                self.counts['links_unnamed'] += 1
                self._example('links_unnamed', href or '(sans href)')
                return
            if _normalize(name).strip(_LABEL_TRIM) in _GENERIC_LABELS:
                self.counts['links_generic'] += 1
                self._example('links_generic', name)
            target = href.strip().lower()
            if target in ('', '#') or target.startswith('javascript:'):
                self.counts['links_dead'] += 1
                self._example('links_dead', name)
        elif tag == 'button':
            if hidden:
                return
            self.counts['buttons'] += 1
            if not name and not a.get('value', '').strip():
                self.counts['buttons_unnamed'] += 1
                self._example('buttons_unnamed', a.get('class') or '(sans classe)')

    def finish(self) -> '_DocumentScan':
        """Close the parser and settle whatever the document left open."""
        try:
            self.close()
        except Exception:  # noqa: BLE001 - malformed markup must not fail an audit
            pass
        self._flush_jsonld()
        for cap in list(self._captures):
            self._finish_capture(cap)
        self._captures.clear()
        self._close_roots(0)
        return self

    @property
    def text(self) -> str:
        return ' '.join(self._text_parts)


def _scan(html: str) -> _DocumentScan:
    scan = _DocumentScan()
    try:
        scan.feed(html or '')
    except Exception:  # noqa: BLE001 - same posture as above
        pass
    return scan.finish()


def _jsonld_facts(blocks: list[str]) -> dict:
    """Read @type values and price presence out of the JSON-LD blocks."""
    types: set[str] = set()
    has_price = False
    for raw in blocks:
        try:
            data = json.loads(raw)
        except (ValueError, TypeError):
            continue
        pending = [data]
        seen = 0
        while pending and seen < 5000:
            node = pending.pop()
            seen += 1
            if isinstance(node, dict):
                declared = node.get('@type')
                declared = [declared] if isinstance(declared, str) else declared or []
                for value in declared:
                    if isinstance(value, str):
                        types.add(value.lower())
                for key, value in node.items():
                    if key.lower() in ('price', 'lowprice', 'highprice',
                                       'pricerange'):
                        has_price = True
                    pending.append(value)
            elif isinstance(node, list):
                pending.extend(node)
    return {'types': types, 'has_price': has_price, 'blocks': len(blocks)}


# ---------------------------------------------------------------------------
# Criteria
# ---------------------------------------------------------------------------

def _score_semantique(scan: _DocumentScan, ctx: dict, budget: _Budget) -> dict:
    marks = scan.landmarks
    if 'main' not in marks:
        budget.hit(6, 'Aucun <main> (ni role="main"). L\'agent ne peut pas '
                      'séparer le contenu principal du menu et du pied de page.')
    if not scan.title:
        budget.hit(4, 'Aucun <title> lisible. C\'est la première chose que lit '
                      'un agent pour nommer la page.')
    if 'nav' not in marks:
        budget.hit(3, 'Aucun <nav> (ni role="navigation"). La navigation du site '
                      'n\'est pas identifiable.')
    if not scan.lang:
        budget.hit(3, 'L\'attribut lang manque sur <html>. Ajoute lang="fr-CA" '
                      'pour annoncer la langue du contenu.')
    elif ctx['french'] and _normalize(scan.lang).startswith('en'):
        budget.hit(3, f'Le contenu est en français mais <html lang="{scan.lang}"> '
                      'annonce l\'anglais. Corrige en lang="fr-CA".')
    if 'header' not in marks:
        budget.hit(2, 'Aucun <header> (ni role="banner"). L\'en-tête de page '
                      'n\'est pas délimité.')
    if 'footer' not in marks:
        budget.hit(2, 'Aucun <footer> (ni role="contentinfo"). Les informations '
                      'de bas de page ne sont pas délimitées.')
    if not (marks & {'article', 'section', 'main'}):
        budget.hit(3, 'Aucun conteneur de contenu (<article>, <section>, <main>). '
                      'La page est une suite de <div> sans structure.')
    return {
        'reperes_trouves': sorted(marks),
        'title': scan.title[:200],
        'lang': scan.lang,
        'contenu_francais': ctx['french'],
    }


def _score_hierarchie_titres(scan: _DocumentScan, ctx: dict,
                             budget: _Budget) -> dict:
    headings = scan.headings
    levels = [h['level'] for h in headings]
    h1_count = levels.count(1)
    empty = sum(1 for h in headings if not h['text'])
    skips = []
    previous = 0
    for level in levels:
        if previous and level > previous + 1:
            skips.append((previous, level))
        previous = level

    if not headings:
        budget.hit(20, 'Aucun titre <h1>-<h6> dans la page. Un agent n\'a aucun '
                       'plan de lecture, il ne voit qu\'un bloc de texte.')
        return {'nb_titres': 0, 'nb_h1': 0, 'sauts': [], 'titres_vides': 0,
                'plan': []}

    if h1_count == 0:
        budget.hit(8, 'Aucun <h1>. Ajoute un titre principal unique qui dit de '
                      'quoi parle la page.')
    elif h1_count > 1:
        budget.hit(4, f'{h1_count} <h1> dans la page. Garde un seul titre '
                      'principal et passe les autres en <h2>.')
    if skips:
        details = ', '.join(f'h{a} vers h{b}' for a, b in skips[:3])
        budget.hit(min(6, 3 * len(skips)),
                   f'Niveaux de titres sautés ({details}). Descends la hiérarchie '
                   'un cran à la fois pour que le plan de la page reste lisible.')
    if empty:
        budget.hit(min(4, 2 * empty),
                   f'{empty} titre(s) sans texte. Un titre vide occupe une place '
                   'dans le plan sans rien annoncer.')
    return {
        'nb_titres': len(headings),
        'nb_h1': h1_count,
        'sauts': [f'h{a}->h{b}' for a, b in skips],
        'titres_vides': empty,
        'plan': [f"h{h['level']}: {h['text'][:80]}" for h in headings[:20]],
    }


def _field_label(field: dict, label_for: set[str]) -> str:
    """Return 'ok', 'placeholder' or 'none' for one form field."""
    if field['aria_label'] or field['aria_labelledby'] or field['title']:
        return 'ok'
    if field['tag'] == 'input':
        kind = field['type']
        if kind in ('submit', 'reset'):
            return 'ok'  # the browser supplies a default label
        if kind == 'button':
            return 'ok' if field['value'] else 'none'
    if field['wrapped']:
        return 'ok'
    if field['id'] and field['id'] in label_for:
        return 'ok'
    if field['placeholder']:
        return 'placeholder'
    return 'none'


def _score_elements_interactifs(scan: _DocumentScan, ctx: dict,
                                budget: _Budget) -> dict:
    counts = scan.counts
    visible_fields = [
        f for f in scan.fields
        if not (f['tag'] == 'input' and f['type'] == 'hidden')
    ]
    states = [_field_label(f, scan.label_for) for f in visible_fields]
    unlabeled = states.count('none')
    placeholder_only = states.count('placeholder')

    if unlabeled:
        budget.hit(min(10, 4 * unlabeled),
                   f'{unlabeled} champ(s) de formulaire sans étiquette. Relie '
                   'chaque champ à un <label for="id"> ou donne-lui un '
                   'aria-label : sans ça, l\'agent ne sait pas quoi y écrire.')
    if counts['click_widgets']:
        budget.hit(min(8, 4 * counts['click_widgets']),
                   f"{counts['click_widgets']} élément(s) cliquable(s) "
                   'construit(s) en <div>/<span> avec onclick, sans role ni '
                   'tabindex. Utilise <button> ou <a href> : sinon l\'agent ne '
                   'voit rien à cliquer.')
    if counts['links_unnamed']:
        budget.hit(min(8, 3 * counts['links_unnamed']),
                   f"{counts['links_unnamed']} lien(s) sans libellé (souvent une "
                   'icône seule). Ajoute du texte ou un aria-label qui dit où '
                   'mène le lien.')
    if counts['buttons_unnamed']:
        budget.hit(min(6, 3 * counts['buttons_unnamed']),
                   f"{counts['buttons_unnamed']} bouton(s) sans libellé. Un "
                   'bouton sans nom est une action que l\'agent ne peut pas '
                   'déclencher.')
    if placeholder_only:
        budget.hit(min(4, 2 * placeholder_only),
                   f'{placeholder_only} champ(s) identifié(s) par le seul '
                   'placeholder. Le placeholder disparaît à la saisie, il ne '
                   'remplace pas une étiquette.')
    if counts['links_generic']:
        budget.hit(min(3, counts['links_generic']),
                   f"{counts['links_generic']} lien(s) au libellé vague "
                   '("cliquez ici", "en savoir plus"). Nomme la destination dans '
                   'le texte du lien.')
    if counts['links_dead']:
        budget.hit(min(3, counts['links_dead']),
                   f"{counts['links_dead']} lien(s) sans destination réelle "
                   '(href="#" ou javascript:). L\'agent ne peut pas les suivre.')
    if not counts['links'] and not counts['buttons'] and not visible_fields:
        # Heavier than the individual defects above: the rest of this
        # criterion passes by default when there is nothing to check.
        budget.hit(12, 'Aucun élément actionnable dans le HTML servi : ni lien, '
                       'ni bouton, ni champ. L\'agent arrive sur la page et ne '
                       'peut ni agir ni continuer sa navigation.')
    return {
        'nb_liens': counts['links'],
        'liens_sans_libelle': counts['links_unnamed'],
        'liens_libelle_vague': counts['links_generic'],
        'liens_sans_destination': counts['links_dead'],
        'nb_boutons': counts['buttons'],
        'boutons_sans_libelle': counts['buttons_unnamed'],
        'nb_champs': len(visible_fields),
        'champs_sans_etiquette': unlabeled,
        'champs_placeholder_seul': placeholder_only,
        'widgets_div_onclick': counts['click_widgets'],
        'widgets_div_avec_aria': counts['click_widgets_aria'],
        'exemples': {
            k: v for k, v in scan.examples.items()
            if k.startswith(('links_', 'buttons_', 'click_'))
        },
    }


def _score_images_alt(scan: _DocumentScan, ctx: dict, budget: _Budget) -> dict:
    counts = scan.counts
    total = counts['images']
    missing = counts['images_no_alt']
    weak = counts['images_weak_alt']
    if not total:
        budget.applicable = False
    if total and missing:
        budget.hit(max(1, round(budget.maximum * missing / total)),
                   f'{missing} image(s) sur {total} sans attribut alt. Décris ce '
                   'que montre l\'image, ou mets alt="" si elle est purement '
                   'décorative.')
    if total and weak:
        # Half weight: an alt repeating the filename exists but says nothing.
        budget.hit(max(1, round(budget.maximum * weak / total / 2)),
                   f'{weak} image(s) dont le alt reprend le nom de fichier '
                   '("photo1.jpg"). Remplace-le par une description utile.')
    return {
        'nb_images': total,
        'sans_alt': missing,
        'alt_non_informatif': weak,
        'exemples': {
            k: v for k, v in scan.examples.items() if k.startswith('images_')
        },
    }


def _score_contenu_sans_js(scan: _DocumentScan, ctx: dict,
                           budget: _Budget) -> dict:
    text_chars = scan.text_chars
    empty_root = ctx['empty_root']
    js_heavy = bool(empty_root or scan.script_src >= 3 or scan.script_chars > 2000)
    noscript = _normalize(' '.join(scan.noscript_text))
    noscript_warns = bool(
        'javascript' in noscript
        and re.search(r'activ|enable|require|besoin|fonctionner', noscript)
    )

    if text_chars < 200:
        if js_heavy:
            budget.hit(15, f'Le HTML servi ne contient que {text_chars} '
                           'caractères de texte alors que la page charge du '
                           'JavaScript : le contenu n\'existe qu\'après '
                           'exécution. Un agent qui récupère l\'URL sans '
                           'navigateur ne voit rien.')
        else:
            budget.hit(6, f'Le HTML servi ne contient que {text_chars} caractères '
                          'de texte. Il n\'y a presque rien à lire pour un agent.')
    elif js_heavy and text_chars < 800:
        budget.hit(8, f'Seulement {text_chars} caractères de texte dans le HTML '
                      'servi, pour une page qui dépend du JavaScript. Rends au '
                      'moins le contenu principal disponible côté serveur.')
    elif text_chars < 400:
        # Short is not the same as broken: a page with no scripts that serves
        # little text is thin, not JavaScript-dependent.
        budget.hit(3, f'Page très courte ({text_chars} caractères de texte). '
                      'Vérifie qu\'un agent y trouve de quoi répondre.')
    elif empty_root:
        budget.hit(10, 'Le conteneur applicatif du HTML servi est vide : la page '
                       'est une coquille remplie par le JavaScript. Active le '
                       'rendu côté serveur ou le prérendu.')
    elif scan.script_chars > 8 * text_chars and text_chars < 3000:
        budget.hit(4, 'Le HTML servi contient beaucoup plus de code que de texte. '
                      'Le contenu utile est probablement assemblé par le '
                      'JavaScript.')
    if noscript_warns and text_chars < 3000:
        budget.hit(3, 'Le <noscript> demande d\'activer le JavaScript : c\'est '
                      'l\'aveu que le contenu n\'est pas dans le HTML servi.')
    return {
        'caracteres_de_texte': text_chars,
        'nb_scripts': scan.script_tags,
        'scripts_externes': scan.script_src,
        'conteneur_applicatif_vide': empty_root,
        'conteneurs_applicatifs': scan.app_roots,
        'noscript_exige_js': noscript_warns,
    }


def _score_infos_cles(scan: _DocumentScan, ctx: dict, budget: _Budget) -> dict:
    ld = ctx['jsonld']
    flat = ctx['flat_text']
    price_hits = len(_PRICE_RE.findall(scan.text))
    commercial = bool(
        any(word in flat for word in _PRICE_INTENT)
        or ld['types'] & {'product', 'offer', 'aggregateoffer', 'service'}
    )
    phone_hits = len(_PHONE_RE.findall(scan.text))
    address_hit = bool(
        _POSTAL_CODE_RE.search(scan.text) or _STREET_RE.search(scan.text)
    )
    contact_intent = any(word in flat for word in _CONTACT_INTENT)

    if scan.text_chars < 200 and not ld['blocks']:
        # No text and no structured data leaves nothing to read at all. Said
        # first, otherwise an empty page passes the checks below by default.
        budget.hit(budget.maximum,
                   'Aucune information lisible dans le HTML servi : ni prix, ni '
                   'coordonnées, ni données structurées. L\'agent n\'a rien à '
                   'citer de cette page.')
    if commercial and not price_hits and not ld['has_price']:
        budget.hit(5, 'La page parle d\'achat ou de tarifs mais aucun montant '
                      'lisible n\'apparaît dans le HTML servi. Écris le prix en '
                      'texte (ex. "49 $ par mois") plutôt que dans une image ou '
                      'un widget chargé après coup.')
    if contact_intent and not phone_hits and not address_hit:
        budget.hit(3, 'La page annonce des coordonnées mais ni téléphone ni '
                      'adresse ne sont lisibles en texte. Un agent qui doit '
                      'joindre l\'entreprise reste bloqué.')
    if not ld['blocks']:
        budget.hit(2, 'Aucun bloc JSON-LD dans la page. Les données structurées '
                      'sont le seul canal où l\'agent lit une information sans '
                      'avoir à l\'interpréter.')
    return {
        'page_commerciale': commercial,
        'prix_lisibles': price_hits,
        'prix_dans_donnees_structurees': ld['has_price'],
        'telephones_lisibles': phone_hits,
        'adresse_lisible': address_hit,
        'intention_contact': contact_intent,
        'blocs_jsonld': ld['blocks'],
        'types_jsonld': sorted(ld['types']),
    }


_SCORERS = {
    'semantique': _score_semantique,
    'hierarchie_titres': _score_hierarchie_titres,
    'elements_interactifs': _score_elements_interactifs,
    'images_alt': _score_images_alt,
    'contenu_sans_js': _score_contenu_sans_js,
    'infos_cles': _score_infos_cles,
}

# Keys stay machine-stable, the French prose is what callers display.
_RESUMES = {
    'excellent': 'Un agent IA lit cette page sans difficulté : structure, '
                 'libellés et contenu sont dans le HTML servi.',
    'bon': 'Un agent IA comprend l\'essentiel de cette page, quelques points '
           'lui échappent encore.',
    'a_ameliorer': 'Un agent IA ne saisit qu\'une partie de cette page : '
                   'plusieurs repères lui manquent.',
    'critique': 'Un agent IA comprend très peu de cette page. Elle est '
                'pratiquement invisible pour une recherche assistée par IA.',
}


def _niveau(score: int) -> str:
    if score >= 85:
        return 'excellent'
    if score >= 70:
        return 'bon'
    if score >= 50:
        return 'a_ameliorer'
    return 'critique'


def _priorite(gain: int) -> str:
    if gain >= 8:
        return 'haute'
    if gain >= 4:
        return 'moyenne'
    return 'basse'


def check_agent_readability(html: str, url: str = '') -> dict:
    """Score how much of a page an AI agent or a screen reader can understand.

    Reads the HTML exactly as served, with no rendering and no network call,
    which is the view an agent gets when it fetches a URL without a browser.
    Returns a 0-100 score, the per-criterion detail, and French
    recommendations sorted by the points each one recovers.
    """
    scan = _scan(html)
    text = scan.text
    ctx = {
        'french': _looks_french(text),
        'flat_text': _normalize(text),
        'jsonld': _jsonld_facts(scan.jsonld),
        # A near-empty SPA mount only means "JS shell" when the rest of the
        # document is thin too, otherwise the content simply lives elsewhere.
        'empty_root': (any(root['text_chars'] < 100 for root in scan.app_roots)
                       and scan.text_chars < 3000),
    }

    criteres: dict[str, dict] = {}
    recommandations: list[dict] = []
    earned = 0
    possible = 0
    for key, libelle, maximum in CRITERIA:
        budget = _Budget(maximum)
        constats = _SCORERS[key](scan, ctx, budget)
        if budget.applicable:
            earned += budget.left
            possible += maximum
        criteres[key] = {
            'libelle': libelle,
            'score': budget.left,
            'max': maximum,
            'applicable': budget.applicable,
            'constats': constats,
            'problemes': budget.problems,
        }
        for problem in budget.problems:
            recommandations.append({
                'critere': key,
                'libelle': libelle,
                'priorite': _priorite(problem['gain']),
                'gain': problem['gain'],
                'message': problem['message'],
            })

    recommandations.sort(key=lambda r: -r['gain'])
    score = round(100 * earned / possible) if possible else 0
    score = max(0, min(100, score))
    niveau = _niveau(score)
    return {
        'url': url,
        'score': score,
        'niveau': niveau,
        'points_applicables': possible,
        'resume': f'{_RESUMES[niveau]} ({score}/100)',
        'criteres': criteres,
        'recommandations': recommandations,
    }
