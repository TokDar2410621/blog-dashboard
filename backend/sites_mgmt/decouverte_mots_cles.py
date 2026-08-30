"""Decouverte de mots-cles sur lesquels un site n'apparait PAS encore.

Le probleme
-----------
Search Console ne montre que les requetes ou le site apparait deja : parfait
pour reperer les positions 4 a 15 a recuperer, aveugle pour tout le reste.
Et le volume de recherche n'est pas disponible : l'endpoint `/search-volume`
de Serper rend `500 Scraping failed` (verifie en prod le 2026-08-27 sur
toutes les formes de requete ; `q` est bien le parametre attendu, l'echec est
cote Serper). Google Keyword Planner donnerait des fourchettes de sept
paliers geants sans campagne publicitaire active, ce qui n'arbitre rien.

Ce que ce module mesure a la place
----------------------------------
Trois faits verifiables, sans aucun chiffre invente :

1. **Google suggere la requete.** L'autocompletion ne propose que ce que les
   gens tapent reellement. C'est une preuve d'existence de la demande, pas
   une mesure de son volume, et le module ne pretend jamais le contraire.
2. **L'intention est commerciale**, jugee sur la page de resultats reelle
   (voir `filtrer_intention_commerciale`), pas sur la formulation.
3. **Le site est ABSENT du top 10**, constate dans un SERP reellement
   interroge, et des concurrents identifies y sont presents.

Un mot-cle qui coche les trois est une occasion documentee. Sans volume, le
classement se fait sur la presence des concurrents : une requete que ton
marche occupe et pas toi vaut mieux qu'une requete que personne ne dispute.

Cout
----
Un credit Serper par appel d'autocompletion, un par SERP verifie. Les deux
sont plafonnes et le compte est rendu dans le resultat : un pipeline qui
depense sans le dire est un pipeline qu'on finit par couper.
"""
import logging
from concurrent.futures import ThreadPoolExecutor

import requests as http_requests

logger = logging.getLogger(__name__)

# Suffixes d'expansion. Les lettres seules font remonter des completions que
# la racine nue ne donne pas (technique standard) ; les modificateurs
# d'intention orientent vers l'achat plutot que vers la definition.
_SUFFIXES = (
    '',
    'a', 'b', 'c', 'd', 'e', 'f', 'g', 'm', 'p', 'r', 's', 't',
    'prix', 'tarif', 'meilleur', 'pres de moi', 'comparatif', 'pour entreprise',
)


def elargir_par_autocomplete(semences: list[str], langue: str = 'fr',
                             pays: str = 'ca', max_appels: int = 80,
                             max_workers: int = 8) -> tuple[list[str], int]:
    """Etend des semences via Google Suggest. Rend (mots_cles, credits_depenses).

    Google ne suggere que ce qui est reellement tape : chaque suggestion est
    donc une requete qui existe. Mesure du 2026-08-27 : 4 semences et 13
    suffixes ont produit 221 mots-cles uniques pour 52 credits.
    """
    import os

    cle = os.environ.get('SERPER_API_KEY')
    if not cle or not semences:
        return [], 0

    requetes = [f'{s} {suf}'.strip()
                for s in semences for suf in _SUFFIXES][:max_appels]

    def suggerer(question):
        try:
            r = http_requests.post(
                'https://google.serper.dev/autocomplete',
                headers={'X-API-KEY': cle, 'Content-Type': 'application/json'},
                json={'q': question, 'gl': pays, 'hl': langue},
                timeout=12,
            )
            if r.status_code != 200:
                return []
            return [s.get('value', '') for s in (r.json().get('suggestions') or [])]
        except Exception:
            return []

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        lots = list(pool.map(suggerer, requetes))

    vus, sortie = set(), []
    for lot in lots:
        for suggestion in lot:
            nettoye = ' '.join(str(suggestion or '').split()).lower()
            # Deux mots minimum : une requete d'un seul mot est trop large
            # pour qu'une PME locale la dispute utilement.
            if nettoye and len(nettoye.split()) >= 2 and nettoye not in vus:
                vus.add(nettoye)
                sortie.append(nettoye)
    return sortie, len(requetes)


