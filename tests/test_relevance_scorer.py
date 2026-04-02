#!/usr/bin/env python3
"""
Tests for the relevance scorer module.

Run with: python tests/test_relevance_scorer.py
"""

import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from summarizer.relevance_scorer import RelevanceScorer, RelevanceScore


def test_source_quality_lookup():
    """Test source quality rating lookup."""
    scorer = RelevanceScorer()

    # Test known sources
    assert scorer.SOURCE_QUALITY['arXiv'] == 95, "Expected arXiv quality 95"
    assert scorer.SOURCE_QUALITY['Bloomberg'] == 90, "Expected Bloomberg quality 90"
    assert scorer.SOURCE_QUALITY['Unknown'] == 50, "Expected Unknown quality 50"
    print("✅ test_source_quality_lookup passed")


def test_score_story_basic():
    """Test basic story scoring."""
    scorer = RelevanceScorer()

    story = {
        'id': 'test-1',
        'title': 'OpenAI Releases GPT-5',
        'content': 'OpenAI announced GPT-5 today with new features.',
        'source': 'TechCrunch',
        'domain': 'ai',
        'published_at': datetime.now(timezone.utc).isoformat(),
        'entities': []
    }

    result = scorer.score_story(story)

    assert isinstance(result, RelevanceScore), f"Expected RelevanceScore"
    assert result.story_id == 'test-1', f"Expected story_id 'test-1'"
    assert result.overall_score > 0, f"Expected positive overall score"
    print("✅ test_score_story_basic passed")


def test_recency_scoring():
    """Test that recent stories get higher recency scores."""
    scorer = RelevanceScorer()

    now = datetime.now(timezone.utc)

    recent_story = {
        'id': 'recent',
        'title': 'Just Announced',
        'content': 'Content here.',
        'source': 'TechCrunch',
        'published_at': now.isoformat()
    }

    old_story = {
        'id': 'old',
        'title': 'Old News',
        'content': 'Content here.',
        'source': 'TechCrunch',
        'published_at': (now - timedelta(days=7)).isoformat()
    }

    recent_score = scorer.score_story(recent_story)
    old_score = scorer.score_story(old_story)

    assert recent_score.recency_score > old_score.recency_score, \
        f"Recent story should have higher recency score"
    print("✅ test_recency_scoring passed")


def test_source_quality_scoring():
    """Test that high-quality sources get higher scores."""
    scorer = RelevanceScorer()

    high_quality = {
        'id': 'hq',
        'title': 'Important News',
        'content': 'Content here.',
        'source': 'arXiv',
        'published_at': datetime.now(timezone.utc).isoformat()
    }

    low_quality = {
        'id': 'lq',
        'title': 'Important News',
        'content': 'Content here.',
        'source': 'Reddit',
        'published_at': datetime.now(timezone.utc).isoformat()
    }

    hq_score = scorer.score_story(high_quality)
    lq_score = scorer.score_story(low_quality)

    assert hq_score.source_quality_score > lq_score.source_quality_score, \
        f"High quality source should have higher source quality score"
    print("✅ test_source_quality_scoring passed")


def test_urgency_detection():
    """Test detection of urgency signals in content."""
    scorer = RelevanceScorer()

    urgent_story = {
        'id': 'urgent',
        'title': 'Breaking: Security Vulnerability Found',
        'content': 'A critical CVE-2024-1234 vulnerability has been discovered.',
        'source': 'TechCrunch',
        'published_at': datetime.now(timezone.utc).isoformat()
    }

    normal_story = {
        'id': 'normal',
        'title': 'Regular Tech Update',
        'content': 'Here is some normal technology news.',
        'source': 'TechCrunch',
        'published_at': datetime.now(timezone.utc).isoformat()
    }

    urgent_score = scorer.score_story(urgent_story)
    normal_score = scorer.score_story(normal_story)

    assert urgent_score.urgency_signals_score > normal_score.urgency_signals_score, \
        f"Urgent story should have higher urgency score"
    print("✅ test_urgency_detection passed")


def test_keyword_boost():
    """Test that high-value keywords boost content score."""
    scorer = RelevanceScorer()

    announcement = {
        'id': 'announce',
        'title': 'Company Announces New Product Launch',
        'content': 'The company announced a breakthrough today.',
        'source': 'TechCrunch',
        'published_at': datetime.now(timezone.utc).isoformat()
    }

    boring = {
        'id': 'boring',
        'title': 'Quarterly Report Published',
        'content': 'The quarterly report is now available.',
        'source': 'TechCrunch',
        'published_at': datetime.now(timezone.utc).isoformat()
    }

    announcement_score = scorer.score_story(announcement)
    boring_score = scorer.score_story(boring)

    assert announcement_score.content_quality_score > boring_score.content_quality_score, \
        f"Story with high-value keywords should have higher content score"
    print("✅ test_keyword_boost passed")


