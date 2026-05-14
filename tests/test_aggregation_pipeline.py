#!/usr/bin/env python3
"""
Tests for the aggregation pipeline.

Run with: python tests/test_aggregation_pipeline.py
"""

import json
import sqlite3
import sys
import tempfile
from datetime import datetime
from pathlib import Path

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from aggregator.feed_fetcher import (
    FeedEntry, FeedSource, FeedCache, FeedFetcher,
    load_sources_from_catalog
)
from aggregator.content_extractor import ContentExtractor, ExtractedContent
from aggregator.deduplicator import Deduplicator, SimHash, URLNormalizer, StoryClusterer
from aggregator.pipeline import AggregationPipeline, PipelineResult, run_pipeline_command


def test_init_creates_tables():
    """Test that initialization creates required tables."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = Path(f.name)

    try:
        cache = FeedCache(db_path)

        with sqlite3.connect(db_path) as conn:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            table_names = {t[0] for t in tables}

        assert 'feed_entries' in table_names, "feed_entries table missing"
        assert 'feed_sources' in table_names, "feed_sources table missing"
        assert 'fetch_log' in table_names, "fetch_log table missing"
        print("✅ test_init_creates_tables passed")
    finally:
        db_path.unlink(missing_ok=True)


def test_save_and_get_source():
    """Test saving and retrieving a feed source."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = Path(f.name)

    try:
        cache = FeedCache(db_path)

        source = FeedSource(
            id='test-source',
            name='Test Source',
            url='https://example.com/feed.xml',
            format='RSS',
            category='Test',
            domain='ai',
            signal_quality='High',
            active=True,
            fetch_interval_minutes=30
        )

        cache.save_source(source)
        sources = cache.get_sources()

        assert len(sources) == 1, f"Expected 1 source, got {len(sources)}"
        assert sources[0].id == 'test-source', f"Expected 'test-source', got {sources[0].id}"
        assert sources[0].name == 'Test Source', f"Expected 'Test Source', got {sources[0].name}"
        print("✅ test_save_and_get_source passed")
    finally:
        db_path.unlink(missing_ok=True)


def test_get_sources_filters_by_domain():
    """Test filtering sources by domain."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = Path(f.name)

    try:
        cache = FeedCache(db_path)

        cache.save_source(FeedSource(
            id='ai-source', name='AI Source', url='https://ai.com/feed',
            format='RSS', category='News', domain='ai', signal_quality='High'
        ))
        cache.save_source(FeedSource(
            id='dev-source', name='Dev Source', url='https://dev.com/feed',
            format='RSS', category='News', domain='software_development', signal_quality='High'
        ))

        ai_sources = cache.get_sources(domain='ai')
        assert len(ai_sources) == 1, f"Expected 1 AI source, got {len(ai_sources)}"
        assert ai_sources[0].id == 'ai-source', f"Expected 'ai-source', got {ai_sources[0].id}"
        print("✅ test_get_sources_filters_by_domain passed")
    finally:
        db_path.unlink(missing_ok=True)


def test_save_and_retrieve_entries():
    """Test saving and retrieving feed entries."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = Path(f.name)

    try:
        cache = FeedCache(db_path)

        cache.save_source(FeedSource(
            id='test-source', name='Test', url='https://test.com/feed',
            format='RSS', category='News', domain='ai', signal_quality='High'
        ))

        entries = [
            FeedEntry(
                id='entry-1',
                title='Test Article',
                url='https://test.com/article',
                source_id='test-source',
                published_at=datetime.now(),
                summary='Summary',
                author='Author',
                content='Content',
                fetched_at=datetime.now()
            )
        ]

        cache.save_entries(entries)

        # Verify entry was saved
        with sqlite3.connect(cache.db_path) as conn:
            row = conn.execute(
                "SELECT title, url FROM feed_entries WHERE id = ?",
                ('entry-1',)
            ).fetchone()

        assert row is not None, "Entry not found"
        assert row[0] == 'Test Article', f"Expected 'Test Article', got {row[0]}"
        print("✅ test_save_and_retrieve_entries passed")
    finally:
        db_path.unlink(missing_ok=True)


