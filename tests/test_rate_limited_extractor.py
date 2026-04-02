#!/usr/bin/env python3
"""
Tests for the RateLimitedContentExtractor.

Run with: python -m pytest tests/test_rate_limited_extractor.py -v
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock

# Import the module under test
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from aggregator.rate_limited_extractor import (
    RateLimitedContentExtractor,
    RateLimitConfig,
    DomainMetrics,
    DEFAULT_DOMAIN_RATE_LIMITS,
    create_rate_limited_extractor,
)


class TestRateLimitConfig:
    """Test RateLimitConfig dataclass."""

    def test_default_values(self):
        config = RateLimitConfig()
        assert config.requests_per_second == 1.0
        assert config.max_retries == 3
        assert config.base_backoff_seconds == 1.0
        assert config.max_backoff_seconds == 60.0
        assert config.timeout_seconds == 10.0
        assert config.enabled is True

    def test_custom_values(self):
        config = RateLimitConfig(
            requests_per_second=0.5,
            max_retries=5,
            timeout_seconds=30.0,
        )
        assert config.requests_per_second == 0.5
        assert config.max_retries == 5
        assert config.timeout_seconds == 30.0


class TestDomainMetrics:
    """Test DomainMetrics dataclass."""

    def test_success_rate_calculation(self):
        metrics = DomainMetrics(domain="example.com", total_requests=10, successful_requests=8)
        assert metrics.success_rate == 80.0

    def test_success_rate_zero_requests(self):
        metrics = DomainMetrics(domain="example.com")
        assert metrics.success_rate == 0.0

    def test_average_latency_calculation(self):
        metrics = DomainMetrics(
            domain="example.com",
            total_requests=4,
            total_latency_ms=1000.0
        )
        assert metrics.average_latency_ms == 250.0

    def test_to_dict(self):
        metrics = DomainMetrics(
            domain="example.com",
            total_requests=10,
            successful_requests=8,
            failed_requests=2,
        )
        data = metrics.to_dict()
        assert data['domain'] == "example.com"
        assert data['total_requests'] == 10
        assert data['success_rate'] == 80.0


class TestRateLimitedContentExtractor:
    """Test RateLimitedContentExtractor class."""

    def test_init(self):
        extractor = RateLimitedContentExtractor()
        assert extractor.request_timeout == 30
        assert extractor.min_fetch_interval == 1.0
        assert extractor.min_success_rate == 50.0
        assert extractor.enable_metrics is True

    def test_get_domain(self):
        extractor = RateLimitedContentExtractor()
        assert extractor._get_domain("https://example.com/article") == "example.com"
        assert extractor._get_domain("https://www.example.com/article") == "example.com"
        assert extractor._get_domain("https://blog.example.com/article") == "blog.example.com"

    def test_get_rate_limit_config_exact_match(self):
        extractor = RateLimitedContentExtractor()
        config = extractor._get_rate_limit_config("huggingface.co")
        assert config.requests_per_second == 0.2

    def test_get_rate_limit_config_parent_domain(self):
        extractor = RateLimitedContentExtractor()
        # blog.huggingface.co should match huggingface.co config
        config = extractor._get_rate_limit_config("blog.huggingface.co")
        assert config.requests_per_second == 0.2

    def test_get_rate_limit_config_default(self):
        extractor = RateLimitedContentExtractor()
        config = extractor._get_rate_limit_config("unknown-domain.com")
        assert config.requests_per_second == 1.0  # Default value

    def test_should_skip_domain_not_enough_data(self):
        extractor = RateLimitedContentExtractor(min_success_rate=50.0)
        # No metrics yet
        assert extractor._should_skip_domain("example.com") is False

        # Less than 3 requests
        extractor._domain_metrics["example.com"] = DomainMetrics(
            domain="example.com",
            total_requests=2,
            successful_requests=0,
        )
        assert extractor._should_skip_domain("example.com") is False

    def test_should_skip_domain_low_success_rate(self):
        extractor = RateLimitedContentExtractor(min_success_rate=50.0)
        extractor._domain_metrics["example.com"] = DomainMetrics(
            domain="example.com",
            total_requests=10,
            successful_requests=3,  # 30% success rate
        )
        assert extractor._should_skip_domain("example.com") is True

    def test_should_not_skip_domain_good_success_rate(self):
        extractor = RateLimitedContentExtractor(min_success_rate=50.0)
        extractor._domain_metrics["example.com"] = DomainMetrics(
            domain="example.com",
            total_requests=10,
            successful_requests=8,  # 80% success rate
        )
        assert extractor._should_skip_domain("example.com") is False

    def test_update_metrics_success(self):
        extractor = RateLimitedContentExtractor()
        extractor._update_metrics("example.com", success=True, latency_ms=100.0)

        metrics = extractor._domain_metrics["example.com"]
        assert metrics.total_requests == 1
        assert metrics.successful_requests == 1
        assert metrics.failed_requests == 0
        assert metrics.total_latency_ms == 100.0

    def test_update_metrics_failure(self):
        extractor = RateLimitedContentExtractor()
        extractor._update_metrics("example.com", success=False, latency_ms=500.0, error="429 Too Many Requests")

        metrics = extractor._domain_metrics["example.com"]
        assert metrics.total_requests == 1
        assert metrics.successful_requests == 0
        assert metrics.failed_requests == 1
        assert metrics.rate_limited_count == 1

    def test_get_metrics(self):
        extractor = RateLimitedContentExtractor()
        extractor._update_metrics("example.com", success=True, latency_ms=100.0)

        metrics = extractor.get_metrics("example.com")
        assert metrics['domain'] == "example.com"
        assert metrics['total_requests'] == 1

    def test_get_metrics_summary(self):
        extractor = RateLimitedContentExtractor()
        extractor._update_metrics("example.com", success=True, latency_ms=100.0)
        extractor._update_metrics("example.org", success=False, latency_ms=200.0, error="Timeout")

        summary = extractor.get_metrics_summary()
        assert summary['total_domains'] == 2
        assert summary['total_requests'] == 2
        assert summary['overall_success_rate'] == 50.0


class TestRateLimitingBehavior:
    """Test actual rate limiting behavior."""

    def test_rate_limit_enforced(self):
        extractor = RateLimitedContentExtractor()
        extractor.domain_rate_limits["test.com"] = RateLimitConfig(
            requests_per_second=2.0,  # 0.5s between requests
        )

        # First request
        start = time.time()
        extractor._apply_rate_limit("test.com")
        extractor._domain_last_request["test.com"] = time.time()

        # Second request should be delayed
        extractor._apply_rate_limit("test.com")
        elapsed = time.time() - start

        # Should have waited at least 0.5s
        assert elapsed >= 0.4  # Allow some tolerance

    def test_rate_limit_disabled_domain(self):
        extractor = RateLimitedContentExtractor()
        extractor.domain_rate_limits["test.com"] = RateLimitConfig(enabled=False)

        start = time.time()
        extractor._apply_rate_limit("test.com")
        extractor._apply_rate_limit("test.com")
        elapsed = time.time() - start

        # Should not have waited
        assert elapsed < 0.1


class TestDefaultRateLimits:
    """Test default rate limit configurations."""

    def test_huggingface_rate_limit(self):
        config = DEFAULT_DOMAIN_RATE_LIMITS['huggingface.co']
        assert config.requests_per_second == 0.2  # 1 per 5 seconds
        assert config.max_retries == 2
        assert config.base_backoff_seconds == 5.0

    def test_medium_rate_limit(self):
        config = DEFAULT_DOMAIN_RATE_LIMITS['medium.com']
        assert config.requests_per_second == 0.5
        assert config.timeout_seconds == 10.0


class TestFactoryFunction:
    """Test create_rate_limited_extractor factory function."""

    def test_create_extractor(self):
        extractor = create_rate_limited_extractor(min_success_rate=60.0)
        assert isinstance(extractor, RateLimitedContentExtractor)
        assert extractor.min_success_rate == 60.0
        assert extractor.enable_metrics is True

    def test_default_domains_configured(self):
        extractor = create_rate_limited_extractor()
        assert 'huggingface.co' in extractor.domain_rate_limits
        assert 'medium.com' in extractor.domain_rate_limits


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
