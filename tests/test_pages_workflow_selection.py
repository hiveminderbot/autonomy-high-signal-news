"""Regression tests for GitHub Pages briefing selection."""
from pathlib import Path


def test_pages_workflow_selects_newest_briefing_across_naming_conventions():
    workflow = Path(".github/workflows/pages.yml").read_text()

    assert "Path('output').glob('briefing*.html')" in workflow
    assert "Path('output').glob('briefing*.md')" in workflow
    assert "sorted(candidates)[-1][2]" in workflow
    assert "stale briefing_YYYY-MM-DD file can hide a fresh high-signal" in workflow