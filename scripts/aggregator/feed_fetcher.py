#!/usr/bin/env python3
"""
RSS Feed Fetcher for High-Signal News

Fetches and caches RSS feeds from configured sources with rate limiting
and respectful crawling behavior.
"""

import json
import hashlib
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict
from urllib.parse import urlparse
import sqlite3

# Optional dependencies with graceful fallback
try:
    import feedparser
    FEEDPARSER_AVAILABLE = True
except ImportError:
    FEEDPARSER_AVAILABLE = False

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


@dataclass
class FeedEntry:
    """Represents a single feed entry/article."""
    id: str
    title: str
    url: str
    source_id: str
    published_at: Optional[datetime]
    summary: Optional[str]
    author: Optional[str]
    content: Optional[str]
    fetched_at: datetime


@dataclass
class FeedSource:
    """Configuration for a feed source."""
    id: str
    name: str
    url: str
    format: str  # RSS, Atom, etc.
    category: str
    domain: str  # ai, software_development, investment
    signal_quality: str
    active: bool = True
    fetch_interval_minutes: int = 60


class FeedCache:
    """SQLite-based cache for feed entries and metadata."""
    
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize the database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS feed_entries (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    published_at TIMESTAMP,
                    summary TEXT,
                    author TEXT,
                    content TEXT,
                    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(url, source_id)
                );
                
                CREATE INDEX IF NOT EXISTS idx_entries_source 
                    ON feed_entries(source_id);
                CREATE INDEX IF NOT EXISTS idx_entries_published 
                    ON feed_entries(published_at DESC);
                CREATE INDEX IF NOT EXISTS idx_entries_fetched 
                    ON feed_entries(fetched_at DESC);
                
                CREATE VIRTUAL TABLE IF NOT EXISTS feed_entries_fts USING fts5(
                    title, summary, content,
                    content='feed_entries',
                    content_rowid='rowid'
                );
                
                CREATE TABLE IF NOT EXISTS feed_sources (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    url TEXT NOT NULL,
                    format TEXT,
                    category TEXT,
                    domain TEXT,
                    signal_quality TEXT,
                    active BOOLEAN DEFAULT 1,
                    last_fetched TIMESTAMP,
                    fetch_interval_minutes INTEGER DEFAULT 60,
                    error_count INTEGER DEFAULT 0,
                    last_error TEXT
                );
                
                CREATE TABLE IF NOT EXISTS fetch_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_id TEXT,
                    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    entries_count INTEGER,
                    success BOOLEAN,
                    error_message TEXT,
                    response_time_ms INTEGER
                );
            """)
    
    def save_source(self, source: FeedSource):
        """Save or update a feed source configuration."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO feed_sources 
                (id, name, url, format, category, domain, signal_quality, active, fetch_interval_minutes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (source.id, source.name, source.url, source.format, 
                  source.category, source.domain, source.signal_quality,
                  source.active, source.fetch_interval_minutes))
    
    def get_sources(self, domain: Optional[str] = None, active_only: bool = True) -> list[FeedSource]:
        """Get configured feed sources."""
        with sqlite3.connect(self.db_path) as conn:
            query = "SELECT * FROM feed_sources WHERE 1=1"
            params = []
            if active_only:
                query += " AND active = 1"
            if domain:
                query += " AND domain = ?"
                params.append(domain)
            
            rows = conn.execute(query, params).fetchall()
            columns = [desc[0] for desc in conn.execute(
                "SELECT * FROM feed_sources LIMIT 0"
            ).description]
            
            sources = []
            for row in rows:
                data = dict(zip(columns, row))
                sources.append(FeedSource(
                    id=data['id'],
                    name=data['name'],
                    url=data['url'],
                    format=data['format'],
                    category=data['category'],
                    domain=data['domain'],
                    signal_quality=data['signal_quality'],
                    active=bool(data['active']),
                    fetch_interval_minutes=data['fetch_interval_minutes']
                ))
            return sources
    
    def should_fetch(self, source_id: str) -> bool:
        """Check if a source should be fetched based on its interval."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                """SELECT last_fetched, fetch_interval_minutes 
                   FROM feed_sources WHERE id = ?""", 
                (source_id,)
            ).fetchone()
            
            if not row or row[0] is None:
                return True
            
            last_fetched = datetime.fromisoformat(row[0])
            interval = timedelta(minutes=row[1])
            return datetime.now() - last_fetched >= interval
    
    def save_entries(self, entries: list[FeedEntry]):
        """Save feed entries to the database."""
        with sqlite3.connect(self.db_path) as conn:
            for entry in entries:
                try:
                    conn.execute("""
                        INSERT OR IGNORE INTO feed_entries 
                        (id, title, url, source_id, published_at, summary, author, content, fetched_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        entry.id, entry.title, entry.url, entry.source_id,
                        entry.published_at.isoformat() if entry.published_at else None,
                        entry.summary, entry.author, entry.content,
                        entry.fetched_at.isoformat()
                    ))
                except sqlite3.IntegrityError:
                    pass  # Duplicate entry, ignore
    
    def log_fetch(self, source_id: str, entries_count: int, success: bool, 
                  error_message: Optional[str] = None, response_time_ms: int = 0):
        """Log a fetch operation."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO fetch_log (source_id, entries_count, success, error_message, response_time_ms)
                VALUES (?, ?, ?, ?, ?)
            """, (source_id, entries_count, success, error_message, response_time_ms))
            
            # Update source's last_fetched and error tracking
            if success:
                conn.execute(
                    "UPDATE feed_sources SET last_fetched = ?, error_count = 0 WHERE id = ?",
                    (datetime.now().isoformat(), source_id)
                )
            else:
                conn.execute(
                    """UPDATE feed_sources 
                       SET error_count = error_count + 1, last_error = ? 
                       WHERE id = ?""",
                    (error_message, source_id)
                )


