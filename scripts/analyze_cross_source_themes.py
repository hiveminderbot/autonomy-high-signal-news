#!/usr/bin/env python3
"""
Cross-source theme analysis.

Only analyzes generalist feeds (HN, Lobsters) for trends.
Domain-specific feeds (TWiR, JS Weekly) are used for content
but NOT for "trend detection" (to avoid tautologies like
"Rust blog has many Rust stories = Rust momentum").
"""

import sqlite3
import sys
import re
from collections import defaultdict
from datetime import datetime, timedelta

DB_PATH = 'news.db'

# Generalist feeds - these are the ONLY sources used for trend detection
GENERALIST_SOURCES = {'Hacker News', 'Lobsters'}

# Domain-specific feeds - content only, not trend detection
DOMAIN_SOURCES = {
    'This Week in Rust': 'rust',
    'JavaScript Weekly': 'javascript',
    'Hugging Face Blog': 'ai',
    'Distill.pub': 'research'
}


def get_recent_generalist_articles(conn, days=7):
    """Get articles from generalist feeds only."""
    placeholders = ','.join(f"'{s}'" for s in GENERALIST_SOURCES)

    cursor = conn.execute(f'''
        SELECT title, url, source, full_content, fetched_at
        FROM articles
        WHERE source IN ({placeholders})
          AND fetched_at >= datetime('now', '-{days} days')
        ORDER BY fetched_at DESC
    ''')
    return cursor.fetchall()


def extract_themes_from_text(title, content):
    """Extract technology themes from text."""
    text = f"{title} {content or ''}".lower()

    themes = {}

    # Define theme patterns with keywords
    theme_patterns = {
        'llms_ai': {
            'keywords': ['llm', 'gpt', 'claude', 'gemini', 'ai model', 'foundation model',
                        'transformer', 'attention mechanism', 'large language'],
            'weight': 1.0
        },
        'ai_safety': {
            'keywords': ['ai safety', 'alignment', 'interpretability', 'mechanistic',
                        'adversarial', 'jailbreak', 'prompt injection'],
            'weight': 1.2
        },
        'training_inference': {
            'keywords': ['training', 'fine-tuning', 'finetune', 'rlhf', 'inference',
                        'serving', 'latency', 'throughput', 'gpu cluster', 'distributed'],
            'weight': 1.0
        },
        'robotics': {
            'keywords': ['robotics', 'robot', 'embodied', 'manipulation', 'grasping',
                        'vla', 'vision language action', 'ros'],
            'weight': 1.3  # Emerging area
        },
        'rust_systems': {
            'keywords': ['rust', 'memory safety', 'borrow checker', 'cargo', 'wasm',
                        'systems programming', 'zero-copy'],
            'weight': 1.0
        },
        'web_platform': {
            'keywords': ['react', 'typescript', 'javascript', 'bun', 'deno', 'node',
                        'frontend', 'webassembly', 'wasm'],
            'weight': 0.8
        },
        'databases': {
            'keywords': ['database', 'sql', 'postgres', 'sqlite', 'graph database',
                        'vector database', 'embedding store'],
            'weight': 0.9
        },
        'security': {
            'keywords': ['security', 'vulnerability', 'cve', 'exploit', 'crypto',
                        'encryption', 'zero-day', 'ransomware'],
            'weight': 1.2
        },
        'developer_tools': {
            'keywords': ['cli', 'terminal', 'editor', 'vscode', 'neovim', 'git',
                        'workflow', 'productivity', 'automation'],
            'weight': 0.7
        },
        'open_source': {
            'keywords': ['open source', 'github', 'license', 'gpl', 'mit license',
                        'contributor', 'maintainer', 'community'],
            'weight': 0.8
        }
    }

    for theme_name, config in theme_patterns.items():
        score = 0
        for keyword in config['keywords']:
            if keyword in text:
                score += 1
        if score > 0:
            themes[theme_name] = score * config['weight']

    return themes


