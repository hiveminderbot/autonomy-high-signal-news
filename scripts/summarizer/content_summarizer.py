#!/usr/bin/env python3
"""
Content Summarizer for High-Signal News

Generates concise summaries of news articles using extractive summarization.
Scores sentences by importance and selects the most informative ones.
"""

import re
from dataclasses import dataclass, field
from collections import defaultdict
from typing import Optional


@dataclass
class SummaryResult:
    """Result of summarization."""
    original_length: int  # Characters
    summary_length: int   # Characters
    compression_ratio: float
    summary: str
    key_sentences: list[str] = field(default_factory=list)
    word_count: int = 0


class ContentSummarizer:
    """Generate extractive summaries of news articles."""
    
    def __init__(self, max_sentences: int = 3, min_sentence_length: int = 40):
        """
        Initialize the summarizer.
        
        Args:
            max_sentences: Maximum number of sentences in summary
            min_sentence_length: Minimum characters for a sentence to be considered
        """
        self.max_sentences = max_sentences
        self.min_sentence_length = min_sentence_length
    
    def _split_sentences(self, text: str) -> list[str]:
        """Split text into sentences."""
        # Simple sentence splitting on period, question mark, exclamation
        # Handle common abbreviations
        text = re.sub(r'\b(Mr|Mrs|Ms|Dr|Prof|Sr|Jr|Inc|Ltd|Corp|LLC)\.\s', r'\1@@@ ', text)
        
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        # Restore periods in abbreviations
        sentences = [s.replace('@@@ ', '. ') for s in sentences]
        
        # Filter out very short sentences and clean
        sentences = [
            s.strip() 
            for s in sentences 
            if len(s.strip()) >= self.min_sentence_length
        ]
        
        return sentences
    
    def _tokenize_words(self, text: str) -> list[str]:
        """Tokenize text into words."""
        text = text.lower()
        text = re.sub(r'[^a-z0-9\s]', ' ', text)
        words = [w for w in text.split() if len(w) > 2]
        return words
    
    def _score_sentences(self, sentences: list[str], title: str) -> list[tuple[str, float]]:
        """
        Score sentences by importance.
        
        Uses multiple features:
        - Position (earlier sentences often more important)
        - Keyword overlap with title
        - Word frequency (TF-like scoring)
        - Sentence length (prefer medium-length sentences)
        """
        if not sentences:
            return []
        
        # Compute word frequencies across all sentences
        word_freq = defaultdict(int)
        for sentence in sentences:
            for word in self._tokenize_words(sentence):
                word_freq[word] += 1
        
        # Normalize frequencies
        max_freq = max(word_freq.values()) if word_freq else 1
        word_freq = {word: freq / max_freq for word, freq in word_freq.items()}
        
        # Title words for overlap scoring
        title_words = set(self._tokenize_words(title))
        
        scored_sentences = []
        for i, sentence in enumerate(sentences):
            score = 0.0
            
            # Position score (earlier sentences get boost)
            position_weight = 1.0 - (i / len(sentences)) * 0.3
            score += position_weight * 0.25
            
            # Title overlap score
            sentence_words = set(self._tokenize_words(sentence))
            title_overlap = len(sentence_words & title_words) / max(len(title_words), 1)
            score += title_overlap * 0.35
            
            # Word frequency score
            sentence_word_freq = sum(
                word_freq.get(word, 0) 
                for word in self._tokenize_words(sentence)
            )
            score += (sentence_word_freq / max(len(sentence_words), 1)) * 0.25
            
            # Length score (prefer medium-length sentences)
            sent_len = len(sentence)
            if 80 <= sent_len <= 200:
                score += 0.15
            elif sent_len < 80:
                score += 0.05
            else:
                score += 0.05
            
            scored_sentences.append((sentence, score))
        
        return scored_sentences
    
    def summarize(self, title: str, content: str) -> SummaryResult:
        """
        Generate a summary of the article.
        
        Args:
            title: Article title
            content: Article content
        
        Returns:
            SummaryResult with the generated summary
        """
        if not content or len(content.strip()) < self.min_sentence_length * 2:
            # Content too short, return as-is
            return SummaryResult(
                original_length=len(content),
                summary_length=len(content),
                compression_ratio=1.0,
                summary=content.strip(),
                key_sentences=[content.strip()] if content else [],
                word_count=len(content.split()) if content else 0
            )
        
        # Split into sentences
        sentences = self._split_sentences(content)
        
        if len(sentences) <= self.max_sentences:
            # Content already concise
            summary = ' '.join(sentences)
            return SummaryResult(
                original_length=len(content),
                summary_length=len(summary),
                compression_ratio=len(summary) / len(content) if content else 1.0,
                summary=summary,
                key_sentences=sentences,
                word_count=len(summary.split())
            )
        
        # Score sentences
        scored = self._score_sentences(sentences, title)
        
        # Sort by score and select top sentences
        scored.sort(key=lambda x: x[1], reverse=True)
        top_sentences = scored[:self.max_sentences]
        
        # Sort selected sentences by original position for coherent flow
        top_sentences_with_idx = [
            (sentences.index(sent), sent, score) 
            for sent, score in top_sentences
        ]
        top_sentences_with_idx.sort(key=lambda x: x[0])
        
        # Build summary
        key_sentences = [sent for _, sent, _ in top_sentences_with_idx]
        summary = ' '.join(key_sentences)
        
        return SummaryResult(
            original_length=len(content),
            summary_length=len(summary),
            compression_ratio=len(summary) / len(content) if content else 1.0,
            summary=summary,
            key_sentences=key_sentences,
            word_count=len(summary.split())
        )
    
    def summarize_batch(self, stories: list[dict]) -> dict[str, SummaryResult]:
        """
        Summarize a batch of stories.
        
        Args:
            stories: List of story dicts with 'id', 'title', 'content'
        
        Returns:
            Dict mapping story_id to SummaryResult
        """
        results = {}
        for story in stories:
            story_id = story.get('id', 'unknown')
            result = self.summarize(
                title=story.get('title', ''),
                content=story.get('content', '')
            )
            results[story_id] = result
        return results


