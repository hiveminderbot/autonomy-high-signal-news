#!/usr/bin/env python3
"""Generate a source-backed Cal.com public signup QA demo packet.

Non-OpenViking revenue experiment. This script does not create accounts, submit
forms, or touch private data. It converts the existing browser-agent QA wedge
into a concrete prospect-facing packet using public HTTP evidence plus a safe
browser-run plan for the next Playwright/agent execution step.
"""
from __future__ import annotations

import argparse
import json
import re
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

LAB_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JSON = LAB_ROOT / "results" / "calcom-signup-browser-qa-20260505.json"
DEFAULT_REPORT = LAB_ROOT / "results" / "calcom-signup-browser-qa-20260505.md"
TARGET_URL = "https://cal.com/signup"


@dataclass
class SourceEvidence:
    name: str
    url: str
    http_status: int | None
    final_url: str | None
    bytes_read: int
    title: str | None
    visible_text_chars: int
    visible_text_sample: str
    form_count: int
    input_count: int
    button_count: int
    script_count: int
    noscript_count: int
    ok: bool
    error: str | None = None


def strip_html(html: str) -> str:
    html = re.sub(r"<script\b.*?</script>", " ", html, flags=re.I | re.S)
    html = re.sub(r"<style\b.*?</style>", " ", html, flags=re.I | re.S)
    html = re.sub(r"<[^>]+>", " ", html)
    for old, new in {
        "&nbsp;": " ",
        "&amp;": "&",
        "&#x27;": "'",
        "&quot;": '"',
        "&lt;": "<",
        "&gt;": ">",
    }.items():
        html = html.replace(old, new)
    return re.sub(r"\s+", " ", html).strip()


def extract_title(html: str) -> str | None:
    match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.I | re.S)
    if not match:
        return None
    return strip_html(match.group(1))[:140] or None


def fetch_url(url: str, timeout: int) -> tuple[int, str, bytes]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "HermesAutonomyCalcomSignupQA/1.0 (+https://github.com/hiveminderbot/autonomy-high-signal-news)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return int(getattr(resp, "status", resp.getcode())), resp.geturl(), resp.read()


def count(pattern: str, html: str) -> int:
    return len(re.findall(pattern, html, flags=re.I))


def collect_source(timeout: int, fetcher: Callable[[str, int], tuple[int, str, bytes]] = fetch_url) -> SourceEvidence:
    try:
        status, final_url, body = fetcher(TARGET_URL, timeout)
        html = body.decode("utf-8", "ignore")
        visible_text = strip_html(html)
        return SourceEvidence(
            name="Cal.com signup public HTML",
            url=TARGET_URL,
            http_status=status,
            final_url=final_url,
            bytes_read=len(body),
            title=extract_title(html),
            visible_text_chars=len(visible_text),
            visible_text_sample=visible_text[:260],
            form_count=count(r"<form\b", html),
            input_count=count(r"<input\b", html),
            button_count=count(r"<button\b", html),
            script_count=count(r"<script\b", html),
            noscript_count=count(r"<noscript\b", html),
            ok=200 <= status < 400 and len(body) >= 5_000,
        )
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return SourceEvidence(
            name="Cal.com signup public HTML",
            url=TARGET_URL,
            http_status=None,
            final_url=None,
            bytes_read=0,
            title=None,
            visible_text_chars=0,
            visible_text_sample="",
            form_count=0,
            input_count=0,
            button_count=0,
            script_count=0,
            noscript_count=0,
            ok=False,
            error=f"{type(exc).__name__}: {exc}",
        )


