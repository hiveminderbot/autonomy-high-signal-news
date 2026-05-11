#!/usr/bin/env python3
"""
RSS Source Validator for High-Signal News

Checks each configured RSS/Atom feed for:
- HTTP 200 response
- Valid XML (well-formed RSS/Atom)
- At least one entry/item present
- Optionally: entries within recent N days

Outputs JSON report and exits with non-zero if any critical feeds fail.
"""

import sqlite3
import sys
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict

# Optional httpx, fallback to urllib
try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

import urllib.request
import urllib.error


DB_PATH = Path(__file__).parent.parent / "news.db"
REPORT_PATH = Path(__file__).parent.parent / "test-output" / "rss_validation_report.json"


@dataclass
class SourceValidationResult:
    source_id: int
    name: str
    url: str
    http_status: Optional[int]
    http_ok: bool
    xml_valid: bool
    xml_error: Optional[str]
    entry_count: int
    has_entries: bool
    latest_entry_date: Optional[str]
    recent_entries_count: int  # entries within 7 days
    response_time_ms: Optional[float]
    overall_ok: bool
    error: Optional[str] = None


def fetch_url(url: str, timeout: int = 20) -> tuple:
    """Fetch URL, return (status_code, content_bytes, response_time_ms, error)."""
    start = datetime.now()
    try:
        if HTTPX_AVAILABLE:
            with httpx.Client(timeout=timeout, follow_redirects=True, headers={
                "User-Agent": "HighSignalNews/1.0 (RSS Validator)"
            }) as client:
                resp = client.get(url)
                elapsed = (datetime.now() - start).total_seconds() * 1000
                return resp.status_code, resp.content, elapsed, None
        else:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "HighSignalNews/1.0 (RSS Validator)"}
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                content = resp.read()
                elapsed = (datetime.now() - start).total_seconds() * 1000
                return resp.getcode(), content, elapsed, None
    except Exception as e:
        elapsed = (datetime.now() - start).total_seconds() * 1000
        return None, b"", elapsed, str(e)


def parse_feed_entries(content: bytes) -> tuple:
    """Parse RSS/Atom feed, return (entry_count, latest_date_iso, recent_count, xml_error)."""
    try:
        root = ET.fromstring(content)
    except ET.ParseError as e:
        return 0, None, 0, str(e)

    entries = []
    now = datetime.now()
    cutoff = now - timedelta(days=7)

    # RSS 2.0
    for item in root.findall('.//item'):
        title = item.find('title')
        link = item.find('link')
        pub_date = item.find('pubDate')
        if title is not None and link is not None:
            date_str = pub_date.text if pub_date is not None else None
            dt = parse_rss_date(date_str)
            entries.append({'date': dt, 'date_str': date_str})

    # Atom
    ns = {'atom': 'http://www.w3.org/2005/Atom'}
    for entry in root.findall('.//atom:entry', ns):
        title = entry.find('atom:title', ns)
        link = entry.find('atom:link', ns)
        pub_date = entry.find('atom:updated', ns)
        if pub_date is None:
            pub_date = entry.find('atom:published', ns)
        if title is not None and link is not None:
            date_str = pub_date.text if pub_date is not None else None
            dt = parse_rss_date(date_str)
            entries.append({'date': dt, 'date_str': date_str})

    if not entries:
        # Try media RSS or other variants
        for item in root.findall('.//item'):
            title = item.find('title')
            if title is not None:
                entries.append({'date': None, 'date_str': None})

    latest_dt = None
    latest_str = None
    recent_count = 0
    for e in entries:
        if e['date'] is not None:
            # Normalize to naive UTC for comparison
            edt = e['date']
            if edt.tzinfo is not None:
                edt = edt.replace(tzinfo=None)
            if latest_dt is None or edt > latest_dt:
                latest_dt = edt
                latest_str = e['date_str']
            if edt >= cutoff:
                recent_count += 1

    return len(entries), latest_str, recent_count, None


