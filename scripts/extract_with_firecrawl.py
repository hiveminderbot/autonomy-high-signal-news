#!/usr/bin/env python3
"""
Extract article content using Firecrawl API as fallback for Jina failures.

Firecrawl provides more robust extraction with JavaScript rendering support
for sites that Jina cannot handle (Distill.pub, paywalled content, etc).

Usage:
    python scripts/extract_with_firecrawl.py           # Process all pending/failed
    python scripts/extract_with_firecrawl.py --retry-failed  # Retry only failed
"""

import sqlite3
import sys
import os
import time
import argparse
from datetime import datetime
from urllib.parse import quote

DB_PATH = 'news.db'
FIRECRAWL_API_KEY = os.environ.get('FIRECRAWL_API_KEY')
FIRECRAWL_BASE = "https://api.firecrawl.dev/v1/scrape"

# Rate limiting - Firecrawl free tier: 500 credits/month
# Conservative: 1 request per 3 seconds to stay within limits
RATE_LIMIT_DELAY = 3.0
TIMEOUT_SECONDS = 45


def extract_with_firecrawl(url):
    """Extract content using Firecrawl API."""
    if not FIRECRAWL_API_KEY:
        return None, "FIRECRAWL_API_KEY not set"

    try:
        import urllib.request
        import urllib.error
        import json

        req = urllib.request.Request(
            FIRECRAWL_BASE,
            data=json.dumps({
                "url": url,
                "formats": ["markdown"],
                "onlyMainContent": True,
                "waitFor": 2000,  # Wait 2s for JS rendering
                "timeout": TIMEOUT_SECONDS * 1000,  # ms
            }).encode('utf-8'),
            headers={
                'Authorization': f'Bearer {FIRECRAWL_API_KEY}',
                'Content-Type': 'application/json',
            },
            method='POST'
        )

        with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS + 10) as response:
            result = json.loads(response.read().decode('utf-8'))

            if not result.get('success'):
                error_msg = result.get('error', 'Unknown error')
                return None, f"Firecrawl error: {error_msg}"

            data = result.get('data', {})
            content = data.get('markdown', '')

            if not content or len(content) < 200:
                return None, "Content too short"

            # Check for error patterns
            error_markers = [
                'access denied', 'subscription required', 'sign in',
                'please enable javascript', 'blocked', 'cloudflare'
            ]
            if any(marker in content.lower()[:500] for marker in error_markers):
                return None, "Blocked or paywalled"

            return content[:20000], None  # Limit to 20k chars

    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}"
    except urllib.error.URLError as e:
        return None, f"URL error: {e.reason}"
    except TimeoutError:
        return None, "Timeout"
    except Exception as e:
        return None, str(e)


def get_articles_to_process(conn, retry_failed=False, source_filter=None):
    """Get articles that need extraction."""
    if retry_failed:
        # Retry articles that failed with Jina
        cursor = conn.execute('''
            SELECT id, title, url, source, content, extraction_status
            FROM articles
            WHERE extraction_status LIKE 'failed%'
               OR extraction_status = 'rss_only'
            ORDER BY
                CASE source
                    WHEN 'Distill.pub' THEN 1
                    WHEN 'Hugging Face Blog' THEN 2
                    WHEN 'arXiv cs.AI' THEN 3
                    WHEN 'arXiv cs.LG' THEN 4
                    ELSE 5
                END
            LIMIT 50
        ''')
    else:
        # Get pending articles
        where_clause = "(extraction_status = 'pending' OR extraction_status IS NULL)"
        params = ()
        if source_filter:
            where_clause += " AND source = ?"
            params = (source_filter,)

        cursor = conn.execute(f'''
            SELECT id, title, url, source, content, extraction_status
            FROM articles
            WHERE {where_clause}
            ORDER BY fetched_at DESC
            LIMIT 30
        ''', params)

    return cursor.fetchall()


def update_extraction(conn, article_id, full_content, status, method='firecrawl'):
    """Update article with extracted content."""
    conn.execute('''
        UPDATE articles
        SET full_content = ?,
            extraction_status = ?,
            extraction_method = ?,
            extracted_at = ?
        WHERE id = ?
    ''', (full_content, status, method, datetime.now().isoformat(), article_id))
    conn.commit()


def main():
    parser = argparse.ArgumentParser(description='Extract articles using Firecrawl')
    parser.add_argument('--retry-failed', action='store_true',
                        help='Retry previously failed articles')
    parser.add_argument('--source', type=str, default=None,
                        help='Filter by source (e.g., "Distill.pub")')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be processed without extracting')
    args = parser.parse_args()

    print("Firecrawl Content Extraction")
    print("=" * 50)

    if not FIRECRAWL_API_KEY:
        print("\n⚠️  FIRECRAWL_API_KEY not set in environment")
        print("Set it with: export FIRECRAWL_API_KEY=your_key")
        return 1

    conn = sqlite3.connect(DB_PATH)

    articles = get_articles_to_process(conn, args.retry_failed, args.source)
    print(f"\nProcessing {len(articles)} articles...")

    if args.dry_run:
        for article_id, title, url, source, content, status in articles:
            print(f"  [{source}] {title[:50]}...")
            print(f"      Status: {status}")
            print(f"      URL: {url[:60]}...")
        return 0

    success = 0
    failed = 0
    paywalled = 0

    for i, (article_id, title, url, source, rss_content, prev_status) in enumerate(articles, 1):
        print(f"\n[{i}/{len(articles)}] {title[:55]}...")
        print(f"    Source: {source}")
        print(f"    Previous: {prev_status}")

        content, error = extract_with_firecrawl(url)

        if content:
            update_extraction(conn, article_id, content, 'extracted', 'firecrawl')
            print(f"    ✓ Extracted {len(content)} chars")
            success += 1
        elif 'paywall' in (error or '').lower() or 'blocked' in (error or '').lower():
            # Keep previous content if available
            fallback = rss_content if rss_content else None
            update_extraction(conn, article_id, fallback, 'paywalled', 'firecrawl_fallback')
            print(f"    ⚠ Paywalled/blocked")
            paywalled += 1
        else:
            # Mark as failed with firecrawl
            new_status = f'failed: {error}'
            update_extraction(conn, article_id, None, new_status, 'firecrawl_failed')
            print(f"    ✗ Failed: {error}")
            failed += 1

        # Rate limiting
        if i < len(articles):
            time.sleep(RATE_LIMIT_DELAY)

    print(f"\n{'='*50}")
    print(f"Results: {success} success, {paywalled} paywalled, {failed} failed")

    # Show updated stats
    cursor = conn.execute('''
        SELECT extraction_method, extraction_status, COUNT(*)
        FROM articles
        WHERE extraction_status IS NOT NULL
        GROUP BY extraction_method, extraction_status
    ''')
    print("\nUpdated extraction breakdown:")
    for row in cursor.fetchall():
        method, status, count = row
        print(f"  {method} ({status}): {count}")

    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
