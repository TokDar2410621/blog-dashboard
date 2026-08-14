"""Keyword clustering measured on real SERP overlap instead of text similarity.

Porte depuis claude-seo v2.2.4 `skills/seo-cluster/SKILL.md` et
`skills/seo-cluster/references/serp-overlap-methodology.md`.
Copyright (c) 2025 Daniel Agrici (AgriciDaniel). MIT.
https://github.com/AgriciDaniel/claude-seo

The source leaves three things to the operator that a backend cannot leave to
anyone: URL normalization is described in one line, the thresholds assume a
full top 10, and grouping is done by eye. So normalization is spelled out here
(protocol, www, trailing slash, tracking parameters, percent-encoded accents,
AMP and index files), a partial SERP is rescaled onto the source's 0 to 10
scale before the thresholds are read, and grouping runs as star clustering
around a pivot so every satellite is measured against the pivot itself, which
is what stops A and C landing together on the strength of B alone. Every label
that reaches a client is in French.
"""
from __future__ import annotations

from urllib.parse import parse_qsl, unquote, urlencode, urlsplit

__all__ = [
    'DEFAULT_TOP_N',
    'MIN_DEPTH_FOR_CONFIDENCE',
    'PALIERS',
    'PALIER_INDETERMINE',
    'normalize_result_url',
    'serp_overlap',
    'cluster_keywords',
    'suggest_internal_links',
]


DEFAULT_TOP_N = 10

# The source's four bands, highest first. `_palier_for` walks this in order,
# so the last entry has to be the catch-all.
PALIERS = [
    {
        'code': 'meme_page',
        'min': 7,
        'max': 10,
        'relation': 'Même page',
        'action': 'fusionner',
        'consequence': (
            "Google sert presque les mêmes pages pour les deux requêtes : une "
            "seule page doit viser les deux, sinon elles se cannibalisent."
        ),
    },
    {
        'code': 'meme_page_probable',
        'min': 4,
        'max': 6,
        'relation': 'Même page probable',
        'action': 'meme_cluster',
        'consequence': (
            "Assez de recoupement pour le même cluster, et pour la même page si "
            "les deux requêtes attendent la même réponse. Deux pages restent "
            "défendables si l'angle diffère vraiment."
        ),
    },
    {
        'code': 'pages_distinctes_maillees',
        'min': 2,
        'max': 3,
        'relation': 'Pages distinctes mais maillées',
        'action': 'mailler',
        'consequence': (
            "Sujets voisins sans être la même réponse : deux pages, dans des "
            "clusters adjacents, reliées par un lien interne dans chaque sens."
        ),
    },
    {
        'code': 'sujets_distincts',
        'min': 0,
        'max': 1,
        'relation': 'Sujets distincts',
        'action': 'separer',
        'consequence': (
            "Google ne voit aucun rapport entre les deux requêtes : deux pages "
            "sans lien, à ne pas regrouper."
        ),
    },
]

# Not in the source. Measuring nothing is not the same as measuring zero, and
# an empty SERP would otherwise be reported as proof that two topics differ.
PALIER_INDETERMINE = {
    'code': 'indetermine',
    'min': 0,
    'max': 0,
    'relation': 'Indéterminé',
    'action': 'recolter',
    'consequence': (
        "Pas assez de résultats pour mesurer quoi que ce soit : il faut "
        "récupérer la SERP des deux requêtes avant de conclure."
    ),
}

# Serper returns ten organic results in the normal case. Under five comparable
# positions, one shared URL moves the rescaled score by two points or more,
# which is a whole band, so the palier is flagged as thin rather than trusted.
MIN_DEPTH_FOR_CONFIDENCE = 5

# Click identifiers and campaign tags name the visit, never the page. Left in,
# the same result arriving twice with different tags counts as two documents
# and every overlap collapses toward zero.
_TRACKING_PARAMS = frozenset({
    'gclid', 'gclsrc', 'gbraid', 'wbraid', 'dclid', 'fbclid', 'msclkid',
    'yclid', 'twclid', 'igshid', 'mc_cid', 'mc_eid', 'srsltid', 'ref',
    'referrer', 'source', 'campaign', 'cmpid', 'ck_subscriber_id', 'si',
    'spm', 'trk', 'trk_contact', 'trk_module', 'vero_id', 'oly_enc_id',
    '_ga', '_gl', '_hsenc', '_hsmi', 'hsa_acc', 'hsa_cam', 'amp',
})

