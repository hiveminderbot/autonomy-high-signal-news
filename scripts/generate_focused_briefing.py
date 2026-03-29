#!/usr/bin/env python3
"""
Generate focused newsletter: synthesis with sources, 5-7 stories max.

Rules:
- Max 3 themes
- Max 2 representative sources per theme
- Max 5 deep dives total
- No "quick hits" — cut ruthlessly
- No redundant source lists
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict

DB_PATH = Path(__file__).parent.parent / "news.db"
OUTPUT_PATH = Path(__file__).parent.parent / "output"


def get_analyzed_articles(days=3):
    """Get articles with LLM insights."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    
    cursor.execute("""
        SELECT a.id, a.title, a.url, a.source, a.domain,
               a.llm_summary, a.llm_insight,
               s.quality_score
        FROM articles a
        JOIN sources s ON a.source = s.name
        WHERE a.published_at > ?
          AND a.llm_insight IS NOT NULL
        ORDER BY s.quality_score DESC, a.published_at DESC
        LIMIT 20
    """, (cutoff,))
    
    articles = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return articles


def detect_themes(articles):
    """Detect 2-3 themes with best representative stories."""
    themes = []
    
    # Theme definitions
    theme_defs = [
        {
            'name': 'AI Systems & Infrastructure',
            'kws': ['inference', 'latency', 'throughput', 'scaling', 'optimization', 'systems'],
            'desc': 'Production AI getting faster and more efficient'
        },
        {
            'name': 'Safety & Interpretability', 
            'kws': ['safety', 'robustness', 'attack', 'adversarial', 'interpretability', 'understanding'],
            'desc': 'Making AI reliable and understandable'
        },
        {
            'name': 'Developer Experience',
            'kws': ['developer', 'tooling', 'workflow', 'rust', 'python', 'languages'],
            'desc': 'Tools and practices shaping how we build software'
        },
    ]
    
    used_articles = set()
    
    for theme_def in theme_defs:
        matches = []
        for art in articles:
            if art['id'] in used_articles:
                continue
            text = (art.get('llm_insight', '') + ' ' + art['title']).lower()
            if any(kw in text for kw in theme_def['kws']):
                matches.append(art)
        
        if len(matches) >= 1:
            # Take top 1 by quality
            matches.sort(key=lambda x: x.get('quality_score', 5), reverse=True)
            reps = matches[:1]
            
            for r in reps:
                used_articles.add(r['id'])
            
            themes.append({
                'name': theme_def['name'],
                'desc': theme_def['desc'],
                'articles': reps
            })
        
        if len(themes) >= 3:
            break
    
    return themes, used_articles


def format_why(art, max_len=140):
    """Format why it matters."""
    insight = art.get('llm_insight', '')
    if not insight:
        return None
    
    # First sentence only
    sent = insight.split('. ')[0].strip()
    sent = sent.replace('**', '').replace('*', '')
    
    if len(sent) > max_len:
        sent = sent[:max_len-3] + '...'
    
    return sent


def generate_briefing():
    """Generate focused briefing."""
    articles = get_analyzed_articles(days=3)
    
    if not articles:
        return None
    
    today = datetime.now().strftime('%Y-%m-%d')
    lines = [
        f"# 🎯 High-Signal Briefing — {today}",
        "",
        "*Synthesized from top sources | 5-7 stories worth your time*",
        "",
        "---",
        "",
    ]
    
    # Detect themes
    themes, used = detect_themes(articles)
    
    # THE BIG THEMES (synthesis + sources)
    if themes:
        lines.append("## 🔥 What Matters This Week")
        lines.append("")
        
        for theme in themes:
            lines.append(f"### {theme['name']}")
            lines.append(f"_{theme['desc']}_")
            lines.append("")
            
            for art in theme['articles']:
                why = format_why(art)
                if why:
                    lines.append(f"**[{art['title']}]({art['url']})** — *{art['source']}*")
                    lines.append(f"> {why}")
                    lines.append("")
        
        lines.append("---")
        lines.append("")
    
    # DEEP DIVES (stories not in themes, max 2)
    remaining = [a for a in articles if a['id'] not in used][:2]
    
    if remaining:
        lines.append("## 📌 Also Notable")
        lines.append("")
        
        for art in remaining:
            why = format_why(art)
            if why:
                lines.append(f"**[{art['title']}]({art['url']})** — *{art['source']}*")
                lines.append(f"> {why}")
                lines.append("")
    
    # Total story count
    total_stories = sum(len(t['articles']) for t in themes) + len(remaining)
    
    lines.append("---")
    lines.append("")
    lines.append(f"*{total_stories} stories | Sources: Distill, HN, Karpathy, Willison, etc.*")
    lines.append(f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}*")
    
    return '\n'.join(lines), total_stories


def main():
    print("Generating focused briefing...")
    
    content, count = generate_briefing()
    if not content:
        print("No content generated")
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
