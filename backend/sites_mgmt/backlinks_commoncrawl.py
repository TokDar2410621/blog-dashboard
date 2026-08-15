"""Real inbound links for one domain, read from Common Crawl's domain graph.

Porte depuis claude-seo v2.2.4 `scripts/commoncrawl_graph.py`.
Copyright (c) 2025 Daniel Agrici (AgriciDaniel). MIT.
https://github.com/AgriciDaniel/claude-seo

Upstream reads one domain's PageRank out of the ranks file and stops there, its
own CLI calling referring domains "not extracted"; this port walks the vertices
and edges files to produce them, because Gridar has to count links and not
mentions. Three adaptations carry the port. The fixed 120 s timeout becomes a
`time_budget` split across stages, so a scan that cannot finish returns what it
read instead of nothing. An unfinished scan is never reported as an absence,
which is the lie upstream ships when its timeout fires and it prints "Domain
not found". And the release is derived from the calendar instead of a hardcoded
list, with the crawl period attached to every payload so no screen can present
a quarterly snapshot as live data.

BACKGROUND WORKERS ONLY, NEVER A REQUEST-RESPONSE CYCLE. The domain graph
files are the largest objects Common Crawl publishes: several GB compressed for
the vertices and the ranks files, more for the edges. A referring-domain answer
needs a full pass over the edges file, which is minutes of streaming at best.
Every function here streams hundreds of megabytes even on a short budget, so
the caller must run them in a worker with a generous `time_budget` and persist
the payload. Anything under a couple of minutes returns a partial answer, which
is why the coverage of each stage is reported instead of hidden.
"""
from __future__ import annotations

import re
import time
import zlib
from datetime import date, datetime, timedelta

# Trusted host, hardcoded below: `data.commoncrawl.org` never comes from a
# caller and the release name is regex-checked before it reaches a URL, so
# plain `requests` is correct here. Nothing in this module fetches a
# third-party address; anything that did would have to go through
# `url_safety.safe_get`.
import requests

__all__ = [
    'CommonCrawlError',
    'CC_GRAPH_BASE',
    'VERSIONS_CONNUES',
    'VERSIONS_VERIFIEES_LE',
    'PERIME_APRES_JOURS',
    'PALIERS_AUTORITE',
    'BUDGET_TACHE_FOND',
    'data_freshness',
    'fetch_domain_graph',
    'referring_domains',
    'authority_signals',
]


class CommonCrawlError(ValueError):
    """Raised on a malformed domain or an unusable release name."""


CC_GRAPH_BASE = 'https://data.commoncrawl.org/projects/hyperlinkgraph'

# Filenames repeat the release as a prefix:
# <release>/domain/<release>-domain-vertices.txt.gz
_SUFFIXE_SOMMETS = '-domain-vertices.txt.gz'
_SUFFIXE_ARETES = '-domain-edges.txt.gz'
_SUFFIXE_CLASSEMENTS = '-domain-ranks.txt.gz'

# Fallback only. `_versions_candidates` derives the recent release names from
# the calendar, so this list exists for the case where naming changes and the
# derived names all 404. Re-verify it when that happens.
VERSIONS_CONNUES = (
    'cc-main-2026-apr-may-jun',
    'cc-main-2026-jan-feb-mar',
    'cc-main-2025-oct-nov-dec',
    'cc-main-2025-jul-aug-sep',
    'cc-main-2025-apr-may-jun',
    'cc-main-2025-jan-feb-mar',
)
VERSIONS_VERIFIEES_LE = '2026-08-14'

SOURCE_DE_VERITE = 'https://commoncrawl.github.io/cc-webgraph-statistics/'

# A release covers a quarter and is published one to two months after that
# quarter closes, so the newest release available is routinely three to five
# months old. Past six months, a newer one exists and we are not reading it.
PERIME_APRES_JOURS = 180

# What a caller should budget for a complete referring-domain scan. The edges
# file has no index and incoming links to one domain are scattered across the
# whole of it, so there is no shortcut: it is a full read or a partial answer.
BUDGET_TACHE_FOND = 1800.0

# Release name grammar. Enforced before interpolation because the caller can
# pass `release`, and that value lands inside a URL path.
_RE_VERSION = re.compile(r'^cc-main-\d{4}-[a-z]{3}(?:-[a-z]{3}){0,3}$')
_RE_DOMAINE = re.compile(
    r'^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]*[a-z0-9])?)+$'
)

_TRIMESTRES = (
    ('jan', 'feb', 'mar'),
    ('apr', 'may', 'jun'),
    ('jul', 'aug', 'sep'),
    ('oct', 'nov', 'dec'),
)
_MOIS_NUM = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12,
}
_MOIS_FR = (
    'janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août',
    'septembre', 'octobre', 'novembre', 'décembre',
)

# How many derived release names to probe before falling back on the pinned
# list. Six quarters is a year and a half of history, which is more than enough
# to survive one skipped publication.
_VERSIONS_CANDIDATES = 6

_ENTETES = {'User-Agent': 'Gridar/1.0 (+https://gridar.app)'}
_TIMEOUT_CONNEXION = 10.0
_TIMEOUT_LECTURE = 30.0
_TAILLE_MORCEAU = 256 * 1024

# Hard ceiling on what one call may download, whatever the time budget says.
# A worker with an hour of budget on a slow day would otherwise pull the whole
# edges file into a Railway container's egress bill.
_MAX_OCTETS = 4 * 1024 * 1024 * 1024

# Ceiling on the referrer ids held in memory. Ints in a set, so 200 000 costs a
# few MB; a hub domain with millions of referrers gets truncated and says so.
_MAX_REFERENTS = 200_000

# Share of the total budget each stage may consume. Deadlines are computed as
# `now + part * total`, so a stage that finishes early hands its unused time to
# the next one, and the global deadline caps everything anyway. The sum is left
# under 1.0 on purpose: release discovery and per-request overhead take the
# rest.
_PARTS = {
    'classements_cible': 0.20,
    'sommets_cible': 0.10,
    'aretes': 0.30,
    'sommets_noms': 0.15,
    'classements_referents': 0.15,
}
_PARTS_SANS_REFERENTS = {
    'classements_cible': 0.70,
    'sommets_cible': 0.25,
}

_LIBELLES_ETAPES = {
    'classements_cible': 'Classement du domaine cible',
    'sommets_cible': 'Identifiant du domaine cible',
    'aretes': 'Liens entrants dans le graphe',
    'sommets_noms': 'Noms des domaines référents',
    'classements_referents': 'Autorité des domaines référents',
}

