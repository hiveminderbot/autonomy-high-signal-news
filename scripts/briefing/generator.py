#!/usr/bin/env python3
"""
Briefing Generator - Phase 4 Core Module

Transforms aggregated and summarized stories into a formatted morning briefing.
Designed for 10-minute reading with maximum signal-to-noise ratio.
"""

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional


class BriefingFormat(Enum):
    """Output format for the briefing."""
    MARKDOWN = "markdown"
    HTML = "html"
    TEXT = "text"
    JSON = "json"


@dataclass
class BriefingSection:
    """A section of the briefing (e.g., AI, Software, Investment)."""
    name: str
    emoji: str
    stories: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            'name': self.name,
            'emoji': self.emoji,
            'stories': self.stories
        }


@dataclass
class BriefingItem:
    """A single item in the briefing."""
    title: str
    summary: str
    sources: list[str]
    tier: str  # must_read, important, contextual
    entities: list[str] = field(default_factory=list)
    urgency: str = "normal"  # breaking, urgent, normal
    url: Optional[str] = None
    published: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            'title': self.title,
            'summary': self.summary,
            'sources': self.sources,
            'tier': self.tier,
            'entities': self.entities,
            'urgency': self.urgency,
            'url': self.url,
            'published': self.published,
        }


@dataclass
class BriefingMetadata:
    """Metadata about the briefing."""
    generated_at: str
    total_stories: int
    must_read_count: int
    important_count: int
    contextual_count: int
    sources_used: int
    reading_time_minutes: int

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class BriefingResult:
    """Complete briefing result."""
    metadata: BriefingMetadata
    sections: list[BriefingSection]

    def to_dict(self) -> dict:
        return {
            'metadata': self.metadata.to_dict(),
            'sections': [s.to_dict() for s in self.sections]
        }


