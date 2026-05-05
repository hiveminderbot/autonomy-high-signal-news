import json
from argparse import Namespace

from scripts.generate_browser_agent_signup_diagnostics_20260506 import (
    TARGETS,
    collect_target,
    extract_title,
    make_payload,
    run,
    strip_html,
)

HTML_FIXTURE = b"""
<!doctype html>
<html>
<head><title>Fixture Signup Diagnostics</title><script>ignored()</script></head>
<body>
  <h1>Browserbase signup</h1>
  <form><input type="email"><input type="password"><button>Continue with Google</button></form>
  <noscript>Please enable JavaScript for full signup.</noscript>
  <p>Email and password sign up for an account, continue with GitHub or SSO, and create your workspace.</p>
</body>
</html>
""" + b"x" * 7000


def test_strip_html_removes_scripts_styles_and_decodes_entities():
    text = strip_html("<script>secret()</script><style>.x{}</style><p>Sign&nbsp;up &amp; continue</p>")
    assert "secret" not in text
    assert ".x" not in text
    assert "Sign up & continue" in text


def test_collect_target_extracts_form_identity_and_findings():
    def fake_fetcher(url, timeout):
        return 200, "https://example.test/final", HTML_FIXTURE

    diagnostic = collect_target(TARGETS[0], timeout=1, fetcher=fake_fetcher)

    assert diagnostic.ok is True
    assert diagnostic.http_status == 200
    assert diagnostic.final_url == "https://example.test/final"
    assert diagnostic.bytes_read >= 5000
    assert diagnostic.title == "Fixture Signup Diagnostics"
    assert diagnostic.form_count == 1
    assert diagnostic.input_count == 2
    assert diagnostic.button_count == 1
    assert diagnostic.has_noscript is True
    assert {"browserbase", "email", "password", "continue"}.issubset(set(diagnostic.expected_term_hits))
    assert {"google", "github", "sso", "continue"}.issubset(set(diagnostic.identity_provider_hits))
    assert diagnostic.outreach_worthy is True
    assert diagnostic.findings


def test_make_payload_adopts_only_with_reachable_outreach_worthy_target():
    def fake_fetcher(url, timeout):
        return 200, url, HTML_FIXTURE

    diagnostics = [collect_target(target, timeout=1, fetcher=fake_fetcher) for target in TARGETS]
    payload = make_payload(diagnostics, "2026-05-06T00:00:00+00:00")

    assert payload["recommendation"] == "ADOPT_PUBLIC_BROWSER_AGENT_QA_DEMO"
    assert payload["acceptance"]["passed"] is True
    assert payload["acceptance"]["reachable_targets"] == 3
    assert payload["acceptance"]["outreach_worthy_targets"] >= 1
    assert payload["strongest_target"] is not None
    assert payload["next_experiment"]["success_gate"].startswith("Run a real browser automation trace")
    assert any(reason.startswith("no prospect has been contacted") for reason in payload["not_revenue_ready_because"])


def test_make_payload_rejects_without_outreach_worthy_finding():
    def fake_fetcher(url, timeout):
        body = b"<html><title>Minimal</title><body>loading</body></html>"
        return 200, url, body

    diagnostics = [collect_target(target, timeout=1, fetcher=fake_fetcher) for target in TARGETS]
    payload = make_payload(diagnostics, "2026-05-06T00:00:00+00:00")

    assert payload["acceptance"]["passed"] is False
    assert payload["recommendation"] == "REJECT_UNTIL_PUBLIC_DIAGNOSTIC_FINDING"
    assert payload["strongest_target"] is None


def test_run_writes_artifacts_and_success_sentinel(monkeypatch, tmp_path, capsys):
    import scripts.generate_browser_agent_signup_diagnostics_20260506 as diagnostics

    def fake_collect(target, timeout):
        return collect_target(target, timeout=timeout, fetcher=lambda url, timeout: (200, url, HTML_FIXTURE))

    monkeypatch.setattr(diagnostics, "collect_target", fake_collect)
    json_path = tmp_path / "diagnostics.json"
    report_path = tmp_path / "diagnostics.md"

    payload = run(
        Namespace(
            timeout=1,
            artifact_timestamp="2026-05-06T00:00:00+00:00",
            json_output=json_path,
            report_output=report_path,
        )
    )
    output = capsys.readouterr().out

    assert payload["acceptance"]["passed"] is True
    assert "BROWSER_AGENT_SIGNUP_DIAGNOSTICS_GENERATED_OK" in output
    assert "SOURCE 200" in output
    assert json.loads(json_path.read_text())["recommendation"] == "ADOPT_PUBLIC_BROWSER_AGENT_QA_DEMO"
    report = report_path.read_text()
    assert "Fixed-price service offer draft" in report
    assert "Not revenue-ready" in report
    assert "One-prospect browser-agent QA demo packet" in report
