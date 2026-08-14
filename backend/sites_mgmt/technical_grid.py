"""Technical SEO grid: nine categories scored on what a site actually serves.

Ported from claude-seo v2.2.4 `skills/seo-technical/SKILL.md`, with the score
weighting of `skills/seo/SKILL.md`.
Copyright (c) 2025 Daniel Agrici (AgriciDaniel). MIT.
https://github.com/AgriciDaniel/claude-seo

Upstream ships the nine categories as a checklist for a human or an LLM and
leans on Playwright, PageSpeed and Lighthouse for half of them. This port keeps
every threshold the source states as fact (Googlebot's 2 MB of HTML, LCP 2.5 s
/ INP 200 ms / CLS 0.1, the five security headers, the table of seven AI
crawlers) and turns the checklist into a deterministic scorer over data the
backend already holds. A check that cannot be measured is dropped from its
category and a category with nothing measurable leaves the denominator, the way
Lighthouse removes an N/A audit, so a site is never charged for what nobody
looked at. Two Quebec adaptations carry the port: blocking a training-only AI
crawler is reported without penalty while blocking one of the two crawlers that
produce citations costs points, and accented or percent-encoded URL paths are
flagged because French CMS exports produce them by the hundred.

Scope is deliberately narrow so nothing gets counted twice in the site score.
Title and meta-description lengths belong to On-Page, deep schema validation to
`schema_validator`, sitemap discovery to `sitemap_discovery`, agent readability
to `agent_ux`. Pure data in, pure data out: no network, no ORM, no Django.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

__all__ = [
    'CATEGORIES',
    'POIDS_CATEGORIES',
    'CRAWLERS_IA',
    'ENTETES_SECURITE',
    'SEUILS_CWV',
    'LIMITE_HTML_GOOGLEBOT',
    'PRIORITES',
    'BLOQUANTS',
    'score_technical',
]


# Ordered (key, French label, weight). Weights sum to 100 and are the share of
# the technical grade, not of the whole site score: the orchestrator gives
# Technical 22 % of its own 100, with Performance and Schema weighted again on
# their own. That is why Core Web Vitals and structured data stay modest here.
CATEGORIES = (
    ('crawlabilite', 'Crawlabilité', 18),
    ('indexabilite', 'Indexabilité', 18),
    ('securite', 'Sécurité', 12),
    ('structure_url', 'Structure des URL', 10),
    ('mobile', 'Mobile et expérience de page', 12),
    ('core_web_vitals', 'Core Web Vitals', 10),
    ('donnees_structurees', 'Données structurées', 8),
    ('rendu_javascript', 'Rendu JavaScript', 8),
    ('indexnow', 'IndexNow', 4),
)

POIDS_CATEGORIES = {cle: poids for cle, _, poids in CATEGORIES}

PRIORITES = ('critique', 'elevee', 'moyenne', 'faible')
_RANG_PRIORITE = {nom: rang for rang, nom in enumerate(PRIORITES)}

# Checks that do not lower a grade, they void it: while one of them fails the
# page cannot enter the index at all, and the other eight categories describe a
# page nobody will ever see. They are reported apart from the score because a
# weighted average cannot express "none of this matters yet".
BLOQUANTS = frozenset({
    'robots_bloque_tout',
    'robots_bloque_googlebot',
    'noindex',
    'statut_http',
})

# The source's AI crawler table. `role` is ours: 'citation' marks the two that
# feed an answer a user reads today (live browsing, search index), 'entrainement'
# the ones that only harvest for model training. Blocking the second kind is a
# business decision Gridar has no standing to penalize; blocking the first kind
# removes the site from AI answers, which is what Gridar sells.
CRAWLERS_IA = (
    ('GPTBot', 'OpenAI', 'entrainement'),
    ('ChatGPT-User', 'OpenAI', 'citation'),
    ('ClaudeBot', 'Anthropic', 'entrainement'),
    ('PerplexityBot', 'Perplexity', 'citation'),
    ('Bytespider', 'ByteDance', 'entrainement'),
    ('Google-Extended', 'Google', 'entrainement'),
    ('CCBot', 'Common Crawl', 'entrainement'),
)

ENTETES_SECURITE = (
    ('content-security-policy', 'Content-Security-Policy'),
    ('strict-transport-security', 'Strict-Transport-Security'),
    ('x-frame-options', 'X-Frame-Options'),
    ('x-content-type-options', 'X-Content-Type-Options'),
    ('referrer-policy', 'Referrer-Policy'),
)

# Good / needs-improvement boundaries. INP replaced FID in March 2024 and FID
# left the field tools in September 2024, so it is read nowhere in this file.
SEUILS_CWV = {
    'lcp': (2.5, 4.0),
    'inp': (200.0, 500.0),
    'cls': (0.1, 0.25),
}

# Googlebot fetches the first 2 MB of an HTML document. Anything past it,
# JSON-LD included, is invisible to the index.
LIMITE_HTML_GOOGLEBOT = 2 * 1024 * 1024
_ALERTE_HTML = 1024 * 1024

# Word floor before a page reads as thin. `html_parse.extract_seo_signals`
# already drops nav and footer from its count, so this floor sits lower than the
# per-type minimums of `quality_gates`, which count the whole document.
_MOTS_MINCE = 300
_MOTS_TRES_MINCE = 150

# Below this many visible words the page is not thin, it is empty: that is a
# rendering problem, scored once under Rendu JavaScript and not again here.
_MOTS_COQUILLE = 50
_MOTS_PARTIELS = 150

_URL_LONGUE = 100
_PROFONDEUR_MAX = 5

# Scans run inside a request cycle on markup fetched from a third party, so
# everything is bounded rather than trusting the page to be a sane size.
_MAX_HTML = 3_000_000
_MAX_ROBOTS_LIGNES = 5000
_FENETRE_POPUP = 1500


# ---------------------------------------------------------------------------
# robots.txt
# ---------------------------------------------------------------------------

def _parse_robots(body: str) -> dict:
    """Group directives by user-agent the way a crawler reads the file.

    Consecutive `User-agent` lines share one group, a rule line closes the
    header, and `Sitemap` is file-global rather than group-scoped.
    """
    groupes: dict[str, dict] = {}
    sitemaps: list[str] = []
    courant: list[str] = []
    entete = True

    for brute in (body or '').splitlines()[:_MAX_ROBOTS_LIGNES]:
        ligne = brute.split('#', 1)[0].strip()
        if not ligne or ':' not in ligne:
            continue
        champ, _, valeur = ligne.partition(':')
        champ = champ.strip().lower()
        valeur = valeur.strip()

        if champ == 'user-agent':
            if not entete:
                courant = []
                entete = True
            agent = valeur.lower()
            if agent:
                courant.append(agent)
                groupes.setdefault(agent, {'allow': [], 'disallow': []})
        elif champ in ('allow', 'disallow'):
            entete = False
            for agent in courant:
                groupes[agent][champ].append(valeur)
        elif champ == 'sitemap' and valeur:
            sitemaps.append(valeur)

    return {'groupes': groupes, 'sitemaps': sitemaps}


def _groupe_pour(robots: dict, agent: str) -> dict | None:
    """The group a crawler obeys: its own if it has one, otherwise the wildcard."""
    groupes = robots['groupes']
    exact = groupes.get(agent.lower())
    if exact is not None:
        return exact
    return groupes.get('*')


def _bloque_tout(groupe) -> bool:
    if not groupe:
        return False
    if any(regle.strip() in ('/', '/*') for regle in groupe['allow']):
        return False
    return any(regle.strip() in ('/', '/*') for regle in groupe['disallow'])


# Paths whose blocking keeps Googlebot from rendering the page it just fetched.
_RE_RESSOURCE = re.compile(
    r'\.(?:css|js)\b|/wp-content|/wp-includes|/assets|/static|/dist|/build'
    r'|/themes|/media|/_next|/bundles',
    re.IGNORECASE,
)


def _ressources_bloquees(groupe) -> list[str]:
    if not groupe:
        return []
    autorises = {regle.strip() for regle in groupe['allow']}
    return [
        regle for regle in groupe['disallow']
        if regle.strip() and regle.strip() not in autorises
        and _RE_RESSOURCE.search(regle)
    ][:5]


# ---------------------------------------------------------------------------
# Raw markup markers
# ---------------------------------------------------------------------------

_RE_META_VIEWPORT = re.compile(
    r'<meta\b[^>]*\bname\s*=\s*["\']?viewport["\']?[^>]*>', re.IGNORECASE,
)
_RE_CONTENT = re.compile(
    r'\bcontent\s*=\s*(?:"([^"]*)"|\'([^\']*)\'|([^\s>]+))', re.IGNORECASE,
)
_RE_SCRIPT = re.compile(r'<script\b[^>]*>(.*?)</script>', re.IGNORECASE | re.DOTALL)
_RE_BASE64_IMG = re.compile(r'data:image/[a-z0-9.+-]+;base64,', re.IGNORECASE)
_RE_ITEMSCOPE = re.compile(r'\bitemscope\b', re.IGNORECASE)
_RE_RDFA = re.compile(r'\b(?:typeof|vocab)\s*=\s*["\']', re.IGNORECASE)

# An empty framework mount point is the signature of a page whose content only
# exists after JavaScript has run.
_RE_COQUILLE_SPA = re.compile(
    r'<(div|main|section)\b[^>]*\bid\s*=\s*["\']?'
    r'(root|app|__next|__nuxt|___gatsby|q-app|application|main-app|svelte)'
    r'["\']?[^>]*>\s*(?:<!--.*?-->\s*)*</\1>',
    re.IGNORECASE | re.DOTALL,
)

# Back-button hijacking, added to Google's spam policies in April 2026 and
# enforced since June 2026. Two markers are required together: a popstate
# handler alone is how every SPA router works, and forcing the history forward
# from inside one is what defeats the Back button.
_RE_POPSTATE = re.compile(
    r'onpopstate|addEventListener\s*\(\s*["\']popstate', re.IGNORECASE,
)
_RE_RETOUR_FORCE = re.compile(
    r'history\s*\.\s*(?:go\s*\(\s*1\s*\)|forward\s*\(\s*\))', re.IGNORECASE,
)

_RE_CONTENEUR_POPUP = re.compile(
    r'<(?:div|section|aside|dialog)\b[^>]*\b(?:class|id)\s*=\s*["\'][^"\']*'
    r'\b(?:popup|pop-up|modal|interstitial|interstitiel|lightbox|overlay)\b',
    re.IGNORECASE,
)
_RE_PROMO = re.compile(
    r"infolettre|newsletter|abonne|abonnez|inscris|inscrivez|rabais|promo"
    r"|coupon|offre exclusive|subscribe|discount|sign ?up",
    re.IGNORECASE,
)
# Consent and legal dialogs are named as acceptable by the source, and Quebec
# sites carry one for Loi 25, so they must never trip the interstitial rule.
_RE_CONSENTEMENT = re.compile(
    r"t[ée]moin|cookie|consent|vie priv[ée]e|privacy|rgpd|gdpr|loi 25"
    r"|confidentialit",
    re.IGNORECASE,
)
_RE_REPLI = re.compile(
    r'class\s*=\s*["\'][^"\']*\b(?:accordion|accordeon|accord[ée]on|collapse'
    r'|tab-pane|panel-collapse|toggle-content|read-more|lire-la-suite)\b',
    re.IGNORECASE,
)


def _markers(html: str) -> dict:
    """Read the handful of raw-markup signals the parsed signals cannot carry.

    `extract_seo_signals` covers everything an audit needs about the document's
    content; what is missing is markup that is not content: the viewport tag,
    the weight of the scripts, an empty SPA shell. Targeted regexes are enough
    for those, and none of them re-parses the page.
    """
    doc = (html or '')[:_MAX_HTML]
    if not doc:
        return {}

    scripts = _RE_SCRIPT.findall(doc)
    octets_scripts = sum(len(corps) for corps in scripts)

    viewport = None
    balise = _RE_META_VIEWPORT.search(doc)
    if balise:
        contenu = _RE_CONTENT.search(balise.group(0))
        viewport = ''
        if contenu:
            viewport = (contenu.group(1) or contenu.group(2)
                        or contenu.group(3) or '').strip().lower()

    return {
        'octets': len(doc.encode('utf-8', 'ignore')),
        'tronque': len(html or '') > _MAX_HTML,
        'octets_scripts': octets_scripts,
        'nb_scripts': len(scripts),
        'viewport': viewport,
        'coquille_spa': bool(_RE_COQUILLE_SPA.search(doc)),
        'images_base64': len(_RE_BASE64_IMG.findall(doc)),
        'microdata': bool(_RE_ITEMSCOPE.search(doc)),
        'rdfa': bool(_RE_RDFA.search(doc)),
        'detournement_retour': bool(
            _RE_POPSTATE.search(doc) and _RE_RETOUR_FORCE.search(doc)
        ),
        'interstitiel': _detecte_interstitiel(doc),
        'blocs_replies': len(_RE_REPLI.findall(doc)),
    }


def _detecte_interstitiel(doc: str) -> bool:
    """A promotional overlay, consent and legal dialogs excluded.

    Static markup cannot prove a layer shows on load, so the rule demands two
    signals at once and stays cheap in points: an overlay container whose own
    neighbourhood sells something, and no consent vocabulary in that same
    window.
    """
    for match in _RE_CONTENEUR_POPUP.finditer(doc):
        fenetre = doc[match.end():match.end() + _FENETRE_POPUP]
        if _RE_PROMO.search(fenetre) and not _RE_CONSENTEMENT.search(fenetre):
            return True
    return False


# ---------------------------------------------------------------------------
# Accumulator
# ---------------------------------------------------------------------------

class _Grid:
    """Collects measured checks per category and renders the final report.

    A check reports a ratio in [0, 1] and the weight it carries inside its
    category. Weights are relative: the category renormalizes over the checks
    that actually ran, so skipping one redistributes rather than punishes.
    """

    def __init__(self):
        self._cat = {
            cle: {
                'gagne': 0.0,
                'possible': 0.0,
                'faites': 0,
                'ignorees': [],
                'constats': [],
                'problemes': [],
            }
            for cle, _, _ in CATEGORIES
        }
        self._recos = []

    def constat(self, categorie: str, texte: str) -> None:
        if texte:
            self._cat[categorie]['constats'].append(texte)

    def ignore(self, categorie: str, raison: str) -> None:
        """Mark one check as not measurable. It leaves the denominator."""
        self._cat[categorie]['ignorees'].append(raison)

    def verifie(self, categorie: str, code: str, poids: float, ratio,
                *, constat: str = '', probleme: str = '', action: str = '',
                priorite: str = 'moyenne') -> None:
        ratio = 1.0 if ratio is True else 0.0 if ratio is False else float(ratio)
        ratio = max(0.0, min(1.0, ratio))
        cat = self._cat[categorie]
        cat['gagne'] += poids * ratio
        cat['possible'] += poids
        cat['faites'] += 1

        if ratio >= 1.0:
            self.constat(categorie, constat)
            return

        if probleme:
            cat['problemes'].append(probleme)
        self._recos.append({
            'categorie': categorie,
            'code': code,
            'priorite': priorite if priorite in _RANG_PRIORITE else 'moyenne',
            'manque': poids * (1.0 - ratio),
            'probleme': probleme,
            'action': action,
        })

    def resultat(self) -> dict:
        categories = {}
        non_mesurees = []
        total_gagne = 0.0
        total_max = 0.0

        for cle, libelle, poids in CATEGORIES:
            cat = self._cat[cle]
            applicable = cat['possible'] > 0
            note = None
            score = 0.0

            if applicable:
                ratio = cat['gagne'] / cat['possible']
                score = round(ratio * poids, 1)
                note = int(round(ratio * 100))
                total_gagne += score
                total_max += poids
            else:
                non_mesurees.append(cle)

            for reco in self._recos:
                if reco['categorie'] == cle:
                    reco['points_recuperables'] = round(
                        reco['manque'] / cat['possible'] * poids, 1,
                    )
                    reco['libelle_categorie'] = libelle

            critique = any(
                r['categorie'] == cle and r['priorite'] == 'critique'
                for r in self._recos
            )
            if not applicable:
                statut = 'non_mesure'
            elif critique or note < 70:
                statut = 'echec'
            elif note < 90:
                statut = 'attention'
            else:
                statut = 'reussi'

            ignorees = list(dict.fromkeys(r for r in cat['ignorees'] if r))
            categories[cle] = {
                'libelle': libelle,
                'score': score,
                'max': float(poids) if applicable else 0.0,
                'note': note,
                'applicable': applicable,
                'statut': statut,
                'constats': cat['constats'],
                'problemes': cat['problemes'],
                'verifications': {
                    'faites': cat['faites'],
                    'ignorees': len(cat['ignorees']),
                },
                'non_mesure': ignorees,
            }

        recommandations = sorted(
            (
                {
                    'categorie': r['categorie'],
                    'libelle_categorie': r['libelle_categorie'],
                    'code': r['code'],
                    'priorite': r['priorite'],
                    'points_recuperables': r['points_recuperables'],
                    'probleme': r['probleme'],
                    'action': r['action'],
                }
                for r in self._recos
            ),
            key=lambda r: (-r['points_recuperables'], _RANG_PRIORITE[r['priorite']]),
        )

        score = int(round(total_gagne / total_max * 100)) if total_max else None
        return {
            'score': score,
            'categories': categories,
            'recommandations': recommandations,
            'bloquants': [
                {
                    'code': r['code'],
                    'categorie': r['categorie'],
                    'probleme': r['probleme'],
                }
                for r in recommandations if r['code'] in BLOQUANTS
            ],
            'couverture': round(total_max, 1),
            'categories_non_mesurees': non_mesurees,
        }


# ---------------------------------------------------------------------------
# Context
# ---------------------------------------------------------------------------

def _texte(valeur) -> str:
    return valeur.strip() if isinstance(valeur, str) else ''


def _entetes(headers) -> dict | None:
    if headers is None:
        return None
    try:
        return {
            str(cle).strip().lower(): str(valeur or '').strip()
            for cle, valeur in headers.items()
        }
    except AttributeError:
        return None


def _sans_www(hote: str) -> str:
    return hote[4:] if hote.startswith('www.') else hote


def _cle_url(url: str) -> str:
    """Comparable form of a URL: no scheme, no www, no trailing slash, no anchor."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return ''
    hote = _sans_www((parsed.hostname or '').lower())
    chemin = (parsed.path or '/').rstrip('/') or '/'
    requete = f'?{parsed.query}' if parsed.query else ''
    return f'{hote}{chemin}{requete}'