_TRACKING_PREFIXES = ('utm_', 'pk_', 'mtm_', 'piwik_', 'matomo_', 'hsa_')

# Same document, different wrapper. Google mixes these forms in one SERP.
_INDEX_SUFFIXES = ('/index.html', '/index.htm', '/index.php', '/default.aspx')

_URL_KEYS = ('link', 'url', 'lien', 'href')

_MAX_KEYWORDS = 200


def _palier_for(count: int) -> dict:
    for palier in PALIERS:
        if count >= palier['min']:
            return palier
    return PALIERS[-1]


def normalize_result_url(result) -> str:
    """Reduce one SERP result to a comparison key. Empty string if unusable.

    Accepts a bare URL or a Serper organic row, so callers can hand over
    `res.json()['organic']` untouched.
    """
    if isinstance(result, dict):
        raw = ''
        for key in _URL_KEYS:
            value = result.get(key)
            if isinstance(value, str) and value.strip():
                raw = value
                break
    elif isinstance(result, str):
        raw = result
    else:
        return ''

    raw = raw.strip()
    if not raw:
        return ''

    # A scheme token never carries a dot, which is what tells `javascript:` and
    # `mailto:` apart from a bare `example.com:8443/page`.
    head = raw.split('/', 1)[0]
    if ':' in head:
        scheme = head.split(':', 1)[0].lower()
        if '.' not in scheme and scheme not in ('http', 'https'):
            return ''

    # urlsplit only fills netloc when it sees an authority marker, and Serper
    # occasionally hands back a bare "example.com/page".
    if '://' not in raw:
        raw = '//' + raw.lstrip('/')

    try:
        parts = urlsplit(raw)
    except ValueError:
        return ''

    if parts.scheme and parts.scheme.lower() not in ('http', 'https', ''):
        return ''

    try:
        host = (parts.hostname or '').lower()
    except ValueError:
        return ''
    host = host.rstrip('.')
    # An organic result always sits on a registrable domain, so a dotless host
    # means the string was a relative path or a scheme that slipped through.
    if not host or '.' not in host:
        return ''
    if host.startswith('www.'):
        host = host[4:]

    # Accented Quebec slugs travel both encoded and decoded through SERP APIs;
    # decoding once puts /référencement and /r%C3%A9f%C3%A9rencement on one key.
    path = unquote(parts.path or '')
    while '//' in path:
        path = path.replace('//', '/')
    for suffix in _INDEX_SUFFIXES:
        if path.lower().endswith(suffix):
            path = path[: -len(suffix)]
            break
    if path.lower().endswith('/amp'):
        path = path[:-4]
    path = path.rstrip('/')

    kept = [
        (name, value)
        for name, value in parse_qsl(parts.query, keep_blank_values=True)
        if name.lower() not in _TRACKING_PARAMS
        and not name.lower().startswith(_TRACKING_PREFIXES)
    ]
    # Sorted so ?page=2&sort=date and ?sort=date&page=2 stay one document.
    query = urlencode(sorted(kept), doseq=False)

    key = host + path
    return f'{key}?{query}' if query else key


def _normalized_seq(results, top_n: int) -> list[str]:
    """Normalized URLs in SERP order, deduplicated, capped at top_n.

    Deduplication happens before the cap so a duplicate does not consume one
    of the ten positions being compared.
    """
    out: list[str] = []
    seen: set[str] = set()
    for raw in results or []:
        key = normalize_result_url(raw)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(key)
        if len(out) >= top_n:
            break
    return out


