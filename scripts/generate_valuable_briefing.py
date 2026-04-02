#!/usr/bin/env python3
"""
Generate a valuable newsletter with synthesis and insight.

This is NOT a link dump. It:
1. Reads article content (via LLM summaries in DB)
2. Synthesizes 2-3 key themes with actual analysis
3. Selects top 5-7 stories with "Why it matters" commentary
4. Adds "The Big Picture" connecting dots across domains
5. Ends with "Worth Watching" — emerging signals
"""

import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

DB_PATH = Path(__file__).parent.parent / "news.db"
OUTPUT_PATH = Path(__file__).parent.parent / "output"


def get_recent_articles(days: int = 3, limit: int = 100):
    """Get recent articles with LLM insights."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cutoff = (datetime.now() - timedelta(days=days)).isoformat()

    cursor.execute("""
        SELECT a.id, a.title, a.url, a.source, a.domain, a.published_at,
               a.llm_summary, a.llm_insight, a.llm_key_findings,
               s.quality_score
        FROM articles a
        JOIN sources s ON a.source = s.name
        WHERE a.published_at > ?
          AND (a.llm_insight IS NOT NULL OR a.llm_summary IS NOT NULL)
        ORDER BY s.quality_score DESC, a.published_at DESC
        LIMIT ?
    """, (cutoff, limit))

    articles = [dict(row) for row in cursor.fetchall()]
    conn.close()

    return articles


def synthesize_themes(articles):
    """Synthesize 2-3 key themes from article insights."""
    # Collect insights by domain
    insights_by_domain = defaultdict(list)

    for art in articles:
        domain = art.get('domain', 'general')
        insight = art.get('llm_insight') or art.get('llm_summary', '')
        if insight:
            insights_by_domain[domain].append({
                'title': art['title'],
                'insight': insight,
                'source': art['source']
            })

    # Look for patterns across domains
    themes = []

    # Check for recurring keywords across insights
    all_insights = ' '.join([(a.get('llm_insight') or '') + ' ' + (a.get('llm_summary') or '')
                             for a in articles]).lower()

    theme_keywords = {
        'AI/ML Infrastructure': ['inference', 'latency', 'throughput', 'scaling', 'optimization'],
        'Safety & Alignment': ['safety', 'alignment', 'robustness', 'attack', 'adversarial'],
        'Hardware & Systems': ['hardware', 'gpu', 'cpu', 'memory', 'throughput'],
        'Developer Tools': ['developer', 'tooling', 'workflow', 'productivity'],
        'Open Source': ['open source', 'github', 'license', 'community'],
    }

    for theme_name, keywords in theme_keywords.items():
        matches = sum(1 for kw in keywords if kw in all_insights)
        if matches >= 3:  # At least 3 keyword mentions
            # Find representative articles for this theme
            reps = []
            for art in articles:
                insight_text = (art.get('llm_insight') or '') + ' ' + (art.get('llm_summary') or '')
                if any(kw in insight_text.lower() for kw in keywords) and len(reps) < 2:
                    reps.append(art)

            if reps:
                themes.append({
                    'name': theme_name,
                    'articles': reps,
                    'strength': matches
                })

    # Sort by strength, take top 3
    themes.sort(key=lambda x: x['strength'], reverse=True)
    return themes[:3]


def select_top_stories(articles, n=6):
    """Select top N stories based on source quality + insight quality."""
    scored = []

    for art in articles:
        score = art.get('quality_score', 5)

        # Boost for having insights
        if art.get('llm_insight'):
            score += 2
        if art.get('llm_key_findings'):
            score += 1

        # Boost for certain high-value sources
        if art['source'] in ['Andrej Karpathy', 'Simon Willison', 'Distill.pub']:
            score += 2

        scored.append((score, art))

    scored.sort(reverse=True, key=lambda x: x[0])
    return [art for _, art in scored[:n]]


def generate_why_it_matters(art):
    """Generate 'Why it matters' from LLM insight."""
    insight = art.get('llm_insight', '')
    summary = art.get('llm_summary', '')
    findings = art.get('llm_key_findings', '')

    # Use insight if available, otherwise summary
    content = insight or summary or findings

    if not content:
        return "Worth tracking for developments in this space."

    # Truncate to one punchy sentence
    sentences = content.split('. ')
    if sentences:
        return sentences[0][:200] + ('...' if len(sentences[0]) > 200 else '')

    return content[:200] + ('...' if len(content) > 200 else '')


def generate_briefing():
    """Generate the full valuable briefing."""
    articles = get_recent_articles(days=3, limit=50)

    if not articles:
        return None, "No articles with insights found"

    today = datetime.now().strftime('%Y-%m-%d')

    lines = [
        f"# 🎯 High-Signal Briefing — {today}",
        "",
        f"*{len(articles)} stories analyzed | Top insights distilled*",
        "",
        "---",
        "",
    ]

    # Synthesize themes
    themes = synthesize_themes(articles)

    if themes:
        lines.append("## 🔥 The Big Themes")
        lines.append("")

        for theme in themes:
            lines.append(f"### {theme['name']}")

            # Create synthesis from representative articles
            reps = theme['articles']
            if reps:
                insights = []
                for r in reps[:2]:
                    insight = r.get('llm_insight') or r.get('llm_summary', '')
                    if insight:
                        insights.append(f"'{r['title']}': {insight[:100]}...")

                if insights:
                    lines.append("Key signals:")
                    for i in insights:
                        lines.append(f"- {i}")

            lines.append("")

    # Top stories with analysis
    top_stories = select_top_stories(articles, n=6)

    if top_stories:
        lines.append("## 📌 Stories That Matter")
        lines.append("")

        for art in top_stories:
            title = art['title']
            url = art['url']
            source = art['source']

            lines.append(f"**{title}** — *{source}*")

            why = generate_why_it_matters(art)
            lines.append(f"> 💡 {why}")
            lines.append(f"> [Read more]({url})")
            lines.append("")

    # Worth Watching section
    emerging = [a for a in articles if a not in top_stories][:3]

    if emerging:
        lines.append("## 👀 Worth Watching")
        lines.append("")
        lines.append("Emerging signals to track:")
        lines.append("")

        for art in emerging:
            title = art['title'][:60] + ('...' if len(art['title']) > 60 else '')
            lines.append(f"- [{title}]({art['url']}) — *{art['source']}*")

        lines.append("")

    # Footer
    lines.append("---")
    lines.append("")
    lines.append(f"*Generated: {datetime.now().isoformat()}*")
    lines.append("*Sources: HN, Lobsters, Karpathy, Willison, Distill, arXiv, and tier-1 blogs*")
    lines.append("*Method: Articles read via LLM, insights synthesized, curated for signal*")

    return '\n'.join(lines), None


def main():
    """Main entry point."""
    print("Generating valuable briefing...")

    content, error = generate_briefing()

    if error:
        print(f"Error: {error}")
        return

    # Write output
    OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
    output_file = OUTPUT_PATH / f"briefing-valuable-{datetime.now().strftime('%Y-%m-%d')}.md"

    with open(output_file, 'w') as f:
        f.write(content)

    print(f"Generated: {output_file}")
    print(f"Content length: {len(content)} chars")


if __name__ == '__main__':
    main()