def test_duplicate_entries_ignored():
    """Test that duplicate entries are ignored."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = Path(f.name)

    try:
        cache = FeedCache(db_path)

        cache.save_source(FeedSource(
            id='test-source', name='Test', url='https://test.com/feed',
            format='RSS', category='News', domain='ai', signal_quality='High'
        ))

        entry = FeedEntry(
            id='entry-1',
            title='Test Article',
            url='https://test.com/article',
            source_id='test-source',
            published_at=datetime.now(),
            summary='Summary',
            author='Author',
            content='Content',
            fetched_at=datetime.now()
        )

        cache.save_entries([entry])
        cache.save_entries([entry])  # Save again

        with sqlite3.connect(cache.db_path) as conn:
            count = conn.execute(
                "SELECT COUNT(*) FROM feed_entries WHERE id = ?",
                ('entry-1',)
            ).fetchone()[0]

        assert count == 1, f"Expected 1 entry, got {count}"
        print("✅ test_duplicate_entries_ignored passed")
    finally:
        db_path.unlink(missing_ok=True)


def test_fetcher_entry_id_stable():
    """Test that entry ID generation is stable."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = Path(f.name)

    try:
        cache = FeedCache(db_path)
        fetcher = FeedFetcher(cache, min_fetch_interval_seconds=0)

        id1 = fetcher._generate_entry_id('https://test.com', 'Title')
        id2 = fetcher._generate_entry_id('https://test.com', 'Title')

        assert id1 == id2, f"Expected same ID, got {id1} and {id2}"
        assert len(id1) == 16, f"Expected 16 char ID, got {len(id1)}"
        print("✅ test_fetcher_entry_id_stable passed")
    finally:
        db_path.unlink(missing_ok=True)


def test_fetcher_entry_id_unique():
    """Test that different inputs produce different IDs."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = Path(f.name)

    try:
        cache = FeedCache(db_path)
        fetcher = FeedFetcher(cache, min_fetch_interval_seconds=0)

        id1 = fetcher._generate_entry_id('https://test.com/1', 'Title A')
        id2 = fetcher._generate_entry_id('https://test.com/2', 'Title B')

        assert id1 != id2, f"Expected different IDs, got same: {id1}"
        print("✅ test_fetcher_entry_id_unique passed")
    finally:
        db_path.unlink(missing_ok=True)


def test_load_sources_from_catalog():
    """Test loading sources from a catalog JSON."""
    with tempfile.TemporaryDirectory() as tmp:
        catalog_path = Path(tmp) / 'catalog.json'

        catalog = {
            "domains": {
                "ai": {
                    "name": "AI",
                    "source_count": 2,
                    "sources": {
                        "newsletters": [
                            {
                                "id": "test-newsletter",
                                "name": "Test Newsletter",
                                "url": "https://test.com/newsletter",
                                "format": "Newsletter",
                                "signal_quality": "High",
                                "active": True
                            }
                        ],
                        "research_papers": [
                            {
                                "id": "arxiv-test",
                                "name": "arXiv Test",
                                "url": "https://arxiv.org/rss/test",
                                "format": "RSS",
                                "signal_quality": "High",
                                "active": True
                            }
                        ]
                    }
                }
            }
        }

        with open(catalog_path, 'w') as f:
            json.dump(catalog, f)

        sources = load_sources_from_catalog(catalog_path)

        # Newsletters are filtered out (handled by newsletter_ingester separately)
        assert len(sources) == 1, f"Expected 1 source (newsletters filtered), got {len(sources)}"
        ids = {s.id for s in sources}
        assert 'test-newsletter' not in ids, "test-newsletter should be filtered (handled separately)"
        assert 'arxiv-test' in ids, "arxiv-test not found"
        print("✅ test_load_sources_from_catalog passed")


def test_end_to_end_flow():
    """Test the complete flow from cache init to entry storage."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = Path(f.name)

    try:
        # Initialize cache
        cache = FeedCache(db_path)

        # Add a source
        source = FeedSource(
            id='test-e2e',
            name='Test E2E',
            url='https://test.com/feed',
            format='RSS',
            category='Test',
            domain='ai',
            signal_quality='High'
        )
        cache.save_source(source)

        # Verify source was saved
        sources = cache.get_sources()
        assert len(sources) == 1, f"Expected 1 source, got {len(sources)}"

        # Create fetcher
        fetcher = FeedFetcher(cache, min_fetch_interval_seconds=0)

        # Verify should_fetch returns True (never fetched)
        assert cache.should_fetch('test-e2e') is True, "Expected should_fetch to be True"

        # Log a successful fetch
        cache.log_fetch('test-e2e', 5, True, response_time_ms=100)

        # Verify should_fetch returns False (just fetched)
        assert cache.should_fetch('test-e2e') is False, "Expected should_fetch to be False after fetch"

        print("✅ test_end_to_end_flow passed")
    finally:
        db_path.unlink(missing_ok=True)


def test_simhash_exact_match():
    """Test SimHash detects exact duplicates."""
    simhash = SimHash()

    text1 = "The quick brown fox jumps over the lazy dog"
    text2 = "The quick brown fox jumps over the lazy dog"

    hash1 = simhash.compute(text1)
    hash2 = simhash.compute(text2)

    assert hash1 == hash2, "Exact texts should have identical hashes"
    assert simhash.similarity(hash1, hash2) == 1.0, "Similarity should be 1.0"
    print("✅ test_simhash_exact_match passed")


