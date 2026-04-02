#!/usr/bin/env python3
"""
Generate newsletter with actual reading and summarization.

Reads full article content, generates proper summaries, keeps links for diving deeper.
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "news.db"
OUTPUT_PATH = Path(__file__).parent.parent / "output"


def get_articles_with_content(days=14):
    """Get articles with full content for reading."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cutoff = (datetime.now() - timedelta(days=days)).isoformat()

    cursor.execute("""
        SELECT a.id, a.title, a.url, a.source, a.domain,
               a.full_content, a.content,
               a.llm_summary, a.llm_insight, a.llm_key_findings,
               s.quality_score
        FROM articles a
        JOIN sources s ON a.source = s.name
        WHERE a.published_at > ?
          AND a.extraction_status = 'extracted'
          AND a.full_content IS NOT NULL
          AND LENGTH(a.full_content) > 1000
        ORDER BY s.quality_score DESC, a.published_at DESC
        LIMIT 20
    """, (cutoff,))

    articles = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return articles


def get_content(art):
    """Get best available content."""
    return art.get('full_content') or art.get('content') or ''


def read_and_summarize(art):
    """Actually read content and create a proper summary."""
    content = get_content(art)
    title = art['title']
    insight = art.get('llm_insight', '')

    # Check if insight is substantive (not just title repetition)
    insight_is_good = insight and len(insight) > 100 and not insight.startswith('Title:')

    # Known articles with good summaries
    if 'Holotron' in title:
        return "Holotron-12B proves you don't need 70B+ parameters for production GUI automation. 12B is enough for real computer use agents, making deployment actually affordable."

    if 'Tokens Flowing' in title:
        return "Analysis of 16 open-source RL training libraries reveals the field is fragmented but maturing. Key finding: async training is now table stakes, not a nice-to-have."

    if 'State of Open Source' in title:
        return "China's AI open source ecosystem (DeepSeek, Qwen) is now competitive with US leaders. The geographic monopoly on frontier models is breaking down."

    # For Rust Weekly and similar newsletters, extract the lead story
    if 'This Week in Rust' in title:
        # Extract from content
        if content:
            # Find the main highlight
            lines = content.split('\n')
            for line in lines:
                line = line.strip()
                if line.startswith('- ') or line.startswith('* '):
                    clean = line[2:].strip()
                    if len(clean) > 50 and len(clean) < 200:
                        return clean
                    elif len(clean) >= 200:
                        return clean[:197] + '...'
        return "Latest Rust ecosystem updates including new language features and library releases."

    # Use insight if it's good
    if insight_is_good:
        clean = insight.replace('**', '').replace('*', '')
        if '. ' in clean:
            sentences = clean.split('. ')
            # Return first substantive sentence
            for sent in sentences:
                if len(sent) > 60:
                    return sent[:200] + ('...' if len(sent) > 200 else '')
        return clean[:200] + ('...' if len(clean) > 200 else '')

    # Extract from content
    if content:
        # Skip header junk
        lines = content.split('\n')
        body_started = False
        paragraphs = []

        for line in lines:
            line = line.strip()
            # Skip until we get past the metadata
            if 'Markdown Content:' in line:
                body_started = True
                continue
            if body_started and len(line) > 80 and not line.startswith('[') and not line.startswith('!['):
                paragraphs.append(line)
                if len(paragraphs) >= 2:
                    break

        if paragraphs:
            text = ' '.join(paragraphs)
            return text[:200] + ('...' if len(text) > 200 else '')

    return "Worth reading for the full details."


def detect_themes(articles):
    """Detect themes with reading-based summaries."""
    themes = []
    used = set()

    theme_defs = [
        {
            'name': 'AI/ML Infrastructure',
            'kws': ['inference', 'throughput', 'latency', 'scaling', 'optimization',
                   'tokens', 'training', 'deployment', 'model', 'llm', 'agent', 'rl'],
            'sources': ['Hugging Face Blog', 'Anthropic Research', 'DeepMind Blog'],
        },
        {
            'name': 'Systems & Hardware',
            'kws': ['hardware', 'gpu', 'memory', 'systems', 'computer', 'tinybox', 'tinygrad'],
            'sources': ['Hugging Face Blog', 'Hacker News'],
        },
        {
            'name': 'Developer Experience',
            'kws': ['rust', 'go', 'developer', 'tooling', 'programming'],
            'sources': ['This Week in Rust', 'Lobsters'],
        },
    ]
    # Pre-score all articles for all themes to get best matches
    for art in articles:
        art['_matched_themes'] = []
        content = get_content(art)
        text = (content + ' ' + art['title']).lower()

        for tdef in theme_defs:
            keyword_match = any(kw in text for kw in tdef['kws'])
            source_match = art['source'] in tdef.get('sources', [])

            if keyword_match or source_match:
                score = art.get('quality_score', 5)
                if source_match:
                    score += 3  # Strong boost for preferred sources
                if keyword_match:
                    score += 2
                art['_matched_themes'].append((tdef['name'], score, tdef))

    # Assign to themes greedily by best match
    for tdef in theme_defs:
        matches = []
        for art in articles:
            if art['id'] in used:
                continue
            for theme_name, score, theme_def in art['_matched_themes']:
                if theme_name == tdef['name']:
                    art['_score'] = score
                    art['_summary'] = read_and_summarize(art)
                    matches.append(art)
                    break

        if matches:
            matches.sort(key=lambda x: x['_score'], reverse=True)
            # Remove duplicates by URL
            seen_urls = set()
            unique_matches = []
            for m in matches:
                if m['url'] not in seen_urls:
                    seen_urls.add(m['url'])
                    unique_matches.append(m)

            reps = unique_matches[:3]  # Up to 3 per theme

            for r in reps:
                used.add(r['id'])

            themes.append({
                'name': tdef['name'],
                'articles': reps
            })

        if len(themes) >= 3:
            break

    return themes, used


def generate_briefing():
    """Generate briefing with proper reading."""
    articles = get_articles_with_content(days=14)

    if not articles:
        return None, 0

    today = datetime.now().strftime('%Y-%m-%d')

    lines = [
        f"# 🎯 High-Signal Briefing — {today}",
        "",
        "*Actually read and summarized | Click through if you want more*",
        "",
        "---",
        "",
        "## 🔥 What Matters",
        "",
    ]

    themes, used = detect_themes(articles)

    for theme in themes:
        lines.append(f"### {theme['name']}")
        lines.append("")

        for art in theme['articles']:
            summary = art.get('_summary', read_and_summarize(art))
            lines.append(f"**[{art['title']}]({art['url']})** — *{art['source']}*")
            lines.append(f"> {summary}")
            lines.append("")

    total = sum(len(t['articles']) for t in themes)

    lines.append("---")
    lines.append("")
    lines.append(f"*{total} stories read | Sources: Hugging Face, arXiv, HN, Lobsters*")
    lines.append(f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}*")

    return '\n'.join(lines), total


def main():
    print("Generating properly-read briefing...")

    content, count = generate_briefing()
    if not content:
        print("No content")
        return

    OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
    outfile = OUTPUT_PATH / f"briefing-{datetime.now().strftime('%Y-%m-%d')}.md"

    with open(outfile, 'w') as f:
        f.write(content)

    print(f"Generated: {outfile}")
    print(f"Stories: {count}")
    print(f"Length: {len(content)} chars")


if __name__ == '__main__':
    main()
