import json
from pathlib import Path

from scripts.generate_calcom_real_browser_trace_20260506 import build_payload, classify_trace, render_report
from scripts.validate_calcom_real_browser_trace_20260506 import validate


def _trace():
    return {
        "target_url": "https://cal.com/signup",
        "final_url": "https://app.cal.com/signup",
        "main_status": 200,
        "goto_error": None,
        "title": "Sign up | Cal.com",
        "body_text_chars": 1800,
        "body_text_sample": "Sign up Continue with Google Continue with email Cal.com",
        "controls": {
            "forms": 1,
            "inputs": 2,
            "buttons": 4,
            "links": 6,
            "text_controls": ["Continue with Google", "Continue with email", "Sign up"],
            "has_noscript": False,
            "script_count": 52,
        },
        "console_messages": [{"type": "log", "text": "ready"}],
        "page_errors": [],
        "failed_requests": [],
        "error_responses": [],
        "screenshot_path": "unused.png",
    }


def test_classify_trace_requires_real_screenshot(tmp_path):
    screenshot = tmp_path / "shot.png"
    screenshot.write_bytes(b"x" * 12_000)
    summary = classify_trace(_trace(), screenshot)
    assert summary["screenshot_ok"] is True
    assert summary["outreach_ready_for_manual_review"] is True
    assert summary["recommendation"] == "ADOPT_ONE_COMPLIANT_OUTREACH_DRAFT"
    assert summary["failed_request_count"] == 0


def test_render_report_contains_safety_and_readiness_language(tmp_path):
    screenshot = tmp_path / "shot.png"
    screenshot.write_bytes(b"x" * 12_000)
    summary = classify_trace(_trace(), screenshot)
    payload = build_payload(_trace(), summary, screenshot)
    report = render_report(payload)
    assert "not revenue-ready" in report.lower()
    assert "not capital-ready" in report.lower()
    assert "Do not send automatically" in report
    assert "OpenViking/Polymarket" in report
    assert "No form submission" in report


def test_validate_accepts_generated_artifact_shape(tmp_path):
    screenshot = tmp_path / "shot.png"
    screenshot.write_bytes(b"x" * 12_000)
    summary = classify_trace(_trace(), screenshot)
    payload = build_payload(_trace(), summary, screenshot)
    json_path = tmp_path / "artifact.json"
    report_path = tmp_path / "artifact.md"
    json_path.write_text(json.dumps(payload, indent=2) + "\n")
    report_path.write_text(render_report(payload))
    validated = validate(json_path, report_path, screenshot)
    assert validated["artifact"] == "calcom-real-browser-trace-20260506"


def test_validate_rejects_capital_ready_claim(tmp_path):
    screenshot = tmp_path / "shot.png"
    screenshot.write_bytes(b"x" * 12_000)
    summary = classify_trace(_trace(), screenshot)
    payload = build_payload(_trace(), summary, screenshot)
    payload["capital_readiness"] = "capital_ready"
    json_path = tmp_path / "artifact.json"
    report_path = tmp_path / "artifact.md"
    json_path.write_text(json.dumps(payload, indent=2) + "\n")
    report_path.write_text(render_report(payload))
    try:
        validate(json_path, report_path, screenshot)
    except AssertionError:
        pass
    else:
        raise AssertionError("capital-ready payload should be rejected")
