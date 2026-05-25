#!/usr/bin/env python3
"""Simple markdown-to-HTML converter for briefing deployment."""
import re
import sys

def convert(md_path, html_path):
    with open(md_path) as f:
        md_text = f.read()
    stories = len(re.findall(r'^### ', md_text, re.MULTILINE))
    urls = set(re.findall(r'https?://[^\s\)\"\'\>\<\]]+', md_text))

    html = md_text
    html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
    html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
    html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
    html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
    html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)
    html = re.sub(r'\[([^\]]+)\]\(([^\)]+)\)', r'<a href="\2">\1</a>', html)
    html = re.sub(r'^---$', r'<hr>', html, flags=re.MULTILINE)
    html = '<br>\n'.join(html.split('\n'))

    with open(html_path, 'w') as f:
        f.write(f'''<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>High-Signal Briefing - 2026-05-25</title><style>
body {{ font-family: system-ui, sans-serif; max-width: 900px; margin: 0 auto; padding: 2rem; line-height: 1.6; }}
h1 {{ border-bottom: 2px solid #333; padding-bottom: 0.5rem; }}
h2 {{ color: #444; margin-top: 2rem; }}
h3 {{ color: #555; }}
a {{ color: #0066cc; }}
.meta {{ color: #666; font-size: 0.9rem; }}
</style></head><body>
{html}
<hr><p class="meta">Generated: 2026-05-25 | {stories} stories | {len(urls)} unique sources</p>
</body></html>''')
    print(f'Generated {html_path} with {stories} stories and {len(urls)} URLs')

if __name__ == '__main__':
    convert(sys.argv[1], sys.argv[2])
