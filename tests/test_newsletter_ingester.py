#!/usr/bin/env python3
"""
Tests for the newsletter ingestion system.

Run with: python tests/test_newsletter_ingester.py
"""

import json
import sqlite3
import sys
import tempfile
from datetime import datetime
from pathlib import Path

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from aggregator.newsletter_ingester import (
    NewsletterSource, NewsletterEntry, NewsletterCache, 
    NewsletterParser, NewsletterIngester,
    load_newsletter_sources_from_catalog
)


def test_newsletter_cache_init():
    """Test that NewsletterCache initializes database correctly."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = Path(f.name)
    
    try:
        cache = NewsletterCache(db_path)
        
        with sqlite3.connect(db_path) as conn:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            table_names = {t[0] for t in tables}
        
        assert 'newsletter_sources' in table_names, "newsletter_sources table missing"
        assert 'newsletter_entries' in table_names, "newsletter_entries table missing"
        assert 'newsletter_ingestion_log' in table_names, "newsletter_ingestion_log table missing"
        print("✅ test_newsletter_cache_init passed")
    finally:
        db_path.unlink(missing_ok=True)


def test_newsletter_source_save_and_get():
    """Test saving and retrieving newsletter sources."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = Path(f.name)
    
    try:
        cache = NewsletterCache(db_path)
        
        source = NewsletterSource(
            id='test-newsletter',
            name='Test Newsletter',
            provider='substack_rss',
            source_url='https://test.substack.com/feed',
            category='Technology',
            domain='ai',
            signal_quality='High',
            active=True,
            config='{"author": "Test Author"}'
        )
        
        cache.save_source(source)
        sources = cache.get_sources()
        
        assert len(sources) == 1, f"Expected 1 source, got {len(sources)}"
        assert sources[0].id == 'test-newsletter'
        assert sources[0].provider == 'substack_rss'
        assert sources[0].config == '{"author": "Test Author"}'
        print("✅ test_newsletter_source_save_and_get passed")
    finally:
        db_path.unlink(missing_ok=True)


def test_newsletter_source_filter_by_domain():
    """Test filtering newsletter sources by domain."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = Path(f.name)
    
    try:
        cache = NewsletterCache(db_path)
        
        cache.save_source(NewsletterSource(
            id='ai-newsletter', name='AI Newsletter', 
            provider='substack_rss', source_url='https://ai.substack.com/feed',
            category='AI', domain='ai', signal_quality='High'
        ))
        cache.save_source(NewsletterSource(
            id='dev-newsletter', name='Dev Newsletter',
            provider='buttondown_rss', source_url='https://dev.buttondown.com/feed',
            category='Development', domain='software_development', signal_quality='High'
        ))
        
        ai_sources = cache.get_sources(domain='ai')
        assert len(ai_sources) == 1
        assert ai_sources[0].id == 'ai-newsletter'
        print("✅ test_newsletter_source_filter_by_domain passed")
    finally:
        db_path.unlink(missing_ok=True)


def test_newsletter_entry_save_and_retrieve():
    """Test saving and retrieving newsletter entries."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = Path(f.name)
    
    try:
        cache = NewsletterCache(db_path)
        
        entry = NewsletterEntry(
            id='entry-1',
            title='Test Newsletter Issue',
            url='https://test.substack.com/p/issue-1',
            newsletter_id='test-newsletter',
            published_at=datetime(2026, 3, 15, 10, 0, 0),
            author='Test Author',
            content_html='<p>Test content</p>',
            content_text='Test content',
            links=[{'url': 'https://example.com', 'title': 'Example Link'}],
            fetched_at=datetime.now()
        )
        
        cache.save_entries([entry])
        
        with sqlite3.connect(cache.db_path) as conn:
            row = conn.execute(
                "SELECT title, url, author FROM newsletter_entries WHERE id = ?",
                ('entry-1',)
            ).fetchone()
        
        assert row is not None, "Entry not found"
        assert row[0] == 'Test Newsletter Issue'
        assert row[2] == 'Test Author'
        print("✅ test_newsletter_entry_save_and_retrieve passed")
    finally:
        db_path.unlink(missing_ok=True)


def test_parser_html_to_text():
    """Test HTML to text conversion."""
    parser = NewsletterParser()
    
    html = "<p>This is a <strong>test</strong> paragraph.</p><p>Second paragraph.</p>"
    text = parser.html_to_text(html)
    
    assert 'test' in text
    assert '<p>' not in text
    assert '<strong>' not in text
    print("✅ test_parser_html_to_text passed")