def _context(signals, robots_txt, headers, url, html, http_status,
             web_vitals, indexnow_ready) -> dict:
    parsed = None
    if url:
        try:
            parsed = urlparse(url)
        except ValueError:
            parsed = None

    corps_robots = _texte(robots_txt)
    return {
        'signals': signals,
        'url': _texte(url),
        'parsed': parsed,
        'robots_brut': corps_robots,
        'robots': _parse_robots(corps_robots) if corps_robots else None,
        'entetes': _entetes(headers),
        'markers': _markers(html) if html else {},
        'statut': http_status,
        'cwv': _normalise_cwv(web_vitals),
        'indexnow': indexnow_ready,
    }


def _normalise_cwv(donnees) -> dict:
    """Read LCP in seconds, INP in milliseconds, CLS unitless, whatever came in.

    PageSpeed returns LCP in milliseconds and CrUX in the same unit, while a
    hand-filled field holds seconds. Guessing from the magnitude is safe: no
    real LCP reaches 60 s and no real INP sits under 5 ms.
    """
    if not isinstance(donnees, dict):
        return {}

    plat = {str(cle).strip().lower(): valeur for cle, valeur in donnees.items()}
    sortie = {'fid_fourni': any(cle in plat for cle in ('fid', 'first_input_delay'))}

    alias = {
        'lcp': ('lcp', 'largest_contentful_paint'),
        'inp': ('inp', 'interaction_to_next_paint'),
        'cls': ('cls', 'cumulative_layout_shift'),
    }
    for metrique, cles in alias.items():
        valeur = None
        for cle in cles:
            brut = plat.get(cle)
            if brut is None:
                continue
            try:
                valeur = float(brut)
            except (TypeError, ValueError):
                valeur = None
            break
        if valeur is None or valeur < 0:
            continue
        if metrique == 'lcp' and valeur > 60:
            valeur = valeur / 1000.0
        elif metrique == 'inp' and 0 < valeur <= 5:
            valeur = valeur * 1000.0
        sortie[metrique] = valeur

    source = str(plat.get('source') or '').strip().lower()
    sortie['terrain'] = source in ('crux', 'field', 'terrain', 'psi', 'pagespeed')
    return sortie


