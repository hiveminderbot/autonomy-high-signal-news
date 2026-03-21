"""
Summarization Engine for High-Signal News

Phase 3 components:
- story_clusterer: Cluster related stories by similarity
- entity_extractor: Extract key entities and topics
- content_summarizer: Generate concise summaries
- relevance_scorer: Score articles by relevance and urgency
"""

from .story_clusterer import StoryClusterer, ClusterResult, StoryCluster
from .entity_extractor import EntityExtractor, ExtractedEntity
from .content_summarizer import ContentSummarizer, SummaryResult
from .relevance_scorer import RelevanceScorer, RelevanceScore

__all__ = [
    'StoryClusterer', 'ClusterResult', 'StoryCluster',
    'EntityExtractor', 'ExtractedEntity',
    'ContentSummarizer', 'SummaryResult',
    'RelevanceScorer', 'RelevanceScore',
]
