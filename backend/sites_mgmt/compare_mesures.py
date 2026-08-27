"""Mesures reelles pour la comparaison de deux domaines.

Pourquoi ce module existe
-------------------------
`PublicCompetitorCompareView` demandait a Gemini d'inventer six scores sur 100
a partir de trois champs texte (title, H1, meta description). Aucune des six
categories n'etait mesuree. "Autorite percue", "Presence IA" et "Strategie
locale" n'avaient meme pas de donnee d'entree : le modele produisait un
chiffre parce que le schema JSON en exigeait un.

Ici, chaque categorie est branchee sur une mesure. Le LLM garde un role, mais
il est retrograde : il ecrit le recit autour des chiffres mesures, il ne les
produit plus.

Le contrat d'une mesure
-----------------------
Toute fonction `mesurer_*` rend la meme forme :

    {
        'score': int | None,      # 0-100, None quand rien n'est mesurable
        'disponible': bool,
        'source': 'mesure' | 'indisponible',
        'preuves': list[str],     # ce qui a ete constate, lisible par un humain
        'raison': str | None,     # pourquoi c'est indisponible, le cas echeant
    }

`score: None` est un resultat legitime, pas un echec. Une categorie
honnetement vide vaut mieux qu'un score invente : c'est exactement le defaut
qu'on corrige. Aucune mesure ne retombe jamais sur une estimation LLM.

Deux principes d'equite
-----------------------
1. **Les deux domaines sont mesures sur les MEMES entrees.** Les requetes
   testees sont l'union dedupliquee de celles des deux sites, jamais celles
   d'un seul (`PublicCompetitorGapView` n'utilise que celles de la cible, ce
   qui la favorise structurellement).
2. **Un seul appel externe sert les deux domaines** partout ou c'est possible.
   Gemini ne recoit pas le domaine dans son prompt, et un SERP contient les
   deux sites : on lit la meme reponse pour les deux. Cout divise par deux, et
   surtout comparaison faite sur un texte identique plutot que sur deux
   generations differentes.
"""
import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests as http_requests

logger = logging.getLogger(__name__)

# Un ecart plus petit que ca, sur une mesure bruitee, ne designe pas un
# gagnant : il designe du bruit. Voir `departager`.
ECART_MINIMAL_SIGNIFICATIF = 15


def _indisponible(raison: str) -> dict:
    """Forme canonique d'une categorie qu'on n'a pas pu mesurer."""
    return {
        'score': None,
        'disponible': False,
        'source': 'indisponible',
        'preuves': [],
        'raison': raison,
    }


def _mesure(score: float, preuves: list[str]) -> dict:
    """Forme canonique d'une categorie mesuree."""
    return {
        'score': max(0, min(100, int(round(score)))),
        'disponible': True,
        'source': 'mesure',
        'preuves': [p for p in preuves if p],
        'raison': None,
    }


def departager(score_a, score_b) -> str:
    """Rend 'domain', 'competitor' ou 'tie'.

    Refuse de designer un gagnant sous `ECART_MINIMAL_SIGNIFICATIF`. Sur des
    mesures bruitees (un taux de mention sur 12 requetes porte une marge
    d'erreur d'environ 10 points), un ecart de 3 points n'est pas un resultat.
    Annoncer un vainqueur la-dessus, c'est refabriquer la fausse precision
    qu'on vient de retirer.

    Rend 'tie' aussi quand une des deux mesures manque : on ne compare pas un
    chiffre a une absence.
    """
    if score_a is None or score_b is None:
        return 'tie'
    if abs(score_a - score_b) < ECART_MINIMAL_SIGNIFICATIF:
        return 'tie'
    return 'domain' if score_a > score_b else 'competitor'


# ---------------------------------------------------------------------------
# PageSpeed : un seul appel par domaine alimente deux categories
# ---------------------------------------------------------------------------
_PSI_ENDPOINT = 'https://www.googleapis.com/pagespeedonline/v5/runPagespeed'


