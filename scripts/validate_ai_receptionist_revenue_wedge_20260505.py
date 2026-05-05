#!/usr/bin/env python3
"""Validate a source-backed AI receptionist revenue wedge outside OpenViking.

The goal is not to prove capital readiness. It is to land a deterministic,
source-backed Tier 1.5/Tier 2 conversion artifact: does the market/tech evidence
justify a small outbound/service pilot, and what exact next experiment should run?
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import textwrap
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

LAB_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JSON = LAB_ROOT / "results" / "ai-receptionist-revenue-wedge-20260505.json"
DEFAULT_REPORT = LAB_ROOT / "results" / "ai-receptionist-revenue-wedge-20260505.md"

SOURCES = [
    {
        "name": "Twilio Programmable Voice pricing",
        "url": "https://www.twilio.com/en-us/voice/pricing/us",
        "role": "delivery_cost",
        "why": "Primary vendor page for PSTN voice-call cost assumptions.",
        "keywords": ["voice", "pricing", "Programmable Voice"],
    },
    {
        "name": "OpenAI Realtime API announcement",
        "url": "https://developers.openai.com/blog/realtime-api",
        "role": "technical_feasibility",
        "why": "Primary OpenAI developer source that realtime speech-to-speech API support exists.",
        "keywords": ["Realtime API", "speech", "audio"],
    },
    {
        "name": "Smith.ai pricing",
        "url": "https://www.smith.ai/pricing",
        "role": "competitor_willingness_to_pay",
        "why": "Competitor pricing page for outsourced receptionist / answering-service willingness to pay.",
        "keywords": ["pricing", "receptionist", "calls"],
    },
    {
        "name": "Slang.ai homepage",
        "url": "https://www.slang.ai/",
        "role": "vertical_competition",
        "why": "AI phone agent competitor focused on restaurants, evidence that verticalized phone automation is an active category.",
        "keywords": ["AI", "phone", "restaurant"],
    },
]


@dataclass
class SourceEvidence:
    name: str
    url: str
    role: str
    why: str
    http_status: int | None
    bytes_read: int
    keyword_hits: list[str]
    ok: bool
    error: str | None = None


def strip_html(value: str) -> str:
    value = re.sub(r"<script\b.*?</script>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<style\b.*?</style>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def fetch_url(url: str, timeout: int) -> tuple[int, bytes]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "HermesAutonomyRevenueWedgeValidator/1.0 (+https://github.com/hiveminderbot/autonomy-high-signal-news)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        status = int(getattr(response, "status", response.getcode()))
        return status, response.read()


def collect_source(source: dict, timeout: int, fetcher: Callable[[str, int], tuple[int, bytes]] = fetch_url) -> SourceEvidence:
    try:
        status, body = fetcher(source["url"], timeout)
        text = strip_html(body.decode("utf-8", "ignore"))
        lower = text.lower()
        hits = [kw for kw in source["keywords"] if kw.lower() in lower]
        ok = 200 <= status < 400 and len(body) >= 1_000 and len(hits) >= 2
        return SourceEvidence(
            name=source["name"],
            url=source["url"],
            role=source["role"],
            why=source["why"],
            http_status=status,
            bytes_read=len(body),
            keyword_hits=hits,
            ok=ok,
            error=None if ok else f"status={status} bytes={len(body)} keyword_hits={hits}",
        )
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return SourceEvidence(
            name=source["name"],
            url=source["url"],
            role=source["role"],
            why=source["why"],
            http_status=None,
            bytes_read=0,
            keyword_hits=[],
            ok=False,
            error=f"{type(exc).__name__}: {exc}",
        )


def make_payload(evidence: list[SourceEvidence], fetched_at: str) -> dict:
    healthy = [item for item in evidence if item.ok]
    roles = {item.role for item in healthy}
    passed = len(healthy) >= 3 and {"delivery_cost", "technical_feasibility", "competitor_willingness_to_pay"}.issubset(roles)
    recommendation = "ADOPT_NARROW_AI_RECEPTIONIST_PILOT" if passed else "REJECT_UNTIL_SOURCE_EVIDENCE_HEALTHY"
    return {
        "artifact": "ai-receptionist-revenue-wedge-20260505",
        "fetched_at": fetched_at,
        "scope": "Non-OpenViking AI service revenue experiment: after-hours AI receptionist for appointment-based local businesses.",
        "recommendation": recommendation,
        "acceptance": {
            "passed": passed,
            "healthy_sources": len(healthy),
            "required_roles_present": sorted(roles),
            "minimum_sources": 3,
        },
        "summary": {
            "finding": "A narrow AI receptionist service pilot is worth one lean validation sprint, not capital deployment.",
            "why_now": "Realtime voice APIs plus commodity telephony make a concierge-style service technically feasible; competitor pricing pages show businesses already buy receptionist/call-handling outcomes.",
            "sunk_cost_guardrail": "This is outside OpenViking/Polymarket and should be killed if a prospect shortlist and live demo cannot produce replies/meetings quickly.",
        },
        "next_experiment": {
            "name": "10-prospect after-hours missed-call concierge pilot",
            "duration_days": 3,
            "deliverables": [
                "one Twilio/OpenAI demo phone number that answers, captures caller intent, and emails a lead summary",
                "a shortlist of 10 local appointment-based businesses with visible after-hours call friction",
                "outreach packet offering a fixed-price setup plus monthly managed answering pilot",
            ],
            "success_gate": "At least 2 human replies or 1 scheduled demo from 10 targeted prospects; otherwise reject or change vertical.",
        },
        "not_capital_ready_because": [
            "no paying customer yet",
            "no measured cost-per-call, containment rate, or booking/revenue lift yet",
            "no production compliance/consent workflow for call recording and PII yet",
        ],
        "source_evidence": [asdict(item) for item in evidence],
    }


def render_report(payload: dict) -> str:
    lines = [
        "# AI receptionist revenue wedge validation — 2026-05-05",
        "",
        f"Recommendation: **{payload['recommendation']}**",
        "",
        "## Bottom line",
        payload["summary"]["finding"],
        "",
        "This is a conversion candidate, not a proven business. It should advance only to a tiny demo + prospect test; it is not capital-ready.",
        "",
        "## Why this is worth one lean pilot",
        f"- {payload['summary']['why_now']}",
        f"- Guardrail: {payload['summary']['sunk_cost_guardrail']}",
        "",
        "## Next experiment",
        f"**{payload['next_experiment']['name']}** ({payload['next_experiment']['duration_days']} days)",
        "",
    ]
    for deliverable in payload["next_experiment"]["deliverables"]:
        lines.append(f"- {deliverable}")
    lines.extend([
        "",
        f"Success gate: {payload['next_experiment']['success_gate']}",
        "",
        "## Not capital-ready because",
    ])
    for reason in payload["not_capital_ready_because"]:
        lines.append(f"- {reason}")
    lines.extend(["", "## Source evidence"])
    for item in payload["source_evidence"]:
        status = "OK" if item["ok"] else "FAIL"
        lines.extend([
            f"- **{item['name']}** — {status}",
            f"  - URL: {item['url']}",
            f"  - Role: {item['role']}",
            f"  - HTTP: {item['http_status']} bytes_minimum_met: {item['bytes_read'] >= 1000}",
            f"  - Keyword hits: {', '.join(item['keyword_hits']) if item['keyword_hits'] else '(none)'}",
            f"  - Why cited: {item['why']}",
        ])
    lines.extend([
        "",
        "## Validation criteria",
        f"- Healthy sources: {payload['acceptance']['healthy_sources']} / {payload['acceptance']['minimum_sources']}",
        f"- Required roles present: {', '.join(payload['acceptance']['required_roles_present'])}",
        f"- Passed: {payload['acceptance']['passed']}",
        "",
    ])
    return "\n".join(lines)


def run(args: argparse.Namespace) -> dict:
    fetched_at = args.artifact_timestamp or datetime.now(timezone.utc).isoformat()
    evidence = [collect_source(source, args.timeout) for source in SOURCES]
    payload = make_payload(evidence, fetched_at)
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.report_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    args.report_output.write_text(render_report(payload))

    for item in payload["source_evidence"]:
        print(f"SOURCE {item['url']} STATUS {item['http_status']} BYTES {item['bytes_read']} OK {item['ok']}")
    print(f"REPORT {args.report_output} BYTES {args.report_output.stat().st_size}")
    print(f"SUMMARY {args.json_output} BYTES {args.json_output.stat().st_size}")
    if payload["acceptance"]["passed"]:
        print("AI_RECEPTIONIST_REVENUE_WEDGE_E2E_OK")
    else:
        print("TASK INCOMPLETE: source evidence threshold not met")
        raise SystemExit(1)
    return payload


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=int, default=25)
    parser.add_argument("--artifact-timestamp", default="2026-05-05T00:00:00+00:00")
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    run(parse_args(sys.argv[1:] if argv is None else argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