# ---------------------------------------------------------------------------
# 1. Crawlability
# ---------------------------------------------------------------------------

def _crawlability(grid, ctx) -> None:
    cle = 'crawlabilite'
    robots = ctx['robots']
    markers = ctx['markers']

    if robots is None:
        grid.ignore(cle, "robots.txt non fourni : les règles du fichier n'ont pas été lues.")
    else:
        groupe_star = robots['groupes'].get('*')
        # The Googlebot check reads the group named after it, never the fallback:
        # a wildcard `Disallow: /` is already charged by the check above, and a
        # crawler blocked twice would cost the category twice.
        groupe_google = robots['groupes'].get('googlebot')

        grid.verifie(
            cle, 'robots_bloque_tout', 5, not _bloque_tout(groupe_star),
            constat="robots.txt ne bloque pas le site pour les robots génériques.",
            probleme="robots.txt contient « User-agent: * » suivi de « Disallow: / » : tout le site est interdit de crawl.",
            action="Retire la ligne « Disallow: / » du groupe « User-agent: * ». Tant qu'elle est là, aucune page ne peut entrer dans l'index.",
            priorite='critique',
        )
        grid.verifie(
            cle, 'robots_bloque_googlebot', 4, not _bloque_tout(groupe_google),
            constat="Googlebot n'est bloqué par aucune règle de robots.txt.",
            probleme="robots.txt interdit explicitement Googlebot sur tout le site.",
            action="Supprime le « Disallow: / » du groupe Googlebot. Une règle propre à Googlebot remplace la règle générique, donc elle décide seule.",
            priorite='critique',
        )

        bloquees = _ressources_bloquees(_groupe_pour(robots, 'googlebot'))
        grid.verifie(
            cle, 'robots_ressources', 2, not bloquees,
            constat="Les fichiers CSS et JavaScript restent accessibles au crawl.",
            probleme=(
                "robots.txt bloque des ressources nécessaires au rendu : "
                + ', '.join(bloquees) + '.'
            ) if bloquees else '',
            action="Autorise les CSS et les JS. Google rend la page comme un navigateur : sans eux, il voit une page cassée et juge la mise en page mobile sur cette version.",
            priorite='elevee',
        )
        grid.verifie(
            cle, 'robots_sitemap', 2, bool(robots['sitemaps']),
            constat=(
                f"{len(robots['sitemaps'])} sitemap(s) déclaré(s) dans robots.txt."
                if robots['sitemaps'] else ''
            ),
            probleme="Aucune ligne « Sitemap: » dans robots.txt.",
            action="Ajoute « Sitemap: https://tondomaine.com/sitemap.xml » à la fin du robots.txt. C'est la seule déclaration que tous les moteurs lisent sans compte à ouvrir.",
            priorite='moyenne',
        )
        _crawlers_ia(grid, robots)

    meta_robots = _texte(ctx['signals'].get('meta_robots')).lower()
    grid.verifie(
        cle, 'meta_nofollow', 2, 'nofollow' not in meta_robots and 'none' not in meta_robots,
        constat='',
        probleme="La balise meta robots de la page contient « nofollow » : aucun lien de cette page n'est suivi.",
        action="Retire « nofollow » de la balise meta robots. Les liens de la page sont le chemin par lequel Google découvre le reste du site.",
        priorite='elevee',
    )

    if not markers:
        grid.ignore(cle, "HTML brut non fourni : le poids du document n'a pas été mesuré.")
        return

    octets = markers['octets']
    if octets > LIMITE_HTML_GOOGLEBOT:
        ratio = 0.0
    elif octets > _ALERTE_HTML:
        ratio = 0.5
    else:
        ratio = 1.0
    detail = ''
    if markers['images_base64']:
        detail = (
            f" {markers['images_base64']} image(s) encodée(s) en base64 directement "
            "dans le HTML pèsent dans ce total."
        )
    grid.verifie(
        cle, 'poids_html', 2, ratio,
        constat=f"Document HTML de {_ko(octets)}, sous le plafond de 2 Mo de Googlebot.",
        probleme=(
            f"Document HTML de {_ko(octets)}. Googlebot ne récupère que les 2 premiers "
            f"Mo : tout ce qui suit, JSON-LD compris, n'existe pas pour l'index.{detail}"
        ) if ratio == 0.0 else (
            f"Document HTML de {_ko(octets)}. Le plafond de Googlebot est à 2 Mo et la "
            f"marge fond vite.{detail}"
        ),
        action="Sors le CSS et le JS en ligne vers des fichiers externes, remplace les images base64 par de vrais fichiers, et garde le contenu principal et le JSON-LD dans le premier mégaoctet.",
        priorite='critique' if ratio == 0.0 else 'moyenne',
    )