def mesurer_pagespeed(url: str, timeout: int = 45) -> dict | None:
    """Un appel PSI, trois categories Lighthouse plus deux metriques de labo.

    Demander trois categories au lieu d'une ne change quasiment rien a la
    latence : Lighthouse fait une seule collecte puis derive les audits. Le
    meme aller-retour alimente donc "UX et design" (performance,
    accessibilite) et une partie de "SEO technique" (seo).

    Rend None si la cle manque ou si l'appel echoue. Un score de categorie
    absent reste None et ne devient JAMAIS zero : les quatre appels PSI de
    views.py font `(... or 0)`, ce qui transforme une categorie manquante en
    zero mesure. Sur un audit mono-domaine c'est deja discutable ; sur une
    comparaison, un zero fantome fait perdre la categorie au concurrent et
    rend le verdict faux sur le site de quelqu'un d'autre. On reprend donc la
    version correcte, celle de `PageSpeedView` (views.py:2521).

    Le resultat est cache 24 h. Mesure faite en prod le 2026-08-25 : PSI est
    erratique, la meme URL passe de 9 s a plus de 75 s d'un appel a l'autre et
    Lighthouse renvoie par intermittence un HTTP 500. A 45 s de timeout, c'est
    a peu pres pile ou face. Un cache long est la reponse la moins couteuse :
    la performance d'un site ne change pas d'une minute a l'autre, donc un
    succes profite a tous les appels suivants sur le meme domaine. Seuls les
    succes sont caches, un echec doit pouvoir etre retente.
    """
    from django.core.cache import cache as cache_django

    cle_cache = f'psi:v1:{url}'
    en_cache = cache_django.get(cle_cache)
    if en_cache is not None:
        return en_cache

    cle = os.environ.get('PAGESPEED_API_KEY')
    if not cle:
        return None
    try:
        r = http_requests.get(
            _PSI_ENDPOINT,
            params={
                'url': url,
                'strategy': 'mobile',
                'category': ['performance', 'seo', 'accessibility'],
                'key': cle,
            },
            timeout=timeout,
        )
        if r.status_code != 200:
            logger.info('PSI HTTP %s pour %s', r.status_code, url)
            return None
        lh = r.json().get('lighthouseResult') or {}
    except Exception as e:
        logger.info('PSI indisponible pour %s: %s', url, str(e)[:120])
        return None

    categories = lh.get('categories') or {}
    audits = lh.get('audits') or {}

    def note(cle_cat):
        cat = categories.get(cle_cat) or {}
        valeur = cat.get('score')
        return None if valeur is None else round(float(valeur) * 100)

    def metrique(cle_audit):
        audit = audits.get(cle_audit) or {}
        valeur = audit.get('numericValue')
        return None if valeur is None else float(valeur)

    lcp = metrique('largest-contentful-paint')
    cls = metrique('cumulative-layout-shift')
    resultat = {
        'performance': note('performance'),
        'seo': note('seo'),
        'accessibilite': note('accessibility'),
        'lcp_s': None if lcp is None else round(lcp / 1000, 2),
        'cls': None if cls is None else round(cls, 3),
    }
    cache_django.set(cle_cache, resultat, timeout=86400)
    return resultat


# ---------------------------------------------------------------------------
# Categorie : SEO technique
# ---------------------------------------------------------------------------
def mesurer_seo_technique(onpage_a: dict | None, psi_a: dict | None,
                          onpage_b: dict | None, psi_b: dict | None
                          ) -> tuple[dict, dict]:
    """Signaux on-page mesures, plus la note SEO de Lighthouse.

    `onpage` vient de `_score_onpage` (views.py) : huit controles deterministes
    sur 100 (title, meta description, H1, hierarchie, JSON-LD). Deterministe
    veut dire que deux domaines sont reellement comparables, contrairement a un
    chiffre genere.

    Les deux domaines sont notes sur les MEMES composantes. La note Lighthouse
    n'entre dans le calcul que si elle existe des DEUX cotes : sinon un site
    serait note sur ses seuls signaux on-page pendant que l'autre recoit une
    moyenne on-page + Lighthouse. Constate en prod le 2026-08-25, PageSpeed
    ayant repondu pour un domaine et pas pour l'autre : 90 d'un cote (on-page
    seul) contre 58 de l'autre (moyenne de 15 et d'un Lighthouse quasi
    parfait). Deux echelles differentes presentees comme un ecart.
    """
    def preuves_onpage(onpage):
        if not onpage or onpage.get('score') is None:
            return []
        lignes = [f"{onpage['score']}/100 sur 8 controles on-page"]
        rates = [c['libelle'] for c in onpage.get('controles', []) if not c.get('reussi')]
        if rates:
            lignes.append('Manque : ' + ', '.join(rates[:4]))
        return lignes

    score_a = onpage_a.get('score') if onpage_a else None
    score_b = onpage_b.get('score') if onpage_b else None
    if score_a is None or score_b is None:
        manquant = "La page n'a pas pu etre lue."
        return _indisponible(manquant), _indisponible(manquant)

    seo_a = (psi_a or {}).get('seo')
    seo_b = (psi_b or {}).get('seo')
    lighthouse_des_deux_cotes = seo_a is not None and seo_b is not None

    def noter(score_onpage, seo, lignes):
        if lighthouse_des_deux_cotes:
            lignes = lignes + [f'Lighthouse SEO : {seo}/100']
            return _mesure((score_onpage + seo) / 2, lignes)
        return _mesure(score_onpage, lignes)

    return (noter(score_a, seo_a, preuves_onpage(onpage_a)),
            noter(score_b, seo_b, preuves_onpage(onpage_b)))


