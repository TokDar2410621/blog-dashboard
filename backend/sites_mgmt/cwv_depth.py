"""Core Web Vitals in depth: field history, LCP decomposition, preload signals.

Porte depuis claude-seo v2.2.4 `scripts/crux_history.py`, `scripts/lcp_subparts.py`
et `scripts/preload_check.py`.
Copyright (c) 2025 Daniel Agrici (AgriciDaniel). MIT.
https://github.com/AgriciDaniel/claude-seo

Three upstream CLI scripts merged into one pure module. The trend detector gains
a noise floor per unit, because upstream's flat 5 % rule reads a 0,005 move on
CLS as a degradation, and it gains threshold-crossing detection, which is the
event a client acts on ("tu es sorti du vert la semaine du 12 janvier"). The LCP
decomposition reads the four phases out of a PageSpeed payload the caller already
holds instead of firing a second CrUX call, and it ranks the subparts against
web.dev's ideal budget (40/10/40/10) instead of upstream's flat "more than 40 %
of LCP", which crowns TTFB at 41 % while a render delay sitting at three times
its own budget is the real culprit. The preload audit consumes
`html_parse.extract_seo_signals` so it can flag the lazy-loaded hero image, the
most common LCP killer on the WordPress sites Gridar audits, and it reads French
Lighthouse phase labels since PageSpeed answers in the locale it is asked in.

Pure data in, pure data out apart from the one CrUX call: no ORM, no view, no
Django import. Display strings are French, dict keys stay unaccented ASCII
because they are API field names.
"""
from __future__ import annotations

import json
import re
import unicodedata
from urllib.parse import urlparse

import requests

from .url_safety import validate_url

__all__ = [
    'CRUX_HISTORY_ENDPOINT',
    'SEUILS_CWV',
    'SOUS_PARTIES_LCP',
    'SEVERITE_RANG',
    'fetch_crux_history',
    'analyze_lcp_subparts',
    'check_preload_signals',
]


# Google's own host, spelled here and nowhere else. `url_safety.safe_get` exists
# for URLs a client typed; it would spend a DNS round trip and a redirect walk on
# a constant we control. The caller-supplied part of this call is the payload
# body, and it is validated at parse time before it goes out.
CRUX_HISTORY_ENDPOINT = (
    'https://chromeuxreport.googleapis.com/v1/records:queryHistoryRecord'
)

_TIMEOUT_CRUX = 25

# Insertion order is the reporting order: the three ranking signals first, then
# the two diagnostic ones that explain them.
SEUILS_CWV = {
    'largest_contentful_paint': {
        'cle': 'lcp',
        'libelle': 'LCP (affichage du plus grand élément)',
        'unite': 'ms',
        'bon': 2500,
        'mauvais': 4000,
    },
    'interaction_to_next_paint': {
        'cle': 'inp',
        'libelle': 'INP (réactivité aux clics)',
        'unite': 'ms',
        'bon': 200,
        'mauvais': 500,
    },
    'cumulative_layout_shift': {
        'cle': 'cls',
        'libelle': 'CLS (stabilité visuelle)',
        'unite': '',
        'bon': 0.1,
        'mauvais': 0.25,
    },
    'first_contentful_paint': {
        'cle': 'fcp',
        'libelle': 'FCP (premier affichage)',
        'unite': 'ms',
        'bon': 1800,
        'mauvais': 3000,
    },
    'experimental_time_to_first_byte': {
        'cle': 'ttfb',
        'libelle': 'TTFB (réponse du serveur)',
        'unite': 'ms',
        'bon': 800,
        'mauvais': 1800,
    },
}

LIBELLES_VERDICT = {
    'bon': 'Bon',
    'a_ameliorer': 'À améliorer',
    'mauvais': 'Mauvais',
}

LIBELLES_TENDANCE = {
    'amelioration': 'En amélioration',
    'degradation': 'En dégradation',
    'stable': 'Stable',
    'donnees_insuffisantes': 'Historique trop court',
}

# CrUX rounds its p75 coarsely, so a swing of a few dozen milliseconds is
# rounding, not movement. Upstream's 5 % rule alone reads a 0,004 drift on a CLS
# of 0,08 as an improvement and tells the client something happened.
_PLANCHER_BRUIT = {'ms': 60.0, '': 0.01}
_VARIATION_MINIMALE = 5.0

# Four points a side is upstream's window. Six total points is the floor here
# instead of upstream's eight, because a site that just became eligible has six
# weeks of history, and "pas assez de données" on a visible degradation is worse
# than a hedged verdict.
_FENETRE_TENDANCE = 4
_POINTS_MINIMUM = 6

# Findings and alerts share the severity vocabulary of gbp_lint and drift_rules,
# so one dashboard component renders every list Gridar produces.
SEVERITE_RANG = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3, 'info': 4}


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _plat(valeur) -> str:
    """Lowercase, accent-free, whitespace-collapsed form used by the matchers."""
    if not valeur:
        return ''
    texte = str(valeur).replace('\u2019', "'").replace('\u02bc', "'")
    texte = unicodedata.normalize('NFD', texte)
    texte = ''.join(c for c in texte if unicodedata.category(c) != 'Mn')
    return ' '.join(texte.lower().split())


def _nombre(valeur, decimal: bool = False):
    """Coerce a CrUX or Lighthouse value to a number, None when unusable.

    CLS arrives string-encoded and empty weeks arrive as the string "NaN", which
    float() accepts happily and every later comparison then silently loses.
    """
    if valeur is None or isinstance(valeur, bool):
        return None
    try:
        flottant = float(valeur)
    except (TypeError, ValueError):
        return None
    if flottant != flottant:
        return None
    return flottant if decimal else int(round(flottant))


def _moyenne(valeurs):
    return sum(valeurs) / len(valeurs) if valeurs else None


def _masquer_cle(texte, api_key: str) -> str:
    """Keep an API key out of a message that ends up in a log or a dashboard."""
    sortie = str(texte)
    if api_key and len(api_key) >= 8:
        sortie = sortie.replace(api_key, 'CLE_API_MASQUEE')
    return sortie