def test_parser_extract_links():
    """Test link extraction from HTML."""
    parser = NewsletterParser()
    
    html = '''
    <p>Here are some links:
    <a href="https://example.com/article">Example Article</a>
    <a href="https://test.org/resource">Test Resource</a>
    </p>
    '''
    links = parser.extract_links_from_html(html)
    
    assert len(links) == 2
    assert links[0]['url'] == 'https://example.com/article'
    assert links[0]['title'] == 'Example Article'
    print("✅ test_parser_extract_links passed")


def test_parser_extract_links_skips_non_http():
    """Test that non-HTTP links are skipped."""
    parser = NewsletterParser()
    
    html = '''
    <a href="https://example.com/valid">Valid</a>
    <a href="mailto:test@example.com">Email</a>
    <a href="javascript:void(0)">JS</a>
    <a href="/relative/path">Relative</a>
    '''
    links = parser.extract_links_from_html(html)
    
    assert len(links) == 1
    assert links[0]['url'] == 'https://example.com/valid'
    print("✅ test_parser_extract_links_skips_non_http passed")


def test_load_newsletter_sources_from_catalog():
    """Test loading newsletter sources from JSON catalog."""
    with tempfile.TemporaryDirectory() as tmpdir:
        catalog_path = Path(tmpdir) / 'newsletter_catalog.json'
        
        catalog_data = {
            "version": "1.0",
            "newsletters": [
                {
                    "id": "test-newsletter-1",
                    "name": "Test Newsletter One",
                    "provider": "substack_rss",
                    "source_url": "https://test1.substack.com/feed",
                    "category": "Technology",
                    "domain": "ai",
                    "signal_quality": "High",
                    "active": True,
                    "config": {"author": "Test Author"}
                },
                {
                    "id": "test-newsletter-2",
                    "name": "Test Newsletter Two",
                    "provider": "buttondown_rss",
                    "source_url": "https://test2.buttondown.com/feed",
                    "category": "Development",
                    "domain": "software_development",
                    "signal_quality": "Medium"
                }
            ]
        }
        
        catalog_path.write_text(json.dumps(catalog_data))
        sources = load_newsletter_sources_from_catalog(catalog_path)
        
        assert len(sources) == 2
        assert sources[0].id == 'test-newsletter-1'
        assert sources[0].provider == 'substack_rss'
        assert sources[1].provider == 'buttondown_rss'
        print("✅ test_load_newsletter_sources_from_catalog passed")


def test_ingester_file_source():
    """Test ingesting from a file-based source."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / 'test.db'
        cache = NewsletterCache(db_path)
        ingester = NewsletterIngester(cache)
        
        # Create a sample JSON file
        data_file = Path(tmpdir) / 'sample.json'
        data = [
            {
                "title": "Issue One",
                "url": "https://example.com/issue-1",
                "published_at": "2026-03-15T10:00:00",
                "author": "Author One",
                "content_html": "<p>Content for issue one</p>",
                "links": [{"url": "https://link1.com", "title": "Link 1"}]
            },
            {
                "title": "Issue Two",
                "url": "https://example.com/issue-2",
                "author": "Author Two",
                "content_text": "Plain text content"
            }
        ]
        data_file.write_text(json.dumps(data))
        
        source = NewsletterSource(
            id='file-newsletter',
            name='File Newsletter',
            provider='file',
            source_url=f'file://{data_file}',
            category='Test',
            domain='test',
            signal_quality='High'
        )
        
        entries = ingester.ingest_source(source)
        
        assert len(entries) == 2
        assert entries[0].title == 'Issue One'
        assert entries[1].title == 'Issue Two'
        print("✅ test_ingester_file_source passed")


def test_ingestion_logging():
    """Test that ingestion attempts are logged."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / 'test.db'
        cache = NewsletterCache(db_path)
        ingester = NewsletterIngester(cache)
        
        # Empty file source (no entries)
        data_file = Path(tmpdir) / 'empty.json'
        data_file.write_text('[]')
        
        source = NewsletterSource(
            id='empty-newsletter',
            name='Empty Newsletter',
            provider='file',
            source_url=f'file://{data_file}',
            category='Test',
            domain='test',
            signal_quality='High'
        )
        
        entries = ingester.ingest_source(source)
        
        # Check log
        with sqlite3.connect(db_path) as conn:
            logs = conn.execute(
                "SELECT * FROM newsletter_ingestion_log WHERE newsletter_id = ?",
                ('empty-newsletter',)
            ).fetchall()
        
        assert len(logs) == 1
        assert logs[0][3] == 0  # entries_count
        assert logs[0][4] == 1  # success (True stored as 1)
        print("✅ test_ingestion_logging passed")


