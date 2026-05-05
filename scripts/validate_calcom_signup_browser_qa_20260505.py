#!/usr/bin/env python3
"""Validate the Cal.com signup browser-agent QA demo packet artifacts."""
from __future__ import annotations

import json
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JSON = LAB_ROOT / "results" / "calcom-signup-browser-qa-20260505.json"
DEFAULT_REPORT = LAB_ROOT / "results" / "calcom-signup-browser-qa-20260505.md"


def validate(json_path: Path = DEFAULT_JSON, report_path: Path = DEFAULT_REPORT) -> dict:
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    report = report_path.read_text(encoding="utf-8")
    errors: list[str] = []

    if payload.get("artifact") != "calcom-signup-browser-qa-20260505":
        errors.append("wrong artifact id")
    if "OpenViking" in report or "Polymarket" in report:
        errors.append("hard-excluded lane leaked into report")
    acceptance = payload.get("acceptance", {})
    if not acceptance.get("passed"):
        errors.append("acceptance did not pass")
    if acceptance.get("recommendation") != "ADOPT_OUTREACH_PACKET_AFTER_REAL_BROWSER_TRACE":
        errors.append("unexpected recommendation")
    source = payload.get("source_evidence", {})
    if source.get("http_status") != 200:
        errors.append(f"source http status not 200: {source.get('http_status')}")
    if int(source.get("bytes_read") or 0) < 5_000:
        errors.append("source bytes below threshold")
    if int(source.get("visible_text_chars") or 0) >= 100:
        errors.append("expected minimal static visible text for Cal.com source")
    if int(source.get("script_count") or 0) < 20:
        errors.append("expected JS-heavy signup surface")
    if int(source.get("form_count") or 0) != 0 or int(source.get("input_count") or 0) != 0:
        errors.append("expected no static form/input controls")
    findings = payload.get("findings", [])
    if len(findings) < 2:
        errors.append("too few findings")
    for phrase in [
        "Source evidence",
        "Outreach packet draft",
        "do not send until browser trace passes",
        "Not revenue-ready because",
        "Acceptance evidence",
    ]:
        if phrase not in report:
            errors.append(f"missing report phrase: {phrase}")
    if errors:
        raise SystemExit("CALCOM_SIGNUP_BROWSER_QA_VALIDATION_FAILED\n" + "\n".join(errors))
    return payload


def main() -> int:
    payload = validate()
    source = payload["source_evidence"]
    print(f"JSON {DEFAULT_JSON} BYTES {DEFAULT_JSON.stat().st_size}")
    print(f"REPORT {DEFAULT_REPORT} BYTES {DEFAULT_REPORT.stat().st_size}")
    print(f"SOURCE {source['http_status']} {source['bytes_read']} {source['url']}")
    print(f"FINDINGS {len(payload['findings'])}")
    print(f"RECOMMENDATION {payload['acceptance']['recommendation']}")
    print("CALCOM_SIGNUP_BROWSER_QA_VALIDATION_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
