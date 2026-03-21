# Research Method: Using adapted-research Skill

This project **dogfoods** the `adapted-research` skill we built in the research-skills lab.

## Why This Matters

Instead of manually compiling a list of sources from memory, we used our own research infrastructure to:
- **Discover** sources we might not know about
- **Validate** which sources are currently recommended
- **Extract** actual URLs and descriptions
- **Evidence-track** our findings

## Research Queries Executed

Used `ResearchOrchestrator` with:
- **Brave Search API** (2,000 queries/month free tier)
- **GitHub API** (5,000/hour with token)
- **Jina AI Reader** (unlimited content extraction)

### Query 1: AI Newsletters
```
"best AI newsletters 2024 high signal low noise"
```
**Results:** 10 sources found, 5 evidence claims
**Key Findings:**
- Zapier's curated list (zapier.com/blog/best-ai-newsletters/)
- AI Time Journal compilation
- GitHub awesome-ai-newsletters repo
- DigitalOcean's 12 AI newsletters guide
- Exploding Topics top 19 list

### Query 2: Software Development
```
"best software development news RSS feeds Hacker News alternatives 2024"
```
**Results:** 10 sources found
**Key Findings:**
- Dev.to community recommendations
- Reddit r/programming discussions
- Specific RSS feed recommendations
- Alternative to Hacker News (Lobsters, etc.)

### Query 3: Investment
```
"best tech investment news sources venture capital startup funding"
```
**Results:** 10 sources found
**Key Findings:**
- TechCrunch, VentureBeat, Axios Pro Rata
- Specific VC firm blogs
- Funding round trackers
- Newsletter recommendations

## Output Files

| File | Description |
|------|-------------|
| `research-2026-03-21T*.json` | Session data with sources and URLs |
| `evidence-2026-03-21T*.json` | Evidence tables with claims |
| `report-2026-03-21T*.md` | Markdown summaries |
| `source-catalog.json` | Merged catalog (generated) |

## Benefits Over Manual Research

1. **Freshness** — Got 2024 recommendations, not outdated lists
2. **Discovery** — Found sources we didn't know about (e.g., specific Substack newsletters)
3. **Validation** — Multiple sources pointing to same newsletters = higher confidence
4. **Evidence** — Tracked which sources recommended what
5. **URLs** — Actual working links, not just names

## Next Steps

Now we evaluate these discovered sources against our criteria:
- Signal-to-noise ratio
- Update frequency
- RSS availability
- Content extraction quality

Then build the aggregation pipeline using the best performers.

## Meta-Learning

This process validates the `adapted-research` skill works for real research tasks:
- ✅ Brave Search found relevant listicles
- ✅ GitHub discovered awesome-lists
- ✅ Jina AI extracted content from pages
- ✅ Evidence tracking captured recommendations

The skill is ready for broader use in other autonomy projects.
