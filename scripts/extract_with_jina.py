#!/usr/bin/env python3
"""
Extract article content using Jina AI Reader API.

Jina provides a free, fast extraction service that handles
most news sites and blogs without needing a browser.
"""

import sqlite3
import sys
import urllib.request
import urllib.error
from datetime import datetime
import json

DB_PATH = 'news.db'
JINA_BASE = "https://r.jina.ai/http://"


def extract_with_jina(url):
    """Extract content using Jina AI Reader."""
    try:
        jina_url = f"{JINA_BASE}{url}"
        req = urllib.request.Request(
            jina_url,
            headers={
                'User-Agent': 'Mozilla/5.0 (compatible; HighSignalBot/1.0)',
                'Accept': 'text/plain, text/markdown'
            }
        )
        
        with urllib.request.urlopen(req, timeout=20) as response:
            content = response.read().decode('utf-8', errors='ignore')
            
            # Jina returns clean text - check if it's useful
            if len(content) < 200:
                return None, "Content too short (likely paywall or error page)"
            
            # Check for common error patterns
            if any(marker in content.lower() for marker in [
                'access denied', 'subscription required', 'sign in',
                '403 forbidden', 'please enable javascript'
            ]):
                return None, "Paywall or access restriction"
            
            return content[:15000], None  # Limit to 15k chars
            
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}"
    except urllib.error.URLError as e:
        return None, f"URL error: {e.reason}"
    except Exception as e:
        return None, str(e)


def ensure_schema(conn):
    """Ensure articles table has extraction columns."""
    cursor = conn.execute("PRAGMA table_info(articles)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if 'full_content' not in columns:
        conn.execute("ALTER TABLE articles ADD COLUMN full_content TEXT")
    if 'extraction_method' not in columns:
        conn.execute("ALTER TABLE articles ADD COLUMN extraction_method TEXT")
    if 'extraction_status' not in columns:
        conn.execute("ALTER TABLE articles ADD COLUMN extraction_status TEXT DEFAULT 'pending'")
    if 'extracted_at' not in columns:
        conn.execute("ALTER TABLE articles ADD COLUMN extracted_at TIMESTAMP")
    
    conn.commit()


def get_articles_needing_extraction(conn, limit=30):
    """Get articles that need content extraction."""
    cursor = conn.execute('''
        SELECT id, title, url, source, content
        FROM articles
        WHERE (extraction_status = 'pending' OR extraction_status IS NULL)
          AND source IN ('Hacker News', 'Lobsters', 'Distill.pub', 'Hugging Face Blog',
                        'This Week in Rust', 'JavaScript Weekly')
        ORDER BY 
            CASE source
                WHEN 'Distill.pub' THEN 1
                WHEN 'Hugging Face Blog' THEN 2
                WHEN 'Hacker News' THEN 3
                WHEN 'Lobsters' THEN 4
                ELSE 5
            END,
            fetched_at DESC
        LIMIT ?
    ''', (limit,))
    return cursor.fetchall()


def update_extraction(conn, article_id, full_content, status, method='jina'):
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
    print("Jina AI Content Extraction")
    print("=" * 50)
    
    conn = sqlite3.connect(DB_PATH)
    ensure_schema(conn)
    
    # Show current stats
    cursor = conn.execute('''
        SELECT extraction_status, COUNT(*)
        FROM articles
        GROUP BY extraction_status
    ''')
    print("\nCurrent extraction status:")
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]} articles")
    
    articles = get_articles_needing_extraction(conn)
    print(f"\nProcessing {len(articles)} articles...")
    
    success = 0
    failed = 0
    paywalled = 0
    
    for i, (article_id, title, url, source, rss_content) in enumerate(articles, 1):
        print(f"\n[{i}/{len(articles)}] {title[:55]}...")
        print(f"    Source: {source}")
        
        content, error = extract_with_jina(url)
        
        if content:
            update_extraction(conn, article_id, content, 'extracted', 'jina')
            print(f"    ✓ Extracted {len(content)} chars")
            success += 1
        elif 'paywall' in (error or '').lower() or 'access' in (error or '').lower():
            # Store RSS content as fallback
            update_extraction(conn, article_id, rss_content, 'paywalled', 'rss_fallback')
            print(f"    ⚠ Paywalled - using RSS content")
            paywalled += 1
        else:
            update_extraction(conn, article_id, None, f'failed: {error}', None)
            print(f"    ✗ Failed: {error}")
            failed += 1
    
    print(f"\n{'='*50}")
    print(f"Results: {success} success, {paywalled} paywalled, {failed} failed")
    
    # Show extraction quality
    cursor = conn.execute('''
        SELECT extraction_method, extraction_status, COUNT(*), AVG(LENGTH(full_content))
        FROM articles
        WHERE extraction_status IS NOT NULL
        GROUP BY extraction_method, extraction_status
    ''')
    print("\nExtraction quality:")
    for row in cursor.fetchall():
        method, status, count, avg_len = row
        avg_len = int(avg_len or 0)
        print(f"  {method} ({status}): {count} articles, avg {avg_len} chars")
    
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
