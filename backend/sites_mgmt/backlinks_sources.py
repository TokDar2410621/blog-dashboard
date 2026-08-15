"""Complementary backlink sources: Moz, Bing Webmaster, merge and sufficiency gate.

Porte depuis claude-seo v2.2.4 `scripts/moz_api.py` et `scripts/bing_webmaster.py`,
avec la regle de suffisance de `skills/seo-backlinks/SKILL.md`.
Copyright (c) 2025 Daniel Agrici (AgriciDaniel). MIT.
https://github.com/AgriciDaniel/claude-seo

Upstream ships two CLI clients that print JSON, plus a health-score rule written
as prose in the skill file; this port keeps the wire protocol of both clients and
turns the prose rule into `merge_sources` and `data_sufficiency`. The lockfile
rate limiter is dropped for the reason `api_budget` dropped its own: Railway runs
several instances and a file lock spans none of them, so a 429 comes back as a
French status instead of being slept away inside a request thread. Deduplication
moves from raw hostname to registrable domain, because three sources naming
`blog.x.com`, `www.x.com` and `x.com` describe one referring domain and not three,
and each merged domain carries a noisy-OR confidence so agreement between sources
is what raises it. One rule is added that upstream lacks: sources that all answer
and all find nothing describe an empty profile, not missing data, so that case is
allowed to score instead of being refused forever.
"""
from __future__ import annotations

import re
import time
from base64 import b64encode
from urllib.parse import urlparse, urlunparse

# moz.com and ssl.bing.com are hardcoded hosts, never caller-supplied, so plain
# `requests` is correct here. Anything whose URL comes from a third party (a
# referring page to verify, for instance) must go through
# `from .url_safety import safe_get` instead: this module never fetches one.
import requests

__all__ = [
    'CONFIANCE_SOURCES',
    'LIBELLES_SOURCES',
    'CATALOGUE_SOURCES',
    'STATUTS_REPONDU',
    'MESSAGE_BING_VERIFICATION',
    'TARIFS_VERIFIES_LE',
    'DELAI_MOZ_SECONDES',
    'registrable_domain',
    'fetch_moz',
    'fetch_bing_webmaster',
    'merge_sources',
    'data_sufficiency',
]


# --------------------------------------------------------------------------
# Constants
# --------------------------------------------------------------------------

# Confidence per source, taken from the weighting table of
# `skills/seo-backlinks/SKILL.md`. These are not accuracy measurements, they are
# the order upstream trusts the providers in, and the merge only uses them to
# rank and to combine. `verification` is the direct link check, which outranks
# every index because it looks at the live page.
CONFIANCE_SOURCES = {
    'dataforseo': 1.00,
    'verification': 0.95,
    'moz': 0.85,
    'bing_webmaster': 0.70,
    'commoncrawl': 0.50,
}
CONFIANCE_INCONNUE = 0.40

LIBELLES_SOURCES = {
    'dataforseo': 'DataForSEO',
    'verification': 'Vérification directe des liens',
    'moz': 'Moz Link Explorer',
    'bing_webmaster': 'Bing Webmaster Tools',
    'commoncrawl': 'Common Crawl',
}

# Shown to the operator when the gate refuses a score and has to say what would
# unblock it. `contrainte` is what stops a source from being usable on a client
# site even when the key exists.
CATALOGUE_SOURCES = {
    'commoncrawl': {
        'libelle': 'Common Crawl',
        'cout': 'gratuit, aucune clé',
        'mise_en_place': 'rien à configurer, le graphe web est public',
        'contrainte': 'mis à jour par trimestre, donc aveugle aux liens récents',
    },
    'moz': {
        'libelle': 'Moz Link Explorer',
        'cout': 'palier gratuit, puis payant',
        'mise_en_place': 'créer une clé API sur moz.com/products/api',
        'contrainte': 'quota mensuel serré et une requête toutes les 10 secondes',
    },
    'bing_webmaster': {
        'libelle': 'Bing Webmaster Tools',
        'cout': 'gratuit',
        'mise_en_place': 'clé API Bing Webmaster',
        'contrainte': (
            'le site doit être vérifié dans le compte qui détient la clé, '
            'donc réservé aux sites de Gridar'
        ),
    },
}

# Bing hands link data back only for properties verified inside the account that
# owns the key. Verifying a client site means dropping a file or a DNS record in
# their infrastructure, which is exactly what Gridar promises never to touch. The
# constant exists so the gate, the fetcher and the report all say the same thing.
MESSAGE_BING_VERIFICATION = (
    'Bing Webmaster ne répond que pour les sites vérifiés dans le compte qui détient '
    'la clé. Utilisable pour les sites de Darius, pas pour ceux de ses clients.'
)

# Free-tier terms and rate limits move without notice. Anything stated in
# CATALOGUE_SOURCES was read on this date; past a couple of months, re-verify
# before quoting a quota to an operator.
TARIFS_VERIFIES_LE = '2026-08-14'

# Moz free tier historically allows one request every ten seconds. This module
# never sleeps on its own (see `pause_s` in `fetch_moz`); the constant is here so
# a scheduled worker can space its calls without re-deriving the number.
DELAI_MOZ_SECONDES = 10

MOZ_BASE = 'https://api.moz.com'
MOZ_CHEMIN_METRIQUES = '/v2/url_metrics'
MOZ_CHEMIN_DOMAINES = '/v2/linking_root_domains'
MOZ_LIMITE_DOMAINES = 50

BING_BASE = 'https://ssl.bing.com/webmaster/api.svc/json'
BING_LIMITE_CIBLES = 10

_AGENT = 'Gridar/1.0 (+https://gridar.app)'

# Statuses where the provider answered. A source can answer and carry nothing,
# which is a different thing from a source that failed, and the gate needs to
# tell them apart.
STATUTS_REPONDU = frozenset({'ok', 'partiel', 'vide'})

# Suffixes where the registrable domain sits three labels deep. The Canadian
# provincial ones matter most here: Quebec clinics, municipalities and school
# boards sit under *.qc.ca, and collapsing that to `qc.ca` would merge unrelated
# referring domains into one and inflate every confidence index built on top.
_SUFFIXES_MULTI_LABELS = frozenset({
    'ab.ca', 'bc.ca', 'gc.ca', 'mb.ca', 'nb.ca', 'nf.ca', 'nl.ca', 'ns.ca',
    'nt.ca', 'nu.ca', 'on.ca', 'pe.ca', 'qc.ca', 'sk.ca', 'yk.ca',
    'ac.uk', 'co.uk', 'gov.uk', 'org.uk',
    'com.au', 'net.au', 'org.au',
    'co.nz', 'co.jp', 'co.za', 'com.br', 'com.mx',
})

