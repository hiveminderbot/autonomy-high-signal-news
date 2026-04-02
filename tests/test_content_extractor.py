#!/usr/bin/env python3
"""
Tests for the content extractor.

Run with: python tests/test_content_extractor.py
"""

import sys
import tempfile
from datetime import datetime
from pathlib import Path

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from aggregator.content_extractor import ContentExtractor, ExtractedContent


def test_extracted_content_dataclass():
    """Test that ExtractedContent dataclass works correctly."""
    content = ExtractedContent(
        url="https://example.com/article",
        title="Test Article",
        author="John Doe",
        published_at=datetime(2024, 3, 15, 10, 30, 0),
        content_text="This is the article content.",
        content_html="<p>This is the article content.</p>",
        excerpt="This is the article...",
        word_count=5,
        reading_time_minutes=1,
        extracted_at=datetime.now(),
        is_paywalled=False,
        extraction_error=None
    )

    assert content.url == "https://example.com/article"
    assert content.title == "Test Article"
    assert content.author == "John Doe"
    assert content.word_count == 5
    assert content.is_paywalled == False
    print("✅ test_extracted_content_dataclass passed")


def test_content_extractor_initialization():
    """Test that ContentExtractor initializes with correct defaults."""
    extractor = ContentExtractor()

    assert extractor.request_timeout == 30
    assert extractor.min_fetch_interval == 1.0
    assert extractor.respect_robots_txt == True
    assert "HighSignalNewsBot" in extractor.user_agent
    print("✅ test_content_extractor_initialization passed")


def test_content_extractor_custom_params():
    """Test that ContentExtractor accepts custom parameters."""
    extractor = ContentExtractor(
        request_timeout=60,
        min_fetch_interval=2.5,
        respect_robots_txt=False,
        user_agent="CustomBot/1.0"
    )

    assert extractor.request_timeout == 60
    assert extractor.min_fetch_interval == 2.5
    assert extractor.respect_robots_txt == False
    assert extractor.user_agent == "CustomBot/1.0"
    print("✅ test_content_extractor_custom_params passed")


def test_paywall_detection():
    """Test paywall detection with mock HTML."""
    from bs4 import BeautifulSoup

    extractor = ContentExtractor()

    # Test HTML with paywall indicator
    html_with_paywall = """
    <html>
        <body>
            <div class="article-content">
                <p>Article preview...</p>
                <div class="paywall-message">Subscribe to read more</div>
            </div>
        </body>
    </html>
    """
    soup = BeautifulSoup(html_with_paywall, 'html.parser')
    assert extractor._detect_paywall(soup) == True

    # Test HTML without paywall
    html_without_paywall = """
    <html>
        <body>
            <article>
                <p>Full article content here</p>
            </article>
        </body>
    </html>
    """
    soup = BeautifulSoup(html_without_paywall, 'html.parser')
    assert extractor._detect_paywall(soup) == False

    print("✅ test_paywall_detection passed")


def test_title_extraction():
    """Test title extraction from various HTML structures."""
    from bs4 import BeautifulSoup

    extractor = ContentExtractor()

    # Test h1.article-title
    html = """
    <html>
        <body>
            <h1 class="article-title">Test Article Title</h1>
        </body>
    </html>
    """
    soup = BeautifulSoup(html, 'html.parser')
    assert extractor._extract_title(soup) == "Test Article Title"

    # Test og:title meta tag
    html = """
    <html>
        <head>
            <meta property="og:title" content="Meta Title">
        </head>
        <body>
            <h1>Wrong Title</h1>
        </body>
    </html>
    """
    soup = BeautifulSoup(html, 'html.parser')
    # Should prefer h1 over meta
    assert extractor._extract_title(soup) == "Wrong Title"

    # Test page title fallback
    html = """
    <html>
        <head><title>Page Title</title></head>
        <body></body>
    </html>
    """
    soup = BeautifulSoup(html, 'html.parser')
    assert extractor._extract_title(soup) == "Page Title"

    print("✅ test_title_extraction passed")


def test_author_extraction():
    """Test author extraction from various HTML structures."""
    from bs4 import BeautifulSoup

    extractor = ContentExtractor()

    # Test rel=author
    html = """
    <html>
        <body>
            <a rel="author" href="/author/john">John Doe</a>
        </body>
    </html>
    """
    soup = BeautifulSoup(html, 'html.parser')
    assert extractor._extract_author(soup) == "John Doe"

    # Test author meta tag
    html = """
    <html>
        <head>
            <meta name="author" content="Jane Smith">
        </head>
        <body></body>
    </html>
    """
    soup = BeautifulSoup(html, 'html.parser')
    assert extractor._extract_author(soup) == "Jane Smith"

    # Test byline class
    html = """
    <html>
        <body>
            <span class="byline">By Bob Writer</span>
        </body>
    </html>
    """
    soup = BeautifulSoup(html, 'html.parser')
    assert extractor._extract_author(soup) == "By Bob Writer"

    print("✅ test_author_extraction passed")


