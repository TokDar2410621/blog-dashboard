"""Standalone HTML report: one file, inline CSS, the PDF left to the browser.

Ported from claude-seo v2.2.4 `scripts/drift_report.py`.
Copyright (c) 2025 Daniel Agrici (AgriciDaniel). MIT.
https://github.com/AgriciDaniel/claude-seo

Upstream renders one fixed shape, the drift comparison, and paints every colour
into an inline `style` attribute. Both had to change. The shape becomes a
generic title / sections / score / table / findings / recommendations structure,
because a dozen Gridar modules already emit findings and each one spells
severity its own way (`critical`, `high`, `warning`, `hard_stop`, `elevee`), so
the renderer normalizes them rather than asking every caller to convert. The
inline colours become classes: an inline style outranks any `@media print` rule,
which is precisely why a screen palette reaches paper unreadable. Everything
injected is escaped, long dashes are folded to hyphens, and link schemes are
checked before an href is written.
"""
from __future__ import annotations

import html
import unicodedata
from collections import Counter
from datetime import datetime, timezone

__all__ = [
    'SEVERITES',
    'LIBELLES_SEVERITES',
    'normalize_severite',
    'render_report',
]


# ---------------------------------------------------------------------------
# Severity vocabulary
# ---------------------------------------------------------------------------

SEVERITES = ('critique', 'elevee', 'moyenne', 'faible', 'info', 'succes')

LIBELLES_SEVERITES = {
    'critique': 'Critique',
    'elevee': 'Élevée',
    'moyenne': 'Moyenne',
    'faible': 'Faible',
    'info': 'Info',
    'succes': 'Conforme',
}

_RANG_SEVERITES = {nom: rang for rang, nom in enumerate(SEVERITES)}

# Every spelling already in use across the backend maps here. drift_rules says
# critical/warning/info, gbp_lint says critical/high/medium/low, schema_validator
# says error/warning, quality_gates says hard_stop/warning/ok, sxo says
# aucune/faible/moyenne/elevee/critique. A report renderer that only understood
# one of those would silently grey out most of what it is handed.
_ALIAS_SEVERITES = {
    'critique': 'critique', 'critical': 'critique', 'crit': 'critique',
    'erreur': 'critique', 'error': 'critique', 'fatal': 'critique',
    'blocker': 'critique', 'bloquant': 'critique', 'hard stop': 'critique',
    'severe': 'critique', 'urgent': 'critique', 'p0': 'critique',
    'echec': 'critique', 'fail': 'critique', 'failed': 'critique',

    'elevee': 'elevee', 'eleve': 'elevee', 'high': 'elevee', 'haute': 'elevee',
    'haut': 'elevee', 'major': 'elevee', 'majeur': 'elevee', 'important': 'elevee',
    'p1': 'elevee',

    'moyenne': 'moyenne', 'moyen': 'moyenne', 'medium': 'moyenne', 'med': 'moyenne',
    'warning': 'moyenne', 'warn': 'moyenne', 'avertissement': 'moyenne',
    'attention': 'moyenne', 'modere': 'moyenne', 'p2': 'moyenne',

    'faible': 'faible', 'low': 'faible', 'mineur': 'faible', 'minor': 'faible',
    'suggestion': 'faible', 'p3': 'faible',

    'info': 'info', 'information': 'info', 'informatif': 'info', 'note': 'info',
    'notice': 'info', 'neutre': 'info', 'indetermine': 'info', 'inconnu': 'info',

    'succes': 'succes', 'success': 'succes', 'ok': 'succes', 'pass': 'succes',
    'passed': 'succes', 'reussi': 'succes', 'conforme': 'succes', 'bon': 'succes',
    'aucune': 'succes', 'aucun': 'succes', 'none': 'succes', 'aligne': 'succes',
    'good': 'succes', 'valide': 'succes',
}


def _plat(valeur) -> str:
    """Lowercase, accent-free, whitespace-collapsed form used by the matchers."""
    if valeur is None:
        return ''
    texte = unicodedata.normalize('NFD', str(valeur))
    texte = ''.join(c for c in texte if unicodedata.category(c) != 'Mn')
    return ' '.join(texte.lower().split())


def normalize_severite(valeur) -> str:
    """Map any severity spelling to one of `SEVERITES`. Unknown becomes 'info'.

    Never raises: a report is rendered from whatever a caller assembled, and a
    typo in a severity string must not cost the whole document.
    """
    plat = _plat(valeur).replace('_', ' ').replace('-', ' ')
    if not plat:
        return 'info'
    if plat in _ALIAS_SEVERITES:
        return _ALIAS_SEVERITES[plat]
    for mot in plat.split():
        if mot in _ALIAS_SEVERITES:
            return _ALIAS_SEVERITES[mot]
    return 'info'


# ---------------------------------------------------------------------------
# Escaping and value flattening
# ---------------------------------------------------------------------------

# Gridar never ships a long dash, in prose or in markup. Folding them here means
# a client article title carrying one cannot smuggle it into the report.
_TIRETS_LONGS = {
    0x2014: '-',   # em dash
    0x2013: '-',   # en dash
    0x2015: '-',   # horizontal bar
    0x2212: '-',   # minus sign
}

_MAX_TEXTE = 4000
_MAX_CELLULE = 600
_MAX_TITRE = 300
_MAX_LIGNES = 400
_MAX_CONSTATS = 300
_MAX_SECTIONS = 60

_POLICES = (
    '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", '
    'Arial, "Noto Sans", sans-serif'
)


