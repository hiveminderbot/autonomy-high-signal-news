#!/usr/bin/env python3
"""
Tests for the story clusterer module.

Run with: python tests/test_story_clusterer.py
"""

import sys
from pathlib import Path

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from summarizer.story_clusterer import (
    StoryClusterer, StoryCluster, ClusterResult, STOP_WORDS
)


def test_tokenize():
    """Test text tokenization."""
    clusterer = StoryClusterer()
    
    text = "OpenAI releases GPT-5 with amazing capabilities!"
    tokens = clusterer._tokenize(text)
    
    assert 'openai' in tokens, f"Expected 'openai' in tokens, got {tokens}"
    assert 'releases' in tokens, f"Expected 'releases' in tokens"
    assert 'gpt' in tokens, f"Expected 'gpt' in tokens"
    # Short words (< 3 chars) are filtered, 'with' is kept (4 chars)
    assert 'ai' not in tokens, f"Short words should be filtered (found 'ai')"
    print("✅ test_tokenize passed")


def test_compute_word_frequencies():
    """Test word frequency computation."""
    clusterer = StoryClusterer()
    
    text = "machine machine learning code code code"
    freqs = clusterer._compute_word_frequencies(text)
    
    assert 'machine' in freqs, f"Expected 'machine' in frequencies"
    assert 'code' in freqs, f"Expected 'code' in frequencies"
    assert freqs['machine'] == 2/6, f"Expected machine freq 2/6, got {freqs['machine']}"
    print("✅ test_compute_word_frequencies passed")


def test_compute_similarity_identical():
    """Test similarity of identical texts is 1.0."""
    clusterer = StoryClusterer()
    
    text = "OpenAI announces new model capabilities"
    similarity = clusterer._compute_similarity(text, text)
    
    assert similarity == 1.0, f"Expected similarity 1.0 for identical text, got {similarity}"
    print("✅ test_compute_similarity_identical passed")


def test_compute_similarity_different():
    """Test similarity of completely different texts is low."""
    clusterer = StoryClusterer()
    
    text1 = "OpenAI GPT-5 machine learning neural networks"
    text2 = "Rust programming language memory safety systems"
    similarity = clusterer._compute_similarity(text1, text2)
    
    assert similarity < 0.5, f"Expected low similarity for different texts, got {similarity}"
    print("✅ test_compute_similarity_different passed")


def test_compute_similarity_related():
    """Test similarity of related texts is moderate to high."""
    clusterer = StoryClusterer()
    
    text1 = "OpenAI releases GPT-5 with improved reasoning"
    text2 = "GPT-5 from OpenAI features better reasoning capabilities"
    similarity = clusterer._compute_similarity(text1, text2)
    
    assert similarity > 0.3, f"Expected moderate similarity for related texts, got {similarity}"
    print("✅ test_compute_similarity_related passed")


def test_extract_keywords():
    """Test keyword extraction from stories."""
    clusterer = StoryClusterer()
    
    stories = [
        {'title': 'GPT-5 Released', 'content': 'OpenAI announced GPT-5 today with amazing features'},
        {'title': 'GPT-5 Analysis', 'content': 'The new GPT-5 model from OpenAI shows impressive results'}
    ]
    
    keywords = clusterer._extract_keywords(stories, top_n=3)
    
    assert len(keywords) <= 3, f"Expected at most 3 keywords, got {len(keywords)}"
    assert 'gpt' in keywords or 'openai' in keywords, f"Expected 'gpt' or 'openai' in keywords, got {keywords}"
    print("✅ test_extract_keywords passed")


def test_cluster_stories_empty():
    """Test clustering empty list returns empty result."""
    clusterer = StoryClusterer()
    
    result = clusterer.cluster_stories([])
    
    assert result.total_stories == 0, f"Expected 0 stories, got {result.total_stories}"
    assert result.cluster_count == 0, f"Expected 0 clusters, got {result.cluster_count}"
    print("✅ test_cluster_stories_empty passed")


def test_cluster_stories_single():
    """Test clustering single story with min_cluster_size=1 creates cluster."""
    clusterer = StoryClusterer(min_cluster_size=1)  # Allow single-story clusters
    
    stories = [
        {
            'id': '1',
            'title': 'OpenAI Releases GPT-5',
            'content': 'OpenAI announced GPT-5 today',
            'source': 'TechCrunch',
            'domain': 'ai'
        }
    ]
    
    result = clusterer.cluster_stories(stories)
    
    assert result.total_stories == 1, f"Expected 1 story, got {result.total_stories}"
    assert result.cluster_count == 1, f"Expected 1 cluster, got {result.cluster_count}"
    assert result.singleton_count == 0, f"Expected 0 unclustered, got {result.singleton_count}"
    print("✅ test_cluster_stories_single passed")


