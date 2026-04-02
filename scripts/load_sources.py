#!/usr/bin/env python3
"""
Load RSS sources from sources-v2-bootstrapped.json into news.db.

Usage:
    python scripts/load_sources.py [--dry-run] [--source-file PATH]

Options:
    --dry-run       Show what would be inserted without modifying database
    --source-file   Path to JSON source file (default: sources/sources-v2-bootstrapped.json)
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Dict, List, Tuple


def get_db_path() -> Path:
    """Get the path to the news database."""
    script_dir = Path(__file__).parent.parent
    db_path = script_dir / "news.db"
    return db_path


def get_source_file_path(custom_path: str = None) -> Path:
    """Get the path to the sources JSON file."""
    script_dir = Path(__file__).parent.parent
    if custom_path:
        return Path(custom_path)
    return script_dir / "sources" / "sources-v2-bootstrapped.json"


def load_sources_from_json(file_path: Path) -> List[Dict]:
    """Load and normalize sources from the JSON file."""
    with open(file_path, 'r') as f:
        data = json.load(f)

    sources = []

    # Process RSS feeds
    for feed in data.get('rss_feeds', []):
        sources.append({
            'name': feed['name'],
            'rss_url': feed['url'],
            'domain': feed['category'],
            'tier': 1 if feed['quality_score'] >= 9 else 2,
            'category': feed['category'],
            'frequency': feed['frequency'],
            'quality_score': feed['quality_score'],
            'special_handling': json.dumps({
                'focus': feed.get('focus', ''),
                'notes': feed.get('notes', ''),
                'type': feed.get('type', 'rss')
            })
        })

    # Process newsletters (use rss_url if available)
    for newsletter in data.get('newsletters', []):
        rss_url = newsletter.get('rss_url', newsletter.get('url', ''))
        sources.append({
            'name': newsletter['name'],
            'rss_url': rss_url,
            'domain': newsletter['category'],
            'tier': 1 if newsletter['quality_score'] >= 9 else 2,
            'category': newsletter['category'],
            'frequency': newsletter['frequency'],
            'quality_score': newsletter['quality_score'],
            'special_handling': json.dumps({
                'focus': newsletter.get('focus', ''),
                'notes': newsletter.get('notes', ''),
                'type': newsletter.get('type', 'newsletter'),
                'original_url': newsletter.get('url', '')
            })
        })

    # Process special handling sources (respect enabled flag)
    for special in data.get('special_handling', []):
        # Skip disabled sources
        if not special.get('enabled', True):
            continue

        rss_url = special.get('rss_url', special.get('url', ''))
        handling = {
            'focus': special.get('focus', ''),
            'notes': special.get('notes', ''),
            'type': special.get('type', 'rss'),
            'min_fetch_interval': special.get('min_fetch_interval', 5)
        }

        sources.append({
            'name': special['name'],
            'rss_url': rss_url,
            'domain': special['category'],
            'tier': 1 if special['quality_score'] >= 9 else 2,
            'category': special['category'],
            'frequency': special['frequency'],
            'quality_score': special['quality_score'],
            'special_handling': json.dumps(handling)
        })

    return sources


def check_existing_sources(conn: sqlite3.Connection, urls: List[str]) -> Dict[str, int]:
    """Check which URLs already exist in the database."""
    cursor = conn.cursor()
    existing = {}

    for url in urls:
        cursor.execute('SELECT id FROM sources WHERE rss_url = ?', (url,))
        row = cursor.fetchone()
        if row:
            existing[url] = row[0]

    return existing


def insert_sources(conn: sqlite3.Connection, sources: List[Dict], dry_run: bool = False) -> Tuple[int, int, int]:
    """Insert sources into database. Returns (inserted, skipped, failed) counts."""
    cursor = conn.cursor()

    # Check existing sources
    urls = [s['rss_url'] for s in sources]
    existing = check_existing_sources(conn, urls)

    inserted = 0
    skipped = 0
    failed = 0

    for source in sources:
        if source['rss_url'] in existing:
            skipped += 1
            print(f"  SKIP: {source['name']} (already exists)")
            continue

        try:
            if not dry_run:
                cursor.execute('''
                    INSERT INTO sources
                    (name, rss_url, domain, tier, category, frequency, quality_score, special_handling, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active')
                ''', (
                    source['name'],
                    source['rss_url'],
                    source['domain'],
                    source['tier'],
                    source['category'],
                    source['frequency'],
                    source['quality_score'],
                    source['special_handling']
                ))
                conn.commit()
            inserted += 1
            print(f"  {'WOULD INSERT' if dry_run else 'INSERT'}: {source['name']} (score: {source['quality_score']})")
        except sqlite3.Error as e:
            failed += 1
            print(f"  ERROR: {source['name']} - {e}")

    return inserted, skipped, failed


def main():
    parser = argparse.ArgumentParser(
        description='Load RSS sources into news.db from JSON catalog'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be inserted without modifying database'
    )
    parser.add_argument(
        '--source-file',
        type=str,
        help='Path to JSON source file (default: sources/sources-v2-bootstrapped.json)'
    )

    args = parser.parse_args()

    # Check database exists
    db_path = get_db_path()
    if not db_path.exists():
        print(f"ERROR: Database not found at {db_path}")
        print("Run: python scripts/aggregator/init_db.py")
        sys.exit(1)

    # Check source file exists
    source_file = get_source_file_path(args.source_file)
    if not source_file.exists():
        print(f"ERROR: Source file not found at {source_file}")
        sys.exit(1)

    print(f"Database: {db_path}")
    print(f"Source file: {source_file}")
    print(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    print()

    # Load sources from JSON
    try:
        sources = load_sources_from_json(source_file)
        print(f"Loaded {len(sources)} sources from JSON")
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in source file: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Failed to load sources: {e}")
        sys.exit(1)

    # Connect to database and insert sources
    conn = sqlite3.connect(db_path)
    try:
        inserted, skipped, failed = insert_sources(conn, sources, dry_run=args.dry_run)
    finally:
        conn.close()

    # Print summary
    print()
    print("=" * 50)
    print("SUMMARY")
    print("=" * 50)
    print(f"Total sources in JSON: {len(sources)}")
    print(f"Inserted: {inserted}")
    print(f"Skipped (existing): {skipped}")
    print(f"Failed: {failed}")

    if args.dry_run:
        print()
        print("DRY RUN complete - no changes made")
        print("Run without --dry-run to insert sources")

    # Exit with error if any failed
    if failed > 0:
        sys.exit(1)


if __name__ == '__main__':
    main()
