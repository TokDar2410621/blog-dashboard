"""Indexer + retriever for SiteMemory RAG.

Two public functions:

- `index_source(site, kind, content, source_ref, title='')` chunks, embeds, and
  upserts memory rows for one source. Idempotent via content_hash: re-running
  on unchanged content is a no-op (zero new embedding calls).

- `retrieve(site, query, k=8, kinds=None)` embeds the query and returns the
  top-k SiteMemory rows by cosine distance, optionally filtered by kind. This
  is what ArticleGenerator calls before each Claude prompt to bypass the
  stateless context limitation.

Why a single module vs methods on the model: keeps Django imports out of the
chunking/embedding utilities so they stay testable in isolation, and keeps the
SiteMemory model itself simple.
"""
from __future__ import annotations

import logging
from typing import Iterable

from django.db import transaction

from .chunking import chunk_markdown
from .embeddings import (
    EMBEDDING_DIMS,
    EmbeddingError,
    content_hash,
    embed_batch,
    embed_text,
    estimate_tokens,
)

logger = logging.getLogger(__name__)


def index_source(
    site,
    kind: str,
    content: str,
    source_ref: str = '',
    title: str = '',
    metadata: dict | None = None,
) -> dict:
    """Chunk, embed, and upsert SiteMemory rows for a single source.

    Idempotency: deletes prior rows with same (site, kind, source_ref), then
    inserts the new chunks. Caller can pass an empty content to wipe.

    Returns {'created': n, 'reused': m, 'skipped_empty': bool}.
    """
    from .models import SiteMemory  # Local to avoid app-loading cycles.

    metadata = metadata or {}
    content = (content or '').strip()

    # Empty content -> just wipe the prior rows for this source.
    if not content:
        deleted = SiteMemory.objects.filter(
            site=site, kind=kind, source_ref=source_ref
        ).delete()
        return {'created': 0, 'reused': 0, 'skipped_empty': True, 'deleted': deleted[0]}

    chunks = chunk_markdown(content)
    if not chunks:
        return {'created': 0, 'reused': 0, 'skipped_empty': True}

    # Pre-compute hashes so we can avoid re-embedding chunks that already exist
    # (e.g. user edited a single paragraph - 90% of chunks unchanged).
    hashes = [content_hash(body) for _, body in chunks]

    existing = {
        m.content_hash: m
        for m in SiteMemory.objects.filter(
            site=site, kind=kind, source_ref=source_ref,
            content_hash__in=hashes,
        )
    }

    # Decide which chunks need a fresh embedding.
    to_embed_idx = [i for i, h in enumerate(hashes) if h not in existing]
    to_embed_texts = [chunks[i][1] for i in to_embed_idx]

    new_embeddings: list[list[float]] = []
    if to_embed_texts:
        try:
            new_embeddings = embed_batch(to_embed_texts, input_type='document')
        except EmbeddingError as e:
            logger.warning('Memory indexing skipped (%s): %s', site.id, e)
            return {'created': 0, 'reused': 0, 'error': str(e)}

    with transaction.atomic():
        # Wipe prior rows for this source so we don't accumulate stale chunks
        # if the source shrank.
        SiteMemory.objects.filter(
            site=site, kind=kind, source_ref=source_ref
        ).exclude(content_hash__in=hashes).delete()

        created = 0
        reused = 0
        embed_iter = iter(new_embeddings)
        for i, ((chunk_title, body), h) in enumerate(zip(chunks, hashes)):
            if h in existing:
                # Update non-embedding fields in case title/metadata changed.
                row = existing[h]
                row.title = chunk_title or title
                row.metadata = metadata
                row.save(update_fields=['title', 'metadata', 'updated_at'])
                reused += 1
                continue
            embedding = next(embed_iter, None)
            if embedding is None:
                continue
            SiteMemory.objects.create(
                site=site,
                kind=kind,
                title=chunk_title or title,
                content=body,
                embedding=embedding,
                source_ref=source_ref,
                content_hash=h,
                token_count=estimate_tokens(body),
                metadata=metadata,
            )
            created += 1

    return {'created': created, 'reused': reused, 'skipped_empty': False}


def retrieve(
    site,
    query: str,
    k: int = 8,
    kinds: Iterable[str] | None = None,
) -> list[dict]:
    """Top-k nearest memory chunks to `query` for this site.

    Returns list of dicts: {kind, title, content, source_ref, distance, score}.
    `score` = 1 - cosine_distance, so higher = more similar (easier to reason
    about than raw distance).
    """
    from pgvector.django import CosineDistance

    from .models import SiteMemory

    query = (query or '').strip()
    if not query:
        return []

    try:
        q_embedding = embed_text(query, input_type='query')
    except EmbeddingError as e:
        logger.warning('Memory retrieve skipped (%s): %s', site.id, e)
        return []

    qs = SiteMemory.objects.filter(site=site, embedding__isnull=False)
    if kinds:
        qs = qs.filter(kind__in=list(kinds))

    qs = (
        qs.annotate(distance=CosineDistance('embedding', q_embedding))
        .order_by('distance')[:k]
    )

    out = []
    for m in qs:
        out.append({
            'kind': m.kind,
            'title': m.title,
            'content': m.content,
            'source_ref': m.source_ref,
            'distance': float(m.distance) if m.distance is not None else None,
            'score': (1.0 - float(m.distance)) if m.distance is not None else None,
        })
    return out


def format_memory_block(retrieved: list[dict], max_chars: int = 4000) -> str:
    """Format retrieved chunks for injection into the Claude prompt.

    Bounded so we don't blow the context window: if retrieved chunks total
    > max_chars, we drop the lowest-scored ones until we fit.
    """
    if not retrieved:
        return ''

    label_map = {
        'article': 'Article publie',
        'kb': 'Knowledge base',
        'audit': 'Audit SEO',
        'decision': 'Decision editoriale',
        'manual': 'Note manuelle',
    }

    lines: list[str] = []
    total = 0
    for r in retrieved:
        label = label_map.get(r['kind'], r['kind'])
        title = r['title'] or '(sans titre)'
        body = r['content'].strip()
        block = f"--- [{label}] {title} ---\n{body}\n"
        if total + len(block) > max_chars:
            break
        lines.append(block)
        total += len(block)

    if not lines:
        return ''

    return (
        "## MEMOIRE DU SITE (extraits pertinents tires d'articles passes, KB, "
        "audits et notes manuelles - utilise pour rester coherent avec ce qui "
        "a deja ete publie et la voix etablie)\n\n"
        + '\n'.join(lines)
    )
