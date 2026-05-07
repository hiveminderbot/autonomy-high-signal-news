"""Test that exposes the > vs >= cutoff bug in rss_fetcher.fetch_all_feeds."""
import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from scripts.aggregator.rss_fetcher import RSSFetcher


def test_article_exactly_hours_old_is_included():
    """Articles published exactly 'hours' ago should still be included."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        fetcher = RSSFetcher(db_path=str(db_path))

        # Bootstrap schema if needed
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sources (
                id INTEGER PRIMARY KEY,
                name TEXT,
                rss_url TEXT,
                domain TEXT,
                status TEXT,
                last_fetch TEXT
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY,
                title TEXT,
                url TEXT UNIQUE,
                source_id INTEGER,
                content TEXT,
                published_at TEXT,
                fetched_at TEXT
            )
        ''')
        cursor.execute('''
            INSERT INTO sources (id, name, rss_url, domain, status)
            VALUES (1, 'Test', 'http://example.com/feed', 'example.com', 'active')
        ''')
        conn.commit()
        conn.close()

        # Use a fixed reference time so cutoff and article published time align
        fixed_now = datetime(2026, 5, 7, 12, 0, 0)
        exactly_24h_ago = (fixed_now - timedelta(hours=24)).isoformat()

        fetcher.fetch_feed = lambda url: [
            {
                'title': 'Exactly 24h old',
                'url': 'http://example.com/exactly-24h',
                'published': exactly_24h_ago,
                'content': 'content',
            }
        ]

        # Patch datetime.now in rss_fetcher to return fixed_now
        with patch('scripts.aggregator.rss_fetcher.datetime') as mock_datetime:
            mock_datetime.now.return_value = fixed_now
            mock_datetime.fromisoformat = datetime.fromisoformat
            total = fetcher.fetch_all_feeds(hours=24)

        # With the bug (>), this article is excluded → total == 0
        # After fix (>=), it is included → total == 1
        assert total == 1, f"Expected 1 article (exactly 24h old should be included), got {total}"
