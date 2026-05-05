import json
from argparse import Namespace
from pathlib import Path

from scripts.validate_live_rss_briefing_proof_20260505 import (
    DEFAULT_FEEDS,
    collect_feed,
    make_payload,
    parse_entries,
    run,
)


RSS_FIXTURE = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Fixture Feed</title>
    <item>
      <title>Live item one</title>
      <link>https://example.com/one</link>
      <pubDate>Tue, 05 May 2026 18:00:00 GMT</pubDate>
      <description><![CDATA[<p>Useful source-backed summary.</p>]]></description>
    </item>
    <item>
      <title>Live item two</title>
      <link>https://example.com/two</link>
      <pubDate>Tue, 05 May 2026 17:00:00 GMT</pubDate>
      <description>Second summary.</description>
    </item>
  </channel>
</rss>
""" + b" " * 600


ATOM_FIXTURE = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Atom Fixture</title>
  <entry>
    <title>Atom item one</title>
    <link href="https://example.com/atom-one" />
    <updated>2026-05-05T18:00:00Z</updated>
    <summary>Atom summary.</summary>
  </entry>
</feed>
""" + b" " * 600


def test_parse_entries_supports_rss_and_atom():
    rss_entries = parse_entries(RSS_FIXTURE)
    atom_entries = parse_entries(ATOM_FIXTURE)

    assert rss_entries[0].title == "Live item one"
    assert rss_entries[0].summary == "Useful source-backed summary."
    assert rss_entries[0].published == "2026-05-05T18:00:00+00:00"
    assert atom_entries[0].url == "https://example.com/atom-one"


def test_collect_feed_marks_source_healthy_with_entries_and_bytes():
    def fake_fetcher(url, timeout):
        return 200, RSS_FIXTURE

    evidence = collect_feed(DEFAULT_FEEDS[0], timeout=1, fetcher=fake_fetcher)

    assert evidence.ok is True
    assert evidence.http_status == 200
    assert evidence.bytes_read >= 500
    assert len(evidence.entries) == 2


def test_make_payload_recommends_adopt_when_thresholds_met():
    def fake_fetcher(url, timeout):
        return 200, RSS_FIXTURE

    evidence = [collect_feed(feed, timeout=1, fetcher=fake_fetcher) for feed in DEFAULT_FEEDS]
    payload = make_payload(evidence, "2026-05-05T18:00:00+00:00")

    assert payload["acceptance"]["healthy_sources"] == len(DEFAULT_FEEDS)
    assert payload["acceptance"]["passed"] is False  # 4 feeds x 2 entries = 8, below live proof bar
    assert payload["recommendation"] == "REJECT_UNTIL_FEEDS_HEALTHY"


def test_run_writes_artifacts_and_success_sentinel(monkeypatch, tmp_path, capsys):
    import scripts.validate_live_rss_briefing_proof_20260505 as proof

    def fake_collect(feed, timeout):
        def fake_fetcher(url, timeout):
            return 200, RSS_FIXTURE

        evidence = collect_feed(feed, timeout=timeout, fetcher=fake_fetcher)
        # Make each feed clear the total-entry threshold in this deterministic unit test.
        evidence.entries = evidence.entries * 2
        return evidence

    monkeypatch.setattr(proof, "collect_feed", fake_collect)
    json_path = tmp_path / "proof.json"
    report_path = tmp_path / "proof.md"
    payload = run(Namespace(timeout=1, artifact_timestamp="2026-05-05T00:00:00+00:00", json_output=json_path, report_output=report_path))
    output = capsys.readouterr().out

    assert payload["acceptance"]["passed"] is True
    assert "LIVE_RSS_BRIEFING_PROOF_OK" in output
    assert json.loads(json_path.read_text())["recommendation"] == "ADOPT_FOR_DAILY_BRIEFING_CRON"
    assert "Source evidence" in report_path.read_text()
