#!/usr/bin/env python3
"""
Fix failed article extractions by updating URLs and re-extracting content.

Articles 12, 13, 15, 16, 17, 19 have generic listing page URLs instead of
specific article URLs. This script updates them to correct URLs and re-extracts.
"""

import sqlite3
import json
import urllib.request
import sys
from datetime import datetime

DB_PATH = 'news.db'
JINA_BASE = "https://r.jina.ai/http://"

# Correct URLs for the failed articles
ARTICLE_FIXES = {
    12: {
        "title": "Anthropic publishes new research on AI safety and alignment",
        "new_url": "https://www.anthropic.com/research/provably-safe-ai",
        "source": "Anthropic Research",
        "domain": "ai_research"
    },
    13: {
        "title": "Google DeepMind announces breakthrough in protein folding",
        "new_url": "https://deepmind.google/discover/blog/alphafold-3-predicts-the-structure-and-interactions-of-all-of-lifes-molecules/",
        "source": "DeepMind Blog",
        "domain": "ai_research"
    },
    15: {
        "title": "Rust 1.85 stabilizes new async features",
        "new_url": "https://blog.rust-lang.org/2025/02/20/Rust-1.85.0.html",
        "source": "Rust Blog",
        "domain": "dev_language"
    },
    16: {
        "title": "React 19 beta released with compiler optimizations",
        "new_url": "https://react.dev/blog/2024/04/25/react-19",
        "source": "React Blog",
        "domain": "dev_framework"
    },
    17: {
        "title": "Anthropic reportedly raising $2B at $60B valuation",
        "new_url": "https://techcrunch.com/2024/09/18/anthropic-is-raising-2b-from-google-and-others-at-a-60b-valuation/",
        "source": "TechCrunch",
        "domain": "investment"
    },
    19: {
        "title": "Sequoia announces new $2B fund focused on AI infrastructure",
        "new_url": "https://www.sequoiacap.com/article/sequoia-announces-2b-fund-for-ai-startups/",
        "source": "Sequoia Capital",
        "domain": "investment"
    }
}


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
        
        with urllib.request.urlopen(req, timeout=30) as response:
            content = response.read().decode('utf-8', errors='ignore')
            
            if len(content) < 200:
                return None, "Content too short"
            
            if '404' in content and 'Not Found' in content:
                return None, "404 Not Found"
            
            return content[:15000], None
            
    except Exception as e:
        return None, str(e)


def update_article_and_extract(conn, article_id, fix_data):
    """Update article URL and re-extract content."""
    cursor = conn.cursor()
    
    # Update URL
    cursor.execute('''
        UPDATE articles
        SET url = ?, source = ?, domain = ?
        WHERE id = ?
    ''', (fix_data['new_url'], fix_data['source'], fix_data['domain'], article_id))
    
    conn.commit()
    print(f"  ✓ Updated URL to: {fix_data['new_url']}")
    
    # Extract new content
    print(f"  → Extracting content with Jina AI...")
    content, error = extract_with_jina(fix_data['new_url'])
    
    if content:
        cursor.execute('''
            UPDATE articles
            SET full_content = ?,
                extraction_status = 'extracted',
                extraction_method = 'jina',
                extracted_at = ?
            WHERE id = ?
        ''', (content, datetime.now().isoformat(), article_id))
        conn.commit()
        print(f"  ✓ Extracted {len(content)} characters")
        return True
    else:
        cursor.execute('''
            UPDATE articles
            SET extraction_status = 'failed',
                extraction_method = NULL
            WHERE id = ?
        ''', (article_id,))
        conn.commit()
        print(f"  ✗ Extraction failed: {error}")
        return False


def main():
    print("Fixing Failed Article Extractions")
    print("=" * 60)
    
    conn = sqlite3.connect(DB_PATH)
    
    success_count = 0
    fail_count = 0
    
    for article_id, fix_data in ARTICLE_FIXES.items():
        print(f"\n[{article_id}] {fix_data['title']}")
        print("-" * 60)
        
        # Get current URL
        cursor = conn.execute("SELECT url FROM articles WHERE id = ?", (article_id,))
        row = cursor.fetchone()
        if row:
            print(f"  Old URL: {row[0]}")
        
        # Update and extract
        if update_article_and_extract(conn, article_id, fix_data):
            success_count += 1
        else:
            fail_count += 1
    
    print(f"\n{'='*60}")
    print(f"Results: {success_count} fixed, {fail_count} still failed")
    
    # Show final status
    print("\nFinal article status:")
    cursor = conn.execute('''
        SELECT id, title, extraction_status, LENGTH(full_content)
        FROM articles
        WHERE id IN (12, 13, 15, 16, 17, 19)
        ORDER BY id
    ''')
    
    for row in cursor.fetchall():
        status_icon = "✓" if row[2] == 'extracted' and row[3] and row[3] > 500 else "✗"
        print(f"  {status_icon} [{row[0]}] {row[1][:50]}... ({row[2]}, {row[3] or 0} chars)")
    
    conn.close()
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
