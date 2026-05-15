# Evidence: Simon Willison feed source expansion

Bead: `autonomy-vojr`  
Validated: 2026-05-15T06:18:00+00:00

## Decision

**Adopt.** The configured Simon Willison Everything Atom feed is live, parseable, recent, and present exactly once in `state/sources.json`.

## Source validation

| Check | Result |
|---|---:|
| URL | https://simonwillison.net/atom/everything/ |
| HTTP status | 200 |
| Final URL | https://simonwillison.net/atom/everything/ |
| Content-Type | `application/xml; charset=utf-8` |
| Response bytes | 89,309 |
| SHA-256 | `34a1484548a643b41bde86e270e4a5385eec480ba8c420504ddba817139c83b6` |
| Parsed Atom entries sampled | 10 |
| `state/sources.json` parse | valid JSON |
| Simon feed entries in config | 1 |

## Sample parsed entries

1. **Not so locked in any more** — 2026-05-14T22:53:49+00:00  
   https://simonwillison.net/2026/May/14/not-so-locked-in/#atom-everything
2. **Quoting Mitchell Hashimoto** — 2026-05-14T22:31:20+00:00  
   https://simonwillison.net/2026/May/14/mitchell-hashimoto/#atom-everything
3. **datasette-ip-rate-limit 0.1a0** — 2026-05-14T04:10:23+00:00  
   https://simonwillison.net/2026/May/14/datasette-ip-rate-limit/#atom-everything
4. **Welcome to the Datasette blog** — 2026-05-13T23:59:39+00:00  
   https://simonwillison.net/2026/May/13/welcome-to-the-datasette-blog/#atom-everything
5. **Quoting Boris Mann** — 2026-05-13T16:15:50+00:00  
   https://simonwillison.net/2026/May/13/boris-mann/#atom-everything

## Why it matters

This is not a real-world result by itself; it is a validated source-expansion capability for the high-signal briefing pipeline. It plausibly improves autonomous opportunity discovery because Simon Willison's feed regularly covers agent tooling, model behavior, evals, security footguns, and practical infrastructure changes that map to active Hermes/autonomy work.

## Next conversion experiment

Let the daily aggregation cron include this feed for 3 runs, then measure:

- accepted item count from this source,
- whether at least one item reaches the briefing under existing high-signal filters,
- whether any item converts to a benchmark, public artifact, deployment, or validated rejection task.

Raw machine-readable evidence: `results/evidence-autonomy-vojr-simon-willison-feed-20260515.json`.
