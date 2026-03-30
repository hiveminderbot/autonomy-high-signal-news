#!/usr/bin/env python3
"""
Approach C: Action-Oriented

What should you DO differently after reading this?

Format:
## Do This: [Action]
[Why it matters - 2 sentences]
→ [Link]

## Stop Doing This: [Action]
[Why - 2 sentences]
→ [Link]

## Watch For: [Trend]
[What to monitor]
→ [Link]

Max 5 actions.
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "news.db"

def get_actionable():
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
        LIMIT 15
    """, (cutoff,))
    
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def classify_action(art):
    """Classify what action this suggests."""
    text = (art.get('full_content', '') + ' ' + art['title']).lower()
    
    # Start doing
    if 'holotron' in text or 'computer use' in text:
        return ('start', 'Deploy smaller GUI automation models', 
                '12B models are now sufficient for production GUI automation. You can deploy computer-use agents at 10x lower cost than frontier APIs.')
    
    if 'china' in text or 'deepseek' in text:
        return ('start', 'Evaluate non-US open source models', 
                'Chinese models (DeepSeek, Qwen) have reached frontier parity. Diversifying your model providers reduces vendor lock-in and cost.')
    
    # Stop doing
    if '70b' in text and ('gui' in text or 'automation' in text):
        return ('stop', 'Defaulting to frontier models for simple tasks',
                'Over-provisioning compute for tasks that smaller models handle fine. Audit your API usage for overkill.')
    
    # Watch for
    if 'rl' in text and ('library' in text or 'training' in text):
        return ('watch', 'Async RL training becoming standard',
                'The field is consolidating on async training patterns. If you\'re doing RL, ensure your stack supports it.')
    
    return None

def generate():
    articles = get_actionable()
    
    actions = []
    for a in articles:
        action = classify_action(a)
        if action:
            actions.append((action, a))
    
    # Deduplicate
    seen = set()
    unique = []
    for (atype, title, why), art in actions:
        if title not in seen:
            seen.add(title)
            unique.append((atype, title, why, art))
    
    if not unique:
        return "No clear actions this week.", 0
    
    lines = [
        "# ⚡ Action Briefing",
        "",
        f"*{len(unique)} things to change based on this week's signals*",
        "",
        "---",
        "",
    ]
    
    for atype, title, why, art in unique[:5]:
        emoji = {'start': '✅', 'stop': '❌', 'watch': '👀'}.get(atype, '•')
        lines.append(f"## {emoji} {title}")
        lines.append("")
        lines.append(why)
        lines.append(f"→ [{art['title']}]({art['url']})")
        lines.append("")
    
    lines.append(f"---\n\n*{len(unique[:5])} actions | Practitioner-focused*")
    
    return '\n'.join(lines), len(unique[:5])

if __name__ == '__main__':
    content, count = generate()
    print(f"Approach C: {count} actions")
    print(content)
