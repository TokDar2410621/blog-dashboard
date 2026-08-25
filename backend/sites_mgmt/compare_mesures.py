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
    """
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
    return {
        'performance': note('performance'),
        'seo': note('seo'),
        'accessibilite': note('accessibility'),
        'lcp_s': None if lcp is None else round(lcp / 1000, 2),
        'cls': None if cls is None else round(cls, 3),
    }


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
    if not requetes:
        return _indisponible('Aucune requete a tester.'), _indisponible('Aucune requete a tester.')

    reponses = {}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futurs = {pool.submit(_demander_gemini, q): q for q in requetes}
        for fut in as_completed(futurs):
            question = futurs[fut]
            try:
                reponses[question] = fut.result()
            except Exception:
                reponses[question] = None

    obtenues = {q: t for q, t in reponses.items() if t}
    if not obtenues:
        indispo = _indisponible("Aucune reponse d'IA obtenue (quota ou cle).")
        return indispo, indispo

    def noter(domaine):
        cites = [q for q, t in obtenues.items() if _cite_le_domaine(t, domaine)]
        taux = len(cites) / len(obtenues) * 100
        preuves = [f'Cite dans {len(cites)} reponse(s) sur {len(obtenues)} testee(s)']
        if cites:
            preuves.append('Par exemple : ' + cites[0])
        return _mesure(taux, preuves)

    return noter(domaine_a), noter(domaine_b)


# ---------------------------------------------------------------------------
# SERP partage : une passe Serper alimente Contenu et Autorite pour les deux
# ---------------------------------------------------------------------------
def _hote(lien: str) -> str:
    hote = (lien or '').lower().split('://', 1)[-1].split('/', 1)[0]
    return hote.removeprefix('www.')


def sonder_serp(requetes: list[str], domaine_a: str, domaine_b: str,
                max_workers: int = 8) -> dict | None:
    """Un appel Serper par requete, positions des DEUX domaines extraites.

    C'est le principal gain face au code existant : `PublicCompetitorGapView`
    depense une requete Serper par mot-cle et par domaine. Ici les deux sites
    sont lus dans le meme SERP, donc quinze requetes coutent quinze credits
    pour les deux, pas quinze chacun.

    Chaque resultat porte un `verifie` explicite. Un non-200 ne doit jamais se
    confondre avec "le site ne se classe pas" : sans ce drapeau, une panne de
    quota annonce au visiteur que son site n'est nulle part.
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
                'hotes': [(_hote(o.get('link')), o.get('position') or 0) for o in organiques],
            }
        except Exception:
            return {'requete': question, 'verifie': False}

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        resultats = list(pool.map(une_requete, requetes))

    verifies = [r for r in resultats if r.get('verifie')]
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
_INDICES_LOCAUX = (
    'localbusiness', 'postaladdress', 'addresslocality', 'opening_hours',
    'openinghours', 'geocoordinates',
)
_VILLES_QC = (
    'montreal', 'québec', 'quebec', 'laval', 'gatineau', 'longueuil',
    'sherbrooke', 'saguenay', 'chicoutimi', 'jonquière', 'jonquiere',
    'trois-rivières', 'trois-rivieres', 'saint-hyacinthe', 'drummondville',
    'lévis', 'levis', 'terrebonne', 'brossard', 'repentigny', 'granby',
)


def mesurer_strategie_locale(crawl: dict | None, html: str) -> dict:
    """Signaux d'ancrage local reellement presents dans la page.

    Trois signaux verifiables : un balisage LocalBusiness, un numero de
    telephone affiche, et des villes nommees dans le contenu. Un site sans
    ambition locale marque bas ici sans que ce soit un defaut : c'est une
    information, pas un reproche, et le recit doit le dire.
    """
    if not crawl or crawl.get('error'):
        return _indisponible("La page n'a pas pu etre lue.")

    bas = (html or '').lower()
    texte = ' '.join(str(crawl.get(c) or '') for c in
                     ('title', 'h1', 'meta_description', 'body_snippet')).lower()

    balisage = any(indice in bas for indice in _INDICES_LOCAUX)
    telephone = bool(re.search(r'(\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}', bas))
    villes = sorted({v for v in _VILLES_QC if v in texte or v in bas})

    points, preuves = 0, []
    if balisage:
        points += 40
        preuves.append('Balisage LocalBusiness detecte')
    else:
        preuves.append('Aucun balisage LocalBusiness')
    if telephone:
        points += 25
        preuves.append('Numero de telephone affiche')
    if villes:
        points += min(35, 12 * len(villes))
        preuves.append('Villes nommees : ' + ', '.join(villes[:4]))
    else:
        preuves.append('Aucune ville nommee dans le contenu lu')

    return _mesure(points, preuves)
