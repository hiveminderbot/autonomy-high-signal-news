#!/usr/bin/env python3
"""
Generate high-signal newsletter with filtering and synthesis.

Refactored to use the centralized briefing.renderer module for all output formats,
eliminating duplicate ad-hoc HTML/JSON/Markdown generation code.

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
import sys
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict


def write_text_without_trailing_whitespace(path: Path, text: str) -> None:
    """Write generated artifacts without line-ending whitespace that breaks diff checks."""
    cleaned = "\n".join(line.rstrip() for line in text.splitlines())
    if text.endswith("\n"):
        cleaned += "\n"
    path.write_text(cleaned)


# Add scripts/ to path so briefing package is importable
_scripts_path = Path(__file__).parent
if str(_scripts_path) not in sys.path:
    sys.path.insert(0, str(_scripts_path))

from briefing.generator import BriefingGenerator, BriefingResult, BriefingSection, BriefingItem, BriefingMetadata
from briefing.renderer import MarkdownRenderer, HTMLRenderer, TextRenderer

DB_PATH = Path(__file__).parent.parent / "news.db"
STATE_FEED_DB_PATH = Path(__file__).parent.parent / "state" / "aggregation.db"
STATE_NEWSLETTER_DB_PATH = Path(__file__).parent.parent / "state" / "newsletters.db"
OUTPUT_PATH = Path(__file__).parent.parent / "output"
MIN_BRIEFING_BYTES = 1024
PLACEHOLDER_BRIEFING_TEXTS = {"test", "todo", "placeholder", "no briefing available yet"}

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
    if not DB_PATH.exists():
        return get_recent_state_entries(days=days)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cutoff = (datetime.now() - timedelta(days=days)).isoformat()

    cursor.execute("""
        WITH source_quality AS (
            SELECT name, MIN(tier) AS tier, MAX(quality_score) AS quality_score
            FROM sources
            GROUP BY name
        )
        SELECT a.id, a.title, a.url, a.source, a.domain, a.published_at,
               a.full_content, a.content, a.llm_insight,
               s.name as source_name, s.tier, s.quality_score
        FROM articles a
        JOIN source_quality s ON a.source = s.name
        WHERE a.fetched_at > ?
          AND a.extraction_status = 'extracted'
          AND s.tier = 1
        ORDER BY s.quality_score DESC,
                 COALESCE(datetime(a.published_at), datetime(a.fetched_at)) DESC
    """, (cutoff,))

    articles = [dict(row) for row in cursor.fetchall()]
    conn.close()

    if articles:
        return articles

    # The daily aggregation cron writes fresh RSS/newsletter rows to state/*.db.
    # When the legacy article store is stale or empty, generate from that live
    # cache instead of silently leaving latest.md as a placeholder.
    return get_recent_state_entries(days=days)


def get_recent_state_entries(days: int = 7, limit: int = 250) -> list:
    """Get recent entries from the live aggregation/newsletter state databases."""
    articles = []

    if STATE_FEED_DB_PATH.exists():
        conn = sqlite3.connect(STATE_FEED_DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, title, url, source_id, published_at, summary, author,
                   content, fetched_at, relevance_score, relevance_tier
            FROM feed_entries
            WHERE datetime(fetched_at) > datetime('now', ?)
            ORDER BY
                COALESCE(relevance_score, 0) DESC,
                length(COALESCE(content, summary, '')) DESC,
                datetime(fetched_at) DESC
            LIMIT ?
            """,
            (f"-{days} days", limit),
        )
        for row in cursor.fetchall():
            text = row["content"] or row["summary"] or ""
            articles.append({
                "id": row["id"],
                "title": row["title"],
                "url": row["url"],
                "source": row["source_id"],
                "source_name": row["source_id"],
                "domain": infer_domain(row["source_id"], row["title"], text),
                "published_at": row["published_at"],
                "fetched_at": row["fetched_at"],
                "full_content": text,
                "content": text,
                "llm_insight": row["summary"],
                "tier": 1,
                "quality_score": row["relevance_score"] or 0.5,
            })
        conn.close()

    if STATE_NEWSLETTER_DB_PATH.exists():
        conn = sqlite3.connect(STATE_NEWSLETTER_DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, title, url, newsletter_id, published_at, author,
                   content_text, fetched_at
            FROM newsletter_entries
            WHERE datetime(fetched_at) > datetime('now', ?)
            ORDER BY length(COALESCE(content_text, '')) DESC, datetime(fetched_at) DESC
            LIMIT ?
            """,
            (f"-{days} days", limit),
        )
        for row in cursor.fetchall():
            text = row["content_text"] or ""
            articles.append({
                "id": row["id"],
                "title": row["title"],
                "url": row["url"],
                "source": row["newsletter_id"],
                "source_name": row["newsletter_id"],
                "domain": infer_domain(row["newsletter_id"], row["title"], text),
                "published_at": row["published_at"],
                "fetched_at": row["fetched_at"],
                "full_content": text,
                "content": text,
                "llm_insight": text[:500],
                "tier": 1,
                "quality_score": 0.7,
            })
        conn.close()

    articles.sort(
        key=lambda article: (
            article.get("quality_score") or 0,
            len(article.get("full_content") or article.get("content") or ""),
        ),
        reverse=True,
    )
    return articles[:limit]


def infer_domain(source: str, title: str, content: str) -> str:
    """Infer a coarse briefing domain from source/title/content."""
    haystack = f"{source} {title} {content[:1000]}".lower()
    if any(term in haystack for term in ["kalshi", "trading", "market", "revenue", "funding", "valuation", "investment"]):
        return "investment"
    if any(term in haystack for term in ["llm", "agent", "openai", "anthropic", "model", "eval", "inference", "ai "]):
        return "ai"
    if any(term in haystack for term in ["python", "rust", "typescript", "database", "github", "security", "kubernetes"]):
        return "software_development"
    if any(term in haystack for term in ["paper", "arxiv", "research"]):
        return "research"
    return "general"


def validate_generated_briefing(content: str) -> None:
    """Fail fast on placeholder or undersized briefing artifacts."""
    stripped = content.strip()
    if stripped.lower() in PLACEHOLDER_BRIEFING_TEXTS:
        raise ValueError(f"Refusing to write placeholder briefing: {stripped!r}")
    size = len(content.encode("utf-8"))
    if size < MIN_BRIEFING_BYTES:
        raise ValueError(f"Refusing to write undersized briefing ({size} < {MIN_BRIEFING_BYTES} bytes)")


def generate_briefing_files(articles: list, output_dir: Path, formats_to_generate: list[str]) -> list[Path]:
    """Generate briefing artifacts and validate non-placeholder output."""
    output_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime('%Y-%m-%d')
    generated = []

    for fmt in formats_to_generate:
        if fmt == 'markdown':
            newsletter = generate_newsletter_markdown(articles)
            validate_generated_briefing(newsletter)
            output_file = output_dir / f"briefing-high-signal-{today}.md"
            write_text_without_trailing_whitespace(output_file, newsletter)
            latest_file = output_dir / "latest.md"
            write_text_without_trailing_whitespace(latest_file, newsletter)
            generated.append(output_file)
            print(f"Generated Markdown: {output_file}")
        elif fmt == 'html':
            html = generate_newsletter_html(articles)
            validate_generated_briefing(html)
            output_file = output_dir / f"briefing-high-signal-{today}.html"
            write_text_without_trailing_whitespace(output_file, html)
            latest_file = output_dir / "latest.html"
            write_text_without_trailing_whitespace(latest_file, html)
            generated.append(output_file)
            print(f"Generated HTML: {output_file}")
        elif fmt == 'json':
            json_out = generate_newsletter_json(articles)
            validate_generated_briefing(json_out)
            output_file = output_dir / f"briefing-high-signal-{today}.json"
            write_text_without_trailing_whitespace(output_file, json_out)
            generated.append(output_file)
            print(f"Generated JSON: {output_file}")
        elif fmt == 'text':
            text = generate_newsletter_text(articles)
            validate_generated_briefing(text)
            output_file = output_dir / f"briefing-high-signal-{today}.txt"
            write_text_without_trailing_whitespace(output_file, text)
            generated.append(output_file)
            print(f"Generated Text: {output_file}")

    return generated


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


def articles_to_stories(articles: list) -> list[dict]:
    """Convert raw article dicts into story dicts for the BriefingGenerator."""
    stories = []
    for art in articles:
        # Map domain to BriefingGenerator domain classification
        domain = art.get('domain', 'general')
        # Determine tier based on quality_score if available
        quality_score = art.get('quality_score', 0)
        if quality_score >= 90:
            tier = 'must_read'
        elif quality_score >= 70:
            tier = 'important'
        else:
            tier = 'contextual'

        raw_content = art.get('content') or ''
        story = {
            'title': art.get('title', 'Untitled'),
            'summary': art.get('llm_insight') or raw_content[:500],
            'sources': [art.get('source_name', 'Unknown')],
            'tier': tier,
            'entities': [],
            'urgency': 'normal',
            'url': art.get('url'),
            'published': art.get('published_at'),
            'domain': domain,
        }
        stories.append(story)
    return stories


def generate_cross_source_themes_markdown(articles: list) -> str:
    """Generate cross-source themes as markdown for the newsletter header."""
    themes = detect_cross_source_themes(articles)
    if not themes:
        return ""

    lines = ["### 🔥 Cross-Source Themes", ""]
    for theme in themes[:3]:
        lines.append(f"**{theme['topic'].title()}** — mentioned across {', '.join(theme['sources'])}")
        for art in theme['articles'][:2]:
            lines.append(f"  - [{art['title'][:70]}]({art['url']})")
        lines.append("")

    return '\n'.join(lines)


def build_briefing_result(articles: list) -> BriefingResult:
    """Build a BriefingResult from raw articles using the centralized generator."""
    stories = articles_to_stories(articles)
    generator = BriefingGenerator(
        max_items_per_section=10,
        max_must_read_total=5,
        max_important_total=10,
        target_reading_time=10,
    )
    # Override domain classification to use article domains instead of keyword matching
    # We manually build sections based on article domains
    by_domain = group_by_domain(articles)

    # Priority order for domains
    priority = [
        'ai',
        'ai_research',
        'ai_labs',
        'software_development',
        'software',
        'research',
        'investment',
        'community',
        'general',
    ]

    sections = []
    all_items = []

    domain_emoji = {
        'ai': '🤖',
        'ai_research': '🧠',
        'ai_labs': '🤖',
        'software_development': '💻',
        'software': '💻',
        'research': '📄',
        'investment': '💰',
        'community': '👥',
        'general': '📰',
    }

    for domain in priority:
        if domain not in by_domain:
            continue
        domain_articles = by_domain[domain]
        if not domain_articles:
            continue

        # Convert to BriefingItems
        domain_stories = articles_to_stories(domain_articles)
        domain_items = []
        for story in domain_stories[:10]:  # max 10 per section
            item = BriefingItem(
                title=story['title'],
                summary=story['summary'],
                sources=story['sources'],
                tier=story['tier'],
                entities=story['entities'],
                urgency=story['urgency'],
                url=story['url'],
                published=story['published'],
            )
            domain_items.append(item)
            all_items.append(item)

        if domain_items:
            sections.append(BriefingSection(
                name=domain.replace('_', ' ').title(),
                emoji=domain_emoji.get(domain, '📰'),
                stories=[i.to_dict() for i in domain_items]
            ))

    # Calculate metadata
    must_read_count = sum(1 for i in all_items if i.tier == 'must_read')
    important_count = sum(1 for i in all_items if i.tier == 'important')
    contextual_count = sum(1 for i in all_items if i.tier == 'contextual')

    total_words = sum(
        len(i.title.split()) + len(i.summary.split())
        for i in all_items
    )
    reading_time = max(1, total_words // 200)

    metadata = BriefingMetadata(
        generated_at=datetime.now().isoformat(),
        total_stories=len(all_items),
        must_read_count=must_read_count,
        important_count=important_count,
        contextual_count=contextual_count,
        sources_used=len(set(
            source for i in all_items for source in i.sources
        )),
        reading_time_minutes=min(reading_time, 10),
    )

    return BriefingResult(metadata=metadata, sections=sections)


def generate_newsletter_markdown(articles: list) -> str:
    """Generate markdown newsletter using the centralized renderer."""
    result = build_briefing_result(articles)
    renderer = MarkdownRenderer()
    rendered = renderer.render(result)

    # Prepend custom header with cross-source themes
    today = datetime.now().strftime('%Y-%m-%d')
    header_lines = [
        f"# High-Signal Briefing — {today}",
        "",
        f"*{len(articles)} high-signal stories from the past week*",
        "",
        "**Tier-1 Sources Only**: Distinguished engineers (Karpathy, Raschka, Huyen, Willison), top researchers (Weng, Lambert), distinguished engineers (Fowler, Luu, Ronacher), and high-signal publications (Distill, arXiv, Papers with Code)",
        "",
        "---",
        "",
    ]

    synthesis = generate_cross_source_themes_markdown(articles)
    if synthesis:
        header_lines.append(synthesis)
        header_lines.append("---")
        header_lines.append("")

    # Replace the renderer's default header with our custom header
    # The renderer produces: # 📰 Morning Briefing - <date>
    # We want to keep the rest but replace the header section
    rendered_lines = rendered.split('\n')
    # Find where the first section starts (## line)
    section_start = 0
    for i, line in enumerate(rendered_lines):
        if line.startswith('## '):
            section_start = i
            break

    # Combine custom header + rendered sections + footer
    output_lines = header_lines + rendered_lines[section_start:]

    return '\n'.join(output_lines)


def generate_newsletter_html(articles: list) -> str:
    """Generate HTML newsletter using the centralized renderer."""
    result = build_briefing_result(articles)
    renderer = HTMLRenderer()
    return renderer.render(result)


def generate_newsletter_json(articles: list) -> str:
    """Generate JSON newsletter using the centralized generator."""
    result = build_briefing_result(articles)
    return json.dumps(result.to_dict(), indent=2, ensure_ascii=False)


def generate_newsletter_text(articles: list) -> str:
    """Generate plain text newsletter using the centralized renderer."""
    result = build_briefing_result(articles)
    renderer = TextRenderer()
    return renderer.render(result)


def main():
    parser = argparse.ArgumentParser(description="Generate high-signal briefing")
    parser.add_argument(
        '--format', choices=['markdown', 'html', 'json', 'text', 'all'],
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
    if args.format == 'all':
        formats_to_generate = ['markdown', 'html', 'json']
    else:
        formats_to_generate = [args.format]

    generated = generate_briefing_files(filtered, args.output_dir, formats_to_generate)

    print(f"\nTotal articles included: {len(filtered)}")
    print(f"Files generated: {len(generated)}")


if __name__ == '__main__':
    main()
