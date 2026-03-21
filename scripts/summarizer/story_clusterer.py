#!/usr/bin/env python3
"""
Story Clusterer for High-Signal News

Clusters related news stories using TF-IDF and cosine similarity.
Groups articles covering the same event or topic from different sources.
"""

import re
from dataclasses import dataclass, field
from typing import Optional
from collections import defaultdict


@dataclass
class StoryCluster:
    """A cluster of related stories."""
    id: str
    stories: list = field(default_factory=list)
    representative_title: str = ""
    representative_summary: str = ""
    keywords: list = field(default_factory=list)
    sources: list = field(default_factory=list)
    domains: list = field(default_factory=list)
    published_at: Optional[str] = None
    cluster_size: int = 0


@dataclass
class ClusterResult:
    """Result of clustering operation."""
    clusters: list[StoryCluster] = field(default_factory=list)
    unclustered: list[dict] = field(default_factory=list)
    total_stories: int = 0
    cluster_count: int = 0
    singleton_count: int = 0


class StoryClusterer:
    """Cluster related news stories by content similarity."""
    
    def __init__(self, similarity_threshold: float = 0.35, min_cluster_size: int = 2):
        """
        Initialize the clusterer.
        
        Args:
            similarity_threshold: Minimum cosine similarity to consider stories related (0-1)
            min_cluster_size: Minimum number of stories to form a cluster
        """
        self.similarity_threshold = similarity_threshold
        self.min_cluster_size = min_cluster_size
        
    def _tokenize(self, text: str) -> list[str]:
        """Simple tokenization for similarity comparison."""
        # Lowercase and extract words
        text = text.lower()
        # Keep alphanumeric and spaces
        text = re.sub(r'[^a-z0-9\s]', ' ', text)
        # Split and filter short words
        words = [w for w in text.split() if len(w) > 2]
        return words
    
    def _compute_word_frequencies(self, text: str) -> dict[str, float]:
        """Compute normalized word frequencies for a document."""
        words = self._tokenize(text)
        if not words:
            return {}
        
        freq = defaultdict(int)
        for word in words:
            freq[word] += 1
        
        # Normalize by document length
        total = len(words)
        return {word: count / total for word, count in freq.items()}
    
    def _compute_similarity(self, text1: str, text2: str) -> float:
        """
        Compute cosine similarity between two texts using word frequencies.
        
        Returns similarity score between 0 and 1.
        """
        # Combine title and content for comparison
        freq1 = self._compute_word_frequencies(text1)
        freq2 = self._compute_word_frequencies(text2)
        
        if not freq1 or not freq2:
            return 0.0
        
        # Get all unique words
        all_words = set(freq1.keys()) | set(freq2.keys())
        
        # Compute dot product
        dot_product = sum(freq1.get(word, 0) * freq2.get(word, 0) for word in all_words)
        
        # Compute magnitudes
        mag1 = sum(f ** 2 for f in freq1.values()) ** 0.5
        mag2 = sum(f ** 2 for f in freq2.values()) ** 0.5
        
        if mag1 == 0 or mag2 == 0:
            return 0.0
        
        return dot_product / (mag1 * mag2)
    
    def _extract_keywords(self, stories: list[dict], top_n: int = 5) -> list[str]:
        """Extract top keywords from a cluster of stories."""
        # Combine all text
        all_text = " ".join([
            f"{s.get('title', '')} {s.get('content', '')}"
            for s in stories
        ])
        
        words = self._tokenize(all_text)
        
        # Count word frequencies
        freq = defaultdict(int)
        for word in words:
            # Skip common stop words
            if word not in STOP_WORDS:
                freq[word] += 1
        
        # Return top N by frequency
        sorted_words = sorted(freq.items(), key=lambda x: x[1], reverse=True)
        return [word for word, _ in sorted_words[:top_n]]
    
    def cluster_stories(self, stories: list[dict]) -> ClusterResult:
        """
        Cluster stories by content similarity.
        
        Args:
            stories: List of story dicts with 'id', 'title', 'content', 'source', 'domain'
        
        Returns:
            ClusterResult with clusters and unclustered stories
        """
        if not stories:
            return ClusterResult()
        
        # Track which stories have been clustered
        clustered = set()
        clusters = []
        
        # Build similarity graph
        for i, story_i in enumerate(stories):
            if story_i['id'] in clustered:
                continue
            
            # Start a new cluster with this story
            cluster_stories = [story_i]
            clustered.add(story_i['id'])
            
            # Find similar stories
            text_i = f"{story_i.get('title', '')} {story_i.get('content', '')[:500]}"
            
            for j, story_j in enumerate(stories[i+1:], start=i+1):
                if story_j['id'] in clustered:
                    continue
                
                text_j = f"{story_j.get('title', '')} {story_j.get('content', '')[:500]}"
                similarity = self._compute_similarity(text_i, text_j)
                
                if similarity >= self.similarity_threshold:
                    cluster_stories.append(story_j)
                    clustered.add(story_j['id'])
            
            # Create cluster if it meets minimum size
            if len(cluster_stories) >= self.min_cluster_size:
                # Sort by published date (newest first) if available
                cluster_stories.sort(
                    key=lambda s: s.get('published_at', ''),
                    reverse=True
                )
                
                # Get representative story (first one, typically most recent)
                rep = cluster_stories[0]
                
                # Extract keywords
                keywords = self._extract_keywords(cluster_stories)
                
                cluster = StoryCluster(
                    id=f"cluster-{len(clusters)}",
                    stories=cluster_stories,
                    representative_title=rep.get('title', ''),
                    representative_summary=rep.get('content', '')[:300] + "..." if len(rep.get('content', '')) > 300 else rep.get('content', ''),
                    keywords=keywords,
                    sources=list(set(s.get('source', 'unknown') for s in cluster_stories)),
                    domains=list(set(s.get('domain', 'unknown') for s in cluster_stories)),
                    published_at=rep.get('published_at'),
                    cluster_size=len(cluster_stories)
                )
                clusters.append(cluster)
        
        # Collect unclustered stories
        unclustered = [
            s for s in stories 
            if s['id'] not in clustered
        ]
        
        return ClusterResult(
            clusters=clusters,
            unclustered=unclustered,
            total_stories=len(stories),
            cluster_count=len(clusters),
            singleton_count=len(unclustered)
        )
    
    def find_cross_domain_clusters(self, cluster_result: ClusterResult) -> list[StoryCluster]:
        """
        Find clusters that span multiple domains (AI, dev, investment).
        
        These represent stories with broad relevance across domains.
        """
        cross_domain = []
        for cluster in cluster_result.clusters:
            if len(cluster.domains) > 1:
                cross_domain.append(cluster)
        return cross_domain