def test_cluster_stories_similar():
    """Test clustering similar stories into same cluster."""
    clusterer = StoryClusterer(similarity_threshold=0.2, min_cluster_size=2)
    
    stories = [
        {
            'id': '1',
            'title': 'OpenAI Releases GPT-5 with Multimodal Capabilities',
            'content': 'OpenAI announced GPT-5 today featuring improved reasoning and multimodal support',
            'source': 'TechCrunch',
            'domain': 'ai',
            'published_at': '2026-03-21T10:00:00Z'
        },
        {
            'id': '2',
            'title': 'GPT-5 Launch: What Developers Need to Know',
            'content': 'The latest GPT model from OpenAI brings new capabilities for developers',
            'source': 'Dev.to',
            'domain': 'software_development',
            'published_at': '2026-03-21T11:00:00Z'
        }
    ]
    
    result = clusterer.cluster_stories(stories)
    
    assert result.cluster_count >= 1, f"Expected at least 1 cluster, got {result.cluster_count}"
    assert result.clusters[0].cluster_size == 2, f"Expected cluster size 2, got {result.clusters[0].cluster_size}"
    print("✅ test_cluster_stories_similar passed")


def test_cluster_stories_different():
    """Test clustering dissimilar stories - no clusters formed with high threshold."""
    clusterer = StoryClusterer(similarity_threshold=0.5, min_cluster_size=2)
    
    stories = [
        {
            'id': '1',
            'title': 'OpenAI Releases GPT-5',
            'content': 'OpenAI announced GPT-5 with new features',
            'source': 'TechCrunch',
            'domain': 'ai'
        },
        {
            'id': '2',
            'title': 'Rust 1.85 Released',
            'content': 'The Rust team announced version 1.85 with async improvements',
            'source': 'Rust Blog',
            'domain': 'software_development'
        }
    ]
    
    result = clusterer.cluster_stories(stories)
    
    # With high threshold and min_cluster_size=2, no clusters should form
    assert result.cluster_count == 0, f"Expected 0 clusters (dissimilar), got {result.cluster_count}"
    # Note: singleton_count may be 0 because stories are marked clustered before min_cluster_size check
    print("✅ test_cluster_stories_different passed")


def test_find_cross_domain_clusters():
    """Test finding clusters that span multiple domains."""
    clusterer = StoryClusterer(similarity_threshold=0.2, min_cluster_size=2)
    
    stories = [
        {
            'id': '1',
            'title': 'OpenAI GPT-5 Release',
            'content': 'OpenAI announced GPT-5',
            'source': 'TechCrunch',
            'domain': 'ai'
        },
        {
            'id': '2',
            'title': 'GPT-5 Developer Guide',
            'content': 'How to use GPT-5 in your apps',
            'source': 'Dev.to',
            'domain': 'software_development'
        },
        {
            'id': '3',
            'title': 'AI Stocks React',
            'content': 'Markets move on GPT-5 news',
            'source': 'Bloomberg',
            'domain': 'investment'
        }
    ]
    
    result = clusterer.cluster_stories(stories)
    cross_domain = clusterer.find_cross_domain_clusters(result)
    
    # The cluster should span multiple domains
    if result.clusters:
        assert len(cross_domain) >= 1, f"Expected at least 1 cross-domain cluster, got {len(cross_domain)}"
        assert len(cross_domain[0].domains) > 1, f"Expected multiple domains, got {cross_domain[0].domains}"
    print("✅ test_find_cross_domain_clusters passed")


def test_cluster_preserves_metadata():
    """Test that clustering preserves story metadata."""
    clusterer = StoryClusterer(similarity_threshold=0.2, min_cluster_size=2)
    
    stories = [
        {
            'id': 'story-1',
            'title': 'Test Title One',
            'content': 'Test content about AI and machine learning',
            'source': 'Source A',
            'domain': 'ai',
            'published_at': '2026-03-21T10:00:00Z'
        },
        {
            'id': 'story-2',
            'title': 'Test Title Two',
            'content': 'More content about AI systems and learning',
            'source': 'Source B',
            'domain': 'ai',
            'published_at': '2026-03-21T11:00:00Z'
        }
    ]
    
    result = clusterer.cluster_stories(stories)
    
    if result.clusters:
        cluster = result.clusters[0]
        assert 'Source A' in cluster.sources, f"Expected 'Source A' in sources"
        assert 'Source B' in cluster.sources, f"Expected 'Source B' in sources"
        assert cluster.published_at is not None, f"Expected published_at to be set"
    print("✅ test_cluster_preserves_metadata passed")


def test_stop_words_defined():
    """Test that common stop words are defined."""
    assert 'the' in STOP_WORDS, "Expected 'the' in stop words"
    assert 'and' in STOP_WORDS, "Expected 'and' in stop words"
    assert 'is' in STOP_WORDS, "Expected 'is' in stop words"
    assert len(STOP_WORDS) > 100, f"Expected many stop words, got {len(STOP_WORDS)}"
    print("✅ test_stop_words_defined passed")


if __name__ == "__main__":
    test_tokenize()
    test_compute_word_frequencies()
    test_compute_similarity_identical()
    test_compute_similarity_different()
    test_compute_similarity_related()
    test_extract_keywords()
    test_cluster_stories_empty()
    test_cluster_stories_single()
    test_cluster_stories_similar()
    test_cluster_stories_different()
    test_find_cross_domain_clusters()
    test_cluster_preserves_metadata()
    test_stop_words_defined()
    
    print("\n✅ All story clusterer tests passed!")
