"""
Briefing Generation Module - Phase 4

Formats aggregated, summarized content into a morning briefing:
- Structured sections by domain (AI, Software, Investment)
- Prioritized by relevance tier (must_read, important, contextual)
- Formatted for quick reading (10-minute limit)
- Multiple output formats (Markdown, HTML, Plain text)
- Delivery via email, Telegram, and file output
"""

from briefing.generator import BriefingGenerator, BriefingFormat, BriefingSection, BriefingItem, BriefingMetadata, BriefingResult
from briefing.renderer import MarkdownRenderer, HTMLRenderer, TextRenderer
from briefing.delivery import (
    DeliveryResult,
    DeliveryChannel,
    EmailDelivery,
    TelegramDelivery,
    FileDelivery,
    MultiChannelDelivery,
    create_delivery_from_config
)

__all__ = [
    # Generator
    'BriefingGenerator',
    'BriefingFormat',
    'BriefingSection',
    'BriefingItem',
    'BriefingMetadata',
    'BriefingResult',
    # Renderer
    'MarkdownRenderer',
    'HTMLRenderer',
    'TextRenderer',
    # Delivery
    'DeliveryResult',
    'DeliveryChannel',
    'EmailDelivery',
    'TelegramDelivery',
    'FileDelivery',
    'MultiChannelDelivery',
    'create_delivery_from_config',
]