# Column layout of the ranks file. Read from the `#` header line when it is
# there, defaulted otherwise, because the layout has been stable for years but
# the header costs nothing to honour.
_COLONNES_DEFAUT = {
    'harmonicc_pos': 0,
    'harmonicc_val': 1,
    'pr_pos': 2,
    'pr_val': 3,
    'host_rev': 4,
    'n_hosts': 5,
}
_ALIAS_NOM = ('host_rev', 'domain_rev', 'rev_host', 'name', 'host', 'domain')

# Authority bands read off the absolute rank position, not off a percentile.
# The graph holds well over a hundred million domains and this module never
# reads the total, so a percentile would need a made-up denominator; a rank
# threshold needs nothing. `authority_signals` computes the percentile only
# when the caller supplies the real total.
PALIERS_AUTORITE = (
    (10_000, 'mondiale', 'Mondiale'),
    (100_000, 'tres_forte', 'Très forte'),
    (1_000_000, 'forte', 'Forte'),
    (10_000_000, 'moyenne', 'Moyenne'),
    (None, 'faible', 'Faible'),
)
_NIVEAU_NON_CLASSE = ('non_classe', 'Non classé')
_NIVEAU_INCONNU = ('inconnu', 'Inconnue')

# Process-wide memo of the discovered release. A worker that audits fifty sites
# would otherwise HEAD the same six URLs fifty times. Two threads racing into
# the discovery both write the same value, so no lock.
_CACHE_VERSION: dict = {'version': None, 'expire': 0.0}
_TTL_CACHE_VERSION = 6 * 3600.0


# --------------------------------------------------------------------------
# Budget and per-file statistics
# --------------------------------------------------------------------------

class _Budget:
    """Wall-clock and byte allowance shared by every stage of one call."""

    def __init__(self, secondes: float, max_octets=None):
        self.total = float(secondes)
        self.debut = time.monotonic()
        self.fin = self.debut + self.total
        # Read off the module at call time rather than bound as a default, so
        # a test can shrink the ceiling and exercise the truncated path.
        self.max_octets = _MAX_OCTETS if max_octets is None else max_octets
        self.octets = 0

    @property
    def restant(self) -> float:
        return max(0.0, self.fin - time.monotonic())

    @property
    def ecoule(self) -> float:
        return time.monotonic() - self.debut

    def epuise(self) -> bool:
        return self.restant <= 0 or self.octets >= self.max_octets

    def echeance(self, part: float) -> float:
        """Absolute deadline for a stage entitled to `part` of the total."""
        return min(self.fin, time.monotonic() + self.total * part)


class _Scan:
    """What one pass over one graph file actually managed to read."""

    def __init__(self, nom: str, url: str = ''):
        self.nom = nom
        self.libelle = _LIBELLES_ETAPES.get(nom, nom)
        self.url = url
        self.octets = 0
        self.octets_total = None
        self.lignes = 0
        self.termine = False
        self.arret = 'non_lance'
        self.erreur = None
        self.secondes = 0.0

    @property
    def fraction(self):
        """Share of the compressed file actually read, None when unknown."""
        if self.termine:
            return 1.0
        if not self.octets_total:
            return None
        return round(min(1.0, self.octets / self.octets_total), 4)

    def payload(self) -> dict:
        return {
            'nom': self.nom,
            'libelle': self.libelle,
            'lancee': self.arret != 'non_lance',
            'terminee': self.termine,
            'arret': self.arret,
            'octets_lus': self.octets,
            'octets_total': self.octets_total,
            'fraction': self.fraction,
            'lignes': self.lignes,
            'secondes': self.secondes,
            'erreur': self.erreur,
        }


# --------------------------------------------------------------------------
# Streaming
# --------------------------------------------------------------------------

def _url(version: str, suffixe: str) -> str:
    return f'{CC_GRAPH_BASE}/{version}/domain/{version}{suffixe}'


def _iter_lines(url: str, budget: _Budget, scan: _Scan, echeance=None):
    """Stream one gzipped graph file and yield raw lines as bytes.

    Lines stay bytes on purpose. These files hold hundreds of millions of
    rows and the caller only ever compares a field against a small set, so
    decoding every line would cost more than the whole scan; the match is done
    on bytes and only the winners get decoded.

    The gzip stream is decompressed incrementally, and concatenated members are
    handled because Common Crawl builds some of these files by appending parts.
    """
    limite = budget.fin if echeance is None else min(budget.fin, echeance)
    debut = time.monotonic()
    scan.arret = 'incomplet'
    reponse = None
    try:
        try:
            reponse = requests.get(
                url, stream=True, headers=_ENTETES,
                timeout=(_TIMEOUT_CONNEXION, _TIMEOUT_LECTURE),
            )
            reponse.raise_for_status()
        except requests.RequestException as exc:
            scan.arret = 'erreur'
            scan.erreur = f'{type(exc).__name__}: {exc}'
            return

        taille = (reponse.headers or {}).get('Content-Length')
        try:
            scan.octets_total = int(taille) if taille is not None else None
        except (TypeError, ValueError):
            scan.octets_total = None

        decompresseur = zlib.decompressobj(zlib.MAX_WBITS | 16)
        reste = b''
        for morceau in reponse.iter_content(chunk_size=_TAILLE_MORCEAU):
            if not morceau:
                continue
            scan.octets += len(morceau)
            budget.octets += len(morceau)
            try:
                donnees = decompresseur.decompress(morceau)
                while decompresseur.eof:
                    suite = decompresseur.unused_data
                    if not suite:
                        break
                    avant = len(suite)
                    decompresseur = zlib.decompressobj(zlib.MAX_WBITS | 16)
                    donnees += decompresseur.decompress(suite)
                    # A member that swallows nothing would loop forever.
                    if decompresseur.eof and len(decompresseur.unused_data) >= avant:
                        break
            except zlib.error as exc:
                scan.arret = 'erreur'
                scan.erreur = f'gzip: {exc}'
                return

            if donnees:
                lignes = (reste + donnees).split(b'\n')
                reste = lignes.pop()
                for ligne in lignes:
                    scan.lignes += 1
                    yield ligne.rstrip(b'\r')

            if time.monotonic() >= limite:
                scan.arret = 'budget'
                return
            if budget.octets >= budget.max_octets:
                scan.arret = 'octets'
                return

        if reste.strip():
            scan.lignes += 1
            yield reste.rstrip(b'\r')
        scan.termine = True
        scan.arret = 'fin'
    finally:
        scan.secondes = round(time.monotonic() - debut, 3)
        if reponse is not None:
            try:
                reponse.close()
            except Exception:  # pragma: no cover - close must never mask a result
                pass


