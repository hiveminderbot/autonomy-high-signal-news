#!/usr/bin/env python3
"""
Migrate sources from sources table to feed_sources table with proper format info.

This bridges the gap between the sources loaded via load_sources.py and the
feed_sources table expected by feed_fetcher.py.
"""

import sqlite3
import json
from pathlib import Path


def migrate_sources(db_path: Path):
    """Migrate sources from sources table to feed_sources table."""
    
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get all sources from the sources table
        cursor.execute("SELECT * FROM sources WHERE status = 'active'")
        sources = cursor.fetchall()
        
        print(f"Found {len(sources)} active sources to migrate")
        
        migrated = 0
        skipped = 0
        
        for source in sources:
            # Generate ID from name
            source_id = source['name'].lower().replace(' ', '-').replace('.', '-').replace('/', '-')
            
            # Check if already in feed_sources
            cursor.execute("SELECT id FROM feed_sources WHERE id = ?", (source_id,))
            if cursor.fetchone():
                print(f"  SKIP: {source['name']} (already in feed_sources)")
                skipped += 1
                continue
            
            # Parse special_handling to get type info
            special_handling = {}
            try:
                special_handling = json.loads(source['special_handling'] or '{}')
            except json.JSONDecodeError:
                pass
            
            # Determine format based on URL and special_handling
            rss_url = source['rss_url'] or ''
            source_type = special_handling.get('type', 'rss').upper()
            
            # Map type to format
            if source_type == 'NEWSLETTER':
                format_type = 'RSS'  # Newsletters have RSS feeds
            elif source_type == 'BLOG':
                format_type = 'RSS'  # Blogs have RSS feeds
            elif source_type == 'SCRAPER':
                format_type = 'SCRAPER'
            elif 'github.com/trending' in rss_url:
                format_type = 'GITHUB_TRENDING'
            elif 'github.com' in rss_url and '/blob/' not in rss_url:
                format_type = 'GITHUB_REPO'
            elif rss_url.endswith('.xml') or rss_url.endswith('.rss') or 'rss' in rss_url or 'feed' in rss_url:
                format_type = 'RSS'
            else:
                format_type = 'RSS'  # Default assumption
            
            # Skip sources without valid RSS URLs
            if not rss_url or rss_url.startswith('http'):
                pass  # Valid URL
            else:
                print(f"  SKIP: {source['name']} (invalid URL: {rss_url[:30]}...)")
                skipped += 1
                continue
            
            # Insert into feed_sources
            try:
                cursor.execute("""
                    INSERT INTO feed_sources 
                    (id, name, url, format, category, domain, signal_quality, active, 
                     fetch_interval_minutes, error_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    source_id,
                    source['name'],
                    rss_url,
                    format_type,
                    source['category'] if source['category'] else 'General',
                    source['domain'] if source['domain'] else 'unknown',
                    'High' if (source['quality_score'] or 5) >= 8 else 'Medium',
                    1,
                    60,  # Default fetch interval
                    0
                ))
                conn.commit()
                print(f"  MIGRATED: {source['name']} ({format_type})")
                migrated += 1
            except sqlite3.Error as e:
                print(f"  ERROR: {source['name']} - {e}")
                skipped += 1
        
        return migrated, skipped


def main():
    db_path = Path(__file__).parent.parent / 'news.db'
    
    print(f"Database: {db_path}")
    print("=" * 50)
    
    migrated, skipped = migrate_sources(db_path)
    
    print("=" * 50)
    print(f"Migration complete: {migrated} migrated, {skipped} skipped")
    
    # Verify
    with sqlite3.connect(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM feed_sources")
        count = cursor.fetchone()[0]
        print(f"Total feed_sources: {count}")


if __name__ == '__main__':
    main()
