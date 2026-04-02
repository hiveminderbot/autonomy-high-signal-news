#!/usr/bin/env python3
"""
Generate newsletter with synthesis AND sources.

Sweet spot format:
1. The Big Themes - Synthesis with links to dive deeper
2. Deep Dives - 5-7 stories with insight AND direct links
3. Quick Hits - Other notable stories with links
4. Sources - All links grouped by domain for exploration
"""

import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

DB_PATH = Path(__file__).parent.parent / "news.db"
OUTPUT_PATH = Path(__file__).parent.parent / "output"


def get_articles_with_insights(days: int = 3):
    """Get articles that have been analyzed."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cutoff = (datetime.now() - timedelta(days=days)).isoformat()

    cursor.execute("""
        SELECT a.id, a.title, a.url, a.source, a.domain, a.published_at,
               a.llm_summary, a.llm_insight, a.llm_key_findings,
               s.quality_score, s.name as source_name
        FROM articles a
        JOIN sources s ON a.source = s.name
        WHERE a.published_at > ?
          AND (a.llm_insight IS NOT NULL OR a.llm_summary IS NOT NULL)
        ORDER BY s.quality_score DESC, a.published_at DESC
    """, (cutoff,))

    articles = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return articles


def get_insight_text(art):
    """Get best available insight text."""
    return art.get('llm_insight') or art.get('llm_summary') or art.get('llm_key_findings') or ''


def synthesize_themes_with_sources(articles):
    """Synthesize themes with representative sources."""
    # Theme detection based on content analysis
    theme_keywords = {
        'AI Infrastructure & Efficiency': {
            'keywords': ['inference', 'latency', 'throughput', 'scaling', 'optimization', 'efficiency', 'performance'],
            'description': 'Production AI systems getting faster, leaner, and more cost-effective'
        },
        'Safety & Robustness': {
            'keywords': ['safety', 'alignment', 'robustness', 'attack', 'adversarial', 'vulnerability', 'reliability'],
            'description': 'Building AI that fails gracefully and resists manipulation'
        },
        'Interpretability & Understanding': {
            'keywords': ['interpretability', 'mechanistic', 'circuits', 'neurons', 'visualizing', 'understanding'],
            'description': 'Opening the black box to understand how models actually work'
        },
        'Systems & Hardware': {
            'keywords': ['hardware', 'gpu', 'memory', 'distributed', 'systems', 'infrastructure'],
            'description': 'The plumbing that makes modern AI possible'
        },
    }

    themes = []

    for theme_name, theme_info in theme_keywords.items():
        keywords = theme_info['keywords']

        # Find articles matching this theme
        matches = []
        for art in articles:
            insight = get_insight_text(art).lower()
            title = art['title'].lower()
            combined = insight + ' ' + title

            if any(kw in combined for kw in keywords):
                matches.append(art)

        if len(matches) >= 2:  # Need at least 2 to be a theme
            # Get top 2 by source quality
            matches.sort(key=lambda x: x.get('quality_score', 5), reverse=True)
            reps = matches[:2]

            themes.append({
                'name': theme_name,
                'description': theme_info['description'],
                'articles': reps,
                'count': len(matches)
            })

    # Sort by article count
    themes.sort(key=lambda x: x['count'], reverse=True)
    return themes[:3]  # Top 3 themes


def select_deep_dives(articles, n=5):
    """Select top stories for deep dive analysis."""
    scored = []

    for art in articles:
        score = art.get('quality_score', 5)

        # Boost for having insights
        if art.get('llm_insight'):
            score += 3
        if art.get('llm_key_findings'):
            score += 1

        # Boost for certain high-value sources
        premium_sources = ['Andrej Karpathy', 'Simon Willison', 'Distill.pub',
                          'Sebastian Raschka', 'Lilian Weng', 'Chip Huyen']
        if art['source'] in premium_sources:
            score += 2

        scored.append((score, art))

    scored.sort(reverse=True, key=lambda x: x[0])
    return [art for _, art in scored[:n]]


def format_insight(art, max_len=180):
    """Format the insight for readability."""
    insight = get_insight_text(art)

    if not insight:
        return "Worth tracking for developments in this space."

    # Take first sentence, clean up
    sentences = insight.split('. ')
    if sentences:
        text = sentences[0].strip()
        # Remove markdown formatting artifacts
        text = text.replace('**', '').replace('*', '')
        if len(text) > max_len:
            text = text[:max_len-3] + '...'
        return text

    return insight[:max_len] + ('...' if len(insight) > max_len else '')


def generate_briefing():
    """Generate the briefing with synthesis AND sources."""
    articles = get_articles_with_insights(days=3)

    if not articles:
        return None, "No analyzed articles found"

    today = datetime.now().strftime('%Y-%m-%d')

    lines = [
        f"# 🎯 High-Signal Briefing — {today}",
        "",
        f"*{len(articles)} stories analyzed | Top insights with sources*",
        "",
        "---",
        "",
    ]

    # === THE BIG THEMES (with sources) ===
    themes = synthesize_themes_with_sources(articles)

    if themes:
        lines.append("## 🔥 The Big Themes")
        lines.append("")
        lines.append("*Patterns across multiple sources worth your attention:*")
        lines.append("")

        for theme in themes:
            lines.append(f"### {theme['name']}")
            lines.append(f"_{theme['description']}_")
            lines.append("")
            lines.append(f"*{theme['count']} stories in this area — here are the best:*")
            lines.append("")

            for art in theme['articles']:
                title = art['title'][:70] + ('...' if len(art['title']) > 70 else '')
                lines.append(f"• **[{title}]({art['url']})** — *{art['source']}*")

                insight = format_insight(art, max_len=150)
                lines.append(f"  > {insight}")
                lines.append("")

        lines.append("---")
        lines.append("")

    # === DEEP DIVES (insight + source) ===
    deep_dives = select_deep_dives(articles, n=5)

    if deep_dives:
        lines.append("## 📌 Deep Dives")
        lines.append("")
        lines.append("*Most significant stories with analysis:*")
        lines.append("")

        for i, art in enumerate(deep_dives, 1):
            lines.append(f"### {i}. {art['title']}")
            lines.append(f"**Source:** [{art['source']}]({art['url']})")
            lines.append("")

            insight = format_insight(art, max_len=200)
            lines.append(f"💡 **Why it matters:** {insight}")
            lines.append("")
            lines.append(f"→ [Read the full story]({art['url']})")
            lines.append("")

    # === QUICK HITS (other notable stories) ===
    other_notable = [a for a in articles if a not in deep_dives][:8]

    if other_notable:
        lines.append("---")
        lines.append("")
        lines.append("## ⚡ Quick Hits")
        lines.append("")
        lines.append("*Other notable stories worth a click:*")
        lines.append("")

        # Group by domain for organization
        by_domain = defaultdict(list)
        for art in other_notable:
            domain = art.get('domain', 'general').replace('_', ' ').title()
            by_domain[domain].append(art)

        for domain, arts in sorted(by_domain.items()):
            lines.append(f"**{domain}:**")
            for art in arts:
                title = art['title'][:55] + ('...' if len(art['title']) > 55 else '')
                lines.append(f"• [{title}]({art['url']}) — *{art['source']}*")
            lines.append("")

    # === SOURCES (organized for exploration) ===
    lines.append("---")
    lines.append("")
    lines.append("## 📚 All Sources")
    lines.append("")
    lines.append("*Explore by topic area:*")
    lines.append("")

    by_domain_all = defaultdict(list)
    for art in articles:
        domain = art.get('domain', 'general').replace('_', ' ').title()
        by_domain_all[domain].append(art)

    for domain, arts in sorted(by_domain_all.items()):
        if len(arts) > 0:
            lines.append(f"**{domain}** ({len(arts)} stories):")
            for art in arts[:5]:  # Top 5 per domain
                title = art['title'][:50] + ('...' if len(art['title']) > 50 else '')
                lines.append(f"• [{title}]({art['url']})")
            if len(arts) > 5:
                lines.append(f"• _...and {len(arts) - 5} more_")
            lines.append("")

    # Footer
    lines.append("---")
    lines.append("")
    lines.append(f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}*")
    lines.append("*Method: LLM-analyzed articles, themes synthesized, sources linked*")
    lines.append("*Want more on any theme? Click through to the sources above.*")

    return '\n'.join(lines), None


def main():
    print("Generating sweet-spot briefing...")

    content, error = generate_briefing()

    if error:
        print(f"Error: {error}")
        return

    OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
    output_file = OUTPUT_PATH / f"briefing-{datetime.now().strftime('%Y-%m-%d')}.md"

    with open(output_file, 'w') as f:
        f.write(content)

    print(f"Generated: {output_file}")
    print(f"Length: {len(content)} chars")

    # Preview structure
    print("\nStructure:")
    sections = content.split('## ')
    for section in sections[1:]:  # Skip title
        title = section.split('\n')[0].strip()
        print(f"  • {title}")


if __name__ == '__main__':
    main()
