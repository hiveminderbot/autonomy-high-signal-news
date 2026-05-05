#!/usr/bin/env python3
"""Validate that high-signal-news can build a non-fabricated live RSS proof.

This intentionally uses only the Python standard library so cron validation does not
silently skip on optional feedparser/requests availability. It fetches a small,
curated set of public RSS/Atom feeds, parses live entries, and writes stable JSON
and Markdown evidence artifacts with an adopt/reject recommendation.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import textwrap
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Callable, Iterable

LAB_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_JSON = LAB_ROOT / "results" / "live-rss-briefing-proof-20260505.json"
DEFAULT_REPORT = LAB_ROOT / "results" / "live-rss-briefing-proof-20260505.md"

DEFAULT_FEEDS = [
    {
        "name": "Hacker News",
        "url": "https://news.ycombinator.com/rss",
        "domain": "software_development",
        "why": "High-signal startup/software community feed with current links.",
    },
    {
        "name": "Lobsters",
        "url": "https://lobste.rs/rss",
        "domain": "software_development",
        "why": "Curated programming community with timestamps and discussion links.",
    },
    {
        "name": "Simon Willison",
        "url": "https://simonwillison.net/atom/everything/",
        "domain": "ai_and_software",
        "why": "Practitioner-focused AI/tooling notes from a high-signal individual source.",
    },
    {
        "name": "Python Insider",
        "url": "https://pythoninsider.blogspot.com/feeds/posts/default",
        "domain": "software_development",
        "why": "Official-ish Python release/community announcements via Atom.",
    },
]


@dataclass
class FeedEntry:
    title: str
    url: str
    published: str | None
    summary: str | None


@dataclass
class FeedEvidence:
    name: str
    url: str
    domain: str
    why: str
    http_status: int | None
    bytes_read: int
    ok: bool
    error: str | None
    entries: list[FeedEntry]


def strip_tags(value: str | None) -> str | None:
    if value is None:
        return None
    text = re.sub(r"<[^>]+>", " ", value)
    return re.sub(r"\s+", " ", text).strip() or None


def normalize_dt(value: str | None) -> str | None:
    if not value:
        return None
    value = value.strip()
    try:
        dt = parsedate_to_datetime(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except Exception:
        pass
    # Atom timestamps are often already ISO-ish. Preserve useful source text if
    # Python cannot parse it without third-party dependencies.
    return value[:80]


def child_text(element: ET.Element, names: Iterable[str]) -> str | None:
    wanted = set(names)
    for child in list(element):
        tag = child.tag.rsplit("}", 1)[-1]
        if tag in wanted and child.text:
            return child.text.strip()
    return None


def entry_link(element: ET.Element) -> str:
    for child in list(element):
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "link":
            href = child.attrib.get("href")
            if href:
                return href.strip()
            if child.text:
                return child.text.strip()
    return ""


def parse_entries(xml_bytes: bytes, limit: int = 8) -> list[FeedEntry]:
    root = ET.fromstring(xml_bytes)
    entries: list[FeedEntry] = []

    # RSS items
    for item in root.findall(".//item"):
        title = child_text(item, ["title"]) or "(untitled)"
        link = child_text(item, ["link"]) or entry_link(item)
        published = normalize_dt(child_text(item, ["pubDate", "published", "updated", "date"]))
        summary = strip_tags(child_text(item, ["description", "summary", "content"]))
        entries.append(FeedEntry(title=title, url=link, published=published, summary=summary))
        if len(entries) >= limit:
            return entries

    # Atom entries, namespace agnostic.
    for entry in [el for el in root.iter() if el.tag.rsplit("}", 1)[-1] == "entry"]:
        title = child_text(entry, ["title"]) or "(untitled)"
        link = entry_link(entry)
        published = normalize_dt(child_text(entry, ["published", "updated", "date"]))
        summary = strip_tags(child_text(entry, ["summary", "content"]))
        entries.append(FeedEntry(title=title, url=link, published=published, summary=summary))
        if len(entries) >= limit:
            return entries

    return entries


def fetch_url(url: str, timeout: int) -> tuple[int, bytes]:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "HermesAutonomyHighSignalNews/1.0 (+https://github.com/hiveminderbot/autonomy-high-signal-news)",
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml;q=0.9, */*;q=0.8",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        status = getattr(response, "status", response.getcode())
        return int(status), response.read()


def collect_feed(
    feed: dict[str, str],
    timeout: int,
    fetcher: Callable[[str, int], tuple[int, bytes]] = fetch_url,
) -> FeedEvidence:
    try:
        status, body = fetcher(feed["url"], timeout)
        entries = parse_entries(body)
        ok = 200 <= status < 400 and len(entries) > 0 and len(body) >= 500
        return FeedEvidence(
            name=feed["name"],
            url=feed["url"],
            domain=feed["domain"],
            why=feed["why"],
            http_status=status,
            bytes_read=len(body),
            ok=ok,
            error=None if ok else f"status={status} entries={len(entries)} bytes={len(body)}",
            entries=entries,
        )
    except (urllib.error.URLError, TimeoutError, ET.ParseError, OSError) as exc:
        return FeedEvidence(
            name=feed["name"],
            url=feed["url"],
            domain=feed["domain"],
            why=feed["why"],
            http_status=None,
            bytes_read=0,
            ok=False,
            error=f"{type(exc).__name__}: {exc}",
            entries=[],
        )


def make_payload(evidence: list[FeedEvidence], fetched_at: str) -> dict:
    healthy = [item for item in evidence if item.ok]
    total_entries = sum(len(item.entries) for item in evidence)
    recommendation = "ADOPT_FOR_DAILY_BRIEFING_CRON" if len(healthy) >= 3 and total_entries >= 10 else "REJECT_UNTIL_FEEDS_HEALTHY"
    next_experiment = (
        "Run the existing high-signal-news briefing generator against these live feed rows for 7 daily runs, "
        "then keep only sources with nonzero entries and no HTTP/parser failures."
        if recommendation.startswith("ADOPT")
        else "Replace or repair failed feed URLs, then rerun this proof before scheduling delivery."
    )
    return {
        "fetched_at": fetched_at,
        "task": "Live RSS briefing proof for high-signal-news",
        "recommendation": recommendation,
        "next_experiment": next_experiment,
        "acceptance": {
            "healthy_sources": len(healthy),
            "total_sources": len(evidence),
            "total_entries": total_entries,
            "minimum_healthy_sources": 3,
            "minimum_entries": 10,
            "passed": len(healthy) >= 3 and total_entries >= 10,
        },
        "sources": [
            {
                **{k: v for k, v in asdict(item).items() if k != "entries"},
                "entries": [asdict(entry) for entry in item.entries],
            }
            for item in evidence
        ],
    }


def write_report(payload: dict, report_path: Path) -> None:
    acceptance = payload["acceptance"]
    lines = [
        "# Live RSS Briefing Proof — 2026-05-05",
        "",
        f"Fetched at: `{payload['fetched_at']}`",
        "",
        "## Recommendation",
        "",
        f"**{payload['recommendation']}**",
        "",
        payload["next_experiment"],
        "",
        "## Validation summary",
        "",
        f"- Healthy sources: {acceptance['healthy_sources']} / {acceptance['total_sources']} (minimum {acceptance['minimum_healthy_sources']})",
        f"- Parsed live entries: {acceptance['total_entries']} (minimum {acceptance['minimum_entries']})",
        f"- Acceptance passed: `{acceptance['passed']}`",
        "",
        "## Source evidence",
        "",
    ]
    for source in payload["sources"]:
        lines += [
            f"### {source['name']}",
            "",
            f"- URL: {source['url']}",
            f"- Domain: {source['domain']}",
            f"- Why included: {source['why']}",
            f"- HTTP status: {source['http_status']}",
            f"- Bytes read: {source['bytes_read']}",
            f"- Parsed entries: {len(source['entries'])}",
            f"- Healthy: `{source['ok']}`",
        ]
        if source["error"]:
            lines.append(f"- Error: `{source['error']}`")
        lines += ["", "Top parsed entries:", ""]
        for entry in source["entries"][:5]:
            published = entry.get("published") or "unknown published time"
            lines.append(f"- [{entry['title']}]({entry['url']}) — {published}")
        lines.append("")
    lines += [
        "## Guardrail",
        "",
        "This artifact is source-backed: every included headline was parsed from a fetched RSS/Atom response in this run. It is not an LLM-fabricated briefing.",
        "",
    ]
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("\n".join(lines), encoding="utf-8")


def run(args: argparse.Namespace) -> dict:
    fetched_at = datetime.now(timezone.utc).isoformat()
    evidence = [collect_feed(feed, timeout=args.timeout) for feed in DEFAULT_FEEDS]
    payload = make_payload(evidence, fetched_at)

    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    write_report(payload, args.report_output)

    for source in payload["sources"]:
        print(
            f"SOURCE {source['name']} STATUS {source['http_status']} "
            f"ENTRIES {len(source['entries'])} BYTES {source['bytes_read']} URL {source['url']}"
        )
    print(f"JSON {args.json_output} BYTES {args.json_output.stat().st_size}")
    print(f"REPORT {args.report_output} BYTES {args.report_output.stat().st_size}")
    if payload["acceptance"]["passed"]:
        print("LIVE_RSS_BRIEFING_PROOF_OK")
        return payload
    raise SystemExit("LIVE_RSS_BRIEFING_PROOF_FAILED")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch live RSS/Atom sources and generate a validated high-signal-news proof artifact.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(
            """
            Success criteria:
              - At least 3 healthy sources return HTTP 2xx/3xx, >=500 bytes, and >=1 parsed entry.
              - At least 10 total entries are parsed.
              - JSON and Markdown artifacts are written under results/.
            """
        ),
    )
    parser.add_argument("--timeout", type=int, default=20, help="Per-source HTTP timeout in seconds")
    parser.add_argument("--json-output", type=Path, default=DEFAULT_JSON)
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    run(parse_args(sys.argv[1:] if argv is None else argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
