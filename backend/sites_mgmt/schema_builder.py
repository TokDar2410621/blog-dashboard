"""JSON-LD builders for entity and service pages, plus a Product validator.

Ported from claude-seo v2.2.4 `scripts/schema_generate.py` and
`scripts/schema_ecommerce_validate.py`.
Copyright (c) 2025 Daniel Agrici (AgriciDaniel). MIT.
https://github.com/AgriciDaniel/claude-seo

Three deviations from upstream. The argparse CLI and the Reservation,
OrderAction and DiscussionForumPosting generators are dropped because Gridar
has no surface that emits them, and a Service builder upstream never had is
added because that is what a Quebec local business actually publishes. The
area-served resolver is new: it matches French place names with the accents
stripped, expands the "St-" and "Ste-" forms everyone types, and wraps each
city in its province and country so "Laval" cannot be read as the French one.
The validator keeps upstream's merchant rules and adds the French-locale traps
that parse as valid JSON yet disqualify the listing, "En stock" written where
the availability enum belongs and "19,99 $" written where a dot decimal
belongs. Finding messages are French because the dashboard renders them
verbatim; comments and docstrings stay English, like the rest of this package.
"""
from __future__ import annotations

import re
import unicodedata
from urllib.parse import urljoin, urlparse

__all__ = [
    'SCHEMA_CONTEXT',
    'build_area_served',
    'build_profile_page',
    'build_service',
    'has_blocking_findings',
    'summarize_findings',
    'validate_product',
]

SCHEMA_CONTEXT = 'https://schema.org'

_SEVERITY_RANK = {'critical': 0, 'high': 1, 'medium': 2, 'info': 3}


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------

def _clean(value) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, bool):
        return ''
    if isinstance(value, (int, float)):
        return str(value)
    return ''


def _first(source: dict, *keys) -> str:
    """First non-empty value among `keys`, so callers can pass either our own
    naming or the Site model field names without a translation layer."""
    for key in keys:
        value = _clean(source.get(key))
        if value:
            return value
    return ''


def _as_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    if isinstance(value, str):
        # Every free-form Site field in this repo is a TextField holding one
        # entry per line, so a bare string is split rather than wrapped.
        return [line.strip() for line in value.splitlines() if line.strip()]
    return [value]


def _first_list(source: dict, *keys) -> list:
    for key in keys:
        if source.get(key) not in (None, '', [], {}):
            return _as_list(source[key])
    return []


def _dedupe(values: list) -> list:
    seen = set()
    out = []
    for value in values:
        marker = repr(value)
        if marker in seen:
            continue
        seen.add(marker)
        out.append(value)
    return out


def _strip_accents(text: str) -> str:
    return ''.join(
        char for char in unicodedata.normalize('NFKD', text or '')
        if not unicodedata.combining(char)
    )


def _is_absolute_url(value: str) -> bool:
    parsed = urlparse(_clean(value))
    return parsed.scheme in ('http', 'https') and bool(parsed.netloc)


def _prune(payload):
    """Drop None and empty containers, recursively.

    `0` and `False` survive: a price of 0 or a boolean flag is data, not an
    absent field.
    """
    if isinstance(payload, dict):
        out = {}
        for key, value in payload.items():
            pruned = _prune(value)
            if pruned is None or pruned == '' or pruned == [] or pruned == {}:
                continue
            out[key] = pruned
        return out
    if isinstance(payload, list):
        out = []
        for item in payload:
            pruned = _prune(item)
            if pruned is None or pruned == '' or pruned == [] or pruned == {}:
                continue
            out.append(pruned)
        return out
    return payload


_LANGUAGES = {
    'fr': ('French', 'fr-CA'),
    'en': ('English', 'en-CA'),
    'es': ('Spanish', 'es'),
}


def _language(source: dict) -> tuple[str, str]:
    """(schema.org Language name, BCP-47 tag). Defaults to Quebec French.

    A bare 'fr' becomes 'fr-CA' rather than 'fr-FR': the region subtag is the
    only signal in the markup that separates a Quebec page from a French one.
    """
    raw = _first(source, 'language', 'default_language', 'lang', 'inLanguage') or 'fr'
    raw = raw.replace('_', '-')
    base = raw.split('-')[0].lower()
    name, default_tag = _LANGUAGES.get(base, _LANGUAGES['fr'])
    if '-' in raw:
        region = raw.split('-', 1)[1].upper()
        return name, f'{base}-{region}'
    return name, default_tag


# ---------------------------------------------------------------------------
# Prices
# ---------------------------------------------------------------------------

# Currency markers and whitespace. Python's `\s` covers the no-break and
# narrow no-break spaces an editor inserts before a dollar sign in French.
_PRICE_NOISE_RE = re.compile(r'\s|\$|CAD|CDN|USD|EUR|€', re.IGNORECASE)
_PLAIN_PRICE_RE = re.compile(r'^\d+(?:\.\d{1,6})?$')


