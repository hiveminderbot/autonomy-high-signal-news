#!/usr/bin/env python3
"""
Newsletter Ingestion System for High-Signal News

Ingests newsletters from various sources (IMAP, webhooks, file-based)
and normalizes them into FeedEntry objects for the aggregation pipeline.
"""

import json
import hashlib
import re
import sqlite3
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse


@dataclass
class NewsletterSource:
    """Configuration for a newsletter source."""
    id: str
    name: str
    provider: str  # substack, buttondown, convertkit, file, imap, etc.
    source_url: str  # URL pattern or file path pattern
    category: str
    domain: str
    signal_quality: str
    active: bool = True
    # Provider-specific config stored as JSON string
    config: Optional[str] = None


@dataclass
class NewsletterEntry:
    """Represents a single newsletter article/issue."""
    id: str
    title: str
    url: str
    newsletter_id: str
    published_at: Optional[datetime]
    author: Optional[str]
    content_html: Optional[str]
    content_text: Optional[str]
    links: list[dict]  # Extracted links with titles
    fetched_at: datetime


class NewsletterCache:
    """SQLite-based cache for newsletter entries and metadata."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize the database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS newsletter_sources (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    provider TEXT NOT NULL,
                    source_url TEXT NOT NULL,
                    category TEXT,
                    domain TEXT,
                    signal_quality TEXT,
                    active BOOLEAN DEFAULT 1,
                    config TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS newsletter_entries (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL,
                    newsletter_id TEXT NOT NULL,
                    published_at TIMESTAMP,
                    author TEXT,
                    content_html TEXT,
                    content_text TEXT,
                    links TEXT,  -- JSON array
                    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(url, newsletter_id)
                );

                CREATE INDEX IF NOT EXISTS idx_nl_entries_newsletter
                    ON newsletter_entries(newsletter_id);
                CREATE INDEX IF NOT EXISTS idx_nl_entries_published
                    ON newsletter_entries(published_at DESC);

                CREATE TABLE IF NOT EXISTS newsletter_ingestion_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    newsletter_id TEXT,
                    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    entries_count INTEGER,
                    success BOOLEAN,
                    error_message TEXT
                );
            """)

    def save_source(self, source: NewsletterSource):
        """Save or update a newsletter source configuration."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO newsletter_sources
                (id, name, provider, source_url, category, domain, signal_quality, active, config)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (source.id, source.name, source.provider, source.source_url,
                  source.category, source.domain, source.signal_quality,
                  source.active, source.config))

    def get_sources(self, domain: Optional[str] = None, active_only: bool = True) -> list[NewsletterSource]:
        """Get configured newsletter sources."""
        with sqlite3.connect(self.db_path) as conn:
            query = "SELECT * FROM newsletter_sources WHERE 1=1"
            params = []
            if active_only:
                query += " AND active = 1"
            if domain:
                query += " AND domain = ?"
                params.append(domain)

            rows = conn.execute(query, params).fetchall()
            columns = [desc[0] for desc in conn.execute(
                "SELECT * FROM newsletter_sources LIMIT 0"
            ).description]

            sources = []
            for row in rows:
                data = dict(zip(columns, row))
                sources.append(NewsletterSource(
                    id=data['id'],
                    name=data['name'],
                    provider=data['provider'],
                    source_url=data['source_url'],
                    category=data['category'] or '',
                    domain=data['domain'] or '',
                    signal_quality=data['signal_quality'] or 'Medium',
                    active=bool(data['active']),
                    config=data['config']
                ))
            return sources

    def save_entries(self, entries: list[NewsletterEntry]):
        """Save newsletter entries to cache."""
        with sqlite3.connect(self.db_path) as conn:
            for entry in entries:
                conn.execute("""
                    INSERT OR REPLACE INTO newsletter_entries
                    (id, title, url, newsletter_id, published_at, author,
                     content_html, content_text, links, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (entry.id, entry.title, entry.url, entry.newsletter_id,
                      entry.published_at, entry.author, entry.content_html,
                      entry.content_text, json.dumps(entry.links), entry.fetched_at))

    def log_ingestion(self, newsletter_id: str, entries_count: int,
                      success: bool, error_message: Optional[str] = None):
        """Log an ingestion attempt."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO newsletter_ingestion_log
                (newsletter_id, entries_count, success, error_message)
                VALUES (?, ?, ?, ?)
            """, (newsletter_id, entries_count, success, error_message))


