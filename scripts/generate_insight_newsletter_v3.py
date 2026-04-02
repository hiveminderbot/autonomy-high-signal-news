#!/usr/bin/env python3
"""
Insight Newsletter Generator v3

Groups stories by theme with LLM-powered 'Why it matters' generation.
Uses actual article content analysis instead of generic pattern matching.

Features:
- Uses LLM insights from run_llm_analysis.py (run via Hermes for LLM access)
- Caching of LLM results in database
- Fallback to v2 pattern matching if no LLM insights available
- Content-aware importance scoring

USAGE:
1. First, populate LLM insights (run from Hermes context):
   python scripts/run_llm_analysis.py

2. Then generate newsletter:
   python scripts/generate_insight_newsletter_v3.py

Note: Direct API calls removed because Kimi Code API keys are restricted
      to specific coding agents (Claude Code, Kimi CLI, etc.).
"""

import sqlite3
import sys
import os
import re
import json
from datetime import datetime
from collections import defaultdict

# Import cross-source theme analysis
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from analyze_cross_source_themes import (
    get_recent_generalist_articles,
    detect_cross_source_themes,
    analyze_sentiment,
    GENERALIST_SOURCES
)

DB_PATH = 'news.db'
OUTPUT_PATH = 'output/insight-newsletter-v3.md'
CACHE_TABLE = 'llm_why_it_matters_cache'


def ensure_cache_table(conn):
    """Ensure cache table exists for LLM insights."""
    conn.execute(f'''
        CREATE TABLE IF NOT EXISTS {CACHE_TABLE} (
            article_id INTEGER PRIMARY KEY,
            why_it_matters TEXT NOT NULL,
            generated_at TEXT NOT NULL,
            model_used TEXT
        )
    ''')
    conn.commit()


def ensure_llm_columns(conn):
    """Ensure articles table has LLM analysis columns."""
    cursor = conn.execute("PRAGMA table_info(articles)")
    columns = [row[1] for row in cursor.fetchall()]

    for col in ['llm_summary', 'llm_insight', 'llm_key_findings', 'llm_processed_at']:
        if col not in columns:
            conn.execute(f"ALTER TABLE articles ADD COLUMN {col} TEXT")

    conn.commit()


def get_cached_why_it_matters(conn, article_id):
    """Get cached LLM insight for article."""
    cursor = conn.execute(
        f'SELECT why_it_matters FROM {CACHE_TABLE} WHERE article_id = ?',
        (article_id,)
    )
    row = cursor.fetchone()
    return row[0] if row else None


def cache_why_it_matters(conn, article_id, why_it_matters, model_used='kimi'):
    """Cache LLM insight for article."""
    conn.execute(f'''
        INSERT OR REPLACE INTO {CACHE_TABLE} (article_id, why_it_matters, generated_at, model_used)
        VALUES (?, ?, ?, ?)
    ''', (article_id, why_it_matters, datetime.now().isoformat(), model_used))
    conn.commit()


def get_why_it_matters(conn, article_id, title, source, content, themes):
    """Get 'why it matters' - tries LLM analysis, then cache, then fallback."""

    # 1. Check if LLM analysis already exists from run_llm_analysis.py
    cursor = conn.execute(
        'SELECT llm_insight FROM articles WHERE id = ? AND llm_insight IS NOT NULL',
        (article_id,)
    )
    row = cursor.fetchone()
    if row and row[0]:
        return row[0], 'llm_analysis'

    # 2. Check our cache
    cached = get_cached_why_it_matters(conn, article_id)
    if cached:
        return cached, 'cached'

    # 3. Fallback to v2 pattern matching (direct API removed - keys restricted)
    return get_fallback_why_it_matters(title, source, themes), 'fallback'


