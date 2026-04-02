#!/usr/bin/env python3
"""
Article Storage for High-Signal News

Provides persistent storage for processed articles with full-text search,
deduplication tracking, and feed metadata management.
"""

import json
import sqlite3
import hashlib
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, Iterator


@dataclass
class Article:
    """A processed, deduplicated article ready for consumption."""
    id: str
    title: str
    url: str
    source_id: str
    source_name: str
    domain: str  # ai, software_development, investment
    published_at: Optional[datetime]
    fetched_at: datetime
    author: Optional[str] = None
    summary: Optional[str] = None
    content: Optional[str] = None  # Full extracted content
    content_hash: Optional[str] = None  # For deduplication
    simhash: Optional[int] = None  # For near-duplicate detection
    word_count: int = 0
    reading_time_minutes: int = 0
    tags: str = ""  # Comma-separated tags
    is_duplicate: bool = False
    duplicate_of: Optional[str] = None  # Original article ID if duplicate
    cluster_id: Optional[str] = None  # Story cluster ID


@dataclass
class StoryCluster:
    """A cluster of articles about the same story/event."""
    id: str
    title: str  # Representative title
    domain: str
    created_at: datetime
    updated_at: datetime
    article_ids: str  # JSON list of article IDs
    source_count: int  # Number of unique sources
    representative_url: str


@dataclass
class IngestionLog:
    """Log entry for ingestion operations."""
    id: int
    operation: str  # 'fetch', 'extract', 'dedup', 'store'
    source_id: Optional[str]
    started_at: datetime
    completed_at: Optional[datetime]
    items_count: int
    success: bool
    error_message: Optional[str] = None