def _crawlers_ia(grid, robots) -> None:
    """Score the AI crawler policy, citation crawlers apart from training ones."""
    bloques_citation = []
    bloques_entrainement = []
    for nom, societe, role in CRAWLERS_IA:
        # Named groups only. A wildcard `Disallow: /` blocks these too, and it
        # is already charged in full by `robots_bloque_tout`.
        groupe = robots['groupes'].get(nom.lower())
        if groupe is None or not _bloque_tout(groupe):
            continue
        if role == 'citation':
            bloques_citation.append(f'{nom} ({societe})')
        else:
            bloques_entrainement.append(f'{nom} ({societe})')

    if bloques_entrainement:
        grid.constat('crawlabilite', (
            "Robots d'entraînement bloqués : " + ', '.join(bloques_entrainement)
            + ". C'est un choix d'affaires légitime, sans effet sur Google Search."
        ))

    total = 2
    ratio = max(0.0, (total - len(bloques_citation)) / total)
    grid.verifie(
        'crawlabilite', 'crawlers_ia_citation', 3, ratio,
        constat="ChatGPT-User et PerplexityBot peuvent lire le site : les réponses IA peuvent le citer.",
        probleme=(
            "robots.txt bloque " + ', '.join(bloques_citation)
            + ". Ce sont les robots qui vont chercher une page au moment où quelqu'un "
              "pose une question : bloqués, le site ne peut plus être cité dans les réponses."
        ),
        action="Laisse passer ChatGPT-User et PerplexityBot. Bloquer GPTBot ou ClaudeBot empêche l'entraînement sans toucher aux citations ; bloquer les deux premiers coupe la visibilité IA. À noter : les robots déclenchés par un humain (Google-Agent, Google-NotebookLM) ignorent robots.txt de toute façon.",
        priorite='elevee',
    )


def _ko(octets: int) -> str:
    if octets >= 1024 * 1024:
        return f'{octets / (1024 * 1024):.1f} Mo'.replace('.', ',')
    return f'{octets / 1024:.0f} ko'


# ---------------------------------------------------------------------------
# 2. Indexability
# ---------------------------------------------------------------------------

_PARAMS_CONTENU = frozenset({
    'p', 'page_id', 'post', 'post_id', 'cat', 'catid', 'product_id', 'id',
    'node', 'article', 'view',
})
_PREFIXES_SUIVI = ('utm_', 'gclid', 'fbclid', 'msclkid', 'mc_cid', 'mc_eid')
_PARAMS_SUIVI = frozenset({
    'gclid', 'fbclid', 'msclkid', 'ref', 'sessionid', 'phpsessid', 'sid',
})


def _params(parsed) -> list[str]:
    if parsed is None or not parsed.query:
        return []
    noms = []
    for morceau in parsed.query.split('&'):
        nom = morceau.split('=', 1)[0].strip().lower()
        if nom:
            noms.append(nom)
    return noms