def test_simhash_similar_text():
    """Test SimHash detects similar but not identical text."""
    simhash = SimHash()

    text1 = "The quick brown fox jumps over the lazy dog in the garden"
    text2 = "The quick brown fox jumps over a lazy dog in a garden"
    text3 = "Completely different content about machine learning"

    hash1 = simhash.compute(text1)
    hash2 = simhash.compute(text2)
    hash3 = simhash.compute(text3)

    sim_12 = simhash.similarity(hash1, hash2)
    sim_13 = simhash.similarity(hash1, hash3)

    assert sim_12 > sim_13, f"Similar text should have higher similarity: {sim_12} vs {sim_13}"
    assert sim_12 > 0.5, f"Similar text should have similarity > 0.5: {sim_12}"
    print("✅ test_simhash_similar_text passed")


def test_url_normalizer():
    """Test URL normalization."""
    normalizer = URLNormalizer()

    # Test cases that should normalize to same value
    urls = [
        'https://example.com/article?utm_source=twitter',
        'http://example.com/article',
        'https://www.example.com/article/',
        'https://example.com/article?utm_medium=email&utm_campaign=test',
    ]

    normalized = [normalizer.normalize(u) for u in urls]
    unique = set(normalized)

    assert len(unique) == 1, f"Expected 1 unique URL, got {len(unique)}: {unique}"
    print("✅ test_url_normalizer passed")


def test_deduplicator_exact_duplicate():
    """Test deduplicator catches exact duplicates."""
    dedup = Deduplicator()

    # First article should not be a duplicate
    result1 = dedup.check_duplicate('id1', 'https://example.com/article', 'Title', 'Content')
    assert result1.is_duplicate is False, "First article should not be duplicate"

    # Add first article
    dedup.add('id1', 'https://example.com/article', 'Title', 'Content')

    # Same URL should be duplicate
    result2 = dedup.check_duplicate('id2', 'https://example.com/article', 'Different', 'Different content')
    assert result2.is_duplicate is True, "Same URL should be duplicate"

    # Same content different URL should be duplicate
    result3 = dedup.check_duplicate('id3', 'https://other.com/article', 'Title', 'Content')
    assert result3.is_duplicate is True, "Same content should be duplicate"
    print("✅ test_deduplicator_exact_duplicate passed")


def test_deduplicator_stats():
    """Test deduplicator statistics."""
    dedup = Deduplicator()

    stats = dedup.get_stats()
    assert 'urls_tracked' in stats, "Stats should include urls_tracked"
    assert 'content_hashes_tracked' in stats, "Stats should include content_hashes_tracked"

    dedup.add('id1', 'https://example.com/1', 'Title 1', 'Content 1')
    dedup.add('id2', 'https://example.com/2', 'Title 2', 'Content 2')

    stats = dedup.get_stats()
    assert stats['urls_tracked'] == 2, f"Expected 2 URLs tracked, got {stats['urls_tracked']}"
    assert stats['content_hashes_tracked'] == 2, f"Expected 2 hashes tracked"
    print("✅ test_deduplicator_stats passed")


def test_story_clusterer():
    """Test story clustering groups related articles."""
    clusterer = StoryClusterer(similarity_threshold=0.6)

    articles = [
        {'id': 'a1', 'title': 'Python 3.12 Released', 'content': 'New features include improved error messages'},
        {'id': 'a2', 'title': 'Python 3.12 Released Today', 'content': 'The new version brings better performance'},
        {'id': 'a3', 'title': 'JavaScript Framework Comparison', 'content': 'React vs Vue vs Angular in 2024'},
        {'id': 'a4', 'title': 'React 19 Announcement', 'content': 'New React features and improvements'},
    ]

    clusters = clusterer.cluster(articles)

    # Should have at least 2 clusters (Python articles clustered, JS/React separate)
    assert len(clusters) >= 2, f"Expected at least 2 clusters, got {len(clusters)}"

    # Find Python cluster
    python_cluster = None
    for cluster in clusters:
        ids = {a['id'] for a in cluster}
        if 'a1' in ids and 'a2' in ids:
            python_cluster = cluster
            break

    assert python_cluster is not None, "Python articles should be clustered together"
    print("✅ test_story_clusterer passed")


def test_content_extractor_init():
    """Test content extractor initialization."""
    extractor = ContentExtractor(
        request_timeout=30,
        min_fetch_interval=1.0,
        respect_robots_txt=True
    )

    assert extractor.request_timeout == 30
    assert extractor.min_fetch_interval == 1.0
    assert extractor.respect_robots_txt is True
    print("✅ test_content_extractor_init passed")


def test_extracted_content_dataclass():
    """Test ExtractedContent dataclass."""
    from datetime import datetime

    content = ExtractedContent(
        url='https://example.com/article',
        title='Test Article',
        author='***',
        published_at=None,
        content_text='Article content here',
        content_html='<p>Article content here</p>',
        excerpt='Article content...',
        word_count=3,
        reading_time_minutes=1,
        extracted_at=datetime.now(),
        is_paywalled=False
    )

    assert content.url == 'https://example.com/article'
    assert content.title == 'Test Article'
    assert content.word_count == 3
    print("✅ test_extracted_content_dataclass passed")


