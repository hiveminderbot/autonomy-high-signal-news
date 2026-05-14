"""Regression tests for high-signal briefing rendering sections."""
from scripts.generate_high_signal_briefing import build_briefing_result


def _article(title: str, domain: str):
    return {
        "title": title,
        "url": f"https://example.test/{title.lower().replace(' ', '-')}",
        "source_name": "Tier One",
        "domain": domain,
        "published_at": "2026-05-14T00:00:00",
        "content": "useful content " * 80,
        "full_content": "useful full content " * 80,
        "quality_score": 95,
    }


def test_build_briefing_result_includes_current_catalog_domain_names():
    result = build_briefing_result([
        _article("AI story", "ai"),
        _article("Software story", "software_development"),
    ])

    assert result.metadata.total_stories == 2
    section_names = {section.name for section in result.sections}
    assert "Ai" in section_names
    assert "Software Development" in section_names