def _measure(seq_a: list[str], seq_b: list[str], top_n: int) -> dict:
    """Overlap between two already normalized sequences."""
    set_b = set(seq_b)
    communes = [url for url in seq_a if url in set_b]
    depth = min(len(seq_a), len(seq_b))

    if depth == 0:
        palier = PALIER_INDETERMINE
        sur_dix = 0
        indice = 0.0
    else:
        indice = len(communes) / depth
        # Serper returns ten results most of the time and fewer when the query
        # is thin. The source's bands are written for ten, so a 3 of 5 overlap
        # is rescaled to 6 of 10 instead of being read as a weak 3.
        sur_dix = min(top_n, int(len(communes) * top_n / depth + 0.5))
        palier = _palier_for(sur_dix)

    return {
        'communs': len(communes),
        'urls_communes': communes,
        'indice': round(indice, 3),
        'profondeur': depth,
        'communs_sur_10': sur_dix,
        'taille_a': len(seq_a),
        'taille_b': len(seq_b),
        'donnees_suffisantes': depth >= MIN_DEPTH_FOR_CONFIDENCE,
        'palier': palier['code'],
        'relation': palier['relation'],
        'action': palier['action'],
        'consequence': palier['consequence'],
    }


def serp_overlap(results_a, results_b, *, top_n: int = DEFAULT_TOP_N) -> dict:
    """Measure how much two SERPs share, and say what that implies.

    `results_a` and `results_b` are the organic results of two queries, as URL
    strings or as Serper rows. Returns the shared count, the overlap index
    (0 to 1 over the compared depth), the source's palier and its consequence
    in French.
    """
    top_n = max(1, int(top_n or DEFAULT_TOP_N))
    seq_a = _normalized_seq(results_a, top_n)
    seq_b = _normalized_seq(results_b, top_n)
    out = _measure(seq_a, seq_b, top_n)

    if out['profondeur'] == 0:
        out['message'] = (
            "Aucune SERP exploitable pour au moins une des deux requêtes. "
            + PALIER_INDETERMINE['consequence']
        )
        return out

    message = (
        f"{out['communs']} résultat(s) commun(s) sur {out['profondeur']} "
        f"comparé(s). {out['consequence']}"
    )
    if not out['donnees_suffisantes']:
        message += (
            f" Mesure fragile : seulement {out['profondeur']} position(s) "
            "comparables."
        )
    out['message'] = message
    return out


def _pair_matrix(keywords: list[str], sequences: dict[str, list[str]],
                 top_n: int) -> list[list[int]]:
    """Symmetric rescaled overlap scores, diagonal at top_n."""
    size = len(keywords)
    scores = [[0] * size for _ in range(size)]
    for i in range(size):
        scores[i][i] = top_n
        for j in range(i + 1, size):
            value = _measure(
                sequences[keywords[i]], sequences[keywords[j]], top_n,
            )['communs_sur_10']
            scores[i][j] = value
            scores[j][i] = value
    return scores


