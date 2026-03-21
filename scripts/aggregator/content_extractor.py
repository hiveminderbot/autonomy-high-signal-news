#!/usr/bin/env python3
"""
Content Extractor for High-Signal News

Fetches and extracts article content from URLs with HTML→text conversion,
metadata extraction, and paywall detection.
"""

import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
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
class ExtractedContent:
    """Represents extracted article content."""
    url: str
    title: Optional[str]
    author: Optional[str]
    published_at: Optional[datetime]
    content_text: str
    content_html: Optional[str]
    excerpt: str
    word_count: int
    reading_time_minutes: int
    extracted_at: datetime
    is_paywalled: bool = False
    extraction_error: Optional[str] = None


class ContentExtractor:
    """Extract article content from URLs with respectful fetching."""
    
    # Common paywall indicators in HTML
    PAYWALL_INDICATORS = [
        'paywall',
        'subscription',
        'subscribe',
        'premium-content',
        ' gated-content',
        'article__paywall',
        'data-paywall',
        'wall-message',
    ]
    
    # Content-heavy selectors to prioritize
    CONTENT_SELECTORS = [
        'article',
        '[role="main"]',
        'main',
        '.post-content',
        '.article-content',
        '.entry-content',
        '.content',
        '#content',
        '.post-body',
        '.article-body',
    ]
    
    # Elements to remove
    NOISE_SELECTORS = [
        'nav', 'header', 'footer', 'aside', 'sidebar',
        '.nav', '.navigation', '.menu',
        '.advertisement', '.ad', '.ads',
        '.social-share', '.share-buttons',
        '.comments', '#comments',
        '.related-articles', '.recommended',
        'script', 'style', 'noscript', 'iframe',
        '.newsletter-signup', '.subscribe',
    ]
    
    def __init__(self, 
                 request_timeout: int = 30,
                 min_fetch_interval: float = 1.0,
                 respect_robots_txt: bool = True,
                 user_agent: str = "HighSignalNewsBot/1.0 (Research Project)"):
        self.request_timeout = request_timeout
        self.min_fetch_interval = min_fetch_interval
        self.respect_robots_txt = respect_robots_txt
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
    
    def _detect_paywall(self, soup: 'BeautifulSoup') -> bool:
        """Detect if content is behind a paywall."""
        html_str = str(soup).lower()
        
        for indicator in self.PAYWALL_INDICATORS:
            if indicator in html_str:
                return True
        
        # Check for common paywall elements
        paywall_selectors = [
            '[class*="paywall"]',
            '[class*="subscription"]',
            '[id*="paywall"]',
            '.regwall',
            '.metered-content',
        ]
        
        for selector in paywall_selectors:
            if soup.select(selector):
                return True
        
        return False
    
    def _extract_title(self, soup: 'BeautifulSoup') -> Optional[str]:
        """Extract article title from HTML."""
        # Try common title selectors
        title_selectors = [
            'h1.article-title',
            'h1.entry-title',
            'h1.post-title',
            'h1[class*="title"]',
            'article h1',
            '.content h1',
            'h1',
        ]
        
        for selector in title_selectors:
            elem = soup.select_one(selector)
            if elem:
                return elem.get_text(strip=True)
        
        # Fallback to meta title
        meta_title = soup.find('meta', property='og:title') or soup.find('meta', attrs={'name': 'title'})
        if meta_title:
            return meta_title.get('content', '').strip()
        
        # Fallback to page title
        if soup.title:
            return soup.title.get_text(strip=True)
        
        return None
    
    def _extract_author(self, soup: 'BeautifulSoup') -> Optional[str]:
        """Extract article author from HTML."""
        author_selectors = [
            '[rel="author"]',
            '.author',
            '.byline',
            '[class*="author"]',
            'meta[name="author"]',
            'meta[property="article:author"]',
        ]
        
        for selector in author_selectors:
            elem = soup.select_one(selector)
            if elem:
                if elem.name == 'meta':
                    return elem.get('content', '').strip()
                return elem.get_text(strip=True)
        
        return None
    
    def _extract_published_date(self, soup: 'BeautifulSoup') -> Optional[datetime]:
        """Extract published date from HTML."""
        date_selectors = [
            'time[datetime]',
            'meta[property="article:published_time"]',
            'meta[name="publish-date"]',
            '[class*="published"]',
            '[class*="date"]',
        ]
        
        for selector in date_selectors:
            elem = soup.select_one(selector)
            if elem:
                if elem.name == 'meta':
                    date_str = elem.get('content', '')
                else:
                    date_str = elem.get('datetime', '') or elem.get_text(strip=True)
                
                if date_str:
                    try:
                        # Try common date formats
                        for fmt in [
                            '%Y-%m-%dT%H:%M:%S',
                            '%Y-%m-%dT%H:%M:%S%z',
                            '%Y-%m-%d %H:%M:%S',
                            '%Y-%m-%d',
                            '%B %d, %Y',
                            '%b %d, %Y',
                        ]:
                            try:
                                return datetime.strptime(date_str[:19], fmt)
                            except ValueError:
                                continue
                    except Exception:
                        pass
        
        return None
    
    def _extract_content(self, soup: 'BeautifulSoup') -> tuple[str, str]:
        """Extract article content text and HTML."""
        # Remove noise elements
        for selector in self.NOISE_SELECTORS:
            for elem in soup.select(selector):
                elem.decompose()
        
        # Try to find main content
        content_elem = None
        for selector in self.CONTENT_SELECTORS:
            content_elem = soup.select_one(selector)
            if content_elem:
                break
        
        if not content_elem:
            # Fallback to body
            content_elem = soup.find('body') or soup
        
        # Get HTML content
        content_html = str(content_elem)
        
        # Get text content
        # Replace common block elements with newlines for readability
        for tag in content_elem.find_all(['p', 'br', 'h1', 'h2', 'h3', 'h4', 'li']):
            tag.append('\n')
        
        content_text = content_elem.get_text(separator=' ', strip=True)
        
        # Clean up whitespace
        content_text = re.sub(r'\n\s*\n', '\n\n', content_text)
        content_text = re.sub(r' +', ' ', content_text)
        content_text = content_text.strip()
        
        return content_text, content_html
    
    def extract(self, url: str) -> ExtractedContent:
        """Extract content from a URL."""
        if not REQUESTS_AVAILABLE:
            return ExtractedContent(
                url=url,
                title=None,
                author=None,
                published_at=None,
                content_text="",
                content_html=None,
                excerpt="",
                word_count=0,
                reading_time_minutes=0,
                extracted_at=datetime.now(),
                extraction_error="requests library not available"
            )
        
        if not BS4_AVAILABLE:
            return ExtractedContent(
                url=url,
                title=None,
                author=None,
                published_at=None,
                content_text="",
                content_html=None,
                excerpt="",
                word_count=0,
                reading_time_minutes=0,
                extracted_at=datetime.now(),
                extraction_error="beautifulsoup4 library not available"
            )
        
        self._rate_limit()
        
        try:
            response = self._session.get(url, timeout=self.request_timeout)
            response.raise_for_status()
            
            # Parse HTML
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Detect paywall
            is_paywalled = self._detect_paywall(soup)
            
            # Extract components
            title = self._extract_title(soup)
            author = self._extract_author(soup)
            published_at = self._extract_published_date(soup)
            content_text, content_html = self._extract_content(soup)
            
            # Calculate metrics
            word_count = len(content_text.split())
            reading_time_minutes = max(1, word_count // 200)  # ~200 WPM reading speed
            
            # Generate excerpt (first ~300 chars)
            excerpt = content_text[:300].strip()
            if len(content_text) > 300:
                excerpt = excerpt.rsplit(' ', 1)[0] + '...'
            
            return ExtractedContent(
                url=url,
                title=title,
                author=author,
                published_at=published_at,
                content_text=content_text,
                content_html=content_html,
                excerpt=excerpt,
                word_count=word_count,
                reading_time_minutes=reading_time_minutes,
                extracted_at=datetime.now(),
                is_paywalled=is_paywalled
            )
            
        except requests.RequestException as e:
            return ExtractedContent(
                url=url,
                title=None,
                author=None,
                published_at=None,
                content_text="",
                content_html=None,
                excerpt="",
                word_count=0,
                reading_time_minutes=0,
                extracted_at=datetime.now(),
                extraction_error=f"Request failed: {str(e)}"
            )
        except Exception as e:
            return ExtractedContent(
                url=url,
                title=None,
                author=None,
                published_at=None,
                content_text="",
                content_html=None,
                excerpt="",
                word_count=0,
                reading_time_minutes=0,
                extracted_at=datetime.now(),
                extraction_error=f"Extraction failed: {str(e)}"
            )
    
    def extract_batch(self, urls: list[str], progress_callback=None) -> list[ExtractedContent]:
        """Extract content from multiple URLs."""
        results = []
        for i, url in enumerate(urls):
            if progress_callback:
                progress_callback(i + 1, len(urls), url)
            result = self.extract(url)
            results.append(result)
        return results


def main():
    """CLI entry point for testing."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Extract content from URLs')
    parser.add_argument('url', help='URL to extract content from')
    parser.add_argument('--output', '-o', choices=['text', 'json', 'excerpt'], default='excerpt',
                        help='Output format')
    
    args = parser.parse_args()
    
    extractor = ContentExtractor()
    result = extractor.extract(args.url)
    
    if result.extraction_error:
        print(f"Error: {result.extraction_error}", file=sys.stderr)
        return 1
    
    if args.output == 'json':
        import json
        output = {
            'url': result.url,
            'title': result.title,
            'author': result.author,
            'published_at': result.published_at.isoformat() if result.published_at else None,
            'word_count': result.word_count,
            'reading_time_minutes': result.reading_time_minutes,
            'is_paywalled': result.is_paywalled,
            'excerpt': result.excerpt,
        }
        print(json.dumps(output, indent=2))
    elif args.output == 'text':
        print(f"Title: {result.title or 'N/A'}")
        print(f"Author: {result.author or 'N/A'}")
        print(f"Word count: {result.word_count}")
        print(f"Reading time: {result.reading_time_minutes} min")
        print(f"Paywalled: {result.is_paywalled}")
        print("-" * 50)
        print(result.content_text)
    else:  # excerpt
        print(f"Title: {result.title or 'N/A'}")
        print(f"Excerpt: {result.excerpt}")
        print(f"Word count: {result.word_count}")
        print(f"Paywalled: {result.is_paywalled}")
    
    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main())
