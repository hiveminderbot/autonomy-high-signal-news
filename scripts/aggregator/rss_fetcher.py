#!/usr/bin/env python3
"""RSS feed fetcher - fetches from configured feeds, not search APIs."""

import sqlite3
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import httpx
from pathlib import Path


class RSSFetcher:
    """Fetch and parse RSS feeds from configured sources."""

    def __init__(self, db_path: str = "news.db"):
        self.db_path = db_path
        self.client = httpx.Client(
            timeout=30.0,
            follow_redirects=True,
            headers={
                "User-Agent": "HighSignalNews/1.0 (RSS Aggregator)"
            }
        )
        self.init_db()

    def init_db(self):
        """Initialize database with sources table."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sources (
                id INTEGER PRIMARY KEY,
                name TEXT,
                rss_url TEXT UNIQUE,
                domain TEXT,
                tier INTEGER,  -- 1 = essential, 2 = high quality
                last_fetch TEXT,
                status TEXT DEFAULT 'active'
            )
        ''')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS articles (
                id INTEGER PRIMARY KEY,
                title TEXT,
                url TEXT UNIQUE,
                source_id INTEGER,
                content TEXT,
                published_at TEXT,
                fetched_at TEXT,
                FOREIGN KEY (source_id) REFERENCES sources(id)
            )
        ''')

        conn.commit()
        conn.close()

    def bootstrap_mvp_sources(self):
        """Add MVP feed sources to database."""
        mvp_sources = [
            # AI
            ("Hacker News", "https://news.ycombinator.com/rss", "software_development", 1),
            ("Import AI", "https://importai.substack.com/feed", "ai", 1),
            ("The Batch", "https://read.deeplearning.ai/the-batch/feed/", "ai", 1),
            ("OpenAI Blog", "https://openai.com/blog/rss.xml", "ai", 1),
            ("Papers with Code", "https://paperswithcode.com/feed", "ai", 1),
            ("arXiv cs.AI", "https://export.arxiv.org/rss/cs.AI", "ai", 1),

            # Dev
            ("Python Insider", "https://pythoninsider.blogspot.com/feeds/posts/default", "software_development", 1),
            ("Go Blog", "https://go.dev/blog/feed.atom", "software_development", 1),
            ("GitHub Changelog", "https://github.blog/changelog/feed/", "software_development", 1),
            ("This Week in Rust", "https://this-week-in-rust.org/rss.xml", "software_development", 1),
            ("Lobsters", "https://lobste.rs/rss", "software_development", 1),

            # Investment
            ("TechCrunch", "https://techcrunch.com/feed/", "investment", 1),
            ("TechCrunch Venture", "https://techcrunch.com/category/venture/feed/", "investment", 1),
            ("Crunchbase News", "https://news.crunchbase.com/feed/", "investment", 1),
            ("VC News Daily", "https://vcnewsdaily.com/feed/", "investment", 1),
        ]

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        for name, url, domain, tier in mvp_sources:
            cursor.execute('''
                INSERT OR IGNORE INTO sources (name, rss_url, domain, tier, status)
                VALUES (?, ?, ?, ?, 'active')
            ''', (name, url, domain, tier))

        conn.commit()
        conn.close()
        print(f"✓ Bootstrapped {len(mvp_sources)} MVP sources")

    def fetch_feed(self, rss_url: str) -> List[Dict]:
        """Fetch and parse a single RSS feed."""
        try:
            response = self.client.get(rss_url)
            response.raise_for_status()

            # Parse XML
            root = ET.fromstring(response.content)

            # Handle both RSS and Atom
            items = []

            # RSS 2.0
            for item in root.findall('.//item'):
                title = item.find('title')
                link = item.find('link')
                pub_date = item.find('pubDate')
                description = item.find('description')

                if title is not None and link is not None:
                    items.append({
                        'title': title.text or "",
                        'url': link.text or "",
                        'published': pub_date.text if pub_date is not None else datetime.now().isoformat(),
                        'content': description.text if description is not None else ""
                    })

            # Media RSS (MRSS) - e.g. YouTube, Substack audio
            media_ns = {'media': 'http://search.yahoo.com/mrss'}
            for item in root.findall('.//item'):
                title = item.find('title')
                link = item.find('link')
                pub_date = item.find('pubDate')
                media_content = item.find('media:content', media_ns)
                description = item.find('description')

                if title is not None and link is not None:
                    media_url = media_content.get('url') if media_content is not None else None
                    content = description.text if description is not None else ""
                    if media_url:
                        content = f"{content}\n[Media: {media_url}]".strip()
                    items.append({
                        'title': title.text or "",
                        'url': link.text or "",
                        'published': pub_date.text if pub_date is not None else datetime.now().isoformat(),
                        'content': content
                    })

            # Atom
            ns = {'atom': 'http://www.w3.org/2005/Atom'}
            for entry in root.findall('.//atom:entry', ns):
                title = entry.find('atom:title', ns)
                link = entry.find('atom:link', ns)
                pub_date = entry.find('atom:updated', ns) or entry.find('atom:published', ns)
                summary = entry.find('atom:summary', ns)

                if title is not None and link is not None:
                    items.append({
                        'title': title.text or "",
                        'url': link.get('href', ''),
                        'published': pub_date.text if pub_date is not None else datetime.now().isoformat(),
                        'content': summary.text if summary is not None else ""
                    })

            return items

        except Exception as e:
            print(f"  ✗ Failed to fetch {rss_url}: {e}")
            return []

    def fetch_all_feeds(self, hours: int = 24):
        """Fetch all configured feeds."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get active sources
        cursor.execute('SELECT id, name, rss_url, domain FROM sources WHERE status = "active"')
        sources = cursor.fetchall()

        total_new = 0
        cutoff = datetime.now() - timedelta(hours=hours)

        for source_id, name, rss_url, domain in sources:
            print(f"Fetching: {name}")
            items = self.fetch_feed(rss_url)

            new_items = 0
            for item in items:
                try:
                    pub_dt = datetime.fromisoformat(item['published'].replace('Z', '+00:00'))
                    if pub_dt >= cutoff:
                        cursor.execute('''
                            INSERT OR IGNORE INTO articles
                            (title, url, source_id, content, published_at, fetched_at)
                            VALUES (?, ?, ?, ?, ?, ?)
                        ''', (
                            item['title'],
                            item['url'],
                            source_id,
                            item['content'],
                            item['published'],
                            datetime.now().isoformat()
                        ))
                        if cursor.rowcount > 0:
                            new_items += 1
                            total_new += 1
                except Exception as e:
                    print(f"  ✗ Insert failed: {e}")

            # Update last fetch time
            cursor.execute('UPDATE sources SET last_fetch = ? WHERE id = ?',
                         (datetime.now().isoformat(), source_id))

            print(f"  ✓ {new_items} new articles")

        conn.commit()
        conn.close()

        print(f"\n✓ Total: {total_new} new articles from {len(sources)} sources")
        return total_new

    def close(self):
        """Close HTTP client."""
        self.client.close()


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Fetch RSS feeds")
    parser.add_argument("--bootstrap", action="store_true", help="Add MVP sources")
    parser.add_argument("--hours", type=int, default=24, help="Only fetch recent items")
    parser.add_argument("--db", default="news.db", help="Database path")

    args = parser.parse_args()

    fetcher = RSSFetcher(args.db)

    if args.bootstrap:
        fetcher.bootstrap_mvp_sources()

    fetcher.fetch_all_feeds(args.hours)
    fetcher.close()


if __name__ == "__main__":
    main()