def _indexability(grid, ctx) -> None:
    cle = 'indexabilite'
    signals = ctx['signals']
    meta_robots = _texte(signals.get('meta_robots')).lower()
    canonical = _texte(signals.get('canonical'))

    noindex = 'noindex' in meta_robots or 'none' in meta_robots
    grid.verifie(
        cle, 'noindex', 6, not noindex,
        constat="Aucune directive noindex sur la page.",
        probleme=f"La page porte une directive noindex (meta robots : « {meta_robots} »).",
        action="Retire « noindex » de la balise meta robots si la page doit être trouvée. Tant qu'elle y est, aucun travail de SEO sur cette page ne peut donner un résultat.",
        priorite='critique',
    )

    grid.verifie(
        cle, 'canonical_presence', 3, bool(canonical),
        constat=f"Balise canonical présente : {canonical}" if canonical else '',
        probleme="Aucune balise canonical sur la page.",
        action="Ajoute « <link rel=\"canonical\" href=\"...\"> » pointant vers l'adresse officielle de la page. Sans elle, Google choisit lui-même laquelle des variantes (avec ou sans www, avec ou sans barre oblique, avec paramètres) il garde.",
        priorite='moyenne',
    )

    if canonical and ctx['url']:
        mienne = _cle_url(ctx['url'])
        sienne = _cle_url(canonical)
        if sienne == mienne:
            grid.verifie(cle, 'canonical_coherence', 3, True,
                         constat="La canonical pointe vers la page elle-même.")
        else:
            hote_page = mienne.split('/', 1)[0]
            hote_canon = sienne.split('/', 1)[0]
            hors_domaine = hote_canon and hote_canon != hote_page
            grid.verifie(
                cle, 'canonical_coherence', 3, 0.0 if hors_domaine else 0.5,
                probleme=(
                    f"La canonical désigne un autre domaine ({canonical}) : la page "
                    "cède son indexation à un site tiers."
                ) if hors_domaine else (
                    f"La canonical ({canonical}) ne correspond pas à l'adresse servie "
                    f"({ctx['url']})."
                ),
                action="Fais pointer la canonical vers l'adresse exacte de la page, à la barre oblique et au www près. Une canonical qui désigne autre chose demande à Google d'indexer autre chose.",
                priorite='critique' if hors_domaine else 'elevee',
            )
    else:
        grid.ignore(cle, "Cohérence de la canonical non vérifiable sans l'adresse servie.")

    mots = signals.get('word_count')
    mots = mots if isinstance(mots, int) else 0
    if mots < _MOTS_COQUILLE:
        # An empty document is a rendering defect, charged once under Rendu
        # JavaScript. Charging it here too would double the same failure.
        grid.ignore(cle, "Contenu mince non évalué : la page ne rend presque aucun texte (voir Rendu JavaScript).")
    else:
        if mots >= _MOTS_MINCE:
            ratio = 1.0
        elif mots >= _MOTS_TRES_MINCE:
            ratio = 0.5
        else:
            ratio = 0.0
        grid.verifie(
            cle, 'contenu_mince', 3, ratio,
            constat=f"{mots} mots de contenu réel, hors menu et pied de page.",
            probleme=(
                f"{mots} mots de contenu réel (menu et pied de page exclus). Sous "
                f"{_MOTS_MINCE} mots, la page a peu de chances de répondre mieux que "
                "celles déjà classées."
            ),
            action="Étoffe la page jusqu'à couvrir la question au complet : le contexte, la réponse, les cas particuliers, le prix ou les étapes. Vise au minimum 300 mots utiles, davantage sur un guide.",
            priorite='elevee' if ratio == 0.0 else 'moyenne',
        )

    hreflang = signals.get('hreflang') or []
    if not hreflang:
        grid.ignore(cle, "Aucune balise hreflang : rien à vérifier de ce côté.")
    else:
        codes = {_texte(item.get('lang')).lower() for item in hreflang if isinstance(item, dict)}
        auto = False
        if ctx['url']:
            mienne = _cle_url(ctx['url'])
            auto = any(
                _cle_url(_texte(item.get('href'))) == mienne
                for item in hreflang if isinstance(item, dict)
            )
        else:
            auto = True
        defaut = 'x-default' in codes
        ratio = (0.6 if auto else 0.0) + (0.4 if defaut else 0.0)
        grid.verifie(
            cle, 'hreflang_complet', 2, ratio,
            constat=f"{len(hreflang)} balise(s) hreflang, autoréférence et x-default en place.",
            probleme=(
                ("La grappe hreflang n'inclut pas la page elle-même. "
                 if not auto else '')
                + ("Aucune balise x-default pour les visiteurs dont la langue "
                   "n'est pas couverte." if not defaut else '')
            ).strip(),
            action="Chaque version doit lister toutes les versions, elle comprise, et une ligne x-default doit désigner la page servie par défaut. Une grappe hreflang non réciproque est ignorée par Google.",
            priorite='moyenne',
        )

    noms = _params(ctx['parsed'])
    if ctx['parsed'] is None:
        grid.ignore(cle, "Paramètres d'URL non vérifiables sans l'adresse servie.")
    else:
        suivi = [
            nom for nom in noms
            if nom in _PARAMS_SUIVI or nom.startswith(_PREFIXES_SUIVI)
        ]
        grid.verifie(
            cle, 'parametres_suivi', 1, not suivi,
            constat='',
            probleme=(
                "L'adresse indexée porte des paramètres de suivi ("
                + ', '.join(sorted(set(suivi))) + ") : chaque variante devient une "
                "page de plus aux yeux de Google."
            ),
            action="Sers la page sur son adresse propre et garde les paramètres de campagne pour les liens sortants. Une canonical sans paramètre sur chaque variante règle le reste.",
            priorite='faible',
        )


# ---------------------------------------------------------------------------
# 3. Security
# ---------------------------------------------------------------------------

def _security(grid, ctx) -> None:
    cle = 'securite'
    parsed = ctx['parsed']

    if parsed is None:
        grid.ignore(cle, "HTTPS non vérifiable sans l'adresse servie.")
    else:
        https = (parsed.scheme or '').lower() == 'https'
        grid.verifie(
            cle, 'https', 5, https,
            constat="Page servie en HTTPS.",
            probleme="La page est servie en HTTP. Les navigateurs affichent « Non sécurisé » et HTTPS est un signal de classement confirmé.",
            action="Installe un certificat (Let's Encrypt est gratuit) et redirige tout le HTTP vers HTTPS en 301, une seule redirection par adresse.",
            priorite='critique',
        )

        images = [
            img for img in (ctx['signals'].get('images') or [])
            if isinstance(img, dict)
        ]
        if not https or not images:
            grid.ignore(cle, "Contenu mixte non évalué : page hors HTTPS ou sans image.")
        else:
            mixtes = [
                _texte(img.get('src')) for img in images
                if _texte(img.get('src')).lower().startswith('http://')
            ]
            grid.verifie(
                cle, 'contenu_mixte', 3, not mixtes,
                constat="Toutes les images sont chargées en HTTPS.",
                probleme=(
                    f"{len(mixtes)} image(s) chargée(s) en HTTP sur une page HTTPS. "
                    "Le navigateur les bloque ou signale la page."
                ),
                action="Réécris ces adresses en https:// ou en chemin relatif. Une seule ressource en HTTP suffit à faire tomber le cadenas.",
                priorite='elevee',
            )

    entetes = ctx['entetes']
    if entetes is None:
        grid.ignore(cle, "En-têtes HTTP non fournis : les en-têtes de sécurité n'ont pas été lus.")
    else:
        presents = [libelle for nom, libelle in ENTETES_SECURITE if entetes.get(nom)]
        manquants = [libelle for nom, libelle in ENTETES_SECURITE if not entetes.get(nom)]
        ratio = len(presents) / len(ENTETES_SECURITE)
        hsts = entetes.get('strict-transport-security', '')
        if 'preload' in hsts.lower():
            grid.constat(cle, "HSTS déclare « preload » : le domaine peut être soumis à la liste de préchargement des navigateurs.")
        grid.verifie(
            cle, 'entetes_securite', 3, ratio,
            constat="Les cinq en-têtes de sécurité sont présents.",
            probleme=(
                f"{len(manquants)} en-tête(s) de sécurité manquant(s) : "
                + ', '.join(manquants) + '.'
            ),
            action="Ajoute-les dans la configuration du serveur ou du CDN. Ce n'est pas un levier de classement : la page expérience n'est pas un système de classement, seuls les Core Web Vitals le sont. À faire une fois, puis à oublier.",
            priorite='faible',
        )

    markers = ctx['markers']
    if not markers:
        grid.ignore(cle, "Détournement du bouton Retour non vérifiable sans le HTML brut.")
    else:
        grid.verifie(
            cle, 'detournement_retour', 4, not markers['detournement_retour'],
            constat="Aucun script ne force l'historique vers l'avant.",
            probleme="Un script piège le bouton Retour : il écoute « popstate » et repousse l'historique vers l'avant. Google traite ce motif comme une pratique malveillante depuis juin 2026.",
            action="Retire ce script, y compris s'il vient d'une régie publicitaire ou d'une librairie tierce. C'est une violation des règles anti-spam, sanctionnée par action manuelle ou déclassement automatique.",
            priorite='critique',
        )