def _nombre(valeur) -> str:
    """French number rendering: comma decimal, no trailing zero on integers."""
    if isinstance(valeur, bool):
        return 'oui' if valeur else 'non'
    if isinstance(valeur, int):
        return str(valeur)
    if isinstance(valeur, float):
        if valeur.is_integer():
            return str(int(valeur))
        return f'{round(valeur, 2)}'.replace('.', ',')
    return str(valeur)


def _texte(valeur, limite: int = _MAX_TEXTE) -> str:
    """Flatten any value to a display string, long dashes folded to hyphens.

    Lists and dicts are flattened rather than refused: callers hand this module
    finding payloads straight out of other analysers, where a field that is
    usually a string is occasionally a list.
    """
    if valeur is None:
        return ''
    if isinstance(valeur, (bool, int, float)):
        brut = _nombre(valeur)
    elif isinstance(valeur, str):
        brut = valeur
    elif isinstance(valeur, dict):
        brut = ', '.join(
            f'{_texte(cle, 80)} : {_texte(val, 200)}' for cle, val in valeur.items()
        )
    elif isinstance(valeur, (list, tuple, set, frozenset)):
        brut = ', '.join(_texte(item, 200) for item in valeur)
    else:
        brut = str(valeur)

    brut = brut.translate(_TIRETS_LONGS).strip()
    if len(brut) > limite:
        brut = brut[:limite].rstrip() + '…'
    return brut


def _esc(valeur, limite: int = _MAX_TEXTE) -> str:
    """Escape for a text node. Apostrophes stay readable in the source."""
    return html.escape(_texte(valeur, limite), quote=False)


def _esc_attr(valeur, limite: int = _MAX_TEXTE) -> str:
    """Escape for an attribute value. Quotes included, always."""
    return html.escape(_texte(valeur, limite), quote=True)


def _esc_multi(valeur, limite: int = _MAX_TEXTE) -> str:
    """Escape a text node and keep its line breaks."""
    escapee = html.escape(_texte(valeur, limite), quote=False)
    return escapee.replace('\r\n', '\n').replace('\r', '\n').replace('\n', '<br>')


def _url_sure(valeur) -> str:
    """Return an http(s) URL fit for an href, or '' when it is anything else.

    A report is assembled from data that came off a client site, so `javascript:`
    and `data:` must never reach an attribute. Control characters are stripped
    first because a browser ignores them while a naive prefix check does not.
    """
    brut = _texte(valeur, 2000)
    nettoye = ''.join(c for c in brut if ord(c) > 0x20 and ord(c) != 0x7f)
    if not nettoye:
        return ''
    debut = nettoye[:8].lower()
    if debut.startswith('http://') or debut.startswith('https://'):
        return nettoye
    return ''


def _lien(url, libelle=None) -> str:
    """Anchor when the URL is safe, plain text otherwise."""
    sure = _url_sure(url)
    texte = _esc(libelle if libelle not in (None, '') else url, 300)
    if not sure:
        return texte
    return (
        f'<a class="lien" href="{_esc_attr(sure, 2000)}" target="_blank" '
        f'rel="noopener noreferrer">{texte}</a>'
    )


# ---------------------------------------------------------------------------
# Input reading
# ---------------------------------------------------------------------------

def _cle(source, *noms, defaut=None):
    """First non-empty value among alias keys. Callers mix French and English."""
    if not isinstance(source, dict):
        return defaut
    for nom in noms:
        valeur = source.get(nom)
        if valeur is not None and valeur != '':
            return valeur
    return defaut


def _cle_presente(source, *noms, defaut=None):
    """Like `_cle`, except an empty string counts as a value.

    A drift finding whose new value is empty is the finding itself: the title
    was removed. Treating '' as absent would hide the worst case.
    """
    if not isinstance(source, dict):
        return defaut
    for nom in noms:
        if nom in source and source[nom] is not None:
            return source[nom]
    return defaut


def _liste(valeur) -> list:
    """Coerce to a list without exploding a string into characters."""
    if valeur is None or valeur == '':
        return []
    if isinstance(valeur, (list, tuple)):
        return list(valeur)
    if isinstance(valeur, (set, frozenset)):
        return sorted(valeur, key=str)
    return [valeur]


_MOIS_FR = (
    'janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août',
    'septembre', 'octobre', 'novembre', 'décembre',
)


def _date_fr(moment: datetime) -> str:
    return (
        f'{moment.day} {_MOIS_FR[moment.month - 1]} {moment.year}, '
        f'{moment.hour:02d}:{moment.minute:02d} UTC'
    )


# ---------------------------------------------------------------------------
# Score block
# ---------------------------------------------------------------------------

def _palier_score(pourcentage: float) -> tuple[str, str]:
    if pourcentage >= 80:
        return 'succes', 'Solide'
    if pourcentage >= 60:
        return 'moyenne', 'Correct'
    if pourcentage >= 40:
        return 'elevee', 'À améliorer'
    return 'critique', 'Critique'