class BriefingGenerator:
    """
    Generates a morning briefing from aggregated and scored stories.

    Organizes content by:
    - Domain sections (AI, Software, Investment)
    - Priority tiers (Must Read, Important, Contextual)
    - Urgency markers (Breaking, Urgent, Normal)
    """

    # Domain classification keywords
    DOMAIN_KEYWORDS = {
        'AI': [
            'llm', 'model', 'gpt', 'claude', 'gemini', 'ai ', 'artificial intelligence',
            'neural', 'transformer', 'training', 'fine-tuning', 'rlhf', 'alignment',
            'agent', 'autonomous', 'multimodal', 'embedding', 'vector', 'rag',
            'openai', 'anthropic', 'google', 'deepmind', 'mistral', 'meta ai',
            'machine learning', 'deep learning', 'foundation model', 'benchmark'
        ],
        'Software': [
            'python', 'rust', 'golang', 'javascript', 'typescript', 'java', 'c++',
            'framework', 'library', 'release', 'version', 'update', 'deprecat',
            'security', 'vulnerability', 'cve', 'patch', 'kubernetes', 'docker',
            'database', 'api', 'microservice', 'serverless', 'cloud', 'aws',
            'architecture', 'performance', 'optimization', 'refactor'
        ],
        'Investment': [
            'funding', 'raise', 'series', 'venture', 'vc', 'investment', 'investor',
            'ipo', 'acquisition', 'merger', 'stock', 'market', 'trading',
            'valuation', 'unicorn', 'startup', 'revenue', 'profit', 'earnings',
            'regulatory', 'sec', 'compliance', 'crypto', 'bitcoin', 'defi',
            'economy', 'inflation', 'fed', 'interest rate'
        ]
    }

    def __init__(
        self,
        max_items_per_section: int = 20,
        max_must_read_total: int = 5,
        max_important_total: int = 15,
        target_reading_time: int = 10,  # minutes
    ):
        self.max_items_per_section = max_items_per_section
        self.max_must_read_total = max_must_read_total
        self.max_important_total = max_important_total
        self.target_reading_time = target_reading_time

    def classify_domain(self, story: dict) -> str:
        """Classify a story into a domain based on content."""
        text = f"{story.get('title', '')} {story.get('summary', '')} {story.get('content', '')}".lower()

        scores = {}
        for domain, keywords in self.DOMAIN_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw.lower() in text)
            scores[domain] = score

        # Return domain with highest score, or 'General' if no matches
        if max(scores.values()) == 0:
            return 'General'
        return max(scores, key=scores.get)

    def create_briefing_item(self, story: dict) -> BriefingItem:
        """Convert a story dict into a BriefingItem."""
        # Extract tier from relevance score if available
        tier = story.get('tier', 'contextual')
        if isinstance(tier, str) and tier not in ['must_read', 'important', 'contextual']:
            tier = 'contextual'

        content = story.get('content') or ''
        summary = story.get('summary') or content[:500]

        return BriefingItem(
            title=story.get('title', 'Untitled'),
            summary=summary,
            sources=story.get('sources', [story.get('source', 'Unknown')]),
            tier=tier,
            entities=story.get('entities', []),
            urgency=story.get('urgency', 'normal'),
            url=story.get('url'),
            published=story.get('published'),
        )

    def organize_by_tier(self, items: list[BriefingItem]) -> tuple[list[BriefingItem], list[BriefingItem], list[BriefingItem]]:
        """Organize items by priority tier."""
        must_read = [i for i in items if i.tier == 'must_read']
        important = [i for i in items if i.tier == 'important']
        contextual = [i for i in items if i.tier == 'contextual']

        # Apply limits
        must_read = must_read[:self.max_must_read_total]
        important = important[:self.max_important_total]

        return must_read, important, contextual

    def generate(
        self,
        stories: list[dict],
        include_domains: Optional[list[str]] = None,
    ) -> BriefingResult:
        """
        Generate a briefing from a list of stories.

        Args:
            stories: List of story dicts with title, summary, tier, etc.
            include_domains: List of domains to include (default: all)

        Returns:
            BriefingResult with organized sections and metadata
        """
        # Default to all domains
        if include_domains is None:
            include_domains = ['AI', 'Software', 'Investment', 'General']

        # Classify and convert stories
        classified = {domain: [] for domain in include_domains}
        for story in stories:
            domain = self.classify_domain(story)
            if domain in classified:
                item = self.create_briefing_item(story)
                classified[domain].append(item)

        # Create sections with tier organization
        sections = []
        all_items = []

        for domain in include_domains:
            items = classified.get(domain, [])
            if not items:
                continue

            must_read, important, contextual = self.organize_by_tier(items)

            # Combine in priority order
            domain_items = must_read + important + contextual
            domain_items = domain_items[:self.max_items_per_section]

            if domain_items:
                emoji = {
                    'AI': '🤖',
                    'Software': '💻',
                    'Investment': '💰',
                    'General': '📰'
                }.get(domain, '📰')

                sections.append(BriefingSection(
                    name=domain,
                    emoji=emoji,
                    stories=[i.to_dict() for i in domain_items]
                ))
                all_items.extend(domain_items)

        # Calculate metadata
        must_read_count = sum(1 for i in all_items if i.tier == 'must_read')
        important_count = sum(1 for i in all_items if i.tier == 'important')
        contextual_count = sum(1 for i in all_items if i.tier == 'contextual')

        # Estimate reading time (average 200 words per minute)
        total_words = sum(
            len(i.title.split()) + len(i.summary.split())
            for i in all_items
        )
        reading_time = max(1, total_words // 200)

        metadata = BriefingMetadata(
            generated_at=datetime.now().isoformat(),
            total_stories=len(all_items),
            must_read_count=must_read_count,
            important_count=important_count,
            contextual_count=contextual_count,
            sources_used=len(set(
                source for i in all_items for source in i.sources
            )),
            reading_time_minutes=min(reading_time, self.target_reading_time),
        )

        return BriefingResult(metadata=metadata, sections=sections)

    def generate_from_pipeline_output(
        self,
        pipeline_output_path: Path,
        output_format: BriefingFormat = BriefingFormat.MARKDOWN,
    ) -> tuple[str, BriefingResult]:
        """
        Generate a briefing from pipeline output file.

        Args:
            pipeline_output_path: Path to pipeline output JSON
            output_format: Desired output format

        Returns:
            Tuple of (formatted_briefing_string, briefing_result)
        """
        with open(pipeline_output_path) as f:
            data = json.load(f)

        # Extract stories from pipeline output
        stories = data.get('stories', [])
        if not stories and 'clusters' in data:
            # Handle clustered output
            stories = []
            for cluster in data.get('clusters', []):
                cluster_stories = cluster.get('stories', [])
                if cluster_stories:
                    # Use first story as representative
                    rep = cluster_stories[0].copy()
                    rep['sources'] = [s.get('source', 'Unknown') for s in cluster_stories]
                    stories.append(rep)

        # Generate briefing
        result = self.generate(stories)

        # Format output
        if output_format == BriefingFormat.MARKDOWN:
            from briefing.renderer import MarkdownRenderer
            renderer = MarkdownRenderer()
        elif output_format == BriefingFormat.HTML:
            from briefing.renderer import HTMLRenderer
            renderer = HTMLRenderer()
        elif output_format == BriefingFormat.TEXT:
            from briefing.renderer import TextRenderer
            renderer = TextRenderer()
        else:
            return json.dumps(result.to_dict(), indent=2), result

        formatted = renderer.render(result)
        return formatted, result


def generate_briefing_command():
    """CLI command to generate a briefing from pipeline output."""
    import argparse

    parser = argparse.ArgumentParser(description='Generate morning briefing')
    parser.add_argument('input', help='Path to pipeline output JSON')
    parser.add_argument('-o', '--output', help='Output file path')
    parser.add_argument('-f', '--format', choices=['markdown', 'html', 'text', 'json'],
                       default='markdown', help='Output format')
    parser.add_argument('--max-must-read', type=int, default=5)
    parser.add_argument('--max-important', type=int, default=10)

    args = parser.parse_args()

    generator = BriefingGenerator(
        max_must_read_total=args.max_must_read,
        max_important_total=args.max_important,
    )

    format_map = {
        'markdown': BriefingFormat.MARKDOWN,
        'html': BriefingFormat.HTML,
        'text': BriefingFormat.TEXT,
        'json': BriefingFormat.JSON,
    }

    formatted, result = generator.generate_from_pipeline_output(
        Path(args.input),
        format_map[args.format]
    )

    if args.output:
        with open(args.output, 'w') as f:
            f.write(formatted)
        print(f"Briefing written to {args.output}")
        print(f"Total stories: {result.metadata.total_stories}")
        print(f"Must read: {result.metadata.must_read_count}")
        print(f"Important: {result.metadata.important_count}")
        print(f"Est. reading time: {result.metadata.reading_time_minutes} min")
    else:
        print(formatted)


if __name__ == '__main__':
    generate_briefing_command()
