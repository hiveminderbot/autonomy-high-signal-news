"""Regression tests for high-signal briefing recency selection."""
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from scripts import generate_high_signal_briefing as briefing


def _insert_article(conn, *, title: str, published_at: str, fetched_at: str, source: str = "Tier One"):
    conn.execute(
        """
        INSERT INTO articles (
            title, url, source, domain, content, published_at, fetched_at,
            full_content, extraction_status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'extracted')
        """,
        (
            title,
            f"https://example.test/{title.lower().replace(' ', '-')}",
            source,
            "ai",
            "summary " * 100,
            published_at,
            fetched_at,
            "full content " * 100,
        ),
    )


def test_get_recent_articles_does_not_duplicate_articles_when_source_names_repeat(monkeypatch, tmp_path: Path):
    db_path = tmp_path / "news.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE sources (
            name TEXT,
            tier INTEGER,
            quality_score INTEGER
        );
        CREATE TABLE articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            url TEXT,
            source TEXT,
            domain TEXT,
            content TEXT,
            published_at TEXT,
            fetched_at TEXT,
            full_content TEXT,
            extraction_status TEXT,
            llm_insight TEXT
        );
        INSERT INTO sources (name, tier, quality_score) VALUES ('Repeated', 1, 95);
        INSERT INTO sources (name, tier, quality_score) VALUES ('Repeated', 1, 90);
        """
    )
    _insert_article(
        conn,
        title="Single article",
        published_at="2026-05-14T00:00:00",
        fetched_at=datetime.now().isoformat(),
        source="Repeated",
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(briefing, "DB_PATH", db_path)

    articles = briefing.get_recent_articles(days=3)

    assert [article["title"] for article in articles] == ["Single article"]


def test_get_recent_articles_uses_iso_fetched_at_not_rfc_published_string_order(monkeypatch, tmp_path: Path):
    """Old RFC-2822 published_at rows must not pass a 3-day ISO cutoff lexicographically."""
    db_path = tmp_path / "news.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """
        CREATE TABLE sources (
            name TEXT PRIMARY KEY,
            tier INTEGER,
            quality_score INTEGER
        );
        CREATE TABLE articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            url TEXT,
            source TEXT,
            domain TEXT,
            content TEXT,
            published_at TEXT,
            fetched_at TEXT,
            full_content TEXT,
            extraction_status TEXT,
            llm_insight TEXT
        );
        INSERT INTO sources (name, tier, quality_score) VALUES ('Tier One', 1, 95);
        """
    )

    now = datetime.now()
    _insert_article(
        conn,
        title="Recent fetched article",
        published_at="Tue, 12 May 2026 12:00:00 +0000",
        fetched_at=(now - timedelta(hours=2)).isoformat(),
    )
    _insert_article(
        conn,
        title="Old RFC article that used to leak in",
        published_at="Sat, 21 Mar 2026 20:32:20 +0000",
        fetched_at=(now - timedelta(days=30)).isoformat(),
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(briefing, "DB_PATH", db_path)

    articles = briefing.get_recent_articles(days=3)
    titles = {article["title"] for article in articles}

    assert "Recent fetched article" in titles
    assert "Old RFC article that used to leak in" not in titles


def test_get_recent_articles_falls_back_to_live_state_databases(monkeypatch, tmp_path: Path):
    legacy_db = tmp_path / "legacy_news.db"
    feed_db = tmp_path / "state_aggregation.db"
    newsletter_db = tmp_path / "state_newsletters.db"

    conn = sqlite3.connect(legacy_db)
    conn.executescript(
        """
        CREATE TABLE sources (name TEXT PRIMARY KEY, tier INTEGER, quality_score INTEGER);
        CREATE TABLE articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            url TEXT,
            source TEXT,
            domain TEXT,
            content TEXT,
            published_at TEXT,
            fetched_at TEXT,
            full_content TEXT,
            extraction_status TEXT,
            llm_insight TEXT
        );
        INSERT INTO sources (name, tier, quality_score) VALUES ('Tier One', 1, 95);
        """
    )
    _insert_article(
        conn,
        title="Stale legacy article",
        published_at="2026-05-01T00:00:00",
        fetched_at=(datetime.now() - timedelta(days=30)).isoformat(),
    )
    conn.commit()
    conn.close()

    conn = sqlite3.connect(feed_db)
    conn.executescript(
        """
        CREATE TABLE feed_entries (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            url TEXT NOT NULL,
            source_id TEXT NOT NULL,
            published_at TIMESTAMP,
            summary TEXT,
            author TEXT,
            content TEXT,
            fetched_at TIMESTAMP,
            relevance_score REAL,
            relevance_tier TEXT
        );
        """
    )
    conn.execute(
        """
        INSERT INTO feed_entries (
            id, title, url, source_id, published_at, summary, author,
            content, fetched_at, relevance_score, relevance_tier
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "feed-1",
            "Fresh agent eval result",
            "https://example.test/fresh-agent-eval",
            "agent-evals",
            datetime.now().isoformat(),
            "summary",
            "author",
            "LLM agent benchmark content " * 40,
            datetime.now().isoformat(),
            0.95,
            "must_read",
        ),
    )
    conn.commit()
    conn.close()

    conn = sqlite3.connect(newsletter_db)
    conn.executescript(
        """
        CREATE TABLE newsletter_entries (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            url TEXT NOT NULL,
            newsletter_id TEXT NOT NULL,
            published_at TIMESTAMP,
            author TEXT,
            content_text TEXT,
            fetched_at TIMESTAMP
        );
        """
    )
    conn.close()

    monkeypatch.setattr(briefing, "DB_PATH", legacy_db)
    monkeypatch.setattr(briefing, "STATE_FEED_DB_PATH", feed_db)
    monkeypatch.setattr(briefing, "STATE_NEWSLETTER_DB_PATH", newsletter_db)

    articles = briefing.get_recent_articles(days=7)

    assert [article["title"] for article in articles] == ["Fresh agent eval result"]
    assert articles[0]["domain"] == "ai"


def test_validate_generated_briefing_rejects_placeholders_and_tiny_output():
    try:
        briefing.validate_generated_briefing("Test")
    except ValueError as exc:
        assert "placeholder" in str(exc)
    else:
        raise AssertionError("placeholder output should be rejected")

    try:
        briefing.validate_generated_briefing("# Brief\nshort")
    except ValueError as exc:
        assert "undersized" in str(exc)
    else:
        raise AssertionError("undersized output should be rejected")
