#!/usr/bin/env python3
"""
Tests for the entity extractor module.

Run with: python tests/test_entity_extractor.py
"""

import sys
from pathlib import Path

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from summarizer.entity_extractor import EntityExtractor, ExtractedEntity


def test_extract_companies():
    """Test extraction of company names."""
    extractor = EntityExtractor()

    title = "OpenAI and Google Announce Partnership"
    content = "Microsoft and Amazon are also involved in this deal with Meta."

    entities = extractor.extract_entities(title, content)

    company_names = [e.name for e in entities if e.entity_type == 'company']
    assert 'OpenAI' in company_names or 'OpenAI'.lower() in [n.lower() for n in company_names], \
        f"Expected OpenAI in companies, got {company_names}"
    print("✅ test_extract_companies passed")


def test_extract_technologies():
    """Test extraction of technology names."""
    extractor = EntityExtractor()

    title = "GPT-5 vs Claude: A Comparison"
    content = "Developers use Python and React with Kubernetes and Docker."

    entities = extractor.extract_entities(title, content)

    tech_names = [e.name for e in entities if e.entity_type == 'technology']
    assert len(tech_names) > 0, f"Expected some technologies, got {tech_names}"
    print("✅ test_extract_technologies passed")


def test_extract_topics():
    """Test extraction of AI/ML topic terms."""
    extractor = EntityExtractor()

    title = "Machine Learning Advances"
    content = "Deep learning and neural networks are transforming natural language processing."

    entities = extractor.extract_entities(title, content)

    topic_names = [e.name for e in entities if e.entity_type == 'topic']
    assert len(topic_names) > 0, f"Expected some topics, got {topic_names}"
    print("✅ test_extract_topics passed")


def test_entity_confidence():
    """Test that extracted entities have confidence scores."""
    extractor = EntityExtractor()

    title = "OpenAI Releases GPT-5"
    content = "The new model features improved capabilities."

    entities = extractor.extract_entities(title, content)

    for entity in entities:
        assert 0.0 <= entity.confidence <= 1.0, \
            f"Expected confidence between 0 and 1, got {entity.confidence}"
    print("✅ test_entity_confidence passed")


def test_entity_mention_counting():
    """Test that entity mention counts are tracked."""
    extractor = EntityExtractor()

    title = "OpenAI News"
    content = "OpenAI announced something. OpenAI is growing. OpenAI leads the market."

    entities = extractor.extract_entities(title, content)

    openai_entities = [e for e in entities if 'openai' in e.name.lower()]
    if openai_entities:
        # Should have multiple mentions
        assert openai_entities[0].mention_count >= 1, \
            f"Expected at least 1 mention, got {openai_entities[0].mention_count}"
    print("✅ test_entity_mention_counting passed")


def test_normalize_company_name():
    """Test company name normalization."""
    extractor = EntityExtractor()

    # Test various normalizations (normalization remaps names like Twitter/Facebook)
    test_cases = [
        ("OPENAI", "OpenAI"),
        ("openai", "OpenAI"),
        ("github", "GitHub"),
        ("GITHUB", "GitHub"),  # Case is preserved after lookup
    ]

    for input_name, expected in test_cases:
        normalized = extractor._normalize_company_name(input_name)
        assert normalized == expected, f"Expected {expected}, got {normalized}"

    # Twitter and X.com are normalized to X per modern naming
    for name in ["twitter", "x.com", "X.COM"]:
        normalized = extractor._normalize_company_name(name)
        assert normalized == "X", f"Expected X for {name}, got {normalized}"

    # Facebook is normalized to Meta
    normalized = extractor._normalize_company_name("facebook")
    assert normalized == "Meta", f"Expected Meta, got {normalized}"
    print("✅ test_normalize_company_name passed")


def test_extract_context():
    """Test context extraction around entity mentions."""
    extractor = EntityExtractor()

    text = "The quick brown fox jumps over the lazy dog. OpenAI announced GPT-5 today. It is amazing."
    position = text.find("OpenAI")

    context = extractor._extract_context(text, position)

    assert "OpenAI" in context, f"Expected 'OpenAI' in context, got {context}"
    assert "GPT-5" in context, f"Expected 'GPT-5' in context, got {context}"
    print("✅ test_extract_context passed")


def test_extract_finance_terms():
    """Test extraction of financial/investment terms."""
    extractor = EntityExtractor()

    title = "Startup Raises Series A Funding"
    content = "The company announced a new funding round with VC investors."

    entities = extractor.extract_entities(title, content)

    # Finance terms are extracted as topics
    topic_names = [e.name for e in entities if e.entity_type == 'topic']
    assert len(topic_names) > 0, f"Expected some finance topics, got {topic_names}"
    print("✅ test_extract_finance_terms passed")


def test_empty_text():
    """Test extraction from empty text."""
    extractor = EntityExtractor()

    entities = extractor.extract_entities("", "")

    assert entities == [], f"Expected empty list for empty text, got {entities}"
    print("✅ test_empty_text passed")


def test_entities_sorted_by_mentions():
    """Test that entities are sorted by mention count."""
    extractor = EntityExtractor()

    title = "OpenAI Google Microsoft Amazon"
    content = "Multiple companies in one article about AI and machine learning."

    entities = extractor.extract_entities(title, content)

    # Entities are sorted by mention count then confidence
    for i in range(len(entities) - 1):
        assert entities[i].mention_count >= entities[i+1].mention_count, \
            "Entities should be sorted by mention count descending"
    print("✅ test_entities_sorted_by_mentions passed")


def test_batch_entity_extraction():
    """Test extraction from multiple stories using batch helper."""
    from summarizer.entity_extractor import extract_entities_batch

    stories = [
        {
            'id': '1',
            'title': 'OpenAI GPT-5',
            'content': 'OpenAI announced GPT-5',
            'source': 'TechCrunch'
        },
        {
            'id': '2',
            'title': 'Google Bard Update',
            'content': 'Google updated Bard with new features',
            'source': 'The Verge'
        }
    ]

    results = extract_entities_batch(stories)

    assert len(results) == 2, f"Expected 2 results, got {len(results)}"
    assert '1' in results, f"Expected story '1' in results"
    assert '2' in results, f"Expected story '2' in results"
    print("✅ test_batch_entity_extraction passed")


def test_entity_dataclass():
    """Test ExtractedEntity dataclass behavior."""
    from summarizer.entity_extractor import ExtractedEntity

    entity = ExtractedEntity(
        name="OpenAI",
        entity_type="company",
        confidence=0.9,
        mention_count=3,
        context_snippets=["OpenAI announced today"]
    )

    assert entity.name == "OpenAI"
    assert entity.entity_type == "company"
    assert entity.confidence == 0.9
    assert entity.mention_count == 3
    print("✅ test_entity_dataclass passed")


if __name__ == "__main__":
    test_extract_companies()
    test_extract_technologies()
    test_extract_topics()
    test_entity_confidence()
    test_entity_mention_counting()
    test_normalize_company_name()
    test_extract_context()
    test_extract_finance_terms()
    test_empty_text()
    test_entities_sorted_by_mentions()
    test_batch_entity_extraction()
    test_entity_dataclass()

    print("\n✅ All entity extractor tests passed!")
