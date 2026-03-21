#!/usr/bin/env python3
"""
Insight Newsletter Generator

Fetches full content from top articles, uses AI to extract insight,
groups by topic, and explains why things matter.
"""

import sqlite3
import sys
import os
import json
from datetime import datetime
from urllib.parse import urlparse

# Import existing extractors
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from aggregator.content_extractor import ContentExtractor
from summarizer.content_summarizer import ContentSummarizer

DB_PATH = 'news.db'
OUTPUT_PATH = 'output/insight-newsletter-2026-03-21.md'

# Skip sites that are paywalled or block scraping
SKIP_DOMAINS = {'bloomberg.com', 'ft.com', 'wsj.com', 'nytimes.com', 'theinformation.com'}


def should_skip_url(url):
    """Check if URL is from a problematic domain."""
    domain = urlparse(url).netloc.lower()
    for skip in SKIP_DOMAINS:
        if skip in domain:
            return True
    return False


def get_top_articles(conn, limit=15):
    """Get top articles that are worth analyzing."""
    cursor = conn.execute('''
        SELECT title, url, source, domain, content, published_at
        FROM articles
        WHERE source IN ('Hacker News', 'Lobsters', 'Distill.pub', 'Hugging Face Blog', 
                         'This Week in Rust', 'JavaScript Weekly')
        ORDER BY 
            CASE source
                WHEN 'Distill.pub' THEN 10
                WHEN 'Hugging Face Blog' THEN 9
                WHEN 'This Week in Rust' THEN 8
                WHEN 'JavaScript Weekly' THEN 7
                WHEN 'Hacker News' THEN 6
                WHEN 'Lobsters' THEN 5
                ELSE 1
            END DESC,
            fetched_at DESC
        LIMIT ?
    ''', (limit,))
    return cursor.fetchall()


def fetch_full_content(url):
    """Fetch full article content."""
    if should_skip_url(url):
        return None, "Paywalled/skipped domain"
    
    try:
        extractor = ContentExtractor()
        result = extractor.extract(url)
        if result.extraction_error:
            return None, result.extraction_error
        return result.content_text[:5000], None  # Limit to 5k chars
    except Exception as e:
        return None, str(e)


def generate_ai_summary(title, content, source):
    """Generate an insightful summary using AI-style analysis."""
    # For now, use extractive + add context
    # In production, this would call Claude API
    
    summarizer = ContentSummarizer(max_sentences=2)
    summary_result = summarizer.summarize(content, title)
    
    # Add source-specific context
    context = ""
    if source == "Distill.pub":
        context = "Research insight:"
    elif source == "Hugging Face Blog":
        context = "AI tooling update:"
    elif source == "Hacker News":
        context = "Community discussion:"
    elif source == "This Week in Rust":
        context = "Rust ecosystem:"
    
    return f"{context} {summary_result.summary}"


def categorize_article(title, content, source):
    """Categorize article by topic."""
    title_lower = title.lower()
    content_lower = content.lower()[:1000]
    
    # Topic detection
    if any(w in title_lower for w in ['llm', 'gpt', 'claude', 'model', 'training', 'ai safety', 'alignment']):
        return '🤖 AI Research'
    if any(w in title_lower for w in ['rust', 'cargo', 'wasm', 'async']):
        return '⚙️ Rust & Systems'
    if any(w in title_lower for w in ['javascript', 'typescript', 'react', 'node']):
        return '🌐 Web Development'
    if any(w in title_lower for w in ['embeddings', 'fine-tune', 'inference', 'deployment']):
        return '🚀 AI Engineering'
    if any(w in title_lower for w in ['database', 'graph', 'sql', 'storage']):
        return '🗄️ Data & Storage'
    if any(w in title_lower for w in ['security', 'vulnerability', 'crypto', 'privacy']):
        return '🔒 Security'
    if source == 'Distill.pub':
        return '🔬 Deep Research'
    if source in ['Hacker News', 'Lobsters']:
        return '💡 Tech Discussion'
    
    return '📰 General Tech'