# --------------------------------------------------------------------------
# Domain and release handling
# --------------------------------------------------------------------------

def _normalise_domaine(valeur) -> str:
    """Reduce anything the caller has to the registrable host Common Crawl uses.

    Accepts a bare domain or a full URL because site records hold both. IDN is
    punycoded since the graph stores hosts in their ASCII form, which is what a
    Quebec domain written with accents needs.
    """
    if not isinstance(valeur, str) or not valeur.strip():
        raise CommonCrawlError('domain must be a non-empty string')

    brut = valeur.strip()
    if '://' in brut:
        from urllib.parse import urlparse
        brut = urlparse(brut).netloc or ''
    brut = brut.split('/')[0].split('?')[0].split('#')[0]
    if '@' in brut:
        raise CommonCrawlError(f'domain must not carry userinfo: {valeur!r}')
    if brut.startswith('[') or brut.count(':') > 1:
        raise CommonCrawlError(f'domain must not be an IPv6 literal: {valeur!r}')
    brut = brut.split(':')[0].strip().rstrip('.').lower()

    if not brut.isascii():
        try:
            brut = brut.encode('idna').decode('ascii')
        except (UnicodeError, ValueError) as exc:
            raise CommonCrawlError(f'domain is not encodable as IDNA: {valeur!r}') from exc

    if brut.startswith('www.'):
        brut = brut[4:]
    if not _RE_DOMAINE.match(brut):
        raise CommonCrawlError(f'not a usable domain: {valeur!r}')
    return brut


def _inverse(domaine: str) -> str:
    """google.com -> com.google, the form the graph files are keyed on."""
    return '.'.join(reversed(domaine.split('.')))


def _endroit(inverse: str) -> str:
    """com.google -> google.com."""
    return '.'.join(reversed(inverse.split('.')))


def _valide_version(version: str) -> str:
    if not isinstance(version, str) or not _RE_VERSION.match(version):
        raise CommonCrawlError(f'not a Common Crawl release name: {version!r}')
    return version


def _versions_candidates(aujourdhui=None) -> list:
    """Release names to probe, newest first.

    Derived from the calendar rather than read from a constant: the naming is
    strictly quarterly, so the list stays correct without a maintainer. The
    quarter currently running is skipped because its graph is published one to
    two months after it closes.
    """
    jour = aujourdhui or date.today()
    if isinstance(jour, datetime):
        jour = jour.date()
    trimestre = (jour.month - 1) // 3 - 1
    annee = jour.year

    sorties = []
    for _ in range(_VERSIONS_CANDIDATES):
        if trimestre < 0:
            trimestre += 4
            annee -= 1
        sorties.append(f'cc-main-{annee}-' + '-'.join(_TRIMESTRES[trimestre]))
        trimestre -= 1
    for version in VERSIONS_CONNUES:
        if version not in sorties:
            sorties.append(version)
    return sorties


def _existe(version: str, budget: _Budget) -> bool:
    """HEAD the vertices file to see whether a release was published."""
    delai = max(1.0, min(5.0, budget.restant))
    try:
        reponse = requests.head(
            _url(version, _SUFFIXE_SOMMETS), headers=_ENTETES,
            timeout=delai, allow_redirects=True,
        )
    except requests.RequestException:
        return False
    return getattr(reponse, 'status_code', 0) == 200


def _resoudre_version(version, budget: _Budget, aujourdhui=None):
    """Return the release to read, discovering it when the caller gave none."""
    if version is not None:
        return _valide_version(version)

    memo = _CACHE_VERSION
    if memo['version'] and memo['expire'] > time.monotonic():
        return memo['version']

    # Discovery is capped hard: six HEAD requests at five seconds each would
    # otherwise swallow a short budget before a single byte of graph is read.
    echeance = min(budget.fin, time.monotonic() + min(15.0, budget.total * 0.25))
    for candidate in _versions_candidates(aujourdhui):
        if time.monotonic() >= echeance:
            break
        if _existe(candidate, budget):
            _CACHE_VERSION['version'] = candidate
            _CACHE_VERSION['expire'] = time.monotonic() + _TTL_CACHE_VERSION
            return candidate
    return None


def _periode(version):
    """(debut, fin, libelle) of the crawl quarter a release covers."""
    correspondance = re.match(r'^cc-main-(\d{4})-([a-z]{3}(?:-[a-z]{3})*)$', version or '')
    if not correspondance:
        return None

    annee = int(correspondance.group(1))
    mois = correspondance.group(2).split('-')
    numeros = [_MOIS_NUM.get(m) for m in mois]
    if any(n is None for n in numeros):
        return None

    # A release can straddle a year end (nov-dec-jan), so bump the year every
    # time the month sequence wraps.
    annees = []
    courante = annee
    for rang, numero in enumerate(numeros):
        if rang and numero < numeros[rang - 1]:
            courante += 1
        annees.append(courante)

    debut = date(annees[0], numeros[0], 1)
    dernier = numeros[-1]
    fin_annee = annees[-1]
    if dernier == 12:
        fin = date(fin_annee + 1, 1, 1) - timedelta(days=1)
    else:
        fin = date(fin_annee, dernier + 1, 1) - timedelta(days=1)

    if len(numeros) == 1:
        libelle = f'{_MOIS_FR[numeros[0] - 1]} {annees[0]}'
    elif annees[0] == annees[-1]:
        libelle = f'{_MOIS_FR[numeros[0] - 1]} à {_MOIS_FR[dernier - 1]} {annees[0]}'
    else:
        libelle = (
            f'{_MOIS_FR[numeros[0] - 1]} {annees[0]} à '
            f'{_MOIS_FR[dernier - 1]} {annees[-1]}'
        )
    return debut, fin, libelle


def _nombre(valeur) -> str:
    """French thousands grouping: 1 234 567."""
    try:
        return f'{int(valeur):,}'.replace(',', ' ')
    except (TypeError, ValueError):
        return str(valeur)


def _jours(nombre: int) -> str:
    return '1 jour' if nombre == 1 else f'{_nombre(nombre)} jours'


def _secondes(valeur) -> str:
    """French decimal comma, because these strings reach a Quebec operator."""
    try:
        return f'{float(valeur):.1f}'.replace('.', ',')
    except (TypeError, ValueError):
        return '?'


