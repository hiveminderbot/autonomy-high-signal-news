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

import argparse
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


def generate_newsletter_html(articles: list) -> str:
    """Generate the newsletter as HTML."""
    today = datetime.now().strftime('%Y-%m-%d')
    generated_at = datetime.now().isoformat()

    # CSS styling
    css = """
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; line-height: 1.6; color: #333; }
        h1 { border-bottom: 2px solid #2563eb; padding-bottom: 10px; color: #1e40af; }
        h2 { color: #374151; margin-top: 30px; border-left: 4px solid #2563eb; padding-left: 12px; }
        .meta { color: #6b7280; font-size: 0.9em; margin-bottom: 20px; }
        .source-note { background: #eff6ff; border-left: 4px solid #2563eb; padding: 12px; margin: 15px 0; border-radius: 4px; }
        .article { margin: 18px 0; padding: 12px; background: #f9fafb; border-radius: 6px; }
        .article-title { font-weight: 600; font-size: 1.05em; margin-bottom: 4px; }
        .article-source { color: #6b7280; font-size: 0.85em; font-style: italic; }
        .article-insight { color: #4b5563; font-size: 0.9em; margin: 8px 0; padding-left: 12px; border-left: 3px solid #d1d5db; }
        .article-link a { color: #2563eb; text-decoration: none; }
        .article-link a:hover { text-decoration: underline; }
        .themes { background: #fef3c7; border-radius: 6px; padding: 12px; margin: 15px 0; }
        .theme-item { margin: 6px 0; }
        .footer { margin-top: 30px; padding-top: 15px; border-top: 1px solid #e5e7eb; color: #9ca3af; font-size: 0.8em; }
    </style>
    """

    lines = [
        "<!DOCTYPE html>",
        "<html lang='en'>",
        "<head>",
        "<meta charset='UTF-8'>",
        f"<title>High-Signal Briefing — {today}</title>",
        css,
        "</head>",
        "<body>",
        f"<h1>High-Signal Briefing — {today}</h1>",
        f"<div class='meta'>{len(articles)} high-signal stories from the past week</div>",
        "<div class='source-note'><strong>Tier-1 Sources Only</strong>: Distinguished engineers, top researchers, and high-signal publications</div>",
    ]

    # Cross-source synthesis
    synthesis = generate_synthesis(articles)
    if synthesis:
        # Convert markdown synthesis to HTML
        lines.append("<div class='themes'>")
        lines.append("<h3>🔥 Cross-Source Themes</h3>")
        for line in synthesis.split('\n'):
            line = line.strip()
            if not line:
                continue
            if line.startswith('###'):
                continue
            if line.startswith('**') and line.endswith('**'):
                lines.append(f"<div class='theme-item'><strong>{line.strip('*')}</strong></div>")
            elif line.startswith('- '):
                lines.append(f"<div class='theme-item'>{line[2:]}</div>")
            else:
                lines.append(f"<div class='theme-item'>{line}</div>")
        lines.append("</div>")

    # Group by domain
    by_domain = group_by_domain(articles)
    priority = ['ai_research', 'ai_labs', 'software', 'research', 'investment', 'community']
    emojis = {
        'ai_research': '🧠',
        'ai_labs': '🤖',
        'software': '💻',
        'research': '📄',
        'investment': '💰',
        'community': '👥',
    }

    for domain in priority:
        if domain not in by_domain:
            continue
        domain_articles = by_domain[domain]
        if not domain_articles:
            continue
        emoji = emojis.get(domain, '📰')
        lines.append(f"<h2>{emoji} {domain.replace('_', ' ').title()}</h2>")
        for art in domain_articles[:5]:
            title = art['title']
            url = art['url']
            source = art.get('source_name', 'Unknown')
            insight = art.get('llm_insight')
            lines.append("<div class='article'>")
            lines.append(f"<div class='article-title'>{title}</div>")
            lines.append(f"<div class='article-source'>{source}</div>")
            if insight:
                lines.append(f"<div class='article-insight'>{insight[:150]}...</div>")
            lines.append(f"<div class='article-link'><a href='{url}'>Read more →</a></div>")
            lines.append("</div>")

    lines.append("<div class='footer'>")
    lines.append(f"<p>Generated: {generated_at}</p>")
    lines.append("<p>Sources: Tier-1 only (distinguished engineers, top researchers, high-signal publications)</p>")
    lines.append("</div>")
    lines.append("</body>")
    lines.append("</html>")

    return '\n'.join(lines)


