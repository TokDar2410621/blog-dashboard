"""Landing-page generator.

Produces structured landing payloads (H1, hero_subtitle, value_props, social_proof,
FAQ, bottom CTA) for HostedLanding. Different from ArticleGenerator: the goal
is conversion-shaped block content, not long-form prose.

Inputs:
  - target keyword (mandatory)
  - site (HostedLanding.site, used for tone / business_model / CTA defaults)
  - optional primary_cta_text / primary_cta_url (overrides site defaults)
  - optional value_props seed (the LLM expands them)

Output:
  - dict with the same shape as HostedLanding fields, ready to be passed to
    HostedLanding.objects.create(**payload, site=site).
"""
from __future__ import annotations

import json
import logging
import os
import re

import requests
from django.utils.text import slugify

logger = logging.getLogger(__name__)


ANTHROPIC_API_URL = 'https://api.anthropic.com/v1/messages'
DEFAULT_MODEL = 'claude-sonnet-5'


class LandingGeneratorError(Exception):
    pass


class LandingGenerator:
    """Generate a structured landing payload from a keyword + site context."""

    def __init__(self, site, language: str | None = None):
        self.site = site
        self.language = (language or site.default_language or 'fr').lower()
        if self.language not in ('fr', 'en', 'es'):
            self.language = 'fr'

    # ------------------------------------------------------------------
    # Claude API
    # ------------------------------------------------------------------

    def _call_claude(self, prompt: str, max_tokens: int = 3000) -> str:
        api_key = os.environ.get('ANTHROPIC_API_KEY')
        if not api_key:
            raise LandingGeneratorError(
                'ANTHROPIC_API_KEY missing - cannot generate landing.'
            )
        resp = requests.post(
            ANTHROPIC_API_URL,
            headers={
                'x-api-key': api_key,
                'anthropic-version': '2023-06-01',
                'content-type': 'application/json',
            },
            json={
                'model': DEFAULT_MODEL,
                'max_tokens': max_tokens,
                # Sonnet 5 runs adaptive thinking by default when `thinking` is
                # omitted, which prepends a thinking block to `content` (so the
                # old content[0]['text'] KeyError'd). We want the JSON directly,
                # not reasoning, so disable it and keep the full token budget.
                'thinking': {'type': 'disabled'},
                'messages': [{'role': 'user', 'content': prompt}],
            },
            timeout=120,
        )
        resp.raise_for_status()
        body = resp.json()
        for block in body.get('content') or []:
            if block.get('type') == 'text':
                return block.get('text') or ''
        raise LandingGeneratorError(
            f"Claude returned no text block (stop_reason={body.get('stop_reason')!r})."
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(
        self,
        keyword: str,
        primary_cta_text: str | None = None,
        primary_cta_url: str | None = None,
        value_props_seed: list | None = None,
        page_subtype: str = 'service',
    ) -> dict:
        """Generate a landing payload. Returns a dict ready for HostedLanding.create."""
        keyword = (keyword or '').strip()
        if not keyword:
            raise LandingGeneratorError('keyword is required')

        cta_text = primary_cta_text or self.site.primary_cta_text or 'Reserve ton appel'
        cta_url = primary_cta_url or self.site.primary_cta_url or '/contact'

        lang_label = {'fr': 'francais', 'en': 'English', 'es': 'espanol'}[self.language]
        bm = self.site.business_model or 'agency'
        kb = (self.site.knowledge_base or '')[:1500]

        seed_block = ''
        if value_props_seed:
            seed_block = (
                "\nValue props imposees (a developper, ne pas en inventer d'autres):\n"
                + json.dumps(value_props_seed, ensure_ascii=False)
            )

        prompt = f"""Tu es un copywriter SEO specialise en landing pages conversion-driven.
Tu vas produire une landing page complete, structuree, en {lang_label}.

KEYWORD CIBLE: "{keyword}"
BUSINESS MODEL: {bm}
SITE: {self.site.name} ({self.site.domain or 'no domain'})
KNOWLEDGE BASE (extrait):
{kb or "(vide)"}

CTA PRINCIPAL: "{cta_text}" -> {cta_url}
TYPE DE PAGE: {page_subtype}
{seed_block}

Reponds UNIQUEMENT en JSON strict (pas de markdown, pas de backticks, pas de texte hors JSON):
{{
  "title": "<title SEO 50-60 chars incluant le keyword>",
  "meta_description": "<155-160 chars>",
  "h1": "<H1 visible, 60-90 chars, emotionnel>",
  "hero_subtitle": "<1-2 phrases promesse claire>",
  "value_props": [
    {{"icon": "<emoji>", "title": "<3-5 mots>", "description": "<1 phrase>"}},
    ... (3 a 5 items)
  ],
  "social_proof": [
    {{"type": "stat", "label": "<chiffre cle>", "value": "<valeur>"}},
    ... (2 a 3 items)
  ],
  "faq": [
    {{"question": "<question reelle d un prospect>", "answer": "<reponse 2-3 phrases>"}},
    ... (4 a 6 items)
  ],
  "body_markdown": "<2-3 paragraphes markdown qui explicitent la promesse, sans repeter les value_props>",
  "cta_bottom_text": "<reformulation du CTA, plus directe>",
  "rationale": "<1 phrase qui explique l angle choisi>"
}}

IMPORTANT:
- Tout en {lang_label}.
- Pas de jargon corporate vide.
- Le keyword "{keyword}" doit apparaitre dans title, h1, meta_description.
- Les value_props doivent etre des benefices, pas des features.
"""
        raw = self._call_claude(prompt, max_tokens=3500)
        # Extract JSON (sometimes wrapped in markdown despite instructions)
        match = re.search(r'\{[\s\S]*\}', raw)
        if not match:
            raise LandingGeneratorError('Claude did not return JSON.')
        try:
            data = json.loads(match.group())
        except json.JSONDecodeError as e:
            raise LandingGeneratorError(f'Invalid JSON from Claude: {e}') from e

        # Build the final HostedLanding payload
        slug = slugify(data.get('title') or keyword)[:200]
        schema_type = {
            'service': 'Service',
            'product': 'Product',
            'pillar': 'WebPage',
            'comparison': 'WebPage',
            'local': 'LocalBusiness',
        }.get(page_subtype, 'WebPage')

        payload = {
            'title': (data.get('title') or keyword)[:200],
            'slug': slug,
            'h1': (data.get('h1') or data.get('title') or keyword)[:200],
            'hero_subtitle': (data.get('hero_subtitle') or '')[:500],
            'hero_cta_text': cta_text[:80],
            'hero_cta_url': cta_url[:500],
            'value_props': data.get('value_props') or [],
            'social_proof': data.get('social_proof') or [],
            'faq': data.get('faq') or [],
            'cta_bottom_text': (data.get('cta_bottom_text') or cta_text)[:80],
            'cta_bottom_url': cta_url[:500],
            'body_markdown': data.get('body_markdown') or '',
            'target_keyword': keyword[:200],
            'meta_description': (data.get('meta_description') or '')[:300],
            'schema_type': schema_type,
            'page_subtype': page_subtype,
            'language': self.language,
            'status': 'draft',
        }
        return payload
