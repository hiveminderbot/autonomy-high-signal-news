# High-Signal News Lab

**Purpose:** Research and build a high-value daily morning briefing system focused on AI, software development, and investment.

## Problem Statement

Information overload is real. Most news aggregators:
- Surface low-signal clickbait
- Lack domain-specific curation
- Don't synthesize across sources
- Provide no actionable intelligence

This lab aims to build a system that delivers a **10-minute daily briefing** with maximum signal-to-noise ratio.

## Domains

| Domain | Focus Areas |
|--------|-------------|
| **AI** | LLM releases, research papers, model capabilities, agent frameworks, safety debates |
| **Software Development** | Language releases, framework updates, architecture patterns, security alerts |
| **Investment** | Public markets (AI/tech), private funding rounds, strategic acquisitions, regulatory changes |

## Project Phases

### Phase 1: Source Discovery (Week 1)
- Research high-signal feeds across all three domains
- Evaluate RSS, newsletters, Twitter/X accounts, GitHub repos, Reddit communities
- Document inclusion criteria for sources

### Phase 2: Aggregation Pipeline (Week 2)
- Build feed aggregation system
- Implement deduplication
- Content extraction and normalization

### Phase 3: Summarization Engine (Week 3)
- Cluster related stories
- Generate concise summaries
- Extract key entities and relationships

### Phase 4: Briefing Generation (Week 4)
- Format for morning reading
- Prioritize by relevance and urgency
- Deliver via preferred channel (email, Telegram, etc.)

## Structure

```
high-signal-news/
├── state/           # Lab state files (STATUS.json, TODO.md, HANDOFF.md)
├── design/          # Architecture decisions, system designs
├── research/        # Source evaluations, curator lists
├── artifacts/       # Output samples, generated briefings
├── scripts/         # Implementation code
└── output/          # Daily briefing output
```

## Key Principles

1. **High Signal-to-Noise** — Better to miss a story than waste time on low-value content
2. **Synthesis Over Aggregation** — Don't just list headlines; explain why they matter
3. **Actionable Intelligence** — Focus on developments that enable decisions
4. **Respect Attention** — 10-minute hard limit; ruthless prioritization

## Status

Active development. See [STATUS.json](./state/STATUS.json) for current state.