def _normalize_price(raw) -> str:
    """'1 299,99 $' -> '1299.99'. Empty string when it cannot be read.

    Google reads `price` as a dot decimal with no symbol and no group
    separator, which is exactly what a price typed in Quebec French is not.
    """
    if isinstance(raw, bool):
        return ''
    if isinstance(raw, int):
        return str(raw)
    if isinstance(raw, float):
        return ('%f' % raw).rstrip('0').rstrip('.') or '0'

    text = _PRICE_NOISE_RE.sub('', _clean(raw))
    if not text:
        return ''
    if ',' in text and '.' in text:
        # Whichever separator comes last is the decimal mark.
        if text.rindex('.') > text.rindex(','):
            text = text.replace(',', '')
        else:
            text = text.replace('.', '').replace(',', '.')
    elif ',' in text:
        # A lone comma in a Quebec price is the decimal mark, never a group
        # separator: '1,5' is one dollar fifty, not fifteen hundred.
        text = text.replace(',', '.')
    return text if _PLAIN_PRICE_RE.match(text) else ''


# ---------------------------------------------------------------------------
# Quebec service areas
# ---------------------------------------------------------------------------

def _flatten(text: str) -> str:
    """Accents stripped, lowercased, punctuation collapsed to single spaces."""
    plain = _strip_accents(_clean(text)).lower()
    return re.sub(r'[^a-z0-9]+', ' ', plain).strip()


def _area_key(text: str) -> str:
    """Place-name lookup key: `_flatten` plus the St/Ste expansion.

    'St-Jerome', 'Saint-Jérôme' and 'saint jerome' have to land on one entry,
    because business owners type all three.
    """
    words = ['saint' if w == 'st' else 'sainte' if w == 'ste' else w
             for w in _flatten(text).split()]
    return ' '.join(words)


# The 40 largest Quebec municipalities plus the ones Gridar's local landings
# target most. Bare "Québec" is deliberately absent: alone it reads as the
# province far more often than as the city, so the city needs an explicit form.
_QC_CITY_LABELS = (
    'Montréal', 'Laval', 'Gatineau', 'Longueuil', 'Sherbrooke',
    'Trois-Rivières', 'Saguenay', 'Lévis', 'Terrebonne', 'Saint-Jean-sur-Richelieu',
    'Repentigny', 'Brossard', 'Drummondville', 'Saint-Jérôme', 'Granby',
    'Blainville', 'Saint-Hyacinthe', 'Shawinigan', 'Rimouski', 'Châteauguay',
    'Victoriaville', 'Rouyn-Noranda', 'Saint-Eustache', 'Mascouche', 'Boucherville',
    'Salaberry-de-Valleyfield', 'Sorel-Tracy', 'Vaudreuil-Dorion', 'Dollard-des-Ormeaux',
    'Côte-Saint-Luc', 'Pointe-Claire', 'Sainte-Julie', 'Saint-Constant', 'Boisbriand',
    'Sept-Îles', 'Joliette', 'Alma', 'Magog', 'Mirabel', 'Val-d\'Or',
    'Beloeil', 'Gaspé', 'Baie-Comeau', 'Thetford Mines', 'Sainte-Thérèse',
    'Varennes', 'Candiac', 'La Prairie', 'Chambly', 'Beauharnois',
)
_QC_CITIES = {_area_key(label): label for label in _QC_CITY_LABELS}
_QC_CITIES.update({
    'ville de quebec': 'Québec',
    'quebec city': 'Québec',
    'quebec ville': 'Québec',
})

# Official administrative regions. Laval and Montréal are also regions on
# paper, but they resolve as cities above, which is what a service page means.
# The official names use an en dash; hyphens are written here and the lookup
# key flattens both anyway.
_QC_REGION_LABELS = (
    'Abitibi-Témiscamingue', 'Bas-Saint-Laurent', 'Capitale-Nationale',
    'Centre-du-Québec', 'Chaudière-Appalaches', 'Côte-Nord', 'Estrie',
    'Gaspésie-Îles-de-la-Madeleine', 'Lanaudière', 'Laurentides', 'Mauricie',
    'Montérégie', 'Nord-du-Québec', 'Outaouais', 'Saguenay-Lac-Saint-Jean',
)
_QC_REGIONS = {_area_key(label): label for label in _QC_REGION_LABELS}

# Zones with no legal boundary that every Quebec quote sheet still uses.
# They stay Place rather than AdministrativeArea because claiming an
# administrative status they do not have is the kind of thing a validator
# forgives and a knowledge graph does not.
_QC_ZONE_LABELS = (
    'Rive-Sud', 'Rive-Nord', 'Grand Montréal', 'Couronne Nord', 'Couronne Sud',
    'Basses-Laurentides', 'West Island', 'Vieux-Montréal', 'Vieux-Québec',
    'Plateau-Mont-Royal', 'Cantons-de-l\'Est', 'Charlevoix', 'Beauce',
    'Lac-Saint-Jean', 'Vallée-du-Richelieu', 'Haut-Richelieu', 'Bois-Francs',
)
_QC_ZONES = {_area_key(label): label for label in _QC_ZONE_LABELS}

_PROVINCE_KEYS = frozenset({'quebec', 'qc', 'province de quebec', 'le quebec'})
_COUNTRY_KEYS = frozenset({'canada', 'ca', 'can'})

# A Canadian forward sortation area: the first three characters of a postal
# code. Quebec's start with G, H or J.
_FSA_RE = re.compile(r'^([A-Za-z]\d[A-Za-z])(?:[\s-]?\d[A-Za-z]\d)?$')


def _canada() -> dict:
    return {'@type': 'Country', 'name': 'Canada'}


def _quebec() -> dict:
    return {'@type': 'State', 'name': 'Québec', 'containedInPlace': _canada()}