# ---------------------------------------------------------------------------
# Categorie : UX et design
# ---------------------------------------------------------------------------
def mesurer_ux(psi: dict | None) -> dict:
    """Core Web Vitals mesurees, pas une impression esthetique.

    Le nom de la categorie parle de design, mais rien ici ne juge le gout. On
    mesure ce qu'un visiteur subit : vitesse de rendu, stabilite visuelle,
    accessibilite. C'est ce que Google mesure aussi.
    """
    if not psi:
        return _indisponible('PageSpeed indisponible (cle absente ou quota).')

    perf, a11y = psi.get('performance'), psi.get('accessibilite')
    if perf is None and a11y is None:
        return _indisponible("Lighthouse n'a rendu aucune note exploitable.")

    preuves = []
    if psi.get('lcp_s') is not None:
        preuves.append(f"Affichage du contenu principal : {psi['lcp_s']} s")
    if psi.get('cls') is not None:
        preuves.append(f"Stabilite visuelle (CLS) : {psi['cls']}")
    if perf is not None:
        preuves.append(f"Performance : {perf}/100")
    if a11y is not None:
        preuves.append(f"Accessibilite : {a11y}/100")

    if perf is not None and a11y is not None:
        score = perf * 0.6 + a11y * 0.4
    else:
        score = perf if perf is not None else a11y
    return _mesure(score, preuves)


# ---------------------------------------------------------------------------
# Categorie : Presence IA
# ---------------------------------------------------------------------------
_GEMINI_URL = (
    'https://generativelanguage.googleapis.com/v1beta/models/'
    'gemini-2.5-flash:generateContent'
)


def _demander_gemini(question: str, timeout: int = 20) -> str | None:
    """Pose une question a Gemini et rend le texte, ou None sur echec.

    Deux differences volontaires avec `_check_ai_mention` (views_tools.py:549),
    qui a deux chemins de zero silencieux :

    1. Un statut non-200 rend None, pas une reponse vide. Chez
       `_check_ai_mention`, tout est enferme dans `if r.status_code == 200:`
       sans `else` et sans `raise_for_status`, seul appel Gemini du fichier
       dans ce cas. Quota epuise (429) = `mentioned: False` pour tout le
       monde, indiscernable d'un vrai "l'IA ne cite pas ce site". Sur une
       comparaison ca donnerait 0 contre 0, un match nul muet.

    2. `thinkingBudget: 0`. Sur gemini-2.5-flash le thinking est actif par
       defaut et ses jetons comptent dans `maxOutputTokens`. Avec un budget de
       500, la reflexion mange l'enveloppe, la reponse revient en
       `finishReason: MAX_TOKENS` avec un `content` sans cle `parts`, et le
       KeyError est avale plus haut. Deuxieme zero silencieux, intermittent
       donc plus difficile a voir que le premier.
    """
    cle = os.environ.get('GEMINI_API_KEY')
    if not cle:
        return None
    try:
        r = http_requests.post(
            _GEMINI_URL,
            params={'key': cle},
            json={
                'contents': [{'parts': [{'text': question}]}],
                'generationConfig': {
                    'maxOutputTokens': 700,
                    'thinkingConfig': {'thinkingBudget': 0},
                },
            },
            timeout=timeout,
        )
        if r.status_code != 200:
            logger.info('Gemini HTTP %s sur une requete de comparaison', r.status_code)
            return None
        parts = (r.json().get('candidates') or [{}])[0] \
            .get('content', {}).get('parts') or []
        texte = ''.join(p.get('text', '') for p in parts).strip()
        return texte or None
    except Exception as e:
        logger.info('Gemini indisponible : %s', str(e)[:120])
        return None


