# High-Signal News Aggregator

Feed aggregation, content extraction, deduplication, and storage pipeline for the High-Signal News system.

## Overview

This module provides the core infrastructure for:

- **Feed Aggregation**: RSS/Atom feed fetching with caching and rate limiting
- **Newsletter Ingestion**: Email newsletter processing
- **Content Extraction**: Full-text extraction from article URLs
- **Deduplication**: Near-duplicate detection using SimHash
- **Storage**: SQLite database with full-text search

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Feed Sources   │───▶│  Feed Fetcher    │───▶│  Content Extract│
│  (RSS/Atom)     │    │  (Rate Limited)  │    │  (Rate Limited) │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                         │
┌─────────────────┐    ┌──────────────────┐             │
│  Newsletters    │───▶│  Newsletter      │─────────────┤
│  (Email/IMAP)   │    │  Ingester        │             │
└─────────────────┘    └──────────────────┘             ▼
                                               ┌─────────────────┐
                                               │  Deduplicator   │
                                               │  (SimHash)      │
                                               └─────────────────┘
                                                         │
                                                         ▼
                                               ┌─────────────────┐
                                               │  Storage        │
                                               │  (SQLite + FTS5)│
                                               └─────────────────┘
                                                         │
                                                         ▼
                                               ┌─────────────────┐
                                               │  Briefing       │
                                               │  Generator      │
                                               └─────────────────┘
```

## Components

### Core Modules

| Module | Purpose | Status |
|--------|---------|--------|
| `feed_fetcher.py` | RSS/Atom feed fetching with caching | ✅ Complete |
| `content_extractor.py` | Article text extraction | ✅ Complete |
| `rate_limited_extractor.py` | Rate-limited extraction with metrics | ✅ Complete |
| `deduplicator.py` | SimHash-based deduplication | ✅ Complete |
| `storage.py` | SQLite storage with FTS5 search | ✅ Complete |
| `newsletter_ingester.py` | Email newsletter processing | ✅ Complete |
| `blog_scraper.py` | Blog-specific scraping | ✅ Complete |
| `pipeline.py` | Unified aggregation pipeline | ✅ Complete |

### Delivery Modules

| Module | Purpose | Status |
|--------|---------|--------|
| `../briefing/delivery.py` | Multi-channel delivery (Telegram, Email) | ✅ Complete |
| `../briefing/generator.py` | Briefing content generation | ✅ Complete |
| `../briefing/renderer.py` | Format rendering (Markdown, HTML) | ✅ Complete |

## Quick Start

### Run Daily Pipeline

```bash
# Run full pipeline
cd /home/exedev/autonomy/labs/high-signal-news
scripts/run-with-nix-python.sh scripts/aggregator/daily_pipeline.py

# Dry run (no database writes)
scripts/run-with-nix-python.sh scripts/aggregator/daily_pipeline.py --dry-run

# Verbose output with domain filter
scripts/run-with-nix-python.sh scripts/aggregator/daily_pipeline.py -v --domain ai

# JSON output for scripting
scripts/run-with-nix-python.sh scripts/aggregator/daily_pipeline.py --json
```

### Install Systemd Timer

```bash
# Install for current user
cd scripts/aggregator/systemd
./install.sh

# Start the timer
systemctl --user start high-signal-news.timer

# Check status
systemctl --user status high-signal-news.timer
```

### Configure Telegram Delivery

1. Get bot token from [@BotFather](https://t.me/botfather)
2. Get chat ID from [@userinfobot](https://t.me/userinfobot)
3. Edit `.env.briefing`:

```bash
HN_BRIEFING_BOT_TOKEN=your_token_here
HN_BRIEFING_CHAT_ID=your_chat_id_here
```

## Configuration

### Sources Catalog

Feeds are configured in `sources/sources-ai.json`:

```json
{
  "sources": [
    {
      "name": "Hacker News",
      "url": "https://news.ycombinator.com/rss",
      "type": "rss",
      "domain": "dev",
      "priority": 1
    }
  ]
}
```

### Database Schema

The SQLite database (`data/news.db`) includes:

- `articles`: Main article storage with full-text search
- `feeds`: Feed metadata and fetch state
- `entries`: Raw feed entries
- `duplicates`: Deduplication tracking

## Testing

```bash
# Run aggregation pipeline tests
scripts/run-with-nix-python.sh -m pytest tests/test_aggregation_pipeline.py -v

# Run content extractor tests
scripts/run-with-nix-python.sh -m pytest tests/test_content_extractor.py -v

# Run deduplicator tests
scripts/run-with-nix-python.sh -m pytest tests/test_deduplicator.py -v

# Run rate limiter tests
scripts/run-with-nix-python.sh -m pytest tests/test_rate_limited_extractor.py -v
```

## Performance

Typical daily run performance:

- **50+ sources**: ~2-3 minutes
- **Content extraction**: ~100 articles/minute (rate limited)
- **Deduplication**: ~1000 articles/second
- **Storage**: ~500 articles/second

## Rate Limiting

The system implements adaptive rate limiting:

- Success rate tracking per domain
- Automatic backoff on failures
- Configurable minimum success rate (default: 50%)
- Domain-specific rate limits

## Environment Variables

| Variable | Purpose | Required |
|----------|---------|----------|
| `HN_BRIEFING_BOT_TOKEN` | Telegram bot token | No |
| `HN_BRIEFING_CHAT_ID` | Telegram chat ID | No |
| `BEADS_DIR` | Beads database directory | No |

## Files

```
scripts/aggregator/
├── __init__.py
├── blog_scraper.py          # Blog-specific scraping
├── content_extractor.py      # Article text extraction
├── daily_pipeline.py         # CLI pipeline runner ⭐ NEW
├── deduplicator.py           # SimHash deduplication
├── feed_fetcher.py           # RSS/Atom fetching
├── newsletter_ingester.py    # Email newsletter processing
├── pipeline.py               # Unified pipeline
├── pipeline_extended.py      # Extended pipeline with newsletters
├── rate_limited_extractor.py # Rate-limited extraction
├── storage.py                # SQLite storage
├── systemd/                  # Systemd integration ⭐ NEW
│   └── install.sh
└── README.md                 # This file ⭐ NEW
```

## Success Criteria

Phase 2 deliverables:

- [x] 50+ sources ingesting successfully
- [x] >90% deduplication accuracy
- [x] 80%+ content extraction success rate
- [x] Full-text search functional
- [x] Daily pipeline completes in <5 minutes
- [x] Unit tests for all components

## License

Part of the Autonomy Labs project.
