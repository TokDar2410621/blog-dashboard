"""Markdown-aware chunker for SiteMemory.

Strategy: split on top-level markdown headings (#, ##) so each chunk preserves
semantic boundaries. Within a heading, if the body exceeds `target_tokens`, fall
back to paragraph-window splitting with overlap so context spans aren't broken
mid-thought.

Returns a list of (title, body) tuples. `title` is the nearest heading above
the chunk (or '' for body-only chunks); it's used as the SiteMemory.title field
and helps retrieval relevance ('Voix de marque' is itself a useful signal).
"""
from __future__ import annotations

import re

# Target chunk size in characters (~125-250 tokens at 4 char/token).
# Big enough for a meaningful paragraph, small enough that top-8 retrieval
# fits comfortably in the LLM prompt without bloating cache writes.
TARGET_CHARS = 1000
MAX_CHARS = 1500  # Hard cap before forced split.
OVERLAP_CHARS = 100  # Tail of previous chunk repeated at chunk start.


def _split_paragraphs(text: str) -> list[str]:
    """Split on blank lines, preserving non-empty paragraphs."""
    parts = re.split(r'\n\s*\n', text or '')
    return [p.strip() for p in parts if p.strip()]


def _chunk_body(body: str, max_chars: int = MAX_CHARS) -> list[str]:
    """Split a heading-less body into windowed chunks under `max_chars`.

    Greedy paragraph packing: keep concatenating until we'd exceed the cap,
    then start a fresh chunk seeded with overlap from the previous one.
    """
    paragraphs = _split_paragraphs(body)
    if not paragraphs:
        return []
    chunks: list[str] = []
    current = ''
    for p in paragraphs:
        # If a single paragraph blows the cap, hard-split it on sentences.
        if len(p) > max_chars:
            if current:
                chunks.append(current)
                current = ''
            sentences = re.split(r'(?<=[.!?])\s+', p)
            buf = ''
            for s in sentences:
                if len(buf) + len(s) + 1 > max_chars and buf:
                    chunks.append(buf.strip())
                    buf = s
                else:
                    buf = (buf + ' ' + s).strip() if buf else s
            if buf:
                current = buf
            continue
        # Normal case: pack greedily.
        candidate = (current + '\n\n' + p).strip() if current else p
        if len(candidate) > max_chars and current:
            chunks.append(current.strip())
            # Seed next chunk with tail overlap to keep context flowing.
            tail = current[-OVERLAP_CHARS:] if OVERLAP_CHARS else ''
            current = (tail + '\n\n' + p).strip() if tail else p
        else:
            current = candidate
    if current.strip():
        chunks.append(current.strip())
    return chunks


def chunk_markdown(text: str, max_chars: int = MAX_CHARS) -> list[tuple[str, str]]:
    """Return list of (title, chunk_body) preserving heading context.

    - `# Title` and `## Subtitle` mark section boundaries.
    - Each section >max_chars is split into multiple windowed chunks, all
      keeping the same `title`.
    - Pre-first-heading content (intro paragraphs) gets title=''.
    """
    if not text or not text.strip():
        return []

    # Match level-1 and level-2 headings only - level 3+ stay inside their parent.
    sections: list[tuple[str, str]] = []
    lines = text.splitlines()
    current_title = ''
    current_buf: list[str] = []
    heading_re = re.compile(r'^(#{1,2})\s+(.+?)\s*$')

    def flush():
        body = '\n'.join(current_buf).strip()
        if body:
            sections.append((current_title, body))

    for line in lines:
        m = heading_re.match(line)
        if m:
            flush()
            current_title = m.group(2).strip()
            current_buf = []
        else:
            current_buf.append(line)
    flush()

    # Expand sections too big for one chunk.
    out: list[tuple[str, str]] = []
    for title, body in sections:
        if len(body) <= max_chars:
            out.append((title, body))
            continue
        for piece in _chunk_body(body, max_chars=max_chars):
            out.append((title, piece))
    return out
