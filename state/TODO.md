# High-Signal News Lab TODO

## Phase 1: Source Discovery

### AI Domain
- [x] Identify top RSS feeds for AI research (arXiv, Papers with Code, etc.) → `sources/sources-ai.json`
- [x] Evaluate high-signal AI newsletters (Import AI, The Batch, etc.) → `sources/sources-ai.json`
- [ ] Curate AI-focused Twitter/X accounts
- [x] Find AI-related GitHub trending repositories → `sources/sources-ai.json`
- [x] Document inclusion criteria for AI sources → `design/inclusion-criteria.md`

### Software Development Domain
- [x] Identify language-specific news sources (Python, JavaScript, Go, Rust) → `sources/sources-dev.json`
- [x] Find framework release trackers (React, Django, etc.) → `sources/sources-dev.json`
- [x] Evaluate dev blogs and newsletters → `sources/sources-dev.json`
- [x] Curate high-signal Hacker News filters → `sources/sources-dev.json`
- [x] Document inclusion criteria for dev sources → `design/inclusion-criteria.md`

### Investment Domain
- [x] Identify public market AI/tech news sources → `sources/sources-investment.json`
- [x] Find VC funding round trackers → `sources/sources-investment.json`
- [x] Evaluate regulatory news sources → `sources/sources-investment.json`
- [x] Curate investment-focused newsletters → `sources/sources-investment.json`
- [x] Document inclusion criteria for investment sources → included in sources-investment.json metadata

### Cross-Domain
- [ ] Research RSS aggregation tools (FreshRSS, Miniflux, etc.)
- [ ] Evaluate newsletter-to-RSS converters (Kill the Newsletter)
- [ ] Test content extraction tools for newsletters
- [ ] Design source quality scoring system

## Phase 2: Aggregation Pipeline

- [x] Build RSS feed aggregator → `scripts/aggregator/feed_fetcher.py`
- [x] Implement newsletter ingestion → `scripts/aggregator/newsletter_ingester.py`
- [x] Create deduplication system → `scripts/aggregator/deduplicator.py`
- [x] Build content extraction pipeline → `scripts/aggregator/content_extractor.py`
- [x] Design storage schema for articles → `scripts/aggregator/storage.py`

## Phase 3: Summarization Engine

- [ ] Research story clustering algorithms
- [ ] Implement content summarization
- [ ] Build entity extraction
- [ ] Create relevance scoring
- [ ] Design cross-domain connection detection

## Phase 4: Briefing Generation

- [ ] Design morning briefing format
- [ ] Implement priority ranking
- [ ] Build output generators (Markdown, Telegram, Email)
- [ ] Create scheduling system
- [ ] Test end-to-end pipeline