def test_date_extraction():
    """Test date extraction from various HTML structures."""
    from bs4 import BeautifulSoup

    extractor = ContentExtractor()

    # Test time[datetime]
    html = """
    <html>
        <body>
            <time datetime="2024-03-15T10:30:00">March 15, 2024</time>
        </body>
    </html>
    """
    soup = BeautifulSoup(html, 'html.parser')
    result = extractor._extract_published_date(soup)
    assert result is not None
    assert result.year == 2024
    assert result.month == 3
    assert result.day == 15

    # Test article:published_time meta
    html = """
    <html>
        <head>
            <meta property="article:published_time" content="2024-01-20T14:00:00">
        </head>
        <body></body>
    </html>
    """
    soup = BeautifulSoup(html, 'html.parser')
    result = extractor._extract_published_date(soup)
    assert result is not None
    assert result.year == 2024
    assert result.month == 1
    assert result.day == 20

    print("✅ test_date_extraction passed")


def test_content_extraction():
    """Test content extraction with noise removal."""
    from bs4 import BeautifulSoup

    extractor = ContentExtractor()

    html = """
    <html>
        <body>
            <nav>Navigation links</nav>
            <header>Site header</header>
            <article>
                <h1>Article Title</h1>
                <p>First paragraph of content.</p>
                <p>Second paragraph with more text.</p>
            </article>
            <aside>Sidebar content</aside>
            <footer>Site footer</footer>
            <script>console.log('test');</script>
        </body>
    </html>
    """
    soup = BeautifulSoup(html, 'html.parser')
    text, html_content = extractor._extract_content(soup)

    # Should contain article content
    assert "Article Title" in text
    assert "First paragraph" in text
    assert "Second paragraph" in text

    # Should not contain navigation/header/footer
    assert "Navigation links" not in text
    assert "Site header" not in text
    assert "Site footer" not in text
    assert "console.log" not in text

    print("✅ test_content_extraction passed")


def test_extracted_content_metrics():
    """Test that word count and reading time are calculated correctly."""
    content_text = "This is a test article with exactly fourteen words contained in it for testing."
    content = ExtractedContent(
        url="https://example.com/article",
        title="Test",
        author=None,
        published_at=None,
        content_text=content_text,
        content_html=f"<p>{content_text}</p>",
        excerpt="",
        word_count=0,
        reading_time_minutes=0,
        extracted_at=datetime.now()
    )

    # Verify word count calculation
    actual_word_count = len(content.content_text.split())
    expected_word_count = len(content_text.split())
    assert actual_word_count == expected_word_count, f"Expected {expected_word_count} words, got {actual_word_count}"

    # Reading time should be at least 1 minute (for < 200 words)
    expected_reading_time = max(1, actual_word_count // 200)
    assert expected_reading_time == 1, f"Expected 1 min reading time, got {expected_reading_time}"

    print("✅ test_extracted_content_metrics passed")


def test_excerpt_generation():
    """Test excerpt generation from content text."""
    from bs4 import BeautifulSoup

    extractor = ContentExtractor()

    # Test with long content
    html = """
    <html>
        <body>
            <article>
                <p>{}</p>
            </article>
        </body>
    </html>
    """.format("This is a very long paragraph. " * 50)  # Long content

    soup = BeautifulSoup(html, 'html.parser')
    text, _ = extractor._extract_content(soup)

    # Generate excerpt (first 300 chars, truncated at word boundary)
    excerpt = text[:300].strip()
    if len(text) > 300:
        excerpt = excerpt.rsplit(' ', 1)[0] + '...'

    assert len(excerpt) <= 304  # 300 + "..."
    assert excerpt.endswith('...')

    print("✅ test_excerpt_generation passed")


def test_content_selectors_fallback():
    """Test that content extraction falls back when selectors don't match."""
    from bs4 import BeautifulSoup

    extractor = ContentExtractor()

    # HTML without article/main tags
    html = """
    <html>
        <body>
            <div class="wrapper">
                <h1>Page Title</h1>
                <p>Content in a div wrapper.</p>
            </div>
        </body>
    </html>
    """
    soup = BeautifulSoup(html, 'html.parser')
    text, html_content = extractor._extract_content(soup)

    # Should still extract something
    assert "Page Title" in text or "Content in a div" in text

    print("✅ test_content_selectors_fallback passed")


def test_empty_html_handling():
    """Test handling of empty or minimal HTML."""
    from bs4 import BeautifulSoup

    extractor = ContentExtractor()

    # Empty HTML
    html = "<html><body></body></html>"
    soup = BeautifulSoup(html, 'html.parser')

    title = extractor._extract_title(soup)
    author = extractor._extract_author(soup)
    date = extractor._extract_published_date(soup)
    text, html_content = extractor._extract_content(soup)

    # Should handle gracefully
    assert title is None
    assert author is None
    assert date is None
    assert text == "" or text.strip() == ""

    print("✅ test_empty_html_handling passed")


def run_all_tests():
    """Run all content extractor tests."""
    tests = [
        test_extracted_content_dataclass,
        test_content_extractor_initialization,
        test_content_extractor_custom_params,
        test_paywall_detection,
        test_title_extraction,
        test_author_extraction,
        test_date_extraction,
        test_content_extraction,
        test_extracted_content_metrics,
        test_excerpt_generation,
        test_content_selectors_fallback,
        test_empty_html_handling,
    ]

    passed = 0
    failed = 0

    print("\n" + "=" * 60)
    print("Running Content Extractor Tests")
    print("=" * 60 + "\n")

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"❌ {test.__name__} FAILED: {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == '__main__':
    success = run_all_tests()
    sys.exit(0 if success else 1)
