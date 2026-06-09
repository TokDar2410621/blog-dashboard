"""Strategic SEO opportunity engine.

For each tracked keyword on a site, generate a structured page concept that
maps the site's existing assets to the keyword's search intent. The output is
not a generic content gap ("create a page for X") - it's a strategic concept
that ties the site's product/lead-magnet to a conversion mechanism.

Example output for Gridar + "audit SEO":
  page_concept       = "Outil d'audit SEO gratuit"
  page_type          = "tool_landing"
  hook               = "Audit gratuit en 60s, sans inscription"
  capture_mechanism  = "Email pour rapport PDF complet"
  conversion_path    = "Upsell vers plan Solo 29.99$/mois"
  angle              = "Tu vends un audit IA, capitalise dessus pour ranker"
  estimated_traffic  = ~150 visites/mois si tu prends top 5
  estimated_leads    = "1-3 clients/mois selon conversion"

Two stages:
  1. compute_traffic_estimate(volume, target_position, business_model)
     -> pure math, CTR table * volume * conversion range
  2. propose_opportunity(site, tracked_keyword) -> dict
     -> calls Claude with structured prompt, returns the concept JSON

The Claude call dominates cost; results are cached in StrategicOpportunity
rows so the page load is cheap once refresh has run.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Iterable, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Static reference data
# ---------------------------------------------------------------------------

# Click-through rate by SERP position. Source: Advanced Web Ranking
# "Industry Benchmarks 2024" aggregated across desktop + mobile. Rounded.
# Used to translate `keyword_volume * target_position -> estimated_traffic`.
CTR_BY_POSITION: dict[int, float] = {
    1: 0.276,
    2: 0.158,
    3: 0.110,
    4: 0.083,
    5: 0.065,
    6: 0.052,
    7: 0.042,
    8: 0.034,
    9: 0.028,
    10: 0.025,
}
# Anything past page 1 collapses fast; use a single conservative number.
CTR_PAGE_2_PLUS = 0.005


def ctr_for_position(position: int | None) -> float:
    """Return the expected CTR for a SERP position. None / 0 / >100 -> 0."""
    if not position or position <= 0:
        return 0.0
    if position in CTR_BY_POSITION:
        return CTR_BY_POSITION[position]
    if position <= 20:
        return CTR_PAGE_2_PLUS * 2
    return CTR_PAGE_2_PLUS


# Conversion ranges by business model. Two stages because most SaaS / lead-gen
# funnels are visit -> email lead -> paying customer. Marketplaces /
# e-commerce skip the email step and go straight to transaction.
# Numbers are ranges (low, high) because variance is huge across niches and
# we want the UI to render "1-3 clients/mois", not a fake-precise "2.4".
CONVERSION_RATES: dict[str, dict[str, tuple[float, float]]] = {
    'saas': {
        # B2B SaaS: free trial sign-up rate, trial-to-paid rate
        'visit_to_lead': (0.02, 0.05),
        'lead_to_paid': (0.05, 0.12),
    },
    'agency': {
        # Agency: contact form / discovery call, call-to-client
        'visit_to_lead': (0.005, 0.015),
        'lead_to_paid': (0.10, 0.25),
    },
    'ecommerce': {
        # E-commerce: direct purchase, no email middle step.
        # lead_to_paid stays at 1.0 so the multiplication still works.
        'visit_to_lead': (0.01, 0.03),
        'lead_to_paid': (1.0, 1.0),
    },
    'marketplace': {
        # Marketplace: sign-up rate, activation rate.
        'visit_to_lead': (0.02, 0.04),
        'lead_to_paid': (0.15, 0.30),
    },
    'media': {
        # Media: newsletter subscription, then sponsored / paid tier.
        'visit_to_lead': (0.03, 0.06),
        'lead_to_paid': (0.02, 0.05),
    },
    'personal_blog': {
        # Personal blog: typically no direct funnel. Treat lead = email sub.
        'visit_to_lead': (0.01, 0.03),
        'lead_to_paid': (0.0, 0.0),
    },
}


def conversion_rates_for(business_model: str) -> dict[str, tuple[float, float]]:
    """Lookup with safe fallback to personal_blog."""
    return CONVERSION_RATES.get(business_model or 'personal_blog',
                                CONVERSION_RATES['personal_blog'])


# ---------------------------------------------------------------------------
# Math: traffic + lead estimates
# ---------------------------------------------------------------------------

def compute_traffic_estimate(
    monthly_volume: int,
    target_position: int = 5,
    business_model: str = 'personal_blog',
) -> dict:
    """Given a monthly search volume and a target SERP position, return a dict
    with visits/leads/paying customers ranges.

    target_position=5 is the default because that's a realistic mid-term goal
    once a page is well-optimised. Top 3 is the stretch goal.
    """
    if not monthly_volume or monthly_volume <= 0:
        return {
            'monthly_volume': monthly_volume or 0,
            'target_position': target_position,
            'estimated_visits': 0,
            'estimated_leads_range': (0, 0),
            'estimated_paid_range': (0, 0),
            'qualitative_traffic': 'inconnu',
        }

    ctr = ctr_for_position(target_position)
    visits = int(round(monthly_volume * ctr))

    rates = conversion_rates_for(business_model)
    lead_lo, lead_hi = rates['visit_to_lead']
    paid_lo, paid_hi = rates['lead_to_paid']

    leads_low = int(round(visits * lead_lo))
    leads_high = int(round(visits * lead_hi))
    paid_low = int(round(visits * lead_lo * paid_lo))
    paid_high = int(round(visits * lead_hi * paid_hi))

    if visits >= 500:
        qualitative = 'élevé'
    elif visits >= 100:
        qualitative = 'moyen'
    elif visits >= 20:
        qualitative = 'faible'
    else:
        qualitative = 'marginal'

    return {
        'monthly_volume': monthly_volume,
        'target_position': target_position,
        'estimated_visits': visits,
        'estimated_leads_range': (leads_low, leads_high),
        'estimated_paid_range': (paid_low, paid_high),
        'qualitative_traffic': qualitative,
    }


# ---------------------------------------------------------------------------
# Volume fetching (Serper)
# ---------------------------------------------------------------------------

def fetch_keyword_volume(keyword: str, language: str = 'fr',
                         country: str = 'ca') -> Optional[int]:
    """Best-effort monthly search volume via Serper /search-volume endpoint.

    Returns None on any error - the caller falls back to qualitative estimate.
    """
    api_key = os.environ.get('SERPER_API_KEY')
    if not api_key or not keyword.strip():
        return None
    try:
        import requests
        res = requests.post(
            'https://google.serper.dev/search',
            headers={'X-API-KEY': api_key, 'Content-Type': 'application/json'},
            json={
                'q': keyword,
                'gl': country,
                'hl': language,
                'num': 10,
            },
            timeout=8,
        )
        if not res.ok:
            return None
        # Serper exposes monthly search volume in the `searchParameters` or
        # `relatedSearches` payload depending on the plan. Fallback: scrape
        # the integer if present, else None.
        data = res.json()
        for key in ('searchVolume', 'volume', 'searchVolumeAvg'):
            v = data.get(key)
            if isinstance(v, int) and v > 0:
                return v
        return None
    except Exception as e:  # noqa: BLE001
        logger.warning('Serper volume fetch failed for %r: %s', keyword, e)
        return None


# ---------------------------------------------------------------------------
# Claude prompt
# ---------------------------------------------------------------------------

STRATEGIC_PROMPT_TEMPLATE = """Tu es stratège SEO senior qui aide une PME à construire des pages \
qui RANQUENT et qui CONVERTISSENT.

