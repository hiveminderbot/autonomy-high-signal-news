#!/usr/bin/env python3
"""
Tests for the briefing generator module.
"""

import json
import tempfile
from datetime import datetime
from pathlib import Path

import pytest

# Add scripts to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from briefing.generator import (
    BriefingGenerator,
    BriefingFormat,
    BriefingItem,
    BriefingMetadata,
    BriefingResult,
    BriefingSection,
)


class TestBriefingItem:
    """Test BriefingItem dataclass."""

    def test_create_basic(self):
        item = BriefingItem(
            title="Test Story",
            summary="A test summary",
            sources=["TechCrunch"],
            tier="important"
        )
        assert item.title == "Test Story"
        assert item.summary == "A test summary"
        assert item.sources == ["TechCrunch"]
        assert item.tier == "important"

    def test_create_with_defaults(self):
        item = BriefingItem(
            title="Test",
            summary="Summary",
            sources=["Source"],
            tier="contextual"
        )
        assert item.entities == []
        assert item.urgency == "normal"
        assert item.url is None
        assert item.published is None

    def test_to_dict(self):
        item = BriefingItem(
            title="Test",
            summary="Summary",
            sources=["Source"],
            tier="must_read",
            entities=["AI", "OpenAI"],
            urgency="breaking",
            url="https://example.com",
            published="2024-01-01"
        )
        d = item.to_dict()
        assert d['title'] == "Test"
        assert d['tier'] == "must_read"
        assert d['entities'] == ["AI", "OpenAI"]
        assert d['urgency'] == "breaking"


class TestBriefingMetadata:
    """Test BriefingMetadata dataclass."""

    def test_create(self):
        meta = BriefingMetadata(
            generated_at="2024-01-01T00:00:00",
            total_stories=10,
            must_read_count=2,
            important_count=5,
            contextual_count=3,
            sources_used=4,
            reading_time_minutes=8
        )
        assert meta.total_stories == 10
        assert meta.reading_time_minutes == 8

    def test_to_dict(self):
        meta = BriefingMetadata(
            generated_at="2024-01-01T00:00:00",
            total_stories=10,
            must_read_count=2,
            important_count=5,
            contextual_count=3,
            sources_used=4,
            reading_time_minutes=8
        )
        d = meta.to_dict()
        assert d['total_stories'] == 10
        assert d['must_read_count'] == 2


