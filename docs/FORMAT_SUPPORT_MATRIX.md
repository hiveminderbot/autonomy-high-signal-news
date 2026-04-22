# Source Format Support Matrix

This document tracks the supported source formats and their implementation status in the High-Signal News aggregation pipeline.

## Overview

| Format | Status | Implementation | File |
|--------|--------|----------------|------|
| RSS/Atom | ✅ Complete | `feed_fetcher.py` | `scripts/aggregator/feed_fetcher.py` |
| Newsletter (RSS) | ✅ Complete | `newsletter_ingester.py` | `scripts/aggregator/newsletter_ingester.py` |
| Blog (HTML scrape) | ✅ Complete | `blog_scraper.py` | `scripts/aggregator/blog_scraper.py` |
| GitHub Trending | ✅ Complete | `blog_scraper.py` | `scripts/aggregator/blog_scraper.py` |
| Content Extraction | ✅ Complete | `content_extractor.py` | `scripts/aggregator/content_extractor.py` |

## Source Catalogs

### 1. RSS Feeds (`sources/sources-ai.json`, `sources/sources-dev.json`)

Standard RSS/Atom feeds that work with `feed_fetcher.py`.

**Working Sources (Validated):**
- arXiv cs.AI, cs.LG, cs.CL
- OpenAI Blog
- Google AI Blog
- DeepMind Blog
- Anthropic Research
- AI Alignment Forum
- Microsoft Research AI
- JavaScript Weekly
- Node Weekly
- Go Weekly
- This Week in Rust
- Django News
- React Newsletter
- GitHub Changelog
- Hacker News (via hnrss.org)

**Broken/Blocked:**
- Papers with Code - Returns HTML instead of RSS
- Python Weekly - Cloudflare protection
- Towards Data Science - Medium restrictions

### 2. Newsletter Catalog (`sources/newsletter_catalog.json`)

Newsletter sources using RSS feeds (primarily Substack, Buttondown).

**Implemented (16 sources):**
| Source | Provider | Domain | Status | Notes |
|--------|----------|--------|--------|-------|
| Stratechery | substack_rss | technology | ✅ Working | 20 entries fetched |
| Benedict Evans | buttondown_rss | technology | ⚠️ Not tested | - |
| Import AI | substack_rss | ai | ✅ Working | 20 entries fetched |
| The Batch | substack_rss | ai | ✅ Working | URL fixed (thebatch.substack.com) |
| AI Supremacy | substack_rss | ai | ⚠️ Not tested | - |
| TLDR Newsletter | substack_rss | software_development | ✅ Working | URL fixed (tldr.substack.com) |
| ByteByteGo | substack_rss | software_development | ⚠️ Not tested | - |
| Lenny's Newsletter | substack_rss | product | ⚠️ Not tested | - |
| First Round Review | substack_rss | startup | ⚠️ Not tested | - |
| Paul Graham Essays | substack_rss | startup | ⚠️ Not tested | - |
| AlphaSignal | substack_rss | ai | ✅ Working | URL fixed (alphasignal.substack.com) |
| The Sequence | substack_rss | ai | ✅ Working | 20 entries fetched |
| JavaScript Weekly | substack_rss | software_development | ✅ Working | 4 entries fetched |
| Django News | substack_rss | software_development | ✅ Working | URL fixed (django-news.substack.com) |
| This Week in Rust | substack_rss | software_development | ✅ Working | 4 entries fetched |
| SemiAnalysis | substack_rss | technology | ⚠️ Empty | Feed returned 0 entries |
| The Diff | substack_rss | investment | ✅ Working | 5 entries fetched |

### 3. Blog Scraper Catalog (`sources/blog_scraper_catalog.json`)

Sources requiring HTML scraping (no RSS or RSS is broken).

**Implemented (14 sources):**

#### Blog Scraping (`blog_scrape` type)
| Source | Domain | Status | Entries | Notes |
|--------|--------|--------|---------|-------|
| Hugging Face Papers | ai | ✅ Working | ~20/day | Community-upvoted ML papers |
| Python Insider | software_development | ✅ Working | ~7/month | Official Python release announcements |
| Node.js Blog | software_development | ✅ Working | ~6/week | Official Node.js releases |
| Go Blog | software_development | ✅ Working | ~20 | Go language blog with author/date |
| React Blog | software_development | ❌ Disabled | N/A | JS-rendered, needs headless browser |
| GitHub Changelog | software_development | ⚠️ Not tested | - | GitHub platform updates |

#### Newsletter Web (`newsletter_web` type)
| Source | Domain | Scraping Strategy |
|--------|--------|-------------------|
| AlphaSignal (fallback) | ai | Archive page scraping |
| The Sequence (fallback) | ai | Substack archive scraping |
| SemiAnalysis (fallback) | technology | Web archive scraping |
| The Diff (fallback) | investment | Web archive scraping |

#### GitHub Trending (`github_trending` type)
| Source | Domain | Scraping Strategy |
|--------|--------|-------------------|
| GitHub Trending Python | software_development | Trending page scraping |
| GitHub Trending JavaScript | software_development | Trending page scraping |
| GitHub Trending Go | software_development | Trending page scraping |
| GitHub Trending Rust | software_development | Trending page scraping |

## Usage

### Fetching RSS Feeds

```bash
# Initialize from catalog
scripts/run-with-nix-python.sh scripts/aggregator/feed_fetcher.py --init --catalog sources/sources-ai.json

# Fetch all feeds
scripts/run-with-nix-python.sh scripts/aggregator/feed_fetcher.py

# Fetch specific domain
scripts/run-with-nix-python.sh scripts/aggregator/feed_fetcher.py --domain ai
```

