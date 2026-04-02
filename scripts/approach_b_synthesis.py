#!/usr/bin/env python3
"""
Approach B: Synthesis-Based

Don't categorize by domain (AI/Software/etc).
Find cross-domain patterns and tell the story.

Format:
## The Pattern: [Pattern Name]
[3-4 sentences explaining the pattern across domains]

- [Story 1 with link]
- [Story 2 with link]
- [Story 3 with link]

## The Counter-Signal: [Opposite trend]
...

Max 2 patterns, 3 stories each.
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "news.db"

def get_recent():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cutoff = (datetime.now() - timedelta(days=7)).isoformat()

    cursor.execute("""
        SELECT a.title, a.url, a.source, a.full_content, a.llm_insight
        FROM articles a
        JOIN sources s ON a.source = s.name
        WHERE a.published_at > ?
          AND a.extraction_status = 'extracted'
          AND a.full_content IS NOT NULL
          AND s.name NOT IN ('This Week in Rust', 'JavaScript Weekly')
        ORDER BY s.quality_score DESC
        LIMIT 20
    """, (cutoff,))

    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def find_patterns(articles):
    """Find cross-cutting patterns."""

    # Pattern 1: Efficiency over scale
    efficiency = []
    for a in articles:
        text = (a.get('full_content', '') + a['title']).lower()
        if any(x in text for x in ['12b', 'small model', 'efficient', 'throughput', 'latency']):
            if any(x in text for x in ['70b', 'large', 'gpt-4', 'frontier']):
                efficiency.append(a)

    # Pattern 2: Geographic diversification
    geo = []
    for a in articles:
        text = (a.get('full_content', '') + a['title']).lower()
        if any(x in text for x in ['china', 'deepseek', 'qwen', 'europe', 'open source']):
            geo.append(a)

    # Pattern 3: Systems moving to edge/local
    edge = []
    for a in articles:
        text = (a.get('full_content', '') + a['title']).lower()
        if any(x in text for x in ['local', 'edge', 'on-device', 'offline', 'tinybox']):
            edge.append(a)

    patterns = []

    if len(efficiency) >= 2:
        patterns.append({
            'name': 'Efficiency Beats Scale',
            'thesis': 'The assumption that bigger is better is being challenged. Production deployments are optimizing for cost and latency over raw capability. The 70B+ parameter era may be plateauing as practitioners discover smaller, specialized models outperform general-purpose giants on real tasks.',
            'stories': efficiency[:3]
        })

    if len(geo) >= 2:
        patterns.append({
            'name': 'The Geographic Decentering of AI',
            'thesis': 'Frontier AI capability is no longer a US-only story. China\'s open source ecosystem has reached functional parity, and European initiatives are gaining traction. The strategic implication: AI dominance will be distributed, not centralized.',
            'stories': geo[:3]
        })

    return patterns

def generate():
    articles = get_recent()
    patterns = find_patterns(articles)

    if not patterns:
        return "No clear patterns emerged this week.", 0

    lines = [
        "# 🕸️ Pattern Briefing",
        "",
        f"*{len(patterns)} cross-domain patterns worth understanding*",
        "",
        "---",
        "",
    ]

    for p in patterns:
        lines.append(f"## {p['name']}")
        lines.append("")
        lines.append(p['thesis'])
        lines.append("")
        lines.append("**Evidence:**")
        for s in p['stories']:
            lines.append(f"- [{s['title']}]({s['url']}) — *{s['source']}*")
        lines.append("")

    total = sum(len(p['stories']) for p in patterns)
    lines.append(f"---\n\n*{total} stories | Connected across domains*")

    return '\n'.join(lines), total

if __name__ == '__main__':
    content, count = generate()
    print(f"Approach B: {count} stories")
    print(content)
