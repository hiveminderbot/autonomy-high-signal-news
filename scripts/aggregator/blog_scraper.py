#!/usr/bin/env python3
"""
Blog Scraper for High-Signal News

Fetches and scrapes blog content from sources that don't have RSS feeds
or where RSS is broken. Uses content_extractor for deep article extraction.
"""

import json
import hashlib
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, List
from urllib.parse import urljoin, urlparse

# Optional dependencies with graceful fallback
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False


@dataclass
class BlogSource:
    """Configuration for a blog source."""
    id: str
    name: str
    url: str
    type: str  # blog_scrape, newsletter_web, github_trending
    category: str
    domain: str
    signal_quality: str
    active: bool = True
    scrape_config: Optional[dict] = None
    notes: Optional[str] = None


@dataclass
class BlogEntry:
    """Represents a scraped blog entry."""
    id: str
    title: str
    url: str
    source_id: str
    published_at: Optional[datetime]
    author: Optional[str]
    summary: Optional[str]
    content: Optional[str]
    scraped_at: datetime
    metadata: Optional[dict] = None


class BlogScraper:
    """Scrape blog and newsletter content from web pages."""
    
    def __init__(self, 
                 request_timeout: int = 30,
                 min_fetch_interval: float = 1.0,
                 user_agent: str = "HighSignalNewsBot/1.0 (Research Project)"):
        self.request_timeout = request_timeout
        self.min_fetch_interval = min_fetch_interval
        self.user_agent = user_agent
        self._last_fetch_time: Optional[float] = None
        self._session: Optional[object] = None
        
        if REQUESTS_AVAILABLE:
            self._session = requests.Session()
            self._session.headers.update({
                'User-Agent': self.user_agent,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
            })
    
    def _rate_limit(self):
        """Enforce minimum interval between requests."""
        if self._last_fetch_time:
            elapsed = time.time() - self._last_fetch_time
            if elapsed < self.min_fetch_interval:
                time.sleep(self.min_fetch_interval - elapsed)
        self._last_fetch_time = time.time()
    
    def _fetch_page(self, url: str) -> Optional[str]:
        """Fetch page content with rate limiting."""
        if not REQUESTS_AVAILABLE:
            raise RuntimeError("requests library not available")
        
        self._rate_limit()
        
        try:
            response = self._session.get(url, timeout=self.request_timeout)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            raise RuntimeError(f"Failed to fetch {url}: {e}")
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse date string into datetime."""
        if not date_str:
            return None
        
        # Common date formats
        formats = [
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%dT%H:%M:%S%z',
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d',
            '%B %d, %Y',
            '%b %d, %Y',
            '%d %B %Y',
            '%d %b %Y',
            '%m/%d/%Y',
            '%d/%m/%Y',
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip()[:19], fmt)
            except ValueError:
                continue
        
        return None
    
    def scrape_blog_list(self, source: BlogSource) -> List[BlogEntry]:
        """
        Scrape article list from a blog source.
        
        Args:
            source: BlogSource configuration with scrape_config
            
        Returns:
            List of BlogEntry objects
        """
        if not BS4_AVAILABLE:
            raise RuntimeError("beautifulsoup4 library not available")
        
        config = source.scrape_config or {}
        list_url = config.get('list_url', source.url)
        
        # Fetch the list page
        html = self._fetch_page(list_url)
        soup = BeautifulSoup(html, 'html.parser')
        
        entries = []
        article_selector = config.get('article_selector', 'article')
        title_selector = config.get('title_selector', 'h2, h3')
        link_selector = config.get('link_selector', 'a')
        author_selector = config.get('author_selector')
        date_selector = config.get('date_selector')
        base_url = config.get('base_url', '')
        
        # Find all article elements
        articles = soup.select(article_selector)
        
        for idx, article in enumerate(articles[:20]):  # Limit to 20 most recent
            try:
                # Extract title
                title_elem = article.select_one(title_selector)
                if not title_elem:
                    continue
                title = title_elem.get_text(strip=True)
                
                # Extract link
                link_elem = article.select_one(link_selector)
                if not link_elem:
                    continue
                
                href = link_elem.get('href', '')
                if not href:
                    continue
                
                # Build full URL
                if href.startswith('http'):
                    article_url = href
                elif href.startswith('/'):
                    article_url = base_url + href
                else:
                    article_url = urljoin(list_url, href)
                
                # Extract author
                author = None
                if author_selector:
                    author_elem = article.select_one(author_selector)
                    if author_elem:
                        author = author_elem.get_text(strip=True)
                
                # Extract date
                published_at = None
                if date_selector:
                    date_elem = article.select_one(date_selector)
                    if date_elem:
                        date_str = date_elem.get('datetime') or date_elem.get_text(strip=True)
                        published_at = self._parse_date(date_str)
                
                # Generate unique ID
                entry_id = hashlib.md5(f"{source.id}:{article_url}".encode()).hexdigest()[:16]
                
                entry = BlogEntry(
                    id=entry_id,
                    title=title[:200],
                    url=article_url,
                    source_id=source.id,
                    published_at=published_at,
                    author=author,
                    summary=None,
                    content=None,
                    scraped_at=datetime.now()
                )
                entries.append(entry)
                
            except Exception as e:
                # Log error but continue with other articles
                print(f"  Warning: Failed to parse article {idx}: {e}")
                continue
        
        return entries
    
    def scrape_with_content_extractor(self, source: BlogSource) -> List[BlogEntry]:
        """
        Scrape blog entries and extract full content using ContentExtractor.
        
        Args:
            source: BlogSource configuration
            
        Returns:
            List of BlogEntry objects with full content
        """
        from aggregator.content_extractor import ContentExtractor
        
        # First get the list of articles
        entries = self.scrape_blog_list(source)
        
        # Then extract full content for each
        extractor = ContentExtractor(
            request_timeout=self.request_timeout,
            min_fetch_interval=self.min_fetch_interval,
            user_agent=self.user_agent
        )
        
        enriched_entries = []
        for entry in entries:
            try:
                # Extract full content
                content = extractor.extract(entry.url)
                
                if content.extraction_error:
                    print(f"  Warning: Content extraction failed for {entry.url}: {content.extraction_error}")
                
                # Update entry with extracted content
                enriched_entry = BlogEntry(
                    id=entry.id,
                    title=content.title or entry.title,
                    url=entry.url,
                    source_id=entry.source_id,
                    published_at=content.published_at or entry.published_at,
                    author=content.author or entry.author,
                    summary=content.excerpt,
                    content=content.content_text,
                    scraped_at=entry.scraped_at,
                    metadata={
                        'word_count': content.word_count,
                        'reading_time_minutes': content.reading_time_minutes,
                        'is_paywalled': content.is_paywalled
                    }
                )
                enriched_entries.append(enriched_entry)
                
            except Exception as e:
                # Keep the original entry if content extraction fails
                print(f"  Warning: Content extraction failed for {entry.url}: {e}")
                enriched_entries.append(entry)
        
        return enriched_entries
    
    def scrape_github_trending(self, source: BlogSource) -> List[BlogEntry]:
        """
        Scrape GitHub trending repositories.
        
        Args:
            source: BlogSource configuration for GitHub trending
            
        Returns:
            List of BlogEntry objects representing trending repos
        """
        if not BS4_AVAILABLE:
            raise RuntimeError("beautifulsoup4 library not available")
        
        config = source.scrape_config or {}
        list_url = config.get('list_url', source.url)
        
        # Fetch the trending page
        html = self._fetch_page(list_url)
        soup = BeautifulSoup(html, 'html.parser')
        
        entries = []
        article_selector = config.get('article_selector', 'article.Box-row')
        title_selector = config.get('title_selector', 'h2 a')
        description_selector = config.get('description_selector', 'p')
        stars_selector = config.get('stars_selector', '[href$="/stargazers"]')
        
        # Find all repository elements
        repos = soup.select(article_selector)
        
        for idx, repo in enumerate(repos[:10]):  # Top 10 trending
            try:
                # Extract repo name
                title_elem = repo.select_one(title_selector)
                if not title_elem:
                    continue
                
                repo_name = title_elem.get_text(strip=True).replace('\n', '').replace(' ', '')
                
                # Extract link
                href = title_elem.get('href', '')
                if not href:
                    continue
                
                repo_url = f"https://github.com{href}" if href.startswith('/') else href
                
                # Extract description
                description = None
                if description_selector:
                    desc_elem = repo.select_one(description_selector)
                    if desc_elem:
                        description = desc_elem.get_text(strip=True)
                
                # Extract stars
                stars = None
                if stars_selector:
                    stars_elem = repo.select_one(stars_selector)
                    if stars_elem:
                        stars = stars_elem.get_text(strip=True)
                
                # Generate unique ID
                entry_id = hashlib.md5(f"{source.id}:{repo_name}".encode()).hexdigest()[:16]
                
                entry = BlogEntry(
                    id=entry_id,
                    title=f"Trending: {repo_name}",
                    url=repo_url,
                    source_id=source.id,
                    published_at=datetime.now(),
                    author=None,
                    summary=description,
                    content=None,
                    scraped_at=datetime.now(),
                    metadata={
                        'stars': stars,
                        'repo_name': repo_name
                    }
                )
                entries.append(entry)
                
            except Exception as e:
                print(f"  Warning: Failed to parse repo {idx}: {e}")
                continue
        
        return entries
    
    def scrape_source(self, source: BlogSource, extract_content: bool = False) -> List[BlogEntry]:
        """
        Scrape a source based on its type.
        
        Args:
            source: BlogSource configuration
            extract_content: Whether to extract full article content
            
        Returns:
            List of BlogEntry objects
        """
        if source.type == 'github_trending':
            return self.scrape_github_trending(source)
        elif extract_content:
            return self.scrape_with_content_extractor(source)
        else:
            return self.scrape_blog_list(source)


def load_blog_sources_from_catalog(catalog_path) -> List[BlogSource]:
    """Load blog sources from a catalog JSON file."""
    if isinstance(catalog_path, str):
        catalog_path = Path(catalog_path)
    if not catalog_path.exists():
        return []
    
    with open(catalog_path) as f:
        data = json.load(f)
    
    sources = []
    
    # Load regular blog sources
    for item in data.get('sources', []):
        sources.append(BlogSource(
            id=item['id'],
            name=item['name'],
            url=item['url'],
            type=item['type'],
            category=item.get('category', 'General'),
            domain=item.get('domain', 'general'),
            signal_quality=item.get('signal_quality', 'Medium'),
            active=item.get('active', True),
            scrape_config=item.get('scrape_config'),
            notes=item.get('notes')
        ))
    
    # Load GitHub trending sources
    for item in data.get('github_trending', []):
        sources.append(BlogSource(
            id=item['id'],
            name=item['name'],
            url=item['url'],
            type=item['type'],
            category=item.get('category', 'Trending'),
            domain=item.get('domain', 'software_development'),
            signal_quality=item.get('signal_quality', 'Medium'),
            active=item.get('active', True),
            scrape_config=item.get('scrape_config'),
            notes=item.get('notes')
        ))
    
    return sources


def main():
    """CLI entry point for testing."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Scrape blog sources')
    parser.add_argument('--catalog', default='sources/blog_scraper_catalog.json',
                        help='Path to blog scraper catalog')
    parser.add_argument('--source', help='Specific source ID to scrape')
    parser.add_argument('--domain', help='Filter by domain')
    parser.add_argument('--extract-content', action='store_true',
                        help='Extract full article content')
    parser.add_argument('--output', '-o', help='Output JSON file')
    parser.add_argument('--limit', type=int, default=10,
                        help='Limit entries per source')
    
    args = parser.parse_args()
    
    # Load sources
    catalog_path = Path(args.catalog)
    sources = load_blog_sources_from_catalog(catalog_path)
    
    if args.domain:
        sources = [s for s in sources if s.domain == args.domain]
    
    if args.source:
        sources = [s for s in sources if s.id == args.source]
    
    if not sources:
        print("No sources found matching criteria")
        return 1
    
    # Scrape sources
    scraper = BlogScraper()
    all_entries = []
    
    for source in sources:
        if not source.active:
            continue
        
        print(f"Scraping {source.name} ({source.id})...")
        try:
            entries = scraper.scrape_source(source, extract_content=args.extract_content)
            print(f"  -> {len(entries)} entries")
            
            for entry in entries[:args.limit]:
                all_entries.append({
                    'id': entry.id,
                    'title': entry.title,
                    'url': entry.url,
                    'source_id': entry.source_id,
                    'published_at': entry.published_at.isoformat() if entry.published_at else None,
                    'author': entry.author,
                    'summary': entry.summary,
                    'metadata': entry.metadata
                })
                
        except Exception as e:
            print(f"  -> ERROR: {e}")
    
    # Output results
    output = {
        'scraped_at': datetime.now().isoformat(),
        'source_count': len(sources),
        'entry_count': len(all_entries),
        'entries': all_entries
    }
    
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(output, f, indent=2)
        print(f"\nResults saved to {args.output}")
    else:
        print(json.dumps(output, indent=2))
    
    return 0


if __name__ == '__main__':
    exit(main())
