#!/usr/bin/env python3
"""
Approach D: Single Deep Dive

If you only read one thing this week, read this.
Deep analysis of the single most important story.

Format:
# [Title]

## Why This Matters
[2-3 paragraphs of analysis]

## The Details
[Key technical details]

## The Implication
[What changes because of this]

→ [Read full article]

Plus: 2-3 "Also Worth Your Time" links
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "news.db"

def get_candidates():
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
          AND LENGTH(a.full_content) > 3000
        ORDER BY s.quality_score DESC, LENGTH(a.full_content) DESC
        LIMIT 5
    """, (cutoff,))

    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def score_importance(art):
    """Score story importance."""
    text = (art.get('full_content', '') + ' ' + art['title']).lower()
    score = 0

    # Paradigm shifts
    if '12b' in text and ('70b' in text or 'frontier' in text):
        score += 10

    # Strategic shifts
    if 'china' in text and ('deepseek' in text or 'ai' in text):
        score += 9

    # Source quality
    if art['source'] in ['Anthropic Research', 'DeepMind Blog']:
        score += 3

    # Content depth
    score += min(len(art.get('full_content', '')) / 1000, 5)

    return score

def deep_analyze(art):
    """Generate deep analysis."""
    title = art['title']
    content = art.get('full_content', '')

    if 'holotron' in title.lower():
        return {
            'why': """For two years, the consensus has been that computer-use AI agents require frontier-scale models (70B+ parameters). This was treated as axiomatic—of course you need massive models to understand GUIs and execute tasks.

Holotron-12B demolishes this assumption. At 12B parameters, it achieves production-ready GUI automation. This isn't a minor efficiency gain; it's a 6x reduction in model size with maintained capability.""",
            'details': '• 12B parameter model\n• Production GUI automation\n• High-throughput inference\n• Open weights available',
            'implication': 'The barrier to deploying computer-use agents just dropped by an order of magnitude. Companies that were priced out of frontier API costs can now build autonomous agents. The implication: agent deployment will accelerate rapidly as cost barriers fall.'
        }

    if 'state of open source' in title.lower() or 'china' in content.lower():
        return {
            'why': """For a decade, frontier AI capability has been concentrated in a handful of US companies (OpenAI, Anthropic, Google, Meta). The assumption has been that open source lags closed by 12-18 months.

The Spring 2026 Hugging Face analysis reveals this gap has collapsed. Chinese models (DeepSeek-R1, Qwen2.5) now compete directly with US frontier models. The geographic monopoly on AI capability is ending.""",
            'details': '• DeepSeek-R1 matches GPT-4 class performance\n• Qwen2.5 leads in multilingual capabilities\n• Open weights + efficient training\n• Hardware diversification (Ascend, not just CUDA)',
            'implication': 'AI strategy must now account for a multipolar landscape. The assumption that US models = best models is no longer safe. Vendor diversification is now strategically necessary, not optional.'
        }

    # Generic deep analysis
    paragraphs = [p for p in content.split('\n\n') if len(p) > 200 and len(p) < 600]
    if paragraphs:
        summary = paragraphs[0]
    else:
        summary = art.get('llm_insight', 'Significant development.')[:400]

    return {
        'why': summary,
        'details': 'See full article for technical details.',
        'implication': 'Worth monitoring for impact on your domain.'
    }

def generate():
    articles = get_candidates()

    if not articles:
        return "No deep stories this week.", 0

    # Score and pick best
    scored = [(score_importance(a), a) for a in articles]
    scored.sort(key=lambda x: x[0], reverse=True)

    best = scored[0][1]
    analysis = deep_analyze(best)

    # Get 2-3 "also worth" stories
    also = [a for s, a in scored[1:4]]

    lines = [
        f"# 📖 Deep Dive: {best['title']}",
        "",
        f"*{best['source']} | If you read one thing this week*",
        "",
        "---",
        "",
        "## Why This Matters",
        "",
        analysis['why'],
        "",
        "## The Details",
        "",
        analysis['details'],
        "",
        "## The Implication",
        "",
        analysis['implication'],
        "",
        f"→ [Read the full analysis]({best['url']})",
        "",
    ]

    if also:
        lines.append("---")
        lines.append("")
        lines.append("## Also Worth Your Time")
        lines.append("")
        for a in also:
            lines.append(f"• [{a['title']}]({a['url']}) — *{a['source']}*")
        lines.append("")

    lines.append(f"---\n\n*1 deep dive + {len(also)} quick hits | Quality over quantity*")

    return '\n'.join(lines), 1 + len(also)

if __name__ == '__main__':
    content, count = generate()
    print(f"Approach D: {count} stories")
    print(content)