_HOTE_VALIDE = re.compile(r'^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)+$')

# Metrics the merge knows how to label and to reconcile. Anything else a source
# carries is passed through with its own key and no French label.
METRIQUES_CONNUES = {
    'autorite_domaine': ('Autorité de domaine', 'echelle'),
    'autorite_page': ('Autorité de page', 'echelle'),
    'score_spam': ('Score de spam', 'echelle'),
    'domaines_referents_total': ('Domaines référents (total annoncé)', 'compte'),
    'liens_externes_total': ('Liens entrants (total annoncé)', 'compte'),
    'pagerank': ('PageRank Common Crawl', 'ratio'),
    'centralite_harmonique': ('Centralité harmonique', 'ratio'),
}

# Two sources rarely agree to the unit on a count, so only a gap wide enough to
# change a decision is reported. On a 0-100 authority scale, 20 points separate
# "small site" from "reference site"; on a raw count, one source seeing three
# times what another sees means one of them is not measuring the same thing.
_ECART_ECHELLE = 20
_RATIO_COMPTE = 3.0

_AXES = (
    ('domaines_referents', 'Liste des domaines référents'),
    ('autorite', 'Autorité (domaine ou page)'),
    ('spam', 'Score de spam'),
    ('ancres', 'Textes d ancre'),
    ('volume_liens', 'Volume de liens annoncé'),
)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _masquer(texte: str, *secrets: str) -> str:
    """Replace any credential that leaked into a message with a placeholder.

    Belt and braces: nothing in this module puts a key into a message on
    purpose, but a provider is free to echo a query string back inside an error
    body, and that body reaches a log.
    """
    resultat = texte or ''
    for secret in secrets:
        if secret and len(secret) >= 6 and secret in resultat:
            resultat = resultat.replace(secret, '***')
    return resultat


def _entier(valeur, defaut=None):
    """Coerce a provider value to a non-negative int, or the default."""
    if isinstance(valeur, bool) or valeur is None:
        return defaut
    try:
        return max(0, int(valeur))
    except (TypeError, ValueError, OverflowError):
        return defaut


def _flottant(valeur, defaut=None):
    if isinstance(valeur, bool) or valeur is None:
        return defaut
    try:
        nombre = float(valeur)
    except (TypeError, ValueError, OverflowError):
        return defaut
    if nombre != nombre or nombre in (float('inf'), float('-inf')):
        return defaut
    return nombre


def _texte(valeur, limite: int = 200) -> str:
    if not isinstance(valeur, str):
        return ''
    return valeur.strip()[:limite]


def _hote(valeur: str) -> str:
    """Hostname of a URL, or the value itself when it already is a hostname."""
    brut = (valeur or '').strip().lower()
    if not brut:
        return ''
    if '://' not in brut:
        # A bare `example.com/page` parses as a path, so give it a scheme first.
        brut = 'https://' + brut.lstrip('/')
    try:
        hote = urlparse(brut).hostname or ''
    except ValueError:
        return ''
    return hote.strip('.').lower()


def registrable_domain(valeur: str) -> str:
    """Collapse a hostname or URL to the part that identifies its owner.

    Deduplication of referring domains rests entirely on this: get it wrong and
    a single site counted under three hostnames looks like three independent
    votes of confidence. `sites_mgmt.sitemap_discovery` holds an equivalent
    private helper; this one is deliberately public and self-contained so the
    merge does not depend on another module's internals.
    """
    hote = _hote(valeur)
    if not hote:
        return ''
    if ':' in hote or hote.replace('.', '').isdigit():
        return hote  # IP literal, no label structure to collapse
    labels = [label for label in hote.split('.') if label]
    if len(labels) <= 2:
        return '.'.join(labels)
    if '.'.join(labels[-2:]) in _SUFFIXES_MULTI_LABELS:
        return '.'.join(labels[-3:])
    return '.'.join(labels[-2:])


def _domaine_cible(domain: str) -> str:
    """Normalize the audited domain, `www.` stripped, or raise ValueError.

    The domain is never fetched here, it only travels as a parameter to a
    trusted host, so there is no SSRF surface. The shape is still checked so a
    malformed value fails in Gridar instead of turning into a strange query.
    """
    hote = _hote(domain)
    if hote.startswith('www.'):
        hote = hote[4:]
    if not hote or not _HOTE_VALIDE.match(hote):
        raise ValueError('Le domaine doit être un nom d hôte public, par exemple exemple.com.')
    return hote


def _url_affichable(url: str) -> str:
    """Strip userinfo, query and fragment from a URL a provider handed back.

    These end up in the dashboard, and a referring URL can carry a session token
    in its query string.
    """
    brut = (url or '').strip()
    if not brut:
        return ''
    if '://' not in brut:
        brut = 'https://' + brut.lstrip('/')
    try:
        parsed = urlparse(brut)
        hote = parsed.hostname or ''
        try:
            port = parsed.port
        except ValueError:
            port = None
    except ValueError:
        return ''
    if not hote:
        return ''
    if port:
        hote = '%s:%d' % (hote, port)
    return urlunparse((parsed.scheme or 'https', hote, parsed.path or '/', '', '', ''))


def _horodatage() -> str:
    return time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())


def _noisy_or(confiances) -> float:
    """Combine independent confirmations without ever exceeding 1.

    Two sources at 0.85 and 0.50 give 0.925: more than either alone, less than
    certainty. Summing would have crossed 1 and made "seen by three weak sources"
    look like a verified fact.
    """
    reste = 1.0
    vu = False
    for valeur in confiances:
        nombre = _flottant(valeur)
        if nombre is None:
            continue
        vu = True
        nombre = min(max(nombre, 0.0), 1.0)
        reste *= (1.0 - nombre)
    if not vu:
        return 0.0
    return round(1.0 - reste, 4)


def _resultat_source(source: str, statut: str, *, domaine: str = '',
                     message: str = '', metriques=None, domaines=None,
                     erreur=None, brut=None) -> dict:
    """Shape every fetcher returns, so the merge has one contract to read."""
    return {
        'source': source,
        'libelle': LIBELLES_SOURCES.get(source, source),
        'statut': statut,
        'confiance': CONFIANCE_SOURCES.get(source, CONFIANCE_INCONNUE),
        'domaine': domaine,
        'metriques': metriques or {},
        'domaines_referents': domaines or [],
        'message': message,
        'erreur': erreur,
        'horodatage': _horodatage(),
        'brut': brut or {},
    }