class NewsletterParser:
    """Parse newsletter HTML/text content into structured data."""

    @staticmethod
    def extract_links_from_html(html: str) -> list[dict]:
        """Extract all links from HTML content."""
        links = []
        # Simple regex-based extraction (production would use BeautifulSoup)
        link_pattern = r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>([^<]*)</a>'
        for match in re.finditer(link_pattern, html, re.IGNORECASE):
            url = match.group(1)
            title = match.group(2).strip()
            if url.startswith('http'):
                links.append({
                    'url': url,
                    'title': title[:200] if title else url[:100]
                })
        return links

    @staticmethod
    def html_to_text(html: str) -> str:
        """Convert HTML to plain text."""
        # Remove script and style elements
        text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
        # Convert common block elements to newlines
        text = re.sub(r'</(p|div|h[1-6]|li)>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
        # Remove remaining tags
        text = re.sub(r'<[^>]+>', '', text)
        # Decode common entities
        text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
        text = text.replace('&quot;', '"').replace('&#39;', "'")
        text = text.replace('&nbsp;', ' ')
        # Normalize whitespace
        text = re.sub(r'\n\s*\n', '\n\n', text)
        return text.strip()

    @staticmethod
    def parse_substack_export(file_path: Path) -> list[NewsletterEntry]:
        """Parse Substack export JSON/HTML files."""
        # Substack exports are typically HTML files with article content
        entries = []
        if not file_path.exists():
            return entries

        content = file_path.read_text(encoding='utf-8')

        # Extract newsletter issues from Substack export
        # Each post is typically wrapped in a known structure
        issue_pattern = r'<div class="post">.*?<h1[^>]*>(.*?)</h1>.*?<div class="body">(.*?)</div>.*?</div>'

        for idx, match in enumerate(re.finditer(issue_pattern, content, re.DOTALL | re.IGNORECASE)):
            title = NewsletterParser.html_to_text(match.group(1))
            html_content = match.group(2)
            text_content = NewsletterParser.html_to_text(html_content)
            links = NewsletterParser.extract_links_from_html(html_content)

            entry = NewsletterEntry(
                id=f"substack-{file_path.stem}-{idx}",
                title=title[:200] if title else f"Issue {idx+1}",
                url=f"file://{file_path}#issue-{idx}",
                newsletter_id=file_path.stem,
                published_at=None,
                author=None,
                content_html=html_content,
                content_text=text_content,
                links=links,
                fetched_at=datetime.now()
            )
            entries.append(entry)

        return entries


class NewsletterIngester:
    """Main class for ingesting newsletters from various sources."""

    def __init__(self, cache: NewsletterCache):
        self.cache = cache
        self.parser = NewsletterParser()

    def ingest_source(self, source: NewsletterSource) -> list[NewsletterEntry]:
        """
        Ingest newsletters from a single source.

        Args:
            source: NewsletterSource configuration

        Returns:
            List of NewsletterEntry objects
        """
        entries = []

        try:
            if source.provider == 'file':
                entries = self._ingest_file_source(source)
            elif source.provider == 'substack_export':
                entries = self._ingest_substack_export(source)
            elif source.provider == 'substack_rss':
                entries = self._ingest_substack_rss(source)
            elif source.provider == 'buttondown_rss':
                entries = self._ingest_buttondown_rss(source)
            else:
                raise ValueError(f"Unknown provider: {source.provider}")

            # Save to cache
            if entries:
                self.cache.save_entries(entries)

            self.cache.log_ingestion(source.id, len(entries), True)

        except Exception as e:
            self.cache.log_ingestion(source.id, 0, False, str(e))
            raise

        return entries

    def _ingest_file_source(self, source: NewsletterSource) -> list[NewsletterEntry]:
        """Ingest from file-based source (JSON, HTML)."""
        entries = []
        path = Path(source.source_url.replace('file://', ''))

        if not path.exists():
            return entries

        if path.suffix == '.json':
            data = json.loads(path.read_text())
            # Expect array of newsletter issues
            for idx, item in enumerate(data):
                entry = NewsletterEntry(
                    id=f"{source.id}-{idx}",
                    title=item.get('title', f'Issue {idx+1}'),
                    url=item.get('url', f"file://{path}#issue-{idx}"),
                    newsletter_id=source.id,
                    published_at=datetime.fromisoformat(item['published_at']) if item.get('published_at') else None,
                    author=item.get('author'),
                    content_html=item.get('content_html'),
                    content_text=item.get('content_text') or self.parser.html_to_text(item.get('content_html', '')),
                    links=item.get('links', []),
                    fetched_at=datetime.now()
                )
                entries.append(entry)

        return entries

    def _ingest_substack_export(self, source: NewsletterSource) -> list[NewsletterEntry]:
        """Ingest from Substack export file."""
        path = Path(source.source_url.replace('file://', ''))
        return self.parser.parse_substack_export(path)

    def _ingest_substack_rss(self, source: NewsletterSource) -> list[NewsletterEntry]:
        """Ingest from Substack RSS feed."""
        return self._ingest_rss_feed(source)

    def _ingest_buttondown_rss(self, source: NewsletterSource) -> list[NewsletterEntry]:
        """Ingest from Buttondown RSS feed."""
        return self._ingest_rss_feed(source)

    def _ingest_rss_feed(self, source: NewsletterSource) -> list[NewsletterEntry]:
        """
        Ingest from any RSS feed URL.

        Uses FeedFetcher to fetch and parse the RSS feed, then converts
        FeedEntry objects to NewsletterEntry objects.

        Args:
            source: NewsletterSource with RSS feed URL

        Returns:
            List of NewsletterEntry objects
        """
        try:
            # Import here to avoid circular dependencies
            from .feed_fetcher import FeedSource, FeedFetcher, FeedCache

            # Create a FeedSource from the NewsletterSource
            feed_source = FeedSource(
                id=source.id,
                name=source.name,
                url=source.source_url,
                format='RSS',
                category=source.category,
                domain=source.domain,
                signal_quality=source.signal_quality,
                active=source.active
            )

            # Use the newsletter cache's db_path for FeedCache
            feed_cache = FeedCache(self.cache.db_path)
            feed_cache.save_source(feed_source)

            # Fetch the RSS feed
            fetcher = FeedFetcher(feed_cache, min_fetch_interval_seconds=1)
            feed_entries = fetcher.fetch_rss(feed_source)

            # Convert FeedEntry objects to NewsletterEntry objects
            newsletter_entries = []
            for feed_entry in feed_entries:
                # Extract links from content if available
                links = []
                if feed_entry.content:
                    links = self.parser.extract_links_from_html(feed_entry.content)

                # Create NewsletterEntry
                entry = NewsletterEntry(
                    id=f"{source.id}-{feed_entry.id}",
                    title=feed_entry.title,
                    url=feed_entry.url,
                    newsletter_id=source.id,
                    published_at=feed_entry.published_at,
                    author=feed_entry.author or self._get_author_from_config(source),
                    content_html=feed_entry.content,
                    content_text=feed_entry.content or feed_entry.summary,
                    links=links,
                    fetched_at=feed_entry.fetched_at
                )
                newsletter_entries.append(entry)

            return newsletter_entries

        except ImportError as e:
            # FeedFetcher not available
            raise RuntimeError(f"RSS ingestion requires feed_fetcher module: {e}")
        except Exception as e:
            # Log error and return empty list
            self.cache.log_ingestion(source.id, 0, False, str(e))
            raise

    def _get_author_from_config(self, source: NewsletterSource) -> Optional[str]:
        """Extract author name from source config if available."""
        if source.config:
            try:
                config = json.loads(source.config)
                return config.get('author')
            except json.JSONDecodeError:
                pass
        return None

    def convert_to_feed_entries(self, newsletter_entries: list[NewsletterEntry]) -> list:
        """
        Convert NewsletterEntry objects to FeedEntry objects for pipeline integration.

        Returns:
            List of FeedEntry-compatible dicts (import FeedEntry from feed_fetcher for full objects)
        """
        feed_entries = []
        for entry in newsletter_entries:
            # Use first link as primary URL if available, else newsletter URL
            primary_url = entry.links[0]['url'] if entry.links else entry.url

            feed_entries.append({
                'id': entry.id,
                'title': entry.title,
                'url': primary_url,
                'source_id': entry.newsletter_id,
                'published_at': entry.published_at,
                'summary': entry.content_text[:500] if entry.content_text else None,
                'author': entry.author,
                'content': entry.content_text,
                'fetched_at': entry.fetched_at
            })

        return feed_entries


def load_newsletter_sources_from_catalog(catalog_path: Path) -> list[NewsletterSource]:
    """Load newsletter sources from a JSON catalog file."""
    if not catalog_path.exists():
        return []

    data = json.loads(catalog_path.read_text())
    sources = []

    for item in data.get('newsletters', []):
        sources.append(NewsletterSource(
            id=item['id'],
            name=item['name'],
            provider=item['provider'],
            source_url=item['source_url'],
            category=item.get('category', 'Newsletter'),
            domain=item.get('domain', 'general'),
            signal_quality=item.get('signal_quality', 'High'),
            active=item.get('active', True),
            config=json.dumps(item.get('config', {}))
        ))

    return sources


if __name__ == '__main__':
    # Simple CLI for testing
    import tempfile

    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = Path(f.name)

    cache = NewsletterCache(db_path)
    ingester = NewsletterIngester(cache)

    # Example: Create a sample newsletter source
    sample_source = NewsletterSource(
        id='sample-newsletter',
        name='Sample Newsletter',
        provider='file',
        source_url='file:///tmp/sample-newsletter.json',
        category='Technology',
        domain='ai',
        signal_quality='High'
    )

    print(f"Newsletter ingestion system initialized")
    print(f"Database: {db_path}")
    print(f"Sources configured: {len(cache.get_sources())}")
