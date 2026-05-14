"""Embeddings service for SiteMemory RAG.

Provider: Voyage AI (voyage-3.5-lite, 512 dims via Matryoshka truncation).
- Why Voyage: Anthropic-recommended, fits our Claude stack, $0.02/1M tokens.
- Why voyage-3.5-lite vs voyage-3.5: same $0.02/1M tokens but optimized for
  cost/latency at indexing scale. Quality drop is tiny for retrieval.
- Why output_dimension=512 (default is 1024): Matryoshka-trained model lets
  us truncate to 512 dims with near-zero quality loss while halving storage
  and pgvector cosine cost. Matches our pgvector(512) column.

Single env var: VOYAGE_API_KEY. If missing, raises a clear error rather than
silently degrading - we want callers to know when memory isn't being indexed.

Batch API (`embed_batch`) is what indexing pipelines should use: Voyage allows
up to 128 inputs per request, so bulk re-indexing a site of 100 chunks fits
in 1 API call instead of 100.
"""
from __future__ import annotations

import hashlib
import os
from typing import Iterable

EMBEDDING_MODEL = 'voyage-3.5-lite'
EMBEDDING_DIMS = 512
# Voyage caps a single batch at 128 inputs and 120k tokens; we stay safe.
MAX_BATCH_SIZE = 64


class EmbeddingError(Exception):
    """Raised when the embedding provider call fails or is misconfigured."""


def _get_client():
    """Lazy import voyageai so the package isn't required at module load time
    (e.g. during migrations or in environments without the API key)."""
    api_key = os.environ.get('VOYAGE_API_KEY')
    if not api_key:
        raise EmbeddingError(
            'VOYAGE_API_KEY non configuree. Ajoute la sur Railway (Settings > '
            'Variables) ou desactive l\'indexation memoire.'
        )
    try:
        import voyageai  # type: ignore[import-not-found]
    except ImportError as e:
        raise EmbeddingError(f'Package voyageai non installe: {e}')
    return voyageai.Client(api_key=api_key)


def embed_text(text: str, input_type: str = 'document') -> list[float]:
    """Embed a single string. Use input_type='query' for retrieval queries
    (Voyage uses asymmetric encoding for better recall)."""
    if not text or not text.strip():
        raise EmbeddingError('Texte vide')
    client = _get_client()
    result = client.embed(
        texts=[text],
        model=EMBEDDING_MODEL,
        input_type=input_type,
        output_dimension=EMBEDDING_DIMS,
    )
    return result.embeddings[0]


def embed_batch(
    texts: list[str], input_type: str = 'document'
) -> list[list[float]]:
    """Embed many strings in batches of MAX_BATCH_SIZE. Empty inputs are
    embedded as None (caller must filter or handle nulls)."""
    if not texts:
        return []
    client = _get_client()
    out: list[list[float]] = []
    for i in range(0, len(texts), MAX_BATCH_SIZE):
        chunk = texts[i:i + MAX_BATCH_SIZE]
        # Voyage rejects empty strings; substitute a space (will produce a
        # generic embedding, callers should filter empties beforehand).
        safe = [t if (t and t.strip()) else ' ' for t in chunk]
        result = client.embed(
            texts=safe,
            model=EMBEDDING_MODEL,
            input_type=input_type,
            output_dimension=EMBEDDING_DIMS,
        )
        out.extend(result.embeddings)
    return out


def content_hash(text: str) -> str:
    """SHA-256 of normalized text. Used to skip re-embedding identical chunks."""
    normalized = ' '.join((text or '').split())
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()


def estimate_tokens(text: str) -> int:
    """Rough token count for budgeting / metadata. ~4 chars per token in EN/FR.
    Not exact but good enough for chunk-size decisions."""
    return max(1, len(text or '') // 4)
