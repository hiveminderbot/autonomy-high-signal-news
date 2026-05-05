# Live RSS Briefing Proof — 2026-05-05

Fetched at: `2026-05-05T22:31:00+00:00`

## Recommendation

**ADOPT_FOR_DAILY_BRIEFING_CRON**

Run the existing high-signal-news briefing generator against these live feed rows for 7 daily runs, then keep only sources with nonzero entries and no HTTP/parser failures.

## Validation summary

- Healthy sources: 4 / 4 (minimum 3)
- Parsed live entries: 32 (minimum 10)
- Acceptance passed: `True`

## Source evidence

### Hacker News

- URL: https://news.ycombinator.com/rss
- Domain: software_development
- Why included: High-signal startup/software community feed with current links.
- HTTP status: 200
- Bytes read: 11970
- Parsed entries: 8
- Healthy: `True`

Top parsed entries:

- [.de TLD offline due to DNSSEC?](https://dnssec-analyzer.verisignlabs.com/nic.de) — 2026-05-05T20:16:35+00:00
- [Accelerating Gemma 4: faster inference with multi-token prediction drafters](https://blog.google/innovation-and-ai/technology/developers-tools/multi-token-prediction-gemma-4/) — 2026-05-05T16:14:17+00:00
- [Write some software, give it away for free](https://nonogra.ph/write-some-software-give-it-away-for-free-05-05-2026) — 2026-05-05T21:26:50+00:00
- [Three Inverse Laws of AI](https://susam.net/inverse-laws-of-robotics.html) — 2026-05-05T15:27:18+00:00
- [Computer Use is 45x more expensive than structured APIs](https://reflex.dev/blog/computer-use-is-45x-more-expensive-than-structured-apis/) — 2026-05-05T16:34:48+00:00

### Lobsters

- URL: https://lobste.rs/rss
- Domain: software_development
- Why included: Curated programming community with timestamps and discussion links.
- HTTP status: 200
- Bytes read: 15736
- Parsed entries: 8
- Healthy: `True`

Top parsed entries:

- [Why didn’t IPv6 work in my home network?](https://gowtham.dev/blog/ipv6-problems.html) — 2026-05-05T13:46:37+00:00
- [A bidirectional typechecking puzzle](https://haskellforall.com/2026/05/a-bidirectional-typechecking-puzzle) — 2026-05-05T13:21:28+00:00
- [RSS Feeds Send Me More Traffic Than Google](https://shkspr.mobi/blog/2026/05/rss-feeds-send-me-more-traffic-than-google/) — 2026-05-05T14:46:08+00:00
- [A Caddy Cert Expired Because systemd-resolved Was Selectively Broken](https://rant.mvh.dev/a-caddy-cert-expired-because-systemd-resolved-was-selectively-broken/) — 2026-05-05T12:32:59+00:00
- [Bun (the js runtime) is being vibe-ported from zig to rust](https://github.com/oven-sh/bun/blob/claude/phase-a-port/docs/PORTING.md) — 2026-05-05T03:07:03+00:00

### Simon Willison

- URL: https://simonwillison.net/atom/everything/
- Domain: ai_and_software
- Why included: Practitioner-focused AI/tooling notes from a high-signal individual source.
- HTTP status: 200
- Bytes read: 106783
- Parsed entries: 8
- Healthy: `True`

Top parsed entries:

- [Our AI started a cafe in Stockholm](https://simonwillison.net/2026/May/5/our-ai-started-a-cafe-in-stockholm/#atom-everything) — 2026-05-05T22:14:21+00:00
- [datasette-llm 0.1a7](https://simonwillison.net/2026/May/5/datasette-llm/#atom-everything) — 2026-05-05T01:56:55+00:00
- [llm-echo 0.5a0](https://simonwillison.net/2026/May/5/llm-echo/#atom-everything) — 2026-05-05T01:31:54+00:00
- [Quoting John Gruber](https://simonwillison.net/2026/May/5/john-gruber/#atom-everything) — 2026-05-05T00:46:29+00:00
- [Granite 4.1 3B SVG Pelican Gallery](https://simonwillison.net/2026/May/4/granite-41-3b-svg-pelican-gallery/#atom-everything) — 2026-05-04T23:49:24+00:00

### Python Insider

- URL: https://pythoninsider.blogspot.com/feeds/posts/default
- Domain: software_development
- Why included: Official-ish Python release/community announcements via Atom.
- HTTP status: 200
- Bytes read: 236423
- Parsed entries: 8
- Healthy: `True`

Top parsed entries:

- [The Python Insider Blog has moved!](https://www.blogger.com/feeds/3941553907430899163/posts/default/2791909950033204350) — 2026-03-03T13:08:00.007-05:00
- [Join the Python Security Response Team!](https://www.blogger.com/feeds/3941553907430899163/posts/default/307741466945747729) — 2026-02-17T02:30:00.001-05:00
- [Python 3.15.0 alpha 6](https://www.blogger.com/feeds/3941553907430899163/posts/default/6973278117439741537) — 2026-02-11T10:42:00.003-05:00
- [Python 3.14.3 and 3.13.12 are now available!](https://www.blogger.com/feeds/3941553907430899163/posts/default/3021891016049002155) — 2026-02-03T17:08:00.002-05:00
- [Python 3.15.0 alpha 5 (yes, another alpha!)](https://www.blogger.com/feeds/3941553907430899163/posts/default/6770398946690401432) — 2026-01-14T12:38:00.006-05:00

## Guardrail

This artifact is source-backed: every included headline was parsed from a fetched RSS/Atom response in this run. It is not an LLM-fabricated briefing.
