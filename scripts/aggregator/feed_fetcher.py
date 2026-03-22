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
    # Summarization fields (Phase 3)
    cluster_id: Optional[str] = None
    relevance_score: Optional[float] = None
    relevance_tier: Optional[str] = None  # 'must_read', 'important', 'contextual', 'skip'
    entities: Optional[str] = None  # JSON-encoded list of entities
    generated_summary: Optional[str] = None  # AI-generated summary


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
    min_fetch_interval: int = 5  # Minimum seconds between requests to this source (rate limiting)


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
                    cluster_id TEXT,
                    relevance_score REAL,
                    relevance_tier TEXT,
                    entities TEXT,
                    generated_summary TEXT,
                    UNIQUE(url, source_id)
                );
                
                CREATE INDEX IF NOT EXISTS idx_entries_source 
                    ON feed_entries(source_id);
                CREATE INDEX IF NOT EXISTS idx_entries_published 
                    ON feed_entries(published_at DESC);
                CREATE INDEX IF NOT EXISTS idx_entries_fetched 
                    ON feed_entries(fetched_at DESC);
                CREATE INDEX IF NOT EXISTS idx_entries_cluster 
                    ON feed_entries(cluster_id);
                CREATE INDEX IF NOT EXISTS idx_entries_relevance 
                    ON feed_entries(relevance_score DESC);
                
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
                        INSERT OR REPLACE INTO feed_entries 
                        (id, title, url, source_id, published_at, summary, author, content, fetched_at,
                         cluster_id, relevance_score, relevance_tier, entities, generated_summary)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        entry.id, entry.title, entry.url, entry.source_id,
                        entry.published_at.isoformat() if entry.published_at else None,
                        entry.summary, entry.author, entry.content,
                        entry.fetched_at.isoformat(),
                        entry.cluster_id, entry.relevance_score, entry.relevance_tier,
                        entry.entities, entry.generated_summary
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
    
    def disable_source(self, source_id: str, reason: str = ""):
        """Disable a source and log the action."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE feed_sources SET active = 0 WHERE id = ?",
                (source_id,)
            )
            # Log the automatic disabling
            conn.execute("""
                INSERT INTO fetch_log (source_id, entries_count, success, error_message, response_time_ms)
                VALUES (?, 0, 0, ?, 0)
            """, (source_id, f"AUTO_DISABLED: {reason}"))
    
    def get_source_error_count(self, source_id: str) -> int:
        """Get the current error count for a source."""
        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT error_count FROM feed_sources WHERE id = ?",
                (source_id,)
            ).fetchone()
            return row[0] if row else 0
    
    def get_disabled_sources(self) -> list[FeedSource]:
        """Get all disabled (inactive) sources."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT * FROM feed_sources WHERE active = 0"
            ).fetchall()
            
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
    
    def reenable_source(self, source_id: str):
        """Re-enable a source and reset its error count."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "UPDATE feed_sources SET active = 1, error_count = 0 WHERE id = ?",
                (source_id,)
            )


class FeedFetcher:
    """Main feed fetcher with rate limiting, caching, and health monitoring."""
    
    # Error threshold for automatic source disabling
    ERROR_THRESHOLD = 5
    
    def __init__(self, cache: FeedCache, min_fetch_interval_seconds: int = 5, 
                 health_monitor=None, auto_disable: bool = True):
        self.cache = cache
        self.min_fetch_interval = min_fetch_interval_seconds
        self.last_fetch_time: Optional[float] = None
        self.last_source_fetch_time: dict[str, float] = {}  # Per-source rate limiting
        self.health_monitor = health_monitor
        self.auto_disable = auto_disable
    
    def _rate_limit(self, source_id: str = None, min_interval: int = None):
        """Enforce minimum interval between fetches.
        
        Args:
            source_id: Optional source ID for per-source rate limiting
            min_interval: Optional override for minimum interval in seconds
        """
        interval = min_interval if min_interval is not None else self.min_fetch_interval
        
        if source_id:
            # Per-source rate limiting
            last_time = self.last_source_fetch_time.get(source_id)
            if last_time:
                elapsed = time.time() - last_time
                if elapsed < interval:
                    sleep_time = interval - elapsed
                    print(f"  ⏱️  Rate limiting {source_id}: sleeping {sleep_time:.1f}s")
                    time.sleep(sleep_time)
            self.last_source_fetch_time[source_id] = time.time()
        else:
            # Global rate limiting (backward compatibility)
            if self.last_fetch_time:
                elapsed = time.time() - self.last_fetch_time
                if elapsed < interval:
                    time.sleep(interval - elapsed)
            self.last_fetch_time = time.time()
    
    def _generate_entry_id(self, url: str, title: str) -> str:
        """Generate a stable ID for a feed entry."""
        content = f"{url}:{title}".encode('utf-8')
        return hashlib.sha256(content).hexdigest()[:16]
    
    # Default headers to avoid bot detection
    # Note: Do NOT set Accept-Encoding - requests library handles decompression automatically
    DEFAULT_HEADERS = {
        'User-Agent': 'HighSignalNews/1.0 (Research Aggregator; https://github.com/exedev/high-signal-news)',
        'Accept': 'application/rss+xml, application/atom+xml, application/xml, text/xml, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Cache-Control': 'no-cache',
        'Connection': 'keep-alive',
    }
    
    # Retry configuration
    MAX_RETRIES = 3
    RETRY_DELAY_BASE = 1  # Base delay in seconds (1s, 2s, 4s)
    
    # RSSHub instances for Cloudflare-protected feeds
    # These are public RSSHub instances that can proxy feeds
    RSSHUB_INSTANCES = [
        'https://rsshub.app',
        'https://rsshub.rssforever.com',
        'https://rsshub.pseudoyu.com',
    ]
    
    def _fetch_with_retry(self, url: str, headers: dict = None) -> tuple[bytes, int]:
        """Fetch URL with exponential backoff retry logic.
        
        Returns:
            Tuple of (content_bytes, response_time_ms)
        """
        if not REQUESTS_AVAILABLE:
            raise RuntimeError("requests library required for fetching")
        
        request_headers = {**self.DEFAULT_HEADERS, **(headers or {})}
        last_error = None
        
        for attempt in range(self.MAX_RETRIES):
            try:
                start_time = time.time()
                response = requests.get(
                    url, 
                    headers=request_headers, 
                    timeout=30,
                    allow_redirects=True
                )
                response.raise_for_status()
                response_time = int((time.time() - start_time) * 1000)
                return response.content, response_time
                
            except requests.exceptions.RequestException as e:
                last_error = e
                if attempt < self.MAX_RETRIES - 1:
                    delay = self.RETRY_DELAY_BASE * (2 ** attempt)
                    time.sleep(delay)
                continue
        
        # All retries exhausted
        raise last_error or RuntimeError(f"Failed to fetch {url} after {self.MAX_RETRIES} attempts")
    
    def _is_cloudflare_error(self, error: Exception) -> bool:
        """Check if error indicates Cloudflare protection."""
        error_str = str(error).lower()
        return (
            'cloudflare' in error_str or
            '403' in error_str or
            'forbidden' in error_str or
            'cf-ray' in error_str
        )
    
    def _is_auth_error(self, error: Exception) -> bool:
        """Check if error indicates an authentication/authorization failure (401)."""
        error_str = str(error).lower()
        return (
            '401' in error_str or
            'unauthorized' in error_str or
            'auth_failed' in error_str
        )
    
    def _try_rsshub_fallback(self, original_url: str) -> tuple[bytes, int]:
        """Try to fetch via RSSHub instances as fallback for Cloudflare-protected feeds.
        
        RSSHub can proxy many feeds through different infrastructure, bypassing
        Cloudflare blocks on the original URL.
        
        Returns:
            Tuple of (content_bytes, response_time_ms) or raises exception
        """
        if not REQUESTS_AVAILABLE:
            raise RuntimeError("requests library required for RSSHub fallback")
        
        last_error = None
        
        for rsshub_base in self.RSSHUB_INSTANCES:
            try:
                # Encode the original URL for RSSHub route
                import urllib.parse
                encoded_url = urllib.parse.quote(original_url, safe='')
                rsshub_url = f"{rsshub_base}/rsshub/transform/json/{encoded_url}"
                
                start_time = time.time()
                response = requests.get(
                    rsshub_url,
                    headers=self.DEFAULT_HEADERS,
                    timeout=60,  # RSSHub can be slower
                    allow_redirects=True
                )
                response.raise_for_status()
                response_time = int((time.time() - start_time) * 1000)
                
                # RSSHub returns JSON, we need to convert it to RSS-like format
                # For now, return the content as-is and let feedparser handle it
                return response.content, response_time
                
            except requests.exceptions.RequestException as e:
                last_error = e
                continue
        
        raise last_error or RuntimeError(f"RSSHub fallback failed for {original_url}")
    
    def _try_feedsyndicate_fallback(self, original_url: str) -> tuple[bytes, int]:
        """Try alternative feed syndication services.
        
        Uses services like FeedBurner, Feedly, or other feed proxies.
        """
        if not REQUESTS_AVAILABLE:
            raise RuntimeError("requests library required for feed syndication fallback")
        
        # Try Feedly's feed fetcher (they have good infrastructure)
        try:
            import urllib.parse
            encoded_url = urllib.parse.quote(original_url, safe='')
            feedly_url = f"https://cloud.feedly.com/v3/streams/contents?streamId=feed/{encoded_url}"
            
            start_time = time.time()
            response = requests.get(
                feedly_url,
                headers=self.DEFAULT_HEADERS,
                timeout=30,
                allow_redirects=True
            )
            response.raise_for_status()
            response_time = int((time.time() - start_time) * 1000)
            
            return response.content, response_time
            
        except requests.exceptions.RequestException:
            pass
        
        raise RuntimeError(f"All feed syndication fallbacks failed for {original_url}")
    
    def _try_html_scrape_fallback(self, source: FeedSource) -> list[FeedEntry]:
        """Try to fetch by scraping HTML as fallback for RSS auth errors.
        
        Some sources (like Hugging Face Papers) require authentication for RSS
        but have public HTML pages. This fallback scrapes the HTML directly.
        
        Args:
            source: The FeedSource to scrape
            
        Returns:
            List of FeedEntry objects scraped from HTML
        """
        # Mapping of RSS source IDs to their HTML scraping configurations
        HTML_SCRAPE_CONFIGS = {
            'hugging-face-papers': {
                'list_url': 'https://huggingface.co/papers',
                'article_selector': 'article',
                'title_selector': 'h3',
                'link_selector': 'h3 a[href^="/papers/"]',
                'author_selector': None,
                'date_selector': None,
                'base_url': 'https://huggingface.co'
            },
            'towards-data-science': {
                'list_url': 'https://towardsdatascience.com/',
                'article_selector': 'article',
                'title_selector': 'h2 a, h1 a, .pw-post-title a',
                'link_selector': 'h2 a[href*="towardsdatascience.com"], h1 a[href*="towardsdatascience.com"], a[rel="noopener"]',
                'author_selector': '.pw-author a, [data-testid="authorName"]',
                'date_selector': 'time, [data-testid="storyPublishDate"]',
                'base_url': 'https://towardsdatascience.com'
            },
            'the-information': {
                'list_url': 'https://www.theinformation.com/',
                'article_selector': 'article, .article-card, .story-card',
                'title_selector': 'h2 a, h3 a, .headline a',
                'link_selector': 'a[href*="/articles/"], .headline a',
                'author_selector': '.byline, .author',
                'date_selector': 'time, .date',
                'base_url': 'https://www.theinformation.com'
            },
        }
        
        if source.id not in HTML_SCRAPE_CONFIGS:
            raise RuntimeError(f"No HTML scraping config for source: {source.id}")
        
        config = HTML_SCRAPE_CONFIGS[source.id]
        
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            raise RuntimeError("beautifulsoup4 required for HTML scraping fallback")
        
        # Fetch the HTML page
        headers = {
            'User-Agent': self.DEFAULT_HEADERS['User-Agent'],
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }
        
        response = requests.get(config['list_url'], headers=headers, timeout=30)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        entries = []
        articles = soup.select(config['article_selector'])
        
        for article in articles[:20]:  # Limit to 20 most recent
            try:
                # Extract title
                title_elem = article.select_one(config['title_selector'])
                if not title_elem:
                    continue
                title = title_elem.get_text(strip=True)
                
                # Extract link
                link_elem = article.select_one(config['link_selector'])
                if not link_elem:
                    continue
                
                href = link_elem.get('href', '')
                if not href:
                    continue
                
                # Build full URL
                if href.startswith('http'):
                    article_url = href
                elif href.startswith('/'):
                    article_url = config['base_url'] + href
                else:
                    from urllib.parse import urljoin
                    article_url = urljoin(config['list_url'], href)
                
                # Generate unique ID
                entry_id = hashlib.md5(f"{source.id}:{article_url}".encode()).hexdigest()[:16]
                
                feed_entry = FeedEntry(
                    id=entry_id,
                    title=title[:200],
                    url=article_url,
                    source_id=source.id,
                    published_at=None,  # HF Papers doesn't have dates in list view
                    summary=None,
                    author=None,
                    content=None,
                    fetched_at=datetime.now()
                )
                entries.append(feed_entry)
                
            except Exception as e:
                # Log and continue
                continue
        
        if not entries:
            raise RuntimeError(f"No entries found scraping HTML for {source.id}")
        
        return entries
    
    def fetch_rss(self, source: FeedSource) -> list[FeedEntry]:
        """Fetch and parse an RSS/Atom feed with retry logic and Cloudflare fallback."""
        if not FEEDPARSER_AVAILABLE:
            raise RuntimeError("feedparser library required for RSS fetching")
        
        # Use per-source rate limiting with configured interval
        self._rate_limit(source_id=source.id, min_interval=source.min_fetch_interval)
        start_time = time.time()
        content = None
        response_time = 0
        used_fallback = False
        fallback_method = None
        
        try:
            # Try primary fetch with retry logic
            try:
                content, response_time = self._fetch_with_retry(source.url)
            except Exception as primary_error:
                # Check if this is a Cloudflare block
                if self._is_cloudflare_error(primary_error):
                    print(f"  ⚠️  Cloudflare detected for {source.id}, trying RSSHub fallback...")
                    try:
                        content, response_time = self._try_rsshub_fallback(source.url)
                        used_fallback = True
                        fallback_method = 'rsshub'
                        print(f"  ✅ RSSHub fallback succeeded for {source.id}")
                    except Exception as rsshub_error:
                        print(f"  ⚠️  RSSHub failed, trying feed syndication fallback...")
                        content, response_time = self._try_feedsyndicate_fallback(source.url)
                        used_fallback = True
                        fallback_method = 'feedsyndicate'
                        print(f"  ✅ Feed syndication fallback succeeded for {source.id}")
                # Check if this is an auth error (401) - try HTML scraping fallback
                elif self._is_auth_error(primary_error):
                    print(f"  ⚠️  Auth error (401) for {source.id}, trying HTML scraping fallback...")
                    try:
                        entries = self._try_html_scrape_fallback(source)
                        used_fallback = True
                        fallback_method = 'html_scrape'
                        print(f"  ✅ HTML scraping fallback succeeded for {source.id} ({len(entries)} entries)")
                        
                        # Log success with fallback note
                        fetch_time = int((time.time() - start_time) * 1000)
                        self.cache.log_fetch(source.id, len(entries), True, 
                                            error_message="Success via html_scrape fallback", 
                                            response_time_ms=fetch_time)
                        
                        # Update health status
                        if self.health_monitor:
                            self.health_monitor.update_health_status(source.id, True)
                        
                        return entries
                    except Exception as html_error:
                        print(f"  ❌ HTML scraping fallback failed for {source.id}: {html_error}")
                        raise primary_error  # Re-raise original error
                else:
                    raise  # Re-raise if not Cloudflare or auth error
            
            parsed = feedparser.parse(content)
            
            # Check for feedparser-level errors
            if hasattr(parsed, 'bozo') and parsed.bozo:
                # Log but don't fail - many feeds have minor issues
                pass
            
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
                    author=entry.get("author"),
                    content=content,
                    fetched_at=datetime.now()
                )
                entries.append(feed_entry)
            
            # Use response_time from _fetch_with_retry or calculate locally
            fetch_time = response_time if response_time else int((time.time() - start_time) * 1000)
            
            # Log success, noting if fallback was used
            success_message = None
            if used_fallback and fallback_method:
                success_message = f"Success via {fallback_method} fallback"
            
            self.cache.log_fetch(source.id, len(entries), True, 
                                error_message=success_message, response_time_ms=fetch_time)
            
            # Update health status
            if self.health_monitor:
                self.health_monitor.update_health_status(source.id, True)
            
            return entries
            
        except Exception as e:
            fetch_time = int((time.time() - start_time) * 1000)
            self.cache.log_fetch(source.id, 0, False, str(e), fetch_time)
            
            # Update health status
            if self.health_monitor:
                self.health_monitor.update_health_status(source.id, False, str(e))
            
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
    
    def fetch_all(self, domain: Optional[str] = None, 
                  include_disabled: bool = False) -> dict[str, list[FeedEntry]]:
        """Fetch all configured sources.
        
        Args:
            domain: Filter by domain
            include_disabled: If True, also fetch disabled sources (for retry mode)
        """
        sources = self.cache.get_sources(domain=domain, active_only=not include_disabled)
        results = {}
        disabled_sources = []
        
        for source in sources:
            try:
                print(f"Fetching {source.name} ({source.id})...")
                entries = self.fetch_source(source)
                self.cache.save_entries(entries)
                results[source.id] = entries
                print(f"  -> {len(entries)} entries")
                
                # If this was a retry of a disabled source and it succeeded, re-enable it
                if include_disabled and not source.active and len(entries) > 0:
                    self.cache.reenable_source(source.id)
                    print(f"  ✅ Re-enabled {source.id} (fetch succeeded)")
                    
            except Exception as e:
                print(f"  -> ERROR: {e}")
                results[source.id] = []
                
                # Check if source should be automatically disabled
                if self.auto_disable and not include_disabled:
                    error_count = self.cache.get_source_error_count(source.id)
                    if error_count >= self.ERROR_THRESHOLD:
                        self.cache.disable_source(
                            source.id, 
                            f"Auto-disabled after {error_count} consecutive failures: {str(e)[:100]}"
                        )
                        disabled_sources.append(source.id)
                        print(f"  ⚠️  AUTO-DISABLED {source.id} after {error_count} failures")
        
        # Summary of auto-disabled sources
        if disabled_sources:
            print(f"\n⚠️  {len(disabled_sources)} source(s) auto-disabled due to repeated failures:")
            for sid in disabled_sources:
                print(f"    - {sid}")
            print(f"\nUse --retry-disabled to attempt fetching these sources again.")
        
        return results


def load_sources_from_catalog(catalog_path: Path) -> list[FeedSource]:
    """Load feed sources from the source catalog JSON."""
    with open(catalog_path) as f:
        catalog = json.load(f)
    
    sources = []
    domain = catalog.get('metadata', {}).get('domain', 'unknown')
    
    def _extract_sources(data, category_hint='General'):
        """Recursively extract feed sources from nested JSON structure."""
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and 'url' in item and 'name' in item:
                    # Skip newsletter sources - these are handled separately by newsletter_ingester
                    item_type = item.get('type', item.get('format', 'RSS')).upper()
                    if item_type == 'NEWSLETTER':
                        continue
                    
                    # Generate ID from name (slugify)
                    item_id = item['name'].lower().replace(' ', '-').replace('.', '-').replace('/', '-')
                    
                    # Check if source is disabled in catalog
                    is_disabled = item.get('disabled', False)
                    
                    source = FeedSource(
                        id=item_id,
                        name=item['name'],
                        url=item['url'],
                        format=item.get('type', item.get('format', 'RSS')).upper(),
                        category=item.get('focus', item.get('category', category_hint)),
                        domain=domain,
                        signal_quality='High' if item.get('quality_score', 0) >= 8 else 'Medium',
                        active=not is_disabled,
                        min_fetch_interval=item.get('min_fetch_interval', 5)  # Per-source rate limiting
                    )
                    sources.append(source)
                elif isinstance(item, (dict, list)):
                    _extract_sources(item, category_hint)
        elif isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, (dict, list)) and key != 'metadata':
                    _extract_sources(value, key.replace('_', ' ').title())
    
    # Extract from all non-metadata sections
    for key, value in catalog.items():
        if key != 'metadata':
            _extract_sources(value, key.replace('_', ' ').title())
    
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
    parser.add_argument('--health-report', action='store_true',
                        help='Generate health report after fetching')
    parser.add_argument('--validate-source', help='Validate a feed URL before adding')
    parser.add_argument('--retry-disabled', action='store_true',
                        help='Retry disabled sources and re-enable if successful')
    parser.add_argument('--no-auto-disable', action='store_true',
                        help='Disable automatic source disabling on repeated failures')
    
    args = parser.parse_args()
    
    # Ensure state directory exists
    db_path = Path(args.db)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Handle validation mode
    if args.validate_source:
        from aggregator.health_monitor import FeedHealthMonitor
        monitor = FeedHealthMonitor(db_path)
        result = monitor.validate_feed(args.validate_source)
        print(json.dumps(result, indent=2))
        return 0 if result['valid'] else 1
    
    cache = FeedCache(db_path)
    
    if args.init:
        catalog_path = Path(args.catalog)
        if not catalog_path.exists():
            print(f"Catalog not found: {catalog_path}")
            return 1
        
        sources = load_sources_from_catalog(catalog_path)
        
        # Validate sources before adding if health_monitor available
        from aggregator.health_monitor import FeedHealthMonitor
        monitor = FeedHealthMonitor(db_path)
        
        valid_sources = []
        for source in sources:
            print(f"Validating {source.name}...", end=' ')
            validation = monitor.validate_feed(source.url)
            if validation['valid']:
                print("✅")
                valid_sources.append(source)
            else:
                print(f"❌ ({validation.get('error', 'Unknown error')})")
        
        for source in valid_sources:
            cache.save_source(source)
            print(f"Registered: {source.name} ({source.id})")
        print(f"\nTotal sources: {len(valid_sources)} (validated)")
        return 0
    
    # Initialize health monitor if available
    try:
        from aggregator.health_monitor import FeedHealthMonitor
        health_monitor = FeedHealthMonitor(db_path)
    except ImportError:
        health_monitor = None
    
    fetcher = FeedFetcher(cache, health_monitor=health_monitor, 
                          auto_disable=not args.no_auto_disable)
    
    # Handle retry-disabled mode
    if args.retry_disabled:
        disabled = cache.get_disabled_sources()
        if disabled:
            print(f"\n🔁 Retrying {len(disabled)} disabled source(s)...")
            for src in disabled:
                print(f"  - {src.id} ({src.name})")
            print()
        else:
            print("No disabled sources to retry.")
    
    results = fetcher.fetch_all(domain=args.domain, include_disabled=args.retry_disabled)
    
    total = sum(len(entries) for entries in results.values())
    print(f"\nTotal entries fetched: {total}")
    
    # Generate health report if requested
    if args.health_report and health_monitor:
        print("\n" + "=" * 60)
        print("📊 Health Report")
        print("=" * 60)
        report = health_monitor.generate_health_report(domain=args.domain)
        print(f"Healthy: {report['summary']['healthy']}")
        print(f"Degraded: {report['summary']['degraded']}")
        print(f"Unhealthy: {report['summary']['unhealthy']}")
        
        if report['problematic_feeds']:
            print("\nProblematic feeds:")
            for feed in report['problematic_feeds']:
                print(f"  - {feed['source_name']}: {feed['status']}")
    
    return 0


if __name__ == '__main__':
    exit(main())
