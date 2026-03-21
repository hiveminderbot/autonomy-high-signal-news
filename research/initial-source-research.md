# Initial Source Research

## AI Domain — Known High-Signal Sources

### Research Papers
| Source | Format | Frequency | Signal Quality | Notes |
|--------|--------|-----------|----------------|-------|
| arXiv cs.AI/CL/LG | RSS | Daily | High | Raw papers, need filtering |
| Papers with Code | RSS | Weekly | Very High | Trending + code |
| Hugging Face Papers | Web | Daily | High | Curated with community notes |
| Google AI Blog | RSS | ~Weekly | High | Official Google research |
| OpenAI Blog | RSS | Sporadic | Very High | Major announcements only |
| Anthropic Blog | RSS | Sporadic | Very High | Safety + capabilities focus |

### Newsletters
| Newsletter | Author | Frequency | Signal Quality | Notes |
|------------|--------|-----------|----------------|-------|
| Import AI | Jack Clark | Weekly | Very High | Policy + research focus |
| The Batch | Andrew Ng | Weekly | High | Educational angle |
| TLDR AI | TLDR | Daily | Medium-High | Quick summaries |
| AlphaSignal | — | Daily | Medium | Aggregator format |
| The Sequence | — | Weekly | Medium | Business + research |

### Twitter/X Accounts
| Account | Focus | Signal Quality | Notes |
|---------|-------|----------------|-------|
| @bindureddy | Agents, startups | High | Automattic founder |
| @karpathy | Education, research | Very High | Ex-OpenAI, Tesla |
| @ylecun | Research, opinions | High | Meta Chief Scientist |
| @goodside | Prompt engineering | High | Scale AI |
| @jeremyphoward | Practical ML | High | Fast.ai founder |

### GitHub
| Source | Type | Signal Quality | Notes |
|--------|------|----------------|-------|
| Trending Python | Auto | Medium | Language-agnostic filter needed |
| microsoft/generative-ai-for-beginners | Curated | High | Educational |
| awesome-ai-agents | Curated | Medium | Lists get stale |

## Software Development Domain

### Language-Specific
| Source | Language | Format | Signal Quality |
|--------|----------|--------|----------------|
| Python Insider | Python | Blog | Very High |
| Node.js Blog | JavaScript | Blog | High |
| Go Blog | Go | Blog | High |
| Rust Blog | Rust | Blog | High |
| This Week in Rust | Rust | Newsletter | Very High |
| JavaScript Weekly | JavaScript | Newsletter | Medium |
| Python Weekly | Python | Newsletter | Medium |

### Frameworks & Tools
| Source | Focus | Format | Signal Quality |
|--------|-------|--------|----------------|
| React Blog | React | Blog | High |
| Django News | Django | Newsletter | Medium |
| GitHub Changelog | GitHub | Blog | High |
| Docker Blog | Docker | Blog | Medium |

### General Dev
| Source | Format | Signal Quality | Notes |
|--------|--------|----------------|-------|
| Hacker News (top 30) | Web | Medium-High | Needs filtering |
| Lobsters | Web | High | Smaller, more technical |
| Dev.to trending | Web | Low-Medium | Variable quality |

## Investment Domain

### Public Markets
| Source | Focus | Format | Signal Quality |
|--------|-------|--------|----------------|
| Bloomberg Tech | Tech stocks | Web/Paid | Very High |
| TechCrunch | Startups, funding | Web | Medium |
| The Information | Tech business | Paid | Very High |
| Ars Technica | Tech + policy | Web | High |
| Stratechery | Strategy | Paid | Very High |

### VC/Funding
| Source | Format | Signal Quality | Notes |
|--------|--------|----------------|-------|
| PitchBook News | Web/Paid | High | Private markets data |
| Crunchbase News | Web | Medium | Funding round tracking |
| Term Sheet (Fortune) | Newsletter | Medium | Daily deals |
| Axios Pro Rata | Newsletter | Medium | Quick deal summaries |

### AI-Specific Investment
| Source | Format | Signal Quality | Notes |
|--------|--------|----------------|-------|
| AI Newsletter (Nathan Benaich) | Newsletter | High | Air Street Capital |
| The Diff | Newsletter | High | AI + finance focus |
| Semianalysis | Blog/Newsletter | Very High | Technical + business |

## Content Aggregation Tools

| Tool | Purpose | Open Source | Notes |
|------|---------|-------------|-------|
| FreshRSS | Self-hosted RSS | Yes | PHP-based, mature |
| Miniflux | Self-hosted RSS | Yes | Go-based, minimalist |
| Kill the Newsletter | Email→RSS | Yes | Convert newsletters |
| RSSHub | RSS bridge | Yes | Generate RSS for any site |
| Nitter | Twitter→RSS | Yes | Unofficial, unstable |

## Initial Recommendations

### MVP Source Set (10 sources)
1. **arXiv cs.AI** (research)
2. **Import AI** (newsletter)
3. **Papers with Code** (trending)
4. **This Week in Rust / Python Insider** (language)
5. **GitHub Changelog** (platform)
6. **Hacker News top stories** (general tech)
7. **TechCrunch** (funding)
8. **Stratechery** (strategy)
9. **The Information** (tech business)
10. **OpenAI/Anthropic blogs** (major releases)

### Quality Criteria
- **Very High:** Original research, primary sources, expert analysis
- **High:** Curated aggregators, official announcements
- **Medium:** General news, broader coverage
- **Low:** Reposts, clickbait, speculation

### Next Steps
1. Set up RSS infrastructure (FreshRSS or Miniflux)
2. Test content extraction quality
3. Design ranking/prioritization algorithm
4. Build summarization pipeline