# ---------------------------------------------------------------------------
# 4. URL structure
# ---------------------------------------------------------------------------

_RE_NON_ASCII = re.compile(r'[^\x00-\x7F]')


def _url_structure(grid, ctx) -> None:
    cle = 'structure_url'
    parsed = ctx['parsed']
    url = ctx['url']

    if parsed is None:
        grid.ignore(cle, "Structure d'URL non vérifiable sans l'adresse servie.")
    else:
        chemin = parsed.path or '/'
        segments = [s for s in chemin.split('/') if s]
        dernier = segments[-1] if segments else ''

        grid.verifie(
            cle, 'longueur_url', 2, len(url) <= _URL_LONGUE,
            constat=f"Adresse de {len(url)} caractères.",
            probleme=f"Adresse de {len(url)} caractères, au-delà du seuil de {_URL_LONGUE}.",
            action="Raccourcis le slug : garde deux ou trois mots porteurs et coupe les niveaux de dossier qui ne servent qu'au classement interne.",
            priorite='faible',
        )

        noms = _params(parsed)
        contenu = [nom for nom in noms if nom in _PARAMS_CONTENU]
        grid.verifie(
            cle, 'parametres_contenu', 2, not contenu,
            constat="Adresse sans paramètre d'identifiant.",
            probleme=(
                "Le contenu est servi par paramètre ("
                + ', '.join(sorted(set(contenu)))
                + ") plutôt que par un chemin lisible."
            ),
            action="Active les permaliens en clair (/plomberie-laval/ plutôt que /?p=482) et redirige les anciennes adresses en 301. Un mot dans l'adresse aide autant l'internaute que le moteur.",
            priorite='moyenne',
        )

        grid.verifie(
            cle, 'casse_url', 1, not any(c.isupper() for c in chemin),
            constat='',
            probleme="Des majuscules dans le chemin de l'adresse. Un serveur qui distingue la casse sert alors deux pages identiques sur deux adresses.",
            action="Passe les adresses en minuscules et redirige les versions à majuscules en 301.",
            priorite='faible',
        )

        grid.verifie(
            cle, 'separateurs', 1, '_' not in dernier,
            constat='',
            probleme="Le slug utilise des tirets bas. Google lit le tiret comme un séparateur de mots, pas le tiret bas.",
            action="Remplace les tirets bas par des traits d'union et redirige l'ancienne adresse en 301.",
            priorite='faible',
        )

        encode = '%' in chemin or bool(_RE_NON_ASCII.search(chemin))
        grid.verifie(
            cle, 'caracteres_encodes', 2, not encode,
            constat="Chemin en caractères ASCII simples.",
            probleme="Le chemin contient des accents ou des caractères encodés (%C3%A9 et compagnie), illisibles dans un partage et fragiles au copier-coller.",
            action="Réécris le slug sans accent (« reparation-toiture » plutôt que « réparation-toiture ») et redirige l'ancienne adresse en 301.",
            priorite='moyenne',
        )

        grid.verifie(
            cle, 'profondeur', 1, len(segments) < _PROFONDEUR_MAX,
            constat=f"{len(segments)} niveau(x) de dossier.",
            probleme=f"{len(segments)} niveaux de dossier dans l'adresse. Une page importante devrait rester à trois clics de l'accueil.",
            action="Aplatis l'arborescence : les pages qui comptent méritent un chemin court, quitte à laisser les archives profondes.",
            priorite='faible',
        )

    _barre_finale(grid, ctx)


def _barre_finale(grid, ctx) -> None:
    """Trailing-slash consistency, read off the page's own internal links.

    One URL cannot show an inconsistency; the set of links the page emits can,
    and that set is exactly what a crawler will follow next.
    """
    brut = ctx['signals'].get('links')
    liens = (brut.get('internal') or []) if isinstance(brut, dict) else []
    avec, sans = 0, 0
    for lien in liens:
        if not isinstance(lien, dict):
            continue
        try:
            chemin = urlparse(_texte(lien.get('href'))).path or ''
        except ValueError:
            continue
        if not chemin or chemin == '/':
            continue
        dernier = chemin.rstrip('/').rsplit('/', 1)[-1]
        if '.' in dernier:
            continue
        if chemin.endswith('/'):
            avec += 1
        else:
            sans += 1

    total = avec + sans
    if total < 8:
        grid.ignore('structure_url', "Cohérence des barres obliques non évaluée : trop peu de liens internes.")
        return

    minorite = min(avec, sans)
    grid.verifie(
        'structure_url', 'barre_finale', 1, minorite / total <= 0.2,
        constat="Les liens internes utilisent la même convention de barre oblique finale.",
        probleme=(
            f"Les liens internes mélangent les deux conventions : {avec} avec barre "
            f"oblique finale, {sans} sans. Chaque page devient joignable par deux "
            "adresses."
        ),
        action="Choisis une convention, applique-la dans les menus et les liens de contenu, et redirige l'autre forme en 301.",
        priorite='faible',
    )


# ---------------------------------------------------------------------------
# 5. Mobile and page experience
# ---------------------------------------------------------------------------

def _mobile(grid, ctx) -> None:
    cle = 'mobile'
    markers = ctx['markers']
    if not markers:
        grid.ignore(cle, "Signaux mobiles non vérifiables sans le HTML brut.")
        return

    viewport = markers['viewport']
    if viewport is None:
        ratio = 0.0
    elif 'width=device-width' in viewport.replace(' ', ''):
        ratio = 1.0
    else:
        ratio = 0.5
    grid.verifie(
        cle, 'viewport', 6, ratio,
        constat="Balise viewport présente et réglée sur la largeur de l'appareil.",
        probleme=(
            "Aucune balise meta viewport. Le téléphone rend alors la page en largeur "
            "bureau et la réduit : texte minuscule, boutons impossibles à viser."
        ) if viewport is None else (
            f"La balise viewport (« {viewport} ») ne déclare pas width=device-width."
        ),
        action="Ajoute « <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\"> » dans le <head>. Googlebot indexe la version mobile en premier depuis 2024.",
        priorite='critique',
    )

    if viewport is None:
        grid.ignore(cle, "Blocage du zoom non évaluable sans balise viewport.")
    else:
        compact = viewport.replace(' ', '')
        bloque = (
            'user-scalable=no' in compact
            or 'user-scalable=0' in compact
            or 'maximum-scale=1' in compact
        )
        grid.verifie(
            cle, 'zoom_bloque', 2, not bloque,
            constat="Le zoom reste possible sur mobile.",
            probleme="La balise viewport interdit le zoom (user-scalable=no ou maximum-scale=1).",
            action="Retire user-scalable et maximum-scale. Bloquer le zoom exclut les gens qui en ont besoin pour lire, et n'apporte rien en retour.",
            priorite='moyenne',
        )

    grid.verifie(
        cle, 'interstitiel', 2, not markers['interstitiel'],
        constat="Aucun interstitiel promotionnel détecté dans le balisage.",
        probleme="Une couche promotionnelle (infolettre, rabais) est présente dans le balisage. Un interstitiel qui couvre le contenu à l'arrivée est un motif nommé par Google.",
        action="Vérifie ce que voit un visiteur mobile qui arrive de Google. Une bannière discrète passe, une fenêtre plein écran non. Les avis de témoins et les mentions légales restent acceptables.",
        priorite='moyenne',
    )

    replis = markers['blocs_replies']
    grid.verifie(
        cle, 'contenu_masque', 2, replis < 4,
        constat='',
        probleme=(
            f"{replis} blocs repliés (accordéons, onglets, « lire la suite ») sur la "
            "page. Le contenu qui demande un clic pour apparaître se qualifie moins "
            "bien."
        ),
        action="Laisse visible à l'arrivée ce qui répond à la question, et garde les accordéons pour le détail secondaire.",
        priorite='faible',
    )