def decouvrir_mots_cles_absents(domaine: str, semences: list[str],
                                max_verifications: int = 60,
                                langue: str = 'fr', pays: str = 'ca') -> dict:
    """Mots-cles ou `domaine` n'apparait pas encore, avec leurs preuves.

    Enchaine : expansion par autocompletion, verification SERP, filtre
    d'intention, puis separation entre les requetes ou le site est present et
    celles ou il est absent.

    Rend un dict qui expose TOUJOURS ce qui a ete depense et ce qui a ete
    ecarte, pour qu'un resultat maigre se lise comme un resultat maigre et
    non comme une mesure incomplete.
    """
    from .compare_mesures import (
        collecter_serps, decouvrir_concurrents, filtrer_intention_commerciale,
    )

    domaine = (domaine or '').lower().removeprefix('www.')
    candidats, credits_autocomplete = elargir_par_autocomplete(
        semences, langue=langue, pays=pays)
    if not candidats:
        return {
            'domaine': domaine, 'occasions': [], 'deja_present': [],
            'ecartees_intention': [],
            'credits': {'autocomplete': credits_autocomplete, 'serp': 0,
                        'total': credits_autocomplete},
            'note': "L'autocompletion n'a rien rendu (cle Serper absente ou "
                    "semences vides).",
        }

    a_verifier = candidats[:max_verifications]
    serps = collecter_serps(a_verifier)
    if not serps:
        return {
            'domaine': domaine, 'occasions': [], 'deja_present': [],
            'ecartees_intention': [],
            'credits': {'autocomplete': credits_autocomplete,
                        'serp': len(a_verifier),
                        'total': credits_autocomplete + len(a_verifier)},
            'note': "Aucune page de resultats n'a pu etre obtenue.",
        }

    serps, ecartees = filtrer_intention_commerciale(serps)
    concurrents = set(decouvrir_concurrents(serps, domaine, maximum=6))

    occasions, deja_present = [], []
    for s in serps:
        hotes = {h for h, _ in s.get('hotes', [])}
        occupants = [
            {'domain': r['hote'], 'position': r['position']}
            for r in (s.get('resultats') or [])[:5]
        ]
        if domaine in hotes:
            rang = next((r['position'] for r in (s.get('resultats') or [])
                         if r['hote'] == domaine), None)
            deja_present.append({'keyword': s['requete'], 'position': rang})
            continue
        rivaux = [o for o in occupants if o['domain'] in concurrents]
        occasions.append({
            'keyword': s['requete'],
            # Preuves, pas estimations. Chacune est verifiable par
            # l'utilisateur en tapant la requete lui-meme.
            'evidence': {
                'suggere_par_google': True,
                'intention_commerciale': True,
                'site_absent_du_top_10': True,
                'concurrents_presents': [r['domain'] for r in rivaux],
            },
            'occupants': occupants,
            # Un mot-cle que TON marche occupe vaut mieux qu'un que personne
            # ne dispute : c'est le seul classement defendable sans volume.
            'rivaux': len(rivaux),
        })

    occasions.sort(key=lambda o: (-o['rivaux'], o['keyword']))
    return {
        'domaine': domaine,
        'occasions': occasions,
        'deja_present': deja_present,
        'ecartees_intention': ecartees,
        'concurrents_identifies': sorted(concurrents),
        'credits': {
            'autocomplete': credits_autocomplete,
            'serp': len(a_verifier),
            'total': credits_autocomplete + len(a_verifier),
        },
        'note': (
            'Aucun volume de recherche : il est indisponible sur ce plan '
            'Serper. Le classement repose sur la presence des concurrents '
            'identifies, pas sur une estimation de trafic.'
        ),
    }
