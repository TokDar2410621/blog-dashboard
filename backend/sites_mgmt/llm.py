"""Shared LLM text call with an automatic DeepSeek fallback.

Gridar calls Anthropic (Claude) over raw HTTP in several modules. When the
primary call fails - notably the self-imposed usage-limit ("You have reached
your specified API usage limits") that caps the account until it resets - we
fall back to DeepSeek (OpenAI-compatible) so generation keeps working.

Returns the raw assistant text; callers parse JSON themselves (unchanged), so
this is a drop-in for the existing per-module Anthropic blocks.

Env:
  ANTHROPIC_API_KEY  (primary)
  DEEPSEEK_API_KEY   (fallback)  - set on Railway, never in a committed file.

Note (Loi 25 / privacy): DeepSeek is a third-party (China) API. The fallback
only fires when Anthropic is unavailable; treat it as a stopgap for continuity,
and be mindful of what client content flows through it.
"""
import logging
import os

import requests

logger = logging.getLogger(__name__)

ANTHROPIC_API_URL = 'https://api.anthropic.com/v1/messages'
ANTHROPIC_MODEL = 'claude-sonnet-5'
DEEPSEEK_API_URL = 'https://api.deepseek.com/chat/completions'
DEEPSEEK_MODEL = 'deepseek-chat'


class LLMError(Exception):
    pass


def _anthropic_text(prompt, max_tokens, system, timeout):
    """Returns text, or None when no key is configured (caller then tries the
    fallback). Raises LLMError on an API failure (so the fallback fires)."""
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        return None
    body = {
        'model': ANTHROPIC_MODEL,
        'max_tokens': max_tokens,
        # Sonnet 5 enables adaptive thinking by default; disable it so the whole
        # budget goes to the output (thinking can otherwise truncate JSON).
        'thinking': {'type': 'disabled'},
        'messages': [{'role': 'user', 'content': prompt}],
    }
    if system:
        body['system'] = system
    resp = requests.post(
        ANTHROPIC_API_URL,
        headers={
            'x-api-key': api_key,
            'anthropic-version': '2023-06-01',
            'content-type': 'application/json',
        },
        json=body,
        timeout=timeout,
    )
    if not resp.ok:
        raise LLMError(f'anthropic HTTP {resp.status_code}: {resp.text[:200]}')
    data = resp.json()
    text = ''.join(
        (b.get('text') or '')
        for b in (data.get('content') or [])
        if b.get('type') == 'text'
    )
    return text.strip()


def _deepseek_text(prompt, max_tokens, system, timeout):
    """OpenAI-compatible DeepSeek call. Raises LLMError on any failure."""
    api_key = os.environ.get('DEEPSEEK_API_KEY')
    if not api_key:
        raise LLMError('DEEPSEEK_API_KEY missing (fallback unavailable)')
    messages = []
    if system:
        messages.append({'role': 'system', 'content': system})
    messages.append({'role': 'user', 'content': prompt})
    resp = requests.post(
        DEEPSEEK_API_URL,
        headers={
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json',
        },
        json={
            'model': DEEPSEEK_MODEL,
            'max_tokens': max_tokens,
            'messages': messages,
            'stream': False,
        },
        timeout=timeout,
    )
    if not resp.ok:
        raise LLMError(f'deepseek HTTP {resp.status_code}: {resp.text[:200]}')
    data = resp.json()
    choice = (data.get('choices') or [{}])[0]
    return ((choice.get('message') or {}).get('content') or '').strip()


def call_llm(prompt: str, max_tokens: int = 2000, system: str = None,
             timeout: int = 90) -> str:
    """Anthropic first, DeepSeek on failure. Returns the raw text ('' if both
    fail). Never raises - callers already treat empty/None as a soft failure."""
    try:
        text = _anthropic_text(prompt, max_tokens, system, timeout)
        if text:
            return text
        # text is None (no Anthropic key) -> fall through to DeepSeek.
    except Exception as exc:  # noqa: BLE001
        logger.warning('LLM primary (Anthropic) failed, trying DeepSeek: %s', exc)

    try:
        text = _deepseek_text(prompt, max_tokens, system, timeout)
        if text:
            logger.info('LLM served by DeepSeek fallback')
        return text or ''
    except Exception as exc:  # noqa: BLE001
        logger.warning('LLM fallback (DeepSeek) failed: %s', exc)
        return ''


def call_deepseek(prompt: str, max_tokens: int = 800, system: str = None,
                  timeout: int = 20) -> str:
    """DeepSeek en direct, sans passer par Anthropic. Rend '' en cas d'echec.

    `call_llm` place Anthropic en premier, ce qui est le bon ordre quand la
    qualite prime. Pour un travail a fort volume et faible enjeu, appele depuis
    un endpoint public a chaque audit, c'est le cout qui prime : DeepSeek est
    un ordre de grandeur moins cher et suffit largement.

    Ne leve jamais : l'appelant doit pouvoir se rabattre sur autre chose.
    """
    try:
        return _deepseek_text(prompt, max_tokens, system, timeout) or ''
    except Exception as exc:  # noqa: BLE001
        logger.warning('DeepSeek direct call failed: %s', exc)
        return ''
