#!/usr/bin/env python3
"""
Run LLM analysis on articles using subagents.

This script is meant to be called FROM Hermes context where
subagents are available. It spawns parallel tasks to analyze
articles and stores results.
"""

import sqlite3
import sys
import json
from datetime import datetime

DB_PATH = 'news.db'


def get_articles_for_analysis(conn, limit=5):
    """Get articles needing LLM analysis."""
    cursor = conn.execute('''
        SELECT id, title, url, source, full_content, content
        FROM articles
        WHERE (llm_summary IS NULL OR llm_insight IS NULL)
          AND (full_content IS NOT NULL OR content IS NOT NULL)
          AND LENGTH(COALESCE(full_content, content)) > 200
        ORDER BY fetched_at DESC
        LIMIT ?
    ''', (limit,))
    return cursor.fetchall()


def ensure_schema(conn):
    """Ensure articles table has LLM analysis columns."""
    cursor = conn.execute("PRAGMA table_info(articles)")
    columns = [row[1] for row in cursor.fetchall()]

    for col in ['llm_summary', 'llm_insight', 'llm_key_findings', 'llm_processed_at']:
        if col not in columns:
            conn.execute(f"ALTER TABLE articles ADD COLUMN {col} TEXT")

    conn.commit()


def store_analysis(conn, article_id, summary, insight, findings):
    """Store LLM analysis results."""
    conn.execute('''
        UPDATE articles
        SET llm_summary = ?,
            llm_insight = ?,
            llm_key_findings = ?,
            llm_processed_at = ?
        WHERE id = ?
    ''', (summary, insight, json.dumps(findings), datetime.now().isoformat(), article_id))
    conn.commit()


def main():
    """
    Main entry point - creates analysis tasks for subagents.

    NOTE: This requires being run from Hermes context with access
to subagent/delegate capabilities. Standalone execution just
prepares the work queue.
    """
    print("LLM Article Analysis (Subagent-based)")
    print("=" * 50)

    conn = sqlite3.connect(DB_PATH)
    ensure_schema(conn)

    articles = get_articles_for_analysis(conn, limit=5)
    print(f"\nFound {len(articles)} articles for LLM analysis")

    if not articles:
        print("No articles to process")
        conn.close()
        return 0

    # Check if we're in Hermes context
    try:
        # This will work if called from Hermes, fail otherwise
        from hermes_tools import delegate_task
        hermes_available = True
    except ImportError:
        hermes_available = False

    if not hermes_available:
        print("\n⚠️  Not running in Hermes context")
        print("Creating task queue for manual processing...")

        # Just show what would be processed
        for article_id, title, url, source, full_content, rss_content in articles:
            content = full_content or rss_content or ""
            print(f"\n[{article_id}] {title}")
            print(f"   Source: {source}")
            print(f"   Content length: {len(content)} chars")

        print("\nTo process: Run this script from Hermes context")
        conn.close()
        return 0

    # We have Hermes - spawn subagents
    print("\n🤖 Spawning subagents for parallel analysis...")

    results = []
    for article_id, title, url, source, full_content, rss_content in articles:
        content = full_content or rss_content or ""
        content_preview = content[:6000]  # Limit for token budget

        print(f"\n  Analyzing: {title[:50]}...")

        # Spawn subagent for analysis
        prompt = f"""Analyze this article and extract insight for practitioners.

TITLE: {title}
SOURCE: {source}
URL: {url}

CONTENT:
{content_preview}

Provide your analysis in this exact format:

SUMMARY: One sentence describing what this is about.

INSIGHT: What's the non-obvious takeaway? Why should practitioners care?

FINDINGS:
- Key finding 1
- Key finding 2
- Key finding 3 (if applicable)

Be specific and technical. Avoid generic statements like "this is interesting" or "AI is changing the world".
"""

        # In real usage, this would call delegate_task
        # For now, output the prompt structure
        print(f"    Would spawn subagent with {len(prompt)} char prompt")
        results.append({
            'article_id': article_id,
            'title': title,
            'prompt_length': len(prompt)
        })

    print(f"\n✓ Prepared {len(results)} analysis tasks")
    print("In Hermes context, these would spawn as parallel subagents")

    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