# --------------------------------------------------------------------------
# Moz Link Explorer
# --------------------------------------------------------------------------

def _entetes_moz(access_id: str, secret_key: str) -> dict:
    """Basic auth on accessId:secretKey, or the newer single-token header.

    Moz issued accessId plus secret for years and now issues one API token. The
    signature keeps two arguments because that is what the older keys look like;
    passing the token alone as `access_id` with an empty secret selects the
    token header instead of inventing a broken `token:` pair.
    """
    entetes = {
        'Content-Type': 'application/json',
        'User-Agent': _AGENT,
    }
    if secret_key:
        jeton = b64encode(('%s:%s' % (access_id, secret_key)).encode('utf-8')).decode('ascii')
        entetes['Authorization'] = 'Basic ' + jeton
    else:
        entetes['x-moz-token'] = access_id
    return entetes


def _appel_moz(chemin: str, corps: dict, entetes: dict, timeout: int,
               secrets) -> tuple:
    """POST to Moz. Returns (statut, payload, message).

    `statut` is one of ok / non_autorise / limite_atteinte / erreur. Nothing in
    the message ever carries a credential: `_masquer` runs on whatever the
    provider echoed back.
    """
    try:
        reponse = requests.post(
            MOZ_BASE + chemin,
            json=corps,
            headers=entetes,
            timeout=timeout,
            allow_redirects=False,
        )
    except requests.exceptions.Timeout:
        return 'erreur', None, 'Moz n a pas répondu dans le délai imparti.'
    except requests.exceptions.RequestException as exc:
        # Never str(exc): requests puts the request URL in it, and a future
        # refactor that moves the key into a query string would leak it here.
        return 'erreur', None, 'Appel Moz échoué (%s).' % type(exc).__name__

    code = getattr(reponse, 'status_code', 0)
    if code == 401:
        return 'non_autorise', None, 'Clé Moz refusée. Vérifiez-la sur moz.com/products/api.'
    if code == 403:
        return ('non_autorise', None,
                'Moz refuse cet appel. Le palier gratuit ne couvre pas toujours ce point d accès.')
    if code == 429:
        return ('limite_atteinte', None,
                'Quota Moz atteint. Le palier gratuit tolère un appel toutes les %d secondes.'
                % DELAI_MOZ_SECONDES)
    if code >= 400:
        detail = ''
        try:
            corps_erreur = reponse.json()
        except (ValueError, AttributeError):
            corps_erreur = None
        if isinstance(corps_erreur, dict):
            detail = _texte(corps_erreur.get('error') or corps_erreur.get('message'), 120)
        message = 'Moz a répondu HTTP %s.' % code
        if detail:
            message += ' ' + _masquer(detail, *secrets)
        return 'erreur', None, message

    try:
        charge = reponse.json()
    except (ValueError, AttributeError):
        return 'erreur', None, 'Moz a renvoyé une réponse illisible.'
    if not isinstance(charge, dict):
        return 'erreur', None, 'Moz a renvoyé une réponse de forme inattendue.'
    return 'ok', charge, ''


def fetch_moz(domain: str, access_id: str, secret_key: str, *, timeout: int = 20,
              limite_domaines: int = MOZ_LIMITE_DOMAINES, pause_s: float = 0.0,
              inclure_domaines: bool = True) -> dict:
    """Domain authority, page authority and referring domains, read from Moz.

    Args:
        domain: the audited domain. `www.` and any scheme are stripped.
        access_id: Moz accessId, or the whole API token when `secret_key` is empty.
        secret_key: Moz secret. Empty selects the single-token header.
        timeout: seconds per HTTP call.
        limite_domaines: how many referring domains to ask for, capped at 50 by Moz.
        pause_s: seconds to wait between the two calls. Left at 0 on purpose:
            this runs inside a Django request thread and blocking one for ten
            seconds is worse than reporting the 429. A scheduled worker that owns
            its own thread should pass `DELAI_MOZ_SECONDES`.
        inclure_domaines: False skips the second call and returns authority only.

    Returns:
        The source dict `merge_sources` and `data_sufficiency` read:
        {'source', 'libelle', 'statut', 'confiance', 'domaine', 'metriques',
         'domaines_referents', 'message', 'erreur', 'horodatage', 'brut'}.
        `statut` is ok / partiel / vide / non_configure / non_autorise /
        limite_atteinte / erreur.

    Cost: Moz keeps a free tier, quota-limited per month and rate-limited to
    roughly one call every ten seconds. Each successful run here spends two
    quota units, one per endpoint. Verified on TARIFS_VERIFIES_LE.

    Never raises on a network or provider failure: the failure comes back as a
    status the gate can count. Only a malformed `domain` raises ValueError.
    """
    cible = _domaine_cible(domain)
    access_id = (access_id or '').strip()
    secret_key = (secret_key or '').strip()
    if not access_id:
        return _resultat_source(
            'moz', 'non_configure', domaine=cible,
            message='Aucune clé Moz configurée. Le palier gratuit suffit pour démarrer.',
            erreur='cle_absente',
        )

    secrets = (access_id, secret_key)
    entetes = _entetes_moz(access_id, secret_key)

    statut, charge, message = _appel_moz(
        MOZ_CHEMIN_METRIQUES, {'targets': [cible]}, entetes, timeout, secrets,
    )
    if statut != 'ok':
        return _resultat_source('moz', statut, domaine=cible, message=message,
                                erreur=statut)

    resultats = charge.get('results')
    premier = resultats[0] if isinstance(resultats, list) and resultats else {}
    if not isinstance(premier, dict):
        premier = {}

    metriques = {
        'autorite_domaine': _entier(premier.get('domain_authority')),
        'autorite_page': _entier(premier.get('page_authority')),
        'score_spam': _entier(premier.get('spam_score')),
        'domaines_referents_total': _entier(premier.get('root_domains_to_root_domain')),
        'liens_externes_total': _entier(premier.get('external_pages_to_root_domain')),
    }
    metriques = {cle: valeur for cle, valeur in metriques.items() if valeur is not None}
    derniere = _texte(premier.get('last_crawled'), 40)

    if not inclure_domaines:
        statut_final = 'ok' if metriques else 'vide'
        return _resultat_source(
            'moz', statut_final, domaine=cible, metriques=metriques,
            message='Autorité lue chez Moz, liste des domaines référents non demandée.',
            brut={'derniere_exploration': derniere},
        )

    if pause_s and pause_s > 0:
        time.sleep(pause_s)

    limite = max(1, min(_entier(limite_domaines, MOZ_LIMITE_DOMAINES) or MOZ_LIMITE_DOMAINES,
                        MOZ_LIMITE_DOMAINES))
    statut_domaines, charge_domaines, message_domaines = _appel_moz(
        MOZ_CHEMIN_DOMAINES,
        {'target': cible, 'target_scope': 'root_domain', 'limit': limite},
        entetes, timeout, secrets,
    )

    if statut_domaines != 'ok':
        # Authority alone is still worth something to the merge, so a failure on
        # the second call downgrades the status instead of discarding the first.
        return _resultat_source(
            'moz', 'partiel', domaine=cible, metriques=metriques,
            message='Autorité lue chez Moz. Domaines référents indisponibles : ' + message_domaines,
            erreur=statut_domaines,
            brut={'derniere_exploration': derniere},
        )

    domaines = []
    for element in (charge_domaines.get('results') or []):
        if not isinstance(element, dict):
            continue
        nom = registrable_domain(_texte(element.get('root_domain'), 253))
        if not nom:
            continue
        vers_cible = element.get('to_target')
        liens = _entier(vers_cible.get('pages'), 1) if isinstance(vers_cible, dict) else 1
        domaines.append({
            'domaine': nom,
            'autorite_domaine': _entier(element.get('domain_authority')),
            'score_spam': _entier(element.get('spam_score')),
            'liens': liens if liens is not None else 1,
        })

    statut_final = 'ok' if (domaines or metriques) else 'vide'
    if domaines:
        message = 'Moz renvoie %d domaine(s) référent(s).' % len(domaines)
    else:
        message = 'Moz ne connaît aucun domaine référent pour ce site.'
    return _resultat_source('moz', statut_final, domaine=cible, metriques=metriques,
                            domaines=domaines, message=message,
                            brut={'derniere_exploration': derniere})