### Ingesting Newsletters

```bash
# Load newsletter sources
scripts/run-with-nix-python.sh -c "
from aggregator.newsletter_ingester import *
from pathlib import Path

catalog = Path('sources/newsletter_catalog.json')
sources = load_newsletter_sources_from_catalog(catalog)
print(f'Loaded {len(sources)} newsletter sources')
"
```

### Pipeline with Newsletter Ingestion

```bash
# Run full pipeline with newsletter ingestion enabled
scripts/run-with-nix-python.sh scripts/aggregator/pipeline.py \
  --catalog sources/sources-ai.json \
  --db data/aggregator.db \
  --blog-catalog sources/blog_scraper_catalog.json \
  --enable-blog-scraping \
  --enable-newsletter-ingestion \
  --verbose
```

### Scraping Blogs

```bash
# Scrape all blog sources
scripts/run-with-nix-python.sh scripts/aggregator/blog_scraper.py --catalog sources/blog_scraper_catalog.json

# Scrape specific source with content extraction
scripts/run-with-nix-python.sh scripts/aggregator/blog_scraper.py --source python-insider --extract-content

# Scrape by domain
scripts/run-with-nix-python.sh scripts/aggregator/blog_scraper.py --domain ai
```

## Adding New Sources

### 1. RSS Feed Sources

Add to `sources/sources-{domain}.json`:

```json
{
  "name": "Source Name",
  "url": "https://example.com/feed.xml",
  "type": "rss",
  "frequency": "daily",
  "focus": "Description",
  "quality_score": 8,
  "notes": "Any special notes"
}
```

### 2. Newsletter Sources

Add to `sources/newsletter_catalog.json`:

```json
{
  "id": "source-id",
  "name": "Source Name",
  "provider": "substack_rss",
  "source_url": "https://source.substack.com/feed",
  "category": "Category",
  "domain": "domain",
  "signal_quality": "High",
  "active": true,
  "config": {
    "author": "Author Name",
    "notes": "Description"
  }
}
```

### 3. Blog/Scraping Sources

Add to `sources/blog_scraper_catalog.json`:

```json
{
  "id": "source-id",
  "name": "Source Name",
  "url": "https://example.com",
  "type": "blog_scrape",
  "category": "Category",
  "domain": "domain",
  "signal_quality": "High",
  "active": true,
  "scrape_config": {
    "list_url": "https://example.com/blog",
    "article_selector": "article",
    "title_selector": "h2",
    "link_selector": "h2 a",
    "author_selector": ".author",
    "date_selector": "time",
    "base_url": "https://example.com"
  }
}
```

## Source Count Summary

| Category | Count | Via RSS | Via Scrape |
|----------|-------|---------|------------|
| AI Research | 15 | 12 | 3 |
| Software Development | 18 | 14 | 4 |
| Technology | 4 | 4 | 0 |
| Investment | 2 | 2 | 0 |
| **Total** | **39** | **32** | **7** |

## Pipeline Integration

The sources feed into the aggregation pipeline in this order:

1. **RSS Fetcher** (`feed_fetcher.py`) - Fetches RSS/Atom feeds
2. **Newsletter Ingester** (`newsletter_ingester.py`) - Handles newsletter RSS feeds
3. **Blog Scraper** (`blog_scraper.py`) - Scrapes non-RSS sources
4. **Content Extractor** (`content_extractor.py`) - Deep content extraction
5. **Deduplicator** (`deduplicator.py`) - Near-duplicate detection
6. **Storage** (`storage.py`) - SQLite with FTS5

## Pipeline Integration Test Results

**Test Date:** 2026-03-21

### Blog Scraper Integration
- ✅ Pipeline successfully scrapes blog sources alongside RSS feeds
- ✅ Deduplication working (no duplicates across RSS and scraped content)
- ✅ Content extraction enabled for blog entries
- ✅ Database storage verified (20 entries from Hugging Face Papers)

### Newsletter Ingestion Integration
- ✅ Pipeline integrates newsletter ingestion via `--enable-newsletter-ingestion` flag
- ✅ 6 of 10 tested newsletter sources working (Import AI, The Sequence, JavaScript Weekly, This Week in Rust, The Diff, Stratechery)
- ✅ Deduplication working across newsletters and other sources
- ✅ Newsletter entries converted to FeedEntry format for unified storage

### Tested Sources
| Source | Type | Entries | Status |
|--------|------|---------|--------|
| Hugging Face Papers | blog_scrape | 20 | ✅ Working |
| Python Insider | blog_scrape | 7 | ✅ Working |
| Go Blog | blog_scrape | 20 | ✅ Working |
| Node.js Blog | blog_scrape | 6 | ✅ Working |
| Import AI | newsletter_rss | 20 | ✅ Working |
| The Sequence | newsletter_rss | 20 | ✅ Working |
| JavaScript Weekly | newsletter_rss | 4 | ✅ Working |
| This Week in Rust | newsletter_rss | 4 | ✅ Working |
| The Diff | newsletter_rss | 5 | ✅ Working |
| Stratechery | newsletter_rss | 20 | ✅ Working |

### Command (Full Pipeline)
```bash
scripts/run-with-nix-python.sh scripts/aggregator/pipeline.py \
  --catalog sources/sources-ai.json \
  --db data/aggregator.db \
  --blog-catalog sources/blog_scraper_catalog.json \
  --enable-blog-scraping \
  --enable-newsletter-ingestion \
  --verbose
```

## Last Updated

2026-03-21 (Newsletter ingestion integration complete)
