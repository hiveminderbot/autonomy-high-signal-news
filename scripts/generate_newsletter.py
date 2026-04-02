#!/usr/bin/env python3
"""Generate newsletter from fresh RSS articles in database."""

import sqlite3
import sys
from datetime import datetime

DB_PATH = 'news.db'
OUTPUT_PATH = 'output/newsletter-2026-03-21-final.md'

# Domain/category mapping
categories = {
    'ai_research': '🤖 Artificial Intelligence',
    'ai_tools': '🤖 AI Tools',
    'dev_language': '💻 Software Development',
    'dev_community': '💻 Developer Community',
    'dev_tools': '🛠️ Developer Tools',
    'tech_news': '📰 Tech News',
    'tech_strategy': '📊 Tech Strategy',
}


def get_recent_articles(conn, hours=48):
    """Get recent articles from database."""
    cursor = conn.execute('''
        SELECT title, url, source, domain, content, published_at
        FROM articles
        ORDER BY fetched_at DESC, published_at DESC
        LIMIT 50
    ''')
    return cursor.fetchall()


def prioritize_articles(articles):
    """Prioritize articles by source quality and freshness."""
    # Source quality scores
    source_scores = {
        'Hacker News': 8,
        'Lobsters': 8,
        'Distill.pub': 10,
        'arXiv cs.AI': 10,
        'Hugging Face Blog': 8,
        'This Week in Rust': 9,
        'JavaScript Weekly': 8,
        'Google AI Blog': 9,
        'DeepMind Blog': 9,
    }

    scored = []
    for article in articles:
        title, url, source, domain, content, published_at = article
        score = source_scores.get(source, 5)
        # Boost for certain keywords
        if any(kw in title.lower() for kw in ['rust', 'ai', 'ml', 'llm', 'gpt', 'show hn']):
            score += 1
        scored.append((score, article))

    scored.sort(reverse=True)
    return [a for _, a in scored]


def format_newsletter(articles):
    """Format articles into markdown newsletter."""
    lines = [
        "# High-Signal Newsletter - March 21, 2026",
        "",
        "*10-minute morning briefing for AI practitioners, developers, and tech investors*",
        "",
        "---",
        "",
    ]

    # Group by domain
    by_domain = {}
    for article in articles[:25]:  # Top 25 articles
        title, url, source, domain, content, published_at = article
        if domain not in by_domain:
            by_domain[domain] = []
        by_domain[domain].append(article)

    # Output by category
    for domain_key, category_name in [
        ('ai_research', '🤖 Artificial Intelligence'),
        ('ai_tools', '🤖 AI Tools'),
        ('dev_language', '💻 Software Development'),
        ('dev_community', '💻 Developer Community'),
        ('dev_tools', '🛠️ Developer Tools'),
        ('tech_news', '📰 Tech News'),
    ]:
        if domain_key not in by_domain:
            continue

        lines.append(f"## {category_name}")
        lines.append("")

        for article in by_domain[domain_key][:5]:  # Top 5 per category
            title, url, source, domain, content, published_at = article

            # Determine priority indicator
            indicator = "⭐"
            if source in ['arXiv cs.AI', 'Distill.pub']:
                indicator = "🔥"
            elif 'Show HN' in title:
                indicator = "🔥"

            lines.append(f"{indicator} **{title}**")
            lines.append(f"   Source: {source} | [Read more]({url})")

            # Add snippet if available
            snippet = content[:200].replace('\n', ' ') if content else ""
            if snippet:
                lines.append(f"   > {snippet}...")
            lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} | {len(articles)} stories from {len(by_domain)} categories*")
    lines.append("")
    lines.append("**Priority indicators:** 🔥 Breaking / Very High Signal | ⭐ Important | 📰 Regular")

    return '\n'.join(lines)


def main():
    print(f"Connecting to {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)

    print("Fetching recent articles...")
    articles = get_recent_articles(conn)
    print(f"  Found {len(articles)} articles")

    if len(articles) == 0:
        print("No articles found!")
        conn.close()
        return 1

    print("Prioritizing articles...")
    prioritized = prioritize_articles(articles)

    print("Generating newsletter...")
    newsletter = format_newsletter(prioritized)

    with open(OUTPUT_PATH, 'w') as f:
        f.write(newsletter)

    print(f"\nNewsletter written to {OUTPUT_PATH}")

    # Show preview
    print("\n" + "="*60)
    print("PREVIEW:")
    print("="*60)
    print(newsletter[:2000])
    print("...")

    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