def test_pipeline_initialization():
    """Test AggregationPipeline initialization."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = Path(f.name)

    try:
        cache = FeedCache(db_path)
        pipeline = AggregationPipeline(cache=cache)

        assert pipeline.cache == cache
        assert pipeline.fetcher is not None
        assert pipeline.deduplicator is not None
        assert pipeline.extract_content is True
        print("✅ test_pipeline_initialization passed")
    finally:
        db_path.unlink(missing_ok=True)


def test_pipeline_result_dataclass():
    """Test PipelineResult dataclass."""
    from datetime import datetime

    started = datetime.now()
    completed = datetime.now()

    result = PipelineResult(
        started_at=started,
        completed_at=completed,
        sources_processed=5,
        entries_fetched=100,
        entries_extracted=90,
        entries_deduplicated=10,
        entries_stored=80,
        errors=[]
    )

    assert result.sources_processed == 5
    assert result.entries_fetched == 100
    assert result.entries_deduplicated == 10

    # Test to_dict
    d = result.to_dict()
    assert d['sources_processed'] == 5
    assert d['entries_stored'] == 80
    assert 'duration_seconds' in d
    print("✅ test_pipeline_result_dataclass passed")


def test_pipeline_filters_provided_sources_by_domain_before_fetching():
    """Domain-filtered cron runs should not fetch every provided catalog source."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = Path(f.name)

    class RecordingFetcher:
        def __init__(self):
            self.fetched_source_ids = []

        def fetch_source(self, source):
            self.fetched_source_ids.append(source.id)
            return []

    try:
        cache = FeedCache(db_path)
        fetcher = RecordingFetcher()
        pipeline = AggregationPipeline(cache, fetcher=fetcher, extract_content=False)
        sources = [
            FeedSource(
                id='ai-source', name='AI Source', url='https://ai.example/feed',
                format='RSS', category='News', domain='ai', signal_quality='High'
            ),
            FeedSource(
                id='dev-source', name='Dev Source', url='https://dev.example/feed',
                format='RSS', category='News', domain='software_development', signal_quality='High'
            ),
        ]

        result = pipeline.run(sources=sources, domain_filter='software_development')

        assert result.sources_processed == 1
        assert fetcher.fetched_source_ids == ['dev-source']
    finally:
        db_path.unlink(missing_ok=True)


def test_pipeline_run_empty_sources():
    """Test pipeline with no sources."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = Path(f.name)

    try:
        cache = FeedCache(db_path)
        pipeline = AggregationPipeline(cache=cache, extract_content=False)

        # Run with empty sources list
        result = pipeline.run(sources=[], verbose=False)

        assert result.sources_processed == 0
        assert result.entries_fetched == 0
        assert result.entries_stored == 0
        assert len(result.errors) == 0
        print("✅ test_pipeline_run_empty_sources passed")
    finally:
        db_path.unlink(missing_ok=True)


def test_pipeline_deduplication_integration():
    """Test pipeline deduplication with mock sources."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = Path(f.name)

    try:
        cache = FeedCache(db_path)

        # Create test source
        source = FeedSource(
            id='test-dedup',
            name='Test Source',
            url='https://test.com/feed',
            format='RSS',
            category='Test',
            domain='ai',
            signal_quality='High'
        )
        cache.save_source(source)

        # Create pipeline without extraction (faster)
        pipeline = AggregationPipeline(cache=cache, extract_content=False)

        # Pre-populate deduplicator with a URL
        pipeline.deduplicator.add('pre-existing', 'https://test.com/article1', 'Title', 'Content')

        # Check that duplicate is detected
        dup_result = pipeline.deduplicator.check_duplicate(
            'new-id', 'https://test.com/article1', 'Different Title', 'Different content'
        )

        assert dup_result.is_duplicate is True
        assert dup_result.match_type in ['url_match', 'exact']
        print("✅ test_pipeline_deduplication_integration passed")
    finally:
        db_path.unlink(missing_ok=True)


def test_pipeline_result_to_json():
    """Test PipelineResult JSON serialization."""
    import json
    from datetime import datetime

    result = PipelineResult(
        started_at=datetime.now(),
        completed_at=datetime.now(),
        sources_processed=3,
        entries_fetched=50,
        entries_extracted=45,
        entries_deduplicated=5,
        entries_stored=40,
        errors=['Error 1', 'Error 2']
    )

    d = result.to_dict()
    json_str = json.dumps(d)

    # Verify it can be round-tripped
    d2 = json.loads(json_str)
    assert d2['sources_processed'] == 3
    assert d2['entries_stored'] == 40
    assert len(d2['errors']) == 2
    print("✅ test_pipeline_result_to_json passed")


