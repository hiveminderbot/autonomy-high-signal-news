import json
from argparse import Namespace

from scripts.validate_ai_receptionist_revenue_wedge_20260505 import (
    SOURCES,
    collect_source,
    make_payload,
    run,
    strip_html,
)

HTML_FIXTURE = b"""
<!doctype html>
<html><head><title>Fixture</title><script>ignored()</script></head>
<body>
  <h1>Programmable Voice pricing and Realtime API</h1>
  <p>AI phone receptionist calls use speech and audio for restaurants.</p>
  <p>Transparent pricing for calls and receptionists.</p>
</body></html>
""" + b"x" * 1500


def test_strip_html_removes_scripts_and_collapses_text():
    text = strip_html("<script>secret()</script><p>AI&nbsp;phone</p><p> pricing </p>")
    assert "secret" not in text
    assert "pricing" in text


def test_collect_source_requires_bytes_and_keywords():
    def fake_fetcher(url, timeout):
        return 200, HTML_FIXTURE

    evidence = collect_source(SOURCES[0], timeout=1, fetcher=fake_fetcher)

    assert evidence.ok is True
    assert evidence.http_status == 200
    assert evidence.bytes_read >= 1000
    assert set(evidence.keyword_hits) >= {"voice", "pricing"}


def test_make_payload_adopts_only_with_required_roles():
    def fake_fetcher(url, timeout):
        return 200, HTML_FIXTURE

    evidence = [collect_source(source, timeout=1, fetcher=fake_fetcher) for source in SOURCES[:3]]
    payload = make_payload(evidence, "2026-05-05T00:00:00+00:00")

    assert payload["acceptance"]["passed"] is True
    assert payload["recommendation"] == "ADOPT_NARROW_AI_RECEPTIONIST_PILOT"
    assert "delivery_cost" in payload["acceptance"]["required_roles_present"]
    assert "technical_feasibility" in payload["acceptance"]["required_roles_present"]
    assert "competitor_willingness_to_pay" in payload["acceptance"]["required_roles_present"]


def test_run_writes_artifacts_and_success_sentinel(monkeypatch, tmp_path, capsys):
    import scripts.validate_ai_receptionist_revenue_wedge_20260505 as wedge

    def fake_collect(source, timeout):
        return collect_source(source, timeout=timeout, fetcher=lambda url, timeout: (200, HTML_FIXTURE))

    monkeypatch.setattr(wedge, "collect_source", fake_collect)
    json_path = tmp_path / "wedge.json"
    report_path = tmp_path / "wedge.md"
    payload = run(
        Namespace(
            timeout=1,
            artifact_timestamp="2026-05-05T00:00:00+00:00",
            json_output=json_path,
            report_output=report_path,
        )
    )
    output = capsys.readouterr().out

    assert payload["acceptance"]["passed"] is True
    assert "AI_RECEPTIONIST_REVENUE_WEDGE_E2E_OK" in output
    assert "SOURCE https://www.twilio.com/en-us/voice/pricing/us" in output
    assert json.loads(json_path.read_text())["recommendation"] == "ADOPT_NARROW_AI_RECEPTIONIST_PILOT"
    report = report_path.read_text()
    assert "Source evidence" in report
    assert "Not capital-ready" in report