def _pourcent(fraction) -> str:
    """Share read, as a French percentage. None when the host sent no size."""
    if fraction is None:
        return 'une part indéterminée'
    return f'{fraction * 100:.1f} %'.replace('.', ',')


def data_freshness(version=None, today=None) -> dict:
    """How old the crawl behind a release is, so the screen can admit it.

    The domain graph is a quarterly snapshot. A link created last week is not
    in it, a link removed last week is still in it, and any interface that
    shows these numbers without the crawl period beside them is claiming live
    data it does not have.

    Args:
        version: release name. None when discovery has not run or failed.
        today: reference date, defaults to the system date. Injectable so
            reports and tests stay deterministic.

    Returns: version, periode_debut, periode_fin, periode_libelle, age_jours,
    est_perime, perime_apres_jours, temps_reel (always False), cadence,
    source_de_verite, versions_verifiees_le, message (French).
    """
    maintenant = today or date.today()
    if isinstance(maintenant, datetime):
        maintenant = maintenant.date()
    if isinstance(maintenant, str):
        maintenant = date.fromisoformat(maintenant.strip()[:10])

    periode = _periode(version) if version else None
    if periode:
        debut, fin, libelle = periode
        # A reference date before the crawl closed means a clock problem, not a
        # negative age.
        age = max(0, (maintenant - fin).days)
    else:
        debut = fin = libelle = None
        age = None

    est_perime = bool(age is not None and age > PERIME_APRES_JOURS)

    if libelle is None:
        message = (
            "Version du graphe inconnue : impossible de dire de quel crawl "
            "viennent ces chiffres."
        )
    else:
        message = (
            f'Instantané du crawl {libelle}, clos il y a {_jours(age)}. '
            f"Common Crawl publie un graphe par trimestre, ce n'est pas un index "
            f'de liens en temps réel : un lien créé depuis cette date ne peut pas '
            f'y figurer.'
        )
        if est_perime:
            message += (
                f' Cette version a plus de {_jours(PERIME_APRES_JOURS)}, '
                f'une plus récente existe : vérifie {SOURCE_DE_VERITE}.'
            )

    return {
        'version': version,
        'periode_debut': debut.isoformat() if debut else None,
        'periode_fin': fin.isoformat() if fin else None,
        'periode_libelle': libelle,
        'age_jours': age,
        'est_perime': est_perime,
        'perime_apres_jours': PERIME_APRES_JOURS,
        'temps_reel': False,
        'cadence': 'trimestrielle',
        'source_de_verite': SOURCE_DE_VERITE,
        'versions_verifiees_le': VERSIONS_VERIFIEES_LE,
        'message': message,
    }


# --------------------------------------------------------------------------
# File parsers
# --------------------------------------------------------------------------

def _colonnes_classements(ligne: bytes):
    """Read the ranks header, e.g. `#harmonicc_pos<TAB>harmonicc_val<TAB>...`."""
    texte = ligne.decode('utf-8', 'replace').lstrip('#').strip()
    if not texte:
        return None
    champs = [c.strip().lower() for c in re.split(r'[\t ]+', texte) if c.strip()]
    if len(champs) < 2:
        return None
    colonnes = {}
    for rang, nom in enumerate(champs):
        if nom in _ALIAS_NOM:
            colonnes['host_rev'] = rang
        elif nom in _COLONNES_DEFAUT:
            colonnes[nom] = rang
    return colonnes or None


def _entier(valeur):
    """int() over a str or a raw field. Bytes are decoded because int() is not.

    Every parser here works on undecoded lines, so this is the single place
    that has to know it; forgetting the decode turns a whole column into None
    without raising anything.
    """
    if isinstance(valeur, (bytes, bytearray)):
        valeur = valeur.decode('ascii', 'ignore')
    try:
        return int(valeur)
    except (TypeError, ValueError):
        return None


def _reel(valeur):
    if isinstance(valeur, (bytes, bytearray)):
        valeur = valeur.decode('ascii', 'ignore')
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return None


def _sommet(champs, index: int):
    """(id, reversed name as bytes, host count) out of one vertices line.

    Common Crawl has shipped this file both as `id<TAB>name<TAB>n_hosts` and as
    `name<TAB>n_hosts` with the id implied by the line number. Both are read
    here rather than pinning one, because guessing wrong turns every edge
    lookup into silence.
    """
    if not champs:
        return None, b'', None
    if len(champs) >= 2 and champs[0].isdigit() and not champs[1].isdigit():
        identifiant = _entier(champs[0])
        nom = champs[1]
        hotes = _entier(champs[2]) if len(champs) >= 3 else None
        return (identifiant if identifiant is not None else index), nom, hotes
    hotes = _entier(champs[1]) if len(champs) >= 2 else None
    return index, champs[0], hotes


def _lire_classements(version, cibles, budget, scan, echeance) -> dict:
    """One pass over the ranks file, collecting every wanted domain at once.

    The file is ordered by authority, best first. That is the property this
    module leans on: a scan cut short by the budget still returns the most
    authoritative matches, and `rang_max_atteint` says how deep it got, which
    is the authority floor below which the answer says nothing.
    """
    trouves = {}
    if not cibles:
        return {'trouves': trouves, 'rang_max_atteint': None}

    attendus = {nom.encode('utf-8'): nom for nom in cibles}
    colonnes = dict(_COLONNES_DEFAUT)
    derniere_position = None

    flux = _iter_lines(_url(version, _SUFFIXE_CLASSEMENTS), budget, scan, echeance)
    try:
        for ligne in flux:
            if not ligne:
                continue
            if ligne.startswith(b'#'):
                maj = _colonnes_classements(ligne)
                if maj:
                    colonnes.update(maj)
                continue
            champs = ligne.split(b'\t')
            index_nom = colonnes['host_rev']
            if len(champs) <= index_nom:
                continue
            position = colonnes['harmonicc_pos']
            if position < len(champs):
                derniere_position = champs[position]
            brut = champs[index_nom]
            if brut not in attendus:
                continue
            nom = attendus[brut]
            trouves[nom] = {
                'centralite_harmonique_rang': _entier(
                    _champ(champs, colonnes, 'harmonicc_pos')),
                'centralite_harmonique': _reel(
                    _champ(champs, colonnes, 'harmonicc_val')),
                'pagerank_rang': _entier(_champ(champs, colonnes, 'pr_pos')),
                'pagerank': _reel(_champ(champs, colonnes, 'pr_val')),
                'nombre_hotes': _entier(_champ(champs, colonnes, 'n_hosts')),
            }
            if len(trouves) >= len(attendus):
                scan.arret = 'trouve'
                break
    finally:
        flux.close()

    return {
        'trouves': trouves,
        'rang_max_atteint': _entier(derniere_position),
    }


