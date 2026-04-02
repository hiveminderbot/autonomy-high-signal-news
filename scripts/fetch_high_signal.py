#!/usr/bin/env python3
"""
Fetch high-signal sources directly using requests + feedparser.
Fetches from tier-1 sources only.
"""

import requests
import feedparser
import sqlite3
import json
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "news.db"

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def save_article(conn, title, url, source, domain, published_at, content=None):
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT OR IGNORE INTO articles
            (title, url, source, domain, published_at, fetched_at, content, extraction_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            title, url, source, domain, published_at, datetime.now().isoformat(),
            content, 'pending' if not content else 'extracted'
        ))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        print(f"Error saving: {e}")
        return False

def fetch_hn_top():
    """Fetch top stories from Hacker News."""
    print("Fetching Hacker News top stories...")
    try:
        # Get top story IDs
        r = requests.get("https://hacker-news.firebaseio.com/v0/topstories.json", timeout=30)
        top_ids = r.json()[:30]  # Top 30

        conn = get_db()
        fetched = 0

        for story_id in top_ids:
            try:
                r = requests.get(f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json", timeout=10)
                story = r.json()

                if story.get('type') != 'story':
                    continue

                title = story.get('title', '')
                url = story.get('url') or f"https://news.ycombinator.com/item?id={story_id}"
                published = datetime.fromtimestamp(story.get('time', 0)).isoformat()

                if save_article(conn, title, url, "Hacker News", "community", published):
                    fetched += 1

            except Exception as e:
                continue

        conn.close()
        print(f"  -> {fetched} new stories")
        return fetched
    except Exception as e:
        print(f"  -> ERROR: {e}")
        return 0

def fetch_lobsters():
    """Fetch from Lobsters."""
    print("Fetching Lobsters...")
    try:
        r = requests.get("https://lobste.rs/rss", timeout=30)
        feed = feedparser.parse(r.content)

        conn = get_db()
        fetched = 0

        for entry in feed.entries[:30]:
            title = entry.get('title', '')
            url = entry.get('link', '')
            published = entry.get('published', datetime.now().isoformat())

            if save_article(conn, title, url, "Lobsters", "community", published):
                fetched += 1

        conn.close()
        print(f"  -> {fetched} new stories")
        return fetched
    except Exception as e:
        print(f"  -> ERROR: {e}")
        return 0

def fetch_rss_feed(name, url, domain, limit=10):
    """Fetch a generic RSS feed."""
    print(f"Fetching {name}...")
    try:
        r = requests.get(url, timeout=30, headers={'User-Agent': 'HighSignalBot/1.0'})
        feed = feedparser.parse(r.content)

        conn = get_db()
        fetched = 0

        for entry in feed.entries[:limit]:
            title = entry.get('title', '')
            url = entry.get('link', '')
            published = entry.get('published', entry.get('updated', datetime.now().isoformat()))

            if save_article(conn, title, url, name, domain, published):
                fetched += 1

        conn.close()
        print(f"  -> {fetched} new stories")
        return fetched
    except Exception as e:
        print(f"  -> ERROR: {e}")
        return 0

def main():
    print(f"[{datetime.now().isoformat()}] Fetching high-signal sources...")
    print()

    total = 0

    # Community aggregators
    total += fetch_hn_top()
    total += fetch_lobsters()

    # High-signal individual blogs
    feeds = [
        ("Simon Willison", "https://simonwillison.net/atom/everything/", "ai_research"),
        ("Andrej Karpathy", "https://karpathy.bearblog.dev/atom/", "ai_research"),
        ("Dan Luu", "https://danluu.com/atom.xml", "software"),
        ("Lilian Weng", "https://lilianweng.github.io/index.xml", "ai_research"),
        ("Distill.pub", "https://distill.pub/rss.xml", "research"),
        ("arXiv cs.AI", "https://rss.arxiv.org/rss/cs.AI", "ai_research"),
        ("arXiv cs.LG", "https://rss.arxiv.org/rss/cs.LG", "ai_research"),
    ]

    for name, url, domain in feeds:
        total += fetch_rss_feed(name, url, domain, limit=5)

    print()
    print(f"Total new articles: {total}")

if __name__ == '__main__':
    main()
