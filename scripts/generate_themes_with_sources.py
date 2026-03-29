#!/usr/bin/env python3
"""
Generate newsletter: Big Themes with sources.

Format:
## 🔥 The Big Themes

### Theme Name
_Theme description_

**[Story Title](URL)** — *Source*
> Why it matters (insight)

**[Story Title](URL)** — *Source*  
> Why it matters (insight)

3 themes max, 2-3 stories per theme.
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "news.db"
OUTPUT_PATH = Path(__file__).parent.parent / "output"


def get_recent_articles(days=14):
    """Get recent articles with insights."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    
    cursor.execute("""
        SELECT a.id, a.title, a.url, a.source, a.domain,
               a.llm_insight, a.llm_summary,
               s.quality_score
        FROM articles a
        JOIN sources s ON a.source = s.name
        WHERE a.published_at > ?
          AND a.extraction_status = 'extracted'
          AND (a.llm_insight IS NOT NULL OR a.llm_summary IS NOT NULL)
        ORDER BY s.quality_score DESC, a.published_at DESC
        LIMIT 30
    """, (cutoff,))
    
    articles = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return articles


def get_insight(art):
    """Get insight text."""
    return art.get('llm_insight') or art.get('llm_summary', '')


def detect_themes(articles):
    """Detect themes with representative stories."""
    themes = []
    used = set()
    
    theme_defs = [
        {
            'name': 'AI/ML Infrastructure',
            'kws': ['inference', 'throughput', 'latency', 'scaling', 'optimization', 
                   'efficiency', 'tokens', 'training', 'deployment', 'model', 'llm', 'agent'],
            'sources': ['Hugging Face Blog', 'Anthropic Research', 'DeepMind Blog', 'OpenAI Blog', 
                       'arXiv cs.AI', 'arXiv cs.LG', 'Import AI', 'The Batch'],
            'desc': 'Production AI systems getting faster, leaner, and more cost-effective'
        },
        {
            'name': 'Safety & Alignment',
            'kws': ['safety', 'alignment', 'robustness', 'attack', 'adversarial',
                   'vulnerability', 'reliable', 'interpretability'],
            'sources': ['Anthropic Research', 'DeepMind Blog', 'AI Alignment Forum', 'Lilian Weng'],
            'desc': 'Building AI that fails gracefully and resists manipulation'
        },
        {
            'name': 'Hardware & Systems',
            'kws': ['hardware', 'gpu', 'cpu', 'memory', 'distributed', 'systems',
                   'infrastructure', 'computer use'],
            'sources': ['Hugging Face Blog', 'Hacker News', 'Lobsters'],
            'desc': 'The plumbing that makes modern AI possible'
        },
    ]
    
    for tdef in theme_defs:
        matches = []
        for art in articles:
            if art['id'] in used:
                continue
            text = (get_insight(art) + ' ' + art['title']).lower()
            
            # Check keyword match
            keyword_match = any(kw in text for kw in tdef['kws'])
            
            # Check source match (prioritize AI sources)
            source_match = art['source'] in tdef.get('sources', [])
            
            # Require keyword match, boost if source also matches
            if keyword_match:
                art['_score'] = art.get('quality_score', 5)
                if source_match:
                    art['_score'] += 3  # Boost for preferred sources
                matches.append(art)
        
        if len(matches) >= 1:
            matches.sort(key=lambda x: x['_score'], reverse=True)
            reps = matches[:2]  # Max 2 per theme
            
            for r in reps:
                used.add(r['id'])
            
            themes.append({
                'name': tdef['name'],
                'desc': tdef['desc'],
                'articles': reps
            })
        
        if len(themes) >= 3:
            break
    
    return themes, used


def format_why(art, max_len=130):
    """Format why it matters."""
    insight = get_insight(art)
    if not insight:
        return None
    
    # First sentence, clean
    sent = insight.split('. ')[0].strip()
    sent = sent.replace('**', '').replace('*', '')
    
    if len(sent) > max_len:
        sent = sent[:max_len-3] + '...'
    
    return sent


def generate_briefing():
    """Generate themes with sources briefing."""
    articles = get_recent_articles(days=2)
    
    if not articles:
        return None, 0
    
    today = datetime.now().strftime('%Y-%m-%d')
    
    lines = [
        f"# 🎯 High-Signal Briefing — {today}",
        "",
        f"*{len(articles)} recent stories analyzed | Top themes with sources*",
        "",
        "---",
        "",
        "## 🔥 The Big Themes",
        "",
        "*Patterns across sources worth your attention:*",
        "",
    ]
    
    themes, used = detect_themes(articles)
    
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
    
    # Count total
    total = sum(len(t['articles']) for t in themes)
    
    lines.append("---")
    lines.append("")
    lines.append(f"*{total} stories | Sources: HN, Lobsters, Hugging Face, arXiv, individual blogs*")
    lines.append(f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M UTC')}*")
    
    return '\n'.join(lines), total


def main():
    print("Generating themes with sources...")
    
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