def parse_rss_date(date_str: Optional[str]) -> Optional[datetime]:
    """Parse various RSS date formats."""
    if not date_str:
        return None
    formats = [
        "%a, %d %b %Y %H:%M:%S %z",
        "%a, %d %b %Y %H:%M:%S %Z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    # Try ISO format with Python 3.7+
    try:
        return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
    except (ValueError, TypeError):
        pass
    return None


def validate_source(source_id: int, name: str, url: str) -> SourceValidationResult:
    """Validate a single RSS source."""
    status, content, elapsed, error = fetch_url(url)

    if error:
        return SourceValidationResult(
            source_id=source_id,
            name=name,
            url=url,
            http_status=status,
            http_ok=False,
            xml_valid=False,
            xml_error=None,
            entry_count=0,
            has_entries=False,
            latest_entry_date=None,
            recent_entries_count=0,
            response_time_ms=elapsed,
            overall_ok=False,
            error=error
        )

    http_ok = status is not None and 200 <= status < 300

    if not http_ok:
        return SourceValidationResult(
            source_id=source_id,
            name=name,
            url=url,
            http_status=status,
            http_ok=False,
            xml_valid=False,
            xml_error=None,
            entry_count=0,
            has_entries=False,
            latest_entry_date=None,
            recent_entries_count=0,
            response_time_ms=elapsed,
            overall_ok=False,
            error=f"HTTP {status}"
        )

    entry_count, latest_date, recent_count, xml_error = parse_feed_entries(content)
    xml_valid = xml_error is None
    has_entries = entry_count > 0

    overall_ok = http_ok and xml_valid and has_entries

    return SourceValidationResult(
        source_id=source_id,
        name=name,
        url=url,
        http_status=status,
        http_ok=http_ok,
        xml_valid=xml_valid,
        xml_error=xml_error,
        entry_count=entry_count,
        has_entries=has_entries,
        latest_entry_date=latest_date,
        recent_entries_count=recent_count,
        response_time_ms=elapsed,
        overall_ok=overall_ok,
        error=xml_error if xml_error else None
    )


def validate_all_sources(db_path: Path, max_workers: int = 8) -> Dict:
    """Validate all active RSS sources in the database."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        'SELECT id, name, rss_url FROM sources WHERE status = "active" ORDER BY id'
    )
    sources = cursor.fetchall()
    conn.close()

    results: List[SourceValidationResult] = []
    ok_count = 0
    fail_count = 0

    print(f"Validating {len(sources)} active RSS sources...\n")

    for source_id, name, url in sources:
        print(f"  [{source_id}] {name} ... ", end="", flush=True)
        result = validate_source(source_id, name, url)
        results.append(result)
        if result.overall_ok:
            ok_count += 1
            print(f"OK ({result.entry_count} entries, {result.response_time_ms:.0f}ms)")
        else:
            fail_count += 1
            reason = result.error or f"HTTP {result.http_status}"
            print(f"FAIL ({reason})")

    summary = {
        "timestamp": datetime.now().isoformat(),
        "total_sources": len(sources),
        "ok_count": ok_count,
        "fail_count": fail_count,
        "ok_rate": round(ok_count / len(sources), 4) if sources else 0,
        "results": [asdict(r) for r in results]
    }

    return summary


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Validate RSS sources")
    parser.add_argument("--db", default=str(DB_PATH), help="Path to news.db")
    parser.add_argument("--output", default=str(REPORT_PATH), help="Path to JSON report")
    parser.add_argument("--min-ok-rate", type=float, default=0.7,
                        help="Minimum acceptable OK rate (0-1)")
    parser.add_argument("--ci", action="store_true",
                        help="Exit non-zero if min-ok-rate not met")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(f"ERROR: Database not found: {db_path}")
        sys.exit(1)

    summary = validate_all_sources(db_path)

    # Write report
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(summary, f, indent=2, default=str)

    print(f"\n{'='*60}")
    print(f"Summary: {summary['ok_count']}/{summary['total_sources']} sources OK")
    print(f"OK rate: {summary['ok_rate']*100:.1f}%")
    print(f"Report written to: {output_path}")
    print(f"{'='*60}")

    if args.ci and summary['ok_rate'] < args.min_ok_rate:
        print(f"\nCI FAIL: OK rate {summary['ok_rate']*100:.1f}% < {args.min_ok_rate*100:.1f}%")
        sys.exit(1)

    # Always exit non-zero if ALL sources fail (complete pipeline breakage)
    if summary['ok_count'] == 0 and summary['total_sources'] > 0:
        print("\nCRITICAL: All sources failed!")
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
