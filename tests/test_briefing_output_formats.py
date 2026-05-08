"""Test HTML and JSON output formats for high-signal briefing generator."""
import json
import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from scripts.generate_high_signal_briefing import (
    generate_newsletter_html,
    generate_newsletter_json,
    get_recent_articles,
    filter_high_signal,
)


def _make_article(article_id, title, url, source, domain, published_at, **kwargs):
    return {
        'id': article_id,
        'title': title,
        'url': url,
        'source': source,
        'domain': domain,
        'published_at': published_at,
        'full_content': kwargs.get('full_content', 'a' * 600),
        'content': kwargs.get('content', 'a' * 600),
        'llm_insight': kwargs.get('llm_insight'),
        'source_name': kwargs.get('source_name', source),
        'tier': kwargs.get('tier', 1),
        'quality_score': kwargs.get('quality_score', 0.9),
    }


def test_generate_newsletter_html_structure():
    """HTML output must be valid HTML with expected sections."""
    articles = [
        _make_article(1, 'Rust 2.0 Released', 'https://example.com/rust', 'Hacker News', 'software', datetime.now().isoformat(), llm_insight='Major memory safety improvements'),
        _make_article(2, 'GPT-5 Benchmarks', 'https://example.com/gpt5', 'Lobsters', 'ai_research', datetime.now().isoformat()),
    ]

    html = generate_newsletter_html(articles)

    assert html.startswith('<!DOCTYPE html>')
    assert '<html' in html
    assert '<head>' in html
    assert '<body>' in html
    assert 'High-Signal Briefing' in html
    assert 'Rust 2.0 Released' in html
    assert 'GPT-5 Benchmarks' in html
    assert 'https://example.com/rust' in html
    assert 'https://example.com/gpt5' in html
    assert 'Hacker News' in html
    assert 'Lobsters' in html
    assert 'Major memory safety improvements' in html
    assert '<style>' in html
    assert 'article' in html.lower()
    assert '</html>' in html


def test_generate_newsletter_html_empty_articles():
    """HTML with no articles should still produce valid HTML."""
    html = generate_newsletter_html([])
    assert html.startswith('<!DOCTYPE html>')
    assert '</html>' in html
    assert '0 high-signal stories' in html or 'high-signal stories' in html


def test_generate_newsletter_json_structure():
    """JSON output must parse and contain expected fields."""
    articles = [
        _make_article(1, 'Rust 2.0 Released', 'https://example.com/rust', 'Hacker News', 'software', datetime.now().isoformat(), llm_insight='Major memory safety improvements'),
        _make_article(2, 'GPT-5 Benchmarks', 'https://example.com/gpt5', 'Lobsters', 'ai_research', datetime.now().isoformat()),
    ]

    json_str = generate_newsletter_json(articles)
    data = json.loads(json_str)

    # Meta
    assert 'meta' in data
    assert 'generated_at' in data['meta']
    assert 'date' in data['meta']
    assert data['meta']['total_articles'] == 2
    assert data['meta']['format_version'] == '1.0'

    # Sources summary
    assert 'sources_summary' in data
    assert data['sources_summary']['tier'] == 1

    # Articles
    assert 'articles' in data
    assert len(data['articles']) == 2
    art = data['articles'][0]
    assert 'id' in art
    assert 'title' in art
    assert 'url' in art
    assert 'source' in art
    assert 'domain' in art
    assert 'tier' in art
    assert 'quality_score' in art

    # Articles by domain
    assert 'articles_by_domain' in data


def test_generate_newsletter_json_empty_articles():
    """JSON with no articles should still produce valid JSON."""
    json_str = generate_newsletter_json([])
    data = json.loads(json_str)
    assert data['meta']['total_articles'] == 0
    assert data['articles'] == []


