#!/usr/bin/env python3
"""Generate public signup/onboarding diagnostics for browser-agent QA prospects.

This is a non-OpenViking revenue-experiment artifact. It does not create
accounts, submit forms, or touch private data. It uses public HTTP evidence to
identify whether the existing browser-agent QA prospect sprint has at least one
credible externally useful finding worth converting into outreach/demo work.
"""
from __future__ import annotations

import argparse
import json
import re
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Iterable

LAB_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JSON = LAB_ROOT / "results" / "browser-agent-signup-diagnostics-20260506.json"
DEFAULT_REPORT = LAB_ROOT / "results" / "browser-agent-signup-diagnostics-20260506.md"

TARGETS = [
    {
        "name": "Browserbase sign-up",
        "url": "https://www.browserbase.com/sign-up",
        "segment": "browser_agent_infra",
        "expected_terms": ["browserbase", "email", "password", "continue"],
        "demo_angle": "Dogfood the browser-automation vendor's own signup surface for static fallback and first-step clarity.",
    },
    {
        "name": "Cal.com signup",
        "url": "https://cal.com/signup",
        "segment": "scheduling_saas",
        "expected_terms": ["cal", "sign", "signup", "account"],
        "demo_angle": "Check whether account creation/calendar-onboarding entry points expose enough first-step content for automated QA triage.",
    },
    {
        "name": "Linear signup",
        "url": "https://linear.app/signup",
        "segment": "collaboration_saas",
        "expected_terms": ["linear", "signup", "workspace", "loading"],
        "demo_angle": "Check whether team/workspace signup has useful no-JS/static fallback and a diagnosable first visible state.",
    },
]

IDENTITY_PROVIDER_TERMS = ["google", "github", "sso", "saml", "oauth", "continue"]


@dataclass
class SignupDiagnostic:
    name: str
    url: str
    segment: str
    demo_angle: str
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
    has_noscript: bool
    expected_term_hits: list[str]
    identity_provider_hits: list[str]
    findings: list[str]
    outreach_worthy: bool
    ok: bool
    error: str | None = None


def strip_html(html: str) -> str:
    html = re.sub(r"<script\b.*?</script>", " ", html, flags=re.I | re.S)
    html = re.sub(r"<style\b.*?</style>", " ", html, flags=re.I | re.S)
    html = re.sub(r"<[^>]+>", " ", html)
    entities = {
        "&nbsp;": " ",
        "&amp;": "&",
        "&#x27;": "'",
        "&quot;": '"',
        "&lt;": "<",
        "&gt;": ">",
    }
    for old, new in entities.items():
        html = html.replace(old, new)
    return re.sub(r"\s+", " ", html).strip()


def extract_title(html: str) -> str | None:
    match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.I | re.S)
    if not match:
        return None
    return strip_html(match.group(1))[:140] or None


def fetch_url(url: str, timeout: int) -> tuple[int, str, bytes]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "HermesAutonomySignupDiagnostics/1.0 (+https://github.com/hiveminderbot/autonomy-high-signal-news)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        status = int(getattr(response, "status", response.getcode()))
        return status, response.geturl(), response.read()


def _count(pattern: str, html: str) -> int:
    return len(re.findall(pattern, html, flags=re.I))


def classify_findings(
    *,
    status: int,
    visible_text_chars: int,
    form_count: int,
    input_count: int,
    button_count: int,
    script_count: int,
    has_noscript: bool,
    expected_hits: Iterable[str],
    identity_hits: Iterable[str],
) -> list[str]:
    findings: list[str] = []
    expected_hits = list(expected_hits)
    identity_hits = list(identity_hits)
    if not (200 <= status < 400):
        findings.append(f"Public signup URL returned HTTP {status}; browser-agent run should verify whether redirects or blockers are intended.")
    if visible_text_chars < 80:
        findings.append(
            "Static HTML exposes almost no visible signup copy before JavaScript execution; this is a credible browser-agent QA demo target for blank/loading-state and no-JS fallback capture."
        )
    if script_count >= 20 and not has_noscript:
        findings.append(
            f"Heavy JavaScript surface ({script_count} script tags) has no <noscript> fallback; browser diagnostics should capture first-paint/loading and console/network failures."
        )
    if form_count == 0 and input_count == 0 and visible_text_chars < 200:
        findings.append(
            "No static form/input controls are present in the fetched signup HTML; a public browser run can validate whether account entry is discoverable after hydration."
        )
    if form_count > 0 and input_count >= 2 and button_count > 0:
        findings.append(
            "Static signup controls are visible without account creation; this is a good baseline target for copy, validation, and accessibility diagnostics."
        )
    if len(expected_hits) < 2:
        findings.append(
            "Fetched page text does not expose enough expected signup/product terminology for a clear static first-step; useful to verify in a browser transcript."
        )
    if not identity_hits and visible_text_chars < 500:
        findings.append(
            "No obvious identity-provider/auth option text appears in the public static response; browser-agent run should document auth-option discoverability."
        )
    return findings


