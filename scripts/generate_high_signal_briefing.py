#!/usr/bin/env python3
"""
Generate high-signal newsletter with filtering and synthesis.

Key improvements:
1. Filters out sponsored content, "coming soon", placeholder posts
2. Requires cross-source corroboration for themes (HN + Lobsters)
3. Synthesizes insights rather than just listing headlines
4. Prioritizes tier-1 sources (distinguished engineers, top researchers)
5. Excludes low-quality content patterns
"""

import sqlite3
import re
import json
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

DB_PATH = Path(__file__).parent.parent / "news.db"
OUTPUT_PATH = Path(__file__).parent.parent / "output"

# Content patterns to exclude (low signal)
EXCLUDE_PATTERNS = [
    r'coming soon',
    r'subscribe now',
    r'subscribe to',
    r'sign up now',
    r'early access',
    r'waitlist',
    r'preview issue',
    r'first issue coming',
    r'stay tuned',
    r'launching soon',
    r'sponsored by',
    r'advertisement',
    r'promoted by',
    r'\[sponsored\]',
    r'paid post',
    r'^(read more|learn more|click here|sign up)$',
]

# Title patterns to exclude
EXCLUDE_TITLE_PATTERNS = [
    r'^issue #\d+',
    r'^weekly issue',
    r'^coming soon',
    r'^welcome to',
    r'^announcement',
]


def should_exclude(article: dict) -> tuple[bool, str]:
    """Check if article should be excluded based on content patterns."""
    title = article.get('title', '').lower()
    # Check full_content first (extracted), then content (raw)
    content = article.get('full_content') or article.get('content') or ''
    content_lower = content.lower()

    # Check title patterns
    for pattern in EXCLUDE_TITLE_PATTERNS:
        if re.search(pattern, title, re.IGNORECASE):
            return True, f"Title pattern: {pattern}"

    # Check content patterns
    for pattern in EXCLUDE_PATTERNS:
        if re.search(pattern, content_lower, re.IGNORECASE):
            return True, f"Content pattern: {pattern}"

    # Exclude very short content (likely placeholder)
    if len(content) < 500:
        return True, "Content too short (< 500 chars)"

    # Exclude if title is too generic
    generic_titles = ['hello', 'welcome', 'introduction', 'about us']
    if title.strip() in generic_titles:
        return True, "Generic title"

    return False, ""