def _champ(champs, colonnes, nom):
    """Decoded value of one named column, None when the line is short."""
    rang = colonnes.get(nom)
    if rang is None or rang >= len(champs):
        return None
    return champs[rang].decode('utf-8', 'replace')


def _lire_sommet_cible(version, cible_inverse: str, budget, scan, echeance) -> dict:
    """Find the target's vertex id, concluding absence from the sort order.

    The vertices file is sorted on the reversed name, so the moment a line
    sorts past the target the domain is provably not in the graph. That is the
    only cheap conclusive answer this module has, and it is what lets a caller
    say "absent" instead of "not found in what we had time to read". The sort
    is verified while reading: if a name ever comes back smaller than the one
    before it, the early exit is disabled rather than trusted.
    """
    cible = cible_inverse.encode('utf-8')
    trie = True
    precedent = b''
    index = 0
    resultat = {'id': None, 'nombre_hotes': None, 'absent': None, 'trie': True}

    flux = _iter_lines(_url(version, _SUFFIXE_SOMMETS), budget, scan, echeance)
    try:
        for ligne in flux:
            if not ligne or ligne.startswith(b'#'):
                continue
            champs = ligne.split(b'\t')
            identifiant, nom, hotes = _sommet(champs, index)
            index += 1
            if not nom:
                continue
            if nom < precedent:
                trie = False
            precedent = nom

            if nom == cible:
                scan.arret = 'trouve'
                resultat.update({
                    'id': identifiant, 'nombre_hotes': hotes,
                    'absent': False, 'trie': trie,
                })
                return resultat
            if trie and nom > cible:
                scan.arret = 'depasse'
                resultat.update({'absent': True, 'trie': True})
                return resultat
    finally:
        flux.close()

    # No match and no overshoot: absence is proven only if the whole file was
    # read.
    resultat.update({'absent': True if scan.termine else None, 'trie': trie})
    return resultat


def _lire_aretes(version, cible_id: int, budget, scan, echeance) -> dict:
    """Collect the vertex ids linking to the target.

    Edges are sorted by source, so incoming links to one domain are spread over
    the entire file and there is no early exit: a complete answer means reading
    all of it. The domain graph carries one edge per domain pair, so the count
    of ids collected is a count of referring domains, not of raw links.
    """
    cible = str(cible_id).encode('ascii')
    identifiants = set()

    flux = _iter_lines(_url(version, _SUFFIXE_ARETES), budget, scan, echeance)
    try:
        for ligne in flux:
            if not ligne or ligne.startswith(b'#'):
                continue
            champs = ligne.split(b'\t')
            if len(champs) < 2 or champs[1] != cible:
                continue
            source = _entier(champs[0])
            # A self-loop is the site linking to itself across two hosts of the
            # same domain. Real, and worth zero as a referring domain.
            if source is None or source == cible_id:
                continue
            identifiants.add(source)
            if len(identifiants) >= _MAX_REFERENTS:
                scan.arret = 'plafond'
                break
    finally:
        flux.close()

    return {'ids': identifiants, 'plafond_atteint': scan.arret == 'plafond'}


def _lire_noms(version, identifiants, budget, scan, echeance) -> dict:
    """Map vertex ids back to reversed domain names.

    Ids ascend with the line order, so the scan stops once it passes the
    largest id wanted. As with the target lookup, the ordering is verified
    while reading and the shortcut is dropped if it does not hold.
    """
    noms = {}
    if not identifiants:
        return noms

    maximum = max(identifiants)
    croissant = True
    precedent = -1
    index = 0

    flux = _iter_lines(_url(version, _SUFFIXE_SOMMETS), budget, scan, echeance)
    try:
        for ligne in flux:
            if not ligne or ligne.startswith(b'#'):
                continue
            champs = ligne.split(b'\t')
            identifiant, nom, _hotes = _sommet(champs, index)
            index += 1
            if identifiant is None or not nom:
                continue
            if identifiant < precedent:
                croissant = False
            precedent = identifiant

            if identifiant in identifiants:
                noms[identifiant] = nom.decode('utf-8', 'replace')
                if len(noms) >= len(identifiants):
                    scan.arret = 'trouve'
                    break
            elif croissant and identifiant > maximum:
                scan.arret = 'depasse'
                break
    finally:
        flux.close()

    return noms


# --------------------------------------------------------------------------
# Authority
# --------------------------------------------------------------------------

def _niveau(rang):
    """(slug, French label) for one absolute rank position."""
    if rang is None:
        return _NIVEAU_NON_CLASSE
    for seuil, cle, libelle in PALIERS_AUTORITE:
        if seuil is None or rang <= seuil:
            return cle, libelle
    return PALIERS_AUTORITE[-1][1], PALIERS_AUTORITE[-1][2]


def _signal(valeur, rang, total):
    cle, libelle = _niveau(rang)
    percentile = None
    if rang is not None and total:
        try:
            percentile = round(max(0.0, (1.0 - rang / float(total))) * 100, 2)
        except (TypeError, ValueError, ZeroDivisionError):
            percentile = None
    return {
        'valeur': valeur,
        'rang': rang,
        'niveau': cle,
        'niveau_libelle': libelle,
        'percentile': percentile,
        'percentile_disponible': percentile is not None,
    }