SITE
  Nom: {site_name}
  Domaine: {site_domain}
  Business model: {business_model}
  Description: {site_description}
  CTA actuel: {primary_cta_text} -> {primary_cta_url}
  Assets / contexte clé:
{knowledge_base}

MOT-CLÉ À ATTAQUER
  Texte: "{keyword}"
  Intent classifié: {intent}
  Position actuelle: {current_position}
  Volume estimé: {monthly_volume}
  Trafic potentiel (rang 5): {projected_visits} visites/mois

PAGES EXISTANTES DU SITE (NE PAS DUPLIQUER)
{existing_pages_summary}

SERP TOP 5 ACTUEL (concurrents qui ranquent déjà)
{serp_summary}

TÂCHE
Propose UNE seule page stratégique qui :
1. Matche l'intent du mot-clé (transactional = page produit/landing, info = guide, etc.)
2. Capitalise sur un ASSET DÉJÀ EXISTANT du site (produit, feature, lead magnet)
3. Inclut un MÉCANISME DE CONVERSION concret (outil gratuit, calculateur, audit,
   quiz, template, démo) - PAS juste "formulaire de contact"
4. A un angle DIFFÉRENT des concurrents qui ranquent déjà

IMPORTANT
- Si le site n'a aucun asset pertinent pour ce mot-clé, recommande quand même
  une page mais sois honnête : marque `asset_match` = false et propose un
  asset à créer en parallèle.