def generate_insight_newsletter(articles_with_content):
    """Generate newsletter with actual insight."""
    lines = [
        "# High-Signal Insight Newsletter",
        "",
        f"*Analysis of {len(articles_with_content)} significant stories | {datetime.now().strftime('%B %d, %Y')}*",
        "",
        "---",
        "",
    ]
    
    # Group by category
    by_category = {}
    for article in articles_with_content:
        cat = article['category']
        if cat not in by_category:
            by_category[cat] = []
        by_category[cat].append(article)
    
    # Category order by importance
    category_order = [
        '🔬 Deep Research',
        '🤖 AI Research', 
        '🚀 AI Engineering',
        '⚙️ Rust & Systems',
        '🗄️ Data & Storage',
        '🌐 Web Development',
        '🔒 Security',
        '💡 Tech Discussion',
        '📰 General Tech'
    ]
    
    for category in category_order:
        if category not in by_category:
            continue
        
        lines.append(f"## {category}")
        lines.append("")
        
        for article in by_category[category][:3]:  # Top 3 per category
            lines.append(f"**{article['title']}**")
            lines.append(f"*{article['source']}* | [Read full article]({article['url']})")
            lines.append("")
            
            # The insight
            if article.get('summary'):
                lines.append(f"→ {article['summary']}")
            
            if article.get('full_content') and len(article['full_content']) > 100:
                # Add a key insight from the content
                content_snippet = article['full_content'][:300].replace('\n', ' ')
                lines.append(f"> {content_snippet}...")
            
            lines.append("")
        
        lines.append("")
    
    # Add trends section
    lines.append("---")
    lines.append("")
    lines.append("## 📊 Emerging Patterns")
    lines.append("")
    
    # Simple pattern detection
    topics = {}
    for article in articles_with_content:
        for topic in ['LLM', 'Rust', 'embeddings', 'async', 'GPU', 'fine-tuning']:
            if topic.lower() in article['title'].lower() or (article.get('full_content') and topic.lower() in article['full_content'].lower()[:2000]):
                topics[topic] = topics.get(topic, 0) + 1
    
    if topics:
        top_topics = sorted(topics.items(), key=lambda x: x[1], reverse=True)[:5]
        for topic, count in top_topics:
            lines.append(f"- **{topic}** appears in {count} stories")
    else:
        lines.append("- No clear pattern detected in today's stories")
    
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(f"*Newsletter generated {datetime.now().strftime('%Y-%m-%d %H:%M')} | Sources: HN, Distill, HF, TWiR, JS Weekly*")
    
    return '\n'.join(lines)


def main():
    print(f"Connecting to {DB_PATH}...")
    conn = sqlite3.connect(DB_PATH)
    
    print("Fetching top articles...")
    articles = get_top_articles(conn, limit=15)
    print(f"  Found {len(articles)} articles to analyze")
    
    if not articles:
        print("No articles found!")
        return 1
    
    # Fetch full content and generate insight
    articles_with_content = []
    for i, (title, url, source, domain, content, published_at) in enumerate(articles, 1):
        print(f"\n[{i}/{len(articles)}] Analyzing: {title[:60]}...")
        
        article_data = {
            'title': title,
            'url': url,
            'source': source,
            'domain': domain,
            'category': categorize_article(title, content or '', source),
            'summary': None,
            'full_content': None
        }
        
        # Try to fetch full content
        if should_skip_url(url):
            print(f"  Skipping (paywalled domain)")
            article_data['summary'] = "Full article requires subscription"
        else:
            print(f"  Fetching full content...")
            full_content, error = fetch_full_content(url)
            if full_content:
                print(f"  Got {len(full_content)} chars, generating insight...")
                article_data['full_content'] = full_content
                article_data['summary'] = generate_ai_summary(title, full_content, source)
            else:
                print(f"  Failed: {error}")
                # Use RSS content as fallback
                if content:
                    article_data['summary'] = generate_ai_summary(title, content, source)
                else:
                    article_data['summary'] = "Unable to extract summary"
        
        articles_with_content.append(article_data)
    
    print(f"\nGenerating newsletter...")
    newsletter = generate_insight_newsletter(articles_with_content)
    
    with open(OUTPUT_PATH, 'w') as f:
        f.write(newsletter)
    
    print(f"Newsletter written to {OUTPUT_PATH}")
    
    # Show preview
    print("\n" + "="*60)
    print("PREVIEW:")
    print("="*60)
    print(newsletter[:3000])
    print("...")
    
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
