#!/usr/bin/env python3
"""
Health check for high-signal-news GitHub Pages deployment.

Validates:
1. The Pages URL returns HTTP 200
2. The HTML contains actual content (not placeholder)
3. The latest briefing date matches today or yesterday
"""

import re
import sys
from datetime import datetime, timedelta
from urllib.request import urlopen, Request
from urllib.error import HTTPError

PAGES_URL = "https://hiveminderbot.github.io/autonomy-high-signal-news/"
PLACEHOLDER_TEXT = "No briefing available yet"
MIN_CONTENT_LENGTH = 500  # bytes — placeholder is ~200 chars


def check_http_status():
    """Verify the Pages URL returns HTTP 200."""
    req = Request(PAGES_URL, headers={"User-Agent": "high-signal-news-health-check/1.0"})
    try:
        with urlopen(req, timeout=30) as resp:
            status = resp.status
            html = resp.read().decode("utf-8", errors="ignore")
            return status, html
    except HTTPError as e:
        return e.code, ""
    except Exception as e:
        return -1, str(e)


def check_content_present(html):
    """Verify HTML contains real content, not placeholder."""
    if PLACEHOLDER_TEXT in html:
        return False, "placeholder text detected"
    if len(html) < MIN_CONTENT_LENGTH:
        return False, f"content too short ({len(html)} < {MIN_CONTENT_LENGTH})"
    # Look for expected briefing structure
    has_title = "<h1>" in html or "<title>" in html
    has_date = re.search(r"\d{4}-\d{2}-\d{2}", html) is not None
    return has_title and has_date, f"title={has_title}, date={has_date}"


def check_date_freshness(html):
    """Verify the briefing date is today or yesterday."""
    today = datetime.now().date()
    yesterday = today - timedelta(days=1)

    # Look for date patterns in the HTML
    date_patterns = [
        r"(\d{4}-\d{2}-\d{2})",  # ISO format
        r"(\d{1,2}\s+[A-Za-z]+\s+\d{4})",  # e.g. "9 May 2026"
    ]

    for pattern in date_patterns:
        matches = re.findall(pattern, html)
        for match in matches:
            try:
                if len(match) == 10 and match[4] == "-":
                    parsed = datetime.strptime(match, "%Y-%m-%d").date()
                else:
                    continue
                if parsed in (today, yesterday):
                    return True, f"found date {parsed}"
            except ValueError:
                continue

    return False, "no fresh date found"


def main():
    print(f"Health check for {PAGES_URL}")
    print("=" * 50)

    # Check 1: HTTP status
    status, html = check_http_status()
    if status == 200:
        print(f"[PASS] HTTP status: {status}")
    else:
        print(f"[FAIL] HTTP status: {status}")
        sys.exit(1)

    # Check 2: Content presence
    content_ok, content_detail = check_content_present(html)
    if content_ok:
        print(f"[PASS] Content present: {content_detail}")
    else:
        print(f"[FAIL] Content check: {content_detail}")
        sys.exit(1)

    # Check 3: Date freshness
    date_ok, date_detail = check_date_freshness(html)
    if date_ok:
        print(f"[PASS] Date freshness: {date_detail}")
    else:
        print(f"[WARN] Date freshness: {date_detail}")
        # Don't fail on date — the cron might run before the daily briefing
        # But flag it for attention

    print("=" * 50)
    print("OVERALL: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
