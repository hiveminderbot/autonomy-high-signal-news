#!/usr/bin/env python3
"""
End-to-End RSS Fetch + Briefing Test

1. Fetches from a small set of reliable RSS feeds
2. Stores articles in the database
3. Generates a non-empty briefing with at least 3 stories
4. Runs in < 60 seconds

This test validates the entire pipeline from RSS fetch to briefing output.
"""

import sqlite3
import sys
import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

# Add scripts to path
SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.path.insert(0, str(SCRIPTS_DIR / "aggregator"))

from rss_fetcher import RSSFetcher
from briefing.generator import BriefingGenerator, BriefingFormat


# Small set of highly reliable feeds for fast testing
TEST_FEEDS = [
    ("Hacker News", "https://news.ycombinator.com/rss", "software_development"),
    ("arXiv cs.AI", "https://export.arxiv.org/rss/cs.AI", "ai"),
    ("Lobsters", "https://lobste.rs/rss", "software_development"),
]

DB_PATH = Path(__file__).parent.parent / "news.db"
OUTPUT_DIR = Path(__file__).parent.parent / "test-output"


def setup_test_db(db_path: Path):
    """Ensure test sources exist in DB."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    for name, url, domain in TEST_FEEDS:
        cursor.execute('''
            INSERT OR IGNORE INTO sources (name, rss_url, domain, tier, status)
            VALUES (?, ?, ?, 1, 'active')
        ''', (name, url, domain))

    conn.commit()
    conn.close()


def fetch_test_feeds(db_path: Path) -> int:
    """Fetch from test feeds and return count of new articles."""
    fetcher = RSSFetcher(str(db_path))
    fetcher.init_db()

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    total_new = 0
    for name, url, domain in TEST_FEEDS:
        print(f"  Fetching {name} ... ", end="", flush=True)
        items = fetcher.fetch_feed(url)

        new_items = 0
        for item in items:
            try:
                cursor.execute('''
                    INSERT OR IGNORE INTO articles
                    (title, url, source, domain, content, published_at, fetched_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    item['title'],
                    item['url'],
                    name,
                    domain,
                    item.get('content', '')[:2000],
                    item['published'],
                    datetime.now().isoformat()
                ))
                if cursor.rowcount > 0:
                    new_items += 1
                    total_new += 1
            except Exception as e:
                print(f"insert error: {e}")

        conn.commit()
        print(f"{new_items} new ({len(items)} total)")

    conn.close()
    return total_new


def get_recent_articles(db_path: Path, hours: int = 48) -> list:
    """Get recent articles from DB as story dicts."""
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    cutoff = (datetime.now() - timedelta(hours=hours)).isoformat()

    cursor.execute('''
        SELECT title, url, source, domain, content, published_at
        FROM articles
        WHERE fetched_at > ? OR published_at > ?
        ORDER BY published_at DESC
        LIMIT 100
    ''', (cutoff, cutoff))

    stories = []
    for row in cursor.fetchall():
        stories.append({
            'title': row[0],
            'url': row[1],
            'source': row[2],
            'domain': row[3],
            'content': row[4] or '',
            'published': row[5],
            'tier': 'important',
        })

    conn.close()
    return stories


def generate_briefing(stories: list, output_path: Path) -> tuple:
    """Generate a briefing and write it to output_path."""
    generator = BriefingGenerator(
        max_items_per_section=20,
        max_must_read_total=5,
        max_important_total=15,
        target_reading_time=10,
    )

    result = generator.generate(stories)

    # Render as markdown
    from briefing.renderer import MarkdownRenderer
    renderer = MarkdownRenderer()
    markdown = renderer.render(result)

    output_path.write_text(markdown, encoding='utf-8')

    return result, markdown


def main():
    import time
    start_time = time.time()

    print("=" * 60)
    print("End-to-End RSS Briefing Test")
    print("=" * 60)

    # 1. Setup
    print("\n[1/4] Setting up test database...")
    setup_test_db(DB_PATH)

    # 2. Fetch
    print("\n[2/4] Fetching from test feeds...")
    new_count = fetch_test_feeds(DB_PATH)

    # 3. Get stories
    print("\n[3/4] Retrieving recent articles...")
    stories = get_recent_articles(DB_PATH)
    print(f"  Found {len(stories)} recent articles")

    # 4. Generate briefing
    print("\n[4/4] Generating briefing...")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    briefing_path = OUTPUT_DIR / "e2e_briefing_test.md"
    result, markdown = generate_briefing(stories, briefing_path)

    # Report
    duration = time.time() - start_time
    total_stories = result.metadata.total_stories

    print(f"\n{'='*60}")
    print(f"Results:")
    print(f"  New articles fetched: {new_count}")
    print(f"  Total recent articles: {len(stories)}")
    print(f"  Briefing stories: {total_stories}")
    print(f"  Duration: {duration:.1f}s")
    print(f"  Output: {briefing_path}")
    print(f"{'='*60}")

    # Assertions
    passed = True

    if duration > 60:
        print(f"\nFAIL: Duration {duration:.1f}s > 60s limit")
        passed = False
    else:
        print(f"\nPASS: Duration {duration:.1f}s <= 60s")

    if total_stories >= 3:
        print(f"PASS: Briefing has {total_stories} stories (>= 3)")
    else:
        print(f"FAIL: Briefing has only {total_stories} stories (< 3)")
        passed = False

    if new_count > 0:
        print(f"PASS: Fetched {new_count} new articles")
    else:
        print(f"WARN: No new articles fetched (may be duplicate content)")
        # Not a hard fail — could be all duplicates

    # Write JSON result for CI
    test_result = {
        "test": "e2e_rss_briefing",
        "timestamp": datetime.now().isoformat(),
        "passed": passed,
        "duration_seconds": round(duration, 2),
        "new_articles_fetched": new_count,
        "recent_articles_total": len(stories),
        "briefing_stories": total_stories,
        "briefing_path": str(briefing_path),
        "metadata": result.metadata.to_dict(),
    }

    result_path = OUTPUT_DIR / "e2e_test_result.json"
    with open(result_path, 'w') as f:
        json.dump(test_result, f, indent=2)
    print(f"\nTest result written to: {result_path}")

    # Print first 500 chars of briefing
    print(f"\n--- Briefing excerpt ---")
    print(markdown[:800])
    print("---")

    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