def collect_target(target: dict, timeout: int, fetcher: Callable[[str, int], tuple[int, str, bytes]] = fetch_url) -> SignupDiagnostic:
    try:
        status, final_url, body = fetcher(target["url"], timeout)
        html = body.decode("utf-8", "ignore")
        text = strip_html(html)
        haystack = f"{target['name']} {target['url']} {final_url} {text}".lower()
        expected_hits = [term for term in target["expected_terms"] if term.lower() in haystack]
        identity_hits = [term for term in IDENTITY_PROVIDER_TERMS if term in haystack]
        form_count = _count(r"<form\b", html)
        input_count = _count(r"<input\b", html)
        button_count = _count(r"<button\b", html)
        script_count = _count(r"<script\b", html)
        has_noscript = bool(re.search(r"<noscript\b", html, flags=re.I))
        findings = classify_findings(
            status=status,
            visible_text_chars=len(text),
            form_count=form_count,
            input_count=input_count,
            button_count=button_count,
            script_count=script_count,
            has_noscript=has_noscript,
            expected_hits=expected_hits,
            identity_hits=identity_hits,
        )
        outreach_worthy = 200 <= status < 400 and bool(findings)
        return SignupDiagnostic(
            name=target["name"],
            url=target["url"],
            segment=target["segment"],
            demo_angle=target["demo_angle"],
            http_status=status,
            final_url=final_url,
            bytes_read=len(body),
            title=extract_title(html),
            visible_text_chars=len(text),
            visible_text_sample=text[:320],
            form_count=form_count,
            input_count=input_count,
            button_count=button_count,
            script_count=script_count,
            has_noscript=has_noscript,
            expected_term_hits=expected_hits,
            identity_provider_hits=identity_hits,
            findings=findings,
            outreach_worthy=outreach_worthy,
            ok=200 <= status < 400 and len(body) >= 5_000,
        )
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return SignupDiagnostic(
            name=target["name"],
            url=target["url"],
            segment=target["segment"],
            demo_angle=target["demo_angle"],
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
            has_noscript=False,
            expected_term_hits=[],
            identity_provider_hits=[],
            findings=[],
            outreach_worthy=False,
            ok=False,
            error=f"{type(exc).__name__}: {exc}",
        )


def stable_record(item: SignupDiagnostic) -> dict:
    record = asdict(item)
    record.pop("bytes_read", None)
    record["bytes_read_minimum_met"] = item.bytes_read >= 5_000
    return record


def make_payload(diagnostics: list[SignupDiagnostic], artifact_timestamp: str) -> dict:
    reachable = [item for item in diagnostics if item.ok]
    outreach_targets = [item for item in reachable if item.outreach_worthy]
    passed = len(reachable) >= 3 and len(outreach_targets) >= 1
    recommendation = "ADOPT_PUBLIC_BROWSER_AGENT_QA_DEMO" if passed else "REJECT_UNTIL_PUBLIC_DIAGNOSTIC_FINDING"
    strongest = max(outreach_targets, key=lambda item: len(item.findings), default=None)
    return {
        "artifact": "browser-agent-signup-diagnostics-20260506",
        "artifact_timestamp": artifact_timestamp,
        "scope": "Non-OpenViking public signup diagnostics for a browser-agent QA revenue experiment; no account creation or private-data entry.",
        "recommendation": recommendation,
        "acceptance": {
            "passed": passed,
            "reachable_targets": len(reachable),
            "minimum_reachable_targets": 3,
            "outreach_worthy_targets": len(outreach_targets),
            "minimum_outreach_worthy_targets": 1,
        },
        "bottom_line": (
            "The browser-agent QA wedge has a concrete public-flow demo path: at least one top prospect exposes a diagnosable signup/onboarding surface that can be converted into a safe outreach artifact."
            if passed
            else "The browser-agent QA wedge should not move to outreach until public diagnostics surface at least one credible reproducible finding."
        ),
        "strongest_target": stable_record(strongest) if strongest else None,
        "diagnostics": [stable_record(item) for item in diagnostics],
        "fixed_price_offer_paragraph": (
            "Offer: I run a fixed-price public onboarding QA pass against your signup flow using browser automation plus HTTP/console/network evidence, then deliver a concise report with reproducible states, screenshots/log excerpts, and prioritized fixes. No private user data or account abuse; the first pass focuses only on public entry points and conversion-blocking friction."
        ),
        "not_revenue_ready_because": [
            "no prospect has been contacted and no paid reply exists",
            "these diagnostics are public HTTP/static evidence, not a full Playwright screenshot/console trace yet",
            "browser-agent cost per useful report is still unmeasured",
        ],
        "next_experiment": {
            "name": "One-prospect browser-agent QA demo packet",
            "target": strongest.name if strongest else None,
            "success_gate": "Run a real browser automation trace against the strongest public target, attach screenshots/console/network snippets, and send one compliant outreach email only if the report contains a reproducible conversion or reliability issue.",
        },
    }


