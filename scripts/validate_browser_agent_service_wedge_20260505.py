#!/usr/bin/env python3
"""Validate a source-backed browser-agent QA/service revenue wedge outside OpenViking.

This lands a deterministic artifact for deciding whether to run a small service
experiment around browser-agent QA/ops automation for SaaS/ecommerce workflows.
It is intentionally not a capital-readiness claim; the acceptance gate is source
health plus a concrete next experiment/rejection path.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

LAB_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JSON = LAB_ROOT / "results" / "browser-agent-service-wedge-20260505.json"
DEFAULT_REPORT = LAB_ROOT / "results" / "browser-agent-service-wedge-20260505.md"

SOURCES = [
    {
        "name": "Microsoft Playwright MCP repository",
        "url": "https://github.com/microsoft/playwright-mcp",
        "role": "automation_surface",
        "why": "Primary source showing Playwright has an MCP server for browser automation through agent tools.",
        "keywords": ["Playwright", "MCP", "browser"],
    },
    {
        "name": "Chrome DevTools MCP repository",
        "url": "https://github.com/ChromeDevTools/chrome-devtools-mcp",
        "role": "diagnostic_surface",
        "why": "Primary source for using Chrome DevTools as an MCP-connected browser diagnostics surface.",
        "keywords": ["Chrome", "DevTools", "MCP"],
    },
    {
        "name": "Browserbase Stagehand introduction",
        "url": "https://docs.browserbase.com/stagehand/introduction",
        "role": "agent_sdk",
        "why": "Primary vendor documentation for an agent-friendly browser automation SDK/API surface.",
        "keywords": ["Stagehand", "Browserbase", "browser"],
    },
    {
        "name": "Anthropic computer use documentation",
        "url": "https://docs.anthropic.com/en/docs/agents-and-tools/computer-use",
        "role": "model_capability",
        "why": "Primary model-provider documentation that computer-use/browser-control capabilities are supported for agents.",
        "keywords": ["computer use", "tool", "Claude"],
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
    value = value.replace("&nbsp;", " ").replace("&amp;", "&")
    return re.sub(r"\s+", " ", value).strip()


def fetch_url(url: str, timeout: int) -> tuple[int, bytes]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "HermesAutonomyBrowserAgentWedgeValidator/1.0 (+https://github.com/hiveminderbot/autonomy-high-signal-news)",
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


def _stable_source_record(item: SourceEvidence) -> dict:
    """Return a deterministic artifact record while stdout can print exact bytes.

    Live HTML byte counts for GitHub/docs pages vary between fetches, so tracked
    JSON/Markdown should store the stable validation fact instead of exact bytes.
    """
    record = asdict(item)
    record.pop("bytes_read", None)
    record["bytes_read_minimum_met"] = item.bytes_read >= 1_000
    return record


def make_payload(evidence: list[SourceEvidence], fetched_at: str) -> dict:
    healthy = [item for item in evidence if item.ok]
    roles = {item.role for item in healthy}
    required_roles = {"automation_surface", "diagnostic_surface", "agent_sdk", "model_capability"}
    passed = len(healthy) >= 4 and required_roles.issubset(roles)
    recommendation = "ADOPT_BROWSER_AGENT_QA_SERVICE_PILOT" if passed else "REJECT_UNTIL_SOURCE_EVIDENCE_HEALTHY"
    return {
        "artifact": "browser-agent-service-wedge-20260505",
        "fetched_at": fetched_at,
        "scope": "Non-OpenViking agent-service revenue experiment: browser-agent QA/ops automation for small SaaS and ecommerce workflows.",
        "recommendation": recommendation,
        "acceptance": {
            "passed": passed,
            "healthy_sources": len(healthy),
            "minimum_sources": 4,
            "required_roles_present": sorted(roles),
            "required_roles": sorted(required_roles),
        },
        "summary": {
            "finding": "Browser-agent QA/ops automation is worth one short service experiment because model, browser-control, and diagnostic surfaces now exist as primary-source-supported building blocks.",
            "why_now": "MCP-connected browser automation, DevTools diagnostics, managed browser-agent SDKs, and computer-use model docs collectively make it feasible to package a narrow bug-reproduction or workflow-monitoring service without building a full product first.",
            "sunk_cost_guardrail": "This is outside OpenViking/Polymarket and should be killed if a 48-hour demo cannot produce at least one externally useful QA artifact for a real public site or prospect workflow.",
        },
        "next_experiment": {
            "name": "48-hour browser-agent QA artifact sprint",
            "duration_days": 2,
            "deliverables": [
                "Pick 3 small SaaS/ecommerce websites with public signup/cart/demo flows and visible complexity.",
                "Use Playwright/DevTools/LLM browser agents to produce one reproducible bug report or workflow-health report per target.",
                "Package the best report as an outreach artifact offering a fixed-price weekly browser-agent QA monitor.",
            ],
            "success_gate": "Adopt only if at least one report contains a reproducible externally visible issue or concrete UX/conversion fix that could plausibly justify paid outreach; otherwise reject this wedge for now.",
        },
        "not_capital_ready_because": [
            "no paying customer or prospect reply yet",
            "no measured cost per successful browser task or failure triage yet",
            "no proof that agent-generated QA reports beat a human checklist for this market",
            "no production monitoring, consent, or anti-abuse process for third-party websites yet",
        ],
        "source_evidence": [_stable_source_record(item) for item in evidence],
    }


def render_report(payload: dict) -> str:
    lines = [
        "# Browser-agent QA/service revenue wedge validation — 2026-05-05",
        "",
        f"Recommendation: **{payload['recommendation']}**",
        "",
        "## Bottom line",
        payload["summary"]["finding"],
        "",
        "This is a service-experiment candidate, not a proven business or capital-ready project.",
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
            f"  - HTTP: {item['http_status']} bytes_minimum_met: {item['bytes_read_minimum_met']}",
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
    args.report_output.write_text(render_report(payload) + "\n")

    for evidence_item, item in zip(evidence, payload["source_evidence"], strict=True):
        print(f"SOURCE {item['url']} STATUS {item['http_status']} BYTES {evidence_item.bytes_read} OK {item['ok']}")
    print(f"REPORT {args.report_output} BYTES {args.report_output.stat().st_size}")
    print(f"SUMMARY {args.json_output} BYTES {args.json_output.stat().st_size}")
    if payload["acceptance"]["passed"]:
        print("BROWSER_AGENT_SERVICE_WEDGE_E2E_OK")
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
