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
import re
from urllib.parse import urlparse
from datetime import datetime
from html.parser import HTMLParser

DB_PATH = 'news.db'


class MLStripper(HTMLParser):
    """Strip HTML tags and extract text."""
    def __init__(self):
        super().__init__()
        self.reset()
        self.fed = []
        self.skip_tags = {'script', 'style', 'nav', 'header', 'footer'}
        self.current_tag = None

    def handle_starttag(self, tag, attrs):
        self.current_tag = tag
        if tag == 'br':
            self.fed.append('\n')
        elif tag in ['p', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li']:
            self.fed.append('\n')

    def handle_endtag(self, tag):
        self.current_tag = None

    def handle_data(self, d):
        if self.current_tag not in self.skip_tags:
            self.fed.append(d)

    def get_data(self):
        return ''.join(self.fed)


def strip_html(html):
    """Remove HTML tags and return plain text."""
    s = MLStripper()
    try:
        s.feed(html)
        return s.get_data()
    except:
        # Fallback: regex-based stripping
        text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<[^>]+>', ' ', text)
        return text


def clean_text(text):
    """Clean up extracted text."""
    # Replace multiple whitespace with single space
    text = re.sub(r'\s+', ' ', text)
    # Replace multiple newlines with double newline
    text = re.sub(r'\n\s*\n+', '\n\n', text)
    # Remove very short lines (likely UI elements)
    lines = text.split('\n')
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        if len(stripped) > 30 or (len(stripped) > 10 and '.' in stripped):
            cleaned_lines.append(stripped)
    return '\n'.join(cleaned_lines[:200])  # First 200 lines


def extract_github_readme(html, url):
    """Extract README content from GitHub repo page HTML."""
    # Try to find README content in various GitHub selectors
    patterns = [
        r'<article[^>]*class="[^"]*markdown-body[^"]*"[^>]*>(.*?)</article>',
        r'<div[^>]*class="[^"]*markdown-body[^"]*"[^>]*>(.*?)</div>',
        r'<div[^>]*data-target="readme-toc\.content"[^>]*>(.*?)</div>',
        r'<div[^>]*id="readme"[^>]*>.*?<article[^>]*>(.*?)</article>',
    ]

    for pattern in patterns:
        match = re.search(pattern, html, re.DOTALL | re.IGNORECASE)
        if match:
            content = match.group(1)
            # Remove any nested divs that might be ads/notifications
            content = re.sub(r'<div[^>]*class="[^"]*flash[^"]*"[^>]*>.*?</div>', '', content, flags=re.DOTALL | re.IGNORECASE)
            return strip_html(content)

    # Fallback: extract from entire page
    return clean_text(strip_html(html))


def extract_with_browser(url):
    """Extract article content using agent-browser."""
    try:
        # Use agent-browser to navigate to the page
        result = subprocess.run(
            ['agent-browser', '--json', 'open', url],
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            return None, f"Browser error: {result.stderr}"

        # Get page HTML content
        result = subprocess.run(
            ['agent-browser', 'get', 'html', 'body'],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            return None, f"Failed to get HTML: {result.stderr}"

        html = result.stdout

        if not html or len(html) < 100:
            return None, "Empty HTML response"

        # Special handling for GitHub repos
        if 'github.com' in url:
            content = extract_github_readme(html, url)
            if content and len(content) > 200:
                return content[:15000], None  # Limit to 15k chars

        # General extraction
        text = strip_html(html)
        content = clean_text(text)

        if len(content) < 200:
            return None, f"Content too short ({len(content)} chars)"

        return content[:15000], None  # Limit to 15k chars

    except subprocess.TimeoutExpired:
        return None, "Timeout"
    except Exception as e:
        return None, str(e)


def extract_with_jina(url):
    """Fallback: Extract using Jina AI Reader API (free tier)."""
    import urllib.request

    try:
        # Jina AI Reader API
        jina_url = f"https://r.jina.ai/http://{url}"
        req = urllib.request.Request(
            jina_url,
            headers={'User-Agent': 'Mozilla/5.0 (compatible; Bot/1.0)'}
        )

        with urllib.request.urlopen(req, timeout=15) as response:
            content = response.read().decode('utf-8')
            return content[:10000], None  # Limit to 10k chars

    except Exception as e:
        return None, f"Jina extraction failed: {e}"


def get_paywalled_articles(conn, limit=10):
    """Get articles marked as paywalled that might be extractable via browser."""
    cursor = conn.execute('''
        SELECT id, title, url, source
        FROM articles
        WHERE extraction_status = 'paywalled'
        ORDER BY fetched_at DESC
        LIMIT ?
    ''', (limit,))
    return cursor.fetchall()


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


def update_article_content(conn, article_id, full_content, extraction_method, extraction_status='extracted'):
    """Update article with extracted content."""
    conn.execute('''
        UPDATE articles
        SET full_content = ?,
            extraction_method = ?,
            extraction_status = ?,
            extracted_at = ?
        WHERE id = ?
    ''', (full_content, extraction_method, extraction_status, datetime.now().isoformat(), article_id))
    conn.commit()


def test_extraction(conn, url, title):
    """Test extraction on a single URL and report results."""
    print(f"\nTesting: {title[:60]}...")
    print(f"URL: {url}")

    # Try browser extraction first for GitHub and JS-heavy sites
    if 'github.com' in url or 'distill.pub' in url:
        print("  Trying browser extraction...")
        content, error = extract_with_browser(url)
        if content:
            print(f"  ✓ Browser success: {len(content)} chars")
            return content, 'browser'
        else:
            print(f"  ✗ Browser failed: {error}")

    # Try Jina AI
    print("  Trying Jina AI extraction...")
    content, error = extract_with_jina(url)
    if content:
        print(f"  ✓ Jina success: {len(content)} chars")
        return content, 'jina'
    else:
        print(f"  ✗ Jina failed: {error}")

    # Final fallback to browser for any remaining
    if 'github.com' not in url:
        print("  Trying browser as fallback...")
        content, error = extract_with_browser(url)
        if content:
            print(f"  ✓ Browser fallback success: {len(content)} chars")
            return content, 'browser_fallback'
        else:
            print(f"  ✗ Browser fallback failed: {error}")

    return None, None


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Browser-based content extraction')
    parser.add_argument('--test-paywalled', action='store_true',
                        help='Test extraction on paywalled articles')
    parser.add_argument('--extract-all', action='store_true',
                        help='Extract content for all articles needing it')
    parser.add_argument('--url', type=str, help='Test extraction on specific URL')
    args = parser.parse_args()

    print("Browser-based Content Extraction")
    print("=" * 50)

    conn = sqlite3.connect(DB_PATH)

    # Ensure table has full_content column
    try:
        conn.execute("ALTER TABLE articles ADD COLUMN full_content TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE articles ADD COLUMN extraction_method TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE articles ADD COLUMN extracted_at TIMESTAMP")
    except sqlite3.OperationalError:
        pass
    conn.commit()

    if args.url:
        # Test specific URL
        content, method = test_extraction(conn, args.url, "Test URL")
        if content:
            print(f"\nExtracted content ({len(content)} chars):")
            print("-" * 50)
            print(content[:2000])
            print("-" * 50)
        conn.close()
        return 0

    if args.test_paywalled:
        # Test on paywalled articles
        articles = get_paywalled_articles(conn)
        print(f"\nFound {len(articles)} paywalled articles to test")

        success_count = 0
        for article_id, title, url, source in articles:
            content, method = test_extraction(conn, url, title)
            if content:
                update_article_content(conn, article_id, content, method, 'extracted')
                success_count += 1
                print(f"  → Updated article {article_id} as extracted")
            else:
                print(f"  → Article {article_id} remains paywalled")

        print(f"\n{'='*50}")
        print(f"Results: {success_count}/{len(articles)} paywalled articles recovered")
        conn.close()
        return 0

    if args.extract_all:
        # Extract all articles needing extraction
        articles = get_articles_needing_extraction(conn)
        print(f"\nFound {len(articles)} articles needing extraction")

        success_count = 0
        fail_count = 0

        for i, (article_id, title, url, source) in enumerate(articles, 1):
            print(f"\n[{i}/{len(articles)}] {title[:60]}...")
            print(f"    Source: {source}")
            print(f"    URL: {url[:80]}...")

            content, method = test_extraction(conn, url, title)
            if content:
                update_article_content(conn, article_id, content, method)
                print(f"    ✓ Saved to database ({method})")
                success_count += 1
            else:
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

    # Default: show usage
    parser.print_help()
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