def build_payload(evidence: SourceEvidence, generated_at: str) -> dict:
    findings: list[dict[str, str]] = []
    if evidence.ok and evidence.visible_text_chars < 100:
        findings.append({
            "severity": "medium",
            "category": "resilience/first-paint",
            "finding": "The public signup HTML exposes almost no visible signup content before JavaScript hydration.",
            "why_it_matters": "A blank/minimal first response gives a browser-agent QA demo a concrete conversion-risk hypothesis: JS, CDN, CSP, or client runtime failures can strand new users before account creation options are visible.",
            "repro": f"Fetch {TARGET_URL}; observe title-only visible text and no static form controls in the HTTP response.",
        })
    if evidence.ok and evidence.script_count >= 20 and evidence.noscript_count == 0:
        findings.append({
            "severity": "low",
            "category": "progressive-enhancement",
            "finding": "The signup page is heavily JavaScript-driven and has no <noscript> fallback in the fetched HTML.",
            "why_it_matters": "This is not automatically a bug, but it is outreach-worthy because browser automation can cheaply verify whether the hydrated page degrades safely under common script/network failure modes.",
            "repro": f"Fetch {TARGET_URL}; count script tags and noscript tags in the response.",
        })
    if evidence.ok and evidence.form_count == 0 and evidence.input_count == 0:
        findings.append({
            "severity": "medium",
            "category": "signup-discoverability",
            "finding": "No form/input/button controls are present in the public static response.",
            "why_it_matters": "A paid QA monitor could repeatedly confirm whether account entry controls appear after hydration and capture regressions with screenshots/console/network logs.",
            "repro": f"Fetch {TARGET_URL}; static control counts are form=0/input=0/button=0.",
        })

    passed = evidence.ok and len(findings) >= 2
    recommendation = "ADOPT_OUTREACH_PACKET_AFTER_REAL_BROWSER_TRACE" if passed else "REJECT_UNTIL_SOURCE_SURFACE_HEALTHY"
    outreach_packet = {
        "subject": "Public signup-flow QA finding for Cal.com",
        "opening": "I ran a source-backed public-entry QA pass on Cal.com's signup URL and found a concrete browser-automation demo target: the initial HTML response exposes almost no signup affordances before hydration.",
        "offer": "I can run a fixed-price browser-agent QA pass that captures screenshots, console/network evidence, and reproducible steps for signup-flow resilience without creating accounts or touching private user data.",
        "guardrail": "Do not send this as a claim of a confirmed production bug until a real browser trace reproduces the hydrated/loading behavior; this packet is a compliant pre-outreach demo scaffold.",
    }
    return {
        "artifact": "calcom-signup-browser-qa-20260505",
        "scope": "Agent-service revenue experiment: public browser-agent QA demo packet for Cal.com signup, explicitly outside trading/parser work.",
        "generated_at": generated_at,
        "target": {"name": "Cal.com signup", "url": TARGET_URL, "segment": "scheduling_saas"},
        "source_evidence": asdict(evidence),
        "findings": findings,
        "outreach_packet": outreach_packet,
        "next_experiment": {
            "name": "One-prospect real-browser trace",
            "command_shape": "Run Playwright/browser-agent against https://cal.com/signup and capture screenshot + console + network failure evidence without account submission.",
            "success_gate": "Send outreach only if a real browser trace confirms a reproducible loading, console, network, accessibility, or copy issue useful to Cal.com.",
        },
        "acceptance": {
            "passed": passed,
            "recommendation": recommendation,
            "source_ok": evidence.ok,
            "finding_count": len(findings),
            "not_revenue_ready_reasons": [
                "no prospect contacted and no paid reply/revenue evidence exists",
                "this run used public HTTP/static evidence; a real browser screenshot/console trace is still required before outreach",
                "browser-agent cost per useful report remains unmeasured",
            ],
        },
    }


def write_report(payload: dict, path: Path) -> None:
    src = payload["source_evidence"]
    lines = [
        "# Cal.com signup browser-agent QA demo packet — 2026-05-05",
        "",
        f"Recommendation: **{payload['acceptance']['recommendation']}**",
        "",
        "## Bottom line",
        "Cal.com remains a credible first outreach target for a browser-agent QA service, but the honest next conversion step is a real browser trace before any prospect email is sent.",
        "",
        "## Source evidence",
        f"- URL: {src['url']}",
        f"- HTTP: {src['http_status']} final_url: {src['final_url']} bytes: {src['bytes_read']} ok: {src['ok']}",
        f"- Title: {src['title']}",
        f"- Static visible text chars: {src['visible_text_chars']} sample: {src['visible_text_sample'] or '(none)'}",
        f"- Forms/inputs/buttons/scripts/noscript: {src['form_count']}/{src['input_count']}/{src['button_count']}/{src['script_count']}/{src['noscript_count']}",
        f"- Error: {src['error'] or '(none)'}",
        "",
        "## Findings for a prospect-facing QA packet",
    ]
    for idx, finding in enumerate(payload["findings"], 1):
        lines += [
            f"{idx}. **{finding['finding']}**",
            f"   - Severity/category: {finding['severity']} / {finding['category']}",
            f"   - Why it matters: {finding['why_it_matters']}",
            f"   - Repro: {finding['repro']}",
        ]
    lines += [
        "",
        "## Outreach packet draft (do not send until browser trace passes)",
        f"- Subject: {payload['outreach_packet']['subject']}",
        f"- Opening: {payload['outreach_packet']['opening']}",
        f"- Offer: {payload['outreach_packet']['offer']}",
        f"- Guardrail: {payload['outreach_packet']['guardrail']}",
        "",
        "## Next experiment",
        f"- Name: {payload['next_experiment']['name']}",
        f"- Command shape: {payload['next_experiment']['command_shape']}",
        f"- Success gate: {payload['next_experiment']['success_gate']}",
        "",
        "## Not revenue-ready because",
    ]
    lines += [f"- {reason}" for reason in payload["acceptance"]["not_revenue_ready_reasons"]]
    lines += [
        "",
        "## Acceptance evidence",
        f"- Source healthy: {payload['acceptance']['source_ok']}",
        f"- Finding count: {payload['acceptance']['finding_count']}",
        f"- Passed: {payload['acceptance']['passed']}",
        "",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--timeout", type=int, default=25)
    args = parser.parse_args()

    evidence = collect_source(args.timeout)
    payload = build_payload(evidence, datetime.now(timezone.utc).isoformat())
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_report(payload, args.report)
    print(f"JSON {args.json} BYTES {args.json.stat().st_size}")
    print(f"REPORT {args.report} BYTES {args.report.stat().st_size}")
    print(f"SOURCE {evidence.http_status} {evidence.bytes_read} {evidence.url}")
    print(f"RECOMMENDATION {payload['acceptance']['recommendation']}")
    print("CALCOM_SIGNUP_BROWSER_QA_GENERATED")
    return 0 if payload["acceptance"]["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