def _cite_le_domaine(texte: str, domaine: str) -> bool:
    """Cherche le domaine dans une reponse d'IA, sans faux positif evident.

    On teste le domaine complet (exemple.com) et sa racine de marque
    (exemple), la racine seulement en mot entier pour ne pas faire matcher
    "notion" dans "notionnel".
    """
    bas = texte.lower()
    domaine = domaine.lower().removeprefix('www.')
    if domaine in bas:
        return True
    racine = domaine.split('.')[0]
    if len(racine) < 4:
        return False
    return re.search(rf'\b{re.escape(racine)}\b', bas) is not None


def mesurer_presence_ia(requetes: list[str], domaine_a: str, domaine_b: str,
                        max_workers: int = 5) -> tuple[dict, dict]:
    """Interroge l'IA une seule fois par requete, lit les DEUX domaines dedans.

    Le prompt de `_check_ai_mention` est litteralement la requete : le domaine
    n'y figure pas. Appeler la fonction deux fois par requete ferait donc deux
    appels identiques dont les reponses different (aucune temperature fixee),
    ce qui compare deux textes differents et double la facture. Une seule
    reponse lue pour les deux sites coute moitie moins et compare enfin la
    meme chose.

    Le score est le taux de mention sur les requetes reellement obtenues. Les
    requetes dont l'appel a echoue sortent du denominateur, elles ne comptent
    pas comme des absences.
    """
    from .moteurs_ia import LIBELLES, formuler, interroger, moteurs_configures

    if not requetes:
        return _indisponible('Aucune requete a tester.'), _indisponible('Aucune requete a tester.')

    moteurs = moteurs_configures()
    if not moteurs:
        indispo = _indisponible("Aucun moteur d'IA configure.")
        return indispo, indispo

    # Une reponse par couple (moteur, requete), et chacune sert les DEUX
    # domaines : la question posee ne contient pas le domaine, donc relancer
    # par domaine paierait deux fois pour comparer deux textes differents.
    travaux = [(m, q) for m in moteurs for q in requetes]
    obtenues, echecs = {}, {}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futurs = {pool.submit(interroger, m, formuler(q)): (m, q)
                  for m, q in travaux}
        for fut in as_completed(futurs):
            cle = futurs[fut]
            try:
                r = fut.result()
            except Exception:
                r = {'disponible': False, 'raison': 'Appel interrompu.'}
            if r.get('disponible'):
                obtenues[cle] = r['texte']
            else:
                echecs.setdefault(cle[0], r.get('raison') or 'Indisponible.')

    if not obtenues:
        detail = ' '.join(f'{LIBELLES.get(m, m)} : {r}' for m, r in echecs.items())
        indispo = _indisponible(
            ("Aucune reponse d'IA obtenue. " + detail).strip())
        return indispo, indispo

    # Les moteurs qui n'ont pas repondu sortent du denominateur. Les compter
    # comme des non-mentions ferait chuter le score pour une panne.
    repondants = sorted({m for m, _ in obtenues})
    libelles = ', '.join(LIBELLES.get(m, m) for m in repondants)

    def noter(domaine):
        cites = [q for (m, q), t in obtenues.items() if _cite_le_domaine(t, domaine)]
        taux = len(cites) / len(obtenues) * 100
        preuves = [
            f'Cite dans {len(cites)} reponse(s) sur {len(obtenues)} obtenue(s)',
            f'Moteurs interroges : {libelles}',
        ]
        if cites:
            preuves.append('Par exemple : ' + cites[0])
        if echecs:
            preuves.append('Non joignable : ' + ', '.join(
                LIBELLES.get(m, m) for m in sorted(echecs)))
        return _mesure(taux, preuves)

    return noter(domaine_a), noter(domaine_b)


# ---------------------------------------------------------------------------
# SERP partage : une passe Serper alimente Contenu et Autorite pour les deux
# ---------------------------------------------------------------------------
def _hote(lien: str) -> str:
    hote = (lien or '').lower().split('://', 1)[-1].split('/', 1)[0]
    return hote.removeprefix('www.')