- Le `hook` doit être ULTRA spécifique. "Audit SEO gratuit" est mauvais.
  "Audit SEO de ton site en 60 secondes, sans inscription, rapport instant"
  est bon.
- L'`angle` explique POURQUOI cette page va battre le top 5 SERP.
- `priority` = "high" si intent transactional/commercial ET asset existant,
  "medium" si info avec gros volume, "low" sinon.

RÉPONDS EN JSON STRICT (pas de markdown, pas de texte avant/après) :
{{
  "page_concept": "Court titre du concept (max 8 mots)",
  "page_type": "tool_landing | service_page | comparison | guide_pillar | quiz_landing | calculator | local_landing | lead_magnet",
  "suggested_title": "Titre H1 de la page (max 60 char)",
  "suggested_url_path": "/slug-court",
  "hook": "Phrase d'accroche concrète (le truc qui fait cliquer)",
  "capture_mechanism": "Comment on capture le lead",
  "conversion_path": "Comment on transforme le lead en client",
  "angle": "Pourquoi cette page bat le SERP actuel",
  "asset_match": true | false,
  "asset_used": "Nom de l'asset du site exploité, ou null si à créer",
  "why_this_works": "1-2 phrases qui résument la logique stratégique",
  "priority": "high | medium | low"
}}
"""


def build_strategic_prompt(
    *,
    site,
    keyword: str,
    intent: str,
    current_position: int | None,
    monthly_volume: int | None,
    projected_visits: int,
    existing_pages_summary: str,
    serp_summary: str,
) -> str:
    kb = (site.knowledge_base or '').strip() or '(aucun contexte fourni)'
    kb_lines = '\n'.join(f'    - {line.strip()}' for line in kb.splitlines() if line.strip())
    if not kb_lines:
        kb_lines = '    - (aucun contexte fourni)'

    return STRATEGIC_PROMPT_TEMPLATE.format(
        site_name=site.name or '(sans nom)',
        site_domain=site.domain or '(sans domaine)',
        business_model=site.business_model or 'inconnu',
        site_description=(site.description or '').strip() or '(non renseigné)',
        primary_cta_text=site.primary_cta_text or '(aucun CTA configuré)',
        primary_cta_url=site.primary_cta_url or '',
        knowledge_base=kb_lines,
        keyword=keyword,
        intent=intent or 'inconnu',
        current_position=current_position if current_position else 'non rankée',
        monthly_volume=monthly_volume if monthly_volume else 'inconnu',
        projected_visits=projected_visits,
        existing_pages_summary=existing_pages_summary or '(aucune)',
        serp_summary=serp_summary or '(SERP non analysé)',
    )


ANTHROPIC_API_URL = 'https://api.anthropic.com/v1/messages'
# Matches landing_generator + article_generator. Sonnet is plenty for the
# structured-JSON task here and keeps the per-refresh cost predictable.
STRATEGIC_MODEL = 'claude-sonnet-4-20250514'


def call_claude_for_opportunity(prompt: str) -> Optional[dict]:
    """Run the strategic prompt against the Anthropic Messages API.

    Returns the parsed JSON dict or None on any failure (no key, API error,
    malformed JSON). Mirrors LandingGenerator._call_claude on purpose so we
    don't depend on the anthropic Python SDK (it's not in requirements.txt).
    """
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        logger.warning('Strategic opportunity: ANTHROPIC_API_KEY missing.')
        return None

    try:
        import requests
        resp = requests.post(
            ANTHROPIC_API_URL,
            headers={
                'x-api-key': api_key,
                'anthropic-version': '2023-06-01',
                'content-type': 'application/json',
            },
            json={
                'model': STRATEGIC_MODEL,
                'max_tokens': 1200,
                'messages': [{'role': 'user', 'content': prompt}],
            },
            timeout=90,
        )
        if not resp.ok:
            logger.warning(
                'Strategic Claude call HTTP %s: %s',
                resp.status_code, resp.text[:300],
            )
            return None
        data = resp.json()
        text = ''
        for block in (data.get('content') or []):
            if block.get('type') == 'text':
                text += block.get('text') or ''
        text = text.strip()
        # Strip accidental markdown fencing in case the model adds it.
        if text.startswith('```'):
            text = text.strip('`')
            if text.lower().startswith('json'):
                text = text[4:].lstrip('\n')
        return json.loads(text)
    except Exception as e:  # noqa: BLE001
        logger.warning('Claude strategic call failed: %s', e)
        return None


# ---------------------------------------------------------------------------
# Per-site driver
# ---------------------------------------------------------------------------

def summarize_existing_pages(site, limit: int = 30) -> str:
    """One-line summary per existing landing/post the LLM can read to avoid
    duplicates. Bounded to `limit` rows."""
    from .models import HostedLanding, HostedPost

    lines: list[str] = []
    landings = HostedLanding.objects.filter(site=site).only(
        'target_keyword', 'h1', 'page_subtype'
    )[:limit]
    for l in landings:
        kw = l.target_keyword or '-'
        lines.append(f'    - LANDING [{l.page_subtype}] kw="{kw}" h1="{l.h1[:70]}"')
    remaining = max(0, limit - len(lines))
    if remaining > 0:
        posts = HostedPost.objects.filter(site=site).only('title', 'slug')[:remaining]
        for p in posts:
            lines.append(f'    - ARTICLE slug={p.slug} title="{p.title[:70]}"')
    if not lines:
        return '    (aucune page publiée pour l\'instant)'
    return '\n'.join(lines)


def summarize_serp(keyword: str, language: str = 'fr', country: str = 'ca') -> str:
    """Best-effort SERP top-5 summary (titles only). Used to feed the LLM
    so it can propose a differentiated angle."""
    api_key = os.environ.get('SERPER_API_KEY')
    if not api_key:
        return ''
    try:
        import requests
        res = requests.post(
            'https://google.serper.dev/search',
            headers={'X-API-KEY': api_key, 'Content-Type': 'application/json'},
            json={'q': keyword, 'gl': country, 'hl': language, 'num': 5},
            timeout=8,
        )
        if not res.ok:
            return ''
        organic = res.json().get('organic') or []
        lines = []
        for i, row in enumerate(organic[:5], start=1):
            t = (row.get('title') or '').strip()[:90]
            link = (row.get('link') or '').strip()[:80]
            lines.append(f'    {i}. "{t}" - {link}')
        return '\n'.join(lines) or ''
    except Exception as e:  # noqa: BLE001
        logger.warning('Serper SERP summary failed for %r: %s', keyword, e)
        return ''


def propose_opportunity(site, tracked_keyword) -> Optional[dict]:
    """Build the full strategic context for one (site, keyword) pair, call
    Claude, and return the structured concept + traffic estimate dict.

    Returns None if Claude is unavailable or returns malformed JSON. The
    caller decides whether to skip or store a fallback.
    """
    keyword = tracked_keyword.keyword
    intent = tracked_keyword.intent
    language = tracked_keyword.language or site.default_language or 'fr'

    # Latest SERP position from SerpRank (if any).
    current_position = None
    try:
        from .models import SerpRank
        latest = (
            SerpRank.objects.filter(tracked=tracked_keyword)
            .order_by('-recorded_at')
            .first()
        )
        if latest:
            current_position = latest.position
    except Exception:  # noqa: BLE001
        pass

    monthly_volume = fetch_keyword_volume(keyword, language=language)
    estimate = compute_traffic_estimate(
        monthly_volume=monthly_volume or 0,
        target_position=5,
        business_model=site.business_model or 'personal_blog',
    )

    existing_pages_summary = summarize_existing_pages(site)
    serp_summary = summarize_serp(keyword, language=language)

    prompt = build_strategic_prompt(
        site=site,
        keyword=keyword,
        intent=intent,
        current_position=current_position,
        monthly_volume=monthly_volume,
        projected_visits=estimate['estimated_visits'],
        existing_pages_summary=existing_pages_summary,
        serp_summary=serp_summary,
    )

    concept = call_claude_for_opportunity(prompt)
    if not concept:
        return None

    return {
        'concept': concept,
        'estimate': estimate,
        'current_position': current_position,
        'language': language,
    }


def has_matching_landing(site, keyword: str) -> bool:
    """True if a HostedLanding already targets this keyword (case-insensitive).

    Used to skip opportunities we've already actioned.
    """
    from .models import HostedLanding
    kw = (keyword or '').strip().lower()
    if not kw:
        return False
    return HostedLanding.objects.filter(
        site=site, target_keyword__iexact=kw
    ).exists()


def candidate_keywords(site) -> Iterable:
    """Active tracked keywords whose intent is worth a dedicated page AND
    which don't already have a matching landing. Returns a queryset."""
    from .models import TrackedKeyword
    qs = TrackedKeyword.objects.filter(
        site=site, is_active=True,
    ).exclude(intent='info')  # info-intent gets articles, not landings
    keep = []
    for tk in qs:
        if not has_matching_landing(site, tk.keyword):
            keep.append(tk.id)
    return TrackedKeyword.objects.filter(id__in=keep).order_by('-updated_at')
