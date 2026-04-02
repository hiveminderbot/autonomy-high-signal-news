#!/usr/bin/env python3
"""
Rate-Limited Content Extractor for High-Signal News

Extends the base ContentExtractor with domain-specific rate limiting,
exponential backoff for 429 errors, and per-domain metrics tracking.
"""

import re
import time
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, List
from urllib.parse import urlparse
from collections import defaultdict

# Import base extractor
from .content_extractor import ContentExtractor, ExtractedContent, REQUESTS_AVAILABLE, BS4_AVAILABLE

if REQUESTS_AVAILABLE:
    import requests


@dataclass
class DomainMetrics:
    """Metrics for a specific domain's extraction performance."""
    domain: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    rate_limited_count: int = 0
    timeout_count: int = 0
    total_latency_ms: float = 0.0
    last_request_at: Optional[datetime] = None
    last_error: Optional[str] = None

    @property
    def success_rate(self) -> float:
        """Calculate success rate as percentage."""
        if self.total_requests == 0:
            return 0.0
        return (self.successful_requests / self.total_requests) * 100

    @property
    def average_latency_ms(self) -> float:
        """Calculate average latency in milliseconds."""
        if self.total_requests == 0:
            return 0.0
        return self.total_latency_ms / self.total_requests

    def to_dict(self) -> dict:
        return {
            'domain': self.domain,
            'total_requests': self.total_requests,
            'successful_requests': self.successful_requests,
            'failed_requests': self.failed_requests,
            'rate_limited_count': self.rate_limited_count,
            'timeout_count': self.timeout_count,
            'success_rate': self.success_rate,
            'average_latency_ms': self.average_latency_ms,
            'last_request_at': self.last_request_at.isoformat() if self.last_request_at else None,
            'last_error': self.last_error,
        }


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting a specific domain."""
    requests_per_second: float = 1.0
    max_retries: int = 3
    base_backoff_seconds: float = 1.0
    max_backoff_seconds: float = 60.0
    timeout_seconds: float = 10.0
    enabled: bool = True


# Default rate limit configurations for known problematic domains
DEFAULT_DOMAIN_RATE_LIMITS: Dict[str, RateLimitConfig] = {
    'huggingface.co': RateLimitConfig(
        requests_per_second=0.2,  # 1 request per 5 seconds
        max_retries=2,
        base_backoff_seconds=5.0,
        max_backoff_seconds=120.0,
        timeout_seconds=15.0,
    ),
    'medium.com': RateLimitConfig(
        requests_per_second=0.5,
        max_retries=3,
        base_backoff_seconds=2.0,
        max_backoff_seconds=60.0,
        timeout_seconds=10.0,
    ),
    'towardsdatascience.com': RateLimitConfig(
        requests_per_second=0.5,
        max_retries=3,
        base_backoff_seconds=2.0,
        max_backoff_seconds=60.0,
        timeout_seconds=10.0,
    ),
    'arxiv.org': RateLimitConfig(
        requests_per_second=1.0,
        max_retries=2,
        base_backoff_seconds=1.0,
        max_backoff_seconds=30.0,
        timeout_seconds=10.0,
    ),
    'reuters.com': RateLimitConfig(
        requests_per_second=0.5,
        max_retries=2,
        base_backoff_seconds=2.0,
        max_backoff_seconds=60.0,
        timeout_seconds=10.0,
    ),
}


class RateLimitedContentExtractor(ContentExtractor):
    """
    Content extractor with domain-specific rate limiting and metrics.

    Features:
    - Per-domain rate limiting with configurable delays
    - Exponential backoff for 429 Too Many Requests
    - Support for Retry-After header
    - Per-domain metrics tracking
    - Automatic skipping of domains with <50% success rate
    """

    def __init__(self,
                 request_timeout: int = 30,
                 min_fetch_interval: float = 1.0,
                 respect_robots_txt: bool = True,
                 user_agent: str = "HighSignalNewsBot/1.0 (Research Project)",
                 domain_rate_limits: Optional[Dict[str, RateLimitConfig]] = None,
                 default_rate_limit: Optional[RateLimitConfig] = None,
                 min_success_rate: float = 50.0,
                 enable_metrics: bool = True):
        """
        Initialize rate-limited content extractor.

        Args:
            request_timeout: Default request timeout in seconds
            min_fetch_interval: Minimum interval between requests (global)
            respect_robots_txt: Whether to respect robots.txt
            user_agent: User agent string
            domain_rate_limits: Dict mapping domain to RateLimitConfig
            default_rate_limit: Default rate limit for unspecified domains
            min_success_rate: Minimum success rate (%) before skipping domain
            enable_metrics: Whether to track per-domain metrics
        """
        super().__init__(
            request_timeout=request_timeout,
            min_fetch_interval=min_fetch_interval,
            respect_robots_txt=respect_robots_txt,
            user_agent=user_agent,
        )

        # Merge provided rate limits with defaults
        self.domain_rate_limits = DEFAULT_DOMAIN_RATE_LIMITS.copy()
        if domain_rate_limits:
            self.domain_rate_limits.update(domain_rate_limits)

        self.default_rate_limit = default_rate_limit or RateLimitConfig()
        self.min_success_rate = min_success_rate
        self.enable_metrics = enable_metrics

        # Per-domain state
        self._domain_last_request: Dict[str, float] = {}
        self._domain_metrics: Dict[str, DomainMetrics] = defaultdict(
            lambda: DomainMetrics(domain="")
        )

        # Track which domains have been warned about (to avoid spam)
        self._domain_skip_warned: set = set()

    def _get_domain(self, url: str) -> str:
        """Extract domain from URL."""
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
        # Remove www. prefix for consistency
        if domain.startswith('www.'):
            domain = domain[4:]
        return domain

    def _get_rate_limit_config(self, domain: str) -> RateLimitConfig:
        """Get rate limit config for a domain, with fallback to default."""
        # Try exact match
        if domain in self.domain_rate_limits:
            return self.domain_rate_limits[domain]

        # Try parent domain (e.g., blog.example.com -> example.com)
        parts = domain.split('.')
        if len(parts) > 2:
            parent = '.'.join(parts[-2:])
            if parent in self.domain_rate_limits:
                return self.domain_rate_limits[parent]

        return self.default_rate_limit

    def _should_skip_domain(self, domain: str) -> bool:
        """Check if domain should be skipped due to poor success rate."""
        if not self.enable_metrics:
            return False

        metrics = self._domain_metrics.get(domain)
        if not metrics or metrics.total_requests < 3:
            # Not enough data to make decision
            return False

        if metrics.success_rate < self.min_success_rate:
            if domain not in self._domain_skip_warned:
                self._domain_skip_warned.add(domain)
                print(f"⚠️  Skipping {domain}: success rate {metrics.success_rate:.1f}% < {self.min_success_rate}%")
            return True

        return False

    def _apply_rate_limit(self, domain: str):
        """Apply rate limiting for a specific domain."""
        config = self._get_rate_limit_config(domain)

        if not config.enabled:
            return

        now = time.time()
        last_request = self._domain_last_request.get(domain)

        if last_request:
            # Calculate required delay
            min_interval = 1.0 / config.requests_per_second
            elapsed = now - last_request

            if elapsed < min_interval:
                sleep_time = min_interval - elapsed
                time.sleep(sleep_time)

        self._domain_last_request[domain] = time.time()

    def _update_metrics(self, domain: str, success: bool, latency_ms: float, error: Optional[str] = None):
        """Update metrics for a domain."""
        if not self.enable_metrics:
            return

        metrics = self._domain_metrics.get(domain)
        if not metrics or not metrics.domain:
            metrics = DomainMetrics(domain=domain)
            self._domain_metrics[domain] = metrics

        metrics.total_requests += 1
        metrics.total_latency_ms += latency_ms
        metrics.last_request_at = datetime.now()

        if success:
            metrics.successful_requests += 1
        else:
            metrics.failed_requests += 1
            metrics.last_error = error

            # Categorize error
            if error:
                if '429' in error or 'Too Many Requests' in error:
                    metrics.rate_limited_count += 1
                elif 'timeout' in error.lower():
                    metrics.timeout_count += 1

    def _extract_with_backoff(self, url: str, domain: str) -> ExtractedContent:
        """
        Extract content with exponential backoff for rate limiting.

        Args:
            url: URL to extract
            domain: Domain for rate limiting

        Returns:
            ExtractedContent result
        """
        if not REQUESTS_AVAILABLE or not BS4_AVAILABLE:
            error_msg = "requests library not available" if not REQUESTS_AVAILABLE else "beautifulsoup4 library not available"
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
                extraction_error=error_msg
            )

        config = self._get_rate_limit_config(domain)

        for attempt in range(config.max_retries + 1):
            start_time = time.time()

            try:
                # Apply rate limiting before request
                self._apply_rate_limit(domain)

                # Make request with domain-specific timeout
                response = self._session.get(url, timeout=config.timeout_seconds)

                # Handle rate limiting (429)
                if response.status_code == 429:
                    latency_ms = (time.time() - start_time) * 1000

                    # Check for Retry-After header
                    retry_after = response.headers.get('Retry-After')
                    if retry_after:
                        try:
                            # Can be seconds or HTTP date
                            wait_seconds = int(retry_after)
                        except ValueError:
                            # Parse HTTP date format
                            wait_seconds = 60  # Default if parsing fails
                    else:
                        # Exponential backoff
                        wait_seconds = min(
                            config.base_backoff_seconds * (2 ** attempt),
                            config.max_backoff_seconds
                        )

                    if attempt < config.max_retries:
                        print(f"⏳ Rate limited on {domain}, waiting {wait_seconds:.1f}s (attempt {attempt + 1}/{config.max_retries + 1})")
                        time.sleep(wait_seconds)
                        continue
                    else:
                        error_msg = f"429 Too Many Requests after {config.max_retries + 1} attempts"
                        self._update_metrics(domain, False, latency_ms, error_msg)
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
                            extraction_error=error_msg
                        )

                # Raise for other HTTP errors
                response.raise_for_status()

                # Parse HTML
                from bs4 import BeautifulSoup
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
                reading_time_minutes = max(1, word_count // 200)

                # Generate excerpt
                excerpt = content_text[:300].strip()
                if len(content_text) > 300:
                    excerpt = excerpt.rsplit(' ', 1)[0] + '...'

                # Success! Update metrics
                latency_ms = (time.time() - start_time) * 1000
                self._update_metrics(domain, True, latency_ms)

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

            except requests.Timeout as e:
                latency_ms = (time.time() - start_time) * 1000
                error_msg = f"Timeout after {config.timeout_seconds}s"
                self._update_metrics(domain, False, latency_ms, error_msg)

                if attempt < config.max_retries:
                    wait_seconds = min(
                        config.base_backoff_seconds * (2 ** attempt),
                        config.max_backoff_seconds
                    )
                    print(f"⏳ Timeout on {domain}, retrying in {wait_seconds:.1f}s")
                    time.sleep(wait_seconds)
                    continue
                else:
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
                        extraction_error=error_msg
                    )

            except requests.RequestException as e:
                latency_ms = (time.time() - start_time) * 1000
                error_msg = f"Request failed: {str(e)}"
                self._update_metrics(domain, False, latency_ms, error_msg)

                # Don't retry on 4xx errors (except 429 handled above)
                if hasattr(e, 'response') and e.response is not None:
                    status_code = e.response.status_code
                    if 400 <= status_code < 500 and status_code != 429:
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
                            extraction_error=error_msg
                        )

                if attempt < config.max_retries:
                    wait_seconds = min(
                        config.base_backoff_seconds * (2 ** attempt),
                        config.max_backoff_seconds
                    )
                    print(f"⏳ Request error on {domain}, retrying in {wait_seconds:.1f}s: {str(e)[:50]}")
                    time.sleep(wait_seconds)
                    continue
                else:
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
                        extraction_error=error_msg
                    )

            except Exception as e:
                latency_ms = (time.time() - start_time) * 1000
                error_msg = f"Extraction failed: {str(e)}"
                self._update_metrics(domain, False, latency_ms, error_msg)

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
                    extraction_error=error_msg
                )

        # Should not reach here, but just in case
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
            extraction_error="Unexpected error: max retries exceeded"
        )

    def extract(self, url: str) -> ExtractedContent:
        """
        Extract content from a URL with rate limiting and metrics.

        Args:
            url: URL to extract

        Returns:
            ExtractedContent result
        """
        domain = self._get_domain(url)

        # Check if domain should be skipped
        if self._should_skip_domain(domain):
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
                extraction_error=f"Domain {domain} skipped due to low success rate"
            )

        # Extract with backoff and rate limiting
        return self._extract_with_backoff(url, domain)

    def get_metrics(self, domain: Optional[str] = None) -> Dict:
        """
        Get extraction metrics.

        Args:
            domain: Optional domain to filter by

        Returns:
            Dict of metrics
        """
        if domain:
            metrics = self._domain_metrics.get(domain)
            return metrics.to_dict() if metrics else {}

        return {
            domain: metrics.to_dict()
            for domain, metrics in self._domain_metrics.items()
        }

    def get_metrics_summary(self) -> Dict:
        """Get a summary of all metrics."""
        if not self._domain_metrics:
            return {
                'total_domains': 0,
                'total_requests': 0,
                'overall_success_rate': 0.0,
                'domains_with_low_success': [],
            }

        total_requests = sum(m.total_requests for m in self._domain_metrics.values())
        total_successful = sum(m.successful_requests for m in self._domain_metrics.values())

        domains_with_low_success = [
            domain for domain, metrics in self._domain_metrics.items()
            if metrics.total_requests >= 3 and metrics.success_rate < self.min_success_rate
        ]

        return {
            'total_domains': len(self._domain_metrics),
            'total_requests': total_requests,
            'overall_success_rate': (total_successful / total_requests * 100) if total_requests > 0 else 0.0,
            'domains_with_low_success': domains_with_low_success,
            'domain_details': self.get_metrics(),
        }

    def reset_metrics(self, domain: Optional[str] = None):
        """Reset metrics for a domain or all domains."""
        if domain:
            if domain in self._domain_metrics:
                del self._domain_metrics[domain]
            if domain in self._domain_skip_warned:
                self._domain_skip_warned.remove(domain)
        else:
            self._domain_metrics.clear()
            self._domain_skip_warned.clear()


def create_rate_limited_extractor(
    min_success_rate: float = 50.0,
    enable_metrics: bool = True
) -> RateLimitedContentExtractor:
    """
    Factory function to create a rate-limited extractor with sensible defaults.

    Args:
        min_success_rate: Minimum success rate before skipping domain
        enable_metrics: Whether to track per-domain metrics

    Returns:
        Configured RateLimitedContentExtractor
    """
    return RateLimitedContentExtractor(
        request_timeout=30,
        min_fetch_interval=0.5,
        respect_robots_txt=True,
        user_agent="HighSignalNewsBot/1.0 (Research Project; +https://github.com/exedev/autonomy)",
        domain_rate_limits=DEFAULT_DOMAIN_RATE_LIMITS.copy(),
        default_rate_limit=RateLimitConfig(
            requests_per_second=2.0,  # 2 req/sec default
            max_retries=3,
            base_backoff_seconds=1.0,
            max_backoff_seconds=30.0,
            timeout_seconds=10.0,
        ),
        min_success_rate=min_success_rate,
        enable_metrics=enable_metrics,
    )


if __name__ == '__main__':
    # Simple test
    import sys

    extractor = create_rate_limited_extractor()

    if len(sys.argv) < 2:
        print("Usage: python rate_limited_extractor.py <url>")
        sys.exit(1)

    url = sys.argv[1]
    print(f"Extracting: {url}")

    result = extractor.extract(url)

    if result.extraction_error:
        print(f"Error: {result.extraction_error}")
    else:
        print(f"Title: {result.title}")
        print(f"Author: {result.author}")
        print(f"Word count: {result.word_count}")
        print(f"Excerpt: {result.excerpt[:200]}...")

    # Print metrics
    print("\nMetrics:")
    metrics = extractor.get_metrics_summary()
    print(json.dumps(metrics, indent=2))