def get_fallback_why_it_matters(title, source, themes):
    """Fallback pattern matching from v2."""

    # LLM/AI developments
    if 'llms' in themes:
        if 'training' in themes:
            return "Training efficiency improvements directly reduce AI development costs and enable larger models."
        if 'inference' in themes:
            return "Inference optimization makes AI cheaper to run at scale, enabling broader deployment."
        if 'embeddings' in themes:
            return "Better embeddings improve search, RAG, and semantic understanding applications."
        return "Foundation model improvements ripple through the entire AI stack."

    # Robotics
    if 'robotics' in themes:
        return "Robotics AI is the next frontier after language models - practical physical automation."

    # Rust
    if 'rust' in themes:
        return "Rust continues displacing C++ in systems programming where memory safety matters."

    # Databases
    if 'databases' in themes:
        return "Database innovations affect every application - performance and scalability bottlenecks."

    # Web
    if 'web' in themes:
        return "Frontend ecosystem changes affect millions of developers and user experiences."

    # HN discussions
    if source == 'Hacker News':
        if 'Show HN' in title:
            return "Community-built tools often indicate emerging developer needs before they become mainstream."
        return "HN discussions reflect practitioner sentiment and emerging technical concerns."

    # Research
    if source == 'Distill.pub':
        return "Distill research provides fundamental understanding that outlasts implementation trends."

    return None


def extract_key_themes(title, content):
    """Extract key themes from article."""
    text = (title + ' ' + (content or '')).lower()
    themes = []

    # AI/ML themes
    if any(w in text for w in ['llm', 'gpt', 'claude', 'transformer', 'fine-tun', 'rlhf']):
        themes.append('llms')
    if any(w in text for w in ['embedding', 'vector', 'retrieval', 'rag']):
        themes.append('embeddings')
    if any(w in text for w in ['training', 'model', 'parameter', 'gpu', 'distributed']):
        themes.append('training')
    if any(w in text for w in ['inference', 'serving', 'deployment', 'latency']):
        themes.append('inference')
    if any(w in text for w in ['robotics', 'embodied', 'manipulation']):
        themes.append('robotics')

    # Systems themes
    if any(w in text for w in ['rust', 'memory safety', 'borrow checker']):
        themes.append('rust')
    if any(w in text for w in ['async', 'concurrent', 'parallel']):
        themes.append('async')
    if any(w in text for w in ['database', 'storage', 'sql', 'graph']):
        themes.append('databases')

    # Web themes
    if any(w in text for w in ['react', 'frontend', 'typescript', 'javascript']):
        themes.append('web')
    if any(w in text for w in ['wasm', 'webassembly']):
        themes.append('wasm')

    # Security themes
    if any(w in text for w in ['security', 'vulnerability', 'exploit', 'crypto']):
        themes.append('security')

    return themes


def get_recent_articles(conn, hours=48):
    """Get recent articles with extracted full content."""
    cursor = conn.execute('''
        SELECT id, title, url, source, domain,
               COALESCE(full_content, content) as content,
               published_at, full_content
        FROM articles
        WHERE source IN ('Hacker News', 'Lobsters', 'This Week in Rust', 'JavaScript Weekly',
                         'Hugging Face Blog', 'Distill.pub')
          AND (full_content IS NOT NULL OR content IS NOT NULL)
        ORDER BY fetched_at DESC
        LIMIT 30
    ''')
    return cursor.fetchall()


def group_by_theme(articles):
    """Group articles by extracted themes."""
    theme_groups = defaultdict(list)
    article_themes = {}

    for article in articles:
        article_id, title, url, source, domain, content, published_at, full_content = article
        themes = extract_key_themes(title, content)
        article_themes[article_id] = themes

        for theme in themes:
            theme_groups[theme].append(article)

    return theme_groups, article_themes