def cluster_keywords(serp_by_keyword, *, min_overlap: int = 4,
                     top_n: int = DEFAULT_TOP_N,
                     seuil_fusion: int = 7) -> dict:
    """Group keywords whose SERPs actually overlap, around a pivot each time.

    `serp_by_keyword` maps a keyword to its organic results. Grouping is star
    shaped: the keyword overlapping the most others becomes the pivot and takes
    in every keyword that clears `min_overlap` against it. Transitive closure
    was rejected on purpose, since it chains A to C through B even when A and C
    share nothing, which is the exact mistake SERP overlap exists to avoid.
    """
    top_n = max(1, int(top_n or DEFAULT_TOP_N))
    min_overlap = max(1, min(int(min_overlap), top_n))
    seuil_fusion = max(min_overlap, min(int(seuil_fusion), top_n))

    sequences: dict[str, list[str]] = {}
    sans_donnees: list[dict] = []
    for keyword, results in list((serp_by_keyword or {}).items())[:_MAX_KEYWORDS]:
        label = (keyword or '').strip()
        if not label:
            continue
        seq = _normalized_seq(results, top_n)
        if seq:
            sequences[label] = seq
        else:
            sans_donnees.append({
                'mot_cle': label,
                'raison': (
                    "Aucun résultat organique exploitable : impossible de "
                    "mesurer le chevauchement, il faut relancer la SERP."
                ),
            })

    keywords = list(sequences.keys())
    scores = _pair_matrix(keywords, sequences, top_n)

    remaining = set(range(len(keywords)))
    clusters: list[dict] = []

    while remaining:
        best_index = None
        best_key = None
        for i in sorted(remaining):
            neighbours = [
                j for j in remaining
                if j != i and scores[i][j] >= min_overlap
            ]
            key = (len(neighbours), sum(scores[i][j] for j in neighbours))
            if best_key is None or key > best_key:
                best_key, best_index = key, i
        if best_index is None or best_key[0] == 0:
            break

        pivot = best_index
        members = sorted(
            (j for j in remaining if j != pivot and scores[pivot][j] >= min_overlap),
            key=lambda j: (-scores[pivot][j], keywords[j]),
        )
        remaining.discard(pivot)
        remaining.difference_update(members)

        satellites = []
        for j in members:
            palier = _palier_for(scores[pivot][j])
            measured = _measure(sequences[keywords[pivot]], sequences[keywords[j]], top_n)
            satellites.append({
                'mot_cle': keywords[j],
                'communs': measured['communs'],
                'communs_sur_10': scores[pivot][j],
                'indice': measured['indice'],
                'palier': palier['code'],
                'relation': palier['relation'],
            })

        group = [pivot] + members
        fusions = []
        for a_pos, a in enumerate(group):
            for b in group[a_pos + 1:]:
                if scores[a][b] >= seuil_fusion:
                    fusions.append({
                        'mots_cles': [keywords[a], keywords[b]],
                        'communs_sur_10': scores[a][b],
                        'message': (
                            f"« {keywords[a]} » et « {keywords[b]} » partagent "
                            f"{scores[a][b]} résultats sur {top_n} : une seule "
                            "page doit viser les deux, deux pages se "
                            "cannibaliseraient."
                        ),
                    })

        clusters.append({
            'id': '',
            'pivot': keywords[pivot],
            'satellites': satellites,
            'mots_cles': [keywords[pivot]] + [keywords[j] for j in members],
            'taille': len(group),
            'fusions_suggerees': fusions,
            'resume': (
                f"« {keywords[pivot]} » sert de page pivot : ses "
                f"{len(satellites)} satellite(s) partagent au moins "
                f"{min_overlap} résultats de SERP sur {top_n} avec lui."
            ),
        })

    clusters.sort(key=lambda c: (-c['taille'], c['pivot']))
    for rank, cluster in enumerate(clusters, start=1):
        cluster['id'] = f'cluster-{rank}'

    orphelins = []
    for i in sorted(remaining):
        best_j, best_score = None, 0
        for j in range(len(keywords)):
            if j != i and scores[i][j] > best_score:
                best_j, best_score = j, scores[i][j]
        # The band of the closest neighbour is what tells an orphan apart: a
        # 2 or 3 asks for a cross link, a 0 asks for a separate topic.
        voisin_palier = _palier_for(best_score)
        orphelins.append({
            'mot_cle': keywords[i],
            'meilleur_voisin': keywords[best_j] if best_j is not None else None,
            'communs_sur_10': best_score,
            'palier_voisin': voisin_palier['code'],
            'relation_voisin': voisin_palier['relation'],
            'raison': (
                f"Au mieux {best_score} résultat(s) commun(s) sur {top_n} avec "
                f"le reste du lot, sous le seuil de {min_overlap} : sujet à "
                "traiter à part ou à documenter avec ses propres mots-clés."
            ),
        })

    regroupes = sum(c['taille'] for c in clusters)
    return {
        'clusters': clusters,
        'orphelins': orphelins,
        'sans_donnees': sans_donnees,
        'matrice': {'mots_cles': keywords, 'scores': scores},
        'parametres': {
            'min_overlap': min_overlap,
            'top_n': top_n,
            'seuil_fusion': seuil_fusion,
        },
        'resume': (
            f"{len(clusters)} cluster(s), {regroupes} mot(s)-clé(s) regroupé(s), "
            f"{len(orphelins)} orphelin(s), {len(sans_donnees)} sans données SERP."
        ),
    }


def _cluster_list(clusters):
    """Accept the cluster_keywords payload or a bare list of clusters."""
    if isinstance(clusters, dict):
        return clusters.get('clusters') or [], clusters.get('matrice') or {}
    if isinstance(clusters, list):
        return clusters, {}
    return [], {}