def _bloc_score(score) -> str:
    """Big number, gauge and label. Accepts a bare number or a dict."""
    if score is None or score == '':
        return ''

    if isinstance(score, dict):
        valeur = _cle(score, 'valeur', 'value', 'score', 'note', defaut=None)
        sur = _cle(score, 'sur', 'max', 'total', 'base', defaut=None)
        libelle = _cle(score, 'libelle', 'label', 'mention', defaut=None)
        detail = _cle(score, 'detail', 'description', 'commentaire', defaut='')
        severite = _cle(score, 'severite', 'severity', 'niveau', defaut=None)
    else:
        valeur, sur, libelle, detail, severite = score, None, None, '', None

    etait_flottant = isinstance(valeur, float)
    try:
        valeur = float(valeur)
    except (TypeError, ValueError):
        return ''

    if sur is None:
        # A float inside (0, 1] is a ratio in every module that produces one
        # (confiance, uniqueness_ratio), never a score out of 100. The test is on
        # the value as it was given: an int 1 is one point, not 100 percent.
        if etait_flottant and 0 < valeur <= 1:
            valeur, sur = round(valeur * 100), 100
        else:
            sur = 100
    try:
        sur = float(sur)
    except (TypeError, ValueError):
        sur = 100.0
    if sur <= 0:
        sur = 100.0

    pourcentage = max(0.0, min(100.0, valeur / sur * 100))
    palier, mention = _palier_score(pourcentage)
    classe = normalize_severite(severite) if severite else palier
    if libelle in (None, ''):
        libelle = mention

    # The only inline style in the document. It carries a geometry, not a
    # colour, so the print overrides still win where it matters.
    largeur = int(round(pourcentage))
    affichee = _nombre(round(valeur, 1))
    suffixe = f'/{_nombre(round(sur, 1))}'

    parties = [
        f'<div class="score sev-{classe}">',
        '<div class="score-chiffre">',
        f'<span class="score-valeur">{_esc(affichee, 20)}</span>',
        f'<span class="score-sur">{_esc(suffixe, 20)}</span>',
        '</div>',
        '<div class="score-corps">',
        f'<p class="score-libelle">{_esc(libelle, 120)}</p>',
        '<div class="jauge" role="img" aria-label="'
        f'{_esc_attr(str(largeur) + " sur 100", 40)}">',
        f'<span class="jauge-barre" style="width:{largeur}%"></span>',
        '</div>',
    ]
    if detail:
        parties.append(f'<p class="score-detail">{_esc_multi(detail, 1200)}</p>')
    parties.append('</div>')
    parties.append('</div>')
    return ''.join(parties)


# ---------------------------------------------------------------------------
# Table block
# ---------------------------------------------------------------------------

def _cellule(cellule) -> str:
    """Render one cell. A dict with a severity paints a chip instead of text."""
    if isinstance(cellule, dict):
        valeur = _cle(cellule, 'valeur', 'value', 'texte', 'text', 'libelle',
                      defaut='')
        severite = _cle(cellule, 'severite', 'severity', 'niveau', 'level',
                        defaut=None)
        url = _cle(cellule, 'url', 'lien', 'href', defaut=None)
        if url:
            corps = _lien(url, valeur if valeur != '' else url)
        else:
            corps = _esc(valeur, _MAX_CELLULE)
        if severite:
            classe = normalize_severite(severite)
            return f'<span class="pastille sev-{classe}">{corps}</span>'
        return corps
    if isinstance(cellule, str) and _url_sure(cellule):
        return _lien(cellule)
    return _esc(cellule, _MAX_CELLULE)


def _colonnes(brutes) -> list:
    sorties = []
    for colonne in brutes:
        if isinstance(colonne, dict):
            cle = _cle(colonne, 'cle', 'key', 'champ', 'field', defaut=None)
            libelle = _cle(colonne, 'libelle', 'label', 'titre', 'title',
                           defaut=cle)
            sorties.append({'cle': cle, 'libelle': libelle})
        else:
            sorties.append({'cle': colonne, 'libelle': colonne})
    return sorties


def _bloc_tableau(tableau) -> str:
    """Header row plus body, wrapped in the container that scrolls sideways."""
    if not tableau:
        return ''
    if isinstance(tableau, (list, tuple)):
        tableau = {'lignes': tableau}
    if not isinstance(tableau, dict):
        return ''

    lignes = _liste(_cle(tableau, 'lignes', 'rows', 'donnees', 'data', defaut=[]))
    colonnes = _colonnes(_liste(_cle(
        tableau, 'colonnes', 'columns', 'entetes', 'headers', 'en_tetes', defaut=[],
    )))
    legende = _cle(tableau, 'legende', 'caption', 'titre', 'title', defaut='')

    # Rows given as dicts carry their own column names when none were declared.
    if not colonnes and lignes and isinstance(lignes[0], dict):
        vues = []
        for ligne in lignes[:50]:
            if isinstance(ligne, dict):
                for cle in ligne:
                    if cle not in vues:
                        vues.append(cle)
        colonnes = _colonnes(vues)
    if not lignes and not colonnes:
        return ''

    total = len(lignes)
    tronque = total > _MAX_LIGNES
    lignes = lignes[:_MAX_LIGNES]

    parties = ['<div class="tableau-defilant" role="region" tabindex="0" aria-label="'
               f'{_esc_attr(legende or "Tableau du rapport", 200)}">', '<table>']
    if legende:
        parties.append(f'<caption>{_esc(legende, 400)}</caption>')
    if colonnes:
        parties.append('<thead><tr>')
        for colonne in colonnes:
            parties.append(
                f'<th scope="col">{_esc(colonne["libelle"], 200)}</th>'
            )
        parties.append('</tr></thead>')

    parties.append('<tbody>')
    for ligne in lignes:
        parties.append('<tr>')
        if isinstance(ligne, dict):
            for colonne in colonnes:
                cellule = ligne.get(colonne['cle'])
                parties.append(f'<td>{_cellule(cellule)}</td>')
        else:
            cellules = _liste(ligne)
            if colonnes:
                cellules = cellules[:len(colonnes)]
                cellules += [''] * (len(colonnes) - len(cellules))
            for cellule in cellules:
                parties.append(f'<td>{_cellule(cellule)}</td>')
        parties.append('</tr>')
    parties.append('</tbody></table></div>')

    if tronque:
        parties.append(
            '<p class="note-tronquage">Affichage limité aux '
            f'{_MAX_LIGNES} premières lignes sur {total} au total.</p>'
        )
    return ''.join(parties)