# --------------------------------------------------------------------------
# Bing Webmaster Tools
# --------------------------------------------------------------------------

def _payload_bing(charge):
    """Unwrap Bing's `d` envelope without trusting the shape it arrives in."""
    if not isinstance(charge, dict):
        return {}
    interne = charge.get('d', charge)
    return interne if isinstance(interne, dict) else {}


def _appel_bing(point: str, params: dict, api_key: str, timeout: int) -> tuple:
    """GET a Bing Webmaster endpoint. Returns (statut, payload, message).

    `allow_redirects=False` matters more than usual: the key travels in the
    query string, and requests carries the query across a redirect, so a
    redirect off ssl.bing.com would hand the key to whatever answered.
    """
    parametres = dict(params)
    parametres['apikey'] = api_key
    try:
        reponse = requests.get(
            '%s/%s' % (BING_BASE, point),
            params=parametres,
            headers={'Content-Type': 'application/json', 'User-Agent': _AGENT},
            timeout=timeout,
            allow_redirects=False,
        )
    except requests.exceptions.Timeout:
        return 'erreur', None, 'Bing Webmaster n a pas répondu dans le délai imparti.'
    except requests.exceptions.RequestException as exc:
        # str(exc) would carry the request URL, and the URL carries the key.
        return 'erreur', None, 'Appel Bing Webmaster échoué (%s).' % type(exc).__name__

    code = getattr(reponse, 'status_code', 0)
    if code == 401:
        return 'non_autorise', None, 'Clé Bing Webmaster refusée.'
    if code == 403:
        return 'non_autorise', None, 'Bing refuse l accès. ' + MESSAGE_BING_VERIFICATION
    if code == 429:
        return 'limite_atteinte', None, 'Quota Bing Webmaster atteint. Réessayez plus tard.'
    if code >= 400:
        # No raise_for_status: its message embeds the full URL, key included.
        return 'erreur', None, 'Bing Webmaster a répondu HTTP %s.' % code

    texte = getattr(reponse, 'text', '') or ''
    if not texte.strip():
        return 'ok', {}, ''
    try:
        charge = reponse.json()
    except (ValueError, AttributeError):
        return 'erreur', None, 'Bing Webmaster a renvoyé une réponse illisible.'
    return 'ok', _payload_bing(charge), ''


