#!/usr/bin/env python3
"""
Insight Newsletter Generator v2

Groups stories by theme, identifies patterns, explains why things matter.
Uses manual curation rules + content analysis.
"""

import sqlite3
import sys
import re
from datetime import datetime
from collections import defaultdict

DB_PATH = 'news.db'
OUTPUT_PATH = 'output/insight-newsletter-v2.md'


def get_recent_articles(conn, hours=48):
    """Get recent articles with good content."""
    cursor = conn.execute('''
        SELECT title, url, source, domain, content, published_at
        FROM articles
        WHERE source IN ('Hacker News', 'Lobsters', 'This Week in Rust', 'JavaScript Weekly',
                         'Hugging Face Blog', 'Distill.pub')
        ORDER BY fetched_at DESC
        LIMIT 30
    ''')
    return cursor.fetchall()


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


def get_why_it_matters(title, source, themes):
    """Generate 'why this matters' context."""
    
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


def group_by_theme(articles):
    """Group articles by extracted themes."""
    theme_groups = defaultdict(list)
    article_themes = {}
    
    for article in articles:
        title, url, source, domain, content, published_at = article
        themes = extract_key_themes(title, content)
        article_themes[title] = themes
        
        # Add to each theme group
        for theme in themes:
            theme_groups[theme].append(article)
    
    return theme_groups, article_themes


def score_article_importance(title, source, content, themes):
    """Score article importance (0-100)."""
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
    
    # Title signals
    if 'Show HN' in title:
        score += 10  # Community validation
    if any(w in title.lower() for w in ['release', 'launch', 'announcing']):
        score += 5
    
    return min(score, 100)


def generate_insight_newsletter(articles, theme_groups, article_themes):
    """Generate newsletter with insight."""
    
    # Score and rank articles
    scored_articles = []
    for article in articles:
        title, url, source, domain, content, published_at = article
        themes = article_themes.get(title, [])
        score = score_article_importance(title, source, content, themes)
        scored_articles.append((score, article, themes))
    
    scored_articles.sort(reverse=True)
    
    lines = [
        "# High-Signal Insight Newsletter",
        "",
        f"*{datetime.now().strftime('%B %d, %Y')} | Curated for practitioners who need to know*",
        "",
        "---",
        "",
    ]
    
    # Top stories section (highest scored)
    lines.append("## 🔥 Top Stories")
    lines.append("")
    lines.append("Stories with highest practitioner impact this week:")
    lines.append("")
    
    for score, article, themes in scored_articles[:5]:
        title, url, source, domain, content, published_at = article
        why = get_why_it_matters(title, source, themes)
        
        lines.append(f"**{title}**")
        lines.append(f"*{source}* | [Read article]({url})")
        if why:
            lines.append(f"💡 **Why it matters:** {why}")
        if themes:
            lines.append(f"🏷️ Tags: {', '.join(themes)}")
        lines.append("")
    
    # Theme sections
    lines.append("---")
    lines.append("")
    
    # Find themes with multiple stories
    multi_story_themes = {t: a for t, a in theme_groups.items() if len(a) >= 2}
    
    if multi_story_themes:
        lines.append("## 📊 Trending Themes")
        lines.append("")
        lines.append("Multiple stories indicate industry momentum in these areas:")
        lines.append("")
        
        theme_order = ['llms', 'training', 'inference', 'robotics', 'rust', 'databases', 'web']
        for theme in theme_order:
            if theme not in multi_story_themes:
                continue
            
            theme_articles = multi_story_themes[theme]
            lines.append(f"### {theme.upper()} ({len(theme_articles)} stories)")
            lines.append("")
            
            for article in theme_articles[:3]:
                title, url, source, domain, content, published_at = article
                lines.append(f"- **{title}** ({source})")
            lines.append("")
    
    # Community highlights
    lines.append("---")
    lines.append("")
    lines.append("## 💡 Community Highlights")
    lines.append("")
    lines.append("Interesting discussions and projects from HN/Lobsters:")
    lines.append("")
    
    community_articles = [a for a in articles if a[2] in ['Hacker News', 'Lobsters']]
    for article in community_articles[:5]:
        title, url, source, domain, content, published_at = article
        lines.append(f"- **{title}** [{source}]")
    
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append("## 🎯 Action Items for Practitioners")
    lines.append("")
    
    # Generate action items based on top themes
    top_themes = sorted(multi_story_themes.keys(), key=lambda t: len(multi_story_themes[t]), reverse=True)[:3]
    
    for theme in top_themes:
        if theme == 'llms':
            lines.append("- **AI/LLM:** Evaluate new training and inference optimizations for cost reduction")
        elif theme == 'robotics':
            lines.append("- **Robotics:** Follow embedded AI trends - edge deployment becoming practical")
        elif theme == 'rust':
            lines.append("- **Rust:** Track ecosystem developments for systems programming decisions")
        elif theme == 'databases':
            lines.append("- **Data:** Review new database tools for upcoming project architecture")
        elif theme == 'web':
            lines.append("- **Frontend:** Check React/TS ecosystem updates for dependency upgrades")
    
    if not top_themes:
        lines.append("- No dominant themes this cycle - good time for deep work on existing stack")
    
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(f"*Generated {datetime.now().strftime('%Y-%m-%d %H:%M')} | Sources: HN, Lobsters, HF, TWiR, JS Weekly, Distill*")
    lines.append("")
    lines.append("**Reading strategy:** 🔥 = Must read | 📊 = Trend tracking | 💡 = Community signal")
    
    return '\n'.join(lines)


def main():
    print(f"Connecting to {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    
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
    
    print("\nGenerating insight newsletter...")
    newsletter = generate_insight_newsletter(articles, theme_groups, article_themes)
    
    with open(OUTPUT_PATH, 'w') as f:
        f.write(newsletter)
    
    print(f"Newsletter written to {OUTPUT_PATH}")
    
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