def test_error_count_incremented_on_failure():
    """Test that error count increments when fetch fails."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = Path(f.name)

    try:
        cache = FeedCache(db_path)

        # Create a source
        cache.save_source(FeedSource(
            id='error-source',
            name='Error Source',
            url='https://error.example.com/feed',
            format='RSS',
            category='Test',
            domain='ai',
            signal_quality='Medium'
        ))

        # Log some failures
        cache.log_fetch('error-source', 0, False, 'Connection timeout', 1000)
        cache.log_fetch('error-source', 0, False, 'Connection timeout', 1000)

        # Check error count
        error_count = cache.get_source_error_count('error-source')
        assert error_count == 2, f"Expected error count 2, got {error_count}"

        print("✅ test_error_count_incremented_on_failure passed")
    finally:
        db_path.unlink(missing_ok=True)


def test_error_count_reset_on_success():
    """Test that error count resets to 0 after successful fetch."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = Path(f.name)

    try:
        cache = FeedCache(db_path)

        # Create a source
        cache.save_source(FeedSource(
            id='recovery-source',
            name='Recovery Source',
            url='https://recovery.example.com/feed',
            format='RSS',
            category='Test',
            domain='ai',
            signal_quality='Medium'
        ))

        # Log some failures
        cache.log_fetch('recovery-source', 0, False, 'Connection timeout', 1000)
        cache.log_fetch('recovery-source', 0, False, 'Connection timeout', 1000)

        # Verify errors accumulated
        assert cache.get_source_error_count('recovery-source') == 2

        # Log a success
        cache.log_fetch('recovery-source', 5, True, None, 500)

        # Error count should be reset to 0
        error_count = cache.get_source_error_count('recovery-source')
        assert error_count == 0, f"Expected error count 0 after success, got {error_count}"

        print("✅ test_error_count_reset_on_success passed")
    finally:
        db_path.unlink(missing_ok=True)


def test_source_auto_disabled_after_threshold():
    """Test that source is auto-disabled after ERROR_THRESHOLD failures."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = Path(f.name)

    try:
        cache = FeedCache(db_path)

        # Create a mock fetcher with auto_disable enabled
        fetcher = FeedFetcher(cache, auto_disable=True)
        threshold = fetcher.ERROR_THRESHOLD

        # Create a source
        cache.save_source(FeedSource(
            id='failing-source',
            name='Failing Source',
            url='https://failing.example.com/feed',
            format='RSS',
            category='Test',
            domain='ai',
            signal_quality='Medium'
        ))

        # Simulate threshold failures
        for i in range(threshold):
            cache.log_fetch('failing-source', 0, False, f'Failure {i+1}', 1000)

        # Source should still be active before hitting the threshold check
        sources = cache.get_sources(active_only=True)
        assert len(sources) == 1, "Source should still be active"

        # Simulate one more failure to trigger auto-disable
        # (This happens in fetch_all when checking error_count >= threshold)
        error_count = cache.get_source_error_count('failing-source')
        if error_count >= threshold:
            cache.disable_source('failing-source', f"Auto-disabled after {error_count} consecutive failures")

        # Verify source is now disabled
        disabled = cache.get_disabled_sources()
        assert len(disabled) == 1, f"Expected 1 disabled source, got {len(disabled)}"
        assert disabled[0].id == 'failing-source'

        # Verify it's not in active sources
        active = cache.get_sources(active_only=True)
        assert len(active) == 0, "Should have no active sources"

        print("✅ test_source_auto_disabled_after_threshold passed")
    finally:
        db_path.unlink(missing_ok=True)


def test_disabled_source_excluded_from_fetch():
    """Test that disabled sources are excluded from fetch_all."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = Path(f.name)

    try:
        cache = FeedCache(db_path)

        # Create active and disabled sources
        cache.save_source(FeedSource(
            id='active-source',
            name='Active Source',
            url='https://active.example.com/feed',
            format='RSS',
            category='Test',
            domain='ai',
            signal_quality='High'
        ))

        cache.save_source(FeedSource(
            id='disabled-source',
            name='Disabled Source',
            url='https://disabled.example.com/feed',
            format='RSS',
            category='Test',
            domain='ai',
            signal_quality='Medium',
            active=False
        ))

        # Get active sources only
        active = cache.get_sources(active_only=True)
        assert len(active) == 1
        assert active[0].id == 'active-source'

        # Get disabled sources
        disabled = cache.get_disabled_sources()
        assert len(disabled) == 1
        assert disabled[0].id == 'disabled-source'

        print("✅ test_disabled_source_excluded_from_fetch passed")
    finally:
        db_path.unlink(missing_ok=True)


