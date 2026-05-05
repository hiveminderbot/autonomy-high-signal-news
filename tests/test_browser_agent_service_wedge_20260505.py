import json
from argparse import Namespace

from scripts.validate_browser_agent_service_wedge_20260505 import (
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
  <h1>Playwright MCP browser automation</h1>
  <p>Chrome DevTools MCP provides browser diagnostics for agents.</p>
  <p>Stagehand and Browserbase provide browser SDK workflows.</p>
  <p>Claude computer use is a tool capability for browser tasks.</p>
</body></html>
""" + b"x" * 1500


def test_strip_html_removes_scripts_and_collapses_text():
    text = strip_html("<script>secret()</script><p>Chrome&nbsp;DevTools</p><p> MCP </p>")
    assert "secret" not in text
    assert "Chrome DevTools" in text
    assert "MCP" in text


def test_collect_source_requires_bytes_and_keywords():
    def fake_fetcher(url, timeout):
        return 200, HTML_FIXTURE

    evidence = collect_source(SOURCES[0], timeout=1, fetcher=fake_fetcher)

    assert evidence.ok is True
    assert evidence.http_status == 200
    assert evidence.bytes_read >= 1000
    assert set(evidence.keyword_hits) >= {"Playwright", "MCP", "browser"}


def test_make_payload_adopts_only_with_all_required_roles():
    def fake_fetcher(url, timeout):
        return 200, HTML_FIXTURE

    evidence = [collect_source(source, timeout=1, fetcher=fake_fetcher) for source in SOURCES]
    payload = make_payload(evidence, "2026-05-05T00:00:00+00:00")

    assert payload["acceptance"]["passed"] is True
    assert payload["recommendation"] == "ADOPT_BROWSER_AGENT_QA_SERVICE_PILOT"
    assert set(payload["acceptance"]["required_roles_present"]) == {
        "automation_surface",
        "diagnostic_surface",
        "agent_sdk",
        "model_capability",
    }


def test_make_payload_rejects_when_model_capability_missing():
    def fake_fetcher(url, timeout):
        return 200, HTML_FIXTURE

    evidence = [collect_source(source, timeout=1, fetcher=fake_fetcher) for source in SOURCES[:3]]
    payload = make_payload(evidence, "2026-05-05T00:00:00+00:00")

    assert payload["acceptance"]["passed"] is False
    assert payload["recommendation"] == "REJECT_UNTIL_SOURCE_EVIDENCE_HEALTHY"


def test_run_writes_artifacts_and_success_sentinel(monkeypatch, tmp_path, capsys):
    import scripts.validate_browser_agent_service_wedge_20260505 as wedge

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
    assert "BROWSER_AGENT_SERVICE_WEDGE_E2E_OK" in output
    assert "SOURCE https://github.com/microsoft/playwright-mcp" in output
    assert json.loads(json_path.read_text())["recommendation"] == "ADOPT_BROWSER_AGENT_QA_SERVICE_PILOT"
    report = report_path.read_text()
    assert "Source evidence" in report
    assert "Not capital-ready" in report
    assert "48-hour browser-agent QA artifact sprint" in report
