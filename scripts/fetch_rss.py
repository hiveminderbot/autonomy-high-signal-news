#!/usr/bin/env python3
"""Fetch RSS feeds and store in database."""

import feedparser
import sqlite3
import sys
from datetime import datetime

DB_PATH = 'news.db'

# List of RSS feeds to fetch
feeds = [
    ('https://news.ycombinator.com/rss', 'Hacker News', 'tech_news'),
    ('https://rss.arxiv.org/rss/cs.AI', 'arXiv cs.AI', 'ai_research'),
    ('https://huggingface.co/blog/feed.xml', 'Hugging Face Blog', 'ai_tools'),
    ('https://this-week-in-rust.org/rss.xml', 'This Week in Rust', 'dev_language'),
    ('https://cprss.s3.amazonaws.com/javascriptweekly.com.xml', 'JavaScript Weekly', 'dev_language'),
    ('https://lobste.rs/rss', 'Lobsters', 'dev_community'),
    ('https://distill.pub/rss.xml', 'Distill.pub', 'ai_research'),
]


def main():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    total_new = 0
    for url, source_name, domain in feeds:
        print(f"\n=== Fetching {source_name} ===")
        try:
            feed = feedparser.parse(url)
            print(f"  Got {len(feed.entries)} entries")
            
            new_entries = 0
            for entry in feed.entries[:10]:
                try:
                    title = entry.get('title', 'Untitled')
                    link = entry.get('link', '')
                    summary = entry.get('summary', '')[:500]
                    published = entry.get('published', datetime.now().isoformat())
                    
                    cursor.execute('''
                        INSERT OR IGNORE INTO articles (title, url, source, domain, content, published_at, fetched_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (title, link, source_name, domain, summary, published, datetime.now().isoformat()))
                    
                    if cursor.rowcount > 0:
                        new_entries += 1
                except Exception as e:
                    pass
            
            conn.commit()
            print(f"  Added {new_entries} new entries")
            total_new += new_entries
            
        except Exception as e:
            print(f"  ERROR: {e}")
    
    print(f"\n=== TOTAL: Added {total_new} new entries ===")
    
    # Show article counts
    print("\n=== Articles by source ===")
    cursor.execute("SELECT source, COUNT(*) FROM articles GROUP BY source ORDER BY COUNT(*) DESC")
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]}")
    
    conn.close()
    return 0 if total_new > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
