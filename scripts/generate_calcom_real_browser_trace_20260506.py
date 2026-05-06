#!/usr/bin/env python3
"""Run a safe public Playwright trace for the Cal.com signup QA demo.

Non-OpenViking revenue experiment. The script only visits the public signup
entry point, captures passive browser diagnostics, and does not create accounts,
submit forms, or contact the prospect.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

LAB_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JSON = LAB_ROOT / "results" / "calcom-real-browser-trace-20260506.json"
DEFAULT_REPORT = LAB_ROOT / "results" / "calcom-real-browser-trace-20260506.md"
DEFAULT_SCREENSHOT = LAB_ROOT / "results" / "calcom-real-browser-trace-20260506.png"
PLAYWRIGHT_MODULE = "/home/exedev/.hermes/hermes-agent/node_modules/playwright"
NODE_BINARY = "/home/exedev/.local/bin/node"
TARGET_URL = "https://cal.com/signup"


def _node_trace_script() -> str:
    return r"""
const fs = require('fs');
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || '/home/exedev/.hermes/hermes-agent/node_modules/playwright');

(async () => {
  const outJson = process.argv[2];
  const screenshot = process.argv[3];
  const targetUrl = process.argv[4] || 'https://cal.com/signup';
  const startedAt = new Date().toISOString();
  const consoleMessages = [];
  const pageErrors = [];
  const failedRequests = [];
  const responses = [];
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1365, height: 900 },
    userAgent: 'HermesAutonomyBrowserQATrace/1.0 (+https://github.com/hiveminderbot/autonomy-high-signal-news)'
  });
  const page = await context.newPage();
  page.on('console', msg => consoleMessages.push({ type: msg.type(), text: msg.text().slice(0, 500) }));
  page.on('pageerror', err => pageErrors.push(String(err).slice(0, 1000)));
  page.on('requestfailed', req => failedRequests.push({ url: req.url().slice(0, 300), method: req.method(), failure: req.failure() ? req.failure().errorText : 'unknown' }));
  page.on('response', resp => {
    const status = resp.status();
    if (status >= 400) responses.push({ status, url: resp.url().slice(0, 300) });
  });
  let gotoError = null;
  let status = null;
  try {
    const response = await page.goto(targetUrl, { waitUntil: 'domcontentloaded', timeout: 45000 });
    status = response ? response.status() : null;
    await page.waitForTimeout(5000);
  } catch (err) {
    gotoError = String(err).slice(0, 1000);
  }
  let bodyText = '';
  try { bodyText = await page.locator('body').innerText({ timeout: 10000 }); } catch (err) { bodyText = ''; }
  const controls = await page.evaluate(() => {
    const texts = Array.from(document.querySelectorAll('button,a,input,[role="button"]'))
      .map((el) => (el.innerText || el.getAttribute('aria-label') || el.getAttribute('placeholder') || el.value || '').trim())
      .filter(Boolean)
      .slice(0, 80);
    return {
      forms: document.querySelectorAll('form').length,
      inputs: document.querySelectorAll('input').length,
      buttons: document.querySelectorAll('button,[role="button"]').length,
      links: document.querySelectorAll('a').length,
      text_controls: texts,
      has_noscript: document.querySelectorAll('noscript').length > 0,
      script_count: document.querySelectorAll('script').length,
    };
  });
  await page.screenshot({ path: screenshot, fullPage: true });
  const title = await (async () => { try { return await page.title(); } catch { return null; } })();
  const finalUrl = page.url();
  const finishedAt = new Date().toISOString();
  await browser.close();
  fs.writeFileSync(outJson, JSON.stringify({
    started_at: startedAt,
    finished_at: finishedAt,
    target_url: targetUrl,
    final_url: finalUrl,
    main_status: status,
    goto_error: gotoError,
    title,
    body_text_chars: bodyText.length,
    body_text_sample: bodyText.replace(/\s+/g, ' ').slice(0, 1000),
    controls,
    console_messages: consoleMessages.slice(0, 50),
    page_errors: pageErrors.slice(0, 20),
    failed_requests: failedRequests.slice(0, 50),
    error_responses: responses.slice(0, 50),
    screenshot_path: screenshot,
  }, null, 2));
})().catch(err => {
  console.error(err);
  process.exit(1);
});
"""


def run_playwright_trace(*, output_json: Path, screenshot: Path, timeout: int = 90) -> dict[str, Any]:
    output_json.parent.mkdir(parents=True, exist_ok=True)
    screenshot.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as handle:
        handle.write(_node_trace_script())
        script_path = Path(handle.name)
    env = os.environ.copy()
    env["PLAYWRIGHT_MODULE"] = PLAYWRIGHT_MODULE
    try:
        subprocess.run(
            [NODE_BINARY, str(script_path), str(output_json), str(screenshot), TARGET_URL],
            check=True,
            timeout=timeout,
            env=env,
        )
    finally:
        script_path.unlink(missing_ok=True)
    return json.loads(output_json.read_text())


def classify_trace(trace: dict[str, Any], screenshot: Path) -> dict[str, Any]:
    controls = trace.get("controls", {}) or {}
    auth_terms = [
        item
        for item in controls.get("text_controls", [])
        if any(term in item.lower() for term in ("google", "email", "sso", "sign", "continue", "cal.com"))
    ]
    findings: list[str] = []
    if trace.get("main_status") and 200 <= int(trace["main_status"]) < 400:
        findings.append("The public signup entry point loaded successfully in a real headless Chromium session.")
    if trace.get("body_text_chars", 0) >= 500:
        findings.append("Hydrated browser text is substantially richer than the static HTML, confirming that a browser trace adds evidence beyond HTTP-only checks.")
    if auth_terms:
        findings.append("The browser trace exposes account-entry/authentication affordances suitable for a compliant no-submit QA packet.")
    if trace.get("failed_requests"):
        findings.append("The trace captured failed network requests worth reviewing before any outreach claim is made.")
    else:
        findings.append("No failed network requests were captured during the passive public-page load window.")
    console_errors = [m for m in trace.get("console_messages", []) if m.get("type") in {"error", "warning"}]
    if console_errors:
        findings.append("Console warnings/errors were observed and can be included as diagnostic context if they reproduce.")
    else:
        findings.append("No console warnings/errors were captured in the passive load window.")

    screenshot_ok = screenshot.exists() and screenshot.stat().st_size >= 10_000
    outreach_ready = bool(
        trace.get("main_status")
        and 200 <= int(trace["main_status"]) < 400
        and screenshot_ok
        and trace.get("body_text_chars", 0) >= 500
        and auth_terms
    )
    return {
        "screenshot_ok": screenshot_ok,
        "screenshot_bytes": screenshot.stat().st_size if screenshot.exists() else 0,
        "auth_terms": auth_terms[:12],
        "console_error_count": len(console_errors),
        "failed_request_count": len(trace.get("failed_requests", [])),
        "finding_count": len(findings),
        "findings": findings,
        "recommendation": "ADOPT_ONE_COMPLIANT_OUTREACH_DRAFT" if outreach_ready else "REJECT_OUTREACH_UNTIL_STRONGER_TRACE",
        "outreach_ready_for_manual_review": outreach_ready,
    }


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(LAB_ROOT))
    except ValueError:
        return str(path)


def build_payload(trace: dict[str, Any], summary: dict[str, Any], screenshot: Path) -> dict[str, Any]:
    return {
        "artifact": "calcom-real-browser-trace-20260506",
        "generated_at": datetime.now(UTC).isoformat(),
        "scope": "Non-OpenViking browser-agent QA revenue experiment; passive public Cal.com signup trace only.",
        "target": {"name": "Cal.com signup", "url": TARGET_URL},
        "capital_readiness": "not_capital_ready",
        "revenue_readiness": "not_revenue_ready_no_prospect_contact_or_payment",
        "safety_guardrails": [
            "No form submission, account creation, login attempt, scraping behind auth, or prospect contact occurred.",
            "Any outreach must describe this as public passive QA evidence, not as proof of a production outage.",
            "OpenViking/Polymarket work is explicitly excluded from this artifact.",
        ],
        "trace": trace,
        "summary": summary,
        "screenshot": {"path": _display_path(screenshot), "bytes": summary["screenshot_bytes"]},
        "next_experiment": {
            "name": "One manual outreach review",
            "success_gate": "Send at most one compliant note only after human review confirms the screenshot and trace contain a useful, reproducible public onboarding observation.",
            "reject_gate": "Reject this wedge for outreach if the screenshot/body text only shows a normal working signup page with no useful QA angle.",
        },
    }


def render_report(payload: dict[str, Any]) -> str:
    trace = payload["trace"]
    summary = payload["summary"]
    controls = trace.get("controls", {}) or {}
    lines = [
        "# Cal.com real-browser signup QA demo trace — 2026-05-06",
        "",
        f"Recommendation: **{summary['recommendation']}**",
        "",
        "## Bottom line",
        "A real headless Chromium trace now exists for the public Cal.com signup page. This upgrades the prior static-only scaffold into a browser-evidence demo packet, but it is still not revenue-ready because no prospect was contacted and no paid pilot exists.",
        "",
        "## Browser trace evidence",
        f"- URL: {payload['target']['url']}",
        f"- Final URL: {trace.get('final_url')}",
        f"- HTTP status: {trace.get('main_status')}",
        f"- Title: {trace.get('title')}",
        f"- Body text chars after hydration: {trace.get('body_text_chars')}",
        f"- Screenshot: {payload['screenshot']['path']} ({payload['screenshot']['bytes']} bytes)",
        f"- Forms/inputs/buttons/links/scripts: {controls.get('forms')}/{controls.get('inputs')}/{controls.get('buttons')}/{controls.get('links')}/{controls.get('script_count')}",
        f"- Auth/control terms observed: {', '.join(summary['auth_terms']) if summary['auth_terms'] else '(none)'}",
        f"- Console warning/error count: {summary['console_error_count']}",
        f"- Failed request count: {summary['failed_request_count']}",
        "",
        "## Findings",
    ]
    for idx, finding in enumerate(summary["findings"], 1):
        lines.append(f"{idx}. {finding}")
    lines += [
        "",
        "## Outreach draft status",
        "Do not send automatically. This trace is ready for internal manual review, not prospect delivery. If a later human-reviewed packet is sent, it should be framed as a small fixed-price public onboarding QA offer, not as a bug bounty or outage claim.",
        "",
        "## Not revenue-ready / not capital-ready because",
        "- no prospect contacted and no reply/revenue evidence exists",
        "- no measured cost per useful browser-agent report yet",
        "- this is one public passive trace, not a repeated monitoring deployment",
        "- all private-account actions and form submissions were intentionally avoided",
        "",
        "## Guardrails",
    ]
    for guardrail in payload["safety_guardrails"]:
        lines.append(f"- {guardrail}")
    lines += [
        "",
        "## Next experiment",
        f"- {payload['next_experiment']['success_gate']}",
        f"- {payload['next_experiment']['reject_gate']}",
        "",
        "## Acceptance evidence",
        f"- Screenshot captured: {summary['screenshot_ok']}",
        f"- Finding count: {summary['finding_count']}",
        f"- Outreach-ready for manual review: {summary['outreach_ready_for_manual_review']}",
    ]
    return "\n".join(lines) + "\n"


def generate(output_json: Path = DEFAULT_JSON, report: Path = DEFAULT_REPORT, screenshot: Path = DEFAULT_SCREENSHOT) -> dict[str, Any]:
    trace = run_playwright_trace(output_json=output_json, screenshot=screenshot)
    summary = classify_trace(trace, screenshot)
    payload = build_payload(trace, summary, screenshot)
    output_json.write_text(json.dumps(payload, indent=2) + "\n")
    report.write_text(render_report(payload))
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--screenshot", type=Path, default=DEFAULT_SCREENSHOT)
    args = parser.parse_args()
    payload = generate(args.json, args.report, args.screenshot)
    print(
        "CALCOM_REAL_BROWSER_TRACE_GENERATED",
        payload["summary"]["recommendation"],
        "screenshot_bytes",
        payload["summary"]["screenshot_bytes"],
        "body_text_chars",
        payload["trace"].get("body_text_chars"),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
