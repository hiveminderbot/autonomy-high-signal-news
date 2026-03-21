"""
Briefing Generation Module - Phase 4

Formats aggregated, summarized content into a morning briefing:
- Structured sections by domain (AI, Software, Investment)
- Prioritized by relevance tier (must_read, important, contextual)
- Formatted for quick reading (10-minute limit)
- Multiple output formats (Markdown, HTML, Plain text)
"""

from briefing.generator import BriefingGenerator, BriefingFormat, BriefingSection
from briefing.renderer import MarkdownRenderer, HTMLRenderer, TextRenderer

__all__ = [
    'BriefingGenerator',
    'BriefingFormat',
    'BriefingSection',
    'MarkdownRenderer',
    'HTMLRenderer',
    'TextRenderer',
]