class ArticleStorage:
    """
    SQLite-based storage for processed articles with full-text search.

    This storage layer sits above FeedCache and stores deduplicated,
    processed articles ready for the summarization engine.
    """

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialize the database schema."""
        with sqlite3.connect(self.db_path) as conn:
            # Main articles table
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS articles (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL UNIQUE,
                    source_id TEXT NOT NULL,
                    source_name TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    published_at TIMESTAMP,
                    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    author TEXT,
                    summary TEXT,
                    content TEXT,
                    content_hash TEXT,
                    simhash INTEGER,
                    word_count INTEGER DEFAULT 0,
                    reading_time_minutes INTEGER DEFAULT 0,
                    tags TEXT DEFAULT '',
                    is_duplicate BOOLEAN DEFAULT 0,
                    duplicate_of TEXT,
                    cluster_id TEXT,
                    FOREIGN KEY (duplicate_of) REFERENCES articles(id),
                    FOREIGN KEY (cluster_id) REFERENCES story_clusters(id)
                );

                CREATE INDEX IF NOT EXISTS idx_articles_domain
                    ON articles(domain);
                CREATE INDEX IF NOT EXISTS idx_articles_source
                    ON articles(source_id);
                CREATE INDEX IF NOT EXISTS idx_articles_published
                    ON articles(published_at DESC);
                CREATE INDEX IF NOT EXISTS idx_articles_fetched
                    ON articles(fetched_at DESC);
                CREATE INDEX IF NOT EXISTS idx_articles_content_hash
                    ON articles(content_hash);
                CREATE INDEX IF NOT EXISTS idx_articles_cluster
                    ON articles(cluster_id);
                CREATE INDEX IF NOT EXISTS idx_articles_duplicate
                    ON articles(is_duplicate);

                -- Full-text search virtual table
                CREATE VIRTUAL TABLE IF NOT EXISTS articles_fts USING fts5(
                    title, summary, content,
                    content='articles',
                    content_rowid='rowid'
                );

                -- Triggers to keep FTS index in sync
                CREATE TRIGGER IF NOT EXISTS articles_fts_insert AFTER INSERT ON articles
                BEGIN
                    INSERT INTO articles_fts(rowid, title, summary, content)
                    VALUES (new.rowid, new.title, new.summary, new.content);
                END;

                CREATE TRIGGER IF NOT EXISTS articles_fts_update AFTER UPDATE ON articles
                BEGIN
                    UPDATE articles_fts SET
                        title = new.title,
                        summary = new.summary,
                        content = new.content
                    WHERE rowid = new.rowid;
                END;

                CREATE TRIGGER IF NOT EXISTS articles_fts_delete AFTER DELETE ON articles
                BEGIN
                    DELETE FROM articles_fts WHERE rowid = old.rowid;
                END;

                -- Story clusters for grouping related articles
                CREATE TABLE IF NOT EXISTS story_clusters (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    domain TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    article_ids TEXT NOT NULL,  -- JSON list
                    source_count INTEGER DEFAULT 1,
                    representative_url TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_clusters_domain
                    ON story_clusters(domain);
                CREATE INDEX IF NOT EXISTS idx_clusters_updated
                    ON story_clusters(updated_at DESC);

                -- Ingestion log for monitoring
                CREATE TABLE IF NOT EXISTS ingestion_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    operation TEXT NOT NULL,
                    source_id TEXT,
                    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    items_count INTEGER DEFAULT 0,
                    success BOOLEAN DEFAULT 1,
                    error_message TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_log_operation
                    ON ingestion_log(operation);
                CREATE INDEX IF NOT EXISTS idx_log_started
                    ON ingestion_log(started_at DESC);
                CREATE INDEX IF NOT EXISTS idx_log_source
                    ON ingestion_log(source_id);
            """)

    def save_article(self, article: Article) -> bool:
        """
        Save an article to storage.

        Returns True if saved, False if duplicate URL (existing returned).
        """
        with sqlite3.connect(self.db_path) as conn:
            try:
                conn.execute("""
                    INSERT INTO articles (
                        id, title, url, source_id, source_name, domain,
                        published_at, fetched_at, author, summary, content,
                        content_hash, simhash, word_count, reading_time_minutes,
                        tags, is_duplicate, duplicate_of, cluster_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    article.id, article.title, article.url, article.source_id,
                    article.source_name, article.domain,
                    article.published_at.isoformat() if article.published_at else None,
                    article.fetched_at.isoformat() if article.fetched_at else datetime.now().isoformat(),
                    article.author, article.summary, article.content,
                    article.content_hash, article.simhash, article.word_count,
                    article.reading_time_minutes, article.tags,
                    article.is_duplicate, article.duplicate_of, article.cluster_id
                ))
                return True
            except sqlite3.IntegrityError:
                # URL already exists
                return False

    def save_articles(self, articles: list[Article]) -> tuple[int, int]:
        """
        Save multiple articles in a transaction.

        Returns (saved_count, duplicate_count).
        """
        saved = 0
        duplicates = 0

        with sqlite3.connect(self.db_path) as conn:
            for article in articles:
                try:
                    conn.execute("""
                        INSERT INTO articles (
                            id, title, url, source_id, source_name, domain,
                            published_at, fetched_at, author, summary, content,
                            content_hash, simhash, word_count, reading_time_minutes,
                            tags, is_duplicate, duplicate_of, cluster_id
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        article.id, article.title, article.url, article.source_id,
                        article.source_name, article.domain,
                        article.published_at.isoformat() if article.published_at else None,
                        article.fetched_at.isoformat() if article.fetched_at else datetime.now().isoformat(),
                        article.author, article.summary, article.content,
                        article.content_hash, article.simhash, article.word_count,
                        article.reading_time_minutes, article.tags,
                        article.is_duplicate, article.duplicate_of, article.cluster_id
                    ))
                    saved += 1
                except sqlite3.IntegrityError:
                    duplicates += 1

            conn.commit()

        return saved, duplicates

    def get_article(self, article_id: str) -> Optional[Article]:
        """Retrieve an article by ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM articles WHERE id = ?",
                (article_id,)
            ).fetchone()

            if row:
                return self._row_to_article(row)
            return None

    def get_article_by_url(self, url: str) -> Optional[Article]:
        """Retrieve an article by URL."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM articles WHERE url = ?",
                (url,)
            ).fetchone()

            if row:
                return self._row_to_article(row)
            return None

    def search_articles(
        self,
        query: str,
        domain: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> list[Article]:
        """
        Search articles using full-text search.

        Args:
            query: FTS5 search query
            domain: Optional domain filter
            limit: Maximum results
            offset: Results offset for pagination
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            if domain:
                rows = conn.execute("""
                    SELECT a.* FROM articles a
                    JOIN articles_fts fts ON a.rowid = fts.rowid
                    WHERE articles_fts MATCH ? AND a.domain = ? AND a.is_duplicate = 0
                    ORDER BY rank
                    LIMIT ? OFFSET ?
                """, (query, domain, limit, offset)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT a.* FROM articles a
                    JOIN articles_fts fts ON a.rowid = fts.rowid
                    WHERE articles_fts MATCH ? AND a.is_duplicate = 0
                    ORDER BY rank
                    LIMIT ? OFFSET ?
                """, (query, limit, offset)).fetchall()

            return [self._row_to_article(row) for row in rows]

    def get_recent_articles(
        self,
        domain: Optional[str] = None,
        hours: int = 24,
        exclude_duplicates: bool = True,
        limit: int = 100
    ) -> list[Article]:
        """Get articles published within the last N hours."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            since = datetime.now().isoformat()

            params = []
            where_clauses = ["published_at > datetime('now', '-{} hours')".format(hours)]

            if domain:
                where_clauses.append("domain = ?")
                params.append(domain)

            if exclude_duplicates:
                where_clauses.append("is_duplicate = 0")

            query = f"""
                SELECT * FROM articles
                WHERE {' AND '.join(where_clauses)}
                ORDER BY published_at DESC
                LIMIT ?
            """
            params.append(limit)

            rows = conn.execute(query, params).fetchall()
            return [self._row_to_article(row) for row in rows]

    def get_articles_by_source(
        self,
        source_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> list[Article]:
        """Get articles from a specific source."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT * FROM articles
                   WHERE source_id = ? AND is_duplicate = 0
                   ORDER BY published_at DESC
                   LIMIT ? OFFSET ?""",
                (source_id, limit, offset)
            ).fetchall()
            return [self._row_to_article(row) for row in rows]

    def get_duplicate_articles(self, original_id: str) -> list[Article]:
        """Get all duplicates of a specific article."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM articles WHERE duplicate_of = ? ORDER BY fetched_at",
                (original_id,)
            ).fetchall()
            return [self._row_to_article(row) for row in rows]

    def check_content_hash_exists(self, content_hash: str) -> Optional[str]:
        """Check if a content hash exists, return article ID if found."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT id FROM articles WHERE content_hash = ? LIMIT 1",
                (content_hash,)
            ).fetchone()
            return row[0] if row else None

    def save_cluster(self, cluster: StoryCluster) -> bool:
        """Save a story cluster."""
        with sqlite3.connect(self.db_path) as conn:
            try:
                conn.execute("""
                    INSERT INTO story_clusters (
                        id, title, domain, created_at, updated_at,
                        article_ids, source_count, representative_url
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET
                        title = excluded.title,
                        updated_at = excluded.updated_at,
                        article_ids = excluded.article_ids,
                        source_count = excluded.source_count,
                        representative_url = excluded.representative_url
                """, (
                    cluster.id, cluster.title, cluster.domain,
                    cluster.created_at.isoformat(),
                    cluster.updated_at.isoformat(),
                    cluster.article_ids, cluster.source_count,
                    cluster.representative_url
                ))
                return True
            except sqlite3.Error:
                return False

    def get_cluster(self, cluster_id: str) -> Optional[StoryCluster]:
        """Retrieve a story cluster by ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM story_clusters WHERE id = ?",
                (cluster_id,)
            ).fetchone()

            if row:
                return StoryCluster(
                    id=row['id'],
                    title=row['title'],
                    domain=row['domain'],
                    created_at=datetime.fromisoformat(row['created_at']),
                    updated_at=datetime.fromisoformat(row['updated_at']),
                    article_ids=row['article_ids'],
                    source_count=row['source_count'],
                    representative_url=row['representative_url']
                )
            return None

    def log_ingestion(
        self,
        operation: str,
        source_id: Optional[str] = None,
        items_count: int = 0,
        success: bool = True,
        error_message: Optional[str] = None
    ) -> int:
        """Log an ingestion operation."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                """INSERT INTO ingestion_log
                   (operation, source_id, items_count, success, error_message)
                   VALUES (?, ?, ?, ?, ?)""",
                (operation, source_id, items_count, success, error_message)
            )
            return cursor.lastrowid

    def complete_ingestion_log(self, log_id: int, success: bool = True, error_message: Optional[str] = None):
        """Mark an ingestion log entry as completed."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """UPDATE ingestion_log
                   SET completed_at = datetime('now'), success = ?, error_message = ?
                   WHERE id = ?""",
                (success, error_message, log_id)
            )

    def get_recent_logs(
        self,
        operation: Optional[str] = None,
        limit: int = 50
    ) -> list[IngestionLog]:
        """Get recent ingestion logs."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            if operation:
                rows = conn.execute(
                    """SELECT * FROM ingestion_log
                       WHERE operation = ?
                       ORDER BY started_at DESC
                       LIMIT ?""",
                    (operation, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT * FROM ingestion_log
                       ORDER BY started_at DESC
                       LIMIT ?""",
                    (limit,)
                ).fetchall()

            return [
                IngestionLog(
                    id=row['id'],
                    operation=row['operation'],
                    source_id=row['source_id'],
                    started_at=datetime.fromisoformat(row['started_at']),
                    completed_at=datetime.fromisoformat(row['completed_at']) if row['completed_at'] else None,
                    items_count=row['items_count'],
                    success=row['success'],
                    error_message=row['error_message']
                )
                for row in rows
            ]

    def get_stats(self) -> dict:
        """Get storage statistics."""
        with sqlite3.connect(self.db_path) as conn:
            stats = {}

            # Article counts
            row = conn.execute(
                "SELECT COUNT(*) FROM articles WHERE is_duplicate = 0"
            ).fetchone()
            stats['total_articles'] = row[0]

            row = conn.execute(
                "SELECT COUNT(*) FROM articles WHERE is_duplicate = 1"
            ).fetchone()
            stats['duplicate_articles'] = row[0]

            # By domain
            rows = conn.execute(
                """SELECT domain, COUNT(*) as count
                   FROM articles WHERE is_duplicate = 0
                   GROUP BY domain"""
            ).fetchall()
            stats['by_domain'] = {row[0]: row[1] for row in rows}

            # By source
            rows = conn.execute(
                """SELECT source_name, COUNT(*) as count
                   FROM articles WHERE is_duplicate = 0
                   GROUP BY source_name ORDER BY count DESC LIMIT 10"""
            ).fetchall()
            stats['top_sources'] = {row[0]: row[1] for row in rows}

            # Recent (24h)
            row = conn.execute(
                """SELECT COUNT(*) FROM articles
                   WHERE fetched_at > datetime('now', '-24 hours')
                   AND is_duplicate = 0"""
            ).fetchone()
            stats['last_24h'] = row[0]

            # Clusters
            row = conn.execute("SELECT COUNT(*) FROM story_clusters").fetchone()
            stats['story_clusters'] = row[0]

            return stats

    def _row_to_article(self, row: sqlite3.Row) -> Article:
        """Convert a database row to an Article."""
        return Article(
            id=row['id'],
            title=row['title'],
            url=row['url'],
            source_id=row['source_id'],
            source_name=row['source_name'],
            domain=row['domain'],
            published_at=datetime.fromisoformat(row['published_at']) if row['published_at'] else None,
            fetched_at=datetime.fromisoformat(row['fetched_at']),
            author=row['author'],
            summary=row['summary'],
            content=row['content'],
            content_hash=row['content_hash'],
            simhash=row['simhash'],
            word_count=row['word_count'],
            reading_time_minutes=row['reading_time_minutes'],
            tags=row['tags'],
            is_duplicate=bool(row['is_duplicate']),
            duplicate_of=row['duplicate_of'],
            cluster_id=row['cluster_id']
        )

    def vacuum(self):
        """Optimize the database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("VACUUM")

    def close(self):
        """Close any open connections (no-op for connection-per-method)."""
        pass


def create_article_from_entry(
    entry_id: str,
    title: str,
    url: str,
    source_id: str,
    source_name: str,
    domain: str,
    published_at: Optional[datetime] = None,
    author: Optional[str] = None,
    summary: Optional[str] = None,
    content: Optional[str] = None,
) -> Article:
    """Helper to create an Article from feed entry data."""
    # Calculate content hash
    content_to_hash = f"{title}:{summary or ''}:{content or ''}"[:1000]
    content_hash = hashlib.sha256(content_to_hash.encode()).hexdigest()[:16]

    # Calculate word count and reading time
    text = content or summary or title
    word_count = len(text.split()) if text else 0
    reading_time_minutes = max(1, word_count // 200)  # ~200 WPM

    return Article(
        id=entry_id,
        title=title,
        url=url,
        source_id=source_id,
        source_name=source_name,
        domain=domain,
        published_at=published_at,
        fetched_at=datetime.now(),
        author=author,
        summary=summary,
        content=content,
        content_hash=content_hash,
        word_count=word_count,
        reading_time_minutes=reading_time_minutes,
    )


if __name__ == '__main__':
    # Quick test
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / 'test.db'
        storage = ArticleStorage(db_path)

        # Create test article
        article = create_article_from_entry(
            entry_id='test-1',
            title='Test Article',
            url='https://example.com/test',
            source_id='test-source',
            source_name='Test Source',
            domain='ai',
            summary='This is a test article',
            content='Full content of the test article.'
        )

        # Save
        saved = storage.save_article(article)
        print(f"Article saved: {saved}")

        # Retrieve
        retrieved = storage.get_article('test-1')
        print(f"Retrieved: {retrieved.title if retrieved else 'None'}")

        # Search
        results = storage.search_articles('test')
        print(f"Search results: {len(results)}")

        # Stats
        stats = storage.get_stats()
        print(f"Stats: {stats}")

        print("\n✅ Storage module test passed!")
