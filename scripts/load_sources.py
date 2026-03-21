#!/usr/bin/env python3
"""Load bootstrapped sources into news.db."""

import json
import sqlite3
import sys
from pathlib import Path
from datetime import datetime

DB_PATH = Path(__file__).parent.parent / "news.db"
SOURCES_PATH = Path(__file__).parent.parent / "sources" / "sources-v2-bootstrapped.json"


def load_sources():
    """Load sources from JSON file."""
    with open(SOURCES_PATH) as f:
        data = json.load(f)
    
    sources = []
    
    # RSS feeds
    for feed in data.get("rss_feeds", []):
        sources.append({
            "name": feed["name"],
            "url": feed["url"],
            "type": "rss",
            "category": feed["category"],
            "frequency": feed["frequency"],
            "quality_score": feed["quality_score"],
            "notes": feed.get("notes", ""),
            "enabled": True,
            "special_handling": json.dumps({})
        })
    
    # Newsletters
    for nl in data.get("newsletters", []):
        sources.append({
            "name": nl["name"],
            "url": nl.get("rss_url", nl["url"]),
            "type": "newsletter",
            "category": nl["category"],
            "frequency": nl["frequency"],
            "quality_score": nl["quality_score"],
            "notes": nl.get("notes", ""),
            "enabled": True,
            "special_handling": json.dumps({})
        })
    
    # Special handling sources
    for sh in data.get("special_handling", []):
        sources.append({
            "name": sh["name"],
            "url": sh.get("rss_url", sh["url"]),
            "type": sh["type"],
            "category": sh["category"],
            "frequency": sh["frequency"],
            "quality_score": sh["quality_score"],
            "notes": sh.get("notes", ""),
            "enabled": sh.get("enabled", True),
            "special_handling": json.dumps({
                "min_fetch_interval": sh.get("min_fetch_interval", 0),
                "rate_limited": sh.get("min_fetch_interval", 0) > 0
            })
        })
    
    return sources


def ensure_table(conn):
    """Ensure sources table exists with proper schema."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sources (
            id INTEGER PRIMARY KEY,
            name TEXT,
            rss_url TEXT UNIQUE,
            domain TEXT,
            tier INTEGER,
            last_fetch TEXT,
            status TEXT DEFAULT 'active',
            category TEXT, 
            frequency TEXT DEFAULT 'daily', 
            quality_score INTEGER DEFAULT 5, 
            special_handling TEXT DEFAULT '{}'
        )
    """)
    conn.commit()


def insert_sources(conn, sources):
    """Insert or update sources in database."""
    cursor = conn.cursor()
    
    inserted = 0
    updated = 0
    
    for source in sources:
        # Map category to domain for compatibility
        domain = source.get("category", source.get("domain", "general"))
        status = "active" if source.get("enabled", True) else "disabled"
        tier = 1 if source["quality_score"] >= 9 else 2
        
        try:
            cursor.execute("""
                INSERT INTO sources 
                (name, rss_url, domain, tier, category, frequency, quality_score, status, special_handling)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                source["name"], source["url"], domain, tier,
                source["category"], source["frequency"], 
                source["quality_score"], status, source["special_handling"]
            ))
            inserted += 1
        except sqlite3.IntegrityError:
            # Update existing
            cursor.execute("""
                UPDATE sources SET
                    rss_url = ?,
                    domain = ?,
                    tier = ?,
                    category = ?,
                    frequency = ?,
                    quality_score = ?,
                    status = ?,
                    special_handling = ?
                WHERE name = ?
            """, (
                source["url"], domain, tier,
                source["category"], source["frequency"],
                source["quality_score"], status, source["special_handling"], source["name"]
            ))
            updated += 1
    
    conn.commit()
    return inserted, updated


def main():
    """Main entry point."""
    print(f"Loading sources from {SOURCES_PATH}")
    print(f"Database: {DB_PATH}")
    
    if not SOURCES_PATH.exists():
        print(f"ERROR: Sources file not found: {SOURCES_PATH}")
        sys.exit(1)
    
    sources = load_sources()
    print(f"Found {len(sources)} sources in catalog")
    
    conn = sqlite3.connect(DB_PATH)
    try:
        ensure_table(conn)
        inserted, updated = insert_sources(conn, sources)
        
        print(f"\nResults:")
        print(f"  Inserted: {inserted}")
        print(f"  Updated: {updated}")
        print(f"  Total: {inserted + updated}")
        
        # Show summary by category
        print("\nSources by category:")
        cursor = conn.execute("""
            SELECT category, COUNT(*), SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END)
            FROM sources
            GROUP BY category
            ORDER BY COUNT(*) DESC
        """)
        for row in cursor.fetchall():
            print(f"  {row[0]}: {row[2]}/{row[1]} enabled")
        
        # Show high-quality sources
        print("\nHigh-quality sources (score >= 9):")
        cursor = conn.execute("""
            SELECT name, category, quality_score
            FROM sources
            WHERE quality_score >= 9 AND status = 'active'
            ORDER BY quality_score DESC
        """)
        for row in cursor.fetchall():
            print(f"  [{row[2]}] {row[0]} ({row[1]})")
        
    finally:
        conn.close()
    
    print("\nDone. Run fetch script to test sources.")


if __name__ == "__main__":
    main()
