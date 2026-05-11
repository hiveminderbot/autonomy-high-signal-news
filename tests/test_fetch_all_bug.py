"""Test that fetch_all preserves fetched entries (regression guard)."""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure scripts/ is discoverable
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts" / "aggregator"))

from feed_fetcher import FeedFetcher, FeedSource, FeedEntry, FeedCache


def test_fetch_all_preserves_entries():
    """fetch_all must return the actual entries, not empty lists."""
    # Create a real cache in a temp location
    db_path = Path("/tmp/test_fetch_all.db")
    if db_path.exists():
        db_path.unlink()
    cache = FeedCache(db_path=db_path)

    fetcher = FeedFetcher(cache=cache, min_fetch_interval_seconds=0)

    # Create a mock source
    source = FeedSource(
        id="test_source",
        name="Test Source",
        url="https://example.com/feed",
        format="RSS",
        category="test",
        domain="ai",
        signal_quality="high",
        active=True,
        fetch_interval_minutes=1,
        min_fetch_interval=0,
    )

    # Mock the cache to return our test source
    mock_cache = MagicMock()
    mock_cache.get_sources.return_value = [source]
    mock_cache.should_fetch.return_value = True
    fetcher.cache = mock_cache

    # Create a fake entry
    fake_entry = FeedEntry(
        id="entry1",
        title="Test Entry",
        url="https://example.com/1",
        source_id="test_source",
        published_at=None,
        summary="Summary",
        author=None,
        content=None,
        fetched_at=__import__('datetime').datetime.now(),
    )

    # Mock fetch_source to return the fake entry
    with patch.object(fetcher, 'fetch_source', return_value=[fake_entry]):
        results = fetcher.fetch_all()

    # The bug: results[source.id] should be [fake_entry], not []
    assert results["test_source"] == [fake_entry], \
        f"Expected [fake_entry], got {results['test_source']}"