def fetch_bing_webmaster(domain: str, api_key: str, *, timeout: int = 20,
                         limite_cibles: int = BING_LIMITE_CIBLES) -> dict:
    """Inbound links as Bing sees them, for a property verified in the key's account.

    Bing only answers for sites verified inside the account holding the key, and
    verifying a site means writing a file or a DNS record into its
    infrastructure. Gridar never touches a client's code or hosting, so this
    source is for Darius's own sites and not for client sites. Calling it on a
    client domain returns `non_autorise` with that explanation, which is the
    honest answer rather than an empty profile that reads like "no backlinks".

    Args:
        domain: the audited domain, verified in the Bing account.
        api_key: Bing Webmaster API key. Never appears in a message or a log.
        timeout: seconds per HTTP call.
        limite_cibles: how many linked pages to expand. Each one costs a call,
            so the run stays bounded at 1 + limite_cibles requests.

    Returns:
        The same source dict as `fetch_moz`. Links whose source sits on the
        audited domain are internal navigation, not backlinks, and are counted
        under `brut['liens_internes']` instead of inflating the profile.

    Cost: free with a Bing Webmaster account. No published per-call price;
    throttling is by account. Verified on TARIFS_VERIFIES_LE.
    """
    cible = _domaine_cible(domain)
    api_key = (api_key or '').strip()
    if not api_key:
        return _resultat_source(
            'bing_webmaster', 'non_configure', domaine=cible,
            message='Aucune clé Bing Webmaster configurée. ' + MESSAGE_BING_VERIFICATION,
            erreur='cle_absente',
        )

    site_url = 'https://%s/' % cible
    statut, charge, message = _appel_bing(
        'GetLinkCounts', {'siteUrl': site_url, 'page': 0}, api_key, timeout,
    )
    if statut != 'ok':
        return _resultat_source('bing_webmaster', statut, domaine=cible,
                                message=message, erreur=statut)

    cibles_brutes = charge.get('Links')
    cibles_brutes = cibles_brutes if isinstance(cibles_brutes, list) else []
    cibles = [item for item in cibles_brutes
              if isinstance(item, dict) and _texte(item.get('Url'), 2048)]
    cibles.sort(key=lambda item: _entier(item.get('Count'), 0) or 0, reverse=True)
    limite = max(1, _entier(limite_cibles, BING_LIMITE_CIBLES) or BING_LIMITE_CIBLES)
    cibles = cibles[:limite]

    liens_annonces = sum((_entier(item.get('Count'), 0) or 0) for item in cibles_brutes
                         if isinstance(item, dict))
    pages_totales = max(1, _entier(charge.get('TotalPages'), 1) or 1)
    complet = len(cibles) == len(cibles_brutes) and pages_totales <= 1

    par_domaine = {}
    liens_internes = 0
    appels_reussis = 0
    echecs = []

    for item in cibles:
        url_cible = item['Url']
        statut_detail, detail, message_detail = _appel_bing(
            'GetUrlLinks', {'siteUrl': site_url, 'link': url_cible, 'page': 0},
            api_key, timeout,
        )
        if statut_detail != 'ok':
            echecs.append(_url_affichable(url_cible))
            complet = False
            continue
        appels_reussis += 1
        details = detail.get('Details')
        details = details if isinstance(details, list) else []
        if max(1, _entier(detail.get('TotalPages'), 1) or 1) > 1:
            complet = False
        for lien in details:
            if not isinstance(lien, dict):
                continue
            url_source = _texte(lien.get('Url'), 2048)
            nom = registrable_domain(url_source)
            if not nom:
                continue
            if nom == registrable_domain(cible):
                liens_internes += 1
                continue
            entree = par_domaine.setdefault(nom, {
                'domaine': nom, 'liens': 0, 'ancres': [], 'urls': [],
            })
            entree['liens'] += 1
            ancre = _texte(lien.get('AnchorText'), 120)
            if ancre and ancre not in entree['ancres']:
                entree['ancres'].append(ancre)
            url_propre = _url_affichable(url_source)
            if url_propre and url_propre not in entree['urls']:
                entree['urls'].append(url_propre)

    if cibles and appels_reussis == 0:
        return _resultat_source(
            'bing_webmaster', 'erreur', domaine=cible,
            message='Bing annonce des pages liées mais aucune n a pu être ouverte.',
            erreur='expansion_impossible',
        )

    metriques = {}
    if liens_annonces:
        metriques['liens_externes_total'] = liens_annonces

    domaines = sorted(par_domaine.values(), key=lambda item: (-item['liens'], item['domaine']))
    if domaines:
        statut_final = 'ok' if complet and not echecs else 'partiel'
        message = 'Bing voit %d domaine(s) référent(s) sur les pages inspectées.' % len(domaines)
    elif cibles:
        statut_final = 'partiel'
        message = 'Bing annonce des pages liées mais n a renvoyé aucun lien entrant exploitable.'
    else:
        statut_final = 'vide'
        message = 'Bing ne voit aucun lien entrant vers ce site.'

    return _resultat_source(
        'bing_webmaster', statut_final, domaine=cible, metriques=metriques,
        domaines=domaines, message=message,
        brut={
            'liens_internes': liens_internes,
            'cibles_disponibles': len(cibles_brutes),
            'cibles_ouvertes': appels_reussis,
            'cibles_en_echec': echecs,
            'complet': complet,
            'note': MESSAGE_BING_VERIFICATION,
        },
    )


# --------------------------------------------------------------------------
# Normalisation of anything a caller hands to the merge
# --------------------------------------------------------------------------

_CLES_DOMAINE = ('domaine', 'domain', 'root_domain', 'source_url', 'url', 'hote', 'host')
_CLES_AUTORITE = ('autorite_domaine', 'domain_authority', 'autorite', 'authority', 'da')
_CLES_SPAM = ('score_spam', 'spam_score', 'spam')
_CLES_LIENS = ('liens', 'links', 'links_to_target', 'external_links', 'count')
_CLES_ANCRE = ('ancre', 'anchor', 'anchor_text')

_ALIAS_METRIQUES = {
    'domain_authority': 'autorite_domaine',
    'page_authority': 'autorite_page',
    'spam_score': 'score_spam',
    'linking_root_domains': 'domaines_referents_total',
    'root_domains_to_root_domain': 'domaines_referents_total',
    'referring_domains_count': 'domaines_referents_total',
    'external_links': 'liens_externes_total',
    'external_pages_to_root_domain': 'liens_externes_total',
    'sampled_inbound_link_count': 'liens_externes_total',
    'harmonic_centrality': 'centralite_harmonique',
}


# Substrings that identify a provider when a source describes itself in prose
# instead of naming a key. Ordered so the longest, least ambiguous match wins.
_INDICES_SOURCE = (
    ('common crawl', 'commoncrawl'),
    ('commoncrawl', 'commoncrawl'),
    ('bing', 'bing_webmaster'),
    ('dataforseo', 'dataforseo'),
    ('moz', 'moz'),
)


def _deviner_source(charge: dict) -> str:
    """Recover a provider name from a nested dataset descriptor."""
    descripteur = charge.get('jeu_de_donnees')
    if not isinstance(descripteur, dict):
        return ''
    etiquette = _texte(descripteur.get('source'), 120).lower()
    for indice, nom in _INDICES_SOURCE:
        if indice in etiquette:
            return nom
    return ''


def _valeur_parmi(element: dict, cles):
    for cle in cles:
        if cle in element and element[cle] is not None:
            return element[cle]
    return None


def _normaliser_domaines(brut, ancres_max: int, urls_max: int) -> tuple:
    """Turn any referring-domain list into the merge's entry shape.

    Accepts plain strings, source URLs, and dicts keyed the way Moz, Bing or a
    hand-rolled source spell them. Returns (entries, unreadable_count).
    """
    entrees = []
    illisibles = 0
    if not isinstance(brut, (list, tuple)):
        return entrees, illisibles
    for element in brut:
        if isinstance(element, str):
            nom = registrable_domain(element)
            if not nom:
                illisibles += 1
                continue
            entrees.append({'domaine': nom, 'autorite_domaine': None, 'score_spam': None,
                            'liens': 1, 'ancres': [], 'urls': []})
            continue
        if not isinstance(element, dict):
            illisibles += 1
            continue
        nom = registrable_domain(_texte(_valeur_parmi(element, _CLES_DOMAINE), 2048))
        if not nom:
            illisibles += 1
            continue
        ancres = element.get('ancres')
        if isinstance(ancres, str):
            ancres = [ancres]
        elif not isinstance(ancres, (list, tuple)):
            ancre_seule = _texte(_valeur_parmi(element, _CLES_ANCRE), 120)
            ancres = [ancre_seule] if ancre_seule else []
        urls = element.get('urls')
        if not isinstance(urls, (list, tuple)):
            url_seule = _texte(element.get('source_url') or element.get('url'), 2048)
            urls = [url_seule] if url_seule else []
        entrees.append({
            'domaine': nom,
            'autorite_domaine': _entier(_valeur_parmi(element, _CLES_AUTORITE)),
            'score_spam': _entier(_valeur_parmi(element, _CLES_SPAM)),
            'liens': _entier(_valeur_parmi(element, _CLES_LIENS), 1) or 1,
            'ancres': [_texte(ancre, 120) for ancre in ancres if _texte(ancre, 120)][:ancres_max],
            'urls': [_url_affichable(url) for url in urls if _url_affichable(url)][:urls_max],
        })
    return entrees, illisibles