# ---------------------------------------------------------------------------
# 6. Core Web Vitals
# ---------------------------------------------------------------------------

_LIBELLES_CWV = {
    'lcp': ('LCP (affichage du plus grand élément)', 's'),
    'inp': ('INP (réactivité aux interactions)', 'ms'),
    'cls': ('CLS (stabilité visuelle)', ''),
}
_ACTIONS_CWV = {
    'lcp': "Sers l'image de l'entête en format moderne et à la bonne taille, précharge-la, et retire le JavaScript qui bloque l'affichage. Le LCP se joue presque toujours sur la première image ou sur le temps de réponse du serveur.",
    'inp': "Découpe les tâches JavaScript longues et allège les scripts tiers (chat, pixels, cartes). L'INP mesure le délai entre le clic et la réaction visible.",
    'cls': "Réserve la place des images (attributs width et height) et des bannières, et évite d'injecter du contenu au-dessus de ce qui est déjà affiché.",
}
_POIDS_CWV = {'lcp': 4, 'inp': 3, 'cls': 3}


def _core_web_vitals(grid, ctx) -> None:
    cle = 'core_web_vitals'
    donnees = ctx['cwv']

    if not donnees:
        grid.ignore(cle, "Core Web Vitals non mesurés : aucune donnée PageSpeed ou CrUX fournie.")
        return
    if donnees.get('fid_fourni'):
        grid.constat(cle, "FID ignoré : la métrique a été remplacée par INP en mars 2024 et retirée des outils terrain en septembre 2024.")
    if donnees.get('terrain'):
        grid.constat(cle, "Données terrain : les seuils s'évaluent au 75e centile des visites réelles.")

    mesure = False
    for metrique in ('lcp', 'inp', 'cls'):
        valeur = donnees.get(metrique)
        libelle, unite = _LIBELLES_CWV[metrique]
        if valeur is None:
            grid.ignore(cle, f"{libelle} non fourni.")
            continue
        mesure = True
        bon, moyen = SEUILS_CWV[metrique]
        if valeur <= bon:
            ratio = 1.0
        elif valeur <= moyen:
            ratio = 0.5
        else:
            ratio = 0.0
        affiche = _nombre(valeur, metrique, unite)
        grid.verifie(
            cle, f'cwv_{metrique}', _POIDS_CWV[metrique], ratio,
            constat=f"{libelle} : {affiche}, dans la cible.",
            probleme=(
                f"{libelle} : {affiche}, la cible est "
                f"{_nombre(bon, metrique, unite)} ou moins."
            ),
            action=_ACTIONS_CWV[metrique],
            priorite='elevee' if ratio == 0.5 else 'critique',
        )

    if not mesure:
        grid.ignore(cle, "Aucune des trois métriques n'a été fournie.")


def _nombre(valeur: float, metrique: str, unite: str) -> str:
    """French display: comma decimal, unit spaced off the number."""
    if metrique == 'inp':
        texte = f'{valeur:.0f}'
    elif metrique == 'lcp':
        texte = f'{valeur:.1f}'.replace('.', ',')
    else:
        texte = f'{valeur:.2f}'.replace('.', ',')
    return f'{texte} {unite}' if unite else texte


# ---------------------------------------------------------------------------
# 7. Structured data
# ---------------------------------------------------------------------------

# Retired rich results. Their presence is not harmful, so the source says to
# report FAQPage at info level and never to recommend removal; only HowTo costs
# anything here, and barely, because it buys nothing since September 2023.
_TYPES_RETIRES = {
    'howto': "le résultat enrichi HowTo n'existe plus depuis septembre 2023",
    'faqpage': "Google a retiré le résultat enrichi FAQ le 7 mai 2026",
}


def _structured_data(grid, ctx) -> None:
    cle = 'donnees_structurees'
    signals = ctx['signals']
    schema = [bloc for bloc in (signals.get('schema') or []) if isinstance(bloc, dict)]
    types = [str(t) for t in (signals.get('schema_types') or []) if t]
    markers = ctx['markers']

    grid.verifie(
        cle, 'jsonld_present', 4, bool(schema),
        constat=f"{len(schema)} entité(s) JSON-LD : {', '.join(types[:6])}." if schema else '',
        probleme="Aucun balisage JSON-LD sur la page.",
        action="Ajoute au minimum le balisage qui décrit l'entité de la page : LocalBusiness pour un commerce, Article pour un texte, Service pour une offre, Product pour un produit. C'est ce que les moteurs et les réponses IA lisent en premier pour savoir de qui et de quoi parle la page.",
        priorite='elevee',
    )

    minuscules = {t.lower() for t in types}
    if 'faqpage' in minuscules:
        grid.constat(cle, "FAQPage détecté : " + _TYPES_RETIRES['faqpage']
                     + ". Rien à supprimer, le balisage reste lisible par les moteurs de réponse.")
    grid.verifie(
        cle, 'types_retires', 1, 'howto' not in minuscules,
        constat='',
        probleme="Balisage HowTo sur la page : " + _TYPES_RETIRES['howto'] + '.',
        action="Garde le contenu, laisse tomber le balisage HowTo : il ne produit plus rien dans les résultats. Un vrai contenu d'étapes bien titré fait le travail.",
        priorite='faible',
    )

    if not markers:
        grid.ignore(cle, "Microdonnées non vérifiables sans le HTML brut.")
    else:
        microdata_seul = (markers['microdata'] or markers['rdfa']) and not schema
        grid.verifie(
            cle, 'microdata_seul', 2, not microdata_seul,
            constat='',
            probleme="Le balisage est en microdonnées (itemscope) ou en RDFa, sans JSON-LD.",
            action="Republie le même balisage en JSON-LD dans un <script type=\"application/ld+json\">. C'est le format que Google recommande et le seul qui se maintient sans toucher au gabarit.",
            priorite='moyenne',
        )

    if not schema:
        grid.ignore(cle, "Validité des entités non évaluée : aucun JSON-LD à lire.")
    else:
        sans_type = [bloc for bloc in schema if not bloc.get('@type')]
        grid.verifie(
            cle, 'entites_typees', 1, not sans_type,
            constat="Toutes les entités JSON-LD déclarent un @type.",
            probleme=f"{len(sans_type)} entité(s) JSON-LD sans @type : elles ne décrivent rien.",
            action="Donne un @type à chaque entité, ou retire-la. Une entité sans type est ignorée par les moteurs.",
            priorite='moyenne',
        )


