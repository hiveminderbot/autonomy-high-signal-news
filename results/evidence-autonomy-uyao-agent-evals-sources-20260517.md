# Evidence for autonomy-uyao

## Artifact produced
- Repo: `labs/high-signal-news`
- Integrated accepted sources into `sources/sources-ai.json`:
  - `METR Updates` → `https://metr.substack.com/feed`
  - `Epoch AI Brief` → `https://epochai.substack.com/feed`
- Added regression coverage: `tests/test_agent_evals_source_catalog.py`
- Preserved source-lead state:
  - `state/source_roster_agentic_briefing_additions.jsonl`
  - `state/agentic_sources_watchlist.jsonl`
- Machine-readable evidence: `results/evidence-autonomy-uyao-agent-evals-sources-20260517.json`

## Source validation
| Source | URL | HTTP | Decision | Evidence |
| --- | --- | ---: | --- | --- |
| METR original lead | `https://metr.org/blog/rss.xml` | 404 | Reject URL | The autonomous lead URL is not a live feed. |
| METR Updates | `https://metr.substack.com/feed` | 200 | Adopt | Feed title `METR`; recent samples include `Measuring the Self-Reported Impact of Early-2026 AI on Technical Worker Productivity`, `Review of the “Risks from automated R&D” section in the Anthropic Risk Report (February 2026)`, and `Task Substitution and Uplift`. |
| Epoch original lead | `https://epoch.ai/blog/rss.xml` | 404 | Reject URL | The autonomous lead URL is not a live feed. |
| Epoch AI Brief | `https://epochai.substack.com/feed` | 200 | Adopt | Feed title `Epoch AI`; recent samples include `The Epoch Brief - May 15, 2026`, `The economics of superstar AI researchers`, and `RIP Classic Reasoning Benchmarks. What’s Next?`. |
| HN Algolia by-date API | `https://hn.algolia.com/api/v1/search_by_date?query=agent%20benchmark&tags=story&hitsPerPage=3` | 200 | Keep as watchlist/API lead, not RSS catalog | Returned current agent/benchmark discussion samples: `Show HN: Emergence World: World building as a way to evaluate LLMs`, `Systematically Auditing AI Agent Benchmarks with BenchJack`, and `Benchmarks for AI Models and Agents on CAD Tasks`. |

## Recommendation
**ADOPT FOR CATALOG:** METR and Epoch are high-signal agent-evaluation / benchmark / automation-economics sources, but the originally filed RSS URLs were wrong. I replaced them with validated Substack feeds and recorded the failed originals so future workers do not re-add the 404s.

**WATCHLIST ONLY:** HN Algolia is useful for timestamped practitioner-discovery queries, but it is an API query surface rather than a normal RSS source. Keep it in `state/agentic_sources_watchlist.jsonl` until a dedicated query-backed ingestion path exists.

## Next experiment / kill gate
- Next experiment: run the next high-signal-news daily aggregation and verify METR/Epoch entries appear in `briefing-high-signal` output.
- Kill/reopen gate: if either Substack feed starts returning non-2xx or produces no relevant entries for 3 consecutive scheduled runs, disable that feed or replace it with a site-native feed/API.

## Validation commands
- Direct URL refetch via Python `urllib.request` → METR original 404, METR feed 200, Epoch original 404, Epoch feed 200, HN Algolia API 200.
- `python3 -m json.tool sources/sources-ai.json >/tmp/sources-ai.json.validated` → pass.
- `python3 -m pytest -q tests/test_agent_evals_source_catalog.py tests/test_e2e_rss_briefing.py` → failed because the system Python lacks `pytest`.
- `.venv/bin/python -m pytest -q tests/test_agent_evals_source_catalog.py tests/test_e2e_rss_briefing.py` → pass: `1 passed in 0.10s`.
- `.venv/bin/python` loader smoke for `load_sources_from_catalog(Path("sources/sources-ai.json"))` → pass: 16 loadable sources; `METR Updates` and `Epoch AI Brief` present with RSS format and `High` signal quality.

## Safety / scope
- No OpenViking/Polymarket work.
- No outreach, spend, accounts, or external posting.
