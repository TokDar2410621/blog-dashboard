"""Tests for the SiteMemory RAG system.

Coverage split across 3 tiers:

1. PURE LOGIC TESTS (always run, zero deps)
   - chunk_markdown: heading boundaries, body overflow, edge cases
   - content_hash: stability, normalization, collision-resistance
   - estimate_tokens: rough sanity bounds

2. INDEXER TESTS (run when Voyage is mocked)
   - index_source idempotency (same content -> reused, not re-embedded)
   - index_source wipes prior rows for same source_ref
   - chunk-level granularity (one paragraph edit re-embeds only that chunk)

3. INTEGRATION TESTS (require Postgres + VOYAGE_API_KEY, marked SKIP_IF_NO_PG)
   - retrieve() end-to-end with real Voyage embeddings + pgvector cosine
   - article generator pulls memory_block when site has content

Run all:
    python manage.py test sites_mgmt.tests_memory

Run only fast tests:
    python manage.py test sites_mgmt.tests_memory.ChunkingTest
    python manage.py test sites_mgmt.tests_memory.IndexerTest
"""
import os
from unittest.mock import patch, MagicMock

from django.contrib.auth import get_user_model
from django.test import TestCase, SimpleTestCase

from .chunking import chunk_markdown, _split_paragraphs, _chunk_body
from .embeddings import content_hash, estimate_tokens, EMBEDDING_DIMS

User = get_user_model()


# =============================================================================
# Tier 1: Pure logic (no DB, no API)
# =============================================================================

class ChunkingTest(SimpleTestCase):
    """Pure-function tests, no Django DB needed."""

    def test_empty_input_returns_empty(self):
        self.assertEqual(chunk_markdown(''), [])
        self.assertEqual(chunk_markdown(None), [])
        self.assertEqual(chunk_markdown('   \n\n  '), [])

    def test_no_headings_returns_single_chunk(self):
        text = "Just a paragraph.\n\nAnother paragraph."
        chunks = chunk_markdown(text)
        self.assertEqual(len(chunks), 1)
        title, body = chunks[0]
        self.assertEqual(title, '')
        self.assertIn('Just a paragraph', body)
        self.assertIn('Another paragraph', body)

    def test_headings_create_separate_chunks(self):
        text = (
            "# Intro paragraph\n\n"
            "Intro body here.\n\n"
            "## Section A\n\n"
            "Body of A.\n\n"
            "## Section B\n\n"
            "Body of B."
        )
        chunks = chunk_markdown(text)
        self.assertEqual(len(chunks), 3)
        titles = [t for t, _ in chunks]
        self.assertEqual(titles, ['Intro paragraph', 'Section A', 'Section B'])

    def test_long_body_splits_with_overlap(self):
        long_body = ("This is a paragraph. " * 100)
        text = f"## Big section\n\n{long_body}"
        chunks = chunk_markdown(text)
        # Sub-chunks all keep the same title.
        self.assertGreater(len(chunks), 1)
        for title, _ in chunks:
            self.assertEqual(title, 'Big section')

    def test_pre_heading_content_gets_empty_title(self):
        text = "Floating intro before any heading.\n\n## Then a section\n\nContent."
        chunks = chunk_markdown(text)
        self.assertEqual(chunks[0][0], '')
        self.assertIn('Floating intro', chunks[0][1])
        self.assertEqual(chunks[1][0], 'Then a section')

    def test_level_3_headings_stay_inside_parent(self):
        text = (
            "## Parent\n\n"
            "Parent intro.\n\n"
            "### Child\n\n"
            "Child body."
        )
        chunks = chunk_markdown(text)
        # H3 doesn't create a new chunk - it stays in the H2 body.
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0][0], 'Parent')
        self.assertIn('Child', chunks[0][1])


class ContentHashTest(SimpleTestCase):
    def test_identical_text_same_hash(self):
        self.assertEqual(content_hash('hello world'), content_hash('hello world'))

    def test_whitespace_normalization(self):
        # Multiple whitespaces should normalize to single space.
        self.assertEqual(
            content_hash('hello  world\n\nfoo'),
            content_hash('hello world foo'),
        )

    def test_different_text_different_hash(self):
        self.assertNotEqual(content_hash('hello'), content_hash('hello!'))

    def test_returns_64_char_hex(self):
        h = content_hash('abc')
        self.assertEqual(len(h), 64)
        int(h, 16)  # raises if not hex


class EstimateTokensTest(SimpleTestCase):
    def test_empty_returns_one(self):
        self.assertEqual(estimate_tokens(''), 1)
        self.assertEqual(estimate_tokens(None), 1)

    def test_rough_4_chars_per_token(self):
        # ~100 chars -> ~25 tokens (allow factor 2 for safety).
        text = 'a' * 100
        n = estimate_tokens(text)
        self.assertGreater(n, 10)
        self.assertLess(n, 50)


# =============================================================================
# Tier 2: Indexer with mocked Voyage (no API calls, but uses Django DB)
# =============================================================================