def test_convert_to_feed_entries():
    """Test converting NewsletterEntry to FeedEntry-compatible format."""
    entries = [
        NewsletterEntry(
            id='nl-1',
            title='Newsletter Issue 1',
            url='https://newsletter.com/issue-1',
            newsletter_id='test-newsletter',
            published_at=datetime(2026, 3, 15, 10, 0, 0),
            author='Author',
            content_html='<p>Content</p>',
            content_text='Content text',
            links=[{'url': 'https://primary-link.com', 'title': 'Primary Link'}],
            fetched_at=datetime.now()
        )
    ]
    
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / 'test.db'
        cache = NewsletterCache(db_path)
        ingester = NewsletterIngester(cache)
        
        feed_entries = ingester.convert_to_feed_entries(entries)
        
        assert len(feed_entries) == 1
        assert feed_entries[0]['title'] == 'Newsletter Issue 1'
        # Should use primary link URL
        assert feed_entries[0]['url'] == 'https://primary-link.com'
        assert feed_entries[0]['source_id'] == 'test-newsletter'
        print("✅ test_convert_to_feed_entries passed")


def test_convert_uses_newsletter_url_when_no_links():
    """Test that newsletter URL is used when no links in content."""
    entries = [
        NewsletterEntry(
            id='nl-1',
            title='Issue',
            url='https://newsletter.com/issue-1',
            newsletter_id='test-newsletter',
            published_at=datetime.now(),
            author=None,
            content_html=None,
            content_text=None,
            links=[],  # No links
            fetched_at=datetime.now()
        )
    ]
    
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / 'test.db'
        cache = NewsletterCache(db_path)
        ingester = NewsletterIngester(cache)
        
        feed_entries = ingester.convert_to_feed_entries(entries)
        
        assert feed_entries[0]['url'] == 'https://newsletter.com/issue-1'
        print("✅ test_convert_uses_newsletter_url_when_no_links passed")


def test_get_author_from_config():
    """Test extracting author from source config."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / 'test.db'
        cache = NewsletterCache(db_path)
        ingester = NewsletterIngester(cache)
        
        # Source with author in config
        source_with_author = NewsletterSource(
            id='test-newsletter',
            name='Test Newsletter',
            provider='substack_rss',
            source_url='https://test.substack.com/feed',
            category='Technology',
            domain='ai',
            signal_quality='High',
            config='{"author": "Test Author", "notes": "Test notes"}'
        )
        
        author = ingester._get_author_from_config(source_with_author)
        assert author == 'Test Author'
        
        # Source without author in config
        source_no_author = NewsletterSource(
            id='test-newsletter-2',
            name='Test Newsletter 2',
            provider='substack_rss',
            source_url='https://test2.substack.com/feed',
            category='Technology',
            domain='ai',
            signal_quality='High',
            config='{"notes": "Test notes"}'
        )
        
        author = ingester._get_author_from_config(source_no_author)
        assert author is None
        
        # Source with no config
        source_no_config = NewsletterSource(
            id='test-newsletter-3',
            name='Test Newsletter 3',
            provider='substack_rss',
            source_url='https://test3.substack.com/feed',
            category='Technology',
            domain='ai',
            signal_quality='High'
        )
        
        author = ingester._get_author_from_config(source_no_config)
        assert author is None
        
        print("✅ test_get_author_from_config passed")


def run_all_tests():
    """Run all newsletter ingester tests."""
    tests = [
        test_newsletter_cache_init,
        test_newsletter_source_save_and_get,
        test_newsletter_source_filter_by_domain,
        test_newsletter_entry_save_and_retrieve,
        test_parser_html_to_text,
        test_parser_extract_links,
        test_parser_extract_links_skips_non_http,
        test_load_newsletter_sources_from_catalog,
        test_ingester_file_source,
        test_ingestion_logging,
        test_convert_to_feed_entries,
        test_convert_uses_newsletter_url_when_no_links,
        test_get_author_from_config,
    ]
    
    passed = 0
    failed = 0
    
    print("="*50)
    print("Running Newsletter Ingester Tests")
    print("="*50)
    
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"❌ {test.__name__} FAILED: {e}")
            failed += 1
    
    print("="*50)
    print(f"Results: {passed} passed, {failed} failed")
    print("="*50)
    
    return failed == 0


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