def build_area_served(zone) -> dict:
    """One `areaServed` node from a zone written the way a client writes it.

    Accepts a string ('montreal', 'St-Jérôme', 'Montérégie', 'Rive-Sud', 'QC',
    'H2X') or a dict. A dict that already carries an `@type` is passed through
    untouched, which is the escape hatch for anything this table does not know.
    Every Quebec place is nested in its province and country: 'Laval' and
    'Granby' both exist elsewhere in the world, and the nesting is what tells
    a knowledge graph which one is meant.
    """
    if isinstance(zone, dict):
        if _clean(zone.get('@type')):
            return dict(zone)
        label = _first(zone, 'name', 'label', 'zone', 'city')
        node = build_area_served(label)
        override = _first(zone, 'type', 'kind')
        if node and override:
            node['@type'] = override
        return node

    label = _clean(zone)
    if not label:
        return {}

    fsa = _FSA_RE.match(label)
    if fsa:
        # GeoShape is the only areaServed-compatible carrier for a postal
        # prefix; DefinedRegion is a StructuredValue and out of range here.
        return {
            '@type': 'GeoShape',
            'addressCountry': 'CA',
            'postalCode': fsa.group(1).upper(),
        }

    key = _area_key(label)
    if key in _QC_CITIES:
        return {'@type': 'City', 'name': _QC_CITIES[key],
                'containedInPlace': _quebec()}
    if key in _QC_REGIONS:
        return {'@type': 'AdministrativeArea', 'name': _QC_REGIONS[key],
                'containedInPlace': _quebec()}
    if key in _QC_ZONES:
        return {'@type': 'Place', 'name': _QC_ZONES[key],
                'containedInPlace': _quebec()}
    if key in _PROVINCE_KEYS:
        return _quebec()
    if key in _COUNTRY_KEYS:
        return _canada()
    return {'@type': 'Place', 'name': label}


# ---------------------------------------------------------------------------
# ProfilePage
# ---------------------------------------------------------------------------

_SOCIAL_KEYS = (
    'linkedin', 'author_linkedin', 'twitter', 'author_twitter', 'x',
    'github', 'facebook', 'instagram', 'youtube', 'tiktok', 'threads',
    'mastodon', 'wikipedia', 'wikidata', 'orcid', 'crunchbase',
    'google_business_profile', 'website', 'author_website',
)

# The organization's own profiles. `author_*` and `website` are left out: a
# Site dict carries the author's LinkedIn and the site's own URL, and neither
# is "another page about this organization".
_ORG_SOCIAL_KEYS = (
    'linkedin', 'twitter', 'x', 'facebook', 'instagram', 'youtube', 'tiktok',
    'github', 'wikipedia', 'wikidata', 'crunchbase', 'google_business_profile',
)


def _thing(entry) -> dict | str:
    """A knowsAbout entry: plain string, or a Thing whose sameAs resolves it.

    A topic pointed at its Wikipedia or Wikidata URL is the part that turns a
    keyword list into an entity graph, so dicts keep their links.
    """
    if isinstance(entry, dict):
        name = _first(entry, 'name', 'label', 'topic', 'title')
        if not name:
            return ''
        links = [u for u in _dedupe(
            _as_list(entry.get('same_as') or entry.get('sameAs') or entry.get('url'))
        ) if _is_absolute_url(_clean(u))]
        node = {'@type': _first(entry, 'type', '@type') or 'Thing', 'name': name}
        if links:
            node['sameAs'] = links if len(links) > 1 else links[0]
        return node
    return _clean(entry)


def build_profile_page(author: dict) -> dict:
    """ProfilePage JSON-LD for an author or a brand.

    `author` is a plain dict. Both our own key names and the Site model field
    names are read, so an integrator can hand over
    `{'default_author': ..., 'author_role': ..., 'author_linkedin': ...}`
    straight from the model without remapping.

    sameAs plus knowsAbout is the cheapest entity-graph builder there is: the
    first says which other profiles are the same entity, the second says what
    that entity is competent about. Both are what an assistant reads when it
    decides whether a brand is a citable source.
    """
    author = author or {}
    name = _first(author, 'name', 'default_author', 'author', 'full_name')
    if not name:
        raise ValueError('build_profile_page: un nom est requis')

    entity_type = _first(author, 'entity_type', 'type') or 'Person'
    if entity_type not in ('Person', 'Organization'):
        raise ValueError(
            f'build_profile_page: entity_type invalide {entity_type!r} '
            '(Person ou Organization)'
        )

    url = _first(author, 'url', 'profile_url', 'page_url', 'author_website', 'website')
    if url and not _is_absolute_url(url):
        url = 'https://' + url.lstrip('/')

    same_as = [
        _clean(link) for link in _dedupe(
            _first_list(author, 'same_as', 'sameAs', 'profiles', 'social_links')
            + [author.get(key) for key in _SOCIAL_KEYS]
        )
    ]
    # An absolute http(s) URL is the only thing sameAs may hold, and the page's
    # own URL is not "another page about the same entity".
    same_as = [link for link in _dedupe(same_as)
               if _is_absolute_url(link) and link.rstrip('/') != url.rstrip('/')]

    knows_about = [
        node for node in (
            _thing(entry) for entry in
            _first_list(author, 'knows_about', 'knowsAbout', 'topics', 'expertise', 'skills')
        ) if node
    ]

    credentials = [
        {'@type': 'EducationalOccupationalCredential', 'name': _clean(item)}
        for item in _first_list(author, 'credentials', 'author_credentials', 'certifications')
        if _clean(item)
    ]

    employer = author.get('works_for') or author.get('organization') or author.get('employer')
    works_for: dict = {}
    if isinstance(employer, dict):
        employer_name = _first(employer, 'name', 'title')
        if employer_name:
            works_for = {'@type': _first(employer, 'type', '@type') or 'Organization',
                         'name': employer_name,
                         'url': _first(employer, 'url', 'website')}
    elif _clean(employer):
        works_for = {'@type': 'Organization', 'name': _clean(employer)}

    entity: dict = {
        '@type': entity_type,
        # A stable @id lets every article on the site point its author at this
        # same node instead of restating the person inline.
        '@id': f'{url}#{entity_type.lower()}' if url else '',
        'name': name,
        'url': url,
        'description': _first(author, 'description', 'bio', 'author_bio', 'summary'),
        'image': _first(author, 'image', 'image_url', 'author_image_url', 'photo'),
        'email': _first(author, 'email', 'author_email'),
        'telephone': _first(author, 'telephone', 'phone'),
        'sameAs': same_as,
        'knowsAbout': knows_about,
        'hasCredential': credentials,
        'worksFor': works_for,
    }
    if entity_type == 'Person':
        entity['jobTitle'] = _first(author, 'job_title', 'jobTitle', 'role', 'author_role')

    _, language_tag = _language(author)
    page = {
        '@context': SCHEMA_CONTEXT,
        '@type': 'ProfilePage',
        'url': url,
        'inLanguage': language_tag,
        'dateCreated': _first(author, 'date_created', 'dateCreated', 'created_at'),
        'dateModified': _first(author, 'date_modified', 'dateModified', 'updated_at'),
        'mainEntity': entity,
    }
    return _prune(page)


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