def test_ranking_tier_assignment():
    """Test that appropriate ranking tiers are assigned."""
    scorer = RelevanceScorer()

    # High quality, urgent, recent story
    must_read = {
        'id': 'must',
        'title': 'Breaking: Critical Security Vulnerability CVE-2024-1234',
        'content': 'A critical vulnerability has been found in production systems.',
        'source': 'arXiv',
        'published_at': datetime.now(timezone.utc).isoformat()
    }

    result = scorer.score_story(must_read)

    assert result.ranking_tier in ['must_read', 'important'], \
        f"Expected high-tier ranking, got {result.ranking_tier}"
    print("✅ test_ranking_tier_assignment passed")


def test_rank_stories():
    """Test batch ranking of multiple stories."""
    scorer = RelevanceScorer()

    stories = [
        {
            'id': '1',
            'title': 'Regular News',
            'content': 'Some content here.',
            'source': 'Reddit',
            'published_at': (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
        },
        {
            'id': '2',
            'title': 'Breaking: Major Announcement',
            'content': 'OpenAI announced GPT-5 today!',
            'source': 'TechCrunch',
            'published_at': datetime.now(timezone.utc).isoformat()
        }
    ]

    ranked = scorer.rank_stories(stories)

    assert len(ranked) == 2, f"Expected 2 ranked stories, got {len(ranked)}"

    # rank_stories returns tuples of (story_id, RelevanceScore)
    assert ranked[0][1].overall_score >= ranked[1][1].overall_score, \
        f"Stories should be sorted by score descending"
    print("✅ test_rank_stories passed")


def test_filter_by_tier():
    """Test filtering stories by ranking tier."""
    scorer = RelevanceScorer()

    scores = [
        RelevanceScore(story_id='1', overall_score=90, ranking_tier='must_read'),
        RelevanceScore(story_id='2', overall_score=70, ranking_tier='important'),
        RelevanceScore(story_id='3', overall_score=40, ranking_tier='contextual'),
        RelevanceScore(story_id='4', overall_score=10, ranking_tier='skip'),
    ]

    must_read_only = scorer.filter_by_tier(scores, ['must_read'])
    assert len(must_read_only) == 1, f"Expected 1 must_read, got {len(must_read_only)}"
    assert must_read_only[0].story_id == '1'

    important_and_above = scorer.filter_by_tier(scores, ['must_read', 'important'])
    assert len(important_and_above) == 2, f"Expected 2 stories, got {len(important_and_above)}"
    print("✅ test_filter_by_tier passed")


def test_tier_thresholds():
    """Test that tier thresholds are properly configured."""
    scorer = RelevanceScorer()

    # Verify thresholds exist and are reasonable
    assert scorer.TIER_THRESHOLDS['must_read'] > scorer.TIER_THRESHOLDS['important']
    assert scorer.TIER_THRESHOLDS['important'] > scorer.TIER_THRESHOLDS['contextual']
    assert scorer.TIER_THRESHOLDS['contextual'] > scorer.TIER_THRESHOLDS['skip']
    print("✅ test_tier_thresholds passed")


def test_empty_story():
    """Test scoring an empty/minimal story."""
    scorer = RelevanceScorer()

    empty_story = {
        'id': 'empty',
        'title': '',
        'content': '',
        'source': 'Unknown'
    }

    result = scorer.score_story(empty_story)

    assert isinstance(result, RelevanceScore), f"Expected RelevanceScore even for empty story"
    assert result.overall_score >= 0, f"Expected non-negative score"
    print("✅ test_empty_story passed")


def test_explanation_generation():
    """Test that scoring generates explanations."""
    scorer = RelevanceScorer()

    story = {
        'id': 'test',
        'title': 'OpenAI GPT-5 Launch Announcement',
        'content': 'Breaking news about GPT-5 release.',
        'source': 'TechCrunch',
        'published_at': datetime.now(timezone.utc).isoformat()
    }

    result = scorer.score_story(story)

    assert result.explanation != "", f"Expected non-empty explanation"
    assert len(result.explanation) > 10, f"Expected meaningful explanation"
    print("✅ test_explanation_generation passed")


def test_score_all_stories():
    """Test batch scoring convenience method."""
    scorer = RelevanceScorer()

    stories = [
        {'id': '1', 'title': 'Story One', 'content': 'Content', 'source': 'TechCrunch'},
        {'id': '2', 'title': 'Story Two', 'content': 'Content', 'source': 'The Verge'},
    ]

    results = scorer.score_all_stories(stories)

    assert len(results) == 2, f"Expected 2 results, got {len(results)}"
    assert '1' in results, f"Expected story '1' in results"
    assert '2' in results, f"Expected story '2' in results"
    print("✅ test_score_all_stories passed")


if __name__ == "__main__":
    test_source_quality_lookup()
    test_score_story_basic()
    test_recency_scoring()
    test_source_quality_scoring()
    test_urgency_detection()
    test_keyword_boost()
    test_ranking_tier_assignment()
    test_rank_stories()
    test_filter_by_tier()
    test_tier_thresholds()
    test_empty_story()
    test_explanation_generation()
    test_score_all_stories()

    print("\n✅ All relevance scorer tests passed!")
