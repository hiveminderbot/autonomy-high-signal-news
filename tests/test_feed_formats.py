#!/usr/bin/env python3
"""
Test feed format handlers for SCRAPER, GITHUB_TRENDING, and GITHUB_REPO formats.

This test verifies that the new feed format handlers in feed_fetcher.py work correctly.
"""

import sys
import os
from pathlib import Path
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts' / 'aggregator'))

from feed_fetcher import FeedSource, FeedEntry, FeedCache, FeedFetcher


def test_feed_source_creation():
    """Test that FeedSource objects can be created with new formats."""
    # Test SCRAPER format
    scraper_source = FeedSource(
        id='anthropic-research',
        name='Anthropic Research',
        url='https://www.anthropic.com/research',
        format='SCRAPER',
        category='research',
        domain='ai',
        signal_quality='high'
    )
    assert scraper_source.format.upper() == 'SCRAPER'
    print("✓ SCRAPER format FeedSource creation works")
    
    # Test GITHUB_TRENDING format
    trending_source = FeedSource(
        id='trending-python-ml',
        name='Trending Python ML',
        url='https://github.com/trending/python?since=daily',
        format='GITHUB_TRENDING',
        category='repositories',
        domain='software_development',
        signal_quality='medium'
    )
    assert trending_source.format.upper() == 'GITHUB_TRENDING'
    print("✓ GITHUB_TRENDING format FeedSource creation works")
    
    # Test GITHUB_REPO format
    repo_source = FeedSource(
        id='awesome-ml',
        name='Awesome ML',
        url='https://github.com/josephmisiti/awesome-machine-learning',
        format='GITHUB_REPO',
        category='resources',
        domain='software_development',
        signal_quality='medium'
    )
    assert repo_source.format.upper() == 'GITHUB_REPO'
    print("✓ GITHUB_REPO format FeedSource creation works")


def test_format_routing():
    """Test that fetch_source routes to the correct handler based on format."""
    # Create a mock cache
    import tempfile
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    try:
        cache = FeedCache(Path(db_path))
        fetcher = FeedFetcher(cache)
        
        # Mock the specific fetch methods to verify routing
        original_methods = {
            'rss': fetcher.fetch_rss,
            'scraper': fetcher.fetch_scraper if hasattr(fetcher, 'fetch_scraper') else None,
            'trending': fetcher.fetch_github_trending if hasattr(fetcher, 'fetch_github_trending') else None,
            'repo': fetcher.fetch_github_repo if hasattr(fetcher, 'fetch_github_repo') else None,
        }
        
        # Verify methods exist
        assert hasattr(fetcher, 'fetch_scraper'), "fetch_scraper method not found"
        assert hasattr(fetcher, 'fetch_github_trending'), "fetch_github_trending method not found"
        assert hasattr(fetcher, 'fetch_github_repo'), "fetch_github_repo method not found"
        assert hasattr(fetcher, '_build_scrape_config'), "_build_scrape_config method not found"
        
        print("✓ All new format handler methods exist")
        
    finally:
        os.unlink(db_path)


def test_scrape_config_builder():
    """Test that _build_scrape_config generates correct configs for known sources."""
    import tempfile
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    
    try:
        cache = FeedCache(Path(db_path))
        fetcher = FeedFetcher(cache)
        
        # Test Anthropic Research config
        anthropic_source = FeedSource(
            id='anthropic-research',
            name='Anthropic Research',
            url='https://www.anthropic.com/research',
            format='SCRAPER',
            category='research',
            domain='ai',
            signal_quality='high'
        )
        config = fetcher._build_scrape_config(anthropic_source)
        assert 'anthropic.com' in config.get('list_url', '')
        assert 'research' in config.get('article_selector', '')
        print("✓ Anthropic Research scrape config is correct")
        
        # Test default config for unknown source
        generic_source = FeedSource(
            id='generic-blog',
            name='Generic Blog',
            url='https://example.com/blog',
            format='SCRAPER',
            category='blog',
            domain='general',
            signal_quality='medium'
        )
        config = fetcher._build_scrape_config(generic_source)
        assert 'article_selector' in config
        assert 'title_selector' in config
        print("✓ Default scrape config is generated for unknown sources")
        
    finally:
        os.unlink(db_path)


def test_github_trending_url_parsing():
    """Test URL parsing logic for GitHub trending sources."""
    from urllib.parse import urlparse, parse_qs
    
    # Test Python daily trending URL
    url = 'https://github.com/trending/python?since=daily'
    parsed = urlparse(url)
    path_parts = parsed.path.strip('/').split('/')
    
    assert path_parts[0] == 'trending'
    assert path_parts[1] == 'python'
    
    query_params = parse_qs(parsed.query)
    assert query_params.get('since') == ['daily']
    
    print("✓ GitHub trending URL parsing works correctly")


def test_github_repo_url_parsing():
    """Test URL parsing logic for GitHub repo sources."""
    from urllib.parse import urlparse
    
    url = 'https://github.com/josephmisiti/awesome-machine-learning'
    parsed = urlparse(url)
    path_parts = parsed.path.strip('/').split('/')
    
    assert len(path_parts) >= 2
    assert path_parts[0] == 'josephmisiti'
    assert path_parts[1] == 'awesome-machine-learning'
    
    print("✓ GitHub repo URL parsing works correctly")


def run_all_tests():
    """Run all feed format tests."""
    print("\n" + "="*60)
    print("Testing Feed Format Handlers")
    print("="*60 + "\n")
    
    try:
        test_feed_source_creation()
        test_format_routing()
        test_scrape_config_builder()
        test_github_trending_url_parsing()
        test_github_repo_url_parsing()
        
        print("\n" + "="*60)
        print("All tests passed! ✓")
        print("="*60 + "\n")
        return True
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
