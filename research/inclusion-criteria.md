# Source Inclusion Criteria

## Version
1.0.0 — March 21, 2026

## Purpose
This document defines the criteria for including, excluding, and ranking news sources in the high-signal news aggregation system.

---

## Signal Quality Levels

### Very High ⭐⭐⭐⭐⭐
**Criteria:**
- Original research or primary source material
- Written by recognized experts in the field
- Editorial oversight and fact-checking
- Primary announcements from major organizations
- Predictable impact on industry discourse

**Examples:**
- arXiv papers (primary research)
- OpenAI/Anthropic blogs (major releases)
- Papers with Code (curated trending research)
- Stratechery, The Information (expert analysis)
- Official language/framework blogs

### High ⭐⭐⭐⭐
**Criteria:**
- Curated aggregation by domain experts
- Official organizational communications
- Consistent editorial standards
- Strong community reputation
- Low noise-to-signal ratio

**Examples:**
- Import AI (curated by Jack Clark)
- This Week in Rust (community curated)
- Semianalysis (technical deep dives)
- GitHub Changelog (official updates)

### Medium-High ⭐⭐⭐
**Criteria:**
- Community-filtered content
- Requires additional filtering for relevance
- Variable quality but generally reliable
- Good for trend detection

**Examples:**
- Hacker News (community voted)
- Lobsters (technical community)

### Medium ⭐⭐
**Criteria:**
- Broad coverage including lower-signal content
- Useful for completeness
- May include promotional content
- Requires significant filtering

**Examples:**
- TechCrunch (broad startup coverage)
- JavaScript Weekly (includes tutorials)
- AlphaSignal (aggregator)

### Low ⭐
**Criteria:**
- Reposts without added value
- Clickbait or sensationalized headlines
- Unverified speculation
- High promotional content

**Action:** Exclude from primary feed, may include in auxiliary sources list.

---

## Domain-Specific Criteria

### AI Domain

**Must Have (for inclusion):**
- [ ] Research-backed claims or citations
- [ ] Technical accuracy in descriptions
- [ ] Relevance to current AI landscape
- [ ] No undisclosed promotional content

**Nice to Have:**
- Code implementations or reproducible results
- Links to primary sources
- Discussion of limitations
- Safety/societal impact consideration

**Automatic Exclusions:**
- AGI hype without technical substance
- Undisclosed AI-generated content
- Unsubstantiated performance claims
- Cryptocurrency/NFT tie-ins without relevance

### Software Development Domain

**Must Have (for inclusion):**
- [ ] Accurate technical information
- [ ] Relevance to practicing developers
- [ ] Practical applicability
- [ ] Current information (not outdated)

**Nice to Have:**
- Code examples
- Migration guides for breaking changes
- Performance benchmarks
- Security implications discussed

**Automatic Exclusions:**
- Outdated tutorials (2+ years old without update)
- Clickbait listicles without substance
- Sponsored content without disclosure
- Framework advocacy without balanced comparison

### Investment Domain

**Must Have (for inclusion):**
- [ ] Verifiable data or citations
- [ ] Clear distinction between fact and opinion
- [ ] Disclosure of conflicts of interest
- [ ] Relevance to tech/AI sectors

**Nice to Have:**
- Quantitative analysis
- Historical context
- Risk disclosure
- Diverse perspective coverage

**Automatic Exclusions:**
- Pump-and-dump schemes
- Unsubstantiated price targets
- Undisclosed paid promotions
- Cryptocurrency speculation without tech relevance

---

## Source Evaluation Checklist

Before adding a new source, verify:

- [ ] **Authority:** Is the author/organization recognized in the domain?
- [ ] **Accuracy:** Has the source demonstrated factual accuracy over time?
- [ ] **Currency:** Is the content regularly updated?
- [ ] **Relevance:** Does it serve our target domains (AI, Dev, Investment)?
- [ ] **Accessibility:** Is the content available via RSS, API, or newsletter?
- [ ] **Sustainability:** Is the source likely to continue publishing?
- [ ] **Uniqueness:** Does it provide information not available elsewhere?
- [ ] **Format:** Is the format parseable for automated ingestion?

---

## Source Lifecycle

### Onboarding
1. Discovery via research or recommendation
2. Initial evaluation against criteria
3. Test ingestion for 1-2 weeks
4. Quality assessment of ingested content
5. Categorization and cataloging
6. Activation in production feed

### Monitoring
- Weekly: Review ingestion success rate
- Monthly: Assess signal quality of ingested content
- Quarterly: Re-evaluate against criteria

### Offboarding
Sources may be deprecated when:
- Publication ceases or becomes sporadic (>3 months gap)
- Quality degrades consistently (2+ quarters)
- Signal-to-noise ratio drops below threshold
- Feed becomes inaccessible (RSS broken, paywall changes)
- Domain relevance is lost

**Deprecation process:**
1. Mark as deprecated in catalog
2. Remove from active ingestion
3. Archive historical data
4. Document reason for deprecation

---

## RSS Feed Quality Indicators

### Excellent RSS Feeds
- Full article content (not just summaries)
- Proper date formatting (RFC 822)
- Unique GUIDs for each item
- Clean HTML (no excessive tracking pixels)
- Categories/tags for filtering
- Reasonable update frequency

### Acceptable RSS Feeds
- Summaries with clear links to full content
- Consistent date formatting
- Stable URLs
- Update frequency matches content type

### Problematic RSS Feeds
- Truncated content requiring click-through
- Inconsistent or missing dates
- Duplicate items
- Broken HTML/encoding issues
- Rate limiting or blocking
- Excessive promotional content

---

## Newsletter Quality Indicators

### Excellent Newsletters
- Clear subject lines with date/issue number
- Consistent format (predictable structure)
- RSS feed available or email-to-RSS convertible
- Archive available online
- Unsubscribe mechanism works

### Acceptable Newsletters
- Regular schedule
- Manageable length (<10 min read)
- Clear sections/topics
- Working links

### Problematic Newsletters
- Irregular schedule
- Excessive length or very short
- Heavy image dependence (not text-friendly)
- Broken links or tracking-dominated
- Poor unsubscribe experience

---

## Scoring Algorithm (Draft)

Proposed formula for source ranking:

```
Source_Score = (Quality × 0.4) + (Freshness × 0.2) + (Relevance × 0.2) + (Uniqueness × 0.2)

Where:
- Quality: 5=Very High, 4=High, 3=Medium-High, 2=Medium, 1=Low
- Freshness: Days since last post (normalized)
- Relevance: User domain interest match (0-1)
- Uniqueness: Overlap with other sources (inverse)
```

---

## Revision History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2026-03-21 | Initial criteria definition |

---

## Open Questions

1. Should we weight sources differently based on user feedback?
2. How do we handle paywalled content that's high quality?
3. What's the threshold for removing a degraded source?
4. Should we have different criteria for breaking news vs. analysis?
