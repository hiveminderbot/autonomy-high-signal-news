# High-Signal News Lab TODO

## Phase 1: Source Discovery

### AI Domain
- [x] Identify top RSS feeds for AI research (arXiv, Papers with Code, etc.) → `sources/sources-ai.json`
- [x] Evaluate high-signal AI newsletters (Import AI, The Batch, etc.) → `sources/sources-ai.json`
- [x] Curate AI-focused Twitter/X accounts → `sources/sources-ai-twitter.json`
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
- [x] Research RSS aggregation tools (FreshRSS, Miniflux, etc.) → `research/rss-aggregation-tools.md`
- [x] Evaluate newsletter-to-RSS converters (Kill the Newsletter) → `research/rss-aggregation-tools.md`
- [ ] Test content extraction tools for newsletters
- [ ] Design source quality scoring system

## Phase 2: Aggregation Pipeline

- [x] Build RSS feed aggregator → `scripts/aggregator/feed_fetcher.py`
- [x] Implement newsletter ingestion → `scripts/aggregator/newsletter_ingester.py`
- [x] Create deduplication system → `scripts/aggregator/deduplicator.py`
- [x] Build content extraction pipeline → `scripts/aggregator/content_extractor.py`
- [x] Design storage schema for articles → `scripts/aggregator/storage.py`

## Phase 3: Summarization Engine

- [x] Research story clustering algorithms → `scripts/summarizer/story_clusterer.py`
- [x] Implement content summarization → `scripts/summarizer/content_summarizer.py`
- [x] Build entity extraction → `scripts/summarizer/entity_extractor.py`
- [x] Create relevance scoring → `scripts/summarizer/relevance_scorer.py`
- [x] Design cross-domain connection detection → `story_clusterer.find_cross_domain_clusters()`
- [x] Add tests for summarization modules (52 tests, all passing)
- [x] Integrate summarization into aggregation pipeline (daily_runner now uses pipeline_with_summarization)

## Phase 4: Briefing Generation

- [x] Design morning briefing format → `design/briefing-format-spec.md`
  - Five-minute read constraint specification
  - Visual priority indicators (🔥⭐📰📊)
  - Section structure (Header, Domain Sections, Key Themes, Footer)
  - Output format variants (Markdown, Plain text, HTML)
  - JSON schema for programmatic access
  - Quality checklist for publication
- [x] Create templates for output formats → `design/templates/`
  - Markdown template with Jinja2 syntax
  - Plain text template for Telegram/Email
- [x] Implement priority ranking → `scripts/summarizer/relevance_scorer.py`
- [x] Build output generators → `scripts/briefing/` module
  - BriefingGenerator: Core generation logic
  - MarkdownRenderer: Markdown output
  - HTMLRenderer: HTML output
  - TextRenderer: Plain text output
- [x] Create scheduling system → `scripts/scheduler/daily_briefing.py`
  - Cron-compatible daily runner
  - Full pipeline orchestration
  - Error handling and logging
- [x] Test end-to-end pipeline ✅ COMPLETED 2026-04-01
  - Integration test: 6/6 passed
  - Full test suite: 218/218 passed
  - Results: test-output/integration-test-20260401-*.json
