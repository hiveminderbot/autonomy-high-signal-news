# Feed Health Monitoring

This document describes the feed health monitoring system for the High-Signal News aggregation pipeline.

## Overview

The health monitoring system tracks the reliability of RSS feed sources and automatically handles problematic feeds. It provides:

- **Per-source health tracking**: Success/failure rates, response times, consecutive failures
- **Automatic degradation handling**: Feeds are marked as degraded after intermittent failures
- **Auto-disable unhealthy feeds**: Feeds are automatically disabled after 3 consecutive failures
- **Health reports**: Dashboard showing feed health across the system

## Components

### FeedHealthMonitor (`aggregator/health_monitor.py`)

The main monitoring class that:
- Tracks fetch success/failure per source
- Calculates health statistics over time windows
- Generates health reports
- Validates new feeds before adding to catalog

### FeedFetcher Integration (`aggregator/feed_fetcher.py`)

The fetcher now:
- Uses exponential backoff retry (3 retries: 1s, 2s, 4s delays)
- Sends proper User-Agent headers to avoid bot detection
- Reports fetch results to health monitor after each attempt
- Validates feeds during `--init` process

## Health Status Levels

| Status | Description | Action Taken |
|--------|-------------|--------------|
| 🟢 **healthy** | ≥80% success rate | None |
| 🟡 **degraded** | 50-80% success rate, or 1-2 consecutive failures | Log warning, monitor closely |
| 🔴 **unhealthy** | <50% success rate, or ≥3 consecutive failures | Auto-disable source |

## Usage

### View Health Report

```bash
cd labs/high-signal-news
scripts/run-with-nix-python.sh -m aggregator.health_monitor --db state/feeds.db
```

With JSON output:
```bash
scripts/run-with-nix-python.sh -m aggregator.health_monitor --db state/feeds.db --json
```

### Validate a New Feed

Before adding a feed to the catalog:

```bash
scripts/run-with-nix-python.sh scripts/aggregator/feed_fetcher.py --validate-source "https://example.com/feed.xml"
```

### Initialize with Validation

When adding sources from catalog, validate each one:

```bash
scripts/run-with-nix-python.sh scripts/aggregator/feed_fetcher.py --init --catalog sources/sources-ai.json
```

### Fetch with Health Report

Generate a health report after fetching:

```bash
scripts/run-with-nix-python.sh scripts/aggregator/feed_fetcher.py --health-report --domain ai
```

## Handling Cloudflare-Protected Feeds

Some RSS feeds are protected by Cloudflare or similar bot detection systems. These feeds return HTTP 403 errors or HTML instead of RSS.

### Identifying Cloudflare-Protected Feeds

The validation system will report:
```json
{
  "valid": false,
  "reachable": false,
  "error": "Access forbidden (403) - may be Cloudflare protected"
}
```

### Workarounds

#### 1. Use RSSHub (Recommended)

[RSSHub](https://rsshub.app) provides RSS feeds for many sites that don't have native feeds or block scrapers.

Example alternatives:
- Python Weekly (blocked): Use RSSHub's newsletter bridge
- Papers with Code (discontinued): Use arXiv RSS directly

#### 2. Alternative Feed Sources

| Original Feed | Status | Alternative |
|--------------|--------|-------------|
| Python Weekly | Cloudflare-blocked | Manual newsletter ingestion |
| Papers with Code | Returns HTML | arXiv cs.AI feed |
| Some subreddits | Rate-limited | Reddit's official RSS |

#### 3. Manual Ingestion

For newsletter-style content without RSS:

```python
# Use the newsletter ingester
from aggregator.newsletter_ingester import NewsletterIngester

ingester = NewsletterIngester()
ingester.ingest_from_email("/path/to/email.eml")
```

#### 4. Mark as Inactive in Catalog

If no workaround exists, mark the source as inactive:

```json
{
  "id": "python-weekly",
  "name": "Python Weekly",
  "url": "https://www.pythonweekly.com/",
  "active": false,
  "notes": "Cloudflare protected, no RSSHub alternative available"
}
```

## Database Schema

The health system uses these tables:

### feed_health_status
- `source_id`: Feed source identifier
- `consecutive_failures`: Count of consecutive failed fetches
- `is_healthy`: Boolean health flag
- `status`: 'healthy', 'degraded', or 'unhealthy'
- `last_status_change`: When status last changed

### fetch_log (existing)
- Records every fetch attempt with success/failure and timing

## Recommendations

1. **Monitor the health report weekly** to catch degrading feeds early
2. **Validate feeds before adding** to the catalog
3. **Use RSSHub alternatives** for Cloudflare-protected sites
4. **Keep fallback sources** - if one AI news feed fails, others should cover
5. **Review auto-disabled feeds monthly** - sites may fix their issues

## Troubleshooting

### Feed shows as degraded but works in browser

- The site may have bot detection. Check if it returns different content to curl:
  ```bash
  curl -A "Mozilla/5.0" https://example.com/feed.xml
  ```

### Feed returns HTML instead of RSS

- Verify the URL is correct (not the homepage)
- Check if the feed has moved (look for `<link rel="alternate">` in HTML)
- Consider using RSSHub

### High response times

- Some feeds are slow; this is normal for sources outside your region
- Consider the feed's geographic location when evaluating

## Integration with Pipeline

The health monitor integrates with the aggregation pipeline:

```python
from aggregator.feed_fetcher import FeedFetcher, FeedCache
from aggregator.health_monitor import FeedHealthMonitor

cache = FeedCache("state/feeds.db")
monitor = FeedHealthMonitor("state/feeds.db")
fetcher = FeedFetcher(cache, health_monitor=monitor)

# Fetches automatically update health status
results = fetcher.fetch_all()

# Generate report
report = monitor.generate_health_report()
```