def get_recent_articles(days: int = 3) -> list:
    """Get articles from last N days."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cutoff = (datetime.now() - timedelta(days=days)).isoformat()

    cursor.execute("""
        SELECT a.id, a.title, a.url, a.source, a.domain, a.published_at,
               a.full_content, a.content, a.llm_insight,
               s.name as source_name, s.tier, s.quality_score
        FROM articles a
        JOIN sources s ON a.source = s.name
        WHERE a.published_at > ?
          AND a.extraction_status = 'extracted'
          AND s.tier = 1
        ORDER BY s.quality_score DESC, a.published_at DESC
    """, (cutoff,))

    articles = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return articles


def filter_high_signal(articles: list) -> list:
    """Filter to high-signal articles only."""
    filtered = []

    for article in articles:
        exclude, reason = should_exclude(article)
        if exclude:
            print(f"  Excluded: {article['title'][:60]}... ({reason})")
            continue
        filtered.append(article)

    return filtered


def detect_cross_source_themes(articles: list) -> list:
    """Detect themes that appear across multiple generalist sources."""
    # Track topics mentioned in HN, Lobsters (generalist sources)
    generalist_sources = {'Hacker News', 'Lobsters'}

    # Extract key phrases from titles
    topic_mentions = defaultdict(lambda: {'sources': set(), 'articles': []})

    for article in articles:
        source = article.get('source_name', '')
        title = article.get('title', '')

        # Only count mentions from generalist sources for theme detection
        if source in generalist_sources:
            # Extract key terms (simple approach)
            key_terms = extract_key_terms(title)

            for term in key_terms:
                topic_mentions[term]['sources'].add(source)
                topic_mentions[term]['articles'].append(article)

    # Find themes mentioned in multiple generalist sources
    themes = []
    for topic, data in topic_mentions.items():
        if len(data['sources']) >= 2:  # Appears in 2+ generalist sources
            themes.append({
                'topic': topic,
                'sources': list(data['sources']),
                'articles': data['articles'][:3],  # Top 3 articles
                'mention_count': len(data['articles'])
            })

    # Sort by mention count
    themes.sort(key=lambda x: x['mention_count'], reverse=True)
    return themes[:5]  # Top 5 themes


def extract_key_terms(title: str) -> list:
    """Extract key technical terms from title."""
    # Technical terms that indicate significant news
    significant_terms = [
        'rust', 'typescript', 'python', 'javascript', 'go', 'wasm',
        'kubernetes', 'docker', 'containers', 'llm', 'gpt', 'ai',
        'machine learning', 'deep learning', 'neural', 'transformer',
        'database', 'postgresql', 'redis', 'sqlite',
        'security', 'vulnerability', 'exploit', 'breach',
        'performance', 'optimization', 'scaling',
        'open source', 'github', 'license',
        'google', 'openai', 'anthropic', 'microsoft', 'amazon',
        'funding', 'acquisition', 'ipo', 'valuation',
    ]

    title_lower = title.lower()
    found = []

    for term in significant_terms:
        if term in title_lower:
            found.append(term)

    return found


def group_by_domain(articles: list) -> dict:
    """Group articles by domain category."""
    by_domain = defaultdict(list)

    for article in articles:
        domain = article.get('domain', 'general')
        by_domain[domain].append(article)

    return dict(by_domain)


def generate_synthesis(articles: list) -> str:
    """Generate synthesis paragraph from articles."""
    if not articles:
        return ""

    # Count by source type
    source_counts = defaultdict(int)
    for a in articles:
        source_counts[a.get('source_name', 'Unknown')] += 1

    # Get top themes
    themes = detect_cross_source_themes(articles)

    lines = []

    # Cross-source themes
    if themes:
        lines.append("### 🔥 Cross-Source Themes")
        lines.append("")
        for theme in themes[:3]:
            lines.append(f"**{theme['topic'].title()}** — mentioned across {', '.join(theme['sources'])}")
            for art in theme['articles'][:2]:
                lines.append(f"  - [{art['title'][:70]}]({art['url']})")
            lines.append("")

    return '\n'.join(lines)


def generate_newsletter(articles: list) -> str:
    """Generate the full newsletter."""
    today = datetime.now().strftime('%Y-%m-%d')

    lines = [
        f"# High-Signal Briefing — {today}",
        "",
        f"*{len(articles)} high-signal stories from the past week*",
        "",
        "**Tier-1 Sources Only**: Distinguished engineers (Karpathy, Raschka, Huyen, Willison), top researchers (Weng, Lambert), distinguished engineers (Fowler, Luu, Ronacher), and high-signal publications (Distill, arXiv, Papers with Code)",
        "",
        "---",
        "",
    ]

    # Cross-source synthesis first
    synthesis = generate_synthesis(articles)
    if synthesis:
        lines.append(synthesis)
        lines.append("---")
        lines.append("")

    # Group by domain
    by_domain = group_by_domain(articles)

    # Priority order
    priority = [
        'ai_research',
        'ai_labs',
        'software',
        'research',
        'investment',
        'community',
    ]

    for domain in priority:
        if domain not in by_domain:
            continue

        domain_articles = by_domain[domain]
        if not domain_articles:
            continue

        # Domain emoji mapping
        emojis = {
            'ai_research': '🧠',
            'ai_labs': '🤖',
            'software': '💻',
            'research': '📄',
            'investment': '💰',
            'community': '👥',
        }

        emoji = emojis.get(domain, '📰')
        lines.append(f"## {emoji} {domain.replace('_', ' ').title()}")
        lines.append("")

        for art in domain_articles[:5]:  # Top 5 per domain
            title = art['title']
            url = art['url']
            source = art.get('source_name', 'Unknown')

            lines.append(f"**{title}** — *{source}*")

            # Add LLM insight if available
            insight = art.get('llm_insight')
            if insight:
                lines.append(f"> {insight[:150]}...")

            lines.append(f"[Read more]({url})")
            lines.append("")

    # Footer
    lines.append("---")
    lines.append("")
    lines.append(f"*Generated: {datetime.now().isoformat()}*")
    lines.append("*Sources: Tier-1 only (distinguished engineers, top researchers, high-signal publications)*")

    return '\n'.join(lines)


def main():
    print("Generating high-signal briefing...")
    print()

    # Get recent articles
    print("Fetching articles from last 7 days...")
    articles = get_recent_articles(days=7)
    print(f"Found: {len(articles)} articles")
    print()

    # Filter
    print("Filtering low-signal content...")
    filtered = filter_high_signal(articles)
    print(f"After filtering: {len(filtered)} articles")
    print()

    # Generate newsletter
    newsletter = generate_newsletter(filtered)

    # Write output
    OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
    output_file = OUTPUT_PATH / f"briefing-high-signal-{datetime.now().strftime('%Y-%m-%d')}.md"

    with open(output_file, 'w') as f:
        f.write(newsletter)

    print(f"Generated: {output_file}")
    print(f"Total articles included: {len(filtered)}")


if __name__ == '__main__':
    main()