class ClusterSummarizer:
    """Generate summaries for clusters of related stories."""
    
    def __init__(self, max_length: int = 400):
        """
        Initialize the cluster summarizer.
        
        Args:
            max_length: Maximum character length for cluster summary
        """
        self.max_length = max_length
        self.summarizer = ContentSummarizer(max_sentences=2)
    
    def summarize_cluster(self, cluster: dict) -> dict:
        """
        Generate a unified summary for a cluster of related stories.
        
        Args:
            cluster: Cluster dict with 'stories', 'keywords', etc.
        
        Returns:
            Enriched cluster dict with summary
        """
        stories = cluster.get('stories', [])
        
        if not stories:
            return cluster
        
        # Get representative story (most recent or most authoritative)
        rep_story = stories[0]
        
        # Combine unique content from all stories
        all_content = []
        seen_content = set()
        
        for story in stories:
            content = story.get('content', '')
            # Use first 300 chars as fingerprint
            fingerprint = content[:300]
            if fingerprint not in seen_content:
                seen_content.add(fingerprint)
                all_content.append(content)
        
        combined_content = ' '.join(all_content)
        
        # Generate summary
        summary_result = self.summarizer.summarize(
            title=cluster.get('representative_title', rep_story.get('title', '')),
            content=combined_content
        )
        
        # Create enriched cluster
        enriched = dict(cluster)
        enriched['summary'] = summary_result.summary
        enriched['summary_compression'] = summary_result.compression_ratio
        enriched['coverage_count'] = len(stories)
        enriched['source_diversity'] = len(set(s.get('source') for s in stories))
        
        return enriched


def generate_briefing_summary(stories: list[dict], max_items: int = 15) -> str:
    """
    Generate a formatted briefing summary from a list of stories.
    
    Args:
        stories: List of story dicts
        max_items: Maximum number of stories to include
    
    Returns:
        Formatted markdown summary
    """
    summarizer = ContentSummarizer(max_sentences=2)
    
    lines = ["# Morning Briefing\n"]
    
    for i, story in enumerate(stories[:max_items], 1):
        title = story.get('title', 'Untitled')
        content = story.get('content', '')
        source = story.get('source', 'Unknown')
        url = story.get('url', '')
        
        result = summarizer.summarize(title, content)
        
        lines.append(f"## {i}. {title}")
        lines.append(f"*{source}*\n")
        lines.append(result.summary)
        if url:
            lines.append(f"\n[Read more]({url})\n")
        else:
            lines.append("")
    
    return '\n'.join(lines)


if __name__ == "__main__":
    # Test the summarizer
    test_title = "OpenAI Releases GPT-5 with Multimodal Capabilities"
    test_content = """
    OpenAI announced GPT-5 today, featuring significant improvements in reasoning
    and multimodal capabilities. The model demonstrates advances in code generation,
    mathematical reasoning, and natural language processing. Early benchmarks show
    substantial gains over GPT-4 across a range of tasks.
    
    Sam Altman, CEO of OpenAI, said the new model represents a major step toward
    artificial general intelligence. The announcement comes as Google prepares to
    launch its next Gemini model and Microsoft integrates AI deeper into its products.
    The competitive landscape in large language models is intensifying.
    
    GPT-5 can process text, images, and audio inputs simultaneously, making it
    suitable for complex multimodal applications. Developers can access the model
    through OpenAI's API, with pricing set at competitive rates compared to GPT-4.
    The model supports function calling and structured outputs out of the box.
    
    Industry analysts expressed mixed reactions. Some praised the technical
    achievements while others raised concerns about safety and the pace of
    development. Regulatory questions remain unresolved as policymakers grapple
    with the implications of increasingly capable AI systems.
    """
    
    summarizer = ContentSummarizer(max_sentences=3)
    result = summarizer.summarize(test_title, test_content)
    
    print(f"Title: {test_title}")
    print(f"\nOriginal length: {result.original_length} chars")
    print(f"Summary length: {result.summary_length} chars")
    print(f"Compression: {result.compression_ratio:.1%}")
    print(f"Word count: {result.word_count}")
    print("\n" + "="*60)
    print("SUMMARY:")
    print("="*60)
    print(result.summary)
    print("\n" + "="*60)
    print("Key sentences:")
    for i, sent in enumerate(result.key_sentences, 1):
        print(f"  {i}. {sent[:100]}...")
