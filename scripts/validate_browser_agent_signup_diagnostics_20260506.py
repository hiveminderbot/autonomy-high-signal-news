#!/usr/bin/env python3
"""Validate browser-agent signup diagnostics artifacts with live source checks."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parents[1]
if str(LAB_ROOT) not in sys.path:
    sys.path.insert(0, str(LAB_ROOT))

from scripts.generate_browser_agent_signup_diagnostics_20260506 import DEFAULT_JSON, DEFAULT_REPORT, fetch_url

EXPECTED_RECOMMENDATIONS = {
    "ADOPT_PUBLIC_BROWSER_AGENT_QA_DEMO",
    "REJECT_UNTIL_PUBLIC_DIAGNOSTIC_FINDING",
}


def validate_artifacts(json_path: Path, report_path: Path, timeout: int) -> dict:
    payload = json.loads(json_path.read_text())
    report = report_path.read_text()

    assert payload["artifact"] == "browser-agent-signup-diagnostics-20260506"
    assert payload["recommendation"] in EXPECTED_RECOMMENDATIONS
    assert "scope" in payload and "Non-OpenViking" in payload["scope"]
    assert "OpenViking" not in report
    assert "Polymarket" not in report
    assert payload["acceptance"]["minimum_reachable_targets"] == 3
    assert payload["acceptance"]["minimum_outreach_worthy_targets"] == 1
    assert len(payload["diagnostics"]) == 3
    assert "Fixed-price service offer draft" in report
    assert "Not revenue-ready" in report
    assert "One-prospect browser-agent QA demo packet" in report
    assert payload["next_experiment"]["success_gate"].startswith("Run a real browser automation trace")

    live_sources = []
    for item in payload["diagnostics"]:
        status, final_url, body = fetch_url(item["url"], timeout=timeout)
        ok = 200 <= status < 400 and len(body) >= 5_000
        live_sources.append({"url": item["url"], "status": status, "final_url": final_url, "bytes": len(body), "ok": ok})
        print(f"SOURCE {status} {len(body)} {item['url']} FINAL {final_url} OK {ok}")

    reachable = sum(1 for item in live_sources if item["ok"])
    assert reachable >= payload["acceptance"]["minimum_reachable_targets"], live_sources
    assert payload["acceptance"]["passed"] is True
    assert payload["recommendation"] == "ADOPT_PUBLIC_BROWSER_AGENT_QA_DEMO"
    assert payload["acceptance"]["outreach_worthy_targets"] >= 1
    assert payload["strongest_target"] is not None

    print(f"JSON {json_path} BYTES {json_path.stat().st_size}")
    print(f"REPORT {report_path} BYTES {report_path.stat().st_size}")
    print("BROWSER_AGENT_SIGNUP_DIAGNOSTICS_VALIDATION_OK")
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--timeout", type=int, default=25)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    validate_artifacts(args.json, args.report, args.timeout)
