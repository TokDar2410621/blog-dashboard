"""Heuristic + AI helpers to classify a keyword's search intent.

Intent labels mirror what Claude returns from SuggestKeywordsView:
- info: question, definition, how-to, guide
- commercial: comparison, "best X", reviews to inform a future purchase
- transactional: ready-to-buy intent ("buy X", "price X", "X cheap")
- local: geo-anchored ("X Montreal", "X near me")

The regex classifier is intentionally simple and FR-CA centric (the only
locale Gridar ships today). When it can't decide it returns 'info' since
that's the safest default for an article generator (most generic format).
"""
from __future__ import annotations

import re

# Order matters: first match wins. local + transactional + commercial are
# stronger signals than info, which we keep as the fallback.
_PATTERNS = [
    ('local', re.compile(
        r'\b(?:montreal|quebec|laval|gatineau|sherbrooke|trois[- ]rivieres|'
        r'longueuil|levis|saguenay|saint[- ]jean|drummondville|granby|'
        r'rimouski|val[- ]d\'or|chicoutimi|joliette|terrebonne|brossard|'
        r'mascouche|repentigny|blainville|boucherville|saint[- ]laurent|'
        r'pres de moi|pres de chez moi|autour de moi|dans ma ville|'
        r'canada|qc)\b',
        re.IGNORECASE,
    )),
    ('transactional', re.compile(
        r'\b(?:acheter|achat|prix|tarif|tarifs|cout|coute|combien|abonnement|'
        r'paiement|reserver|reservation|commander|commande|location|louer|'
        r'devis|telecharger|download|gratuit|free|essai|trial|inscription|'
        r's\'inscrire|essayer|tester)\b',
        re.IGNORECASE,
    )),
    ('commercial', re.compile(
        r'\b(?:meilleur|meilleure|meilleurs|meilleures|top \d+|comparatif|'
        r'comparaison|comparer|versus|vs\.?|alternatives?|alternative a|'
        r'avis|review|reviews|avantages|inconvenients|note|notation|'
        r'classement|recommandation|recommander)\b',
        re.IGNORECASE,
    )),
    ('info', re.compile(
        r'\b(?:comment|c\'est quoi|qu\'est[- ]ce que|quoi|pourquoi|quel|'
        r'quelle|quels|quelles|definition|guide|tutoriel|tuto|tutorial|'
        r'apprendre|expliquer|fonctionne|signifie|methodes?|etapes?|exemple|'
        r'exemples)\b',
        re.IGNORECASE,
    )),
]


def classify_intent_heuristic(keyword: str) -> str:
    """Return one of {info, commercial, transactional, local}. Never None.

    Uses simple regex over FR-CA buy/locate/learn signals. Calling code that
    needs higher accuracy should fall back to Claude (see classify_intents_ai
    in views) - this is the always-free, always-fast baseline.
    """
    if not keyword or not isinstance(keyword, str):
        return 'info'
    text = keyword.strip().lower()
    if not text:
        return 'info'
    for label, pattern in _PATTERNS:
        if pattern.search(text):
            return label
    return 'info'


classify_intent = classify_intent_heuristic


def map_intent_to_article_type(intent: str, keyword: str = '') -> str:
    """Pick the most natural article_type for an autopilot run.

    The mapping is intent-first, with a small refinement on `info` (split
    between guide and tutorial based on whether the keyword reads like a
    step-by-step request). Falls back to 'guide' when intent is unknown.
    """
    intent = (intent or '').lower()
    kw = (keyword or '').lower()
    if intent == 'commercial':
        return 'comparison'
    if intent == 'transactional':
        return 'review'
    if intent == 'local':
        return 'local'
    if intent == 'info':
        if re.search(r'\b(?:comment|tutoriel|tuto|tutorial|etape|etapes|guide pratique)\b', kw):
            return 'tutorial'
        return 'guide'
    return 'guide'


def pick_length(intent: str, keyword: str = '') -> str:
    """Smart length picker for the autopilot - returns 'medium' or 'long'.

    'short' was retired from the autopilot per user feedback (too thin to
    rank on real queries). The rule of thumb:
    - long: anything that demands depth (comparisons, complex guides, "X de A a Z")
    - medium: simple questions, transactional, local, short answers
    """
    intent = (intent or '').lower()
    kw = (keyword or '').lower()

    if intent == 'commercial':
        return 'long'
    if intent in ('transactional', 'local'):
        return 'medium'

    # info default: long when the keyword signals breadth / depth, else medium
    if re.search(
        r'\b(?:guide complet|tout savoir|de a a z|en \d+ etapes|guide ultime|'
        r'fondamentaux|maitriser|approfondi|complet)\b', kw,
    ):
        return 'long'
    if re.search(r'\b(?:qu\'est[- ]ce que|c\'est quoi|definition|signifie)\b', kw):
        return 'medium'
    if re.search(r'\b(?:comment|tutoriel|methode|etapes?)\b', kw):
        return 'long'
    return 'medium'
