#!/usr/bin/env python3
"""
Relevance Scorer for High-Signal News

Scores articles by relevance, urgency, and importance for the daily briefing.
Uses multiple signals: recency, source quality, entity prominence, and content signals.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from collections import defaultdict


@dataclass
class RelevanceScore:
    """Relevance scoring result for an article."""
    story_id: str
    overall_score: float  # 0-100 composite score

    # Component scores (0-100 each)
    recency_score: float = 0
    source_quality_score: float = 0
    content_quality_score: float = 0
    entity_prominence_score: float = 0
    urgency_signals_score: float = 0

    # Metadata
    ranking_tier: str = ""  # 'must_read', 'important', 'contextual', 'skip'
    explanation: str = ""


class RelevanceScorer:
    """Score articles by relevance for the daily briefing."""

    # Tier thresholds for ranking (score ranges)
    TIER_THRESHOLDS = {
        'must_read': 85,
        'important': 70,
        'contextual': 50,
        'skip': 0,
    }

    # Source quality ratings (0-100)
    SOURCE_QUALITY = {
        'arXiv': 95,
        'Papers with Code': 95,
        'Hugging Face': 90,
        'GitHub Blog': 90,
        'Python Insider': 90,
        'React Blog': 90,
        'Bloomberg': 90,
        'Reuters': 90,
        'Financial Times': 88,
        'The Information': 88,
        'TechCrunch': 80,
        'The Verge': 80,
        'Wired': 85,
        'MIT Technology Review': 90,
        'Nature': 95,
        'Science': 95,
        'Distill': 90,
        'Import AI': 85,
        'The Batch': 85,
        'TLDR Newsletter': 75,
        'Hacker News': 70,
        'Reddit': 60,
        'Unknown': 50,
    }

    # High-value keywords that boost relevance
    HIGH_VALUE_KEYWORDS = {
        'announcement': 10, 'launch': 10, 'release': 8, 'breakthrough': 12,
        'acquisition': 10, 'merger': 10, 'IPO': 12, 'funding': 8,
        'vulnerability': 15, 'CVE': 15, 'security': 10, 'breach': 12,
        'GPT-5': 15, 'GPT-4': 10, 'Claude': 10, 'Gemini': 10,
        'open source': 8, 'open-source': 8,
        'earnings': 10, 'revenue': 8, 'profit': 8, 'guidance': 10,
    }

    # Urgency indicators
    URGENCY_PATTERNS = [
        r'\b(?:urgent|breaking|alert|warning)\b',
        r'\b(?:just announced|just released|breaking news)\b',
        r'\b(?:CVE-\d{4}-\d+)\b',  # Security vulnerabilities
        r'\b(?:zero-day|0-day)\b',
        r'\b(?:critical|severe|high severity)\b',
    ]

    def __init__(self):
        """Initialize the relevance scorer."""
        self.urgency_regex = [re.compile(p, re.IGNORECASE) for p in self.URGENCY_PATTERNS]

    def score_story(self, story: dict) -> RelevanceScore:
        """
        Score a single story by relevance.

        Args:
            story: Story dict with 'id', 'title', 'content', 'source',
                   'domain', 'published_at', 'entities'

        Returns:
            RelevanceScore with component and overall scores
        """
        story_id = story.get('id', 'unknown')
        title = story.get('title', '')
        content = story.get('content', '')
        source = story.get('source', 'Unknown')
        domain = story.get('domain', 'unknown')
        published_at = story.get('published_at')

        # Calculate component scores
        recency = self._score_recency(published_at)
        source_quality = self._score_source(source)
        content_quality = self._score_content_quality(title, content)
        entity_prominence = self._score_entities(story.get('entities', []))
        urgency = self._score_urgency(title, content)

        # Calculate weighted composite score
        weights = {
            'recency': 0.20,
            'source_quality': 0.25,
            'content_quality': 0.20,
            'entity_prominence': 0.20,
            'urgency': 0.15,
        }

        overall = (
            recency * weights['recency'] +
            source_quality * weights['source_quality'] +
            content_quality * weights['content_quality'] +
            entity_prominence * weights['entity_prominence'] +
            urgency * weights['urgency']
        )

        # Determine ranking tier
        tier = self._determine_tier(overall, urgency)

        # Generate explanation
        explanation = self._generate_explanation(
            overall, recency, source_quality, content_quality,
            entity_prominence, urgency
        )

        return RelevanceScore(
            story_id=story_id,
            overall_score=round(overall, 1),
            recency_score=round(recency, 1),
            source_quality_score=round(source_quality, 1),
            content_quality_score=round(content_quality, 1),
            entity_prominence_score=round(entity_prominence, 1),
            urgency_signals_score=round(urgency, 1),
            ranking_tier=tier,
            explanation=explanation
        )

    def _score_recency(self, published_at: Optional[str]) -> float:
        """Score based on how recent the article is."""
        if not published_at:
            return 50.0  # Unknown recency - middle score

        try:
            # Parse various datetime formats
            if 'T' in published_at:
                published = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
            else:
                published = datetime.strptime(published_at, '%Y-%m-%d %H:%M:%S')
                published = published.replace(tzinfo=timezone.utc)

            now = datetime.now(timezone.utc)
            hours_old = (now - published).total_seconds() / 3600

            if hours_old < 1:
                return 100.0
            elif hours_old < 4:
                return 95.0
            elif hours_old < 12:
                return 90.0
            elif hours_old < 24:
                return 85.0
            elif hours_old < 48:
                return 75.0
            elif hours_old < 72:
                return 65.0
            elif hours_old < 168:  # 1 week
                return 50.0
            else:
                return 30.0
        except:
            return 50.0

    def _score_source(self, source: str) -> float:
        """Score based on source quality/reputation."""
        # Direct match
        if source in self.SOURCE_QUALITY:
            return float(self.SOURCE_QUALITY[source])

        # Partial match
        for known_source, quality in self.SOURCE_QUALITY.items():
            if known_source.lower() in source.lower():
                return float(quality)

        return 50.0  # Unknown source

    def _score_content_quality(self, title: str, content: str) -> float:
        """Score based on content quality signals."""
        full_text = f"{title} {content}".lower()
        score = 50.0  # Base score

        # Keyword boosts
        for keyword, boost in self.HIGH_VALUE_KEYWORDS.items():
            if keyword.lower() in full_text:
                score += boost

        # Content length factor (prefer substantial articles)
        content_len = len(content)
        if content_len < 200:
            score -= 10
        elif 500 <= content_len <= 3000:
            score += 10
        elif content_len > 5000:
            score += 5  # Very long might be too detailed

        # Title quality signals
        if any(w in title.lower() for w in ['how', 'why', 'what', 'analysis']):
            score += 5  # Analytical content

        if re.search(r'\d+', title):
            score += 3  # Has data/numbers

        return min(100, max(0, score))

    def _score_entities(self, entities: list) -> float:
        """Score based on prominence of mentioned entities."""
        if not entities:
            return 50.0

        # Count high-prominence entities
        score = 50.0

        for entity in entities:
            entity_type = getattr(entity, 'entity_type', '')
            confidence = getattr(entity, 'confidence', 0.5)
            mention_count = getattr(entity, 'mention_count', 1)

            # Companies and technologies get higher scores
            if entity_type in ('company', 'technology'):
                score += confidence * 10 * min(mention_count, 3)
            elif entity_type == 'person':
                score += confidence * 5 * min(mention_count, 2)

        return min(100, score)

    def _score_urgency(self, title: str, content: str) -> float:
        """Score based on urgency signals in content."""
        full_text = f"{title} {content}"
        score = 0.0

        for pattern in self.urgency_regex:
            matches = pattern.findall(full_text)
            score += len(matches) * 20

        # Cap at 100
        return min(100, score)

    def _determine_tier(self, overall_score: float, urgency_score: float) -> str:
        """Determine the ranking tier for a story."""
        if urgency_score >= 70 or overall_score >= 85:
            return 'must_read'
        elif overall_score >= 70:
            return 'important'
        elif overall_score >= 50:
            return 'contextual'
        else:
            return 'skip'

    def _generate_explanation(self, overall: float, recency: float,
                              source: float, content: float,
                              entities: float, urgency: float) -> str:
        """Generate human-readable explanation of scores."""
        factors = []

        if urgency >= 70:
            factors.append("urgent/breaking")
        if recency >= 85:
            factors.append("very recent")
        if source >= 80:
            factors.append("high-quality source")
        if content >= 75:
            factors.append("high-value content")
        if entities >= 70:
            factors.append("prominent entities")

        if factors:
            return f"High relevance due to: {', '.join(factors)}"
        elif overall < 50:
            return "Lower relevance: older content or lower-priority source"
        else:
            return "Moderate relevance across all signals"

    def rank_stories(self, stories: list[dict]) -> list[tuple[dict, RelevanceScore]]:
        """
        Rank a list of stories by relevance.

        Args:
            stories: List of story dicts

        Returns:
            List of (story, score) tuples sorted by overall_score descending
        """
        scored = [(story, self.score_story(story)) for story in stories]
        scored.sort(key=lambda x: x[1].overall_score, reverse=True)
        return scored

    def filter_for_briefing(self, stories: list[dict],
                           max_stories: int = 15,
                           min_score: float = 45.0) -> list[dict]:
        """
        Filter stories for inclusion in the daily briefing.

        Args:
            stories: List of story dicts
            max_stories: Maximum number of stories to include
            min_score: Minimum relevance score for inclusion

        Returns:
            Filtered and ranked list of stories
        """
        ranked = self.rank_stories(stories)

        # Filter by minimum score and tier
        filtered = [
            story for story, score in ranked
            if score.overall_score >= min_score and score.ranking_tier != 'skip'
        ]

        return filtered[:max_stories]

    def filter_by_tier(self, scores: list[RelevanceScore],
                       tiers: list[str]) -> list[RelevanceScore]:
        """
        Filter relevance scores by ranking tier.

        Args:
            scores: List of RelevanceScore objects
            tiers: List of tiers to include (e.g., ['must_read', 'important'])

        Returns:
            Filtered list of RelevanceScore objects
        """
        return [score for score in scores if score.ranking_tier in tiers]

    def score_all_stories(self, stories: list[dict]) -> dict[str, RelevanceScore]:
        """
        Batch score multiple stories and return as a dict.

        Args:
            stories: List of story dicts

        Returns:
            Dict mapping story_id to RelevanceScore
        """
        return {story.get('id', 'unknown'): self.score_story(story) for story in stories}


def calculate_domain_distribution(stories: list[dict]) -> dict[str, int]:
    """Calculate distribution of stories across domains."""
    distribution = defaultdict(int)
    for story in stories:
        domain = story.get('domain', 'unknown')
        distribution[domain] += 1
    return dict(distribution)


if __name__ == "__main__":
    # Test the scorer
    test_stories = [
        {
            'id': '1',
            'title': 'OpenAI Announces GPT-5 with Breakthrough Capabilities',
            'content': 'OpenAI announced GPT-5 today featuring significant improvements in reasoning and code generation.',
            'source': 'TechCrunch',
            'domain': 'ai',
            'published_at': '2026-03-21T10:00:00Z',
            'entities': [
                type('Entity', (), {'name': 'OpenAI', 'entity_type': 'company', 'confidence': 0.9, 'mention_count': 2})(),
                type('Entity', (), {'name': 'GPT-5', 'entity_type': 'technology', 'confidence': 0.95, 'mention_count': 1})(),
            ]
        },
        {
            'id': '2',
            'title': 'Critical Security Vulnerability Found in Python Package',
            'content': 'A critical CVE has been identified in a popular Python library. Users should upgrade immediately.',
            'source': 'Python Insider',
            'domain': 'software_development',
            'published_at': '2026-03-21T09:30:00Z',
            'entities': []
        },
        {
            'id': '3',
            'title': 'Weekly Tech Roundup: Various Updates',
            'content': 'A summary of minor updates from various tech companies this week.',
            'source': 'Unknown Blog',
            'domain': 'ai',
            'published_at': '2026-03-18T12:00:00Z',
            'entities': []
        }
    ]

    scorer = RelevanceScorer()

    print("Story Relevance Scores:")
    print("-" * 80)

    for story in test_stories:
        score = scorer.score_story(story)
        print(f"\n{story['title']}")
        print(f"  Source: {story['source']} | Domain: {story['domain']}")
        print(f"  Overall: {score.overall_score} | Tier: {score.ranking_tier}")
        print(f"  Recency: {score.recency_score} | Source: {score.source_quality_score} | "
              f"Content: {score.content_quality_score}")
        print(f"  Urgency: {score.urgency_signals_score}")
        print(f"  {score.explanation}")

    # Test ranking
    print("\n" + "=" * 80)
    print("RANKED STORIES:")
    print("=" * 80)

    ranked = scorer.rank_stories(test_stories)
    for i, (story, score) in enumerate(ranked, 1):
        print(f"{i}. [{score.ranking_tier.upper()}] {story['title']} (Score: {score.overall_score})")