def _verdict(nom_metrique: str, valeur) -> str | None:
    seuils = SEUILS_CWV.get(nom_metrique)
    if seuils is None or valeur is None:
        return None
    if valeur <= seuils['bon']:
        return 'bon'
    if valeur <= seuils['mauvais']:
        return 'a_ameliorer'
    return 'mauvais'


def _valeur_lisible(valeur, unite: str) -> str:
    """Quebec formatting: comma decimal, and seconds once past a thousand."""
    if valeur is None:
        return 'inconnu'
    if unite == 'ms':
        if valeur >= 1000:
            return ('%.2f' % (valeur / 1000)).replace('.', ',') + ' s'
        return '%d ms' % round(valeur)
    return ('%.3f' % valeur).rstrip('0').rstrip('.').replace('.', ',')


def _alerte(code: str, severite: str, message: str, **extra) -> dict:
    alerte = {'code': code, 'severity': severite, 'message': message}
    alerte.update(extra)
    return alerte


# ---------------------------------------------------------------------------
# CrUX History
# ---------------------------------------------------------------------------

_FORM_FACTORS = ('PHONE', 'DESKTOP', 'TABLET')


def _normaliser_cible(url_or_origin: str) -> str:
    """Add the scheme Gridar's stored domains lack, and drop the fragment."""
    cible = (url_or_origin or '').strip()
    if not cible:
        return ''
    if '://' not in cible:
        cible = 'https://' + cible.lstrip('/')
    return cible.split('#', 1)[0]


def _corps_requete(cible: str, form_factor: str) -> tuple[dict, str]:
    """Build the CrUX body and say whether it asks at origin or at URL level.

    A bare domain has to be asked as an origin: CrUX keeps a URL record only for
    pages with their own traffic volume, and most pages of a Quebec small
    business have none, while the origin almost always answers.
    """
    parsed = urlparse(cible)
    au_niveau_origine = parsed.path in ('', '/') and not parsed.query
    if au_niveau_origine:
        corps = {'origin': '%s://%s' % (parsed.scheme, parsed.netloc)}
        granularite = 'origine'
    else:
        corps = {'url': cible}
        granularite = 'url'
    if form_factor:
        corps['formFactor'] = form_factor
    return corps, granularite


def _serie_percentiles(donnees: dict, decimal: bool) -> list:
    brut = (donnees.get('percentilesTimeseries') or {}).get('p75s') or []
    return [_nombre(valeur, decimal) for valeur in brut]


def _series_histogramme(donnees: dict) -> dict:
    """Weekly share of visits in each of the three CrUX buckets, in percent."""
    bacs = donnees.get('histogramTimeseries') or []
    parts = {'bon_pct': [], 'a_ameliorer_pct': [], 'mauvais_pct': []}
    for index, nom in enumerate(('bon_pct', 'a_ameliorer_pct', 'mauvais_pct')):
        if index >= len(bacs):
            continue
        for densite in (bacs[index].get('densities') or []):
            valeur = _nombre(densite, decimal=True)
            parts[nom].append(None if valeur is None else round(valeur * 100, 1))
    return parts


