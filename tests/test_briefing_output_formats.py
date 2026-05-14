"""Test HTML and JSON output formats for high-signal briefing generator.

These tests verify that the refactored generator (using centralized briefing.renderer)
produces valid, structurally correct output in all supported formats.
"""
import json
import sqlite3
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from scripts.generate_high_signal_briefing import (
    generate_newsletter_html,
    generate_newsletter_json,
    generate_newsletter_markdown,
    generate_newsletter_text,
    get_recent_articles,
    filter_high_signal,
    build_briefing_result,
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
    # Renderer produces "Morning Briefing" header; articles must be present
    assert 'Morning Briefing' in html or 'Briefing' in html
    assert 'Rust 2.0 Released' in html
    assert 'GPT-5 Benchmarks' in html
    assert 'https://example.com/rust' in html
    assert 'https://example.com/gpt5' in html
    assert 'Hacker News' in html
    assert 'Lobsters' in html
    assert 'Major memory safety improvements' in html
    assert '<style>' in html
    assert 'story' in html.lower() or 'article' in html.lower()
    assert '</html>' in html


def test_generate_newsletter_html_empty_articles():
    """HTML with no articles should still produce valid HTML."""
    html = generate_newsletter_html([])
    assert html.startswith('<!DOCTYPE html>')
    assert '</html>' in html
    # Renderer shows 0 stories in metadata line
    assert '0 stories' in html or 'stories' in html


def test_generate_newsletter_json_structure():
    """JSON output must parse and contain expected fields from BriefingResult."""
    articles = [
        _make_article(1, 'Rust 2.0 Released', 'https://example.com/rust', 'Hacker News', 'software', datetime.now().isoformat(), llm_insight='Major memory safety improvements'),
        _make_article(2, 'GPT-5 Benchmarks', 'https://example.com/gpt5', 'Lobsters', 'ai_research', datetime.now().isoformat()),
    ]

    json_str = generate_newsletter_json(articles)
    data = json.loads(json_str)

    # BriefingResult structure: metadata + sections
    assert 'metadata' in data
    assert 'generated_at' in data['metadata']
    assert 'total_stories' in data['metadata']
    assert data['metadata']['total_stories'] == 2

    # Sections
    assert 'sections' in data
    assert len(data['sections']) >= 1
    section = data['sections'][0]
    assert 'name' in section
    assert 'emoji' in section
    assert 'stories' in section

    # Stories have expected fields
    stories = section['stories']
    assert len(stories) >= 1
    art = stories[0]
    assert 'title' in art
    assert 'summary' in art
    assert 'sources' in art
    assert 'tier' in art


def test_generate_newsletter_json_empty_articles():
    """JSON with no articles should still produce valid JSON."""
    json_str = generate_newsletter_json([])
    data = json.loads(json_str)
    assert data['metadata']['total_stories'] == 0
    assert data['sections'] == []


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
    assert data1['metadata']['total_stories'] == data2['metadata']['total_stories']
    assert len(data1['sections']) == len(data2['sections'])


def test_build_briefing_result_structure():
    """BriefingResult builder must produce valid structure."""
    articles = [
        _make_article(1, 'Rust 2.0 Released', 'https://example.com/rust', 'Hacker News', 'software', datetime.now().isoformat()),
        _make_article(2, 'GPT-5 Benchmarks', 'https://example.com/gpt5', 'Lobsters', 'ai_research', datetime.now().isoformat()),
    ]

    result = build_briefing_result(articles)
    assert result.metadata.total_stories == 2
    assert len(result.sections) >= 1
    # Articles should be grouped by domain
    section_names = [s.name for s in result.sections]
    assert 'Software' in section_names or 'Ai Research' in section_names or 'Ai Labs' in section_names


def test_generate_newsletter_markdown_structure():
    """Markdown output must contain expected structural elements."""
    articles = [
        _make_article(1, 'Rust 2.0 Released', 'https://example.com/rust', 'Hacker News', 'software', datetime.now().isoformat()),
    ]

    md = generate_newsletter_markdown(articles)
    assert '# High-Signal Briefing' in md
    assert 'Rust 2.0 Released' in md
    assert 'https://example.com/rust' in md
    assert 'Hacker News' in md


def test_generate_newsletter_text_structure():
    """Text output must contain expected structural elements."""
    articles = [
        _make_article(1, 'Rust 2.0 Released', 'https://example.com/rust', 'Hacker News', 'software', datetime.now().isoformat()),
    ]

    text = generate_newsletter_text(articles)
    assert 'MORNING BRIEFING' in text or 'BRIEFING' in text
    assert 'Rust 2.0 Released' in text


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
    assert data['metadata']['total_stories'] == 2

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
    assert (tmp_path / 'latest.md').read_text() == md
    assert (tmp_path / 'latest.html').read_text() == html


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


def test_generated_artifact_writer_strips_trailing_whitespace(tmp_path):
    from scripts.generate_high_signal_briefing import write_text_without_trailing_whitespace

    output = tmp_path / 'artifact.html'
    write_text_without_trailing_whitespace(output, 'line with spaces   \nclean\n')

    assert output.read_text() == 'line with spaces\nclean\n'


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
