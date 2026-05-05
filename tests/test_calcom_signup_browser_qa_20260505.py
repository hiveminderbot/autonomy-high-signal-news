from scripts.generate_calcom_signup_browser_qa_20260505 import (
    SourceEvidence,
    build_payload,
    collect_source,
    write_report,
)
from scripts.validate_calcom_signup_browser_qa_20260505 import validate


def fake_calcom_fetch(url: str, timeout: int):
    html = b"""
    <!doctype html><html><head><title>Sign up | Cal.com</title></head>
    <body><div id="__next"></div>
    """ + (b"<script src='/_next/static/chunk.js'></script>" * 30) + (b"<!--" + b"x" * 6000 + b"-->") + b"</body></html>"
    return 200, "https://app.cal.com/signup", html


def test_collect_source_detects_js_heavy_minimal_static_signup():
    evidence = collect_source(timeout=1, fetcher=fake_calcom_fetch)
    assert evidence.ok is True
    assert evidence.http_status == 200
    assert evidence.final_url == "https://app.cal.com/signup"
    assert evidence.visible_text_chars < 100
    assert evidence.script_count == 30
    assert evidence.noscript_count == 0
    assert evidence.form_count == 0
    assert evidence.input_count == 0


def test_build_payload_has_outreach_guardrail_and_recommendation():
    evidence = SourceEvidence(
        name="Cal.com signup public HTML",
        url="https://cal.com/signup",
        http_status=200,
        final_url="https://app.cal.com/signup",
        bytes_read=9000,
        title="Sign up | Cal.com",
        visible_text_chars=17,
        visible_text_sample="Sign up | Cal.com",
        form_count=0,
        input_count=0,
        button_count=0,
        script_count=46,
        noscript_count=0,
        ok=True,
    )
    payload = build_payload(evidence, "2026-05-05T00:00:00+00:00")
    assert payload["acceptance"]["passed"] is True
    assert payload["acceptance"]["recommendation"] == "ADOPT_OUTREACH_PACKET_AFTER_REAL_BROWSER_TRACE"
    assert len(payload["findings"]) >= 2
    assert "Do not send" in payload["outreach_packet"]["guardrail"]
    assert "OpenViking" not in payload["scope"]
    assert "real browser trace" in payload["next_experiment"]["success_gate"]


def test_write_report_and_validator_accept_generated_artifacts(tmp_path):
    evidence = collect_source(timeout=1, fetcher=fake_calcom_fetch)
    payload = build_payload(evidence, "2026-05-05T00:00:00+00:00")
    json_path = tmp_path / "packet.json"
    report_path = tmp_path / "packet.md"
    json_path.write_text(__import__("json").dumps(payload), encoding="utf-8")
    write_report(payload, report_path)
    validated = validate(json_path, report_path)
    assert validated["artifact"] == "calcom-signup-browser-qa-20260505"
    report = report_path.read_text(encoding="utf-8")
    assert "Outreach packet draft" in report
    assert "Not revenue-ready because" in report