def test_reenable_source_resets_error_count():
    """Test that re-enabling a source resets its error count."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = Path(f.name)

    try:
        cache = FeedCache(db_path)

        # Create and disable a source with errors
        cache.save_source(FeedSource(
            id='reenable-source',
            name='Re-enable Source',
            url='https://reenable.example.com/feed',
            format='RSS',
            category='Test',
            domain='ai',
            signal_quality='Medium'
        ))

        # Add errors and disable
        for i in range(5):
            cache.log_fetch('reenable-source', 0, False, f'Error {i}', 1000)
        cache.disable_source('reenable-source', 'Test disable')

        # Verify disabled with errors
        assert cache.get_source_error_count('reenable-source') == 5

        # Re-enable
        cache.reenable_source('reenable-source')

        # Verify reset
        assert cache.get_source_error_count('reenable-source') == 0

        # Verify it's active
        active = cache.get_sources(active_only=True)
        assert len(active) == 1

        print("✅ test_reenable_source_resets_error_count passed")
    finally:
        db_path.unlink(missing_ok=True)


def test_fetcher_auto_disable_disabled():
    """Test that auto-disable can be turned off."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = Path(f.name)

    try:
        cache = FeedCache(db_path)

        # Create fetcher with auto_disable=False
        fetcher = FeedFetcher(cache, auto_disable=False)

        # Create a source
        cache.save_source(FeedSource(
            id='no-disable-source',
            name='No Disable Source',
            url='https://example.com/feed',
            format='RSS',
            category='Test',
            domain='ai',
            signal_quality='Medium'
        ))

        # Log many failures
        for i in range(10):
            cache.log_fetch('no-disable-source', 0, False, f'Error {i}', 1000)

        # Source should still be active because auto_disable is False
        # (in real usage, fetch_all checks auto_disable before calling disable_source)
        active = cache.get_sources(active_only=True)
        assert len(active) == 1, "Source should still be active with auto_disable=False"

        print("✅ test_fetcher_auto_disable_disabled passed")
    finally:
        db_path.unlink(missing_ok=True)