def collecter_serps(requetes: list[str], max_workers: int = 8) -> list[dict] | None:
    """Un appel Serper par requete, TOUS les resultats organiques conserves.

    C'est la primitive partagee par les outils qui ont besoin de lire un SERP.
    Un seul SERP contient tout le monde : le site analyse, ses concurrents,
    les annuaires. Le lire une fois et en deriver ce dont chaque outil a
    besoin coute une requete la ou l'ancien code en depensait une par domaine
    et par mot-cle.

    Chaque resultat porte un `verifie` explicite. Un non-200 ne doit jamais se
    confondre avec "le site ne se classe pas" : sans ce drapeau, une panne de
    quota annonce au visiteur que son site n'est nulle part.

    Rend None quand la cle manque ou qu'AUCUN SERP n'a pu etre obtenu, pour
    que l'appelant distingue "rien trouve" de "rien regarde".
    """
    cle = os.environ.get('SERPER_API_KEY')
    if not cle or not requetes:
        return None

    def une_requete(question):
        try:
            r = http_requests.post(
                'https://google.serper.dev/search',
                headers={'X-API-KEY': cle, 'Content-Type': 'application/json'},
                # num reste a 10 : au-dela le parametre est silencieusement
                # plafonne (verifie 2026-08-25 : num=20 rend 200 avec 8
                # resultats). Pour aller plus loin il faut paginer.
                json={'q': question, 'num': 10, 'hl': 'fr', 'gl': 'ca'},
                timeout=8,
            )
            if r.status_code != 200:
                return {'requete': question, 'verifie': False}
            organiques = r.json().get('organic') or []
            return {
                'requete': question,
                'verifie': True,
                'hotes': [(_hote(o.get('link')), o.get('position') or 0)
                          for o in organiques],
                'resultats': [
                    {
                        'hote': _hote(o.get('link')),
                        'position': o.get('position') or 0,
                        'url': o.get('link') or '',
                        'titre': o.get('title') or '',
                    }
                    for o in organiques
                ],
            }
        except Exception:
            return {'requete': question, 'verifie': False}

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        resultats = list(pool.map(une_requete, requetes))

    verifies = [r for r in resultats if r.get('verifie')]
    return verifies or None


def sonder_serp(requetes: list[str], domaine_a: str, domaine_b: str,
                max_workers: int = 8) -> dict | None:
    """Positions des DEUX domaines, extraites des memes SERP.

    Quinze requetes coutent quinze credits pour les deux domaines, pas quinze
    chacun, et surtout les deux sites sont compares sur des pages de resultats
    identiques plutot que sur deux interrogations separees.
    """
    verifies = collecter_serps(requetes, max_workers=max_workers)
    if not verifies:
        return None

    def positions(domaine):
        trouvees = {}
        for r in verifies:
            for hote, rang in r['hotes']:
                if hote == domaine:
                    trouvees[r['requete']] = rang
                    break
        return trouvees

    return {
        'requetes_verifiees': [r['requete'] for r in verifies],
        'positions_a': positions(domaine_a),
        'positions_b': positions(domaine_b),
    }


def _noter_serp(positions: dict, total: int, etiquette: str) -> dict:
    """Largeur de positionnement plus qualite des rangs obtenus."""
    if not total:
        return _indisponible('Aucun SERP verifie.')
    largeur = len(positions) / total * 100
    if positions:
        qualite = sum(max(0, 100 - (rang - 1) * 10) for rang in positions.values()) / len(positions)
    else:
        qualite = 0
    preuves = [f'Present dans {len(positions)} SERP sur {total} testes ({etiquette})']
    if positions:
        meilleur = min(positions.items(), key=lambda kv: kv[1])
        preuves.append(f'Meilleure position : #{meilleur[1]} sur "{meilleur[0]}"')
    return _mesure(largeur * 0.6 + qualite * 0.4, preuves)


def mesurer_contenu(serp: dict | None, pages_a: int | None, pages_b: int | None
                    ) -> tuple[dict, dict]:
    """Largeur de positionnement, complete par l'empreinte indexee.

    Ce que Serper permet vraiment de dire sur le contenu : sur combien de
    requetes reelles le site apparait, a quel rang, et combien de pages il a
    d'indexees. Pas la qualite editoriale, qui n'est pas mesurable ici.
    """
    if not serp:
        indispo = _indisponible('Donnees SERP indisponibles.')
        return indispo, indispo

    total = len(serp['requetes_verifiees'])
    a = _noter_serp(serp['positions_a'], total, 'requetes communes')
    b = _noter_serp(serp['positions_b'], total, 'requetes communes')

    for mesure, pages in ((a, pages_a), (b, pages_b)):
        if mesure['disponible'] and pages is not None:
            mesure['preuves'].append(f'{pages} page(s) indexee(s) reperee(s)')
    return a, b


