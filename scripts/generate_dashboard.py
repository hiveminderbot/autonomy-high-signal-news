#!/usr/bin/env python3
"""
Convert high-signal-news markdown briefings to a static HTML dashboard.
Usage: python scripts/generate_dashboard.py [input_md] [output_dir]
"""
import sys, os, re, json, datetime

def md_to_html(md_text):
    """Minimal markdown-to-HTML converter for briefings."""
    lines = md_text.splitlines()
    html = []
    in_list = False
    in_blockquote = False
    for line in lines:
        stripped = line.strip()
        # Headers
        if stripped.startswith('# '):
            html.append(f'<h1>{stripped[2:]}</h1>')
            continue
        if stripped.startswith('## '):
            html.append(f'<h2>{stripped[3:]}</h2>')
            continue
        if stripped.startswith('### '):
            html.append(f'<h3>{stripped[4:]}</h3>')
            continue
        # Horizontal rule
        if stripped == '---':
            html.append('<hr>')
            continue
        # Blockquote
        if stripped.startswith('>'):
            if not in_blockquote:
                html.append('<blockquote>')
                in_blockquote = True
            html.append(stripped[1:].strip() + '<br>')
            continue
        else:
            if in_blockquote:
                html.append('</blockquote>')
                in_blockquote = False
        # List items
        if stripped.startswith('- ') or stripped.startswith('* '):
            if not in_list:
                html.append('<ul>')
                in_list = True
            item = stripped[2:]
            item = re.sub(r'\[(.*?)\]\((.*?)\)', r'<a href="\2" target="_blank">\1</a>', item)
            html.append(f'<li>{item}</li>')
            continue
        else:
            if in_list:
                html.append('</ul>')
                in_list = False
        # Table rows
        if stripped.startswith('|') and not stripped.startswith('|---'):
            cells = [c.strip() for c in stripped.split('|')[1:-1]]
            if cells:
                tag = 'th' if html and '<table>' not in html[-10:] and 'h1' in html[-1] else 'td'
                row = ''.join(f'<{tag}>{c}</{tag}>' for c in cells)
                if '<table>' not in html[-10:]:
                    html.append('<table>')
                html.append(f'<tr>{row}</tr>')
            continue
        else:
            if '<table>' in ''.join(html[-3:]):
                html.append('</table>')
        # Bold / links
        line = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', stripped)
        line = re.sub(r'\[(.*?)\]\((.*?)\)', r'<a href="\2" target="_blank">\1</a>', line)
        line = re.sub(r'🔥|⭐|📊|📈|🎯|🤖|💻|💰|🔍|✅|⚠️|❌', lambda m: m.group(0), line)
        if line:
            html.append(f'<p>{line}</p>')
    if in_list:
        html.append('</ul>')
    if in_blockquote:
        html.append('</blockquote>')
    if '<table>' in ''.join(html[-3:]):
        html.append('</table>')
    return '\n'.join(html)

def generate_dashboard(input_md, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    with open(input_md, 'r', encoding='utf-8') as f:
        md_text = f.read()
    body = md_to_html(md_text)
    # Extract title from first h1
    title_match = re.search(r'<h1>(.*?)</h1>', body)
    title = title_match.group(1) if title_match else 'High-Signal News Dashboard'
    # Count stories
    story_count = len(re.findall(r'<h2>', body))
    now = datetime.datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')
    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
:root {{ --bg:#0d1117; --fg:#c9d1d9; --accent:#58a6ff; --muted:#8b949e; --card:#161b22; --border:#30363d; }}
body {{ font-family: -apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif; background:var(--bg); color:var(--fg); max-width:900px; margin:0 auto; padding:2rem; line-height:1.6; }}
h1 {{ color:#f0f6fc; border-bottom:2px solid var(--accent); padding-bottom:.5rem; }}
h2 {{ color:var(--accent); margin-top:2rem; }}
h3 {{ color:#79c0ff; }}
a {{ color:var(--accent); text-decoration:none; }}
a:hover {{ text-decoration:underline; }}
blockquote {{ border-left:4px solid var(--accent); padding-left:1rem; color:var(--muted); margin:1rem 0; }}
table {{ width:100%; border-collapse:collapse; margin:1rem 0; }}
th,td {{ padding:.5rem; border:1px solid var(--border); text-align:left; }}
th {{ background:var(--card); color:#f0f6fc; }}
ul {{ padding-left:1.5rem; }}
li {{ margin:.3rem 0; }}
hr {{ border:none; border-top:1px solid var(--border); margin:2rem 0; }}
.meta {{ color:var(--muted); font-size:.85rem; margin-top:2rem; border-top:1px solid var(--border); padding-top:1rem; }}
.story-count {{ background:var(--card); padding:.5rem 1rem; border-radius:6px; display:inline-block; margin-bottom:1rem; border:1px solid var(--border); }}
</style>
</head>
<body>
<div class="story-count">📰 Stories: <strong>{story_count}</strong> | Generated: {now}</div>
{body}
<div class="meta">
<p>Dashboard auto-generated from <a href="https://github.com/hiveminderbot/autonomy-high-signal-news">high-signal-news</a> pipeline.</p>
</div>
</body>
</html>'''
    out_path = os.path.join(output_dir, 'index.html')
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html)
    return out_path, story_count

if __name__ == '__main__':
    input_md = sys.argv[1] if len(sys.argv) > 1 else 'output/briefing-2026-03-21-REAL.md'
    output_dir = sys.argv[2] if len(sys.argv) > 2 else 'dashboard'
    out_path, story_count = generate_dashboard(input_md, output_dir)
    print(f'Generated {out_path} with {story_count} stories.')