# ---------------------------------------------------------------------------
# Findings and recommendations
# ---------------------------------------------------------------------------

def _lire_constat(constat) -> dict:
    if not isinstance(constat, dict):
        constat = {'message': constat}
    severite = normalize_severite(_cle(
        constat, 'severite', 'severity', 'niveau', 'level', 'gravite', defaut='',
    ))
    return {
        'severite': severite,
        'titre': _cle(constat, 'titre', 'title', 'regle', 'rule', 'check',
                      'nom', defaut=''),
        'message': _cle(constat, 'message', 'description', 'detail', 'texte',
                        'explication', defaut=''),
        'details': _liste(_cle(constat, 'details', 'elements', 'items',
                               'exemples', 'preuves', defaut=[])),
        'avant': _cle_presente(constat, 'avant', 'valeur_avant', 'old_value',
                               'before', defaut=None),
        'apres': _cle_presente(constat, 'apres', 'valeur_apres', 'new_value',
                               'after', defaut=None),
        'url': _cle(constat, 'url', 'lien', 'page', 'href', defaut=None),
        'correctif': _cle(constat, 'correctif', 'recommandation', 'fix',
                          'action', defaut=''),
    }


def _bloc_constat(lu: dict) -> str:
    classe = lu['severite']
    parties = [f'<article class="constat sev-{classe}">', '<div class="constat-tete">',
               f'<span class="badge">{_esc(LIBELLES_SEVERITES[classe], 40)}</span>']
    if lu['titre']:
        parties.append(f'<h3 class="constat-titre">{_esc(lu["titre"], _MAX_TITRE)}</h3>')
    parties.append('</div>')

    if lu['message']:
        parties.append(f'<p class="constat-message">{_esc_multi(lu["message"])}</p>')

    if lu['url']:
        parties.append(f'<p class="constat-url">{_lien(lu["url"])}</p>')

    if lu['details']:
        parties.append('<ul class="constat-details">')
        for detail in lu['details'][:40]:
            parties.append(f'<li>{_esc(detail, 800)}</li>')
        parties.append('</ul>')

    if lu['avant'] is not None or lu['apres'] is not None:
        parties.append('<div class="diff">')
        if lu['avant'] is not None:
            parties.append(
                '<p class="diff-avant"><span class="diff-etiquette">Avant</span> '
                f'{_esc(lu["avant"], 800) or "(vide)"}</p>'
            )
        if lu['apres'] is not None:
            parties.append(
                '<p class="diff-apres"><span class="diff-etiquette">Après</span> '
                f'{_esc(lu["apres"], 800) or "(vide)"}</p>'
            )
        parties.append('</div>')

    if lu['correctif']:
        parties.append(
            '<p class="constat-correctif"><span class="diff-etiquette">Correctif</span> '
            f'{_esc_multi(lu["correctif"], 1200)}</p>'
        )
    parties.append('</article>')
    return ''.join(parties)


def _bloc_recommandations(recommandations) -> str:
    elements = _liste(recommandations)
    if not elements:
        return ''
    parties = ['<ol class="recos">']
    for brute in elements[:60]:
        if not isinstance(brute, dict):
            brute = {'texte': brute}
        texte = _cle(brute, 'texte', 'text', 'message', 'titre', 'title',
                     'action', defaut='')
        detail = _cle(brute, 'detail', 'description', 'pourquoi', defaut='')
        priorite = _cle(brute, 'priorite', 'priority', 'severite', 'severity',
                        defaut=None)
        effort = _cle(brute, 'effort', 'charge', defaut='')
        url = _cle(brute, 'url', 'lien', 'href', defaut=None)

        classe = normalize_severite(priorite) if priorite else 'info'
        parties.append(f'<li class="reco sev-{classe}">')
        if priorite:
            libelle = LIBELLES_SEVERITES[classe].lower()
            parties.append(f'<span class="badge">Priorité {_esc(libelle, 40)}</span>')
        parties.append(f'<span class="reco-texte">{_esc_multi(texte, 1600)}</span>')
        if detail:
            parties.append(f'<p class="reco-detail">{_esc_multi(detail, 1600)}</p>')
        if url:
            parties.append(f'<p class="reco-url">{_lien(url)}</p>')
        if effort:
            parties.append(f'<p class="reco-effort">Effort : {_esc(effort, 120)}</p>')
        parties.append('</li>')
    parties.append('</ol>')
    return ''.join(parties)


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------

def _lire_section(section) -> dict:
    if not isinstance(section, dict):
        section = {'titre': '', 'resume': section}
    constats = [_lire_constat(c) for c in
                _liste(_cle(section, 'constats', 'findings', 'issues', 'problemes',
                            'anomalies', defaut=[]))]
    total_constats = len(constats)
    # Sort before the cap so a truncated section keeps its worst findings.
    constats.sort(key=lambda c: _RANG_SEVERITES[c['severite']])
    constats = constats[:_MAX_CONSTATS]
    return {
        'titre': _cle(section, 'titre', 'title', 'nom', 'name', defaut=''),
        'resume': _cle(section, 'resume', 'description', 'intro', 'texte',
                       defaut=''),
        'score': _cle(section, 'score', 'note', defaut=None),
        'tableau': _cle(section, 'tableau', 'table', 'donnees', defaut=None),
        'constats': constats,
        'total_constats': total_constats,
        'recommandations': _cle(section, 'recommandations', 'recommendations',
                                'recos', 'actions', defaut=None),
        'notes': _liste(_cle(section, 'notes', 'remarques', defaut=[])),
    }


