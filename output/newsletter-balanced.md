# High-Signal Newsletter - Balanced Multi-Source

*March 22, 2026 | 2 articles per source, no duplication*

---

## Philosophy

**Balanced sourcing:** 2 articles each from Hacker News, JavaScript Weekly, and Lobsters.
No single source dominates. Cross-source themes require validation across independent editorial teams.

**High-signal social:** Also tracking individual voices (Karpathy, Willison, LeCun, Dan Luu,
Carmack) on Twitter/X - see sources-high-signal-social.json for the list.

---

## Hacker News

**Tinybox- offline AI device 120B parameters**
[https://tinygrad.org/#tinybox](https://tinygrad.org/#tinybox)

*Tinybox is a dedicated hardware device enabling local inference of 120B parameter AI models without cloud connectivity*

**Insight:** Local 120B inference enables true data privacy, zero latency variance, offline operation, and cost predictability vs recurring API fees

• 120B models now runnable on single device via quantization and optimized inference
• Power/thermal critical: 300-800W consumption with sophisticated cooling

*Evidence: 7,043 chars extracted*

**Electronics for Kids, 2nd Edition**
[https://nostarch.com/electronics-for-kids-2e](https://nostarch.com/electronics-for-kids-2e)

*Book teaches hardware fundamentals to children through hands-on projects, updated 2nd edition*

**Insight:** Hardware literacy demystifies technology and creates better-rounded engineers who understand both hardware and software

• Tangible learning more effective for electronics concepts than software-only
• Fills "maker gap" in children's tech education

*Evidence: 10,604 chars extracted*


## JavaScript Weekly

**It’s about time: Temporal advances, Vite accelerates**
[https://javascriptweekly.com/issues/777](https://javascriptweekly.com/issues/777)

*JavaScript Temporal API (modern date/time) moving forward; Vite build tool getting faster*

**Insight:** JS Date has been problematic since 1995; build tool speed directly impacts developer productivity and CI costs

• Temporal reached TC39 Stage 3 (browser implementation underway)
• Vite shows 10-100x faster cold starts vs webpack

*Evidence: 11,526 chars extracted*

**Oxfmt beta: 30x faster than Prettier, 100% compatible**
[https://javascriptweekly.com/issues/774](https://javascriptweekly.com/issues/774)

*Oxfmt is a Rust-based JS/TS formatter achieving 30x speedup over Prettier with 100% compatibility*

**Insight:** Rust keeps winning for JS tooling because of zero-cost abstractions and ecosystem maturation (shared Oxc parser, deterministic output)

• Parser Advantage Compound Effect: shared Oxc parser amortizes costs across tools
• Format-Once Consistency: deterministic output makes 100% compatibility achievable

*Evidence: 8,364 chars extracted*


## Lobsters

**Predicting home electricity usage based on historical patterns in Home Assistant**
[https://blog.cyplo.dev/posts/2026/03/load-prediction-in-home-assistant/](https://blog.cyplo.dev/posts/2026/03/load-prediction-in-home-assistant/)

*ML-based electricity forecasting using Home Assistant to predict usage and optimize time-of-use energy rates*

**Insight:** Local ML preserves privacy (usage data reveals intimate patterns) while offering lower latency, no subscription costs, and customization

• Temporal patterns (time/day/season) dominate electricity predictability
• Discretionary load shifting (EVs, appliances) yields biggest savings

*Evidence: 11,348 chars extracted*

**bye bye RTMP**
[https://daniel.haxx.se/blog/2026/03/21/bye-bye-rtmp/](https://daniel.haxx.se/blog/2026/03/21/bye-bye-rtmp/)

*RTMP is dead - Adobe deprecated it alongside Flash; curl removing RTMP support signals infrastructure unmaintainability*

**Insight:** Legacy protocols persist due to infrastructure inertia, "good enough" ingest, hardware encoder lock-in, and latency requirements

• SRT replaces RTMP for ingest (better resilience, open-source, OBS native)
• Playback splits: HLS for scale, WebRTC for sub-second latency

*Evidence: 9,247 chars extracted*


---

## Cross-Source Synthesis

Themes validated across **multiple independent sources**:

**AI/ML Applications**
   Seen in: Hacker News, Lobsters

**Local-First/Privacy**
   Seen in: Hacker News, Lobsters

**Hardware/Physical Computing**
   Seen in: Hacker News, Lobsters

---

## Source Distribution

| Source | Articles | Type |
|--------|----------|------|
| Hacker News | 2 | Generalist tech |
| JavaScript Weekly | 2 | Domain (JS ecosystem) |
| Lobsters | 2 | Generalist programming |

**High-signal individuals tracked:**
• Twitter/X: Karpathy, Willison, LeCun, Howard, Dan Luu, patio11, jessfraz, Carmack
• See `sources/sources-high-signal-social.json` for full list

---

*Generated: 2026-03-22 03:26*

**Methodology:**
1. Fetch RSS from 22+ sources
2. Select balanced set (2 per source)
3. Extract full content (Jina AI)
4. Spawn parallel LLM subagents for analysis
5. No duplication: each article appears exactly once
6. Cross-source themes require 2+ independent sources

**This issue:** 6 articles, 3 sources, 3 cross-source themes