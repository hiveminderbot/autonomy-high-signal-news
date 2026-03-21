# RSS Feed Catalog

**Purpose:** High-signal RSS feeds for daily briefing ingestion.

**Discovery method:** Research with Brave Search, validated working RSS feeds.

---

## 🤖 Artificial Intelligence

### Tier 1: Essential

| Source | RSS URL | Type | Update Freq |
|--------|---------|------|-------------|
| **Import AI** | https://importai.substack.com/feed | Newsletter | Weekly |
| **The Batch** | https://read.deeplearning.ai/the-batch/feed/ | Newsletter | Weekly |
| **Hugging Face Blog** | https://huggingface.co/blog/feed.xml | Blog | Weekly |
| **OpenAI Blog** | https://openai.com/blog/rss.xml | Blog | Sporadic |
| **Anthropic Blog** | https://www.anthropic.com/blog/rss.xml | Blog | Sporadic |
| **Papers with Code** | https://paperswithcode.com/feed | Research | Daily |
| **arXiv cs.AI** | https://export.arxiv.org/rss/cs.AI | Research | Daily |

### Tier 2: High Quality

| Source | RSS URL | Type |
|--------|---------|------|
| **Google AI Blog** | https://ai.googleblog.com/feeds/posts/default | Blog |
| **DeepMind Blog** | https://deepmind.google/discover/feed/ | Blog |
| **Distill.pub** | https://distill.pub/rss.xml | Research |
| **BAIR Blog** | https://bair.berkeley.edu/blog/feed.xml | Research |
| **MIT AI News** | https://news.mit.edu/rss/topic/artificial-intelligence2 | News |

---

## 💻 Software Development

### Tier 1: Essential

| Source | RSS URL | Type | Language/Focus |
|--------|---------|------|----------------|
| **Hacker News** | https://news.ycombinator.com/rss | Community | General |
| **Lobsters** | https://lobste.rs/rss | Community | General |
| **GitHub Blog** | https://github.blog/feed/ | Blog | Platform |
| **GitHub Changelog** | https://github.blog/changelog/feed/ | Changelog | Platform |
| **Python Insider** | https://pythoninsider.blogspot.com/feeds/posts/default | Language | Python |
| **Go Blog** | https://go.dev/blog/feed.atom | Language | Go |
| **Rust Blog** | https://blog.rust-lang.org/feed.xml | Language | Rust |
| **This Week in Rust** | https://this-week-in-rust.org/rss.xml | Newsletter | Rust |
| **Node.js Blog** | https://nodejs.org/en/feed/blog.xml | Language | JavaScript |
| **React Blog** | https://react.dev/blog/rss.xml | Framework | React |

### Tier 2: High Quality

| Source | RSS URL | Type |
|--------|---------|------|
| **Django News** | https://django-news.com/feed/ | Framework |
| **JavaScript Weekly** | https://javascriptweekly.com/rss/ | Newsletter |
| **Frontend Focus** | https://frontendfoc.us/rss/ | Newsletter |
| **CSS-Tricks** | https://css-tricks.com/feed/ | Blog |
| **Smashing Magazine** | https://www.smashingmagazine.com/feed/ | Blog |
| **InfoQ** | https://www.infoq.com/feed/ | News |
| **High Scalability** | http://highscalability.com/rss.xml | Architecture |
| **Martin Fowler** | https://martinfowler.com/feed.atom | Architecture |

---

## 💰 Investment & Markets

### Tier 1: Essential

| Source | RSS URL | Type | Focus |
|--------|---------|------|-------|
| **TechCrunch** | https://techcrunch.com/feed/ | News | Startups |
| **TechCrunch Venture** | https://techcrunch.com/category/venture/feed/ | News | VC |
| **The Information** | https://www.theinformation.com/feed/ | News | Tech Business |
| **Axios Pro Rata** | https://www.axios.com/newsletters/ | Newsletter | Deals |
| **PitchBook News** | https://pitchbook.com/news/feed/ | News | Private Markets |
| **Crunchbase News** | https://news.crunchbase.com/feed/ | News | Funding |
| **VC News Daily** | https://vcnewsdaily.com/feed/ | News | VC |

### Tier 2: High Quality

| Source | RSS URL | Type |
|--------|---------|------|
| **Bloomberg Technology** | https://feeds.bloomberg.com/bloomberg/view/technology | News |
| **Ars Technica** | https://feeds.arstechnica.com/arstechnica/technology-lab | News |
| **Term Sheet (Fortune)** | https://fortune.com/tag/term-sheet/feed/ | Newsletter |
| **Semianalysis** | https://www.semianalysis.com/feed/ | Analysis |
| **Stratechery** | https://stratechery.com/feed/ | Analysis |
| **Benedict Evans** | https://www.ben-evans.com/benedictevans/rss | Analysis |

---

## 🔧 Tools & Infrastructure

### Feed Discovery
- **Kill the Newsletter** - Convert email newsletters to RSS
- **RSSHub** - Generate RSS for sites without feeds
- **FetchRSS** - Create RSS from any website

### Feed Validation
Test feeds with: `curl -s <feed_url> | head -20`

### Feed Reader Recommendations
- **FreshRSS** - Self-hosted, PHP-based
- **Miniflux** - Self-hosted, Go-based, minimalist
- **Tiny Tiny RSS** - Self-hosted, mature

---

## Bootstrap Strategy

### MVP Feed Set (15 feeds)
1. Hacker News (general tech)
2. Import AI (AI research)
3. The Batch (AI business)
4. OpenAI Blog (major releases)
5. Python Insider (language updates)
6. Go Blog (language updates)
7. GitHub Changelog (platform updates)
8. TechCrunch (startup news)
9. TechCrunch Venture (funding)
10. Papers with Code (AI research trends)
11. arXiv cs.AI (research papers)
12. This Week in Rust (systems programming)
13. Lobsters (developer discussion)
14. Axios Pro Rata (deal flow)
15. The Information (tech business)

### Daily Fetch Schedule
- Run every 6 hours (4x daily)
- Parse RSS, extract new items
- Deduplicate by URL
- Store in database
- Generate briefing at 7am local time

---

## Notes

**Feed Quality Indicators:**
- ✅ Full content in feed (not just summaries)
- ✅ Consistent update schedule
- ✅ Valid RSS/Atom format
- ✅ No paywall on original content (or good excerpt)

**Feed Maintenance:**
- Check feeds monthly for 404s
- Monitor for format changes
- Track signal-to-noise ratio
- Remove feeds that go stale (>30 days no update)
