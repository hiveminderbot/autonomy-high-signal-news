---
title: RSS Aggregation Tools Research
date: 2026-03-28
lab: high-signal-news
status: completed
---

# RSS Aggregation Tools Research

## Executive Summary

This research evaluates three RSS aggregation solutions for potential integration with the high-signal-news lab:
1. **FreshRSS** - Feature-rich self-hosted RSS aggregator
2. **Miniflux** - Minimalist self-hosted RSS reader  
3. **Kill the Newsletter** - Newsletter-to-RSS conversion service

**Recommendation**: Continue with current custom Python aggregator. FreshRSS and Miniflux add operational complexity without significant benefits for our use case. Consider Kill the Newsletter as supplementary tool for specific newsletter sources.

---

## 1. FreshRSS

### Overview
FreshRSS is a self-hosted RSS feed aggregator with a web-based interface, written in PHP.

**Repository**: github.com/FreshRSS/FreshRSS
**License**: AGPL-3.0
**Language**: PHP (requires PHP 7.4+)

### Key Features
- Web-based RSS reader with responsive UI
- REST API for programmatic access (JSON, OPML)
- Multi-user support with authentication
- Mobile apps available (Android: News+, iOS: Fiery Feeds)
- Extension system for customization
- Import/export OPML
- Filters and search capabilities
- Statistics and monitoring

### Pros
| Aspect | Assessment |
|--------|------------|
| Feature Set | Rich feature set with web UI |
| API Access | Good REST API for integration |
| Maturity | Established project (2013+) |
| Community | Active development |

### Cons
| Aspect | Assessment |
|--------|------------|
| Complexity | Requires PHP + web server setup |
| Resource Usage | Moderate (PHP + MySQL/SQLite) |
| Integration | Would need HTTP API calls from Python |
| Maintenance | Another service to maintain |

### Deployment Options
- Docker (recommended): `freshrss/freshrss`
- Traditional: Apache/Nginx + PHP + MySQL/SQLite/PostgreSQL

### API Capabilities
```bash
# Example API endpoints
GET /api/v1/entries      # Fetch articles
GET /api/v1/feeds        # List feeds
POST /api/v1/entries     # Mark as read/unread
```

---

## 2. Miniflux

### Overview
Miniflux is a minimalist self-hosted RSS reader focused on simplicity and performance.

**Repository**: github.com/miniflux/v2
**License**: Apache-2.0
**Language**: Go (single binary deployment)

### Key Features
- Minimalist web interface (no JavaScript framework)
- Single Go binary deployment
- PostgreSQL database
- Fever API and Google Reader API compatible
- Content scraping (fetch full article text)
- Built-in full-text search
- Keyboard shortcuts
- No social features, no ads, no tracking

### Pros
| Aspect | Assessment |
|--------|------------|
| Simplicity | Single binary, minimal config |
| Resource Usage | Low (Go binary) |
| API Access | Fever/Google Reader API compatible |
| Maintenance | Easier than FreshRSS |

### Cons
| Aspect | Assessment |
|--------|------------|
| Feature Set | Minimal by design |
| Database | Requires PostgreSQL |
| Integration | Still requires HTTP API calls |
| Flexibility | Less extensible than FreshRSS |

### Deployment Options
- Docker: `miniflux/miniflux`
- Binary: Single static binary

### API Capabilities
- Fever API compatible (legacy but widely supported)
- Google Reader API compatible
- No native REST API

---

## 3. Kill the Newsletter

### Overview
Kill the Newsletter converts newsletter subscriptions into RSS feeds.

**Website**: kill-the-newsletter.com
**License**: N/A (hosted service or self-hostable)

### Key Features
- Creates email addresses that convert to RSS
- No signup required (ephemeral feeds)
- Simple web interface
- RSS/Atom/XML output
- Self-hostable via Docker

### Pros
| Aspect | Assessment |
|--------|------------|
| Use Case Fit | Solves newsletter-to-RSS conversion |
| Simplicity | Extremely simple |
| Integration | Just another RSS feed |
| No Maintenance | Use hosted version |

### Cons
| Aspect | Assessment |
|--------|------------|
| Scope | Single purpose tool |
| Reliability | Dependent on hosted service |
| Privacy | Email goes through third-party |

### Deployment Options
- Hosted: kill-the-newsletter.com (free)
- Self-hosted: Docker available

---

## Comparison Matrix

| Criteria | FreshRSS | Miniflux | Kill the Newsletter |
|----------|----------|----------|---------------------|
| **Deployment Complexity** | Medium (PHP+DB) | Low (Go binary) | Very Low |
| **Resource Usage** | Moderate | Low | Minimal |
| **API for Integration** | Good REST API | Fever API | N/A (RSS output) |
| **Feature Richness** | High | Low-Medium | Single purpose |
| **Maintenance Overhead** | Medium | Low | None (hosted) |
| **Newsletter Support** | Via email plugins | No | Core feature |
| **Python Integration** | HTTP API calls | HTTP API calls | Feed parser |
| **Our Use Case Fit** | Medium | Low | High |

---

## Current Architecture Assessment

The high-signal-news lab currently uses:
- `scripts/aggregator/feed_fetcher.py` - Custom RSS fetcher
- `scripts/aggregator/newsletter_ingester.py` - Email-based newsletter ingestion
- `scripts/aggregator/content_extractor.py` - Full-text extraction
- `scripts/aggregator/deduplicator.py` - SimHash deduplication
- `scripts/aggregator/storage.py` - SQLite storage

### Strengths of Current Approach
1. **Tight Integration**: Direct database writes, no HTTP API overhead
2. **Custom Logic**: SimHash deduplication tailored to our needs
3. **Rate Limiting**: Per-domain rate limits built-in
4. **Newsletter Support**: Already implemented via email forwarding
5. **Single Codebase**: No external service dependencies
6. **Test Coverage**: 218 tests covering all components

### Weaknesses
1. **Maintenance Burden**: Custom code requires maintenance
2. **Feature Gaps**: No web UI for manual feed management
3. **Mobile Access**: No mobile app for feed reading

---

## Recommendations

### Primary Recommendation: Continue with Custom Aggregator

**Rationale**:
- Current system is tested (218 tests passing) and operational
- Adding FreshRSS/Miniflux would introduce operational complexity
- API integration would add latency and failure modes
- No significant feature gaps that justify migration

### Secondary Recommendation: Adopt Kill the Newsletter

**Use Case**: Supplement current newsletter ingestion for sources that:
- Do not offer RSS feeds
- Have newsletters not covered by current email setup
- Need quick one-off RSS conversion

**Integration Path**:
```python
# Add to newsletter_ingester.py as alternative source
ktn_feeds = [
    "https://kill-the-newsletter.com/feeds/xyz.xml",
]
```

### Future Consideration: FreshRSS as Feed Manager

If manual feed curation becomes important:
1. Deploy FreshRSS for feed management UI
2. Use FreshRSS API as alternative feed source
3. Keep custom aggregator as primary ingestion path
4. Gradually migrate if benefits materialize

---

## Conclusion

The current custom Python aggregator is well-suited for the high-signal-news lab's needs. The operational simplicity and tight integration outweigh the benefits of adopting FreshRSS or Miniflux. Kill the Newsletter can be adopted as a supplementary tool for specific newsletter-to-RSS conversion needs.

---

## References

- FreshRSS: freshrss.github.io/FreshRSS/en/
- Miniflux: miniflux.app/docs/index.html
- Kill the Newsletter: kill-the-newsletter.com
- Current aggregator: `scripts/aggregator/`
