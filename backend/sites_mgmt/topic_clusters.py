"""Topic cluster mapping + one-click build.

`build_cluster_map(site)` groups a site's known keywords (tracked keywords +
strategic opportunities) into topic clusters - one pillar + N spokes - and
flags which keywords already have a page. The clustering is deterministic
(shared significant-token union-find), so the MAP needs no LLM call or quota.

`build_cluster(...)` generates the whole cluster: the pillar page + spoke
articles + the internal mesh (spokes -> pillar, pillar -> spokes), honouring
Site.delivery_mode for dev sites. Generation uses the article/landing
generators (LLM), so it is subject to the usual generation quota.
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter, defaultdict

from django.utils.text import slugify


# Stopwords + intent modifiers stripped before clustering. Topic anchors are
# nouns ("menuiserie", "seo"), never intent words ("comment", "prix", "best").
_STOP = frozenset({
    # articles / prepositions / pronouns (FR / EN / ES)
    'le', 'la', 'les', 'un', 'une', 'des', 'du', 'de', 'au', 'aux', 'et', 'ou',
    'a', 'the', 'an', 'of', 'for', 'to', 'in', 'on', 'and', 'or', 'with', 'my',
    'your', 'el', 'los', 'las', 'y', 'en', 'para', 'por', 'con',
    # intent modifiers - not topic anchors
    'comment', 'pourquoi', 'quoi', 'quel', 'quelle', 'quels', 'quelles',
    'prix', 'tarif', 'tarifs', 'cout', 'couts', 'coute', 'combien', 'meilleur',
    'meilleure', 'meilleurs', 'meilleures', 'avis', 'comparatif', 'comparaison',
    'guide', 'tutoriel', 'exemple', 'exemples', 'best', 'top', 'how', 'what',
    'why', 'when', 'where', 'price', 'cost', 'review', 'reviews', 'vs', 'versus',
    'near', 'me', 'pres', 'moi', 'sans', 'pour', 'dans', 'avec',
})


def _strip_accents(s: str) -> str:
    return ''.join(
        c for c in unicodedata.normalize('NFD', (s or '').lower())
        if unicodedata.category(c) != 'Mn'
    )


def _tokens(keyword: str) -> set[str]:
    """Significant, accent-stripped topic tokens of a keyword."""
    words = re.findall(r"[a-z0-9]+", _strip_accents(keyword))
    return {w for w in words if len(w) >= 3 and w not in _STOP and not w.isdigit()}


def _pillar_title(keyword: str, language: str) -> str:
    kw = keyword.strip()
    if (language or 'fr')[:2] == 'fr':
        return f"Guide complet : {kw}"
    return f"The complete guide to {kw}"


def build_cluster_map(site, min_cluster_size: int = 2, max_clusters: int = 40) -> dict:
    """Group the site's keyword universe into topic clusters.

    Returns {clusters: [...], total_keywords, clustered, unclustered}. Each
    cluster: {anchor, pillar:{keyword,intent,suggested_title,covered,...},
    spokes:[{keyword,intent,covered}], size, missing}.
    """
    from .models import (
        TrackedKeyword, StrategicOpportunity, HostedPost, HostedLanding,
    )

    # 1) Gather the keyword universe (tracked keywords + strategic opportunities).
    records = []
    seen = set()

    def _add(keyword, language, intent, source):
        norm = _strip_accents(keyword).strip()
        if not norm or norm in seen:
            return
        seen.add(norm)
        records.append({
            'keyword': (keyword or '').strip(),
            'language': (language or 'fr')[:2],
            'intent': (intent or '').strip().lower(),
            'source': source,
            'norm': norm,
            'tokens': _tokens(keyword),
        })

    for tk in TrackedKeyword.objects.filter(site=site, is_active=True):
        _add(tk.keyword, tk.language, tk.intent, 'tracked')
    for op in (StrategicOpportunity.objects.filter(site=site)
               .exclude(status='dismissed')):
        _add(op.keyword, op.language, op.intent, 'opportunity')

    # 2) Union-find on shared significant tokens -> connected components.
    parent = list(range(len(records)))

    def _find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def _union(i, j):
        ri, rj = _find(i), _find(j)
        if ri != rj:
            parent[max(ri, rj)] = min(ri, rj)

    token_to_idx = defaultdict(list)
    for i, r in enumerate(records):
        for t in r['tokens']:
            token_to_idx[t].append(i)
    for idxs in token_to_idx.values():
        for j in idxs[1:]:
            _union(idxs[0], j)

    groups = defaultdict(list)
    for i in range(len(records)):
        groups[_find(i)].append(i)

    # 3) Coverage: a keyword is "covered" if a page slug matches it, or a
    #    tracked keyword already points at a target_url.
    existing_slugs = set(
        HostedPost.objects.filter(site=site).values_list('slug', flat=True)
    ) | set(
        HostedLanding.objects.filter(site=site).values_list('slug', flat=True)
    )
    covered_norm = {
        _strip_accents(kw).strip()
        for kw in (TrackedKeyword.objects.filter(site=site)
                   .exclude(target_url='')
                   .values_list('keyword', flat=True))
    }

    def _covered(rec):
        return rec['norm'] in covered_norm or slugify(rec['keyword']) in existing_slugs

    # 4) Shape clusters (size >= min), pillar = broadest keyword.
    clusters = []
    clustered_count = 0
    for idxs in groups.values():
        if len(idxs) < min_cluster_size:
            continue
        members = [records[i] for i in idxs]
        clustered_count += len(members)
        counter = Counter()
        for m in members:
            counter.update(m['tokens'])
        anchor = counter.most_common(1)[0][0] if counter else ''
        # Broadest keyword = fewest tokens, then shortest string.
        pillar = min(members, key=lambda m: (len(m['tokens']), len(m['keyword'])))
        spokes = [m for m in members if m is not pillar]

        pillar_covered = _covered(pillar)
        spokes_out = [{
            'keyword': s['keyword'],
            'language': s['language'],
            'intent': s['intent'] or 'informational',
            'source': s['source'],
            'covered': _covered(s),
        } for s in spokes]
        missing = (0 if pillar_covered else 1) + sum(1 for s in spokes_out if not s['covered'])

        clusters.append({
            'anchor': anchor,
            'size': len(members),
            'missing': missing,
            'pillar': {
                'keyword': pillar['keyword'],
                'language': pillar['language'],
                'intent': pillar['intent'] or 'informational',
                'suggested_title': _pillar_title(pillar['keyword'], pillar['language']),
                'suggested_slug': slugify(pillar['keyword']) or 'pilier',
                'source': pillar['source'],
                'covered': pillar_covered,
            },
            'spokes': spokes_out,
        })

    # Biggest, least-covered clusters first (most opportunity).
    clusters.sort(key=lambda c: (c['missing'], c['size']), reverse=True)
    clusters = clusters[:max_clusters]

    return {
        'clusters': clusters,
        'total_keywords': len(records),
        'clustered': clustered_count,
        'unclustered': len(records) - clustered_count,
    }