def _tendance(p75: list, unite: str) -> dict:
    """Compare the last weeks to the first ones, with a floor under the noise."""
    valides = [valeur for valeur in p75 if valeur is not None]
    if len(valides) < _POINTS_MINIMUM:
        return {
            'direction': 'donnees_insuffisantes',
            'libelle': LIBELLES_TENDANCE['donnees_insuffisantes'],
            'variation_pct': None,
            'debut': None,
            'fin': None,
            'points': len(valides),
        }

    fenetre = min(_FENETRE_TENDANCE, len(valides) // 2)
    debut = _moyenne(valides[:fenetre])
    fin = _moyenne(valides[-fenetre:])
    ecart = fin - debut
    variation = 0.0 if debut == 0 else (ecart / debut) * 100

    plancher = _PLANCHER_BRUIT.get(unite, 0.0)
    if abs(ecart) < plancher or abs(variation) < _VARIATION_MINIMALE:
        direction = 'stable'
    elif ecart < 0:
        # Every Core Web Vital is better when smaller, CLS included.
        direction = 'amelioration'
    else:
        direction = 'degradation'

    decimales = 3 if unite == '' else 0
    return {
        'direction': direction,
        'libelle': LIBELLES_TENDANCE[direction],
        'variation_pct': round(variation, 1),
        'debut': round(debut, decimales) if decimales else round(debut),
        'fin': round(fin, decimales) if decimales else round(fin),
        'points': len(valides),
        'fenetre': fenetre,
    }


def _franchissement(nom_metrique: str, p75: list, semaines: list) -> dict | None:
    """Last week where the metric changed zone, the date a client asks for."""
    verdicts = [
        (index, _verdict(nom_metrique, valeur))
        for index, valeur in enumerate(p75)
        if valeur is not None
    ]
    if len(verdicts) < 2:
        return None
    actuel = verdicts[-1][1]
    for position in range(len(verdicts) - 2, -1, -1):
        if verdicts[position][1] == actuel:
            continue
        index = verdicts[position + 1][0]
        semaine = semaines[index]['fin'] if index < len(semaines) else None
        return {
            'de': verdicts[position][1],
            'vers': actuel,
            'semaine': semaine,
            'sortie_du_vert': verdicts[position][1] == 'bon' and actuel != 'bon',
        }
    return None


def _date_crux(bloc: dict) -> str:
    annee = bloc.get('year')
    if not annee:
        return ''
    return '%04d-%02d-%02d' % (int(annee), int(bloc.get('month') or 0),
                               int(bloc.get('day') or 0))


def _alertes_metrique(metrique: dict) -> list:
    alertes = []
    cle = metrique['cle']
    libelle = metrique['libelle']
    unite = metrique['unite']
    tendance = metrique['tendance']

    if metrique['verdict'] == 'mauvais':
        alertes.append(_alerte(
            'cwv_hors_seuil', 'critical',
            "%s à %s chez les vrais visiteurs, au-delà du seuil d'échec de "
            "Google (%s). Cette page perd du classement sur mobile."
            % (libelle, metrique['valeur_lisible'],
               _valeur_lisible(metrique['seuil_mauvais'], unite)),
            metrique=cle,
        ))
    elif metrique['verdict'] == 'a_ameliorer':
        alertes.append(_alerte(
            'cwv_zone_orange', 'medium',
            "%s à %s : dans la zone orange, sous le seuil du vert (%s)."
            % (libelle, metrique['valeur_lisible'],
               _valeur_lisible(metrique['seuil_bon'], unite)),
            metrique=cle,
        ))

    if tendance['direction'] == 'degradation':
        alertes.append(_alerte(
            'cwv_degradation', 'high',
            "%s s'est dégradé de %s %% sur les %s semaines mesurées (%s vers %s)."
            % (libelle, round(abs(tendance['variation_pct'])), tendance['points'],
               _valeur_lisible(tendance['debut'], unite),
               _valeur_lisible(tendance['fin'], unite)),
            metrique=cle,
        ))

    franchissement = metrique.get('franchissement')
    if franchissement and franchissement.get('sortie_du_vert'):
        alertes.append(_alerte(
            'cwv_sortie_du_vert', 'high',
            "%s est sorti du vert la semaine terminée le %s. Cherche ce qui a "
            "changé sur le site à cette date."
            % (libelle, franchissement.get('semaine') or 'inconnue'),
            metrique=cle,
        ))
    return alertes


def _resume(resultat: dict) -> str:
    metriques = resultat['metriques']
    if not metriques:
        return "Aucune métrique CrUX exploitable pour cette cible."
    mauvaises = [m['libelle'] for m in metriques.values() if m['verdict'] == 'mauvais']
    degradees = [
        m['libelle'] for m in metriques.values()
        if m['tendance']['direction'] == 'degradation'
    ]
    portee = 'le domaine' if resultat['granularite'] == 'origine' else 'cette page'
    phrases = [
        "%s semaines de données terrain pour %s (%s métriques)."
        % (resultat['nb_semaines'], portee, len(metriques))
    ]
    if mauvaises:
        phrases.append("Hors seuil : %s." % ', '.join(mauvaises))
    if degradees:
        phrases.append("En dégradation : %s." % ', '.join(degradees))
    if not mauvaises and not degradees:
        phrases.append("Rien hors seuil et rien en dégradation sur la période.")
    return ' '.join(phrases)


def fetch_crux_history(url_or_origin: str, api_key: str,
                       *, form_factor: str = 'PHONE') -> dict:
    """Read up to 25 weeks of real-user Core Web Vitals from the CrUX History API.

    Args:
        url_or_origin: a page URL, or a domain, in which case the query runs at
            origin level. A bare domain gets the https scheme added.
        api_key: a Google API key. Gridar's PAGESPEED_API_KEY opens CrUX too, at
            no extra cost and against a separate quota.
        form_factor: 'PHONE', 'DESKTOP' or 'TABLET'. Anything else, 'ALL'
            included, asks for every form factor at once.

    Returns a dict with `cible`, `granularite` ('origine' or 'url'), `semaines`,
    `metriques` keyed by short name (lcp, inp, cls, fcp, ttfb), `alertes`,
    `resume` and `erreur`. Never raises: a network failure, a bad key or a page
    CrUX does not cover comes back as a French `erreur` with empty series.
    """
    facteur = (form_factor or '').strip().upper()
    if facteur not in _FORM_FACTORS:
        facteur = ''

    resultat = {
        'cible': (url_or_origin or '').strip(),
        'granularite': None,
        'form_factor': facteur or 'ALL',
        'semaines': [],
        'nb_semaines': 0,
        'metriques': {},
        'alertes': [],
        'resume': '',
        'erreur': None,
    }

    cle = (api_key or '').strip()
    if not cle:
        resultat['erreur'] = (
            "Clé API Google absente : configure PAGESPEED_API_KEY pour lire "
            "l'historique CrUX."
        )
        return resultat

    cible = _normaliser_cible(url_or_origin)
    if not cible or not validate_url(cible):
        resultat['erreur'] = "URL invalide : donne une adresse http ou https publique."
        return resultat
    resultat['cible'] = cible

    corps, granularite = _corps_requete(cible, facteur)
    resultat['granularite'] = granularite

    try:
        # The key travels in a header, not in the query string: an exception
        # message or a retry log would otherwise carry the credential out of
        # the process.
        reponse = requests.post(
            CRUX_HISTORY_ENDPOINT,
            headers={'Content-Type': 'application/json', 'X-Goog-Api-Key': cle},
            json=corps,
            timeout=_TIMEOUT_CRUX,
        )
    except requests.exceptions.Timeout:
        resultat['erreur'] = "L'API CrUX n'a pas répondu dans le délai imparti."
        return resultat
    except requests.exceptions.RequestException as exc:
        resultat['erreur'] = "Appel à l'API CrUX impossible : %s" % _masquer_cle(exc, cle)
        return resultat

    statut = getattr(reponse, 'status_code', 0)
    if statut == 404:
        if granularite == 'url':
            resultat['erreur'] = (
                "Aucun historique CrUX pour cette page : elle reçoit trop peu de "
                "visites Chrome. Réessaie au niveau du domaine."
            )
        else:
            resultat['erreur'] = (
                "Aucun historique CrUX pour ce domaine : il reçoit trop peu de "
                "visites Chrome pour figurer dans les données terrain de Google."
            )
        return resultat
    if statut == 429:
        resultat['erreur'] = (
            "Quota CrUX dépassé (150 requêtes par minute, partagé). Réessaie dans "
            "une minute."
        )
        return resultat
    if statut != 200:
        detail = ''
        try:
            detail = ((reponse.json() or {}).get('error') or {}).get('message') or ''
        except (ValueError, AttributeError, TypeError):
            detail = ''
        resultat['erreur'] = _masquer_cle(
            "L'API CrUX a répondu HTTP %s%s"
            % (statut, (' : ' + detail) if detail else '.'),
            cle,
        )
        return resultat

    try:
        donnees = reponse.json() or {}
    except ValueError:
        resultat['erreur'] = "Réponse CrUX illisible (JSON invalide)."
        return resultat

    enregistrement = donnees.get('record') or {}
    for periode in (enregistrement.get('collectionPeriods') or []):
        resultat['semaines'].append({
            'debut': _date_crux(periode.get('firstDate') or {}),
            'fin': _date_crux(periode.get('lastDate') or {}),
        })
    resultat['nb_semaines'] = len(resultat['semaines'])

    metriques_brutes = enregistrement.get('metrics') or {}
    for nom, seuils in SEUILS_CWV.items():
        donnees_metrique = metriques_brutes.get(nom)
        if not isinstance(donnees_metrique, dict):
            continue
        p75 = _serie_percentiles(donnees_metrique, decimal=seuils['unite'] == '')
        connus = [valeur for valeur in p75 if valeur is not None]
        if not connus:
            continue
        p75_actuel = connus[-1]
        metrique = {
            'cle': seuils['cle'],
            'metrique_crux': nom,
            'libelle': seuils['libelle'],
            'unite': seuils['unite'],
            'seuil_bon': seuils['bon'],
            'seuil_mauvais': seuils['mauvais'],
            'p75': p75,
            'p75_actuel': p75_actuel,
            'valeur_lisible': _valeur_lisible(p75_actuel, seuils['unite']),
            'verdict': _verdict(nom, p75_actuel),
            'tendance': _tendance(p75, seuils['unite']),
            'franchissement': _franchissement(nom, p75, resultat['semaines']),
        }
        metrique['libelle_verdict'] = LIBELLES_VERDICT.get(metrique['verdict'], '')
        metrique.update(_series_histogramme(donnees_metrique))
        metrique['part_bonne_actuelle'] = next(
            (valeur for valeur in reversed(metrique['bon_pct']) if valeur is not None),
            None,
        )
        resultat['metriques'][seuils['cle']] = metrique

    for metrique in resultat['metriques'].values():
        resultat['alertes'].extend(_alertes_metrique(metrique))
    resultat['alertes'].sort(key=lambda item: SEVERITE_RANG.get(item['severity'], 9))

    if not resultat['metriques']:
        resultat['erreur'] = (
            "CrUX a répondu sans aucune métrique exploitable pour cette cible."
        )
    resultat['resume'] = _resume(resultat)
    return resultat


# ---------------------------------------------------------------------------
# LCP subparts
# ---------------------------------------------------------------------------

# web.dev's ideal split of an LCP: the share each phase holds on a page that is
# not the problem. Upstream flags any subpart above 40 % of the total, which
# flags a healthy TTFB and lets a render delay at three times its budget pass.
SOUS_PARTIES_LCP = (
    ('ttfb', 'Réponse du serveur (TTFB)', 0.40),
    ('delai_ressource', "Délai avant le chargement de la ressource", 0.10),
    ('chargement_ressource', 'Chargement de la ressource', 0.40),
    ('rendu', "Délai de rendu de l'élément", 0.10),
)

# Below this excess over budget, the split is balanced enough that naming a
# culprit would send the client fixing the wrong thing.
_EXCES_SIGNIFICATIF = 0.05

_METRIQUES_TERRAIN = {
    'largest_contentful_paint_image_time_to_first_byte': 'ttfb',
    'largest_contentful_paint_image_resource_load_delay': 'delai_ressource',
    'largest_contentful_paint_image_resource_load_duration': 'chargement_ressource',
    'largest_contentful_paint_image_element_render_delay': 'rendu',
}

_ACTIONS_LCP = {
    'ttfb': (
        "Le serveur met trop de temps à répondre. Active la mise en cache de "
        "pages chez ton hébergeur, mets un CDN devant le site, et regarde les "
        "extensions qui s'exécutent à chaque requête. Cible : moins de 800 ms."
    ),
    'delai_ressource': (
        "Le navigateur découvre l'image trop tard. Retire le chargement différé "
        "sur l'image du haut de page, ajoute-lui fetchpriority=\"high\", et "
        "sors-la du carrousel ou du script qui la charge après coup."
    ),
    'chargement_ressource': (
        "L'image du haut de page est trop lourde. Sers-la en WebP ou en AVIF, "
        "génère plusieurs tailles avec srcset, et fixe des dimensions qui "
        "correspondent à l'affichage réel sur mobile."
    ),
    'rendu': (
        "L'image est chargée mais l'affichage reste bloqué. Réduis le CSS et le "
        "JavaScript bloquants avant le premier rendu, ajoute font-display: swap "
        "aux polices, et repousse les scripts tiers après le chargement."
    ),
}


def _cle_phase(libelle) -> str | None:
    """Map a Lighthouse phase label to a subpart key, English or French.

    PageSpeed answers in the locale it is asked in and Gridar asks in French, so
    matching the English labels alone would decompose nothing in production.
    Order matters: "Load Delay" and "Délai de chargement" hold both words.
    """
    plat = _plat(libelle)
    if not plat:
        return None
    if ('ttfb' in plat or 'first byte' in plat or 'premier octet' in plat
            or 'reponse du serveur' in plat or 'temps de reponse' in plat):
        return 'ttfb'
    if 'render' in plat or 'rendu' in plat or 'affichage' in plat:
        return 'rendu'
    if 'delay' in plat or 'delai' in plat or 'attente' in plat:
        return 'delai_ressource'
    if 'load' in plat or 'chargement' in plat or 'duree' in plat or 'temps' in plat:
        return 'chargement_ressource'
    return None


def _lignes_phases(noeud, sortie: list, profondeur: int = 0) -> None:
    """Collect the {phase, timing} rows wherever Lighthouse nested them.

    The audit shape moved between Lighthouse versions (a bare table, then a list
    holding two tables), so the rows are searched for rather than addressed by
    a fixed path that a version bump would break.
    """
    if profondeur > 8 or len(sortie) >= 12:
        return
    if isinstance(noeud, dict):
        if 'phase' in noeud and 'timing' in noeud:
            sortie.append(noeud)
            return
        for valeur in noeud.values():
            _lignes_phases(valeur, sortie, profondeur + 1)
    elif isinstance(noeud, list):
        for valeur in noeud[:60]:
            _lignes_phases(valeur, sortie, profondeur + 1)


def _noeud_element(noeud, profondeur: int = 0):
    """Find the DOM node Lighthouse identified as the LCP element."""
    if profondeur > 8:
        return None
    if isinstance(noeud, dict):
        candidat = noeud.get('node')
        if isinstance(candidat, dict) and (candidat.get('selector')
                                           or candidat.get('snippet')):
            return candidat
        for valeur in noeud.values():
            trouve = _noeud_element(valeur, profondeur + 1)
            if trouve:
                return trouve
    elif isinstance(noeud, list):
        for valeur in noeud[:60]:
            trouve = _noeud_element(valeur, profondeur + 1)
            if trouve:
                return trouve
    return None


def _valeur_terrain(entree) -> float | None:
    """Read a p75 out of either PSI's loadingExperience or a raw CrUX record."""
    if not isinstance(entree, dict):
        return None
    valeur = _nombre(entree.get('percentile'), decimal=True)
    if valeur is not None:
        return valeur
    percentiles = entree.get('percentiles')
    if isinstance(percentiles, dict):
        return _nombre(percentiles.get('p75'), decimal=True)
    return None


def _sous_parties_terrain(metriques) -> dict:
    if not isinstance(metriques, dict):
        return {}
    trouvees = {}
    for nom, entree in metriques.items():
        cle = _METRIQUES_TERRAIN.get(str(nom).lower())
        if not cle:
            continue
        valeur = _valeur_terrain(entree)
        if valeur is not None:
            trouvees[cle] = valeur
    return trouvees


def _sous_parties_labo(audits: dict):
    audit = audits.get('largest-contentful-paint-element')
    if not isinstance(audit, dict):
        return {}, None
    lignes = []
    _lignes_phases(audit.get('details'), lignes)
    trouvees = {}
    for ligne in lignes:
        cle = _cle_phase(ligne.get('phase'))
        valeur = _nombre(ligne.get('timing'), decimal=True)
        if cle and valeur is not None and cle not in trouvees:
            trouvees[cle] = valeur
    return trouvees, _noeud_element(audit.get('details'))


def _sections_psi(psi_payload):
    """Split a payload into (lighthouse, field metrics, CrUX record metrics).

    Accepts the full PageSpeed response, a bare lighthouseResult, or a CrUX
    queryRecord answer, because all three reach this backend from different call
    sites and none of them is worth a second round trip just to be reshaped.
    """
    if not isinstance(psi_payload, dict):
        return {}, {}, {}
    lighthouse = psi_payload.get('lighthouseResult')
    if not isinstance(lighthouse, dict):
        lighthouse = psi_payload if 'audits' in psi_payload else {}
    experience = psi_payload.get('loadingExperience')
    terrain = experience.get('metrics') if isinstance(experience, dict) else {}
    enregistrement = psi_payload.get('record')
    crux = enregistrement.get('metrics') if isinstance(enregistrement, dict) else {}
    return lighthouse, (terrain or {}), (crux or {})


def analyze_lcp_subparts(psi_payload) -> dict:
    """Break a slow LCP into its four phases and name the one that dominates.

    Takes a PageSpeed Insights response the caller already fetched. Field data
    wins over lab data when the payload carries the CrUX subparts, since that is
    what Google ranks on; otherwise the Lighthouse phase table is used and
    `source` says so.

    Returns `lcp_ms`, `verdict`, `sous_parties` (each with its share and its
    budget), `dominante`, a French `diagnostic`, the `actions` to take, and the
    LCP `element` when Lighthouse identified it. Never raises: a payload with no
    LCP audit comes back with `source` at 'aucune' and an `erreur`.
    """
    resultat = {
        'source': 'aucune',
        'url': None,
        'strategie': None,
        'lcp_ms': None,
        'lcp_lisible': None,
        'verdict': None,
        'libelle_verdict': None,
        'lcp_terrain_ms': None,
        'verdict_terrain': None,
        'sous_parties': [],
        'dominante': None,
        'libelle_dominante': None,
        'diagnostic': '',
        'actions': [],
        'element': None,
        'notes': [],
        'erreur': None,
    }

    lighthouse, terrain, crux = _sections_psi(psi_payload)
    if not lighthouse and not terrain and not crux:
        resultat['erreur'] = (
            "Charge PageSpeed illisible : passe la réponse complète de l'API "
            "PageSpeed Insights."
        )
        return resultat

    resultat['url'] = (lighthouse.get('finalUrl') or lighthouse.get('requestedUrl')
                       or psi_payload.get('id'))
    reglages = lighthouse.get('configSettings')
    if isinstance(reglages, dict):
        resultat['strategie'] = (reglages.get('formFactor')
                                 or reglages.get('emulatedFormFactor'))

    audits = lighthouse.get('audits')
    audits = audits if isinstance(audits, dict) else {}

    lcp_terrain = _valeur_terrain(terrain.get('LARGEST_CONTENTFUL_PAINT_MS'))
    if lcp_terrain is None:
        lcp_terrain = _valeur_terrain(crux.get('largest_contentful_paint'))
    if lcp_terrain is not None:
        resultat['lcp_terrain_ms'] = round(lcp_terrain)
        resultat['verdict_terrain'] = _verdict('largest_contentful_paint', lcp_terrain)

    parts_terrain = _sous_parties_terrain(terrain) or _sous_parties_terrain(crux)
    parts_labo, element = _sous_parties_labo(audits)

    # Three of the four phases is enough to name a culprit; below that the field
    # breakdown is too partial and the lab table says more.
    if len(parts_terrain) >= 3:
        parts = parts_terrain
        resultat['source'] = 'terrain'
        total = lcp_terrain
    elif parts_labo:
        parts = parts_labo
        resultat['source'] = 'labo'
        total = _nombre((audits.get('largest-contentful-paint') or {}).get('numericValue'),
                        decimal=True)
        resultat['notes'].append(
            "Décomposition de laboratoire (une seule mesure simulée). Google "
            "classe sur les données terrain, qui peuvent différer."
        )
    else:
        resultat['erreur'] = (
            "Aucune décomposition du LCP dans cette réponse : l'audit "
            "largest-contentful-paint-element est absent."
        )
        if resultat['lcp_terrain_ms'] is not None:
            resultat['notes'].append(
                "LCP terrain connu (%s) mais sans détail par phase."
                % _valeur_lisible(resultat['lcp_terrain_ms'], 'ms')
            )
        return resultat

    if not total or total <= 0:
        total = sum(parts.values())
        if total > 0:
            resultat['notes'].append(
                "LCP total absent de la réponse : reconstitué en additionnant "
                "les phases connues."
            )
    if not total or total <= 0:
        resultat['erreur'] = "LCP introuvable dans cette réponse PageSpeed."
        return resultat

    resultat['lcp_ms'] = round(total)
    resultat['lcp_lisible'] = _valeur_lisible(total, 'ms')
    resultat['verdict'] = _verdict('largest_contentful_paint', total)
    resultat['libelle_verdict'] = LIBELLES_VERDICT.get(resultat['verdict'], '')

    manquantes = []
    for cle, libelle, budget in SOUS_PARTIES_LCP:
        valeur = parts.get(cle)
        if valeur is None:
            manquantes.append(libelle)
            continue
        part = valeur / total
        resultat['sous_parties'].append({
            'cle': cle,
            'libelle': libelle,
            'ms': round(valeur),
            'lisible': _valeur_lisible(valeur, 'ms'),
            'part': round(part, 3),
            'part_cible': budget,
            'exces': round(part - budget, 3),
            'hors_budget': part - budget > _EXCES_SIGNIFICATIF,
        })
    if manquantes:
        resultat['notes'].append(
            "Phases absentes de la réponse : %s. Cela arrive quand le plus grand "
            "élément est du texte plutôt qu'une image." % ', '.join(manquantes)
        )

    # The culprit is the phase furthest over its own budget, not the largest one.
    # A TTFB at 41 % sits inside its 40 % budget while a render delay at 30 % is
    # three times its own, and upstream's flat rule names the first.
    candidats = [part for part in resultat['sous_parties']
                 if part['exces'] > _EXCES_SIGNIFICATIF]
    if candidats:
        candidats.sort(key=lambda part: -part['exces'])
        dominante = candidats[0]
        resultat['dominante'] = dominante['cle']
        resultat['libelle_dominante'] = dominante['libelle']
        resultat['actions'] = [_ACTIONS_LCP[part['cle']] for part in candidats]
        resultat['diagnostic'] = (
            "LCP de %s (%s). %s occupe %s %% du temps alors que la cible est "
            "%s %% : c'est là que se joue le gain."
            % (resultat['lcp_lisible'],
               (resultat['libelle_verdict'] or 'sans verdict').lower(),
               dominante['libelle'],
               round(dominante['part'] * 100),
               round(dominante['part_cible'] * 100))
        )
    elif resultat['verdict'] == 'bon':
        resultat['diagnostic'] = (
            "LCP de %s, dans le vert, et chaque phase tient son budget. Rien à "
            "corriger de ce côté." % resultat['lcp_lisible']
        )
    else:
        resultat['diagnostic'] = (
            "LCP de %s (%s) mais aucune phase ne déborde nettement son budget : "
            "le retard est réparti, il faut gagner un peu partout."
            % (resultat['lcp_lisible'],
               (resultat['libelle_verdict'] or 'sans verdict').lower())
        )
        resultat['actions'] = [_ACTIONS_LCP['ttfb'],
                               _ACTIONS_LCP['chargement_ressource']]

    if isinstance(element, dict):
        resultat['element'] = {
            'selecteur': element.get('selector') or '',
            'extrait': (element.get('snippet') or '')[:300],
            'nom': element.get('nodeLabel') or '',
        }

    return resultat


# ---------------------------------------------------------------------------
# Preload, Speculation Rules, bfcache
# ---------------------------------------------------------------------------

_MAX_HTML = 2_000_000

_RE_BLOC_SPECULATION = re.compile(
    r'<script\b[^>]*\btype\s*=\s*["\']?speculationrules["\']?[^>]*>'
    r'(?P<corps>.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)
_RE_BALISE_LINK = re.compile(r'<link\b[^>]*>', re.IGNORECASE)
_RE_BALISE_META = re.compile(r'<meta\b[^>]*>', re.IGNORECASE)
# Bare attributes matter here: `crossorigin` carries no value and its absence is
# exactly what the font findings are about.
_RE_ATTRIBUT = re.compile(r'([-\w:]+)(?:\s*=\s*("[^"]*"|\'[^\']*\'|[^\s"\'>]+))?')
_RE_FETCHPRIORITY_HAUTE = re.compile(
    r'<(?:img|video|source|link|script)\b[^>]*\bfetchpriority\s*=\s*["\']?high\b',
    re.IGNORECASE,
)
_RE_ECOUTEUR_UNLOAD = re.compile(
    r'\baddEventListener\s*\(\s*["\']unload["\']|\bonunload\s*=', re.IGNORECASE,
)
_RE_ECOUTEUR_BEFOREUNLOAD = re.compile(
    r'\baddEventListener\s*\(\s*["\']beforeunload["\']|\bonbeforeunload\s*=',
    re.IGNORECASE,
)

# Third parties heavy enough that their connection setup shows up inside the
# LCP, and common enough on Quebec small-business sites to be worth naming.
# The flag says whether the preconnect needs crossorigin to be of any use.
_TIERS_LOURDS = (
    ('fonts.gstatic.com', 'les polices Google', True),
    ('use.typekit.net', 'les polices Adobe', True),
    ('fonts.googleapis.com', 'la feuille de style des polices Google', False),
    ('cdn.shopify.com', 'les fichiers Shopify', False),
    ('www.googletagmanager.com', 'Google Tag Manager', False),
    ('connect.facebook.net', 'le pixel Facebook', False),
    ('res.cloudinary.com', 'les images Cloudinary', False),
)

# Past this, preloads fight each other for the same bandwidth and the LCP image
# arrives later than it would have with none at all.
_PRELOADS_EXCESSIFS = 6

# Speculation rules only pay off on a page with somewhere to navigate to.
_LIENS_INTERNES_MINIMUM = 5

_METHODES_LAZY = {
    'native': 'l\'attribut loading="lazy"',
    'perfmatters': 'le chargement différé de Perfmatters',
    'ewww': 'le chargement différé de EWWW',
    'js-generic': 'un script de chargement différé',
}


def _attributs(balise: str) -> dict:
    """Attribute dict for one tag, first occurrence wins, values unquoted."""
    attributs = {}
    interieur = balise[1:-1] if balise.endswith('>') else balise[1:]
    for nom, valeur in _RE_ATTRIBUT.findall(interieur):
        cle = nom.lower()
        if cle in attributs:
            continue
        if valeur and valeur[:1] in ('"', "'"):
            valeur = valeur[1:-1]
        attributs[cle] = valeur or ''
    return attributs


def _jetons(valeur: str) -> set:
    return {jeton for jeton in (valeur or '').lower().replace(',', ' ').split() if jeton}


def _constat(code: str, severite: str, message: str, correctif: str, **extra) -> dict:
    constat = {'code': code, 'severity': severite, 'message': message,
               'fix': correctif}
    constat.update(extra)
    return constat


def _premiere_image_utile(images):
    """First non-decorative image in document order, the LCP candidate.

    Decorative images are skipped because a theme's logo or a spacer sits first
    in the DOM and is never what the visitor is waiting for. An image with no
    `src` still counts when it declares a lazy loader: that is precisely how a
    JS lazy loader ships a hero image, and skipping it would blind the one check
    that matters most here.
    """
    for image in (images or []):
        if not isinstance(image, dict):
            continue
        if image.get('decorative'):
            continue
        if (not (image.get('src') or '').strip()
                and (image.get('lazy_method') or 'none') == 'none'):
            continue
        return image
    return None


def _analyser_regles_speculation(html: str) -> dict:
    blocs = list(_RE_BLOC_SPECULATION.finditer(html))
    actions = set()
    invalides = 0
    for bloc in blocs:
        try:
            charge = json.loads(bloc.group('corps').strip())
        except (ValueError, TypeError):
            invalides += 1
            continue
        if not isinstance(charge, dict):
            invalides += 1
            continue
        connues = [nom for nom in ('prefetch', 'prerender') if charge.get(nom)]
        if not connues:
            invalides += 1
            continue
        actions.update(connues)
    return {'blocs': len(blocs), 'actions': sorted(actions), 'invalides': invalides}


def check_preload_signals(signals: dict, html: str = '') -> list[dict]:
    """Audit the loading hints that decide the LCP and the instant back button.

    Args:
        signals: the dict from `html_parse.extract_seo_signals`. Its `images`
            list carries the lazy-loading method, which is what exposes the most
            common LCP defect: a hero image the theme defers.
        html: the raw body. Optional, but the head hints (preload, preconnect,
            speculation rules, bfcache killers) live nowhere else, so without it
            only the image check runs and a note says so.

    Returns findings shaped like the rest of the dashboard: `code`, `severity`
    ('critical' down to 'info'), `message`, `fix`, sorted by severity. Never
    raises, and returns an empty list on a page that does everything right.
    """
    signals = signals if isinstance(signals, dict) else {}
    markup = (html or '')[:_MAX_HTML]
    constats = []

    images = signals.get('images')
    images = images if isinstance(images, list) else []
    liens = signals.get('links')
    liens = liens if isinstance(liens, dict) else {}
    liens_internes = liens.get('internal')
    liens_internes = liens_internes if isinstance(liens_internes, list) else []

    heros = _premiere_image_utile(images)
    if heros and heros.get('lazy_method') not in (None, '', 'none'):
        constats.append(_constat(
            'lcp_image_en_lazy', 'critical',
            "La première image de la page (%s) est chargée en différé par %s. Le "
            "navigateur ne la découvre qu'après avoir lu le reste du document, "
            "ce qui ajoute souvent une seconde au LCP."
            % (heros.get('src') or 'sans attribut src',
               _METHODES_LAZY.get(heros['lazy_method'], 'un mécanisme de différé')),
            "Retire le chargement différé sur cette seule image et ajoute-lui "
            "fetchpriority=\"high\". Garde le différé pour les images plus bas.",
            image=heros.get('src') or '',
            methode=heros.get('lazy_method'),
        ))

    if not markup.strip():
        constats.append(_constat(
            'html_absent', 'info',
            "HTML non fourni : seule la vérification des images a été faite. Les "
            "indices de chargement (preload, preconnect, règles de spéculation, "
            "cache retour-avant) vivent dans le code source de la page.",
            "Passe le corps de la page à check_preload_signals pour l'audit complet.",
        ))
        constats.sort(key=lambda item: (SEVERITE_RANG.get(item['severity'], 9),
                                        item['code']))
        return constats

    # -- head hints --------------------------------------------------------
    preloads = []
    preconnects = {}
    prerenders = 0
    for balise in _RE_BALISE_LINK.findall(markup):
        attributs = _attributs(balise)
        rels = _jetons(attributs.get('rel'))
        if 'preload' in rels or 'modulepreload' in rels:
            preloads.append(attributs)
        if 'preconnect' in rels or 'dns-prefetch' in rels:
            try:
                hote = _plat(urlparse(attributs.get('href') or '').hostname or '')
            except ValueError:
                hote = ''
            if hote:
                preconnects[hote] = attributs
        if 'prerender' in rels:
            prerenders += 1

    fetchpriority_haute = _RE_FETCHPRIORITY_HAUTE.findall(markup)
    preload_image = any(_plat(attributs.get('as')) == 'image'
                        for attributs in preloads)

    if not fetchpriority_haute and not preload_image and images:
        constats.append(_constat(
            'lcp_sans_priorite', 'high',
            "Aucune image n'est marquée prioritaire : ni fetchpriority=\"high\", "
            "ni <link rel=\"preload\" as=\"image\">. Le navigateur doit deviner "
            "laquelle afficher en premier, et il devine mal sur une page à héros.",
            "Ajoute fetchpriority=\"high\" à l'image du haut de page. Une seule "
            "image, sinon la priorité ne veut plus rien dire.",
        ))
    elif len(fetchpriority_haute) > 2:
        constats.append(_constat(
            'priorite_diluee', 'low',
            "%s éléments demandent fetchpriority=\"high\". Quand tout est "
            "prioritaire, plus rien ne l'est et l'image du LCP attend son tour."
            % len(fetchpriority_haute),
            "Garde la priorité haute sur le seul élément qui déclenche le LCP.",
        ))

    sans_as = [attributs for attributs in preloads
               if 'preload' in _jetons(attributs.get('rel'))
               and not (attributs.get('as') or '').strip()]
    if sans_as:
        constats.append(_constat(
            'preload_sans_as', 'medium',
            "%s balise(s) <link rel=\"preload\"> sans attribut as. Le navigateur "
            "ne sait pas quoi en faire et télécharge souvent le fichier deux fois."
            % len(sans_as),
            "Ajoute as=\"image\", as=\"font\", as=\"style\" ou as=\"script\" selon "
            "la ressource préchargée.",
        ))

    polices_sans_crossorigin = [
        attributs for attributs in preloads
        if _plat(attributs.get('as')) == 'font' and 'crossorigin' not in attributs
    ]
    if polices_sans_crossorigin:
        constats.append(_constat(
            'preload_police_sans_crossorigin', 'medium',
            "%s police(s) préchargée(s) sans attribut crossorigin. Les polices "
            "voyagent toujours en mode anonyme : sans crossorigin, le fichier "
            "préchargé est ignoré et téléchargé une deuxième fois."
            % len(polices_sans_crossorigin),
            "Écris <link rel=\"preload\" as=\"font\" type=\"font/woff2\" crossorigin>.",
        ))

    if len(preloads) > _PRELOADS_EXCESSIFS:
        constats.append(_constat(
            'preload_excessif', 'medium',
            "%s ressources préchargées. Au-delà de %s, elles se disputent la "
            "bande passante et retardent justement ce qui compte pour le LCP."
            % (len(preloads), _PRELOADS_EXCESSIFS),
            "Garde le préchargement pour l'image du LCP et la police du titre, "
            "retire le reste.",
        ))

    for hote, description, besoin_crossorigin in _TIERS_LOURDS:
        if hote not in markup:
            continue
        attributs = preconnects.get(hote)
        if attributs is None:
            constats.append(_constat(
                'preconnect_manquant', 'low',
                "La page charge %s (%s) sans préconnexion. Chaque nouveau domaine "
                "coûte une résolution DNS et une poignée de main TLS avant même "
                "le premier octet." % (description, hote),
                "Ajoute <link rel=\"preconnect\" href=\"https://%s\"%s> dans le head."
                % (hote, ' crossorigin' if besoin_crossorigin else ''),
                hote=hote,
            ))
        elif besoin_crossorigin and 'crossorigin' not in attributs:
            constats.append(_constat(
                'preconnect_sans_crossorigin', 'low',
                "La préconnexion vers %s n'a pas l'attribut crossorigin. Les "
                "polices se chargent en mode anonyme, donc la connexion ouverte "
                "ne sert à rien et le navigateur en ouvre une deuxième." % hote,
                "Écris <link rel=\"preconnect\" href=\"https://%s\" crossorigin>."
                % hote,
                hote=hote,
            ))

    # -- speculation rules --------------------------------------------------
    speculation = _analyser_regles_speculation(markup)
    if speculation['invalides']:
        constats.append(_constat(
            'regles_speculation_invalides', 'medium',
            "%s bloc(s) <script type=\"speculationrules\"> illisibles ou sans "
            "règle prefetch ni prerender. Chrome les ignore en silence."
            % speculation['invalides'],
            "Vérifie le JSON du bloc : il doit contenir une clé \"prerender\" ou "
            "\"prefetch\" avec une liste de règles.",
        ))
    elif speculation['blocs'] and 'prerender' not in speculation['actions']:
        constats.append(_constat(
            'speculation_sans_prerender', 'low',
            "Les règles de spéculation ne font que du prefetch. Le prerender va "
            "plus loin : la page suivante est déjà affichée quand le visiteur "
            "clique dessus.",
            "Ajoute une règle \"prerender\" sur les deux ou trois pages les plus "
            "visitées depuis celle-ci.",
        ))
    elif not speculation['blocs'] and len(liens_internes) >= _LIENS_INTERNES_MINIMUM:
        constats.append(_constat(
            'regles_speculation_absentes', 'medium',
            "Aucune règle de spéculation sur une page qui pointe vers %s pages "
            "internes. Chrome sait précharger la page suivante et l'afficher "
            "instantanément au clic, sans rien coûter." % len(liens_internes),
            "Ajoute un <script type=\"speculationrules\"> avec une règle prerender "
            "sur les liens du menu principal.",
        ))

    if prerenders:
        constats.append(_constat(
            'rel_prerender_deprecie', 'medium',
            "%s balise(s) <link rel=\"prerender\">. Chrome a retiré ce format à "
            "la version 120 : elles ne font plus rien." % prerenders,
            "Remplace-les par un bloc <script type=\"speculationrules\">.",
        ))

    # -- bfcache ------------------------------------------------------------
    if _RE_ECOUTEUR_UNLOAD.search(markup):
        constats.append(_constat(
            'bfcache_unload', 'high',
            "Un écouteur d'événement unload est présent. Il exclut la page du "
            "cache retour-avant : chaque retour du visiteur recharge tout au lieu "
            "de restituer la page instantanément.",
            "Remplace unload par pagehide ou visibilitychange, qui font la même "
            "chose sans casser le cache.",
        ))
    elif _RE_ECOUTEUR_BEFOREUNLOAD.search(markup):
        constats.append(_constat(
            'bfcache_beforeunload', 'low',
            "Un écouteur beforeunload est présent. Chrome le tolère, mais Firefox "
            "et Safari refusent la page au cache retour-avant.",
            "Garde beforeunload uniquement sur les pages avec un formulaire en "
            "cours de saisie, et retire-le ailleurs.",
        ))

    for balise in _RE_BALISE_META.findall(markup):
        attributs = _attributs(balise)
        if _plat(attributs.get('http-equiv')) != 'cache-control':
            continue
        if 'no-store' in _plat(attributs.get('content')):
            constats.append(_constat(
                'bfcache_no_store', 'high',
                "La page déclare Cache-Control: no-store. Elle est exclue du "
                "cache retour-avant et rechargée entièrement à chaque retour.",
                "Réserve no-store aux pages derrière un compte. Sur une page "
                "publique, no-cache suffit.",
            ))
            break

    constats.sort(key=lambda item: (SEVERITE_RANG.get(item['severity'], 9),
                                    item['code']))
    return constats