def test_generate_newsletter_json_roundtrip():
    """JSON output must be re-parsable and idempotent in structure."""
    articles = [
        _make_article(1, 'Test Article', 'https://example.com/test', 'Hacker News', 'software', datetime.now().isoformat()),
    ]

    json_str1 = generate_newsletter_json(articles)
    data1 = json.loads(json_str1)
    json_str2 = generate_newsletter_json(articles)
    data2 = json.loads(json_str2)

    # Structure identical (excluding generated_at which changes)
    assert data1['meta']['format_version'] == data2['meta']['format_version']
    assert data1['meta']['total_articles'] == data2['meta']['total_articles']
    assert len(data1['articles']) == len(data2['articles'])


def test_main_all_formats(tmp_path):
    """Integration: running main with --format all produces md, html, json."""
    from scripts.generate_high_signal_briefing import main

    # Patch get_recent_articles to return mock data
    mock_articles = [
        _make_article(1, 'Rust 2.0 Released', 'https://example.com/rust', 'Hacker News', 'software', datetime.now().isoformat(), llm_insight='Major improvements'),
        _make_article(2, 'GPT-5 Benchmarks', 'https://example.com/gpt5', 'Lobsters', 'ai_research', datetime.now().isoformat()),
    ]

    with patch('scripts.generate_high_signal_briefing.get_recent_articles', return_value=mock_articles):
        with patch('scripts.generate_high_signal_briefing.OUTPUT_PATH', tmp_path):
            with patch('sys.argv', ['generate_high_signal_briefing.py', '--format', 'all', '--output-dir', str(tmp_path)]):
                main()

    # Check all three files exist
    files = list(tmp_path.glob('briefing-high-signal-*'))
    assert len(files) == 3
    extensions = {f.suffix for f in files}
    assert extensions == {'.md', '.html', '.json'}

    # Validate JSON
    json_file = next(f for f in files if f.suffix == '.json')
    data = json.loads(json_file.read_text())
    assert data['meta']['total_articles'] == 2

    # Validate HTML
    html_file = next(f for f in files if f.suffix == '.html')
    html = html_file.read_text()
    assert html.startswith('<!DOCTYPE html>')
    assert 'Rust 2.0 Released' in html

    # Validate Markdown
    md_file = next(f for f in files if f.suffix == '.md')
    md = md_file.read_text()
    assert 'Rust 2.0 Released' in md
    assert '# High-Signal Briefing' in md


def test_main_single_format_json(tmp_path):
    """Integration: --format json produces only JSON."""
    from scripts.generate_high_signal_briefing import main

    mock_articles = [
        _make_article(1, 'Test', 'https://example.com', 'Hacker News', 'software', datetime.now().isoformat()),
    ]

    with patch('scripts.generate_high_signal_briefing.get_recent_articles', return_value=mock_articles):
        with patch('sys.argv', ['generate_high_signal_briefing.py', '--format', 'json', '--output-dir', str(tmp_path)]):
            main()

    files = list(tmp_path.glob('briefing-high-signal-*'))
    assert len(files) == 1
    assert files[0].suffix == '.json'


def test_main_single_format_html(tmp_path):
    """Integration: --format html produces only HTML."""
    from scripts.generate_high_signal_briefing import main

    mock_articles = [
        _make_article(1, 'Test', 'https://example.com', 'Hacker News', 'software', datetime.now().isoformat()),
    ]

    with patch('scripts.generate_high_signal_briefing.get_recent_articles', return_value=mock_articles):
        with patch('sys.argv', ['generate_high_signal_briefing.py', '--format', 'html', '--output-dir', str(tmp_path)]):
            main()

    files = list(tmp_path.glob('briefing-high-signal-*'))
    assert len(files) == 1
    assert files[0].suffix == '.html'


def test_main_no_articles(tmp_path, capsys):
    """Integration: no articles after filtering should print message and exit cleanly."""
    from scripts.generate_high_signal_briefing import main

    with patch('scripts.generate_high_signal_briefing.get_recent_articles', return_value=[]):
        with patch('sys.argv', ['generate_high_signal_briefing.py', '--format', 'all', '--output-dir', str(tmp_path)]):
            main()

    files = list(tmp_path.glob('briefing-high-signal-*'))
    assert len(files) == 0
    captured = capsys.readouterr()
    assert 'No articles passed filtering' in captured.out or '0 articles' in captured.out