def mesurer_autorite(serp: dict | None, hotes_a: int | None, hotes_b: int | None
                     ) -> tuple[dict, dict]:
    """Dominance sur le SERP partage, plus les domaines qui mentionnent la marque.

    Ce n'est PAS une mesure de backlinks et ne doit jamais etre presentee
    comme telle. Serper n'expose aucun graphe de liens, `link:` est retire par
    Google depuis longtemps, et une mention n'est pas un lien. Le repo s'est
    deja brule dessus : une ancienne cle `total_referring_domains` alimentait
    15 % d'un score composite sur cette affirmation fausse.
    """
    if not serp:
        indispo = _indisponible('Donnees SERP indisponibles.')
        return indispo, indispo

    total = len(serp['requetes_verifiees'])
    if not total:
        return _indisponible('Aucun SERP verifie.'), _indisponible('Aucun SERP verifie.')

    # Le compte de mentions n'entre dans le calcul que s'il existe des DEUX
    # cotes, sinon un domaine serait note sur sa seule dominance SERP pendant
    # que l'autre recoit un melange dominance + mentions : deux echelles
    # differentes presentees comme un ecart.
    mentions_des_deux_cotes = hotes_a is not None and hotes_b is not None

    def noter(positions, hotes):
        # Presence en top 3 : le vrai signal de dominance sur une requete.
        top3 = sum(1 for rang in positions.values() if 1 <= rang <= 3)
        dominance = top3 / total * 100
        preuves = [f'Top 3 sur {top3} des {total} requetes communes']
        if mentions_des_deux_cotes:
            preuves.append(
                f'{hotes} domaine(s) distinct(s) mentionnent la marque '
                '(mentions, pas des liens entrants ; mesure saturee a 10)'
            )
            # Sature a 10 : une seule page de SERP est lue, on ne peut pas
            # distinguer 10 hotes de 400.
            return _mesure(dominance * 0.7 + min(100, hotes * 10) * 0.3, preuves)
        return _mesure(dominance, preuves)

    return noter(serp['positions_a'], hotes_a), noter(serp['positions_b'], hotes_b)


def compter_hotes_mentionnant(marque: str, domaine: str) -> int | None:
    """Combien de domaines distincts parlent de la marque, hors son propre site.

    Un credit Serper. Sature a 10 par construction (une page de resultats).
    """
    cle = os.environ.get('SERPER_API_KEY')
    if not cle or not marque or len(marque) < 2:
        return None
    try:
        r = http_requests.post(
            'https://google.serper.dev/search',
            headers={'X-API-KEY': cle, 'Content-Type': 'application/json'},
            json={'q': f'"{marque}" -site:{domaine}', 'num': 10, 'hl': 'fr', 'gl': 'ca'},
            timeout=8,
        )
        if r.status_code != 200:
            return None
        hotes = {_hote(o.get('link')) for o in (r.json().get('organic') or [])}
        return len({h for h in hotes if h and h != domaine})
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Categorie : Strategie locale
# ---------------------------------------------------------------------------
def _blocs_jsonld(html: str) -> list:
    """Rend les objets JSON-LD de la page, `@graph` aplati.

    Le balisage structure est le seul endroit ou l'ancrage local d'une page se
    lit de facon FERMEE : schema.org definit `addressLocality`, `areaServed`,
    `telephone` et `openingHours`, et cette definition vaut pour tous les
    sites du monde, pas seulement pour ceux qu'on a deja croises.
    """
    import json as _json

    objets = []
    for bloc in re.findall(
        r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>',
        html or '', re.I | re.DOTALL,
    ):
        try:
            data = _json.loads(bloc.strip())
        except Exception:
            continue
        file = data if isinstance(data, list) else [data]
        while file:
            item = file.pop()
            if not isinstance(item, dict):
                continue
            objets.append(item)
            graphe = item.get('@graph')
            if isinstance(graphe, list):
                file.extend(graphe)
    return objets


