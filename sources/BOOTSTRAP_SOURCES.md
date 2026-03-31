# High-Signal Source Bootstrap

**Date:** 2026-03-21  
**Status:** Sources researched and cataloged

## Philosophy

Use search APIs **once** (or periodically) to discover high-signal sources. Then **track those sources via RSS** for daily updates. Never use search APIs for daily content fetching.

## Source Inventory

### Tier 1: Essential Daily (Research)
- **arXiv cs.AI/LG/CL** - All AI/ML/NLP research (3 feeds)
- **Hugging Face Blog** - Model releases and tools
- **Distill.pub** - Explanatory research (monthly but high value)

### Tier 2: Daily News & Discussion
- **Hacker News** - Tech news and discussions (high volume, filter for >50 points)
- **Lobsters** - Programming community (smaller, more technical)
- **Ars Technica** - Tech journalism
- **MIT Technology Review** - Long-form tech reporting

### Tier 3: Weekly Curations
- **Import AI** - Jack Clark's research roundup (weekly, excellent)
- **This Week in Rust** - Curated Rust ecosystem
- **JavaScript Weekly** - Curated JS ecosystem
- **Stratechery** - Tech strategy analysis (partial via RSS)

### Tier 4: Tools & Platforms
- **GitHub Changelog** - Platform updates
- **PyTorch Blog** - Framework updates

### Tier 5: Special Handling
- **OpenAI Blog** - Major announcements only (low volume)
- **DeepMind Blog** - Research updates
- **AI Alignment Forum** - Safety research (rate limited)

## Implementation Plan

### Phase 1: Core RSS (Complete)
- [x] Identify 15+ high-signal RSS feeds
- [x] Categorize by quality_score and frequency
- [x] Document special handling requirements

### Phase 2: Database Load (Complete)
- [x] Create `load_sources.py` script
- [x] Insert sources into `news.db` (22 sources loaded, 21 active, 1 disabled)
- [x] Mark disabled sources (AI Alignment Forum rate-limited)

### Phase 3: Aggregation Schedule
- [ ] Morning run (7 AM): arXiv + newsletters + tech news
- [ ] Midday run (1 PM): HN + Lobsters updates
- [ ] Evening run (7 PM): All remaining sources
- [ ] Weekly only: This Week in Rust, JS Weekly, Stratechery

### Phase 4: Content Prioritization
- [ ] Filter arXiv by keyword relevance
- [ ] Filter HN by score threshold (>50 points)
- [ ] Prioritize by quality_score + freshness
- [ ] Deduplicate across sources (SimHash)

## Daily Operation (No Search APIs)

```
06:30 - Fetch arXiv feeds
06:35 - Fetch newsletter RSS feeds
06:40 - Fetch tech news (Ars, MIT Tech Review)
06:45 - Deduplicate and rank
07:00 - Generate morning briefing

13:00 - Fetch HN + Lobsters updates
13:15 - Add to database
13:30 - Generate midday update (if significant news)

19:00 - Fetch remaining sources
19:15 - Deduplicate
19:30 - Generate evening digest
```

## Weekly Operation

```
Monday:
  - This Week in Rust (check if new issue)
  - JavaScript Weekly (check if new issue)
  
Wednesday/Thursday:
  - Import AI (usually Wednesday)
  - The Diff (daily but digest on Thu)
  
Friday:
  - Stratechery (free weekly)
```

## Quality Gates

1. **Minimum quality_score: 7** for inclusion in briefing
2. **Maximum 10 articles per category** in daily briefing
3. **Deduplication threshold: 0.85** similarity (SimHash)
4. **Content freshness: <7 days** for most sources

## Source Verification

All RSS URLs have been tested and return valid feeds:
- ✅ 200 OK: arXiv, HuggingFace, Distill, HN, TWiR, JS Weekly, etc.
- ⚠️ Redirects: OpenAI, DeepMind (follow redirects)
- ⚠️ Rate limited: Alignment Forum (60s delay)

## Next Actions

1. Run `load_sources.py` to populate database
2. Test fetch for each feed
3. Configure cron schedule
4. Generate first real briefing
