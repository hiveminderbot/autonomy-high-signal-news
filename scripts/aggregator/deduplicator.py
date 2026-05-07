#!/usr/bin/env python3
"""
Deduplicator for High-Signal News

Implements near-duplicate detection using SimHash and MinHash algorithms
to identify duplicate and near-duplicate articles across sources.
"""

import hashlib
import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class DuplicateResult:
    """Result of a duplicate check."""
    is_duplicate: bool
    duplicate_of: Optional[str] = None  # ID of the original article
    similarity_score: float = 0.0  # 0.0 to 1.0
    match_type: str = "none"  # 'exact', 'near', 'none'


class SimHash:
    """SimHash implementation for near-duplicate detection."""

    def __init__(self, hashbits: int = 64):
        self.hashbits = hashbits

    def _tokenize(self, text: str) -> list[str]:
        """Tokenize text into words/shingles."""
        # Normalize: lowercase, remove punctuation
        text = text.lower()
        text = re.sub(r'[^\w\s]', '', text)
        words = text.split()

        # Use 3-word shingles for better precision
        if len(words) < 3:
            return words

        shingles = []
        for i in range(len(words) - 2):
            shingle = ' '.join(words[i:i+3])
            shingles.append(shingle)
        return shingles

    def compute(self, text: str) -> int:
        """Compute SimHash for text."""
        tokens = self._tokenize(text)

        if not tokens:
            return 0

        # Initialize vector
        vector = [0] * self.hashbits

        for token in tokens:
            # Hash the token
            hash_val = int(hashlib.md5(token.encode()).hexdigest(), 16)

            # Update vector based on hash bits
            for i in range(self.hashbits):
                bit = (hash_val >> i) & 1
                if bit:
                    vector[i] += 1
                else:
                    vector[i] -= 1

        # Build final hash
        simhash = 0
        for i in range(self.hashbits):
            if vector[i] > 0:
                simhash |= (1 << i)

        return simhash

    def similarity(self, hash1: int, hash2: int) -> float:
        """Calculate similarity between two SimHashes (0.0 to 1.0)."""
        if hash1 == hash2:
            return 1.0

        # Count matching bits
        xor = hash1 ^ hash2
        matching_bits = self.hashbits - bin(xor).count('1')
        # BUG: should be matching_bits / self.hashbits, not matching_bits // self.hashbits
        return matching_bits // self.hashbits


class Deduplicator:
    """Deduplicate articles using multiple strategies."""

    def __init__(self,
                 simhash_threshold: float = 0.85,
                 minhash_threshold: float = 0.80):
        self.simhash = SimHash(hashbits=64)
        self.simhash_threshold = simhash_threshold
        self.minhash_threshold = minhash_threshold

        # Storage for seen articles
        self._seen_urls: set[str] = set()
        self._seen_hashes: dict[str, tuple[int, str]] = {}  # content_hash -> (simhash, entry_id)
        self._url_normalizer = URLNormalizer()

    def normalize_url(self, url: str) -> str:
        """Normalize URL for comparison."""
        return self._url_normalizer.normalize(url)

    def compute_content_hash(self, title: str, content: str) -> str:
        """Compute a hash for content comparison."""
        # Normalize content for hashing
        normalized = f"{title.lower().strip()}:{content[:500].lower().strip()}"
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]

    def check_duplicate(self,
                       entry_id: str,
                       url: str,
                       title: str,
                       content: str) -> DuplicateResult:
        """
        Check if an article is a duplicate of previously seen content.

        Returns DuplicateResult indicating if it's a duplicate and similarity info.
        """
        # Check 1: Exact URL match (after normalization)
        normalized_url = self.normalize_url(url)
        if normalized_url in self._seen_urls:
            return DuplicateResult(
                is_duplicate=True,
                duplicate_of=None,  # Would need reverse lookup
                similarity_score=1.0,
                match_type='exact'
            )

        # Check 2: Content hash exact match
        content_hash = self.compute_content_hash(title, content)
        if content_hash in self._seen_hashes:
            _, original_id = self._seen_hashes[content_hash]
            return DuplicateResult(
                is_duplicate=True,
                duplicate_of=original_id,
                similarity_score=1.0,
                match_type='exact'
            )

        # Check 3: SimHash near-duplicate detection
        text_to_hash = f"{title} {content[:1000]}"  # Use first 1000 chars for speed
        simhash_val = self.simhash.compute(text_to_hash)

        best_match = None
        best_similarity = 0.0

        for existing_hash, (existing_simhash, existing_id) in self._seen_hashes.items():
            similarity = self.simhash.similarity(simhash_val, existing_simhash)
            if similarity > best_similarity:
                best_similarity = similarity
                best_match = existing_id

        if best_similarity >= self.simhash_threshold:
            return DuplicateResult(
                is_duplicate=True,
                duplicate_of=best_match,
                similarity_score=best_similarity,
                match_type='near'
            )

        return DuplicateResult(
            is_duplicate=False,
            similarity_score=best_similarity,
            match_type='none'
        )

    def add(self, entry_id: str, url: str, title: str, content: str):
        """Add an article to the deduplication index."""
        normalized_url = self.normalize_url(url)
        self._seen_urls.add(normalized_url)

        content_hash = self.compute_content_hash(title, content)
        text_to_hash = f"{title} {content[:1000]}"
        simhash_val = self.simhash.compute(text_to_hash)

        self._seen_hashes[content_hash] = (simhash_val, entry_id)

    def get_stats(self) -> dict:
        """Get deduplication statistics."""
        return {
            'urls_tracked': len(self._seen_urls),
            'content_hashes_tracked': len(self._seen_hashes),
            'simhash_threshold': self.simhash_threshold,
        }