def _bloc_section(lue: dict, ancre: str) -> str:
    parties = [f'<section class="section" id="{_esc_attr(ancre, 40)}">']
    if lue['titre']:
        parties.append(f'<h2 class="section-titre">{_esc(lue["titre"], _MAX_TITRE)}</h2>')
    if lue['resume']:
        parties.append(f'<p class="section-resume">{_esc_multi(lue["resume"])}</p>')

    parties.append(_bloc_score(lue['score']))
    parties.append(_bloc_tableau(lue['tableau']))

    if lue['constats']:
        parties.append('<div class="constats">')
        for constat in lue['constats']:
            parties.append(_bloc_constat(constat))
        parties.append('</div>')
        if lue['total_constats'] > len(lue['constats']):
            parties.append(
                f'<p class="note-tronquage">{lue["total_constats"]} constats au '
                f'total, {len(lue["constats"])} affichés.</p>'
            )

    recos = _bloc_recommandations(lue['recommandations'])
    if recos:
        parties.append('<h3 class="sous-titre">Recommandations</h3>')
        parties.append(recos)

    if lue['notes']:
        parties.append('<ul class="notes">')
        for note in lue['notes'][:30]:
            parties.append(f'<li>{_esc(note, 1200)}</li>')
        parties.append('</ul>')

    parties.append('</section>')
    return ''.join(parties)


# ---------------------------------------------------------------------------
# Header pieces
# ---------------------------------------------------------------------------

def _bloc_meta(meta) -> str:
    """Key/value strip under the title: site, page, period, whatever fits."""
    if not meta:
        return ''
    if isinstance(meta, dict):
        paires = list(meta.items())
    else:
        paires = []
        for item in _liste(meta):
            if isinstance(item, dict):
                paires.append((
                    _cle(item, 'libelle', 'label', 'cle', 'key', 'nom', defaut=''),
                    _cle(item, 'valeur', 'value', 'texte', defaut=''),
                ))
            elif isinstance(item, (list, tuple)) and len(item) >= 2:
                paires.append((item[0], item[1]))
    if not paires:
        return ''

    parties = ['<dl class="meta">']
    for libelle, valeur in paires[:20]:
        corps = _lien(valeur) if _url_sure(valeur) else _esc(valeur, 400)
        parties.append(
            f'<div class="meta-item"><dt>{_esc(libelle, 120)}</dt>'
            f'<dd>{corps}</dd></div>'
        )
    parties.append('</dl>')
    return ''.join(parties)


def _bloc_bilan(compte: Counter) -> str:
    """Counts per severity. Zeros are shown: no critical finding is a result."""
    if not sum(compte.values()):
        return ''
    montrees = [s for s in SEVERITES
                if s in ('critique', 'elevee', 'moyenne', 'faible') or compte[s]]
    parties = ['<div class="bilan">']
    for severite in montrees:
        parties.append(
            f'<div class="bilan-carte sev-{severite}">'
            f'<span class="bilan-nombre">{compte[severite]}</span>'
            f'<span class="bilan-libelle">{_esc(LIBELLES_SEVERITES[severite], 40)}</span>'
            '</div>'
        )
    parties.append('</div>')
    return ''.join(parties)


def _bloc_sommaire(sections: list, ancres: list) -> str:
    if len(sections) < 2:
        return ''
    parties = ['<nav class="sommaire" aria-label="Sommaire">',
               '<p class="sommaire-titre">Sommaire</p>', '<ol>']
    for lue, ancre in zip(sections, ancres):
        titre = lue['titre'] or 'Section'
        pire = min((c['severite'] for c in lue['constats']),
                   key=lambda s: _RANG_SEVERITES[s], default=None)
        marque = ''
        if pire and pire != 'info':
            marque = (f'<span class="pastille sev-{pire}">'
                      f'{_esc(LIBELLES_SEVERITES[pire], 40)}</span>')
        parties.append(
            f'<li><a class="lien" href="#{_esc_attr(ancre, 40)}">'
            f'{_esc(titre, _MAX_TITRE)}</a>{marque}</li>'
        )
    parties.append('</ol></nav>')
    return ''.join(parties)


# ---------------------------------------------------------------------------
# Stylesheet
# ---------------------------------------------------------------------------

