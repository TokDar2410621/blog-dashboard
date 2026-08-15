"""JSON-LD validation gate, run before a page or an article goes live.

Ported from claude-seo v2.2.4 `hooks/validate-schema.py`.
Copyright (c) 2025 Daniel Agrici (AgriciDaniel). MIT.
https://github.com/AgriciDaniel/claude-seo

Upstream is a Claude Code hook: it greps `<script type="application/ld+json">`
out of the file it just edited, prints to stdout and exits 2 to block the
write. Gridar needs the same rules as a library call on the object it is
about to store or ship, so this port takes the parsed data and returns
structured issues instead of exiting, and it keeps the HTML entry point as
a thin wrapper. The rule set is widened well past upstream's quartet of
@context, @type, placeholders and dead types: required fields per type,
absolute-URL and ISO-8601 checks, plus the Quebec French side upstream has
no reason to carry (placeholders written `[Ville]` or `[Telephone]`, prices
written `19,99 $`, `inLanguage` left at a bare `fr`, phone numbers without
the +1). FAQPage is reported at warning level, never as an error: Google
retired FAQ rich results on 2026-05-07, yet the type still feeds answer
extraction by the AI engines Gridar targets.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

__all__ = [
    'ERROR',
    'WARNING',
    'validate_jsonld',
    'validate_html_jsonld',
    'has_blocking_errors',
]

ERROR = 'error'
WARNING = 'warning'

# Bounds. A JSONField coming back from Postgres is caller-controlled data,
# and the caller is often an LLM, so neither the depth nor the node count
# can be assumed sane.
_MAX_ISSUES = 200
_MAX_NODES = 2000
_MAX_DEPTH = 16


# ---------------------------------------------------------------------------
# Vocabulary tables
# ---------------------------------------------------------------------------

# Retired from Google rich results and not replaced. Emitting one in 2026
# means the generator is working from a stale template, which is why these
# are errors and FAQPage is not.
_DEAD_TYPES = {
    'HowTo': 'rich results supprimes en septembre 2023, le balisage ne produit plus rien',
    'SpecialAnnouncement': 'deprecie le 31 juillet 2025, plus traite par Google',
    'CourseInfo': 'retire en juin 2025, fusionne dans Course',
    'EstimatedSalary': 'retire en juin 2025',
    'LearningVideo': 'retire en juin 2025, utiliser VideoObject',
    'ClaimReview': 'retire en juin 2025, les rich results fact-check sont abandonnes',
    'VehicleListing': 'retire en juin 2025',
    'Vehicle': 'retire en juin 2025 (Vehicle Listing)',
}

# Still valid vocabulary, but no Google SERP feature. Worth publishing for
# other reasons, so the caller is told rather than blocked.
_WEAKENED_TYPES = {
    'FAQPage': (
        'Google a retire les rich results FAQ le 7 mai 2026, cette page '
        'n obtiendra aucun affichage enrichi. Le type reste valide et utile '
        'pour l extraction par les moteurs IA, on le garde.'
    ),
    'Dataset': (
        'aucun rich result dans la recherche Google, le balisage n est lu '
        'que par Dataset Search'
    ),
    'Book': (
        'les Book Actions sont depreciees depuis juin 2025, verifier qu une '
        'source primaire confirme encore le support'
    ),
}

# Subtypes routed to a parent rule set. Restricted to the verticals Gridar
# actually generates for at the moment: local trades, clinics, restaurants.
_TYPE_PARENTS = {
    'BlogPosting': 'Article',
    'NewsArticle': 'Article',
    'TechArticle': 'Article',
    'Report': 'Article',
    'AdvertiserContentArticle': 'Article',
    'Restaurant': 'LocalBusiness',
    'Dentist': 'LocalBusiness',
    'Physician': 'LocalBusiness',
    'MedicalClinic': 'LocalBusiness',
    'LegalService': 'LocalBusiness',
    'AccountingService': 'LocalBusiness',
    'Plumber': 'LocalBusiness',
    'Electrician': 'LocalBusiness',
    'RoofingContractor': 'LocalBusiness',
    'HVACBusiness': 'LocalBusiness',
    'GeneralContractor': 'LocalBusiness',
    'HomeAndConstructionBusiness': 'LocalBusiness',
    'MovingCompany': 'LocalBusiness',
    'AutoRepair': 'LocalBusiness',
    'RealEstateAgent': 'LocalBusiness',
    'BeautySalon': 'LocalBusiness',
    'HairSalon': 'LocalBusiness',
    'ProfessionalService': 'LocalBusiness',
    'Store': 'LocalBusiness',
    'FinancialService': 'LocalBusiness',
    'ChildCare': 'LocalBusiness',
    'Landscaper': 'LocalBusiness',
    'Locksmith': 'LocalBusiness',
    'PestControlService': 'LocalBusiness',
    'FoodEstablishment': 'LocalBusiness',
    'OnlineBusiness': 'Organization',
    'Corporation': 'Organization',
    'NGO': 'Organization',
    'EducationalOrganization': 'Organization',
    'SportsOrganization': 'Organization',
}

_REQUIRED_FIELDS = {
    'Article': ('headline', 'author', 'datePublished'),
    'Product': ('name', 'image', 'offers'),
    'LocalBusiness': ('name', 'address', 'telephone'),
    'FAQPage': ('mainEntity',),
    'Service': ('name', 'provider'),
    'BreadcrumbList': ('itemListElement',),
    'Organization': ('name',),
    'Person': ('name',),
    'Question': ('name', 'acceptedAnswer'),
    'Answer': ('text',),
    'Offer': ('price', 'priceCurrency'),
    'PostalAddress': ('addressLocality', 'addressCountry'),
    'WebSite': ('name', 'url'),
    'Event': ('name', 'startDate', 'location'),
    'VideoObject': ('name', 'thumbnailUrl', 'uploadDate'),
    'ImageObject': ('url',),
    'AggregateRating': ('ratingValue', 'ratingCount'),
    'Review': ('reviewRating', 'author'),
}

_RECOMMENDED_FIELDS = {
    'Article': ('image', 'dateModified', 'publisher', 'inLanguage'),
    'Product': ('description', 'brand', 'sku'),
    'LocalBusiness': ('url', 'openingHoursSpecification', 'geo', 'priceRange', 'image'),
    'FAQPage': ('inLanguage',),
    'Service': ('areaServed', 'description'),
    'Organization': ('url', 'logo'),
    'Offer': ('availability', 'url'),
    'PostalAddress': ('streetAddress', 'addressRegion', 'postalCode'),
    'WebPage': ('name', 'description', 'inLanguage'),
    'Event': ('endDate', 'offers'),
}

# Types this module knows by name. Used only to catch a casing slip such as
# "localBusiness", which parses as JSON but names nothing in the vocabulary.
_KNOWN_TYPES = frozenset(
    set(_DEAD_TYPES)
    | set(_WEAKENED_TYPES)
    | set(_TYPE_PARENTS)
    | set(_REQUIRED_FIELDS)
    | set(_RECOMMENDED_FIELDS)
    | {
        'Thing', 'CreativeWork', 'Blog', 'CollectionPage', 'AboutPage',
        'ContactPage', 'ProfilePage', 'QAPage', 'SearchResultsPage',
        'SoftwareApplication', 'WebApplication', 'MobileApplication',
        'ItemList', 'ListItem', 'OfferCatalog', 'AggregateOffer',
        'GeoCoordinates', 'OpeningHoursSpecification', 'ContactPoint',
        'Place', 'PostalAddress', 'Brand', 'Course', 'JobPosting',
        'DiscussionForumPosting', 'ProductGroup', 'MerchantReturnPolicy',
        'OfferShippingDetails', 'MonetaryAmount', 'PriceSpecification',
        'Audience', 'AdministrativeArea', 'City', 'State', 'Country',
        'Menu', 'MenuItem', 'Rating', 'Speakable', 'SpeakableSpecification',
        'HowToStep', 'Quiz', 'MediaObject', 'AudioObject', 'Occupation',
    }
)
_KNOWN_TYPES_BY_LOWER = {t.lower(): t for t in _KNOWN_TYPES}

# Keys whose value must resolve on its own, from any page, without a base URL.
_ABSOLUTE_URL_KEYS = frozenset({
    'url', 'contentUrl', 'embedUrl', 'thumbnailUrl', 'logo', 'image',
    'sameAs', 'item', 'downloadUrl', 'installUrl', 'primaryImageOfPage',
    'significantLink', 'relatedLink', 'discussionUrl', 'archivedAt',
})

_DATE_KEYS = frozenset({
    'datePublished', 'dateModified', 'dateCreated', 'uploadDate',
    'startDate', 'endDate', 'validFrom', 'validThrough', 'priceValidUntil',
    'datePosted', 'foundingDate', 'availabilityStarts', 'availabilityEnds',
    'expires', 'temporalCoverage', 'dateIssued',
})

# A bare dict here is almost always a shape bug: schema.org consumers need
# the @type to know what the nested object is.
_KEYS_EXPECTING_TYPED_OBJECT = frozenset({
    'author', 'publisher', 'address', 'offers', 'geo', 'mainEntity',
    'acceptedAnswer', 'suggestedAnswer', 'provider', 'brand', 'review',
    'aggregateRating', 'contactPoint', 'itemListElement', 'location',
    'hasMerchantReturnPolicy', 'shippingDetails', 'areaServed',
    'mainEntityOfPage', 'reviewRating', 'seller', 'performer', 'organizer',
})


# ---------------------------------------------------------------------------
# Placeholder detection
# ---------------------------------------------------------------------------

# Uppercase-only on purpose for the marker words. "replace" and "a remplir"
# are ordinary French and English copy in lowercase, so matching them
# case-insensitively would flag legitimate sentences such as "formulaire a
# remplir en ligne".
_PLACEHOLDER_PATTERNS = (
    re.compile(r'\{\{[^{}]{1,60}\}\}'),
    re.compile(r'\$\{[^{}]{1,60}\}'),
    re.compile(r'(?<![\w{}$])\{[A-Za-z_][A-Za-z0-9_.\- ]{0,40}\}(?!\})'),
    re.compile(r'%[A-Z][A-Z0-9_]{1,30}%'),
    re.compile(r'<%[^%]{1,40}%>'),
    re.compile(r'\b(?:TODO|FIXME|TBD|XXX+|REPLACE|REPLACE_ME|INSERT)\b'),
    re.compile(
        r'\b(?:A|À)\s+(?:REMPLIR|COMPLETER|COMPLÉTER|DEFINIR|DÉFINIR'
        r'|DETERMINER|DÉTERMINER|VALIDER)\b'
    ),
    re.compile(r'lorem\s+ipsum', re.IGNORECASE),
    re.compile(r'\b(?:exemple|example|domaine|domain)\.(?:com|org|net|ca)\b', re.IGNORECASE),
    re.compile(
        r'\b(?:votresite|votre-site|votredomaine|votre-domaine|monsite|mon-site'
        r'|yoursite|your-site|yourdomain|your-domain|mysite)\b',
        re.IGNORECASE,
    ),
    re.compile(r'\bplaceholder\b', re.IGNORECASE),
)

# A bracketed short label with no sentence punctuation: [City], [Ville],
# [Nom de l entreprise], [YYYY-MM-DD]. The character class admits no comma,
# period, colon or question mark, so a bracketed sentence never matches.
_BRACKET_PLACEHOLDER_RE = re.compile(
    r'\[[A-Za-zÀ-ÖØ-öø-ÿ0-9 _/\'’+-]{2,40}\]'
)
# Second gate on the bracket rule, because bracketed prose does occur in
# real FAQ answers and a false error would block a good page. A template
# label either opens on a capital or a digit ([Ville], [YYYY-MM-DD]) or
# names a field the generator was meant to substitute.
_BRACKET_HINT_RE = re.compile(
    r'\b(?:ville|city|state|province|region|phone|telephone|téléphone|adresse'
    r'|address|nom|name|business|entreprise|commerce|courriel|email|mail|url'
    r'|site|insert|inserer|insérer|your|votre|yyyy|mm|dd|prix|price|zip'
    r'|postal|company|title|titre|date|auteur|author)\b',
    re.IGNORECASE,
)
_OPENS_LIKE_LABEL_RE = re.compile(r'^[A-ZÀ-Ö0-9]')


def _find_placeholders(value: str) -> list[str]:
    """Return the template markers left in a string value, deduped."""
    found: list[str] = []
    seen: set[str] = set()

    for pattern in _PLACEHOLDER_PATTERNS:
        for match in pattern.findall(value):
            snippet = match if isinstance(match, str) else match[0]
            if snippet and snippet not in seen:
                seen.add(snippet)
                found.append(snippet)

    for match in _BRACKET_PLACEHOLDER_RE.findall(value):
        inner = match[1:-1].strip()
        if not (_OPENS_LIKE_LABEL_RE.match(inner) or _BRACKET_HINT_RE.search(inner)):
            continue
        if match not in seen:
            seen.add(match)
            found.append(match)

    return found[:4]


# ---------------------------------------------------------------------------
# Value-level checks
# ---------------------------------------------------------------------------

_ISO_DATE_RE = re.compile(
    r'^\d{4}-\d{2}-\d{2}'
    r'(?:[T ]\d{2}:\d{2}(?::\d{2}(?:\.\d{1,6})?)?'
    r'(?:Z|z|[+-]\d{2}:?\d{2})?)?$'
)
_LANG_TAG_RE = re.compile(r'^[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*$')
_PLAIN_NUMBER_RE = re.compile(r'^\d+(?:\.\d+)?$')
_TYPE_NAME_RE = re.compile(r'^[A-Z][A-Za-z0-9]*$')


def _is_empty(value) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, dict, set)):
        return len(value) == 0
    return False


def _url_verdict(value: str) -> tuple[str, str] | None:
    """Return (level, reason) when the URL is unusable in JSON-LD, else None."""
    raw = value.strip()
    if raw.startswith('//'):
        return ERROR, 'URL sans protocole (commence par //)'
    if raw.startswith('data:'):
        return ERROR, 'URL en data: URI, les moteurs ne la suivent pas'

    parsed = urlparse(raw)
    if not parsed.scheme:
        return ERROR, 'URL relative, une URL absolue est exigee'
    if parsed.scheme not in ('http', 'https'):
        return ERROR, f'protocole « {parsed.scheme} » refuse, http ou https attendu'
    if not parsed.netloc:
        return ERROR, 'URL sans nom de domaine'
    host = parsed.hostname or ''
    if '.' not in host:
        return ERROR, f'domaine « {host} » incomplet'
    if parsed.scheme == 'http':
        return WARNING, 'URL en http, la version https est attendue'
    return None


def _parse_iso(value: str) -> datetime | None:
    raw = value.strip()
    if not _ISO_DATE_RE.match(raw):
        return None
    normalized = raw.replace(' ', 'T').replace('z', 'Z')
    if normalized.endswith('Z'):
        normalized = normalized[:-1] + '+00:00'
    if len(normalized) == 10:
        normalized += 'T00:00:00'
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


# ---------------------------------------------------------------------------
# Walk
# ---------------------------------------------------------------------------

class _Report:
    def __init__(self):
        self.issues: list[dict] = []
        self.nodes = 0
        self.truncated = False

    def add(self, level: str, path: str, message: str) -> None:
        if len(self.issues) >= _MAX_ISSUES:
            self.truncated = True
            return
        self.issues.append({'level': level, 'path': path, 'message': message})


def _node_types(node: dict) -> list[str]:
    """Every @type on a node, with the IRI and prefix forms normalized away."""
    raw = node.get('@type')
    values = raw if isinstance(raw, list) else [raw]
    types: list[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        name = value.strip()
        for prefix in ('https://schema.org/', 'http://schema.org/', 'schema:'):
            if name.startswith(prefix):
                name = name[len(prefix):]
                break
        if name:
            types.append(name)
    return types


def _rule_key(types: list[str]) -> str | None:
    """The rule set a node answers to, following the subtype table."""
    for name in types:
        if name in _REQUIRED_FIELDS or name in _RECOMMENDED_FIELDS:
            return name
        parent = _TYPE_PARENTS.get(name)
        if parent:
            return parent
    return None


def _check_string(key: str, value: str, path: str, report: _Report) -> None:
    for marker in _find_placeholders(value):
        report.add(
            ERROR, path,
            f'Placeholder non remplace : « {marker} ». '
            'Le gabarit a ete publie sans les vraies donnees.',
        )

    if key in _ABSOLUTE_URL_KEYS or key == '@id':
        verdict = _url_verdict(value)
        if verdict:
            level, reason = verdict
            # A bare @id fragment resolves against the page, so it is only a
            # portability problem: the same block copied elsewhere breaks.
            if key == '@id' and value.strip().startswith('#'):
                report.add(
                    WARNING, path,
                    '@id est un simple fragment, prefixer par l URL canonique '
                    'de la page pour un identifiant stable.',
                )
            else:
                report.add(level, path, f'Champ « {key} » : {reason}.')

    if key in _DATE_KEYS:
        if _parse_iso(value) is None:
            report.add(
                ERROR, path,
                f'Date « {value} » mal formee. Format ISO 8601 attendu '
                '(2026-08-14 ou 2026-08-14T09:30:00-04:00).',
            )

    if key == 'inLanguage':
        tag = value.strip()
        if not _LANG_TAG_RE.match(tag):
            report.add(
                WARNING, path,
                f'Code de langue « {tag} » invalide, tag BCP 47 attendu '
                '(fr-CA, en-CA).',
            )
        elif tag.lower() in ('fr', 'en'):
            report.add(
                WARNING, path,
                f'inLanguage vaut « {tag} », preciser « {tag}-CA » pour cibler '
                'le marche quebecois.',
            )

    if key == 'priceCurrency' and not re.match(r'^[A-Z]{3}$', value.strip()):
        report.add(
            ERROR, path,
            f'Devise « {value} » invalide, code ISO 4217 a trois lettres '
            'attendu (CAD).',
        )

    if key == 'price' and not _PLAIN_NUMBER_RE.match(value.strip()):
        report.add(
            ERROR, path,
            f'Prix « {value} » non exploitable. Google exige un nombre nu '
            'avec le point comme separateur decimal : « 19.99 », pas '
            '« 19,99 $ ».',
        )

    if key == 'telephone':
        digits = re.sub(r'\D', '', value)
        if len(digits) < 10:
            report.add(
                WARNING, path,
                f'Numero de telephone « {value} » incomplet, indicatif '
                'regional attendu.',
            )
        elif not value.strip().startswith('+'):
            report.add(
                WARNING, path,
                f'Numero « {value} » sans indicatif pays, format E.164 '
                'recommande : +1 suivi des dix chiffres.',
            )


def _check_types(node: dict, types: list[str], path: str, report: _Report) -> None:
    if not types:
        report.add(
            ERROR, f'{path}.@type',
            f'Champ @type vide ou illisible ({node.get("@type")!r}), '
            'un nom de type schema.org est attendu.',
        )
        return

    for name in types:
        if name in _DEAD_TYPES:
            report.add(
                ERROR, path,
                f'Type « {name} » mort en 2026 : {_DEAD_TYPES[name]}.',
            )
            continue
        if name in _WEAKENED_TYPES:
            report.add(WARNING, path, f'Type « {name} » : {_WEAKENED_TYPES[name]}')
            continue
        if not _TYPE_NAME_RE.match(name):
            suggestion = _KNOWN_TYPES_BY_LOWER.get(name.lower())
            if suggestion:
                report.add(
                    ERROR, path,
                    f'Type « {name} » mal capitalise, schema.org attend '
                    f'« {suggestion} ».',
                )
            else:
                report.add(
                    ERROR, path,
                    f'Type « {name} » invalide, un type schema.org commence '
                    'par une majuscule et ne contient ni espace ni tiret.',
                )


def _check_required(node: dict, rule_key: str, path: str, report: _Report) -> None:
    required = _REQUIRED_FIELDS.get(rule_key, ())
    for field in required:
        if field not in node:
            report.add(
                ERROR, f'{path}.{field}',
                f'Champ requis « {field} » absent du type {rule_key}.',
            )
    for field in _RECOMMENDED_FIELDS.get(rule_key, ()):
        if field not in node:
            report.add(
                WARNING, f'{path}.{field}',
                f'Champ recommande « {field} » absent du type {rule_key}.',
            )


def _check_empty_values(node: dict, required: tuple, path: str, report: _Report) -> None:
    for key, value in node.items():
        if not _is_empty(value):
            continue
        child = f'{path}.{key}'
        if key in _ABSOLUTE_URL_KEYS or key == '@id':
            report.add(
                ERROR, child,
                f'Champ « {key} » vide alors qu une URL absolue est exigee.',
            )
        elif key.startswith('@'):
            # @type and @context emptiness is reported by their own checks,
            # with a message that says what to put back.
            continue
        elif key in required:
            report.add(ERROR, child, f'Champ requis « {key} » vide.')
        else:
            report.add(
                WARNING, child,
                f'Champ « {key} » vide, le retirer plutot que le publier vide.',
            )


def _check_article(node: dict, path: str, report: _Report) -> None:
    headline = node.get('headline')
    if isinstance(headline, str) and len(headline) > 110:
        report.add(
            WARNING, f'{path}.headline',
            f'headline de {len(headline)} caracteres, Google tronque au-dela '
            'de 110.',
        )
    author = node.get('author')
    if isinstance(author, str):
        report.add(
            WARNING, f'{path}.author',
            'author en texte brut, un objet Person ou Organization avec name '
            'et url porte mieux le signal E-E-A-T.',
        )
    published = node.get('datePublished')
    modified = node.get('dateModified')
    if isinstance(published, str) and isinstance(modified, str):
        pub, mod = _parse_iso(published), _parse_iso(modified)
        if pub and mod and mod < pub:
            report.add(
                ERROR, f'{path}.dateModified',
                f'dateModified ({modified}) anterieure a datePublished '
                f'({published}).',
            )
    if isinstance(published, str):
        pub = _parse_iso(published)
        if pub and pub > datetime.now(timezone.utc) + timedelta(days=2):
            report.add(
                WARNING, f'{path}.datePublished',
                f'datePublished ({published}) dans le futur, Google ignore '
                'ces dates.',
            )


def _check_product(node: dict, path: str, report: _Report) -> None:
    offers = node.get('offers')
    candidates = offers if isinstance(offers, list) else [offers]
    for index, offer in enumerate(candidates):
        if not isinstance(offer, dict):
            continue
        offer_path = f'{path}.offers[{index}]' if isinstance(offers, list) else f'{path}.offers'
        types = _node_types(offer)
        if 'AggregateOffer' in types:
            report.add(
                WARNING, offer_path,
                'AggregateOffer ne declenche pas la fiche marchande, un Offer '
                'par produit est attendu.',
            )
        elif types and 'Offer' not in types:
            report.add(
                ERROR, offer_path,
                f'offers doit porter @type Offer, pas « {types[0]} ».',
            )


def _check_faqpage(node: dict, path: str, report: _Report) -> None:
    entries = node.get('mainEntity')
    if entries is None:
        return
    items = entries if isinstance(entries, list) else [entries]
    if not items:
        report.add(
            ERROR, f'{path}.mainEntity',
            'FAQPage sans aucune question, le balisage est invalide.',
        )
        return
    for index, item in enumerate(items):
        item_path = f'{path}.mainEntity[{index}]'
        if not isinstance(item, dict):
            report.add(ERROR, item_path, 'Entree de FAQ qui n est pas un objet Question.')
            continue
        if 'Question' not in _node_types(item):
            report.add(
                ERROR, item_path,
                'Chaque entree de mainEntity doit porter @type Question.',
            )


def _check_breadcrumb(node: dict, path: str, report: _Report) -> None:
    elements = node.get('itemListElement')
    if elements is None:
        return
    if not isinstance(elements, list):
        report.add(
            ERROR, f'{path}.itemListElement',
            'itemListElement doit etre une liste de ListItem.',
        )
        return
    if not elements:
        report.add(ERROR, f'{path}.itemListElement', 'Fil d Ariane vide.')
        return

    positions: list[int] = []
    last = len(elements) - 1
    for index, element in enumerate(elements):
        item_path = f'{path}.itemListElement[{index}]'
        if not isinstance(element, dict):
            report.add(ERROR, item_path, 'Entree de fil d Ariane qui n est pas un ListItem.')
            continue
        if 'ListItem' not in _node_types(element):
            report.add(ERROR, item_path, 'Chaque entree doit porter @type ListItem.')

        position = element.get('position')
        if isinstance(position, bool) or position is None:
            report.add(ERROR, f'{item_path}.position', 'Champ requis « position » absent.')
        elif isinstance(position, int):
            positions.append(position)
        elif isinstance(position, str) and position.strip().isdigit():
            positions.append(int(position))
            report.add(
                WARNING, f'{item_path}.position',
                f'position « {position} » en texte, un entier est attendu.',
            )
        else:
            report.add(
                ERROR, f'{item_path}.position',
                f'position « {position} » invalide, un entier est attendu.',
            )

        if _is_empty(element.get('name')):
            report.add(ERROR, f'{item_path}.name', 'Champ requis « name » absent du ListItem.')

        # The trailing crumb is the current page, so Google treats its item
        # as optional. Any earlier crumb without a target breaks the trail.
        if index != last and _is_empty(element.get('item')):
            report.add(
                ERROR, f'{item_path}.item',
                'Maillon sans « item », seul le dernier niveau peut s en passer.',
            )

    if positions and positions != list(range(1, len(positions) + 1)):
        report.add(
            ERROR, f'{path}.itemListElement',
            f'Positions {positions} non sequentielles, la numerotation doit '
            'aller de 1 a N sans trou.',
        )


def _check_localbusiness(node: dict, path: str, report: _Report) -> None:
    address = node.get('address')
    if isinstance(address, str):
        report.add(
            WARNING, f'{path}.address',
            'address en texte brut, un objet PostalAddress decoupe '
            '(streetAddress, addressLocality, addressRegion, postalCode, '
            'addressCountry) est attendu.',
        )
    if isinstance(address, dict):
        region = str(address.get('addressRegion') or '')
        country = str(address.get('addressCountry') or '')
        if region.strip().lower() in ('qc', 'quebec', 'québec') and not country.strip():
            report.add(
                WARNING, f'{path}.address.addressCountry',
                'addressRegion quebecois sans addressCountry, ajouter « CA ».',
            )


_NODE_CHECKS = {
    'Article': _check_article,
    'Product': _check_product,
    'FAQPage': _check_faqpage,
    'BreadcrumbList': _check_breadcrumb,
    'LocalBusiness': _check_localbusiness,
}


# `{"@type": "WebPage", "@id": "https://.../page"}` under mainEntityOfPage is
# a pointer to a node described elsewhere, not a node to complete. Asking it
# for a name or a description is the fastest way to make this validator noise.
_REFERENCE_NODE_KEYS = frozenset({'@type', '@context', '@id'})


def _check_node(node: dict, path: str, report: _Report) -> None:
    types = _node_types(node)
    _check_types(node, types, path, report)

    if '@id' in node and set(node) <= _REFERENCE_NODE_KEYS:
        return

    rule_key = _rule_key(types)
    required = _REQUIRED_FIELDS.get(rule_key, ()) if rule_key else ()
    _check_empty_values(node, required, path, report)
    if rule_key:
        _check_required(node, rule_key, path, report)
        checker = _NODE_CHECKS.get(rule_key)
        if checker:
            checker(node, path, report)


def _walk(value, path: str, key: str, report: _Report, depth: int) -> None:
    if report.nodes >= _MAX_NODES or depth > _MAX_DEPTH:
        report.truncated = True
        return

    if isinstance(value, dict):
        report.nodes += 1
        if '@type' in value:
            _check_node(value, path, report)
        elif key in _KEYS_EXPECTING_TYPED_OBJECT:
            report.add(
                WARNING, path,
                f'Objet imbrique sous « {key} » sans @type, les moteurs ne '
                'savent pas quoi en faire.',
            )
        for child_key, child in value.items():
            _walk(child, f'{path}.{child_key}', child_key, report, depth + 1)
        return

    if isinstance(value, list):
        for index, child in enumerate(value):
            _walk(child, f'{path}[{index}]', key, report, depth + 1)
        return

    if isinstance(value, str):
        if value.strip():
            _check_string(key, value, path, report)
        return

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if key == 'price' and value < 0:
            report.add(ERROR, path, f'Prix negatif ({value}).')


def _check_context(node: dict, path: str, report: _Report) -> None:
    context = node.get('@context')
    if context is None:
        report.add(
            ERROR, f'{path}.@context',
            'Champ @context absent, ajouter "@context": "https://schema.org".',
        )
        return
    if isinstance(context, str):
        value = context.strip().rstrip('/')
        if value == 'http://schema.org':
            report.add(
                WARNING, f'{path}.@context',
                '@context en http, utiliser "https://schema.org".',
            )
        elif value != 'https://schema.org':
            report.add(
                ERROR, f'{path}.@context',
                f'@context « {context} » inattendu, "https://schema.org" est '
                'attendu.',
            )
        return
    if isinstance(context, (dict, list)):
        if 'schema.org' not in json.dumps(context, ensure_ascii=False):
            report.add(
                ERROR, f'{path}.@context',
                '@context ne reference pas schema.org.',
            )
        return
    report.add(ERROR, f'{path}.@context', '@context doit etre une chaine, un objet ou une liste.')


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate_jsonld(data, *, root_path: str = '$') -> list[dict]:
    """Check a JSON-LD payload and return every issue found.

    Accepts a single node, a list of nodes, a `@graph` wrapper, or the raw
    JSON text. Each issue is `{'level': 'error' | 'warning', 'path': str,
    'message': str}`; `path` is a JSON pointer written in dotted form so a
    caller can show the operator which field to fix. An empty list means the
    payload is publishable.
    """
    report = _Report()

    if isinstance(data, bytes):
        try:
            data = data.decode('utf-8')
        except UnicodeDecodeError as exc:
            return [{'level': ERROR, 'path': root_path,
                     'message': f'Bloc JSON-LD illisible : {exc}.'}]
    if isinstance(data, str):
        if not data.strip():
            return [{'level': ERROR, 'path': root_path,
                     'message': 'Bloc JSON-LD vide.'}]
        try:
            data = json.loads(data)
        except json.JSONDecodeError as exc:
            return [{'level': ERROR, 'path': root_path,
                     'message': f'JSON invalide : {exc.msg} (ligne {exc.lineno}, '
                                f'colonne {exc.colno}).'}]

    if data is None or (isinstance(data, (dict, list)) and not data):
        return [{'level': ERROR, 'path': root_path,
                 'message': 'Aucun JSON-LD a valider, le bloc est vide.'}]
    if not isinstance(data, (dict, list)):
        return [{'level': ERROR, 'path': root_path,
                 'message': f'JSON-LD attendu sous forme d objet ou de liste, '
                            f'recu {type(data).__name__}.'}]

    roots: list[tuple[str, object]] = []
    if isinstance(data, dict) and '@graph' in data:
        _check_context(data, root_path, report)
        graph = data['@graph']
        if not isinstance(graph, list) or not graph:
            report.add(ERROR, f'{root_path}.@graph', '@graph doit etre une liste non vide de noeuds.')
        else:
            roots = [(f'{root_path}.@graph[{i}]', n) for i, n in enumerate(graph)]
        # Nodes inside a @graph inherit the wrapper context, so they are not
        # asked for one of their own.
        for path, node in roots:
            if isinstance(node, dict) and '@type' not in node:
                report.add(ERROR, f'{path}.@type', 'Champ @type absent du noeud.')
            elif not isinstance(node, dict):
                report.add(ERROR, path, 'Noeud de @graph qui n est pas un objet.')
    else:
        if isinstance(data, dict):
            roots = [(root_path, data)]
        else:
            roots = [(f'{root_path}[{i}]', n) for i, n in enumerate(data)]
        for path, node in roots:
            if not isinstance(node, dict):
                report.add(ERROR, path, 'Bloc JSON-LD qui n est pas un objet.')
                continue
            _check_context(node, path, report)
            if '@type' not in node:
                report.add(ERROR, f'{path}.@type', 'Champ @type absent du noeud.')

    _walk(data, root_path, '', report, 0)

    if report.truncated:
        report.issues.append({
            'level': WARNING,
            'path': root_path,
            'message': 'Analyse interrompue : le bloc JSON-LD est trop gros ou '
                       'trop imbrique, corriger les problemes listes puis relancer.',
        })

    seen: set[tuple[str, str, str]] = set()
    unique: list[dict] = []
    for issue in report.issues:
        signature = (issue['level'], issue['path'], issue['message'])
        if signature not in seen:
            seen.add(signature)
            unique.append(issue)
    unique.sort(key=lambda i: (i['level'] != ERROR, i['path']))
    return unique


_JSONLD_BLOCK_RE = re.compile(
    r'<script[^>]*type\s*=\s*["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)
_CDATA_RE = re.compile(r'^\s*(?://)?\s*<!\[CDATA\[|\]\]>\s*(?://)?\s*$|<!--|-->')


def validate_html_jsonld(html: str) -> list[dict]:
    """Validate every JSON-LD block embedded in an HTML document.

    Mirrors what the upstream hook does to a file, for the case where Gridar
    holds rendered HTML rather than a parsed object. HTML with no JSON-LD at
    all returns a single warning: a page Gridar publishes is expected to
    carry structured data.
    """
    blocks = _JSONLD_BLOCK_RE.findall(html or '')
    if not blocks:
        return [{'level': WARNING, 'path': '$',
                 'message': 'Aucun bloc application/ld+json trouve dans la page.'}]

    issues: list[dict] = []
    for index, block in enumerate(blocks):
        cleaned = _CDATA_RE.sub('', block).strip()
        issues.extend(validate_jsonld(cleaned, root_path=f'$.script[{index}]'))
    return issues


def has_blocking_errors(issues: list[dict]) -> bool:
    """True when at least one issue is severe enough to hold publication."""
    return any(issue.get('level') == ERROR for issue in issues)