class TestBriefingGenerator:
    """Test BriefingGenerator class."""

    @pytest.fixture
    def generator(self):
        return BriefingGenerator()

    @pytest.fixture
    def sample_stories(self):
        return [
            {
                'title': 'OpenAI Releases GPT-5',
                'summary': 'New model with improved reasoning capabilities.',
                'content': 'OpenAI has announced GPT-5 with significant improvements.',
                'source': 'TechCrunch',
                'tier': 'must_read',
                'urgency': 'breaking',
                'entities': ['OpenAI', 'GPT-5'],
                'url': 'https://techcrunch.com/gpt5',
            },
            {
                'title': 'Python 3.13 Released',
                'summary': 'New features include improved performance.',
                'source': 'Python Blog',
                'tier': 'important',
                'entities': ['Python'],
            },
            {
                'title': 'VC Funding Down in Q1',
                'summary': 'Venture capital investments have decreased.',
                'source': 'Bloomberg',
                'tier': 'contextual',
                'entities': ['VC', 'Funding'],
            },
        ]

    def test_init_default(self, generator):
        assert generator.max_items_per_section == 20
        assert generator.max_must_read_total == 5
        assert generator.max_important_total == 15
        assert generator.target_reading_time == 10

    def test_init_custom(self):
        gen = BriefingGenerator(
            max_items_per_section=5,
            max_must_read_total=3,
            target_reading_time=5
        )
        assert gen.max_items_per_section == 5
        assert gen.max_must_read_total == 3
        assert gen.target_reading_time == 5

    def test_classify_domain_ai(self, generator):
        story = {'title': 'GPT-5 Released', 'content': 'New LLM from OpenAI'}
        assert generator.classify_domain(story) == 'AI'

    def test_classify_domain_software(self, generator):
        story = {'title': 'Python 3.13', 'content': 'New release with security fixes'}
        assert generator.classify_domain(story) == 'Software'

    def test_classify_domain_investment(self, generator):
        story = {'title': 'Startup Raises', 'content': 'Series A funding round completed'}
        assert generator.classify_domain(story) == 'Investment'

    def test_classify_domain_general(self, generator):
        story = {'title': 'Random News', 'content': 'Something happened'}
        assert generator.classify_domain(story) == 'General'

    def test_create_briefing_item(self, generator):
        story = {
            'title': 'Test',
            'summary': 'Summary',
            'source': 'Source',
            'tier': 'important',
            'url': 'https://example.com'
        }
        item = generator.create_briefing_item(story)
        assert item.title == 'Test'
        assert item.tier == 'important'
        assert item.url == 'https://example.com'

    def test_create_briefing_item_invalid_tier(self, generator):
        story = {'title': 'Test', 'tier': 'invalid', 'sources': ['Src']}
        item = generator.create_briefing_item(story)
        assert item.tier == 'contextual'  # Falls back to contextual

    def test_organize_by_tier(self, generator):
        items = [
            BriefingItem(title='A', summary='s', sources=['S'], tier='must_read'),
            BriefingItem(title='B', summary='s', sources=['S'], tier='must_read'),
            BriefingItem(title='C', summary='s', sources=['S'], tier='important'),
            BriefingItem(title='D', summary='s', sources=['S'], tier='contextual'),
        ]
        must_read, important, contextual = generator.organize_by_tier(items)
        assert len(must_read) == 2
        assert len(important) == 1
        assert len(contextual) == 1

    def test_organize_by_tier_limits_must_read(self, generator):
        generator.max_must_read_total = 2
        items = [
            BriefingItem(title=f'M{i}', summary='s', sources=['S'], tier='must_read')
            for i in range(5)
        ]
        must_read, _, _ = generator.organize_by_tier(items)
        assert len(must_read) == 2  # Limited by max_must_read_total

    def test_generate_empty(self, generator):
        result = generator.generate([])
        assert result.metadata.total_stories == 0
        assert result.sections == []

    def test_generate_basic(self, generator, sample_stories):
        result = generator.generate(sample_stories)

        assert result.metadata.total_stories == 3
        assert result.metadata.must_read_count == 1
        assert result.metadata.important_count == 1
        assert result.metadata.contextual_count == 1
        assert result.metadata.sources_used == 3

        # Should have sections for AI and Software at least
        section_names = [s.name for s in result.sections]
        assert 'AI' in section_names
        assert 'Software' in section_names

    def test_generate_filtered_domains(self, generator, sample_stories):
        result = generator.generate(sample_stories, include_domains=['AI'])
        section_names = [s.name for s in result.sections]
        assert section_names == ['AI']

    def test_generate_from_pipeline_output_json(self, generator, tmp_path):
        # Create a mock pipeline output file
        pipeline_data = {
            'stories': [
                {
                    'title': 'Test Story',
                    'summary': 'Test summary',
                    'source': 'Test Source',
                    'tier': 'important',
                    'url': 'https://example.com'
                }
            ]
        }
        output_file = tmp_path / 'pipeline_output.json'
        with open(output_file, 'w') as f:
            json.dump(pipeline_data, f)

        formatted, result = generator.generate_from_pipeline_output(
            output_file,
            BriefingFormat.JSON
        )

        assert result.metadata.total_stories == 1
        assert 'Test Story' in formatted

    def test_generate_from_pipeline_output_clusters(self, generator, tmp_path):
        # Test with clustered output format
        pipeline_data = {
            'clusters': [
                {
                    'stories': [
                        {'title': 'Story 1', 'source': 'Source A'},
                        {'title': 'Story 2', 'source': 'Source B'},
                    ]
                }
            ]
        }
        output_file = tmp_path / 'clusters.json'
        with open(output_file, 'w') as f:
            json.dump(pipeline_data, f)

        formatted, result = generator.generate_from_pipeline_output(
            output_file,
            BriefingFormat.JSON
        )

        assert result.metadata.total_stories == 1
        # Should aggregate sources
        assert result.sections[0].stories[0]['sources'] == ['Source A', 'Source B']


class TestBriefingResult:
    """Test BriefingResult dataclass."""

    def test_to_dict(self):
        meta = BriefingMetadata(
            generated_at="2024-01-01T00:00:00",
            total_stories=1,
            must_read_count=1,
            important_count=0,
            contextual_count=0,
            sources_used=1,
            reading_time_minutes=5
        )
        section = BriefingSection(name='AI', emoji='🤖', stories=[{'title': 'Test'}])
        result = BriefingResult(metadata=meta, sections=[section])

        d = result.to_dict()
        assert d['metadata']['total_stories'] == 1
        assert d['sections'][0]['name'] == 'AI'


class TestDomainClassificationEdgeCases:
    """Test edge cases for domain classification."""

    @pytest.fixture
    def generator(self):
        return BriefingGenerator()

    def test_empty_story(self, generator):
        assert generator.classify_domain({}) == 'General'
        assert generator.classify_domain({'title': ''}) == 'General'

    def test_case_insensitive(self, generator):
        story = {'title': 'GPT-5', 'content': 'OPENAI announcement'}
        assert generator.classify_domain(story) == 'AI'

    def test_multiple_domain_keywords(self, generator):
        # Story with both AI and Software keywords
        story = {
            'title': 'Python ML Library',
            'content': 'New machine learning framework for Python developers'
        }
        # Should pick the domain with most matches
        domain = generator.classify_domain(story)
        assert domain in ['AI', 'Software']


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