# ---------------------------------------------------------------------------
# 8. JavaScript rendering
# ---------------------------------------------------------------------------

def _js_rendering(grid, ctx) -> None:
    cle = 'rendu_javascript'
    signals = ctx['signals']
    markers = ctx['markers']
    mots = signals.get('word_count')
    mots = mots if isinstance(mots, int) else 0

    if mots >= _MOTS_PARTIELS:
        ratio = 1.0
    elif mots >= _MOTS_COQUILLE:
        ratio = 0.5
    else:
        ratio = 0.0
    grid.verifie(
        cle, 'contenu_servi', 5, ratio,
        constat=f"{mots} mots sont présents dans le HTML servi, avant toute exécution de JavaScript.",
        probleme=(
            f"Le HTML servi ne contient que {mots} mots lisibles. Le contenu est "
            "construit par JavaScript après le chargement."
        ),
        action="Rends le contenu principal côté serveur (SSR, génération statique ou prérendu). Google finit souvent par rendre le JavaScript, mais avec du retard, et les robots des moteurs de réponse IA ne le rendent pas du tout.",
        priorite='critique' if ratio == 0.0 else 'elevee',
    )

    if not markers:
        grid.ignore(cle, "Coquille applicative et poids des scripts non vérifiables sans le HTML brut.")
    else:
        grid.verifie(
            cle, 'coquille_spa', 3, not markers['coquille_spa'],
            constat="Aucun conteneur applicatif vide dans le HTML servi.",
            probleme="Le HTML servi contient un conteneur d'application vide (<div id=\"root\"></div> ou équivalent) : la page n'existe qu'après exécution du JavaScript.",
            action="Active le rendu serveur du cadriciel (Next, Nuxt, Angular Universal) ou publie une version prérendue. Les balises title, canonical, meta robots et le JSON-LD doivent en particulier être dans la réponse initiale.",
            priorite='critique',
        )

        octets = max(1, markers['octets'])
        part_scripts = markers['octets_scripts'] / octets
        lourd = part_scripts > 0.6 and mots < 400
        grid.verifie(
            cle, 'poids_scripts', 2, not lourd,
            constat=f"Les scripts en ligne occupent {round(part_scripts * 100)} % du document.",
            probleme=(
                f"Les scripts en ligne occupent {round(part_scripts * 100)} % du "
                f"document pour seulement {mots} mots de contenu."
            ),
            action="Sors les scripts en fichiers externes et retire ceux qui ne servent plus. Un document surtout fait de code repousse le contenu utile vers la fin, là où le plafond de 2 Mo de Googlebot devient un vrai risque.",
            priorite='moyenne',
        )

    statut = ctx['statut']
    try:
        statut = int(statut) if statut is not None else None
    except (TypeError, ValueError):
        statut = None
    if statut is None:
        grid.ignore(cle, "Code de réponse HTTP non fourni.")
    else:
        grid.verifie(
            cle, 'statut_http', 2, statut == 200,
            constat="La page répond 200.",
            probleme=(
                f"La page répond {statut}. Google n'exécute pas le JavaScript sur une "
                "réponse autre que 200 : tout ce qui est injecté par script reste "
                "invisible, et la page n'est de toute façon pas indexée."
            ),
            action="Sers un 200 sur les adresses qui doivent être indexées. Si la page a déménagé, réponds 301 vers la nouvelle adresse plutôt que d'afficher un message d'erreur en 200.",
            priorite='critique',
        )


# ---------------------------------------------------------------------------
# 9. IndexNow
# ---------------------------------------------------------------------------

def _indexnow(grid, ctx) -> None:
    cle = 'indexnow'
    etat = ctx['indexnow']
    if etat is None:
        grid.ignore(cle, "IndexNow non vérifié : l'accessibilité du fichier de clé n'a pas été testée.")
        return
    grid.verifie(
        cle, 'indexnow_actif', 1, bool(etat),
        constat="IndexNow est actif : le fichier de clé répond à la racine du domaine.",
        probleme="IndexNow n'est pas configuré : aucun fichier de clé accessible à la racine du domaine.",
        action="Publie le fichier « <clé>.txt » à la racine et soumets les nouvelles adresses à IndexNow. Google n'y participe pas, mais Bing indexe en quelques minutes, et Bing alimente ChatGPT Search, Copilot et DuckDuckGo.",
        priorite='moyenne',
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def score_technical(signals: dict, *, robots_txt: str = '', headers: dict = None,
                    url: str = '', html: str = '', http_status: int = None,
                    web_vitals: dict = None, indexnow_ready: bool = None) -> dict:
    """Score one served page against the nine technical categories.

    Args:
        signals: exactly the output of `html_parse.extract_seo_signals`.
        robots_txt: body of the site's robots.txt. Empty means it was not
            fetched, and the robots checks are skipped rather than failed: a
            missing file is reported by `sitemap_discovery`, and inferring
            absence from silence would invent a defect.
        headers: response headers of the page fetch. None skips the security
            headers.
        url: the address the body was served from.
        html: the raw response body, for the markup that is not content
            (viewport, script weight, empty app shell, document size).
        http_status: status code of that response.
        web_vitals: {'lcp', 'inp', 'cls', 'source'}. Seconds or milliseconds
            both work. Absent, Core Web Vitals leave the denominator.
        indexnow_ready: True when the `<key>.txt` file answers at the root,
            False when it was checked and missing, None when unknown.

    Returns:
        {
          'score': 0-100, or None when nothing at all could be measured,
          'categories': {cle: {'libelle', 'score', 'max', 'note', 'applicable',
                               'statut', 'constats', 'problemes',
                               'verifications', 'non_mesure'}},
          'recommandations': [{'categorie', 'libelle_categorie', 'code',
                               'priorite', 'points_recuperables', 'probleme',
                               'action'}] sorted by recoverable points,
          'bloquants': the subset of those findings that keep the page out of
                       the index entirely,
          'couverture': points of the 100 that were actually measured,
          'categories_non_mesurees': [cle, ...],
        }

    `score` is the ratio of earned points to measurable points, so a site is
    never charged for a category nobody could look at. `couverture` says how
    much of the grid the inputs supported, which is what tells a caller whether
    the number deserves to be shown. A non-empty `bloquants` outranks both: a
    page under noindex or behind a `Disallow: /` still collects points on the
    other categories, and showing that number without the blocker beside it
    would read as "your site is halfway fine" when it is invisible.

    Never raises on partial input: every field is optional and a missing one
    removes its checks instead of failing the run.
    """
    ctx = _context(
        signals if isinstance(signals, dict) else {},
        robots_txt, headers, url, html, http_status, web_vitals, indexnow_ready,
    )
    grid = _Grid()
    _crawlability(grid, ctx)
    _indexability(grid, ctx)
    _security(grid, ctx)
    _url_structure(grid, ctx)
    _mobile(grid, ctx)
    _core_web_vitals(grid, ctx)
    _structured_data(grid, ctx)
    _js_rendering(grid, ctx)
    _indexnow(grid, ctx)
    return grid.resultat()
