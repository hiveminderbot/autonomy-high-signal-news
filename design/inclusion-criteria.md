# Source Inclusion Criteria

**Version:** 1.0.0  
**Created:** 2026-03-21  
**Applies to:** High-Signal News aggregation pipeline

## Overview

This document defines the criteria for including sources in the high-signal news aggregation pipeline. The goal is to maximize signal-to-noise ratio while maintaining sufficient coverage across AI and software development domains.

## Quality Dimensions

### 1. Publication Regularity

| Score | Criteria |
|-------|----------|
| 10 | Daily or multiple times per day |
| 8 | Weekly with consistent schedule |
| 6 | Bi-weekly or monthly with reliable schedule |
| 4 | Irregular but high-quality when published |
| 0 | Sporadic or unreliable |

### 2. Content Depth

| Score | Criteria |
|-------|----------|
| 10 | Original research, primary sources, or deep technical analysis |
| 8 | Curated summaries with editorial commentary and context |
| 6 | Aggregated news with light curation |
| 4 | Brief mentions or announcements only |
| 0 | Reposts without added value |

### 3. Author/Editor Expertise

| Score | Criteria |
|-------|----------|
| 10 | Recognized expert with track record in domain |
| 8 | Organization with dedicated editorial staff |
| 6 | Practicing developer/researcher sharing experience |
| 4 | Community-driven with quality controls |
| 0 | Unknown or unverified authorship |

### 4. Community Validation

| Score | Criteria |
|-------|----------|
| 10 | Frequently cited by other high-quality sources |
| 8 | Strong engagement from domain practitioners |
| 6 | Moderate community following |
| 4 | Niche but dedicated audience |
| 0 | No visible community engagement |

### 5. Signal-to-Noise Ratio

| Score | Criteria |
|-------|----------|
| 10 | Every item is relevant and valuable |
| 8 | Occasional filler but mostly high-value |
| 6 | Mixed quality, requires filtering |
| 4 | High volume with variable relevance |
| 0 | Mostly noise with rare gems |

## Minimum Inclusion Threshold

A source must achieve:
- **Total score:** ≥ 35/50
- **No single dimension:** < 6
- **Content depth:** ≥ 6 (must have some curation or original content)

## Source Categories

### Tier 1: Essential (Score 40+)

These sources form the core of the aggregation pipeline. They have:
- Consistent high-quality output
- Strong editorial curation
- High practitioner recognition
- Reliable publication schedule

Examples:
- arXiv cs.AI/cs.LG (research)
- Import AI (newsletter)
- This Week in Rust (community)
- GitHub Changelog (platform)

### Tier 2: Valuable (Score 35-39)

These sources provide good supplementary coverage:
- Solid quality with occasional variance
- Good curation but less comprehensive
- Strong in specific niches

Examples:
- TLDR AI (newsletter)
- Python Weekly (community)
- Console (tool reviews)

### Tier 3: Monitoring (Score 30-34)

These sources require more filtering but contain valuable content:
- Variable quality
- High volume
- Worth monitoring for important announcements

Examples:
- Dev.to feed (requires filtering)
- Hacker News frontpage (high volume)

## Domain-Specific Criteria

### AI/ML Domain

**Priority characteristics:**
1. Research novelty (new papers, techniques)
2. Implementation availability (code, models)
3. Reproducibility information
4. Benchmark results
5. Practical applicability

**Red flags:**
- Hype without technical detail
- Unverified claims
- Marketing content disguised as research
- Clickbait titles

### Software Development Domain

**Priority characteristics:**
1. Release announcements with changelogs
2. Security advisories
3. Performance improvements
4. Breaking changes documentation
5. Best practices and patterns

**Red flags:**
- Outdated content
- Framework-specific marketing
- Basic tutorials without insight
- Duplicate announcements

## Source Review Process

### Initial Evaluation

1. Review 4-6 weeks of historical content
2. Score each quality dimension
3. Check minimum threshold compliance
4. Document rationale for inclusion/exclusion

### Ongoing Monitoring

1. Monthly quality spot-checks
2. Track signal-to-noise ratio trends
3. Remove sources that fall below threshold
4. Accept community suggestions for review

### Removal Criteria

A source may be removed if:
- Quality score drops below 30 for 2+ consecutive months
- Publication becomes unreliable (missed 3+ expected issues)
- Content shifts away from target domain
- Community feedback indicates declining value

## Implementation Notes

### RSS Feed Requirements

Valid RSS feeds should:
- Include full content or substantial excerpt
- Provide publication timestamps
- Include author information
- Have stable URLs
- Support conditional GET (ETag/Last-Modified)

### Newsletter Handling

Newsletters without RSS:
- Use Kill the Newsletter or similar service
- Monitor for format changes
- Have fallback email ingestion ready

### GitHub Sources

For GitHub trending/release tracking:
- Use GitHub API with proper authentication
- Cache responses to respect rate limits
- Focus on releases, not just stars

## Current Source Inventory

### AI Domain
- **RSS Feeds:** 8 sources (arXiv, Papers with Code, HF, Google, OpenAI, Anthropic)
- **Newsletters:** 4 sources (Import AI, The Batch, TLDR AI, Interconnects)
- **GitHub:** 2 sources (Trending, Awesome lists)

### Software Development Domain
- **Language RSS:** 6 sources (Python x2, JS x2, Rust x1, Go x1)
- **Framework RSS:** 3 sources (React, Django, FastAPI)
- **General Dev:** 3 sources (HN, Dev.to, GitHub)
- **Newsletters:** 3 sources (TLDR, Console, Pointer)

**Total Active Sources:** 26 RSS feeds + 7 newsletters = 33 sources

## Changelog

| Date | Version | Changes |
|------|---------|---------|
| 2026-03-21 | 1.0.0 | Initial criteria definition |
