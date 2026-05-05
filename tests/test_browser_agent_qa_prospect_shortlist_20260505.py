import json
from argparse import Namespace

from scripts.validate_browser_agent_qa_prospect_shortlist_20260505 import (
    TARGETS,
    collect_target,
    extract_title,
    make_payload,
    run,
    strip_html,
)

HTML_FIXTURE = b"""
<!doctype html>
<html><head><title>Fixture Signup Page</title><script>ignored()</script></head>
<body>
  <h1>Cal signup account workflow</h1>
  <p>PostHog signup login dashboard and Linear workspace onboarding.</p>
  <p>Sentry error setup, Supabase dashboard sign up, Browserbase browser sign-up, Vercel deploy signup.</p>
</body></html>
""" + b"x" * 6000


def test_strip_html_removes_scripts_and_collapses_text():
    text = strip_html("<script>secret()</script><p>Browserbase&nbsp;signup</p><p> dashboard </p>")
    assert "secret" not in text
    assert "Browserbase signup" in text
    assert "dashboard" in text


def test_extract_title_from_html():
    assert extract_title("<html><title> Example Signup </title></html>") == "Example Signup"
    assert extract_title("<html><body>No title</body></html>") is None


def test_collect_target_requires_bytes_and_keywords():
    def fake_fetcher(url, timeout):
        return 200, HTML_FIXTURE

    evidence = collect_target(TARGETS[0], timeout=1, fetcher=fake_fetcher)

    assert evidence.ok is True
    assert evidence.http_status == 200
    assert evidence.bytes_read >= 5000
    assert set(evidence.keyword_hits) >= {"cal", "sign", "account"}
    assert evidence.title == "Fixture Signup Page"


def test_make_payload_adopts_with_five_targets_across_segments():
    def fake_fetcher(url, timeout):
        return 200, HTML_FIXTURE

    evidence = [collect_target(target, timeout=1, fetcher=fake_fetcher) for target in TARGETS]
    payload = make_payload(evidence, "2026-05-05T00:00:00+00:00")

    assert payload["acceptance"]["passed"] is True
    assert payload["recommendation"] == "ADOPT_BROWSER_AGENT_QA_PROSPECT_SPRINT"
    assert payload["acceptance"]["healthy_targets"] >= 5
    assert len(payload["acceptance"]["segments_present"]) >= 4
    assert len(payload["shortlist"]) == 5


def test_make_payload_rejects_when_too_few_segments():
    def fake_fetcher(url, timeout):
        return 200, HTML_FIXTURE

    evidence = [collect_target(target, timeout=1, fetcher=fake_fetcher) for target in TARGETS[:3]]
    payload = make_payload(evidence, "2026-05-05T00:00:00+00:00")

    assert payload["acceptance"]["passed"] is False
    assert payload["recommendation"] == "REJECT_UNTIL_PROSPECT_EVIDENCE_HEALTHY"


def test_run_writes_artifacts_and_success_sentinel(monkeypatch, tmp_path, capsys):
    import scripts.validate_browser_agent_qa_prospect_shortlist_20260505 as shortlist

    def fake_collect(target, timeout):
        return collect_target(target, timeout=timeout, fetcher=lambda url, timeout: (200, HTML_FIXTURE))

    monkeypatch.setattr(shortlist, "collect_target", fake_collect)
    json_path = tmp_path / "prospects.json"
    report_path = tmp_path / "prospects.md"
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
    assert "BROWSER_AGENT_QA_PROSPECT_SHORTLIST_E2E_OK" in output
    assert "SOURCE https://cal.com/signup" in output
    assert json.loads(json_path.read_text())["recommendation"] == "ADOPT_BROWSER_AGENT_QA_PROSPECT_SPRINT"
    report = report_path.read_text()
    assert "Top shortlist" in report
    assert "Not revenue-ready" in report
    assert "One-day public onboarding QA demo sprint" in report