def generate_newsletter_json(articles: list) -> str:
    """Generate the newsletter as structured JSON."""
    today = datetime.now().strftime('%Y-%m-%d')
    generated_at = datetime.now().isoformat()

    # Group by domain
    by_domain = group_by_domain(articles)

    # Build articles list with full metadata
    articles_out = []
    for art in articles:
        articles_out.append({
            'id': art.get('id'),
            'title': art.get('title'),
            'url': art.get('url'),
            'source': art.get('source_name', 'Unknown'),
            'domain': art.get('domain', 'general'),
            'tier': art.get('tier'),
            'quality_score': art.get('quality_score'),
            'published_at': art.get('published_at'),
            'insight': art.get('llm_insight'),
        })

    # Cross-source themes
    themes = detect_cross_source_themes(articles)
    themes_out = [
        {
            'topic': t['topic'],
            'sources': t['sources'],
            'mention_count': t['mention_count'],
            'article_titles': [a['title'] for a in t['articles']],
        }
        for t in themes
    ]

    payload = {
        'meta': {
            'generated_at': generated_at,
            'date': today,
            'total_articles': len(articles),
            'format_version': '1.0',
        },
        'sources_summary': {
            'tier': 1,
            'criteria': 'distinguished engineers, top researchers, high-signal publications',
        },
        'themes': themes_out,
        'articles_by_domain': {
            domain.replace('_', ' ').title(): [
                {
                    'title': a.get('title'),
                    'url': a.get('url'),
                    'source': a.get('source_name', 'Unknown'),
                    'insight': a.get('llm_insight'),
                }
                for a in arts[:5]
            ]
            for domain, arts in by_domain.items()
        },
        'articles': articles_out,
    }

    return json.dumps(payload, indent=2, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser(description="Generate high-signal briefing")
    parser.add_argument(
        '--format', choices=['markdown', 'html', 'json', 'all'],
        default='all',
        help='Output format(s) to generate (default: all)'
    )
    parser.add_argument(
        '--days', type=int, default=7,
        help='Number of days to look back (default: 7)'
    )
    parser.add_argument(
        '--output-dir', type=Path, default=OUTPUT_PATH,
        help='Output directory (default: output/)'
    )
    args = parser.parse_args()

    print("Generating high-signal briefing...")
    print(f"Format: {args.format}")
    print()

    # Get recent articles
    print(f"Fetching articles from last {args.days} days...")
    articles = get_recent_articles(days=args.days)
    print(f"Found: {len(articles)} articles")
    print()

    # Filter
    print("Filtering low-signal content...")
    filtered = filter_high_signal(articles)
    print(f"After filtering: {len(filtered)} articles")
    print()

    if not filtered:
        print("No articles passed filtering. Nothing to generate.")
        return

    # Write output
    args.output_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime('%Y-%m-%d')
    generated = []

    formats_to_generate = []
    if args.format == 'all':
        formats_to_generate = ['markdown', 'html', 'json']
    else:
        formats_to_generate = [args.format]

    for fmt in formats_to_generate:
        if fmt == 'markdown':
            newsletter = generate_newsletter(filtered)
            output_file = args.output_dir / f"briefing-high-signal-{today}.md"
            with open(output_file, 'w') as f:
                f.write(newsletter)
            generated.append(output_file)
            print(f"Generated Markdown: {output_file}")
        elif fmt == 'html':
            html = generate_newsletter_html(filtered)
            output_file = args.output_dir / f"briefing-high-signal-{today}.html"
            with open(output_file, 'w') as f:
                f.write(html)
            generated.append(output_file)
            print(f"Generated HTML: {output_file}")
        elif fmt == 'json':
            json_out = generate_newsletter_json(filtered)
            output_file = args.output_dir / f"briefing-high-signal-{today}.json"
            with open(output_file, 'w') as f:
                f.write(json_out)
            generated.append(output_file)
            print(f"Generated JSON: {output_file}")

    print(f"\nTotal articles included: {len(filtered)}")
    print(f"Files generated: {len(generated)}")


if __name__ == '__main__':
    main()