def _site_url(site: dict) -> str:
    url = _first(site, 'url', 'site_url', 'website', 'public_url')
    if not url:
        url = _first(site, 'domain', 'public_blog_domain', 'host')
    if not url:
        return ''
    if not re.match(r'^https?://', url, re.IGNORECASE):
        url = 'https://' + url.lstrip('/')
    return url.rstrip('/')


def _absolute(url: str, base: str) -> str:
    url = _clean(url)
    if not url or _is_absolute_url(url):
        return url
    return urljoin(base + '/', url.lstrip('/')) if base else url


def _postal_address(raw) -> dict:
    """PostalAddress from a dict or a one-line address string.

    addressCountry falls back to CA, which is the whole customer base. The
    region is never guessed: an address with no province stays without one
    rather than being stamped QC on a client who is not in Quebec.
    """
    if isinstance(raw, dict):
        address = {
            '@type': 'PostalAddress',
            'streetAddress': _first(raw, 'street_address', 'streetAddress', 'street', 'address'),
            'addressLocality': _first(raw, 'city', 'locality', 'addressLocality', 'ville'),
            'addressRegion': _first(raw, 'region', 'addressRegion', 'province', 'state'),
            'postalCode': _first(raw, 'postal_code', 'postalCode', 'zip', 'code_postal'),
            'addressCountry': _first(raw, 'country', 'addressCountry') or 'CA',
        }
        return _prune(address)
    text = _clean(raw)
    if not text:
        return {}
    return {'@type': 'PostalAddress', 'streetAddress': text, 'addressCountry': 'CA'}


def _provider(site: dict, service: dict, base_url: str) -> dict:
    name = _first(site, 'name', 'site_name', 'business_name', 'organization', 'brand')
    if not name:
        raise ValueError('build_service: le nom du site est requis pour le provider')

    address = _postal_address(
        site.get('address') or site.get('postal_address') or site.get('adresse')
    )
    # LocalBusiness without an address is an invalid node, so the type is
    # earned by the data rather than assumed from the business model.
    default_type = 'LocalBusiness' if address else 'Organization'
    provider_type = _first(site, 'provider_type', 'organization_type') or default_type

    same_as = [_clean(link) for link in _dedupe(
        _first_list(site, 'same_as', 'sameAs', 'social_links', 'profiles')
        + [site.get(key) for key in _ORG_SOCIAL_KEYS]
    )]
    same_as = [link for link in _dedupe(same_as)
               if _is_absolute_url(link) and link.rstrip('/') != base_url.rstrip('/')]

    node = {
        '@type': provider_type,
        '@id': f'{base_url}#organization' if base_url else '',
        'name': name,
        'url': base_url,
        'description': _first(site, 'description', 'tagline', 'about'),
        'logo': _absolute(_first(site, 'logo', 'logo_url', 'og_image_url'), base_url),
        'telephone': _first(site, 'telephone', 'phone', 'tel'),
        'email': _first(site, 'email', 'contact_email'),
        'priceRange': _first(site, 'price_range', 'priceRange'),
        'address': address,
        'sameAs': same_as,
    }
    override = service.get('provider')
    if isinstance(override, dict) and override:
        node.update(override)
    return _prune(node)


def _offer(service: dict, currency: str, url: str) -> dict:
    price = _normalize_price(
        service.get('price') if service.get('price') is not None else service.get('prix')
    )
    low = _normalize_price(service.get('price_min') or service.get('min_price'))
    high = _normalize_price(service.get('price_max') or service.get('max_price'))
    if not price and not low and not high:
        return {}

    offer: dict = {'@type': 'Offer', 'priceCurrency': currency, 'url': url}
    if price:
        offer['price'] = price
    else:
        offer['priceSpecification'] = _prune({
            '@type': 'PriceSpecification',
            'priceCurrency': currency,
            'minPrice': low,
            'maxPrice': high,
        })
    availability = _clean(service.get('availability'))
    if availability:
        offer['availability'] = _availability_url(availability) or availability
    valid_until = _first(service, 'price_valid_until', 'priceValidUntil')
    if valid_until:
        offer['priceValidUntil'] = valid_until
    return _prune(offer)


