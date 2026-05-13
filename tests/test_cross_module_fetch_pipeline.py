"""Test cross-module fetch-to-pipeline integration (regression guard).

This test verifies that entries fetched by FeedFetcher.fetch_source()
actually flow through AggregationPipeline.run() and are counted in
entries_fetched and entries_stored.
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from aggregator.feed_fetcher import FeedFetcher, FeedSource, FeedEntry, FeedCache
from aggregator.pipeline import AggregationPipeline


def test_pipeline_processes_fetched_entries():
    """Pipeline must count and store entries returned by fetch_source."""
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    try:
        cache = FeedCache(db_path)

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
        cache.save_source(source)

        # Create fake entries that fetch_source will return
        fake_entries = [
            FeedEntry(
                id="entry1",
                title="Test Entry 1",
                url="https://example.com/1",
                source_id="test_source",
                published_at=datetime.now(),
                summary="Summary 1",
                author=None,
                content=None,
                fetched_at=datetime.now(),
            ),
            FeedEntry(
                id="entry2",
                title="Test Entry 2",
                url="https://example.com/2",
                source_id="test_source",
                published_at=datetime.now(),
                summary="Summary 2",
                author=None,
                content=None,
                fetched_at=datetime.now(),
            ),
        ]

        # Build pipeline with a mocked fetcher
        fetcher = FeedFetcher(cache, min_fetch_interval_seconds=0)
        pipeline = AggregationPipeline(cache=cache, fetcher=fetcher, extract_content=False)

        # Mock fetch_source to return our fake entries
        with patch.object(fetcher, "fetch_source", return_value=fake_entries):
            result = pipeline.run(sources=[source], verbose=False)

        # The bug in pipeline.py sets entries = [] after fetch_source,
        # so entries_fetched will be 0 instead of 2.
        assert result.entries_fetched == 2, (
            f"Expected 2 entries fetched, got {result.entries_fetched}"
        )
        assert result.entries_stored == 2, (
            f"Expected 2 entries stored, got {result.entries_stored}"
        )
    finally:
        db_path.unlink(missing_ok=True)