def _normaliser_metriques(brut) -> dict:
    metriques = {}
    if not isinstance(brut, dict):
        return metriques
    for cle, valeur in brut.items():
        if not isinstance(cle, str):
            continue
        nom = _ALIAS_METRIQUES.get(cle, cle)
        if nom in ('pagerank', 'centralite_harmonique'):
            nombre = _flottant(valeur)
        elif nom in METRIQUES_CONNUES:
            nombre = _entier(valeur)
        else:
            nombre = _flottant(valeur)
        if nombre is not None:
            metriques[nom] = nombre
    return metriques


def _normaliser_source(brut, ancres_max: int, urls_max: int) -> dict:
    """Read one source, whatever shape it arrives in.

    Three shapes are accepted: what the fetchers above return, the upstream CLI
    envelope {'status', 'data', 'error', 'metadata'}, and a loose dict that just
    names a source and lists referring domains. Being permissive here is the
    point: Common Crawl is ported separately and its output must drop in without
    either module knowing about the other.
    """
    if not isinstance(brut, dict):
        return {}

    charge = brut
    enveloppe = brut.get('data')
    metadonnees = brut.get('metadata') if isinstance(brut.get('metadata'), dict) else {}
    if isinstance(enveloppe, dict) and 'source' not in brut:
        charge = dict(enveloppe)
        charge.setdefault('source', metadonnees.get('source', ''))

    nom = _texte(charge.get('source') or brut.get('source') or metadonnees.get('source'), 40).lower()
    if nom not in CONFIANCE_SOURCES:
        # A port that names itself inside a nested dataset descriptor rather
        # than at the top level would otherwise land as 'inconnue' and lose the
        # confidence its provider is entitled to.
        nom = _deviner_source(charge) or nom
    if not nom:
        nom = 'inconnue'

    statut = _texte(brut.get('statut') or charge.get('statut'), 30).lower()
    if not statut:
        # Upstream envelope: success / partial / error / rate_limited.
        equivalences = {
            'success': 'ok', 'partial': 'partiel', 'error': 'erreur',
            'rate_limited': 'limite_atteinte',
        }
        statut = equivalences.get(_texte(brut.get('status'), 30).lower(), '')

    confiance = _flottant(brut.get('confiance', brut.get('confidence')))
    if confiance is None:
        confiance = CONFIANCE_SOURCES.get(nom, CONFIANCE_INCONNUE)
    confiance = min(max(confiance, 0.0), 1.0)

    liste = charge.get('domaines_referents')
    if liste is None:
        liste = charge.get('referring_domains')
    if liste is None:
        liste = charge.get('links')
    domaines, illisibles = _normaliser_domaines(liste, ancres_max, urls_max)

    metriques = _normaliser_metriques(charge.get('metriques'))
    if not metriques:
        # A source may expose its numbers flat, the way Common Crawl does.
        plat = {cle: valeur for cle, valeur in charge.items()
                if cle in _ALIAS_METRIQUES or cle in METRIQUES_CONNUES}
        metriques = _normaliser_metriques(plat)

    if not statut:
        if brut.get('erreur') or charge.get('erreur'):
            # A source that failed must never be read as "answered and found
            # nothing": that would let the empty-profile branch of the gate
            # publish a zero built on a network error.
            statut = 'erreur'
        else:
            statut = 'ok' if (domaines or metriques) else 'vide'

    cible = _hote(_texte(charge.get('domaine') or charge.get('domain')
                         or charge.get('site_url') or charge.get('target'), 2048))

    return {
        'source': nom,
        'libelle': _texte(brut.get('libelle'), 80) or LIBELLES_SOURCES.get(nom, nom),
        'statut': statut,
        'confiance': round(confiance, 4),
        'domaine': registrable_domain(cible) if cible else '',
        'metriques': metriques,
        'domaines_referents': domaines,
        'message': _texte(brut.get('message') or brut.get('error') or charge.get('note'), 300),
        'illisibles': illisibles,
    }


def _porte_donnees(source: dict) -> bool:
    """True when a source brought something a score could be built on."""
    if source.get('statut') not in STATUTS_REPONDU:
        return False
    return bool(source.get('domaines_referents')) or bool(source.get('metriques'))


# --------------------------------------------------------------------------
# Merge
# --------------------------------------------------------------------------

def _desaccord(cle: str, valeurs) -> bool:
    """True when two sources disagree enough to change a reading."""
    nombres = [valeur for valeur in valeurs if valeur is not None]
    if len(nombres) < 2:
        return False
    bas, haut = min(nombres), max(nombres)
    genre = METRIQUES_CONNUES.get(cle, ('', 'compte'))[1]
    if genre == 'echelle':
        return (haut - bas) > _ECART_ECHELLE
    if genre == 'ratio':
        return bas > 0 and (haut / bas) > _RATIO_COMPTE
    if bas <= 0:
        return haut > 0
    return (haut / bas) > _RATIO_COMPTE