def authority_signals(graph_payload, *, total_domains=None) -> dict:
    """Turn PageRank and harmonic centrality into something readable.

    Harmonic centrality leads, PageRank follows: Common Crawl publishes both
    and recommends the first for ranking domains, since PageRank on a web-scale
    graph is dominated by crawl artefacts. The level comes from the absolute
    rank position, not from a percentile, because this module never reads the
    number of domains in the graph and a percentile over an invented
    denominator would be a number that looks precise and means nothing. Pass
    `total_domains` when you know it and the percentile appears.

    Args:
        graph_payload: a `fetch_domain_graph` result, or any dict carrying the
            same metric keys, which includes one entry of
            `referring_domains()['domaines_referents']`.
        total_domains: number of domains ranked in that release, when known.

    Returns: primaire, niveau, niveau_libelle, percentile, signaux (per metric),
    fiable, resume (French), paliers.
    """
    if not isinstance(graph_payload, dict):
        raise TypeError('graph_payload must be a dict')

    harmonique = _signal(
        graph_payload.get('centralite_harmonique'),
        graph_payload.get('centralite_harmonique_rang'),
        total_domains,
    )
    pagerank = _signal(
        graph_payload.get('pagerank'),
        graph_payload.get('pagerank_rang'),
        total_domains,
    )

    primaire = 'centralite_harmonique' if harmonique['rang'] is not None else (
        'pagerank' if pagerank['rang'] is not None else 'centralite_harmonique'
    )
    retenu = harmonique if primaire == 'centralite_harmonique' else pagerank

    classe = retenu['rang'] is not None
    conclusif = graph_payload.get('conclusif')
    fiable = bool(classe or conclusif is not False)

    if classe:
        cle, libelle = retenu['niveau'], retenu['niveau_libelle']
        metrique = ('centralité harmonique' if primaire == 'centralite_harmonique'
                    else 'PageRank')
        resume = (
            f'Autorité {libelle.lower()} : rang {_nombre(retenu["rang"])} '
            f'en {metrique} dans le graphe de domaines Common Crawl.'
        )
        if retenu['percentile'] is not None:
            resume += (
                f' Devant {str(retenu["percentile"]).replace(".", ",")} % '
                f'des domaines classés.'
            )
    elif fiable:
        cle, libelle = _NIVEAU_NON_CLASSE
        resume = (
            'Domaine absent des classements Common Crawl : aucune autorité '
            "mesurable ici, ce qui est normal pour un site récent ou petit."
        )
    else:
        cle, libelle = _NIVEAU_INCONNU
        resume = (
            "Autorité inconnue : la lecture du graphe s'est arrêtée avant de "
            'conclure, ce sont des données manquantes et pas une absence.'
        )

    return {
        'primaire': primaire,
        'niveau': cle,
        'niveau_libelle': libelle,
        'percentile': retenu['percentile'],
        'signaux': {
            'centralite_harmonique': harmonique,
            'pagerank': pagerank,
        },
        'fiable': fiable,
        'resume': resume,
        'paliers': [
            {'rang_max': seuil, 'niveau': cle_p, 'libelle': libelle_p}
            for seuil, cle_p, libelle_p in PALIERS_AUTORITE
        ],
    }


# --------------------------------------------------------------------------
# Public entry points
# --------------------------------------------------------------------------

def _base_payload(domaine, inverse, version, today) -> dict:
    periode = _periode(version) if version else None
    return {
        'domaine': domaine,
        'domaine_inverse': inverse,
        'version': version,
        'jeu_de_donnees': {
            'source': 'Common Crawl, graphe de domaines',
            'version': version,
            'periode_libelle': periode[2] if periode else None,
            'url_classements': _url(version, _SUFFIXE_CLASSEMENTS) if version else None,
            'url_sommets': _url(version, _SUFFIXE_SOMMETS) if version else None,
            'url_aretes': _url(version, _SUFFIXE_ARETES) if version else None,
        },
        'fraicheur': data_freshness(version, today=today),
        'trouve': False,
        'dans_le_graphe': None,
        'conclusif': False,
        'pagerank': None,
        'pagerank_rang': None,
        'centralite_harmonique': None,
        'centralite_harmonique_rang': None,
        'nombre_hotes': None,
        'domaines_referents': [],
        'liens_entrants_detectes': 0,
        'referents_demandes': True,
        'referents_complets': False,
        'rang_max_atteint': None,
        'etapes': [],
        'couverture': {},
        'message': '',
        'erreur': None,
    }