def score_article_importance(title, source, content, themes, why_source):
    """Score article importance (0-100), bonus for LLM-generated insights."""
    score = 50  # Base score

    # Source quality bonus
    source_scores = {
        'Distill.pub': 20,
        'Hugging Face Blog': 15,
        'This Week in Rust': 10,
        'JavaScript Weekly': 8,
        'Hacker News': 5,
        'Lobsters': 5,
    }
    score += source_scores.get(source, 0)

    # Theme importance
    theme_scores = {
        'llms': 15,
        'training': 12,
        'inference': 12,
        'robotics': 15,
        'rust': 10,
        'databases': 8,
        'security': 15,
        'web': 5,
    }
    for theme in themes:
        score += theme_scores.get(theme, 0)

    # LLM insight bonus (content-aware > generic)
    if why_source == 'llm_new':
        score += 10
    elif why_source == 'llm_analysis':
        score += 8
    elif why_source == 'cached':
        score += 5

    # Title signals
    if 'Show HN' in title:
        score += 10
    if any(w in title.lower() for w in ['release', 'launch', 'announcing']):
        score += 5

    return min(score, 100)


def generate_insight_newsletter(articles, theme_groups, article_themes, conn):
    """Generate newsletter with LLM-powered insight."""

    # Score and rank articles
    scored_articles = []
    why_sources = {}

    for article in articles:
        article_id, title, url, source, domain, content, published_at, full_content = article
        themes = article_themes.get(article_id, [])

        # Get content-aware why_it_matters
        why, why_source = get_why_it_matters(conn, article_id, title, source, full_content or content, themes)
        why_sources[article_id] = why_source

        score = score_article_importance(title, source, content, themes, why_source)
        scored_articles.append((score, article, themes, why, why_source))

    scored_articles.sort(reverse=True)

    # Count sources used
    source_counts = defaultdict(int)
    for _, _, _, _, why_source in scored_articles:
        source_counts[why_source] += 1

    lines = [
        "# High-Signal Insight Newsletter",
        "",
        f"*{datetime.now().strftime('%B %d, %Y')} | Curated for practitioners who need to know*",
        "",
        f"_Generated with {source_counts.get('llm_new', 0)} new LLM insights, "
        f"{source_counts.get('cached', 0)} cached, "
        f"{source_counts.get('llm_analysis', 0)} from prior analysis, "
        f"{source_counts.get('fallback', 0)} pattern-matched_",
        "",
        "---",
        "",
    ]

    # Top stories section
    lines.append("## 🔥 Top Stories")
    lines.append("")
    lines.append("Stories with highest practitioner impact this week:")
    lines.append("")

    for score, article, themes, why, why_source in scored_articles[:5]:
        article_id, title, url, source, domain, content, published_at, full_content = article

        # Add indicator for insight source
        source_indicator = {
            'llm_new': '✨',
            'llm_analysis': '🔍',
            'cached': '💾',
            'fallback': '📋'
        }.get(why_source, '')

        lines.append(f"**{title}**")
        lines.append(f"*{source}* | [Read article]({url})")
        if why:
            lines.append(f"💡 **Why it matters:** {why} {source_indicator}")
        if themes:
            lines.append(f"🏷️ Tags: {', '.join(themes)}")
        lines.append("")

    # Theme sections - using cross-source analysis
    lines.append("---")
    lines.append("")

    # Get cross-source themes from generalist feeds only
    cross_source_themes = detect_cross_source_themes(
        get_recent_generalist_articles(conn)
    )

    if cross_source_themes:
        lines.append("## 📊 Cross-Source Trending Themes")
        lines.append("")
        lines.append("Themes appearing across multiple independent sources (HN + Lobsters):")
        lines.append("")
        lines.append("*Unlike naive 'momentum' counting, these themes only register when")
        lines.append("discussed across generalist communities, avoiding source bias.*")
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

        for theme_key, data in list(cross_source_themes.items())[:5]:
            display_name = theme_names.get(theme_key, theme_key.replace('_', ' ').title())
            article_count = data['article_count']
            sources = ', '.join(data['sources'])

            lines.append(f"### {display_name}")
            lines.append("")
            lines.append(f"**{article_count} articles** across {sources}")
            lines.append("")
            lines.append("Key stories:")
            for article in data['articles'][:3]:
                lines.append(f"- **{article['title']}** ({article['source']})")
            lines.append("")

    # Community highlights
    lines.append("---")
    lines.append("")
    lines.append("## 💡 Community Highlights")
    lines.append("")
    lines.append("Interesting discussions and projects from HN/Lobsters:")
    lines.append("")

    community_articles = [a for a in articles if a[3] in ['Hacker News', 'Lobsters']]
    for article in community_articles[:5]:
        article_id, title, url, source, domain, content, published_at, full_content = article
        lines.append(f"- **{title}** [{source}]")

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 🎯 Action Items for Practitioners")
    lines.append("")

    # Use cross-source themes for action items
    top_cross_themes = list(cross_source_themes.keys())[:3] if cross_source_themes else []

    for theme in top_cross_themes:
        if theme == 'llms_ai':
            lines.append("- **AI/LLM:** Evaluate new training and inference optimizations for cost reduction")
        elif theme == 'training_inference':
            lines.append("- **AI Infrastructure:** Focus shifting to efficiency - review serving costs and latency")
        elif theme == 'robotics':
            lines.append("- **Robotics:** Follow embedded AI trends - edge deployment becoming practical")
        elif theme == 'rust_systems':
            lines.append("- **Rust:** Track ecosystem developments for systems programming decisions")
        elif theme == 'databases':
            lines.append("- **Data:** Review new database tools for upcoming project architecture")
        elif theme == 'web_platform':
            lines.append("- **Frontend:** Check React/TS ecosystem updates for dependency upgrades")
        elif theme == 'ai_safety':
            lines.append("- **AI Safety:** Monitor alignment research - may affect deployment strategies")
        elif theme == 'security':
            lines.append("- **Security:** Review dependencies and security posture - active discussions indicate threats")
        elif theme == 'developer_tools':
            lines.append("- **DevTools:** Evaluate new tools for workflow improvements")
        elif theme == 'open_source':
            lines.append("- **Open Source:** Track license and community changes affecting dependencies")

    if not top_cross_themes:
        lines.append("- No dominant cross-source themes this cycle - good time for deep work on existing stack")

    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(f"*Generated {datetime.now().strftime('%Y-%m-%d %H:%M')} | "
                 f"Sources: HN, Lobsters, HF, TWiR, JS Weekly, Distill*")
    lines.append("")
    lines.append("**Legend:** ✨=New LLM insight | 🔍=Prior LLM analysis | 💾=Cached | 📋=Pattern-matched")
    lines.append("")
    lines.append("**Reading strategy:** 🔥 = Must read | 📊 = Trend tracking | 💡 = Community signal")

    return '\n'.join(lines), source_counts