def detect_cross_source_themes(articles):
    """Detect themes that appear across multiple generalist sources."""

    # Theme -> list of articles
    theme_articles = defaultdict(list)

    for article in articles:
        title, url, source, content, fetched_at = article
        themes = extract_themes_from_text(title, content)

        for theme, score in themes.items():
            if score > 0.5:  # Threshold
                theme_articles[theme].append({
                    'title': title,
                    'url': url,
                    'source': source,
                    'score': score,
                    'fetched_at': fetched_at
                })

    # Filter to themes with multiple sources (cross-source = more significant)
    cross_source_themes = {}
    for theme, articles_list in theme_articles.items():
        sources = set(a['source'] for a in articles_list)
        if len(sources) >= 2:  # Appears in multiple generalist sources
            cross_source_themes[theme] = {
                'article_count': len(articles_list),
                'sources': list(sources),
                'articles': articles_list[:5],  # Top 5
                'total_score': sum(a['score'] for a in articles_list)
            }

    # Sort by significance (total score)
    return dict(sorted(
        cross_source_themes.items(),
        key=lambda x: x[1]['total_score'],
        reverse=True
    ))


def analyze_sentiment(title, content):
    """Simple sentiment analysis for practitioner sentiment."""
    text = f"{title} {content or ''}".lower()

    positive = ['excited', 'awesome', 'great', 'love', 'impressive', 'breakthrough', 'milestone']
    negative = ['concerned', 'worried', 'problem', 'issue', 'broken', 'disappointed', 'frustrated']
    concerned = ['enshittification', 'consolidation', 'monopoly', 'privacy', 'surveillance']

    pos_count = sum(1 for p in positive if p in text)
    neg_count = sum(1 for n in negative if n in text)
    concern_count = sum(1 for c in concerned if c in text)

    if concern_count > 0:
        return 'concerned', concern_count
    elif neg_count > pos_count:
        return 'negative', neg_count
    elif pos_count > neg_count:
        return 'positive', pos_count
    else:
        return 'neutral', 0