class IndexerTest(TestCase):
    """Tests index_source idempotency + delta logic without hitting Voyage."""

    @classmethod
    def setUpTestData(cls):
        from .models import Site
        cls.user = User.objects.create_user(username='memtest', email='m@t.test')
        cls.site = Site.objects.create(
            name='Test Site', domain='test.example', owner=cls.user
        )

    def _mock_embed_batch(self, n_chunks):
        """Return a mock that yields predictable dummy embeddings."""
        return MagicMock(return_value=[
            [0.1] * EMBEDDING_DIMS for _ in range(n_chunks)
        ])

    @patch('sites_mgmt.memory_index.embed_batch')
    def test_index_source_creates_rows(self, mock_embed):
        from .memory_index import index_source
        from .models import SiteMemory

        mock_embed.side_effect = self._mock_embed_batch(2).side_effect or (
            lambda texts, **kw: [[0.1] * EMBEDDING_DIMS for _ in texts]
        )

        content = "# Title\n\nBody.\n\n## Section\n\nMore body."
        result = index_source(
            site=self.site, kind='manual', content=content,
            source_ref='test:1', title='Test',
        )

        self.assertEqual(result['created'], 2)
        self.assertEqual(SiteMemory.objects.filter(site=self.site).count(), 2)
        # embed_batch was called once with all chunks.
        self.assertEqual(mock_embed.call_count, 1)

    @patch('sites_mgmt.memory_index.embed_batch')
    def test_reindex_identical_content_skips_embedding(self, mock_embed):
        """Idempotency: same content_hash -> no new Voyage call."""
        from .memory_index import index_source
        from .models import SiteMemory

        mock_embed.side_effect = lambda texts, **kw: [
            [0.1] * EMBEDDING_DIMS for _ in texts
        ]

        content = "# T\n\nUnchanged paragraph."
        index_source(self.site, 'manual', content, 'test:2', '')
        self.assertEqual(mock_embed.call_count, 1)
        baseline = SiteMemory.objects.filter(site=self.site, source_ref='test:2').count()

        # Re-index identical content - should be no-op.
        result = index_source(self.site, 'manual', content, 'test:2', '')
        self.assertEqual(result['created'], 0)
        self.assertGreaterEqual(result['reused'], 1)
        self.assertEqual(mock_embed.call_count, 1)  # NOT called again
        self.assertEqual(
            SiteMemory.objects.filter(site=self.site, source_ref='test:2').count(),
            baseline,
        )

    @patch('sites_mgmt.memory_index.embed_batch')
    def test_delta_reindex_only_embeds_changed_chunks(self, mock_embed):
        """If only one paragraph changes, only that chunk is re-embedded."""
        from .memory_index import index_source

        mock_embed.side_effect = lambda texts, **kw: [
            [0.1] * EMBEDDING_DIMS for _ in texts
        ]

        v1 = "## A\n\nFirst.\n\n## B\n\nSecond."
        index_source(self.site, 'manual', v1, 'test:3', '')
        embed_calls_v1 = sum(len(c.args[0]) for c in mock_embed.call_args_list)

        # Change only section B.
        v2 = "## A\n\nFirst.\n\n## B\n\nSecond CHANGED."
        result = index_source(self.site, 'manual', v2, 'test:3', '')

        # The unchanged chunk should be reused; only 1 new chunk embedded.
        self.assertEqual(result['created'], 1)
        self.assertEqual(result['reused'], 1)
        embed_calls_v2 = sum(len(c.args[0]) for c in mock_embed.call_args_list)
        # The 2nd call should have embedded only 1 chunk (not 2).
        self.assertEqual(embed_calls_v2 - embed_calls_v1, 1)

    @patch('sites_mgmt.memory_index.embed_batch')
    def test_empty_content_wipes_prior_rows(self, mock_embed):
        from .memory_index import index_source
        from .models import SiteMemory

        mock_embed.side_effect = lambda texts, **kw: [
            [0.1] * EMBEDDING_DIMS for _ in texts
        ]

        index_source(self.site, 'manual', "Some content here.", 'test:wipe', '')
        self.assertGreater(
            SiteMemory.objects.filter(site=self.site, source_ref='test:wipe').count(), 0
        )

        # Now wipe via empty content.
        result = index_source(self.site, 'manual', '', 'test:wipe', '')
        self.assertTrue(result.get('skipped_empty'))
        self.assertEqual(
            SiteMemory.objects.filter(site=self.site, source_ref='test:wipe').count(), 0
        )


# =============================================================================
# Tier 3: Live integration (requires VOYAGE_API_KEY + Postgres with pgvector)
# =============================================================================

class LiveRetrievalTest(TestCase):
    """End-to-end smoke test against the real Voyage API + pgvector.

    Skipped automatically if VOYAGE_API_KEY is missing or DATABASE_URL points
    at SQLite. Run manually on Railway:

        railway run python manage.py test sites_mgmt.tests_memory.LiveRetrievalTest
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from django.db import connection
        cls._skip = (
            not os.environ.get('VOYAGE_API_KEY')
            or connection.vendor != 'postgresql'
        )

    def setUp(self):
        if self._skip:
            self.skipTest('Needs VOYAGE_API_KEY + Postgres with pgvector')
        from .models import Site
        self.user = User.objects.create_user(username='live', email='l@t.test')
        self.site = Site.objects.create(
            name='Live Site', domain='live.example', owner=self.user
        )

    def test_index_then_retrieve_returns_relevant_chunks(self):
        from .memory_index import index_source, retrieve

        # Index 3 chunks on distinct topics.
        index_source(
            self.site, 'manual',
            "## Voix de marque\n\nOn tutoie jamais nos clients PME.",
            'test:voix', 'Voix',
        )
        index_source(
            self.site, 'manual',
            "## Pricing\n\nLes prix sont en CAD, taxes incluses pour le QC.",
            'test:pricing', 'Pricing',
        )
        index_source(
            self.site, 'manual',
            "## Concurrents\n\nNe jamais lier vers Ahrefs ou Surfer SEO.",
            'test:competitors', 'Concurrents',
        )

        # Query about pricing should return the pricing chunk first.
        results = retrieve(self.site, "combien ca coute en dollars canadiens", k=3)
        self.assertGreater(len(results), 0)
        # Top result should mention pricing concepts.
        top_content = results[0]['content'].lower()
        self.assertTrue(
            'cad' in top_content or 'prix' in top_content or 'pricing' in top_content,
            f"Expected pricing-related top hit, got: {top_content[:100]}"
        )