def fetch_domain_graph(domain, *, time_budget=60.0, release=None,
                       referents=True, today=None) -> dict:
    """Query Common Crawl's domain graph for one domain.

    Runs up to five streaming passes, each with its own slice of the budget:
    the target's ranks entry, its vertex id, the incoming edges, the names
    behind those edges, and the ranks of those names. A stage that runs out of
    time stops and says so; the stages after it still get their slice, so a
    short budget degrades into a partial answer rather than nothing.

    This is a background call. See the module docstring: the files are tens of
    gigabytes and a complete referring-domain answer needs a full pass over the
    largest of them.

    Args:
        domain: bare domain or full URL. www is dropped, IDN is punycoded.
        time_budget: seconds of wall clock the whole call may use, discovery
            included. `BUDGET_TACHE_FOND` is the order of magnitude a complete
            referring-domain scan needs.
        release: pin a release name (`cc-main-2026-jan-feb-mar`). Discovered
            from the calendar when None.
        referents: False to skip the three expensive stages and spend the whole
            budget on the domain's own authority.
        today: reference date for the freshness block. Injectable for tests.

    Returns a dict with: domaine, version, jeu_de_donnees, fraicheur, trouve,
    dans_le_graphe, conclusif, pagerank(+_rang), centralite_harmonique(+_rang),
    nombre_hotes, domaines_referents (unsorted), liens_entrants_detectes,
    referents_complets, rang_max_atteint, etapes, couverture, message
    (French), erreur.

    `conclusif` is the field that matters: False means the scan stopped early
    and an empty result proves nothing. Never render an absence without it.

    Raises CommonCrawlError on a malformed domain or release name, ValueError
    on a negative budget. Network failures come back in `erreur`, not as
    exceptions, since a worker needs the partial payload.
    """
    domaine = _normalise_domaine(domain)
    inverse = _inverse(domaine)
    if time_budget is None or float(time_budget) < 0:
        raise ValueError('time_budget must be positive')
    if release is not None:
        _valide_version(release)

    budget = _Budget(float(time_budget))
    version = _resoudre_version(release, budget, today)
    payload = _base_payload(domaine, inverse, version, today)
    payload['referents_demandes'] = bool(referents)

    if not version:
        payload['erreur'] = 'version_introuvable'
        payload['message'] = (
            'Aucune version du graphe Common Crawl accessible : le service ne '
            "répond pas ou aucun nom de version connu n'existe. Réessaie plus "
            'tard.'
        )
        payload['couverture'] = _couverture(budget, [])
        return payload

    parts = _PARTS if referents else _PARTS_SANS_REFERENTS
    scans = []

    # 1. The target's own authority. First because it is the cheap, useful half
    # of the answer, and losing it to an edges scan that was never going to
    # finish would be the worst possible trade.
    scan_rangs = _Scan('classements_cible', _url(version, _SUFFIXE_CLASSEMENTS))
    scans.append(scan_rangs)
    classements = _lire_classements(
        version, [inverse], budget, scan_rangs, budget.echeance(parts['classements_cible']),
    )
    payload['rang_max_atteint'] = classements['rang_max_atteint']
    entree = classements['trouves'].get(inverse)
    if entree:
        payload.update({
            'trouve': True,
            'dans_le_graphe': True,
            'pagerank': entree['pagerank'],
            'pagerank_rang': entree['pagerank_rang'],
            'centralite_harmonique': entree['centralite_harmonique'],
            'centralite_harmonique_rang': entree['centralite_harmonique_rang'],
            'nombre_hotes': entree['nombre_hotes'],
        })

    # 2. The vertex id. Needed for the edges, and it doubles as the only proof
    # of absence available, thanks to the file's sort order.
    sommet = {'id': None, 'absent': None, 'nombre_hotes': None}
    besoin_sommet = referents or not payload['trouve']
    if besoin_sommet and not budget.epuise():
        scan_sommet = _Scan('sommets_cible', _url(version, _SUFFIXE_SOMMETS))
        scans.append(scan_sommet)
        sommet = _lire_sommet_cible(
            version, inverse, budget, scan_sommet,
            budget.echeance(parts['sommets_cible']),
        )
        if sommet['id'] is not None:
            payload['dans_le_graphe'] = True
            if payload['nombre_hotes'] is None:
                payload['nombre_hotes'] = sommet['nombre_hotes']
        elif sommet['absent'] is True and not payload['trouve']:
            payload['dans_le_graphe'] = False

    # A domain proven absent from the vertices is absent from the ranks too, so
    # either proof closes the question.
    payload['conclusif'] = bool(
        payload['trouve']
        or payload['dans_le_graphe'] is False
        or scan_rangs.termine
    )

    # 3 to 5. Referring domains. A domain proven absent from the vertices has
    # no incoming edges by construction, so that empty list is complete and
    # must not be reported as an unfinished scan.
    if referents and payload['dans_le_graphe'] is False:
        payload['referents_complets'] = True
    elif referents and sommet['id'] is not None and not budget.epuise():
        scan_aretes = _Scan('aretes', _url(version, _SUFFIXE_ARETES))
        scans.append(scan_aretes)
        aretes = _lire_aretes(
            version, sommet['id'], budget, scan_aretes,
            budget.echeance(parts['aretes']),
        )
        identifiants = aretes['ids']
        payload['liens_entrants_detectes'] = len(identifiants)

        noms = {}
        if identifiants and not budget.epuise():
            scan_noms = _Scan('sommets_noms', _url(version, _SUFFIXE_SOMMETS))
            scans.append(scan_noms)
            noms = _lire_noms(
                version, identifiants, budget, scan_noms,
                budget.echeance(parts['sommets_noms']),
            )

        rangs = {}
        rang_max_referents = None
        if noms and not budget.epuise():
            scan_ref = _Scan('classements_referents', _url(version, _SUFFIXE_CLASSEMENTS))
            scans.append(scan_ref)
            resultat = _lire_classements(
                version, set(noms.values()), budget, scan_ref,
                budget.echeance(parts['classements_referents']),
            )
            rangs = resultat['trouves']
            rang_max_referents = resultat['rang_max_atteint']

        referentiels = []
        for identifiant, nom_inverse in noms.items():
            metriques = rangs.get(nom_inverse) or {}
            niveau, libelle = _niveau(metriques.get('centralite_harmonique_rang'))
            referentiels.append({
                'domaine': _endroit(nom_inverse),
                'domaine_inverse': nom_inverse,
                'id': identifiant,
                'centralite_harmonique': metriques.get('centralite_harmonique'),
                'centralite_harmonique_rang': metriques.get('centralite_harmonique_rang'),
                'pagerank': metriques.get('pagerank'),
                'pagerank_rang': metriques.get('pagerank_rang'),
                'nombre_hotes': metriques.get('nombre_hotes'),
                'niveau': niveau,
                'niveau_libelle': libelle,
                'autorite_lue': bool(metriques),
            })
        payload['domaines_referents'] = referentiels
        payload['referents_complets'] = bool(
            scan_aretes.termine
            and not aretes['plafond_atteint']
            and (not identifiants or len(noms) == len(identifiants))
        )
        if rang_max_referents is not None:
            payload['rang_max_atteint'] = max(
                payload['rang_max_atteint'] or 0, rang_max_referents,
            )

    # Every attempted read failing is a different situation from a read that
    # ran and found nothing, and the caller has to be able to retry one without
    # retrying the other.
    lancees = [scan for scan in scans if scan.arret != 'non_lance']
    if lancees and all(scan.arret == 'erreur' for scan in lancees):
        payload['erreur'] = 'lecture_impossible'

    payload['etapes'] = [scan.payload() for scan in scans]
    payload['couverture'] = _couverture(budget, scans)
    payload['message'] = _message_graphe(payload, scan_rangs)
    return payload


def _couverture(budget: _Budget, scans) -> dict:
    """What the call actually got through, in one block a screen can print."""
    return {
        'budget_secondes': round(budget.total, 2),
        'temps_ecoule': round(budget.ecoule, 2),
        'budget_epuise': budget.epuise(),
        'octets_lus': budget.octets,
        'plafond_octets': budget.max_octets,
        'etapes_terminees': [s.nom for s in scans if s.termine],
        'etapes_incompletes': [s.nom for s in scans if not s.termine],
    }


def _message_graphe(payload, scan_rangs) -> str:
    """One honest French sentence about what was and was not established."""
    domaine = payload['domaine']
    libelle = payload['jeu_de_donnees'].get('periode_libelle')
    crawl = f'crawl {libelle}' if libelle else 'crawl inconnu'

    if payload['erreur'] == 'lecture_impossible':
        return (
            f'Lecture du graphe Common Crawl impossible : aucun fichier du '
            f'{crawl} ne répond. Rien ne peut être affirmé sur {domaine}, '
            f'réessaie plus tard.'
        )

    if payload['trouve']:
        morceaux = [f'{domaine} figure dans le graphe Common Crawl ({crawl}).']
        if payload['centralite_harmonique_rang'] is not None:
            morceaux.append(
                f'Centralité harmonique : rang '
                f'{_nombre(payload["centralite_harmonique_rang"])}.'
            )
        if payload['pagerank_rang'] is not None:
            morceaux.append(
                f'PageRank : rang {_nombre(payload["pagerank_rang"])}.'
            )
        return ' '.join(morceaux)

    if payload['dans_le_graphe'] is False:
        return (
            f'{domaine} est absent du graphe de domaines Common Crawl ({crawl}) : '
            f'aucun lien vers lui vu pendant ce trimestre. Trop récent, trop '
            f'petit, ou jamais crawlé.'
        )

    if payload['dans_le_graphe'] is True:
        return (
            f'{domaine} apparaît dans le graphe Common Crawl ({crawl}) mais pas '
            f'dans le classement lu. Ses valeurs de PageRank et de centralité '
            f'restent inconnues.'
        )

    fraction = scan_rangs.fraction
    return (
        f'Recherche incomplète : {_pourcent(fraction)} du fichier de classement '
        f'lu en {_secondes(payload["couverture"].get("temps_ecoule", 0))} s. '
        f"L'absence de {domaine} n'est pas prouvée, relance en tâche de fond "
        f'avec un budget plus large.'
    )


