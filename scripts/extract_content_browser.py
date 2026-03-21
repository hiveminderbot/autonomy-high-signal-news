#!/usr/bin/env python3
"""
Browser-based content extraction using agent-browser.

Extracts full article content by rendering pages in a real browser,
not just parsing RSS feeds.
"""

import subprocess
import json
import sqlite3
import sys
from urllib.parse import urlparse
from datetime import datetime

DB_PATH = 'news.db'


def extract_with_browser(url):
    """Extract article content using agent-browser."""
    try:
        # Use agent-browser to navigate and extract content
        result = subprocess.run(
            ['agent-browser', '--json', 'open', url],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            return None, f"Browser error: {result.stderr}"
        
        # Get page content via snapshot
        result = subprocess.run(
            ['agent-browser', '--json', 'snapshot'],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode != 0:
            return None, "Snapshot failed"
        
        try:
            data = json.loads(result.stdout)
            content = data.get('content', '')
            
            # Clean up content (remove navigation, etc)
            lines = [l.strip() for l in content.split('\n') if l.strip()]
            # Filter out short lines that are likely UI elements
            content_lines = [l for l in lines if len(l) > 40 or '.' in l]
            
            return '\n'.join(content_lines[:100]), None  # First 100 lines
            
        except json.JSONDecodeError:
            return None, "Invalid JSON from browser"
            
    except subprocess.TimeoutExpired:
        return None, "Timeout"
    except Exception as e:
        return None, str(e)


def extract_with_jina(url):
    """Fallback: Extract using Jina AI Reader API (free tier)."""
    import urllib.request
    
    try:
        jina_url = f"https://r.jina.ai/http://{url}"
        req = urllib.request.Request(
            jina_url,
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        
        with urllib.request.urlopen(req, timeout=15) as response:
            content = response.read().decode('utf-8')
            return content[:10000], None  # Limit to 10k chars
            
    except Exception as e:
        return None, f"Jina extraction failed: {e}"


def get_articles_needing_extraction(conn, limit=20):
    """Get articles that need full content extraction."""
    cursor = conn.execute('''
        SELECT id, title, url, source
        FROM articles
        WHERE (full_content IS NULL OR LENGTH(full_content) < 500)
          AND source IN ('Hacker News', 'Lobsters', 'Distill.pub', 'Hugging Face Blog')
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


def update_article_content(conn, article_id, full_content, extraction_method):
    """Update article with extracted content."""
    conn.execute('''
        UPDATE articles
        SET full_content = ?,
            extraction_method = ?,
            extracted_at = ?
        WHERE id = ?
    ''', (full_content, extraction_method, datetime.now().isoformat(), article_id))
    conn.commit()


def main():
    print("Browser-based Content Extraction")
    print("=" * 50)
    
    conn = sqlite3.connect(DB_PATH)
    
    # Ensure table has full_content column
    try:
        conn.execute("ALTER TABLE articles ADD COLUMN full_content TEXT")
        conn.execute("ALTER TABLE articles ADD COLUMN extraction_method TEXT")
        conn.execute("ALTER TABLE articles ADD COLUMN extracted_at TIMESTAMP")
        conn.commit()
    except sqlite3.OperationalError:
        pass  # Columns already exist
    
    articles = get_articles_needing_extraction(conn)
    print(f"\nFound {len(articles)} articles needing extraction")
    
    success_count = 0
    fail_count = 0
    
    for i, (article_id, title, url, source) in enumerate(articles, 1):
        print(f"\n[{i}/{len(articles)}] {title[:60]}...")
        print(f"    Source: {source}")
        print(f"    URL: {url[:80]}...")
        
        # Try browser first for JS-heavy sites
        if 'distill.pub' in url or 'huggingface.co' in url:
            print("    Trying browser extraction...")
            content, error = extract_with_browser(url)
            method = "browser"
            
            if not content:
                print(f"    Browser failed: {error}")
                print("    Trying Jina AI fallback...")
                content, error = extract_with_jina(url)
                method = "jina"
        else:
            # Try Jina first for simpler sites
            print("    Trying Jina AI extraction...")
            content, error = extract_with_jina(url)
            method = "jina"
        
        if content and len(content) > 500:
            update_article_content(conn, article_id, content, method)
            print(f"    ✓ Success ({len(content)} chars, {method})")
            success_count += 1
        else:
            print(f"    ✗ Failed: {error or 'Content too short'}")
            fail_count += 1
    
    print(f"\n{'='*50}")
    print(f"Results: {success_count} success, {fail_count} failed")
    
    # Show extraction stats
    cursor = conn.execute('''
        SELECT extraction_method, COUNT(*), AVG(LENGTH(full_content))
        FROM articles
        WHERE full_content IS NOT NULL
        GROUP BY extraction_method
    ''')
    print("\nExtraction method breakdown:")
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]} articles, avg {int(row[2] or 0)} chars")
    
    conn.close()
    return 0 if success_count > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