# Common English stop words
STOP_WORDS = {
    'the', 'be', 'to', 'of', 'and', 'a', 'in', 'that', 'have', 'i',
    'it', 'for', 'not', 'on', 'with', 'he', 'as', 'you', 'do', 'at',
    'this', 'but', 'his', 'by', 'from', 'they', 'we', 'say', 'her',
    'she', 'or', 'an', 'will', 'my', 'one', 'all', 'would', 'there',
    'their', 'what', 'so', 'up', 'out', 'if', 'about', 'who', 'get',
    'which', 'go', 'me', 'when', 'make', 'can', 'like', 'time', 'no',
    'just', 'him', 'know', 'take', 'people', 'into', 'year', 'your',
    'good', 'some', 'could', 'them', 'see', 'other', 'than', 'then',
    'now', 'look', 'only', 'come', 'its', 'over', 'think', 'also',
    'back', 'after', 'use', 'two', 'how', 'our', 'work', 'first',
    'well', 'way', 'even', 'new', 'want', 'because', 'any', 'these',
    'give', 'day', 'most', 'us', 'is', 'was', 'are', 'were', 'been',
    'has', 'had', 'did', 'does', 'doing', 'done', 'being', 'having',
    'said', 'says', 'saying', 'went', 'going', 'gone', 'came', 'coming',
    'comes', 'made', 'making', 'makes', 'found', 'finding', 'finds',
    'put', 'puts', 'putting', 'set', 'sets', 'setting', 'let', 'lets',
    'letting', 'got', 'gets', 'getting', 'took', 'takes', 'taking',
}


if __name__ == "__main__":
    # Simple test
    test_stories = [
        {
            'id': '1',
            'title': 'OpenAI Releases GPT-5 with Multimodal Capabilities',
            'content': 'OpenAI announced GPT-5 today, featuring improved reasoning and multimodal input support. The model demonstrates significant advances in code generation and mathematical reasoning.',
            'source': 'TechCrunch',
            'domain': 'ai',
            'published_at': '2026-03-21T10:00:00Z'
        },
        {
            'id': '2',
            'title': 'GPT-5 Launch: What Developers Need to Know',
            'content': 'The latest GPT model from OpenAI brings new capabilities for software developers. Key features include better code completion and API improvements.',
            'source': 'Dev.to',
            'domain': 'software_development',
            'published_at': '2026-03-21T11:00:00Z'
        },
        {
            'id': '3',
            'title': 'Markets React to OpenAI GPT-5 Announcement',
            'content': 'AI-related stocks saw significant movement following the GPT-5 release. Investors are pricing in the competitive implications for the AI sector.',
            'source': 'Bloomberg',
            'domain': 'investment',
            'published_at': '2026-03-21T12:00:00Z'
        },
        {
            'id': '4',
            'title': 'Rust 1.85 Released with New Features',
            'content': 'The Rust team announced version 1.85 today, bringing async improvements and better error messages.',
            'source': 'Rust Blog',
            'domain': 'software_development',
            'published_at': '2026-03-21T09:00:00Z'
        }
    ]
    
    clusterer = StoryClusterer(similarity_threshold=0.25)
    result = clusterer.cluster_stories(test_stories)
    
    print(f"Total stories: {result.total_stories}")
    print(f"Clusters formed: {result.cluster_count}")
    print(f"Unclustered: {result.singleton_count}")
    print()
    
    for cluster in result.clusters:
        print(f"\nCluster: {cluster.representative_title}")
        print(f"  Keywords: {', '.join(cluster.keywords)}")
        print(f"  Domains: {', '.join(cluster.domains)}")
        print(f"  Sources: {', '.join(cluster.sources)}")
        print(f"  Size: {cluster.cluster_size}")
    
    cross_domain = clusterer.find_cross_domain_clusters(result)
    print(f"\nCross-domain clusters: {len(cross_domain)}")