def _offer_catalog(service: dict, currency: str, base_url: str) -> dict:
    entries = _first_list(service, 'catalog', 'offer_catalog', 'sub_services', 'prestations')
    items = []
    for entry in entries:
        if isinstance(entry, dict):
            name = _first(entry, 'name', 'title', 'label')
            if not name:
                continue
            item = {
                '@type': 'Offer',
                'itemOffered': _prune({
                    '@type': 'Service',
                    'name': name,
                    'description': _first(entry, 'description', 'summary'),
                    'url': _absolute(_first(entry, 'url', 'href'), base_url),
                }),
            }
            price = _normalize_price(entry.get('price'))
            if price:
                item['price'] = price
                item['priceCurrency'] = currency
            items.append(item)
        elif _clean(entry):
            items.append({
                '@type': 'Offer',
                'itemOffered': {'@type': 'Service', 'name': _clean(entry)},
            })
    if not items:
        return {}
    return {
        '@type': 'OfferCatalog',
        'name': _first(service, 'catalog_name') or _first(service, 'name', 'title'),
        'itemListElement': items,
    }


def build_service(site: dict, service: dict) -> dict:
    """Service JSON-LD with a provider, a serviceType and Quebec service areas.

    `site` carries the business (name, domain, address, phone, socials) and
    `service` the offer itself (name, service_type, description, price, zones).
    Zones go through `build_area_served`, so 'Rive-Sud', 'St-Jérôme',
    'Montérégie', 'QC' and 'H2X' all resolve; anything unknown is kept as a
    named Place instead of being dropped.
    """
    site = site or {}
    service = service or {}

    name = _first(service, 'name', 'title', 'service_name')
    if not name:
        raise ValueError('build_service: le nom du service est requis')

    base_url = _site_url(site)
    url = _absolute(_first(service, 'url', 'page_url', 'href'), base_url)
    language_name, language_tag = _language(
        {'language': _first(service, 'language') or _first(site, 'language', 'default_language')}
    )
    currency = (_first(service, 'price_currency', 'priceCurrency', 'currency')
                or _first(site, 'price_currency', 'currency')
                or 'CAD').upper()

    zones = _first_list(service, 'area_served', 'areaServed', 'areas', 'zones', 'service_area')
    if not zones:
        zones = _first_list(site, 'area_served', 'areaServed', 'zones', 'service_area')
    areas = [node for node in (build_area_served(zone) for zone in zones) if node]

    channel = _prune({
        '@type': 'ServiceChannel',
        'serviceUrl': _absolute(_first(service, 'booking_url', 'channel_url'), base_url) or url,
        'servicePhone': _first(service, 'telephone', 'phone') or _first(site, 'telephone', 'phone'),
        'availableLanguage': {'@type': 'Language', 'name': language_name,
                              'alternateName': language_tag},
    })

    payload = {
        '@context': SCHEMA_CONTEXT,
        '@type': _first(service, 'schema_type', '@type') or 'Service',
        'name': name,
        # serviceType is the searchable label ('Plomberie d'urgence'); without
        # an explicit one the service name is the closest honest value.
        'serviceType': _first(service, 'service_type', 'serviceType', 'type') or name,
        'description': _first(service, 'description', 'summary', 'excerpt'),
        'url': url,
        'image': _absolute(_first(service, 'image', 'image_url'), base_url),
        'category': _first(service, 'category', 'categorie'),
        'provider': _provider(site, service, base_url),
        'areaServed': areas,
        'availableChannel': channel,
        'offers': _offer(service, currency, url),
        'hasOfferCatalog': _offer_catalog(service, currency, base_url),
        'termsOfService': _absolute(_first(service, 'terms_url', 'termsOfService'), base_url),
    }
    return _prune(payload)


# ---------------------------------------------------------------------------
# Product validation
# ---------------------------------------------------------------------------

# Rich results Google retired in June and July 2025, announced at
# developers.google.com/search/blog/2025/06/simplifying-search-results.
# Emitting one of these in 2026 is dead weight in the page: the markup parses
# and nothing renders. `critical` is the flag the dashboard sorts on.
_RETIRED_TYPES: dict[str, dict] = {
    'Vehicle': {
        'critical': True, 'retired': '2025-06',
        'message': "Le rich result Vehicle Listing a ete retire en juin 2025.",
    },
    'VehicleListing': {
        'critical': True, 'retired': '2025-06',
        'message': "Le rich result Vehicle Listing a ete retire en juin 2025.",
    },
    'ClaimReview': {
        'critical': True, 'retired': '2025-06',
        'message': "Le rich result Claim Review a ete retire en juin 2025.",
    },
    'EstimatedSalary': {
        'critical': True, 'retired': '2025-06',
        'message': "Le rich result Estimated Salary a ete retire en juin 2025.",
    },
    'LearningVideo': {
        'critical': True, 'retired': '2025-06',
        'message': "Le rich result Learning Video a ete retire en juin 2025.",
    },
    'SpecialAnnouncement': {
        'critical': True, 'retired': '2025-07',
        'message': "Le rich result Special Announcement a ete deprecie en juillet 2025.",
    },
    # Upstream marks Course Critical alongside the rest, which contradicts its
    # own message: only the Course Info carousel went away in June 2025 and the
    # Course rich result still renders. Flagged, not blocking.
    'Course': {
        'critical': False, 'retired': '2025-06',
        'message': ("Le carrousel Course Info a ete retire en juin 2025. Le rich "
                    "result Course reste actif : verifie lequel des deux tu vises."),
    },
}