def render_report(payload: dict) -> str:
    lines = [
        "# Browser-agent signup diagnostics — 2026-05-06",
        "",
        f"Recommendation: **{payload['recommendation']}**",
        "",
        "## Bottom line",
        payload["bottom_line"],
        "",
        "## Fixed-price service offer draft",
        payload["fixed_price_offer_paragraph"],
        "",
        "## Strongest outreach target",
    ]
    strongest = payload.get("strongest_target")
    if strongest:
        lines.extend([
            f"- **{strongest['name']}** — {strongest['url']}",
            f"  - Segment: {strongest['segment']}",
            f"  - Title: {strongest['title']}",
            f"  - Static visible text chars: {strongest['visible_text_chars']}",
            f"  - Forms/inputs/buttons/scripts: {strongest['form_count']}/{strongest['input_count']}/{strongest['button_count']}/{strongest['script_count']}",
        ])
        for finding in strongest["findings"]:
            lines.append(f"  - Finding: {finding}")
    else:
        lines.append("- None; reject outreach until a reproducible public finding exists.")
    lines.extend(["", "## Per-target diagnostics"])
    for item in payload["diagnostics"]:
        lines.extend([
            f"- **{item['name']}** — {item['url']}",
            f"  - HTTP: {item['http_status']} final_url: {item['final_url']} bytes_minimum_met: {item['bytes_read_minimum_met']}",
            f"  - Title: {item['title']}",
            f"  - Static visible text chars: {item['visible_text_chars']} sample: {item['visible_text_sample']}",
            f"  - Forms/inputs/buttons/scripts/noscript: {item['form_count']}/{item['input_count']}/{item['button_count']}/{item['script_count']}/{item['has_noscript']}",
            f"  - Expected hits: {', '.join(item['expected_term_hits']) or '(none)'}",
            f"  - Identity/auth hits: {', '.join(item['identity_provider_hits']) or '(none)'}",
            f"  - Outreach-worthy: {item['outreach_worthy']}",
        ])
        if item["findings"]:
            for finding in item["findings"]:
                lines.append(f"  - Finding: {finding}")
        if item["error"]:
            lines.append(f"  - Error: {item['error']}")
    lines.extend([
        "",
        "## Acceptance evidence",
        f"- Reachable targets: {payload['acceptance']['reachable_targets']} / {payload['acceptance']['minimum_reachable_targets']}",
        f"- Outreach-worthy targets: {payload['acceptance']['outreach_worthy_targets']} / {payload['acceptance']['minimum_outreach_worthy_targets']}",
        f"- Passed: {payload['acceptance']['passed']}",
        "",
        "## Not revenue-ready because",
    ])
    lines.extend(f"- {reason}" for reason in payload["not_revenue_ready_because"])
    lines.extend([
        "",
        "## Next experiment",
        f"- Name: {payload['next_experiment']['name']}",
        f"- Target: {payload['next_experiment']['target']}",
        f"- Success gate: {payload['next_experiment']['success_gate']}",
        "",
    ])
    return "\n".join(lines)


def run(args: argparse.Namespace) -> dict:
    diagnostics = [collect_target(target, args.timeout) for target in TARGETS]
    payload = make_payload(diagnostics, args.artifact_timestamp)
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.report_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    args.report_output.write_text(render_report(payload))
    for item in diagnostics:
        print(
            "SOURCE",
            item.http_status,
            item.bytes_read,
            item.url,
            "OUTREACH_WORTHY",
            item.outreach_worthy,
            "FINDINGS",
            len(item.findings),
        )
    print(f"REPORT {args.report_output} BYTES {args.report_output.stat().st_size}")
    print(f"JSON {args.json_output} BYTES {args.json_output.stat().st_size}")
    print("BROWSER_AGENT_SIGNUP_DIAGNOSTICS_GENERATED_OK")
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=int, default=25)
    parser.add_argument("--artifact-timestamp", default="2026-05-06T00:00:00+00:00")
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