def _valeurs_imbriquees(objet, cle: str) -> list:
    """Toutes les valeurs trouvees sous `cle`, a n'importe quelle profondeur.

    schema.org autorise `address` en chaine, en objet ou en liste d'objets,
    donc on ne peut pas supposer une forme unique. Les nombres comptent aussi :
    `latitude` est souvent un float (`48.44`) et etait ignore quand seules les
    chaines etaient collectees.
    """
    trouvees = []
    file = [objet]
    while file:
        item = file.pop()
        if isinstance(item, dict):
            for k, v in item.items():
                if k.lower() == cle.lower():
                    if isinstance(v, bool):
                        continue          # un booleen n'est pas une valeur ici
                    if isinstance(v, (int, float)):
                        trouvees.append(str(v))
                    elif isinstance(v, str) and v.strip():
                        trouvees.append(v.strip())
                    elif isinstance(v, (dict, list)):
                        file.append(v)
                elif isinstance(v, (dict, list)):
                    file.append(v)
        elif isinstance(item, list):
            file.extend(item)
    return trouvees


def mesurer_strategie_locale(crawl: dict | None, html: str) -> dict:
    """Ancrage local lu dans le balisage structure de la page.

    Pourquoi PAS une liste de villes
    --------------------------------
    Une version precedente comparait le texte de la page a une liste de
    villes quebecoises codee en dur. Elle a ete retiree le 2026-08-25 : une
    liste ecrite a la main ne connait que les villes qu'on a pensees. Un
    commerce de Rimouski, de Val-d'Or ou de Gaspe absent de la liste se
    voyait afficher "Aucune ville nommee dans le contenu lu" comme PREUVE,
    donc une faussete presentee au visiteur a propos de son propre site. Une
    liste ne repare que les cas deja connus et ment sur tous les autres.

    Ce qui est lu ici vient de schema.org, un vocabulaire ferme et
    documente : `addressLocality`, `areaServed`, `telephone`,
    `openingHours`, `geo`. Cette definition vaut pour n'importe quel site, y
    compris ceux qu'on n'a jamais vus. C'est aussi exactement ce qu'un
    moteur de recherche lit pour comprendre l'ancrage local.

    On ne regarde PAS le `@type`. Une premiere version comparait le type a
    une liste (`LocalBusiness`, `Store`, `Restaurant`...), ce qui reintroduisait
    le meme defaut : schema.org compte environ 200 sous-types de
    `LocalBusiness`, et un plombier balise `Plumber` tombait a 65 au lieu de
    100. Ce sont les PROPRIETES qui portent le signal local, pas l'etiquette
    au-dessus. Un type invente demain fonctionnera donc sans changement.

    Consequence assumee : un commerce qui nomme sa ville en toutes lettres
    sans balisage marque bas. Le libelle le dit franchement (le balisage
    manque), ce qui est vrai et actionnable, au lieu d'affirmer a tort que
    la page ne cite aucun lieu.
    """
    if not crawl or crawl.get('error'):
        return _indisponible("La page n'a pas pu etre lue.")

    objets = _blocs_jsonld(html)
    localites, telephones, horaires, coordonnees = [], [], [], []
    for o in objets:
        localites += _valeurs_imbriquees(o, 'addressLocality')
        localites += _valeurs_imbriquees(o, 'areaServed')
        telephones += _valeurs_imbriquees(o, 'telephone')
        horaires += _valeurs_imbriquees(o, 'openingHours')
        horaires += _valeurs_imbriquees(o, 'openingHoursSpecification')
        coordonnees += _valeurs_imbriquees(o, 'latitude')

    points, preuves = 0, []

    # La localite desservie EST le signal local. Sans elle, le reste ne dit
    # pas ou l'entreprise opere, donc elle porte le poids principal.
    lieux = sorted({v for v in localites if v})[:4]
    if lieux:
        points += 45
        preuves.append('Zone desservie declaree : ' + ', '.join(lieux))
    else:
        preuves.append('Aucune localite declaree dans le balisage')

    if telephones:
        points += 20
        preuves.append('Telephone dans le balisage')
    if horaires:
        points += 20
        preuves.append("Heures d'ouverture declarees")
    if coordonnees:
        points += 15
        preuves.append('Coordonnees geographiques declarees')

    # Les preuves doivent pouvoir se lire ensemble sans se contredire. Une
    # premiere version ajoutait "Aucun balisage local exploitable" des que
    # les signaux secondaires manquaient, y compris quand une localite AVAIT
    # ete trouvee : la page affichait alors "Zone desservie : Montreal" juste
    # au-dessus. Vu en prod le 2026-08-25.
    if lieux and not (telephones or horaires or coordonnees):
        preuves.append('Aucun autre signal local declare (telephone, heures, coordonnees)')
    elif not lieux and not (telephones or horaires or coordonnees):
        preuves.append('Aucun balisage local exploitable sur la page')

    return _mesure(points, preuves)