# One stylesheet, inlined. No font file, no image, no script: the document has
# to survive being e-mailed, opened from a file:// path and served under a CSP
# that forbids inline handlers, which is also why there is no print button.
_CSS = """
:root {
  --fond: #f5f6f8;
  --fond-carte: #ffffff;
  --texte: #1f2937;
  --texte-doux: #5b6472;
  --bordure: #e2e6ec;
  --accent: #1e3a5f;
  --accent-doux: #eef2f7;
  --critique: #b32217;
  --elevee: #b4460b;
  --moyenne: #96610a;
  --faible: #47536b;
  --info: #1e3a5f;
  --succes: #04684d;
  --fond-critique: #fdf2f1;
  --fond-elevee: #fff5ec;
  --fond-moyenne: #fffaeb;
  --fond-faible: #f4f6f9;
  --fond-info: #eef3fa;
  --fond-succes: #ecfaf4;
  --sev: var(--info);
  --sev-fond: var(--fond-info);
}
.sev-critique { --sev: var(--critique); --sev-fond: var(--fond-critique); }
.sev-elevee { --sev: var(--elevee); --sev-fond: var(--fond-elevee); }
.sev-moyenne { --sev: var(--moyenne); --sev-fond: var(--fond-moyenne); }
.sev-faible { --sev: var(--faible); --sev-fond: var(--fond-faible); }
.sev-info { --sev: var(--info); --sev-fond: var(--fond-info); }
.sev-succes { --sev: var(--succes); --sev-fond: var(--fond-succes); }

*, *::before, *::after { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body {
  margin: 0;
  padding: 2rem 1rem 4rem;
  background: var(--fond);
  color: var(--texte);
  font-family: FAMILLE_POLICE;
  font-size: 16px;
  line-height: 1.6;
}
.page { max-width: 62rem; margin: 0 auto; }
h1, h2, h3 { line-height: 1.25; margin: 0; }
p { margin: 0 0 0.75rem; }
p:last-child { margin-bottom: 0; }
.lien { color: var(--accent); text-decoration: underline; word-break: break-word; }

.barre {
  max-width: 62rem;
  margin: 0 auto 1rem;
  padding: 0.6rem 0.9rem;
  background: var(--accent-doux);
  border: 1px solid var(--bordure);
  border-radius: 8px;
  color: var(--texte-doux);
  font-size: 0.85rem;
}

.entete {
  background: var(--accent);
  color: #ffffff;
  border-radius: 12px;
  padding: 1.75rem 1.5rem;
  margin-bottom: 1.5rem;
}
.entete-marque {
  font-size: 0.75rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  opacity: 0.85;
  margin-bottom: 0.4rem;
}
.entete h1 { font-size: 1.75rem; }
.entete-sous-titre { margin-top: 0.5rem; font-size: 1rem; opacity: 0.92; }
.entete-date { margin-top: 0.75rem; font-size: 0.85rem; opacity: 0.8; }

.meta {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(11rem, 1fr));
  gap: 0.75rem 1.25rem;
  margin: 1.25rem 0 0;
}
.meta-item { min-width: 0; }
.meta dt {
  font-size: 0.72rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  opacity: 0.8;
}
.meta dd { margin: 0.15rem 0 0; font-size: 0.92rem; word-break: break-word; }
.entete .meta .lien { color: #ffffff; }

.resume {
  background: var(--fond-carte);
  border: 1px solid var(--bordure);
  border-left: 4px solid var(--accent);
  border-radius: 10px;
  padding: 1rem 1.15rem;
  margin-bottom: 1.5rem;
}

.bilan {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(7.5rem, 1fr));
  gap: 0.75rem;
  margin-bottom: 1.5rem;
}
.bilan-carte {
  background: var(--fond-carte);
  border: 1px solid var(--bordure);
  border-top: 3px solid var(--sev);
  border-radius: 10px;
  padding: 0.85rem 0.6rem;
  text-align: center;
}
.bilan-nombre { display: block; font-size: 1.7rem; font-weight: 700; color: var(--sev); }
.bilan-libelle { display: block; font-size: 0.78rem; color: var(--texte-doux); }

.sommaire {
  background: var(--fond-carte);
  border: 1px solid var(--bordure);
  border-radius: 10px;
  padding: 1rem 1.15rem;
  margin-bottom: 1.5rem;
}
.sommaire-titre {
  font-size: 0.75rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--texte-doux);
  margin-bottom: 0.5rem;
}
.sommaire ol { margin: 0; padding-left: 1.25rem; }
.sommaire li { margin-bottom: 0.35rem; }

.section {
  background: var(--fond-carte);
  border: 1px solid var(--bordure);
  border-radius: 12px;
  padding: 1.4rem 1.35rem;
  margin-bottom: 1.5rem;
}
.section-titre {
  font-size: 1.25rem;
  color: var(--accent);
  border-bottom: 2px solid var(--accent-doux);
  padding-bottom: 0.55rem;
  margin-bottom: 0.85rem;
}
.section-resume { color: var(--texte-doux); }
.sous-titre {
  font-size: 0.78rem;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--texte-doux);
  margin: 1.25rem 0 0.6rem;
}

.score {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 1.25rem;
  background: var(--sev-fond);
  border: 1px solid var(--bordure);
  border-radius: 10px;
  padding: 1rem 1.15rem;
  margin-bottom: 1.1rem;
}
.score-chiffre { color: var(--sev); white-space: nowrap; }
.score-valeur { font-size: 2.6rem; font-weight: 700; line-height: 1; }
.score-sur { font-size: 1rem; opacity: 0.7; }
.score-corps { flex: 1 1 14rem; min-width: 0; }
.score-libelle { font-weight: 600; margin-bottom: 0.45rem; }
.jauge {
  height: 9px;
  border-radius: 999px;
  background: rgba(0, 0, 0, 0.08);
  overflow: hidden;
}
.jauge-barre {
  display: block;
  height: 100%;
  background: var(--sev);
  print-color-adjust: exact;
  -webkit-print-color-adjust: exact;
}
.score-detail { margin-top: 0.55rem; font-size: 0.9rem; color: var(--texte-doux); }

.tableau-defilant {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  border: 1px solid var(--bordure);
  border-radius: 10px;
  margin-bottom: 1.1rem;
}
.tableau-defilant table {
  width: 100%;
  min-width: 34rem;
  border-collapse: collapse;
  font-size: 0.9rem;
}
caption {
  caption-side: top;
  text-align: left;
  padding: 0.7rem 0.85rem 0;
  font-size: 0.85rem;
  color: var(--texte-doux);
}
th, td {
  padding: 0.6rem 0.85rem;
  text-align: left;
  border-bottom: 1px solid var(--bordure);
  vertical-align: top;
  word-break: break-word;
}
th { background: var(--accent-doux); font-size: 0.78rem; text-transform: uppercase;
     letter-spacing: 0.05em; color: var(--accent); }
tbody tr:last-child td { border-bottom: 0; }

.constat {
  background: var(--sev-fond);
  border: 1px solid var(--bordure);
  border-left: 4px solid var(--sev);
  border-radius: 8px;
  padding: 0.9rem 1rem;
  margin-bottom: 0.75rem;
}
.constat-tete { display: flex; align-items: baseline; flex-wrap: wrap; gap: 0.6rem;
                margin-bottom: 0.45rem; }
.constat-titre { font-size: 1rem; }
.constat-message { font-size: 0.95rem; }
.constat-url { font-size: 0.85rem; }
.constat-details { margin: 0.5rem 0 0; padding-left: 1.15rem; font-size: 0.88rem;
                   color: var(--texte-doux); }
.constat-correctif { margin-top: 0.6rem; font-size: 0.92rem; }
.diff {
  margin-top: 0.6rem;
  background: var(--fond-carte);
  border: 1px solid var(--bordure);
  border-radius: 6px;
  padding: 0.6rem 0.75rem;
  font-size: 0.85rem;
  word-break: break-word;
}
.diff-avant { color: var(--critique); }
.diff-apres { color: var(--succes); }
.diff-etiquette {
  display: inline-block;
  font-size: 0.7rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--texte-doux);
  margin-right: 0.35rem;
}
.badge {
  display: inline-block;
  padding: 0.1rem 0.55rem;
  border-radius: 999px;
  background: var(--sev);
  color: #ffffff;
  font-size: 0.7rem;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  white-space: nowrap;
  print-color-adjust: exact;
  -webkit-print-color-adjust: exact;
}
.pastille {
  display: inline-block;
  padding: 0.05rem 0.5rem;
  margin-left: 0.4rem;
  border: 1px solid var(--sev);
  border-radius: 999px;
  color: var(--sev);
  font-size: 0.72rem;
  white-space: nowrap;
}

.recos { margin: 0; padding-left: 1.3rem; }
.reco { margin-bottom: 0.7rem; }
.reco-texte { display: inline; }
.reco .badge { margin-right: 0.45rem; }
.reco-detail, .reco-url, .reco-effort {
  margin: 0.3rem 0 0;
  font-size: 0.87rem;
  color: var(--texte-doux);
}
.notes { margin: 1rem 0 0; padding-left: 1.2rem; font-size: 0.87rem;
         color: var(--texte-doux); }
.note-tronquage { font-size: 0.82rem; color: var(--texte-doux); font-style: italic; }

.pied {
  margin-top: 2rem;
  padding-top: 1rem;
  border-top: 1px solid var(--bordure);
  font-size: 0.82rem;
  color: var(--texte-doux);
  text-align: center;
}

@media (max-width: 40rem) {
  body { padding: 1rem 0.75rem 2.5rem; }
  .entete { padding: 1.25rem 1rem; border-radius: 10px; }
  .entete h1 { font-size: 1.35rem; }
  .section { padding: 1.1rem 0.9rem; }
  .score-valeur { font-size: 2.1rem; }
}

@media print {
  /* Screen tints are unreadable on paper and most browsers drop backgrounds
     entirely, so every semantic colour is darkened and every fill is dropped. */
  :root {
    --fond: #ffffff;
    --fond-carte: #ffffff;
    --texte: #111111;
    --texte-doux: #3a3a3a;
    --bordure: #9aa0a6;
    --accent: #10243d;
    --accent-doux: #ffffff;
    --critique: #7a1410;
    --elevee: #6b2a06;
    --moyenne: #573806;
    --faible: #22293a;
    --info: #10243d;
    --succes: #044231;
    --fond-critique: #ffffff;
    --fond-elevee: #ffffff;
    --fond-moyenne: #ffffff;
    --fond-faible: #ffffff;
    --fond-info: #ffffff;
    --fond-succes: #ffffff;
  }
  @page { margin: 15mm; }
  .no-print { display: none !important; }
  body {
    padding: 0;
    background: #ffffff;
    color: var(--texte);
    font-size: 10.5pt;
  }
  .page { max-width: none; }
  .entete {
    background: #ffffff;
    color: var(--texte);
    border: 0;
    border-bottom: 2pt solid var(--texte);
    border-radius: 0;
    padding: 0 0 0.6rem;
  }
  .entete-marque, .entete-sous-titre, .entete-date, .meta dt { opacity: 1; }
  .entete .meta .lien { color: var(--accent); }
  .section, .resume, .sommaire, .bilan-carte, .constat, .score, .diff,
  .tableau-defilant {
    background: #ffffff;
    box-shadow: none;
  }
  .section { border: 0; border-top: 1pt solid var(--bordure); border-radius: 0;
             padding: 0.6rem 0 0; margin-bottom: 1rem; }
  .badge {
    background: #ffffff;
    color: var(--sev);
    border: 1pt solid var(--sev);
  }
  .jauge { border: 1pt solid var(--texte); background: #ffffff; }
  .jauge-barre { background: var(--texte); }
  .tableau-defilant { overflow: visible; }
  .tableau-defilant table { min-width: 0; font-size: 9pt; }
  th { background: #ffffff; color: var(--texte); border-bottom: 1pt solid var(--texte); }
  .constat, .score, .reco, .bilan-carte, tr, .diff { break-inside: avoid;
                                                     page-break-inside: avoid; }
  h1, h2, h3 { break-after: avoid; page-break-after: avoid; }
  .lien { color: var(--texte); }
  a[href^="http"]::after {
    content: " (" attr(href) ")";
    font-size: 0.85em;
    word-break: break-all;
  }
}
""".replace('FAMILLE_POLICE', _POLICES)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def render_report(report: dict) -> str:
    """Render a complete, self-contained HTML document from a report dict.

    Nothing outside the returned string is needed to display it: no stylesheet,
    no font, no image, no script. Printing is the browser's job, which is the
    whole point of the port; a server-side PDF engine would drag native
    libraries into a nixpacks build for no gain.

    Accepted structure, every key optional, French or English spelling:

        {
          'titre' | 'title': str,
          'sous_titre' | 'subtitle': str,
          'date': str,                     # free text, defaults to now (UTC)
          'marque' | 'brand': str,         # defaults to 'Gridar'
          'meta': dict | [{'libelle', 'valeur'}] | [(libelle, valeur)],
          'resume' | 'summary': str,
          'score': number | {'valeur', 'sur', 'libelle', 'detail', 'severite'},
          'sections': [
            {
              'titre': str,
              'resume' | 'description': str,
              'score': number | dict,
              'tableau' | 'table': {
                 'colonnes': [str | {'cle', 'libelle'}],
                 'lignes': [[cell, ...] | {col: cell}],
                 'legende': str,
              },
              'constats' | 'findings': [
                 str | {'severite', 'titre', 'message', 'details',
                        'avant', 'apres', 'url', 'correctif'}
              ],
              'recommandations': [str | {'texte', 'priorite', 'detail',
                                         'effort', 'url'}],
              'notes': [str],
            }
          ],
          'pied' | 'footer': str,
        }

    Severity accepts any spelling used in this app (`critical`, `high`,
    `warning`, `hard_stop`, `elevee`); see `normalize_severite`. A cell may be a
    dict carrying its own severity to be shown as a chip. Values of any type are
    flattened rather than refused, and every one of them is HTML-escaped.
    """
    donnees = report if isinstance(report, dict) else {}

    marque = _texte(_cle(donnees, 'marque', 'brand', defaut='Gridar'), 80)
    titre = _texte(_cle(donnees, 'titre', 'title', defaut=''), _MAX_TITRE) or 'Rapport SEO'
    sous_titre = _cle(donnees, 'sous_titre', 'subtitle', 'sous-titre', defaut='')
    date = _cle(donnees, 'date', 'genere_le', 'generated_at', 'horodatage',
                defaut=None)
    if date is None:
        date = _date_fr(datetime.now(timezone.utc))
    resume = _cle(donnees, 'resume', 'summary', 'intro', 'chapeau', defaut='')
    pied = _cle(donnees, 'pied', 'footer', 'pied_de_page', defaut='')

    sections_brutes = _liste(_cle(donnees, 'sections', 'blocs', defaut=[]))
    sections = [_lire_section(s) for s in sections_brutes[:_MAX_SECTIONS]]
    ancres = [f'section-{index + 1}' for index in range(len(sections))]

    compte = Counter({severite: 0 for severite in SEVERITES})
    for lue in sections:
        for constat in lue['constats']:
            compte[constat['severite']] += 1

    titre_page = f'{titre} | {marque}' if marque else titre

    parties = [
        '<!DOCTYPE html>',
        '<html lang="fr">',
        '<head>',
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        # A client report handed out over a link has no business being indexed.
        '<meta name="robots" content="noindex, nofollow">',
        '<meta name="color-scheme" content="light">',
        f'<title>{_esc(titre_page, 400)}</title>',
        f'<style>{_CSS}</style>',
        '</head>',
        '<body>',
        '<div class="barre no-print">Pour obtenir un PDF : ouvrez le menu '
        'd\'impression du navigateur (Ctrl+P ou Cmd+P), puis choisissez '
        '« Enregistrer en PDF ».</div>',
        '<div class="page">',
        '<header class="entete">',
    ]
    if marque:
        parties.append(f'<p class="entete-marque">{_esc(marque, 80)}</p>')
    parties.append(f'<h1>{_esc(titre, _MAX_TITRE)}</h1>')
    if sous_titre:
        parties.append(f'<p class="entete-sous-titre">{_esc(sous_titre, 600)}</p>')
    parties.append(f'<p class="entete-date">{_esc(date, 200)}</p>')
    parties.append(_bloc_meta(_cle(donnees, 'meta', 'metadonnees', 'metadata',
                                   defaut=None)))
    parties.append('</header>')

    if resume:
        parties.append(f'<div class="resume">{_esc_multi(resume)}</div>')

    parties.append(_bloc_score(_cle(donnees, 'score', 'note', defaut=None)))
    parties.append(_bloc_bilan(compte))
    parties.append(_bloc_sommaire(sections, ancres))

    for lue, ancre in zip(sections, ancres):
        parties.append(_bloc_section(lue, ancre))

    parties.append('<footer class="pied">')
    if pied:
        parties.append(f'<p>{_esc_multi(pied, 2000)}</p>')
    else:
        parties.append(
            f'<p>Rapport produit par {_esc(marque, 80) or "Gridar"}. Les constats '
            'reflètent l\'état du site au moment de l\'analyse.</p>'
        )
    parties.append(f'<p>{_esc(date, 200)}</p>')
    parties.append('</footer>')
    parties.append('</div>')
    parties.append('</body>')
    parties.append('</html>')

    return '\n'.join(part for part in parties if part)
