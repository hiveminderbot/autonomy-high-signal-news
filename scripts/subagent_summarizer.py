#!/usr/bin/env python3
"""
Subagent-based content summarizer.

Uses delegate_task to spawn subagents that extract insight
from articles. The subagents use the LLM (me) for analysis.
"""

import sqlite3
import sys
import json
from datetime import datetime

DB_PATH = 'news.db'


def get_articles_for_summarization(conn, limit=10):
    """Get articles that need LLM summarization."""
    cursor = conn.execute('''
        SELECT id, title, url, source, full_content, content
        FROM articles
        WHERE (llm_summary IS NULL OR llm_insight IS NULL)
          AND (full_content IS NOT NULL OR content IS NOT NULL)
          AND LENGTH(COALESCE(full_content, content)) > 200
        ORDER BY
            CASE source
                WHEN 'Distill.pub' THEN 1
                WHEN 'Hugging Face Blog' THEN 2
                WHEN 'Hacker News' THEN 3
                WHEN 'Lobsters' THEN 4
                ELSE 5
            END
        LIMIT ?
    ''', (limit,))
    return cursor.fetchall()


def ensure_schema(conn):
    """Add LLM summary columns."""
    cursor = conn.execute("PRAGMA table_info(articles)")
    columns = [row[1] for row in cursor.fetchall()]

    if 'llm_summary' not in columns:
        conn.execute("ALTER TABLE articles ADD COLUMN llm_summary TEXT")
    if 'llm_insight' not in columns:
        conn.execute("ALTER TABLE articles ADD COLUMN llm_insight TEXT")
    if 'llm_key_findings' not in columns:
        conn.execute("ALTER TABLE articles ADD COLUMN llm_key_findings TEXT")
    if 'llm_processed_at' not in columns:
        conn.execute("ALTER TABLE articles ADD COLUMN llm_processed_at TIMESTAMP")

    conn.commit()


def create_subagent_task(article_id, title, content, source):
    """Create a subagent task for article analysis."""

    # Truncate content for reasonable processing
    content_preview = content[:8000] if content else ""

    task = {
        "task_type": "article_analysis",
        "article_id": article_id,
        "title": title,
        "source": source,
        "content_preview": content_preview,
        "instructions": """
Analyze this article and extract:

1. ONE SENTENCE SUMMARY - What is this about?
2. KEY INSIGHT - What's the non-obvious takeaway for practitioners?
3. WHY IT MATTERS - How does this affect the industry/field?
4. KEY FINDINGS - 2-3 bullet points of specific findings/claims

Be concise. Focus on practitioner value, not generic descriptions.
        """
    }

    return task


def store_llm_analysis(conn, article_id, analysis):
    """Store LLM analysis results."""
    conn.execute('''
        UPDATE articles
        SET llm_summary = ?,
            llm_insight = ?,
            llm_key_findings = ?,
            llm_processed_at = ?
        WHERE id = ?
    ''', (
        analysis.get('summary', ''),
        analysis.get('insight', ''),
        json.dumps(analysis.get('findings', [])),
        datetime.now().isoformat(),
        article_id
    ))
    conn.commit()


def main():
    print("Subagent-based Article Summarizer")
    print("=" * 50)

    conn = sqlite3.connect(DB_PATH)
    ensure_schema(conn)

    articles = get_articles_for_summarization(conn)
    print(f"\nFound {len(articles)} articles needing LLM analysis")

    if not articles:
        print("No articles to process")
        conn.close()
        return 0

    # Create task payloads
    tasks = []
    for article_id, title, url, source, full_content, rss_content in articles:
        content = full_content if full_content and len(full_content) > 500 else rss_content
        task = create_subagent_task(article_id, title, content, source)
        tasks.append((article_id, title, task))

    # For now, we'll create a batch file that can be processed by delegate_task
    # In practice, this would integrate with the actual subagent system

    batch_file = 'state/subagent_batch.json'
    with open(batch_file, 'w') as f:
        json.dump({
            'created_at': datetime.now().isoformat(),
            'task_count': len(tasks),
            'tasks': [t[2] for t in tasks]
        }, f, indent=2)

    print(f"\nCreated batch file: {batch_file}")
    print(f"Tasks: {len(tasks)}")

    print("\nArticle queue:")
    for article_id, title, _ in tasks:
        print(f"  [{article_id}] {title[:50]}...")

    print(f"\nNext: Process these with delegate_task")
    print("Or run the analysis directly if called from Hermes context")

    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