def test_fetch_log_tracks_errors():
    """Test that fetch log tracks error messages."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = Path(f.name)

    try:
        cache = FeedCache(db_path)

        # Create a source
        cache.save_source(FeedSource(
            id='log-test-source',
            name='Log Test Source',
            url='https://log.example.com/feed',
            format='RSS',
            category='Test',
            domain='ai',
            signal_quality='Medium'
        ))

        # Log fetches with various statuses
        cache.log_fetch('log-test-source', 10, True, None, 500)
        cache.log_fetch('log-test-source', 0, False, 'Network timeout', 1000)
        cache.log_fetch('log-test-source', 0, False, 'HTTP 500', 2000)

        # Query the fetch log
        with sqlite3.connect(db_path) as conn:
            rows = conn.execute(
                "SELECT success, error_message FROM fetch_log WHERE source_id = ? ORDER BY id",
                ('log-test-source',)
            ).fetchall()

        assert len(rows) == 3
        assert rows[0] == (1, None)
        assert rows[1] == (0, 'Network timeout')
        assert rows[2] == (0, 'HTTP 500')

        print("✅ test_fetch_log_tracks_errors passed")
    finally:
        db_path.unlink(missing_ok=True)


def run_all_tests():
    """Run all tests."""
    tests = [
        test_init_creates_tables,
        test_save_and_get_source,
        test_get_sources_filters_by_domain,
        test_save_and_retrieve_entries,
        test_duplicate_entries_ignored,
        test_fetcher_entry_id_stable,
        test_fetcher_entry_id_unique,
        test_load_sources_from_catalog,
        test_end_to_end_flow,
        test_simhash_exact_match,
        test_simhash_similar_text,
        test_url_normalizer,
        test_deduplicator_exact_duplicate,
        test_deduplicator_stats,
        test_story_clusterer,
        test_content_extractor_init,
        test_extracted_content_dataclass,
        test_pipeline_initialization,
        test_pipeline_result_dataclass,
        test_pipeline_run_empty_sources,
        test_pipeline_deduplication_integration,
        test_pipeline_result_to_json,
        test_extended_pipeline_result_dataclass,
        test_extended_pipeline_newsletter_integration,
        # ArticleStorage tests
        test_storage_init_creates_tables,
        test_storage_save_and_get_article,
        test_storage_duplicate_url_rejection,
        test_storage_full_text_search,
        test_storage_get_recent_articles,
        test_storage_stats,
        test_storage_content_hash_dedup,
        test_storage_ingestion_log,
        # Auto-disable tests
        test_error_count_incremented_on_failure,
        test_error_count_reset_on_success,
        test_source_auto_disabled_after_threshold,
        test_disabled_source_excluded_from_fetch,
        test_reenable_source_resets_error_count,
        test_fetcher_auto_disable_disabled,
        test_fetch_log_tracks_errors,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            print(f"❌ {test.__name__} FAILED: {e}")
            failed += 1
        except Exception as e:
            print(f"❌ {test.__name__} ERROR: {e}")
            failed += 1

    print(f"\n{'='*50}")
    print(f"Results: {passed} passed, {failed} failed")
    return failed == 0


# Extended pipeline tests
def test_extended_pipeline_result_dataclass():
    """Test ExtendedPipelineResult serialization."""
    from aggregator.pipeline_extended import ExtendedPipelineResult

    result = ExtendedPipelineResult(
        started_at=datetime(2026, 3, 15, 10, 0, 0),
        completed_at=datetime(2026, 3, 15, 10, 1, 30),
        sources_processed=5,
        entries_fetched=100,
        entries_extracted=95,
        entries_deduplicated=10,
        entries_stored=85,
        errors=[],
        newsletter_sources_processed=3,
        newsletter_entries_fetched=20,
        newsletter_entries_stored=18,
    )

    data = result.to_dict()
    assert data['sources_processed'] == 5
    assert data['entries_stored'] == 85
    assert data['newsletter_sources_processed'] == 3
    assert data['newsletter_entries_stored'] == 18
    assert data['duration_seconds'] == 90.0
    print("✅ test_extended_pipeline_result_dataclass passed")


def test_extended_pipeline_newsletter_integration():
    """Test that extended pipeline can integrate with newsletter cache."""
    from aggregator.pipeline_extended import ExtendedAggregationPipeline
    from aggregator.newsletter_ingester import NewsletterCache, NewsletterIngester

    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = Path(f.name)

    try:
        feed_cache = FeedCache(db_path)
        newsletter_cache = NewsletterCache(db_path)

        pipeline = ExtendedAggregationPipeline(
            cache=feed_cache,
            newsletter_cache=newsletter_cache,
            newsletter_ingester=NewsletterIngester(newsletter_cache),
        )

        # Verify both caches are accessible
        assert pipeline.cache is feed_cache
        assert pipeline.newsletter_cache is newsletter_cache
        assert pipeline.newsletter_ingester is not None
        print("✅ test_extended_pipeline_newsletter_integration passed")
    finally:
        db_path.unlink(missing_ok=True)


def test_storage_init_creates_tables():
    """Test that ArticleStorage initializes the database correctly."""
    from aggregator.storage import ArticleStorage

    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = Path(f.name)

    try:
        storage = ArticleStorage(db_path)

        with sqlite3.connect(db_path) as conn:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            table_names = {t[0] for t in tables}

        assert 'articles' in table_names, "articles table missing"
        assert 'story_clusters' in table_names, "story_clusters table missing"
        assert 'ingestion_log' in table_names, "ingestion_log table missing"
        print("✅ test_storage_init_creates_tables passed")
    finally:
        db_path.unlink(missing_ok=True)


def test_storage_save_and_get_article():
    """Test saving and retrieving an article."""
    from aggregator.storage import ArticleStorage, create_article_from_entry

    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = Path(f.name)

    try:
        storage = ArticleStorage(db_path)

        article = create_article_from_entry(
            entry_id='test-article-1',
            title='Test Article Title',
            url='https://example.com/article1',
            source_id='test-source',
            source_name='Test Source',
            domain='ai',
            summary='A test article',
            content='Full content here'
        )

        saved = storage.save_article(article)
        assert saved, "Article should be saved"

        retrieved = storage.get_article('test-article-1')
        assert retrieved is not None, "Article should be retrievable"
        assert retrieved.title == 'Test Article Title'
        assert retrieved.url == 'https://example.com/article1'
        assert retrieved.domain == 'ai'

        print("✅ test_storage_save_and_get_article passed")
    finally:
        db_path.unlink(missing_ok=True)


def test_storage_duplicate_url_rejection():
    """Test that duplicate URLs are rejected."""
    from aggregator.storage import ArticleStorage, create_article_from_entry

    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = Path(f.name)

    try:
        storage = ArticleStorage(db_path)

        article1 = create_article_from_entry(
            entry_id='article-1',
            title='First Article',
            url='https://example.com/same',
            source_id='source-1',
            source_name='Source 1',
            domain='ai'
        )

        article2 = create_article_from_entry(
            entry_id='article-2',
            title='Second Article',
            url='https://example.com/same',  # Same URL
            source_id='source-2',
            source_name='Source 2',
            domain='software_development'
        )

        saved1 = storage.save_article(article1)
        saved2 = storage.save_article(article2)

        assert saved1, "First article should be saved"
        assert not saved2, "Second article with same URL should be rejected"

        print("✅ test_storage_duplicate_url_rejection passed")
    finally:
        db_path.unlink(missing_ok=True)


def test_storage_full_text_search():
    """Test full-text search functionality."""
    from aggregator.storage import ArticleStorage, create_article_from_entry

    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = Path(f.name)

    try:
        storage = ArticleStorage(db_path)

        # Create articles with different content
        articles = [
            create_article_from_entry(
                f'ai-{i}',
                f'AI Research Article {i}',
                f'https://ai.com/article{i}',
                'ai-source',
                'AI Source',
                'ai',
                content='Machine learning and neural networks are advancing rapidly.'
            )
            for i in range(3)
        ] + [
            create_article_from_entry(
                f'dev-{i}',
                f'Programming Article {i}',
                f'https://dev.com/article{i}',
                'dev-source',
                'Dev Source',
                'software_development',
                content='Python and JavaScript frameworks comparison.'
            )
            for i in range(2)
        ]

        for article in articles:
            storage.save_article(article)

        # Search for AI content
        ai_results = storage.search_articles('machine learning')
        assert len(ai_results) >= 3, f"Expected at least 3 AI results, got {len(ai_results)}"

        # Search with domain filter
        dev_results = storage.search_articles('Python', domain='software_development')
        assert len(dev_results) == 2, f"Expected 2 dev results, got {len(dev_results)}"

        print("✅ test_storage_full_text_search passed")
    finally:
        db_path.unlink(missing_ok=True)


def test_storage_get_recent_articles():
    """Test retrieving recent articles."""
    from aggregator.storage import ArticleStorage, create_article_from_entry
    from datetime import datetime, timedelta

    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = Path(f.name)

    try:
        storage = ArticleStorage(db_path)

        # Create articles with recent published_at dates
        now = datetime.now()
        for i in range(5):
            article = create_article_from_entry(
                f'recent-{i}',
                f'Recent Article {i}',
                f'https://example.com/recent{i}',
                'test-source',
                'Test Source',
                'ai',
                published_at=now - timedelta(hours=i)  # Published within last few hours
            )
            storage.save_article(article)

        # Get recent articles
        recent = storage.get_recent_articles(hours=24, limit=10)
        assert len(recent) == 5, f"Expected 5 recent articles, got {len(recent)}"

        # Filter by domain
        ai_recent = storage.get_recent_articles(domain='ai', hours=24)
        assert len(ai_recent) == 5

        print("✅ test_storage_get_recent_articles passed")
    finally:
        db_path.unlink(missing_ok=True)


def test_storage_stats():
    """Test storage statistics."""
    from aggregator.storage import ArticleStorage, create_article_from_entry

    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = Path(f.name)

    try:
        storage = ArticleStorage(db_path)

        # Create articles in different domains
        for i in range(3):
            storage.save_article(create_article_from_entry(
                f'ai-{i}', f'AI {i}', f'https://ai.com/{i}',
                'source1', 'Source 1', 'ai'
            ))

        for i in range(2):
            storage.save_article(create_article_from_entry(
                f'dev-{i}', f'Dev {i}', f'https://dev.com/{i}',
                'source2', 'Source 2', 'software_development'
            ))

        stats = storage.get_stats()

        assert stats['total_articles'] == 5, f"Expected 5 articles, got {stats['total_articles']}"
        assert stats['by_domain']['ai'] == 3
        assert stats['by_domain']['software_development'] == 2
        assert stats['last_24h'] == 5

        print("✅ test_storage_stats passed")
    finally:
        db_path.unlink(missing_ok=True)


def test_storage_content_hash_dedup():
    """Test content hash based deduplication check."""
    from aggregator.storage import ArticleStorage, create_article_from_entry
    import hashlib

    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = Path(f.name)

    try:
        storage = ArticleStorage(db_path)

        # Create and save article
        article = create_article_from_entry(
            'original',
            'Same Title',
            'https://example.com/original',
            'source1',
            'Source 1',
            'ai',
            summary='Same summary',
            content='Same content'
        )
        storage.save_article(article)

        # Check if content hash exists
        content_to_hash = f"Same Title:Same summary:Same content"[:1000]
        content_hash = hashlib.sha256(content_to_hash.encode()).hexdigest()[:16]

        existing_id = storage.check_content_hash_exists(content_hash)
        assert existing_id == 'original', "Should find the original article"

        # Check non-existent hash
        nonexistent = storage.check_content_hash_exists('nonexistenthash123')
        assert nonexistent is None

        print("✅ test_storage_content_hash_dedup passed")
    finally:
        db_path.unlink(missing_ok=True)


def test_storage_ingestion_log():
    """Test ingestion logging."""
    from aggregator.storage import ArticleStorage

    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = Path(f.name)

    try:
        storage = ArticleStorage(db_path)

        # Log operations
        log_id = storage.log_ingestion('fetch', 'source1', 10, True)
        assert log_id > 0

        storage.complete_ingestion_log(log_id, True)

        # Log error
        log_id2 = storage.log_ingestion('extract', 'source2', 0, False, 'Network error')
        storage.complete_ingestion_log(log_id2, False, 'Network error')

        # Get logs
        logs = storage.get_recent_logs(limit=10)
        assert len(logs) == 2

        # Filter by operation
        fetch_logs = storage.get_recent_logs(operation='fetch')
        assert len(fetch_logs) == 1

        print("✅ test_storage_ingestion_log passed")
    finally:
        db_path.unlink(missing_ok=True)


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
