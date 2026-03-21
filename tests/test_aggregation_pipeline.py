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
        
        assert len(sources) == 2, f"Expected 2 sources, got {len(sources)}"
        ids = {s.id for s in sources}
        assert 'test-newsletter' in ids, "test-newsletter not found"
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


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