def merge_sources(sources, *, ancres_max: int = 5, urls_max: int = 3) -> dict:
    """Fuse several backlink sources into one profile, deduplicated by owner.

    Every referring domain is collapsed to its registrable domain, so
    `blog.x.com`, `www.x.com` and `x.com` land on one entry, and that entry
    records which sources confirm it. Confidence is a noisy-OR over those
    sources: one domain seen by Moz and Common Crawl outranks one seen by Common
    Crawl alone, which is the whole point of reading several sources.

    Args:
        sources: source dicts from the fetchers above, from the Common Crawl
            port, or in the upstream CLI envelope. Unknown shapes are skipped
            rather than crashing the merge.
        ancres_max: anchors kept per referring domain.
        urls_max: referring URLs kept per referring domain.

    Returns:
        {
          'domaine': the audited domain when the sources agree on one,
          'sources': one line per source, with what it contributed,
          'domaines_referents': [{'domaine', 'sources', 'nb_sources', 'confiance',
                                  'autorite_domaine', 'score_spam', 'liens',
                                  'ancres', 'urls'}] sorted by confidence then
                                 authority,
          'total_domaines_referents', 'domaines_multi_sources',
          'confiance_moyenne',
          'metriques': {cle: {'libelle', 'valeur', 'source', 'confiance',
                              'autres', 'desaccord'}},
          'desaccords': the metrics where two sources contradict each other,
          'couverture': {'sources_totales', 'sources_avec_donnees',
                         'sources_sans_donnees', 'axes_couverts', 'axes_manquants'},
          'ignores': {'auto_references', 'entrees_illisibles', 'sources_illisibles'},
        }

    A metric keeps the value of the most confident source that carries it, and
    the others are listed beside it: hiding a contradiction would be worse than
    showing it, because it is usually the sign that one source measures
    something else.
    """
    if not isinstance(sources, (list, tuple)):
        sources = []

    normalisees = []
    sources_illisibles = 0
    for brut in sources:
        source = _normaliser_source(brut, ancres_max, urls_max)
        if source:
            normalisees.append(source)
        else:
            sources_illisibles += 1

    # The audited domain is whatever the sources agree on. Without it, a link a
    # site makes to itself would be counted as a referring domain.
    votes = {}
    for source in normalisees:
        if source['domaine']:
            votes[source['domaine']] = votes.get(source['domaine'], 0) + 1
    domaine_cible = max(votes.items(), key=lambda item: (item[1], item[0]))[0] if votes else ''

    agrege = {}
    auto_references = 0
    illisibles = 0
    lignes_sources = []

    for source in normalisees:
        illisibles += source.get('illisibles', 0)
        apportes = 0
        for entree in source['domaines_referents']:
            nom = entree['domaine']
            if domaine_cible and nom == domaine_cible:
                auto_references += 1
                continue
            fusion = agrege.setdefault(nom, {
                'domaine': nom,
                'sources': [],
                'confiances': [],
                'autorites': [],
                'spams': [],
                'liens': 0,
                'ancres': [],
                'urls': [],
            })
            if source['source'] not in fusion['sources']:
                # A source listing the same owner twice is one vote, not two.
                fusion['sources'].append(source['source'])
                fusion['confiances'].append(source['confiance'])
                apportes += 1
            if entree['autorite_domaine'] is not None:
                fusion['autorites'].append(entree['autorite_domaine'])
            if entree['score_spam'] is not None:
                fusion['spams'].append(entree['score_spam'])
            fusion['liens'] = max(fusion['liens'], entree['liens'] or 1)
            for ancre in entree['ancres']:
                if ancre not in fusion['ancres'] and len(fusion['ancres']) < ancres_max:
                    fusion['ancres'].append(ancre)
            for url in entree['urls']:
                if url not in fusion['urls'] and len(fusion['urls']) < urls_max:
                    fusion['urls'].append(url)

        lignes_sources.append({
            'source': source['source'],
            'libelle': source['libelle'],
            'statut': source['statut'],
            'confiance': source['confiance'],
            'domaines_apportes': apportes,
            'metriques_apportees': sorted(source['metriques'].keys()),
            'porte_donnees': _porte_donnees(source),
            'message': source['message'],
        })

    domaines_referents = []
    for fusion in agrege.values():
        domaines_referents.append({
            'domaine': fusion['domaine'],
            'sources': sorted(fusion['sources']),
            'nb_sources': len(fusion['sources']),
            'confiance': _noisy_or(fusion['confiances']),
            # Authority: the highest reading wins, spam: the worst. Both are the
            # cautious direction, since a domain flagged spammy by one index
            # stays a risk even if another index has not looked at it.
            'autorite_domaine': max(fusion['autorites']) if fusion['autorites'] else None,
            'score_spam': max(fusion['spams']) if fusion['spams'] else None,
            'liens': fusion['liens'],
            'ancres': fusion['ancres'],
            'urls': fusion['urls'],
        })
    domaines_referents.sort(
        key=lambda item: (-item['nb_sources'], -item['confiance'],
                          -(item['autorite_domaine'] or 0), item['domaine']),
    )

    metriques = {}
    desaccords = []
    cles = []
    for source in normalisees:
        for cle in source['metriques']:
            if cle not in cles:
                cles.append(cle)
    for cle in cles:
        porteuses = [(source['confiance'], source['source'], source['metriques'][cle])
                     for source in normalisees if cle in source['metriques']]
        porteuses.sort(key=lambda item: (-item[0], item[1]))
        confiance, nom_source, valeur = porteuses[0]
        conflit = _desaccord(cle, [item[2] for item in porteuses])
        metriques[cle] = {
            'libelle': METRIQUES_CONNUES.get(cle, (cle, 'compte'))[0],
            'valeur': valeur,
            'source': nom_source,
            'confiance': confiance,
            'autres': [{'source': item[1], 'valeur': item[2]} for item in porteuses[1:]],
            'desaccord': conflit,
        }
        if conflit:
            desaccords.append({
                'metrique': cle,
                'libelle': METRIQUES_CONNUES.get(cle, (cle, 'compte'))[0],
                'valeurs': [{'source': item[1], 'valeur': item[2]} for item in porteuses],
                'note': 'Les sources ne mesurent pas la même chose. Affichez la source à côté du chiffre.',
            })

    axes_couverts = []
    if domaines_referents:
        axes_couverts.append('domaines_referents')
    if ('autorite_domaine' in metriques or 'autorite_page' in metriques
            or any(item['autorite_domaine'] is not None for item in domaines_referents)):
        axes_couverts.append('autorite')
    if ('score_spam' in metriques
            or any(item['score_spam'] is not None for item in domaines_referents)):
        axes_couverts.append('spam')
    if any(item['ancres'] for item in domaines_referents):
        axes_couverts.append('ancres')
    if 'liens_externes_total' in metriques or 'domaines_referents_total' in metriques:
        axes_couverts.append('volume_liens')

    avec_donnees = [ligne for ligne in lignes_sources if ligne['porte_donnees']]
    confiances_domaines = [item['confiance'] for item in domaines_referents]

    return {
        'domaine': domaine_cible or None,
        'sources': lignes_sources,
        'domaines_referents': domaines_referents,
        'total_domaines_referents': len(domaines_referents),
        'domaines_multi_sources': sum(1 for item in domaines_referents if item['nb_sources'] > 1),
        'confiance_moyenne': (round(sum(confiances_domaines) / len(confiances_domaines), 4)
                              if confiances_domaines else None),
        'metriques': metriques,
        'desaccords': desaccords,
        'couverture': {
            'sources_totales': len(lignes_sources),
            'sources_avec_donnees': len(avec_donnees),
            'sources_sans_donnees': [ligne['source'] for ligne in lignes_sources
                                     if not ligne['porte_donnees']],
            'axes_couverts': axes_couverts,
            'axes_manquants': [cle for cle, _ in _AXES if cle not in axes_couverts],
        },
        'ignores': {
            'auto_references': auto_references,
            'entrees_illisibles': illisibles,
            'sources_illisibles': sources_illisibles,
        },
    }