_REQUIRED_PRODUCT_FIELDS = ('name', 'image', 'offers')
_RECOMMENDED_PRODUCT_FIELDS = ('description',)
_RECOMMENDED_OFFER_FIELDS = ('price', 'priceCurrency', 'availability')
_REQUIRED_RETURN_POLICY_FIELDS = ('applicableCountry', 'returnPolicyCategory')
_REQUIRED_SHIPPING_FIELDS = ('shippingDestination', 'deliveryTime')

_AVAILABILITY_ENUM = frozenset({
    'BackOrder', 'Discontinued', 'InStock', 'InStoreOnly', 'LimitedAvailability',
    'MadeToOrder', 'OnlineOnly', 'OutOfStock', 'PreOrder', 'PreSale', 'SoldOut',
})

# Free text a merchant writes where the enum belongs. The French half is the
# reason this table exists: a Quebec catalogue exports "En stock", the JSON is
# valid, and the merchant listing is refused with no visible error.
_AVAILABILITY_TEXT = {
    'en stock': 'InStock',
    'en inventaire': 'InStock',
    'disponible': 'InStock',
    'in stock': 'InStock',
    'available': 'InStock',
    'rupture de stock': 'OutOfStock',
    'en rupture': 'OutOfStock',
    'en rupture de stock': 'OutOfStock',
    'epuise': 'OutOfStock',
    'indisponible': 'OutOfStock',
    'non disponible': 'OutOfStock',
    'out of stock': 'OutOfStock',
    'unavailable': 'OutOfStock',
    'precommande': 'PreOrder',
    'en precommande': 'PreOrder',
    'preorder': 'PreOrder',
    'pre order': 'PreOrder',
    'sur commande': 'BackOrder',
    'en commande': 'BackOrder',
    'commande differee': 'BackOrder',
    'backorder': 'BackOrder',
    'back order': 'BackOrder',
    'vendu': 'SoldOut',
    'vendu au complet': 'SoldOut',
    'complet': 'SoldOut',
    'sold out': 'SoldOut',
    'discontinue': 'Discontinued',
    'produit discontinue': 'Discontinued',
    'arret de production': 'Discontinued',
    'discontinued': 'Discontinued',
    'en magasin seulement': 'InStoreOnly',
    'en ligne seulement': 'OnlineOnly',
    'quantite limitee': 'LimitedAvailability',
    'stock limite': 'LimitedAvailability',
    'sur mesure': 'MadeToOrder',
    'fabrique sur mesure': 'MadeToOrder',
}

_RETURN_POLICY_ENUM = frozenset({
    'MerchantReturnFiniteReturnWindow', 'MerchantReturnNotPermitted',
    'MerchantReturnUnlimitedWindow', 'MerchantReturnUnspecified',
})

_ISO_CURRENCY_RE = re.compile(r'^[A-Z]{3}$')


def _enum_name(value: str) -> str:
    """'https://schema.org/InStock' -> 'InStock'. Also handles the http and
    'schema:' spellings a CMS emits."""
    text = _clean(value)
    if not text:
        return ''
    text = re.sub(r'^https?://schema\.org/', '', text)
    text = re.sub(r'^schema:', '', text)
    return text.strip('/')


def _availability_url(value: str) -> str:
    """Canonical availability URL for a value written as text or as an enum."""
    name = _enum_name(value)
    if name in _AVAILABILITY_ENUM:
        return f'{SCHEMA_CONTEXT}/{name}'
    mapped = _AVAILABILITY_TEXT.get(_flatten(value))
    return f'{SCHEMA_CONTEXT}/{mapped}' if mapped else ''


def _iter_typed(payload, target_type: str):
    """Yield every dict in `payload` whose @type matches `target_type`."""
    if isinstance(payload, dict):
        kind = payload.get('@type')
        if isinstance(kind, str) and kind == target_type:
            yield payload
        elif isinstance(kind, list) and target_type in kind:
            yield payload
        for value in payload.values():
            yield from _iter_typed(value, target_type)
    elif isinstance(payload, list):
        for value in payload:
            yield from _iter_typed(value, target_type)


def _all_types(payload) -> list[str]:
    types: list[str] = []
    if isinstance(payload, dict):
        kind = payload.get('@type')
        if isinstance(kind, str):
            types.append(kind)
        elif isinstance(kind, list):
            types.extend(t for t in kind if isinstance(t, str))
        for value in payload.values():
            types.extend(_all_types(value))
    elif isinstance(payload, list):
        for value in payload:
            types.extend(_all_types(value))
    return types


def _has_type(payload: dict, target_type: str) -> bool:
    kind = payload.get('@type')
    if isinstance(kind, str):
        return kind == target_type
    if isinstance(kind, list):
        return target_type in kind
    return False


def _finding(severity: str, rule: str, message: str, field: str = '', **extra) -> dict:
    item = {'severity': severity, 'rule': rule, 'message': message,
            'critical': severity == 'critical'}
    if field:
        item['field'] = field
    item.update(extra)
    return item