def generate_theme_report(themes, articles):
    """Generate a theme analysis report."""

    lines = [
        "# Cross-Source Theme Analysis",
        "",
        f"*Analysis of {len(articles)} articles from {len(GENERALIST_SOURCES)} generalist sources*",
        f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*",
        "",
        "---",
        "",
        "## Methodology",
        "",
        "Unlike naive 'momentum' detection that counts stories per source,",
        "this analysis ONLY looks at generalist feeds (HN, Lobsters) for trends.",
        "",
        "A theme only registers as 'significant' if it appears across",
        "multiple independent generalist sources - indicating genuine",
        "industry momentum rather than source bias.",
        "",
        "Domain-specific feeds (TWiR, JS Weekly, etc.) provide content",
        "but are NOT used for trend detection (avoiding tautologies).",
        "",
        "---",
        "",
    ]

    if not themes:
        lines.append("## No Cross-Source Themes Detected")
        lines.append("")
        lines.append("No themes appeared across multiple generalist sources this period.")
        lines.append("This could indicate:")
        lines.append("- Fragmented news cycle (no dominant narratives)")
        lines.append("- Diverse technical discussions")
        lines.append("- Need to check domain-specific feeds for deeper content")
        return '\n'.join(lines)

    lines.append("## 🔥 Significant Cross-Source Themes")
    lines.append("")
    lines.append("Themes appearing in multiple generalist sources:")
    lines.append("")

    theme_names = {
        'llms_ai': '🤖 LLMs & Foundation Models',
        'ai_safety': '⚠️ AI Safety & Alignment',
        'training_inference': '🚀 Training & Inference',
        'robotics': '🦾 Robotics & Embodied AI',
        'rust_systems': '⚙️ Rust & Systems Programming',
        'web_platform': '🌐 Web Platform',
        'databases': '🗄️ Databases & Storage',
        'security': '🔒 Security',
        'developer_tools': '🛠️ Developer Tools',
        'open_source': '📂 Open Source'
    }

    for theme_key, data in list(themes.items())[:5]:
        display_name = theme_names.get(theme_key, theme_key)
        lines.append(f"### {display_name}")
        lines.append("")
        lines.append(f"**Significance:** {data['article_count']} articles across {', '.join(data['sources'])}")
        lines.append("")
        lines.append("Key stories:")
        for article in data['articles'][:3]:
            sentiment, _ = analyze_sentiment(article['title'], '')
            emoji = {'positive': '✅', 'negative': '⚠️', 'concerned': '🚨', 'neutral': '•'}[sentiment]
            lines.append(f"{emoji} **{article['title']}** ({article['source']})")
        lines.append("")

    # Sentiment analysis
    lines.append("---")
    lines.append("")
    lines.append("## 📊 Practitioner Sentiment")
    lines.append("")

    sentiments = defaultdict(int)
    for article in articles:
        sentiment, _ = analyze_sentiment(article[0], article[3])
        sentiments[sentiment] += 1

    total = len(articles)
    for sentiment, count in sorted(sentiments.items(), key=lambda x: x[1], reverse=True):
        pct = (count / total) * 100
        emoji = {'positive': '✅', 'negative': '⚠️', 'concerned': '🚨', 'neutral': '⚪'}[sentiment]
        lines.append(f"{emoji} {sentiment.capitalize()}: {count} articles ({pct:.0f}%)")

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 🎯 Implications")
    lines.append("")

    # Generate implications based on top themes
    top_themes = list(themes.keys())[:3]

    if 'llms_ai' in top_themes and 'training_inference' in top_themes:
        lines.append("- **AI Infrastructure:** Focus shifting from model releases to")
        lines.append("  training efficiency and inference optimization - sign of maturation")

    if 'robotics' in top_themes:
        lines.append("- **Physical AI:** Robotics discussions crossing into generalist tech")
        lines.append("  communities - potential inflection point for embodied AI")

    if 'rust_systems' in top_themes:
        lines.append("- **Systems Language Shift:** Rust continues expanding beyond")
        lines.append("  early adopters into mainstream systems programming")

    if 'ai_safety' in top_themes:
        lines.append("- **Safety Mainstreaming:** AI safety/alignment discussions")
        lines.append("  appearing in general engineering forums, not just research circles")

    if not top_themes:
        lines.append("- **No dominant narratives** - fragmented attention across")
        lines.append("  many technical areas. Good time for focused deep work.")

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(f"*Analysis method: Cross-source theme detection on {len(GENERALIST_SOURCES)} generalist feeds*")
    lines.append(f"*Data: {len(articles)} articles from past 7 days*")

    return '\n'.join(lines)


def main():
    print("Cross-Source Theme Analysis")
    print("=" * 50)
    print(f"Generalist sources: {', '.join(GENERALIST_SOURCES)}")
    print(f"Domain sources (content only): {', '.join(DOMAIN_SOURCES.keys())}")
    print()

    conn = sqlite3.connect(DB_PATH)

    print("Fetching articles from generalist sources...")
    articles = get_recent_generalist_articles(conn)
    print(f"  Found {len(articles)} articles")

    if len(articles) < 5:
        print("ERROR: Not enough articles for meaningful analysis")
        conn.close()
        return 1

    print("\nExtracting themes...")
    themes = detect_cross_source_themes(articles)
    print(f"  Found {len(themes)} cross-source themes")

    for theme, data in themes.items():
        print(f"    {theme}: {data['article_count']} articles, sources: {data['sources']}")

    print("\nGenerating report...")
    report = generate_theme_report(themes, articles)

    output_path = 'output/cross-source-analysis.md'
    with open(output_path, 'w') as f:
        f.write(report)

    print(f"Report written to {output_path}")

    # Preview
    print("\n" + "="*50)
    print("PREVIEW:")
    print("="*50)
    print(report[:2000])
    print("...")

    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