def referring_domains(domain, *, limit=200, time_budget=60.0, release=None,
                      today=None) -> dict:
    """Domains linking to this one, most authoritative first.

    Real edges out of Common Crawl's domain graph, not a mention count: each
    entry is a distinct domain that carried at least one link to the target
    during that crawl quarter. The order is harmonic centrality rank, then
    PageRank rank, then unranked domains alphabetically.

    The sort survives a truncated scan better than it looks. The ranks file is
    ordered by authority, so a pass cut short by the budget has already seen
    the strongest referrers; what it misses are the weak ones, which land at
    the bottom of the list anyway.

    Background call. See the module docstring.

    Args:
        domain: bare domain or full URL.
        limit: how many referring domains to return, best first.
        time_budget: seconds of wall clock for the whole call.
        release: pin a release name. Discovered from the calendar when None.
        today: reference date for the freshness block.

    Returns: domaine, version, jeu_de_donnees, fraicheur, domaines_referents,
    nombre, nombre_total, limite, tronquee, complet, conclusif,
    liens_entrants_detectes, autorite (the target's own signals), etapes,
    couverture, message (French), erreur.

    `complet` False means the list is a floor, never a total. Raises
    CommonCrawlError on a malformed domain, ValueError on a bad limit.
    """
    if not isinstance(limit, int) or isinstance(limit, bool) or limit < 1:
        raise ValueError('limit must be a positive integer')

    payload = fetch_domain_graph(
        domain, time_budget=time_budget, release=release,
        referents=True, today=today,
    )

    referentiels = sorted(payload['domaines_referents'], key=_cle_tri)
    total = len(referentiels)
    retenus = referentiels[:limit]

    resultat = {
        'domaine': payload['domaine'],
        'version': payload['version'],
        'jeu_de_donnees': payload['jeu_de_donnees'],
        'fraicheur': payload['fraicheur'],
        'domaines_referents': retenus,
        'nombre': len(retenus),
        'nombre_total': total,
        'limite': limit,
        'tronquee': total > limit,
        'complet': bool(payload['referents_complets']),
        'conclusif': bool(payload['conclusif']),
        'dans_le_graphe': payload['dans_le_graphe'],
        'liens_entrants_detectes': payload['liens_entrants_detectes'],
        'rang_max_atteint': payload['rang_max_atteint'],
        'autorite': authority_signals(payload),
        'etapes': payload['etapes'],
        'couverture': payload['couverture'],
        'erreur': payload['erreur'],
    }
    resultat['message'] = _message_referents(resultat, payload)
    return resultat


def _cle_tri(entree):
    """Harmonic rank, then PageRank rank, unranked domains last."""
    rang = entree.get('centralite_harmonique_rang')
    if rang is None:
        rang = entree.get('pagerank_rang')
    if rang is None:
        return (1, 0, entree.get('domaine', ''))
    return (0, rang, entree.get('domaine', ''))


def _message_referents(resultat, payload) -> str:
    """French summary that never turns an unfinished scan into a total."""
    if payload['erreur']:
        return payload['message']

    domaine = resultat['domaine']
    libelle = resultat['jeu_de_donnees'].get('periode_libelle')
    crawl = f'crawl {libelle}' if libelle else 'crawl inconnu'
    total = resultat['nombre_total']

    if resultat['dans_le_graphe'] is False:
        return (
            f'{domaine} est absent du graphe de domaines Common Crawl ({crawl}) : '
            f'aucun lien entrant vu pendant ce trimestre.'
        )

    if resultat['complet']:
        if total == 0:
            return (
                f'Aucun domaine référent pour {domaine} dans le graphe Common '
                f'Crawl ({crawl}). Lecture complète, le zéro est réel.'
            )
        tete = (
            f'1 domaine référent trouvé pour {domaine}'
            if total == 1
            else f'{_nombre(total)} domaines référents trouvés pour {domaine}'
        )
        fin = f' ({crawl}, lecture complète).'
        if resultat['tronquee']:
            fin = (
                f' ({crawl}, lecture complète), les {_nombre(resultat["nombre"])} '
                f'plus forts sont listés.'
            )
        return tete + fin

    etapes = {e['nom']: e for e in resultat['etapes']}
    aretes = etapes.get('aretes')
    fraction = aretes['fraction'] if aretes else None
    lu = _pourcent(fraction)
    secondes = resultat['couverture'].get('temps_ecoule', 0)

    if aretes is None:
        return (
            f"Liste des domaines référents non établie pour {domaine} : le "
            f'budget de {_secondes(resultat["couverture"].get("budget_secondes", 0))} s '
            f"s'est épuisé avant la lecture des liens ({crawl}). "
            f'Relance en tâche de fond.'
        )

    # Links can be found without their names when the budget dies between the
    # edges pass and the vertices pass. Saying "0 domaines" there would be the
    # same lie as calling a timeout an absence.
    detectes = resultat['liens_entrants_detectes']
    if total == 1:
        tete = f'1 domaine référent trouvé pour {domaine}'
    elif total:
        tete = f'{_nombre(total)} domaines référents trouvés pour {domaine}'
    elif detectes:
        tete = (
            f'{_nombre(detectes)} liens entrants repérés pour {domaine}, '
            f'sans le nom des domaines'
        )
    else:
        tete = f'Aucun domaine référent lu pour {domaine}'

    return (
        f'{tete} en lisant {lu} du fichier de liens en {_secondes(secondes)} s '
        f'({crawl}). Ce résultat est un plancher, pas un total : relance en '
        f'tâche de fond avec un budget de {_nombre(BUDGET_TACHE_FOND)} s pour '
        f'la liste complète.'
    )