def _satellite_names(cluster) -> list[str]:
    names = []
    for satellite in cluster.get('satellites') or []:
        if isinstance(satellite, dict):
            name = (satellite.get('mot_cle') or '').strip()
        else:
            name = str(satellite).strip()
        if name:
            names.append(name)
    return names


def suggest_internal_links(clusters, *, max_siblings: int = 2) -> list[dict]:
    """Build the internal link matrix for the clusters, pivot both ways.

    Pivot to satellite and satellite to pivot are mandatory: a cluster missing
    either is not a cluster for a crawler. Sibling links are capped because the
    source asks for two or three per page, not for a clique. When the full
    `cluster_keywords` payload is passed, the matrix also yields cross cluster
    links for the pairs sitting in the 2 to 3 band, one per keyword.
    """
    cluster_rows, matrice = _cluster_list(clusters)
    max_siblings = max(0, int(max_siblings))

    links: list[dict] = []
    seen: set[tuple[str, str]] = set()

    def add(source: str, target: str, kind: str, mandatory: bool,
            cluster_id: str, reason: str) -> bool:
        if not source or not target or source == target:
            return False
        pair = (source, target)
        if pair in seen:
            return False
        seen.add(pair)
        links.append({
            'de': source,
            'vers': target,
            'type': kind,
            'obligatoire': mandatory,
            'ancre': target,
            'cluster': cluster_id,
            'raison': reason,
        })
        return True

    keyword_to_cluster: dict[str, str] = {}

    for cluster in cluster_rows:
        if not isinstance(cluster, dict):
            continue
        pivot = (cluster.get('pivot') or '').strip()
        cluster_id = cluster.get('id') or ''
        satellites = _satellite_names(cluster)
        if not pivot:
            continue
        keyword_to_cluster[pivot] = cluster_id
        for name in satellites:
            keyword_to_cluster[name] = cluster_id

        for name in satellites:
            add(
                name, pivot, 'satellite_vers_pivot', True, cluster_id,
                "Chaque satellite doit renvoyer à la page pivot, sinon Google "
                "ne voit pas le cluster.",
            )
            add(
                pivot, name, 'pivot_vers_satellite', True, cluster_id,
                "La page pivot doit pointer vers chacun de ses satellites, "
                "sinon le satellite reste orphelin.",
            )

        # Siblings are already ordered by their overlap with the pivot, so the
        # ring walk hands each page its closest neighbours first.
        count = len(satellites)
        for position, name in enumerate(satellites):
            for step in range(1, min(max_siblings, max(count - 1, 0)) + 1):
                target = satellites[(position + step) % count]
                add(
                    name, target, 'satellite_vers_satellite', False, cluster_id,
                    "Deux satellites du même cluster : un lien contextuel garde "
                    "le lecteur et la valeur dans le cluster.",
                )

    keywords = matrice.get('mots_cles') or []
    scores = matrice.get('scores') or []
    if keywords and scores:
        band = next(p for p in PALIERS if p['code'] == 'pages_distinctes_maillees')
        used: dict[str, int] = {}
        candidates = []
        for i, kw_a in enumerate(keywords):
            for j in range(i + 1, len(keywords)):
                kw_b = keywords[j]
                cluster_a = keyword_to_cluster.get(kw_a)
                cluster_b = keyword_to_cluster.get(kw_b)
                if not cluster_a or not cluster_b or cluster_a == cluster_b:
                    continue
                score = scores[i][j]
                if band['min'] <= score <= band['max']:
                    candidates.append((-score, kw_a, kw_b, score))
        for _, kw_a, kw_b, score in sorted(candidates):
            # The source allows zero or one cross cluster link per page, so the
            # strongest bridge wins and the rest are dropped rather than queued.
            if used.get(kw_a, 0) or used.get(kw_b, 0):
                continue
            reason = (
                f"{score} résultat(s) commun(s) sur {DEFAULT_TOP_N} entre deux "
                "clusters : un seul lien croisé dans chaque sens, pas plus."
            )
            add(kw_a, kw_b, 'lien_croise', False, 'inter-clusters', reason)
            add(kw_b, kw_a, 'lien_croise', False, 'inter-clusters', reason)
            used[kw_a] = used.get(kw_a, 0) + 1
            used[kw_b] = used.get(kw_b, 0) + 1

    return links
