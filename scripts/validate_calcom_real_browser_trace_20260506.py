#!/usr/bin/env python3
"""Validate the Cal.com real-browser trace artifact and print E2E sentinels."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JSON = LAB_ROOT / "results" / "calcom-real-browser-trace-20260506.json"
DEFAULT_REPORT = LAB_ROOT / "results" / "calcom-real-browser-trace-20260506.md"
DEFAULT_SCREENSHOT = LAB_ROOT / "results" / "calcom-real-browser-trace-20260506.png"


def validate(payload_path: Path = DEFAULT_JSON, report_path: Path = DEFAULT_REPORT, screenshot_path: Path = DEFAULT_SCREENSHOT) -> dict:
    payload = json.loads(payload_path.read_text())
    report = report_path.read_text()
    assert payload["artifact"] == "calcom-real-browser-trace-20260506"
    assert payload["capital_readiness"] == "not_capital_ready"
    assert payload["revenue_readiness"].startswith("not_revenue_ready")
    assert "OpenViking/Polymarket" in "\n".join(payload["safety_guardrails"])
    assert payload["target"]["url"] == "https://cal.com/signup"
    trace = payload["trace"]
    summary = payload["summary"]
    assert trace["main_status"] is not None and 200 <= int(trace["main_status"]) < 400
    assert "cal.com" in (trace.get("final_url") or "").lower()
    assert int(trace.get("body_text_chars") or 0) >= 300
    assert summary["screenshot_ok"] is True
    assert summary["screenshot_bytes"] >= 10_000
    assert screenshot_path.exists()
    assert screenshot_path.stat().st_size == summary["screenshot_bytes"]
    assert summary["finding_count"] >= 4
    assert summary["recommendation"] in {
        "ADOPT_ONE_COMPLIANT_OUTREACH_DRAFT",
        "REJECT_OUTREACH_UNTIL_STRONGER_TRACE",
    }
    assert "not revenue-ready" in report.lower()
    assert "not capital-ready" in report.lower()
    assert "Do not send automatically" in report
    assert "No form submission" in report
    assert "OpenViking/Polymarket" in report
    return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--screenshot", type=Path, default=DEFAULT_SCREENSHOT)
    args = parser.parse_args()
    payload = validate(args.json, args.report, args.screenshot)
    print("end_to_end_validation")
    print("CALCOM_REAL_BROWSER_TRACE_E2E_OK")
    print(f"REPORT {args.report} BYTES {args.report.stat().st_size}")
    print(f"JSON {args.json} BYTES {args.json.stat().st_size}")
    print(f"SCREENSHOT {args.screenshot} BYTES {args.screenshot.stat().st_size}")
    print(f"URL {payload['target']['url']} STATUS {payload['trace']['main_status']} FINAL {payload['trace']['final_url']}")
    print(f"BODY_TEXT_CHARS {payload['trace']['body_text_chars']}")
    print(f"FINDINGS {payload['summary']['finding_count']} RECOMMENDATION {payload['summary']['recommendation']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