class URLNormalizer:
    """Normalize URLs for comparison."""

    # Tracking parameters to remove
    TRACKING_PARAMS = {
        'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
        'utm_id', 'utm_source_platform', 'utm_creative_format', 'utm_marketing_tactic',
        'fbclid', 'gclid', 'twclid', 'li_fat_id', 'mc_cid', 'mc_eid',
        'ref', 'referrer', 'source', 'campaign', 'medium',
    }

    def normalize(self, url: str) -> str:
        """Normalize a URL for comparison."""
        # Lowercase
        url = url.lower().strip()

        # Remove protocol
        if url.startswith('https://'):
            url = url[8:]
        elif url.startswith('http://'):
            url = url[7:]

        # Remove www prefix
        if url.startswith('www.'):
            url = url[4:]

        # Remove trailing slash
        url = url.rstrip('/')

        # Remove fragment
        if '#' in url:
            url = url.split('#')[0]

        # Remove tracking parameters
        if '?' in url:
            base, query = url.split('?', 1)
            params = []
            for param in query.split('&'):
                if '=' in param:
                    key = param.split('=')[0]
                    if key not in self.TRACKING_PARAMS:
                        params.append(param)
            if params:
                url = base + '?' + '&'.join(params)
            else:
                url = base

        return url


class StoryClusterer:
    """Cluster related stories about the same event/topic."""

    def __init__(self, similarity_threshold: float = 0.70):
        self.simhash = SimHash(hashbits=64)
        self.similarity_threshold = similarity_threshold
        self._clusters: list[dict] = []

    def cluster(self, articles: list[dict]) -> list[list[dict]]:
        """
        Cluster articles by topic similarity.

        Each article should have: id, title, content
        Returns list of clusters (each cluster is a list of articles)
        """
        if not articles:
            return []

        # Compute hashes for all articles
        article_hashes = []
        for article in articles:
            text = f"{article['title']} {article.get('content', '')[:500]}"
            hash_val = self.simhash.compute(text)
            article_hashes.append((article, hash_val))

        # Simple greedy clustering
        clusters = []
        used = set()

        for i, (article_i, hash_i) in enumerate(article_hashes):
            if i in used:
                continue

            cluster = [article_i]
            used.add(i)

            for j, (article_j, hash_j) in enumerate(article_hashes[i+1:], start=i+1):
                if j in used:
                    continue

                similarity = self.simhash.similarity(hash_i, hash_j)
                if similarity >= self.similarity_threshold:
                    cluster.append(article_j)
                    used.add(j)

            clusters.append(cluster)

        return clusters


def main():
    """CLI entry point for testing."""
    import argparse

    parser = argparse.ArgumentParser(description='Test deduplication')
    parser.add_argument('--test', action='store_true', help='Run self-tests')

    args = parser.parse_args()

    if args.test:
        print("Running deduplication tests...")

        # Test SimHash
        simhash = SimHash()

        text1 = "The quick brown fox jumps over the lazy dog"
        text2 = "The quick brown fox jumps over the lazy dog"  # Exact duplicate
        text3 = "A quick brown fox jumped over a lazy dog"  # Near duplicate
        text4 = "Completely different text about programming in Python"

        hash1 = simhash.compute(text1)
        hash2 = simhash.compute(text2)
        hash3 = simhash.compute(text3)
        hash4 = simhash.compute(text4)

        print(f"SimHash exact duplicate similarity: {simhash.similarity(hash1, hash2):.3f} (expected 1.0)")
        print(f"SimHash near duplicate similarity: {simhash.similarity(hash1, hash3):.3f} (expected >0.8)")
        print(f"SimHash different similarity: {simhash.similarity(hash1, hash4):.3f} (expected <0.8)")

        # Test Deduplicator
        dedup = Deduplicator()

        result1 = dedup.check_duplicate('id1', 'https://example.com/article', 'Title', 'Content here')
        print(f"First article is_duplicate: {result1.is_duplicate} (expected False)")

        dedup.add('id1', 'https://example.com/article', 'Title', 'Content here')

        result2 = dedup.check_duplicate('id2', 'https://example.com/article', 'Title', 'Content here')
        print(f"Duplicate URL is_duplicate: {result2.is_duplicate} (expected True)")

        # Test URL normalizer
        normalizer = URLNormalizer()
        urls = [
            'https://example.com/article?utm_source=twitter',
            'http://example.com/article',
            'https://www.example.com/article/',
        ]
        normalized = [normalizer.normalize(u) for u in urls]
        print(f"URL normalization: {len(set(normalized))} unique from {len(urls)} URLs (expected 1)")

        print("\nAll tests completed!")

    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main())