def _is_empty(value) -> bool:
    return value in (None, '', [], {})


def _check_price(offer: dict, findings: list) -> None:
    raw = offer.get('price')
    if _is_empty(raw):
        return
    if isinstance(raw, bool):
        findings.append(_finding('high', 'price-not-numeric',
                                 "offers.price n'est pas un nombre.", 'offers.price'))
        return
    if isinstance(raw, (int, float)):
        return
    text = _clean(raw)
    if _PLAIN_PRICE_RE.match(text):
        return
    normalized = _normalize_price(text)
    if normalized:
        findings.append(_finding(
            'high', 'price-locale-format',
            f"offers.price = {text!r} est ecrit au format francais. Google lit "
            f"un point decimal, sans symbole ni espace : utilise {normalized!r}.",
            'offers.price', suggestion=normalized,
        ))
    else:
        findings.append(_finding(
            'high', 'price-not-numeric',
            f"offers.price = {text!r} n'est pas lisible comme un nombre.",
            'offers.price',
        ))


def _check_currency(offer: dict, expected_currency: str, findings: list) -> None:
    raw = offer.get('priceCurrency')
    if _is_empty(raw):
        return
    text = _clean(raw)
    if not _ISO_CURRENCY_RE.match(text):
        findings.append(_finding(
            'high', 'currency-not-iso',
            f"offers.priceCurrency = {text!r} n'est pas un code ISO 4217 a trois "
            "lettres (ex: CAD).",
            'offers.priceCurrency',
        ))
        return
    if expected_currency and text != expected_currency.upper():
        findings.append(_finding(
            'medium', 'currency-unexpected',
            f"offers.priceCurrency = {text!r} alors que la boutique vend en "
            f"{expected_currency.upper()}.",
            'offers.priceCurrency',
        ))


def _check_availability(offer: dict, findings: list) -> None:
    raw = offer.get('availability')
    if _is_empty(raw):
        return
    text = _clean(raw)
    if _enum_name(text) in _AVAILABILITY_ENUM:
        return
    suggested = _availability_url(text)
    if suggested:
        findings.append(_finding(
            'high', 'availability-free-text',
            f"offers.availability = {text!r} est du texte libre. Le champ attend "
            f"l'enum Schema.org : {suggested}.",
            'offers.availability', suggestion=suggested,
        ))
    else:
        findings.append(_finding(
            'high', 'availability-unknown',
            f"offers.availability = {text!r} ne correspond a aucune valeur "
            "ItemAvailability de Schema.org.",
            'offers.availability',
        ))


def _check_return_policy(policy: dict, findings: list) -> None:
    for field in _REQUIRED_RETURN_POLICY_FIELDS:
        if _is_empty(policy.get(field)):
            findings.append(_finding(
                'medium', f'return-policy-{field}',
                f"hasMerchantReturnPolicy n'a pas de {field!r}.",
                f'hasMerchantReturnPolicy.{field}',
            ))
    category = policy.get('returnPolicyCategory')
    if not _is_empty(category) and _enum_name(_clean(category)) not in _RETURN_POLICY_ENUM:
        findings.append(_finding(
            'high', 'return-policy-category-invalid',
            f"returnPolicyCategory = {_clean(category)!r} n'est pas une enum "
            "MerchantReturnEnumeration (ex: "
            "https://schema.org/MerchantReturnFiniteReturnWindow).",
            'hasMerchantReturnPolicy.returnPolicyCategory',
        ))
    countries = [_clean(c).upper() for c in _as_list(policy.get('applicableCountry'))]
    if countries and 'CA' not in countries:
        findings.append(_finding(
            'medium', 'return-policy-country-ca',
            "applicableCountry ne contient pas 'CA' : la politique ne couvre pas "
            "les acheteurs canadiens.",
            'hasMerchantReturnPolicy.applicableCountry',
        ))


def _check_shipping(shipping: dict, findings: list) -> None:
    for field in _REQUIRED_SHIPPING_FIELDS:
        if _is_empty(shipping.get(field)):
            findings.append(_finding(
                'medium', f'shipping-{field}',
                f"OfferShippingDetails n'a pas de {field!r}.",
                f'shippingDetails.{field}',
            ))
    countries: list[str] = []
    for destination in _as_list(shipping.get('shippingDestination')):
        if isinstance(destination, dict):
            countries.extend(
                _clean(c).upper() for c in _as_list(destination.get('addressCountry'))
            )
    if countries and 'CA' not in countries:
        findings.append(_finding(
            'medium', 'shipping-country-ca',
            "shippingDestination ne contient pas 'CA' : aucune livraison declaree "
            "vers le Canada.",
            'shippingDetails.shippingDestination',
        ))