class FeedFetcher:
    """Main feed fetcher with rate limiting and caching."""
    
    def __init__(self, cache: FeedCache, min_fetch_interval_seconds: int = 5):
        self.cache = cache
        self.min_fetch_interval = min_fetch_interval_seconds
        self.last_fetch_time: Optional[float] = None
    
    def _rate_limit(self):
        """Enforce minimum interval between fetches."""
        if self.last_fetch_time:
            elapsed = time.time() - self.last_fetch_time
            if elapsed < self.min_fetch_interval:
                time.sleep(self.min_fetch_interval - elapsed)
        self.last_fetch_time = time.time()
    
    def _generate_entry_id(self, url: str, title: str) -> str:
        """Generate a stable ID for a feed entry."""
        content = f"{url}:{title}".encode('utf-8')
        return hashlib.sha256(content).hexdigest()[:16]
    
    def fetch_rss(self, source: FeedSource) -> list[FeedEntry]:
        """Fetch and parse an RSS/Atom feed."""
        if not FEEDPARSER_AVAILABLE:
            raise RuntimeError("feedparser library required for RSS fetching")
        
        self._rate_limit()
        start_time = time.time()
        
        try:
            parsed = feedparser.parse(source.url)
            entries = []
            
            for entry in parsed.entries:
                # Extract publication date
                published = None
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    published = datetime(*entry.published_parsed[:6])
                elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                    published = datetime(*entry.updated_parsed[:6])
                
                # Get content/summary
                content = None
                if hasattr(entry, 'content') and entry.content:
                    content = entry.content[0].value
                
                summary = entry.get('summary', '')
                if not summary and content:
                    summary = content[:500] + '...' if len(content) > 500 else content
                
                feed_entry = FeedEntry(
                    id=self._generate_entry_id(entry.link, entry.title),
                    title=entry.title,
                    url=entry.link,
                    source_id=source.id,
                    published_at=published,
                    summary=summary,
                    author=entry.get('author'),
                    content=content,
                    fetched_at=datetime.now()
                )
                entries.append(feed_entry)
            
            response_time = int((time.time() - start_time) * 1000)
            self.cache.log_fetch(source.id, len(entries), True, response_time_ms=response_time)
            
            return entries
            
        except Exception as e:
            response_time = int((time.time() - start_time) * 1000)
            self.cache.log_fetch(source.id, 0, False, str(e), response_time)
            raise
    
    def fetch_source(self, source: FeedSource) -> list[FeedEntry]:
        """Fetch a single source based on its format."""
        if not self.cache.should_fetch(source.id):
            print(f"Skipping {source.id}: fetched recently")
            return []
        
        if source.format.upper() in ('RSS', 'ATOM'):
            return self.fetch_rss(source)
        else:
            raise ValueError(f"Unsupported feed format: {source.format}")
    
    def fetch_all(self, domain: Optional[str] = None) -> dict[str, list[FeedEntry]]:
        """Fetch all configured sources."""
        sources = self.cache.get_sources(domain=domain)
        results = {}
        
        for source in sources:
            try:
                print(f"Fetching {source.name} ({source.id})...")
                entries = self.fetch_source(source)
                self.cache.save_entries(entries)
                results[source.id] = entries
                print(f"  -> {len(entries)} entries")
            except Exception as e:
                print(f"  -> ERROR: {e}")
                results[source.id] = []
        
        return results


def load_sources_from_catalog(catalog_path: Path) -> list[FeedSource]:
    """Load feed sources from the source catalog JSON."""
    with open(catalog_path) as f:
        catalog = json.load(f)
    
    sources = []
    for domain_key, domain_data in catalog.get('domains', {}).items():
        for category, items in domain_data.get('sources', {}).items():
            for item in items:
                if 'url' in item and item.get('active', False):
                    source = FeedSource(
                        id=item['id'],
                        name=item['name'],
                        url=item['url'],
                        format=item.get('format', 'RSS').upper(),
                        category=item.get('category', category),
                        domain=domain_key,
                        signal_quality=item.get('signal_quality', 'Medium'),
                        active=item.get('active', True)
                    )
                    sources.append(source)
    
    return sources


def main():
    """CLI entry point for testing."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Fetch RSS feeds for high-signal news')
    parser.add_argument('--db', default='state/feeds.db', help='Database path')
    parser.add_argument('--catalog', default='research/source-catalog.json', 
                        help='Source catalog JSON')
    parser.add_argument('--domain', choices=['ai', 'software_development', 'investment'],
                        help='Filter by domain')
    parser.add_argument('--init', action='store_true', 
                        help='Initialize with sources from catalog')
    
    args = parser.parse_args()
    
    # Ensure state directory exists
    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    cache = FeedCache(db_path)
    
    if args.init:
        catalog_path = Path(args.catalog)
        if not catalog_path.exists():
            print(f"Catalog not found: {catalog_path}")
            return 1
        
        sources = load_sources_from_catalog(catalog_path)
        for source in sources:
            cache.save_source(source)
            print(f"Registered: {source.name} ({source.id})")
        print(f"\nTotal sources: {len(sources)}")
        return 0
    
    fetcher = FeedFetcher(cache)
    results = fetcher.fetch_all(domain=args.domain)
    
    total = sum(len(entries) for entries in results.values())
    print(f"\nTotal entries fetched: {total}")
    return 0


if __name__ == '__main__':
    exit(main())