# ---------------------------------------------------------------------------
# Decouverte de concurrents et ecarts de mots-cles
# ---------------------------------------------------------------------------
def decouvrir_concurrents(serps: list[dict], domaine: str, maximum: int = 3
                          ) -> list[str]:
    """Deduit les concurrents des SERP deja collectes, par frequence d'apparition.

    Pourquoi cette methode : l'ancienne lisait `relatedSearches` sur une
    requete `site:{domaine}`. Or Serper n'inclut PAS cette cle sur les
    requetes `site:` (verifie en prod le 2026-08-25, seules `credits`,
    `organic` et `searchParameters` sont rendues). La liste restait donc
    toujours vide, sans erreur, et l'outil ne trouvait jamais un seul
    concurrent tout en depensant une vingtaine de credits Serper pour un
    resultat garanti nul.

    Un domaine qui revient sur plusieurs des requetes commerciales du site
    analyse se dispute reellement le meme terrain. C'est un signal direct,
    lu dans des pages de resultats qu'on a deja payees.

    LIMITE CONNUE, NON RESOLUE
    --------------------------
    Cette fonction remonte parfois des hotes qui ne sont pas des concurrents
    actionnables. Verifie en prod le 2026-08-25 : sur tokamdarius.ca (site
    d'un developpeur pigiste), elle a rendu `emplois.ca.indeed.com`,
    `ca.linkedin.com` et `jobillico.com`. Sur "developpeur web chicoutimi",
    Google lit une recherche d'EMPLOI, pas une recherche de prestataire. Sur
    notion.so, elle a rendu `fr.capterra.ca` et `fr.getapp.ca`, des annuaires
    de logiciels.

    Une liste noire de domaines a ete essayee puis RETIREE volontairement. Une
    liste maintenue a la main n'est jamais complete : chaque site rencontre en
    ajoute un, ce qui revient a coder pour chaque cas particulier au lieu de
    resoudre le probleme. La ou le probleme est reellement pose, c'est en
    amont : ces requetes n'ont pas une intention commerciale, donc elles
    n'auraient jamais du entrer dans l'analyse.

    Deux pistes structurelles, aucune implementee :
      1. Juger l'intention d'une requete a la composition de son SERP. Une
         page de resultats majoritairement occupee par des offres d'emploi
         signale une intention d'emploi, quels que soient les domaines
         precis. La requete sort alors de l'analyse entiere.
      2. Faire qualifier l'intention en amont, au moment ou les requetes
         commerciales sont generees, plutot que de filtrer les resultats
         apres coup.
    """
    frequences = {}
    meilleures = {}
    for serp in serps:
        vus = set()
        for hote, rang in serp.get('hotes', []):
            if not hote or hote == domaine:
                continue
            if hote in vus:      # une seule voix par SERP, pas une par URL
                continue
            vus.add(hote)
            frequences[hote] = frequences.get(hote, 0) + 1
            meilleures[hote] = min(meilleures.get(hote, 99), rang or 99)

    # Frequence d'abord, meilleur rang pour departager. Un hote vu une seule
    # fois sur dix requetes est un passant, pas un concurrent : on exige deux
    # apparitions des qu'il y a assez de SERP pour que ce soit significatif.
    minimum = 2 if len(serps) >= 4 else 1
    candidats = [h for h, n in frequences.items() if n >= minimum]
    candidats.sort(key=lambda h: (-frequences[h], meilleures[h], h))
    return candidats[:maximum]


def trouver_ecarts(serps: list[dict], domaine: str, concurrents: list[str]
                   ) -> list[dict]:
    """Requetes ou un concurrent se classe et ou le domaine est absent.

    Le domaine est declare absent d'une requete uniquement si on a REGARDE ce
    SERP (`collecter_serps` ne rend que les SERP verifies), jamais parce qu'un
    appel a echoue.
    """
    concurrents = set(concurrents)
    ecarts = []
    for serp in serps:
        resultats = serp.get('resultats') or []
        if any(r['hote'] == domaine for r in resultats):
            continue     # le domaine se classe deja, ce n'est pas un ecart
        rival = next((r for r in resultats if r['hote'] in concurrents), None)
        if not rival:
            continue
        ecarts.append({
            'keyword': serp['requete'],
            'competitor': rival['hote'],
            'position': rival['position'],
            'url': rival['url'],
            'title': rival['titre'],
        })
    return ecarts
