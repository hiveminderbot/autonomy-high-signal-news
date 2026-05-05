#!/usr/bin/env python3
"""Validate a live prospect shortlist for a browser-agent QA service experiment.

This advances the earlier browser-agent QA wedge from abstract source evidence to a
public-target shortlist for one outreach/demo sprint. It is deliberately outside
OpenViking/Polymarket and does not claim revenue or capital readiness; it creates
a validated list of externally reachable signup/onboarding surfaces worth testing.
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
DEFAULT_JSON = LAB_ROOT / "results" / "browser-agent-qa-prospect-shortlist-20260505.json"
DEFAULT_REPORT = LAB_ROOT / "results" / "browser-agent-qa-prospect-shortlist-20260505.md"

TARGETS = [
    {
        "name": "Cal.com signup",
        "url": "https://cal.com/signup",
        "segment": "scheduling_saas",
        "keywords": ["cal", "sign", "account"],
        "why_fit": "Scheduling onboarding usually has account creation, calendar/account connection, timezone, and team-routing complexity that browser agents can check repeatedly.",
        "demo_hypothesis": "Produce a signup/onboarding friction report covering field validation, auth options, and calendar-connection dead ends without touching private data.",
    },
    {
        "name": "PostHog signup",
        "url": "https://app.posthog.com/signup",
        "segment": "product_analytics",
        "keywords": ["posthog", "signup", "login"],
        "why_fit": "Analytics onboarding depends on multi-step project creation and instrumentation guidance, a good fit for workflow-health and copy/friction checks.",
        "demo_hypothesis": "Check whether a new user can reach the first-project setup path and capture any confusing or blocked instrumentation steps.",
    },
    {
        "name": "Sentry signup",
        "url": "https://sentry.io/signup/",
        "segment": "developer_tools",
        "keywords": ["sentry", "sign", "error"],
        "why_fit": "Developer-tool onboarding combines auth, organization/project setup, and SDK-install instructions where broken or confusing flows are high-value.",
        "demo_hypothesis": "Generate a browser-agent transcript from landing on signup through first SDK/project prompts, highlighting friction and console/network errors.",
    },
    {
        "name": "Linear signup",
        "url": "https://linear.app/signup",
        "segment": "collaboration_saas",
        "keywords": ["linear", "signup", "workspace"],
        "why_fit": "Team/workspace creation has several branching onboarding states that can regress visibly and matter to conversion.",
        "demo_hypothesis": "Validate account/workspace-entry affordances and report any stalled or unclear browser states from a fresh public session.",
    },
    {
        "name": "Supabase dashboard sign-up",
        "url": "https://supabase.com/dashboard/sign-up",
        "segment": "developer_platform",
        "keywords": ["supabase", "sign", "dashboard"],
        "why_fit": "Developer-platform onboarding includes auth, organization/project creation, and dashboard load behavior that automated browser diagnostics can measure.",
        "demo_hypothesis": "Check first-dashboard path and capture timing, console, and copy issues around project creation prompts.",
    },
    {
        "name": "Browserbase sign-up",
        "url": "https://www.browserbase.com/sign-up",
        "segment": "browser_agent_infra",
        "keywords": ["browserbase", "sign", "browser"],
        "why_fit": "A browser-automation infrastructure vendor is a meta-fit: their own onboarding can be evaluated with the service category they sell.",
        "demo_hypothesis": "Create a concise dogfood-style onboarding QA artifact focused on signup clarity and developer activation path.",
    },
    {
        "name": "Vercel signup",
        "url": "https://vercel.com/signup",
        "segment": "developer_platform",
        "keywords": ["vercel", "sign", "deploy"],
        "why_fit": "Deployment-platform onboarding is high-volume and depends on auth/provider branching, dashboard load, and first-deploy guidance.",
        "demo_hypothesis": "Assess whether a fresh visitor can understand account options and first-deploy path; capture browser errors and blocked states.",
    },
]


@dataclass
class TargetEvidence:
    name: str
    url: str
    segment: str
    why_fit: str
    demo_hypothesis: str
    http_status: int | None
    bytes_read: int
    keyword_hits: list[str]
    title: str | None
    ok: bool
    error: str | None = None


def strip_html(value: str) -> str:
    value = re.sub(r"<script\b.*?</script>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<style\b.*?</style>", " ", value, flags=re.I | re.S)
    value = re.sub(r"<[^>]+>", " ", value)
    value = value.replace("&nbsp;", " ").replace("&amp;", "&").replace("&#x27;", "'")
    return re.sub(r"\s+", " ", value).strip()


def extract_title(html: str) -> str | None:
    match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.I | re.S)
    if not match:
        return None
    return strip_html(match.group(1))[:140] or None


def fetch_url(url: str, timeout: int) -> tuple[int, bytes]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "HermesAutonomyBrowserAgentProspectValidator/1.0 (+https://github.com/hiveminderbot/autonomy-high-signal-news)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        status = int(getattr(response, "status", response.getcode()))
        return status, response.read()


def collect_target(target: dict, timeout: int, fetcher: Callable[[str, int], tuple[int, bytes]] = fetch_url) -> TargetEvidence:
    try:
        status, body = fetcher(target["url"], timeout)
        html = body.decode("utf-8", "ignore")
        text = strip_html(html)
        haystack = f"{target['url']} {target['name']} {text}".lower()
        hits = [kw for kw in target["keywords"] if kw.lower() in haystack]
        ok = 200 <= status < 400 and len(body) >= 5_000 and len(hits) >= 2
        return TargetEvidence(
            name=target["name"],
            url=target["url"],
            segment=target["segment"],
            why_fit=target["why_fit"],
            demo_hypothesis=target["demo_hypothesis"],
            http_status=status,
            bytes_read=len(body),
            keyword_hits=hits,
            title=extract_title(html),
            ok=ok,
            error=None if ok else f"status={status} bytes={len(body)} keyword_hits={hits}",
        )
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return TargetEvidence(
            name=target["name"],
            url=target["url"],
            segment=target["segment"],
            why_fit=target["why_fit"],
            demo_hypothesis=target["demo_hypothesis"],
            http_status=None,
            bytes_read=0,
            keyword_hits=[],
            title=None,
            ok=False,
            error=f"{type(exc).__name__}: {exc}",
        )


def _stable_target_record(item: TargetEvidence) -> dict:
    record = asdict(item)
    record.pop("bytes_read", None)
    record["bytes_read_minimum_met"] = item.bytes_read >= 5_000
    return record


def make_payload(evidence: list[TargetEvidence], fetched_at: str) -> dict:
    healthy = [item for item in evidence if item.ok]
    segments = sorted({item.segment for item in healthy})
    passed = len(healthy) >= 5 and len(segments) >= 4
    recommendation = "ADOPT_BROWSER_AGENT_QA_PROSPECT_SPRINT" if passed else "REJECT_UNTIL_PROSPECT_EVIDENCE_HEALTHY"
    ranked = sorted(healthy, key=lambda item: (item.segment != "browser_agent_infra", item.name))[:5]
    return {
        "artifact": "browser-agent-qa-prospect-shortlist-20260505",
        "fetched_at": fetched_at,
        "scope": "Non-OpenViking browser-agent QA service experiment: live public signup/onboarding prospect shortlist.",
        "recommendation": recommendation,
        "acceptance": {
            "passed": passed,
            "healthy_targets": len(healthy),
            "minimum_targets": 5,
            "segments_present": segments,
            "minimum_segments": 4,
        },
        "bottom_line": "A browser-agent QA service sprint now has enough live public onboarding surfaces to run a concrete demo/outreach experiment rather than more abstract tooling research.",
        "shortlist": [_stable_target_record(item) for item in ranked],
        "all_target_evidence": [_stable_target_record(item) for item in evidence],
        "next_experiment": {
            "name": "One-day public onboarding QA demo sprint",
            "success_gate": "Run browser-agent/Playwright diagnostics against the top 3 reachable targets and adopt the service wedge only if at least one artifact contains a reproducible public UX, console, network, or copy issue useful enough for credible outreach.",
            "deliverables": [
                "One reproducible public-flow QA report per selected target, with screenshots/log snippets and no private-account actions beyond public signup entry points.",
                "One fixed-price service offer paragraph tied to the strongest report.",
                "A reject memo if no externally useful finding emerges within one day.",
            ],
        },
        "not_revenue_ready_because": [
            "no live browser-agent runs against these targets were executed in this task",
            "no prospect contacted and no reply/revenue evidence exists yet",
            "no measured agent cost per useful report yet",
            "must respect public-site terms, rate limits, and avoid private data entry before outreach use",
        ],
    }


def render_report(payload: dict) -> str:
    lines = [
        "# Browser-agent QA prospect shortlist — 2026-05-05",
        "",
        f"Recommendation: **{payload['recommendation']}**",
        "",
        "## Bottom line",
        payload["bottom_line"],
        "",
        "This is a prospect/demo shortlist, not proof of revenue and not a capital-ready claim.",
        "",
        "## Top shortlist",
    ]
    for item in payload["shortlist"]:
        lines.extend([
            f"- **{item['name']}** ({item['segment']}) — {item['url']}",
            f"  - Title: {item['title'] or '(none)'}",
            f"  - HTTP: {item['http_status']} bytes_minimum_met: {item['bytes_read_minimum_met']} keyword_hits: {', '.join(item['keyword_hits'])}",
            f"  - Why fit: {item['why_fit']}",
            f"  - Demo hypothesis: {item['demo_hypothesis']}",
        ])
    lines.extend([
        "",
        "## Next experiment",
        f"**{payload['next_experiment']['name']}**",
        "",
    ])
    for deliverable in payload["next_experiment"]["deliverables"]:
        lines.append(f"- {deliverable}")
    lines.extend([
        "",
        f"Success gate: {payload['next_experiment']['success_gate']}",
        "",
        "## Not revenue-ready because",
    ])
    for reason in payload["not_revenue_ready_because"]:
        lines.append(f"- {reason}")
    lines.extend(["", "## All source evidence"])
    for item in payload["all_target_evidence"]:
        status = "OK" if item["ok"] else "FAIL"
        lines.extend([
            f"- **{item['name']}** — {status}",
            f"  - URL: {item['url']}",
            f"  - HTTP: {item['http_status']} bytes_minimum_met: {item['bytes_read_minimum_met']}",
            f"  - Keyword hits: {', '.join(item['keyword_hits']) if item['keyword_hits'] else '(none)'}",
            f"  - Error: {item['error'] or '(none)'}",
        ])
    lines.extend([
        "",
        "## Validation criteria",
        f"- Healthy targets: {payload['acceptance']['healthy_targets']} / {payload['acceptance']['minimum_targets']}",
        f"- Segments present: {', '.join(payload['acceptance']['segments_present'])}",
        f"- Passed: {payload['acceptance']['passed']}",
        "",
    ])
    return "\n".join(lines)


def run(args: argparse.Namespace) -> dict:
    fetched_at = args.artifact_timestamp or datetime.now(timezone.utc).isoformat()
    evidence = [collect_target(target, args.timeout) for target in TARGETS]
    payload = make_payload(evidence, fetched_at)
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.report_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    args.report_output.write_text(render_report(payload) + "\n")

    for evidence_item, item in zip(evidence, payload["all_target_evidence"], strict=True):
        print(f"SOURCE {item['url']} STATUS {item['http_status']} BYTES {evidence_item.bytes_read} OK {item['ok']}")
    print(f"REPORT {args.report_output} BYTES {args.report_output.stat().st_size}")
    print(f"SUMMARY {args.json_output} BYTES {args.json_output.stat().st_size}")
    if payload["acceptance"]["passed"]:
        print("BROWSER_AGENT_QA_PROSPECT_SHORTLIST_E2E_OK")
    else:
        print("TASK INCOMPLETE: prospect evidence threshold not met")
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