# --------------------------------------------------------------------------
# Data sufficiency gate
# --------------------------------------------------------------------------

def _raison(source: dict) -> str:
    statut = source.get('statut')
    if statut == 'non_configure':
        return 'Aucune clé configurée.'
    if statut == 'non_autorise':
        return 'Accès refusé par le fournisseur.'
    if statut == 'limite_atteinte':
        return 'Quota atteint chez le fournisseur.'
    if statut == 'erreur':
        return 'Appel en échec.'
    if statut == 'vide':
        return 'La source a répondu et ne trouve rien.'
    return 'La source a répondu sans donnée exploitable.'


def _accord(nombre: int, singulier: str, pluriel: str) -> str:
    """French agreement for the counts the gate prints. 1 stays singular."""
    return '%d %s' % (nombre, singulier if nombre <= 1 else pluriel)


def _suggestions(presentes) -> list:
    """What is left to plug in, cheapest and least intrusive first."""
    ordre = ('commoncrawl', 'moz', 'bing_webmaster')
    suggestions = []
    for cle in ordre:
        if cle in presentes:
            continue
        fiche = CATALOGUE_SOURCES[cle]
        suggestions.append({
            'source': cle,
            'libelle': fiche['libelle'],
            'cout': fiche['cout'],
            'mise_en_place': fiche['mise_en_place'],
            'contrainte': fiche['contrainte'],
        })
    return suggestions


def data_sufficiency(sources, *, floor: int = 2) -> dict:
    """Decide whether a backlink score may be published at all.

    Upstream states the rule in prose: a number built on one source is
    misleading, because it reads as "your profile is weak" when the truth is
    "we did not look". This gate counts the sources that actually carry data and
    refuses the score below `floor`.

    One case is added that upstream refuses forever: when at least `floor`
    sources answered and every one of them found nothing, the profile is empty
    rather than unknown, and a score of zero is then the honest number. A brand
    new site would otherwise never get past the gate.

    Args:
        sources: the same shapes `merge_sources` accepts.
        floor: how many sources must carry data before a score is allowed.

    Returns:
        {'sources_totales', 'sources_avec_donnees', 'sources_ayant_repondu',
         'noms_avec_donnees', 'plancher', 'score_autorise', 'niveau',
         'confiance_cumulee', 'message', 'details', 'suggestions'}

        `niveau` is 'suffisant', 'profil_vide' or 'insuffisant'. `message` is the
        French line to show the operator, and it is the only thing to display
        when `score_autorise` is False.
    """
    if not isinstance(sources, (list, tuple)):
        sources = []
    plancher = max(1, _entier(floor, 2) or 2)

    normalisees = [_normaliser_source(brut, 5, 3) for brut in sources]
    normalisees = [source for source in normalisees if source]

    details = []
    avec_donnees = []
    ont_repondu = []
    presentes = set()
    for source in normalisees:
        presentes.add(source['source'])
        porte = _porte_donnees(source)
        repondu = source['statut'] in STATUTS_REPONDU
        if porte:
            avec_donnees.append(source)
        if repondu:
            ont_repondu.append(source)
        details.append({
            'source': source['source'],
            'libelle': source['libelle'],
            'statut': source['statut'],
            'confiance': source['confiance'],
            'porte_donnees': porte,
            'a_repondu': repondu,
            'domaines_referents': len(source['domaines_referents']),
            'raison': '' if porte else _raison(source),
        })

    noms = [source['libelle'] for source in avec_donnees]
    confiance_cumulee = _noisy_or(source['confiance'] for source in avec_donnees)
    suggestions = _suggestions(presentes)

    if len(avec_donnees) >= plancher:
        niveau = 'suffisant'
        autorise = True
        message = ('%s de backlinks (%s). Le score peut être calculé.'
                   % (_accord(len(avec_donnees), 'source porte des données',
                              'sources portent des données'),
                      ', '.join(noms)))
    elif len(ont_repondu) >= plancher and not avec_donnees:
        niveau = 'profil_vide'
        autorise = True
        message = (
            '%s et aucune ne trouve de lien entrant. Le profil est vide, '
            'pas inconnu : le score vaut 0 et il est exact.'
            % _accord(len(ont_repondu), 'source a répondu', 'sources ont répondu')
        )
    else:
        niveau = 'insuffisant'
        autorise = False
        if len(avec_donnees) == 1:
            debut = ('Score de backlinks non calculé : une seule source porte des données (%s), '
                     'il en faut %d.' % (', '.join(noms), plancher))
        elif avec_donnees:
            debut = ('Score de backlinks non calculé : %s (%s), il en faut %d.'
                     % (_accord(len(avec_donnees), 'source porte des données',
                                'sources portent des données'),
                        ', '.join(noms), plancher))
        else:
            debut = ('Score de backlinks non calculé : aucune source ne porte de données, '
                     'il en faut %d.' % plancher)
        milieu = ('Un chiffre bâti là-dessus dirait « profil faible » alors que la réalité est '
                  '« personne n a regardé ».')
        if suggestions:
            branche = suggestions[0]
            fin = ('Branchez %s (%s) pour débloquer le calcul.'
                   % (branche['libelle'], branche['cout']))
        else:
            fin = 'Réessayez quand les sources configurées répondront.'
        message = ' '.join([debut, milieu, fin])

    return {
        'sources_totales': len(normalisees),
        'sources_avec_donnees': len(avec_donnees),
        'sources_ayant_repondu': len(ont_repondu),
        'noms_avec_donnees': [source['source'] for source in avec_donnees],
        'plancher': plancher,
        'score_autorise': autorise,
        'niveau': niveau,
        'confiance_cumulee': confiance_cumulee,
        'message': message,
        'details': details,
        'suggestions': suggestions,
    }