def validate_product(product: dict, *, expected_currency: str = 'CAD',
                     require_eu_energy: bool = False) -> list[dict]:
    """Merchant-listing findings for a Product JSON-LD block.

    `product` is the parsed JSON-LD: a single Product, or any blob holding one
    (a @graph, a list of nodes). The whole structure is walked, so a retired
    type nested three levels down is still caught.

    The Rich Results Test catches structural errors. This catches the policy
    errors, fields that parse fine and still disqualify the listing, plus the
    French-locale values a Quebec catalogue exports into enum fields.

    Returns findings sorted critical first, each with a boolean `critical` key.
    An empty list means nothing to fix.
    """
    findings: list[dict] = []

    for kind in _dedupe(_all_types(product)):
        retired = _RETIRED_TYPES.get(kind)
        if retired:
            findings.append(_finding(
                'critical' if retired['critical'] else 'medium',
                'retired-type',
                f"@type={kind!r} : {retired['message']}",
                '@type', retired=retired['retired'],
            ))

    products = list(_iter_typed(product, 'Product'))
    if not products:
        findings.append(_finding(
            'high', 'missing-product',
            "Aucun bloc @type=\"Product\" trouve dans le JSON-LD.",
        ))

    for prod in products:
        for field in _REQUIRED_PRODUCT_FIELDS:
            if _is_empty(prod.get(field)):
                findings.append(_finding(
                    'high', f'missing-product-{field}',
                    f"Le Product n'a pas de {field!r}, requis pour une fiche "
                    "marchande.", field,
                ))
        for field in _RECOMMENDED_PRODUCT_FIELDS:
            if _is_empty(prod.get(field)):
                findings.append(_finding(
                    'medium', f'recommended-product-{field}',
                    f"Le Product n'a pas de {field!r}, recommande par Google.",
                    field,
                ))

        for image in _as_list(prod.get('image')):
            candidate = image.get('url') if isinstance(image, dict) else image
            if _clean(candidate) and not _is_absolute_url(_clean(candidate)):
                findings.append(_finding(
                    'high', 'image-not-absolute',
                    f"image = {_clean(candidate)!r} est relative. Schema.org exige "
                    "une URL absolue.", 'image',
                ))

        offers = prod.get('offers')
        if isinstance(offers, dict):
            offers_list = [offers]
        elif isinstance(offers, list):
            offers_list = [o for o in offers if isinstance(o, dict)]
        else:
            offers_list = []

        for offer in offers_list:
            if _has_type(offer, 'AggregateOffer'):
                findings.append(_finding(
                    'high', 'merchant-listing-offer-type',
                    "Une fiche marchande exige offers.@type='Offer', pas "
                    "'AggregateOffer'.", 'offers.@type',
                ))
            elif not _has_type(offer, 'Offer'):
                findings.append(_finding(
                    'high', 'merchant-listing-offer-type',
                    "Une fiche marchande exige offers.@type='Offer'.",
                    'offers.@type',
                ))
            for field in _RECOMMENDED_OFFER_FIELDS:
                if _is_empty(offer.get(field)):
                    findings.append(_finding(
                        'medium', f'recommended-offer-{field}',
                        f"L'Offer n'a pas de {field!r}, recommande par Google.",
                        f'offers.{field}',
                    ))
            _check_price(offer, findings)
            _check_currency(offer, expected_currency, findings)
            _check_availability(offer, findings)

        return_policy = prod.get('hasMerchantReturnPolicy') or (
            offers_list[0].get('hasMerchantReturnPolicy') if offers_list else None
        )
        if not return_policy:
            findings.append(_finding(
                'medium', 'missing-return-policy',
                "Ni le Product ni son Offer ne declarent hasMerchantReturnPolicy.",
                'hasMerchantReturnPolicy',
            ))
        elif isinstance(return_policy, dict):
            _check_return_policy(return_policy, findings)

        shipping = prod.get('shippingDetails') or (
            offers_list[0].get('shippingDetails') if offers_list else None
        )
        if not shipping:
            findings.append(_finding(
                'medium', 'missing-shipping-details',
                "Ni le Product ni son Offer ne declarent shippingDetails.",
                'shippingDetails',
            ))
        elif isinstance(shipping, dict):
            _check_shipping(shipping, findings)

        # Loyalty pricing is a Google Shopping bonus, not a listing gate.
        # Upstream files it as Medium; at Medium it fires on every product of
        # every small merchant, which is noise, so it lands as info here.
        has_tier_pricing = any(
            isinstance(o.get('priceSpecification'), dict)
            and o['priceSpecification'].get('validForMemberTier')
            for o in offers_list
        )
        if not prod.get('hasMemberProgram') and not has_tier_pricing:
            findings.append(_finding(
                'info', 'missing-member-program',
                "Aucun MemberProgram ni prix membre declare : le prix fidelite ne "
                "s'affichera pas dans Google Shopping.", 'hasMemberProgram',
            ))

        if require_eu_energy and _is_empty(prod.get('energyEfficiencyClass')):
            findings.append(_finding(
                'high', 'missing-eu-energy-class',
                "Mode UE : les categories visees par EPREL exigent "
                "energyEfficiencyClass.", 'energyEfficiencyClass',
            ))

    if products and not list(_iter_typed(product, 'ProductGroup')):
        findings.append(_finding(
            'info', 'no-product-group',
            "Si le produit a des variantes (taille, couleur), declare un "
            "ProductGroup : Google le demande de plus en plus pour le vetement.",
        ))

    findings.sort(key=lambda f: _SEVERITY_RANK.get(f['severity'], 9))
    return findings


def has_blocking_findings(findings: list[dict]) -> bool:
    """True when at least one finding blocks the rich result."""
    return any(f.get('severity') in ('critical', 'high') for f in findings)


def summarize_findings(findings: list[dict]) -> dict:
    """Counts per severity plus `ok`, the shape the dashboard renders."""
    summary = {level: 0 for level in _SEVERITY_RANK}
    for finding in findings:
        level = finding.get('severity')
        if level in summary:
            summary[level] += 1
    summary['total'] = len(findings)
    summary['ok'] = not has_blocking_findings(findings)
    return summary