def main():
    print(f"Connecting to {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)

    ensure_cache_table(conn)
    ensure_llm_columns(conn)

    print("Fetching recent articles...")
    articles = get_recent_articles(conn)
    print(f"  Found {len(articles)} articles")

    if not articles:
        print("No articles found!")
        return 1

    print("Analyzing themes...")
    theme_groups, article_themes = group_by_theme(articles)

    print(f"  Identified {len(theme_groups)} themes:")
    for theme, articles_in_theme in sorted(theme_groups.items(), key=lambda x: len(x[1]), reverse=True):
        print(f"    {theme}: {len(articles_in_theme)} articles")

    print("\nGenerating insight newsletter v3...")
    print("  LLM sources: llm_analysis column, cache, fallback patterns")
    print("  Note: Run run_llm_analysis.py from Hermes context for LLM insights")

    newsletter, source_counts = generate_insight_newsletter(articles, theme_groups, article_themes, conn)

    with open(OUTPUT_PATH, 'w') as f:
        f.write(newsletter)

    print(f"\nNewsletter written to {OUTPUT_PATH}")
    print(f"\nInsight sources:")
    for source, count in sorted(source_counts.items()):
        icon = {'llm_new': '✨', 'llm_analysis': '🔍', 'cached': '💾', 'fallback': '📋'}.get(source, '?')
        print(f"  {icon} {source}: {count}")

    # Show preview
    print("\n" + "="*60)
    print("PREVIEW:")
    print("="*60)
    print(newsletter[:2500])
    print("...")

    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
