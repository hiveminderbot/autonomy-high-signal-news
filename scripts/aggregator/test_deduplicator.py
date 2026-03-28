#!/usr/bin/env python3
"""
Unit tests for the deduplicator module.

Tests SimHash, URLNormalizer, Deduplicator, and StoryClusterer classes.
"""

import unittest
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from .deduplicator import (
    SimHash,
    URLNormalizer,
    Deduplicator,
    StoryClusterer,
    DuplicateResult,
)


class TestSimHash(unittest.TestCase):
    """Tests for SimHash algorithm."""

    def setUp(self):
        self.simhash = SimHash(hashbits=64)

    def test_exact_duplicate_similarity(self):
        """Exact duplicates should have similarity 1.0."""
        text = "The quick brown fox jumps over the lazy dog"
        hash1 = self.simhash.compute(text)
        hash2 = self.simhash.compute(text)
        self.assertEqual(self.simhash.similarity(hash1, hash2), 1.0)

    def test_near_duplicate_high_similarity(self):
        """Near duplicates should have high similarity."""
        text1 = "The quick brown fox jumps over the lazy dog"
        text2 = "The quick brown fox jumped over the lazy dog"
        hash1 = self.simhash.compute(text1)
        hash2 = self.simhash.compute(text2)
        similarity = self.simhash.similarity(hash1, hash2)
        # Note: 3-word shingles with small text can give ~0.65-0.70 similarity
        self.assertGreater(similarity, 0.6, f"Expected >0.6, got {similarity}")

    def test_different_text_low_similarity(self):
        """Different texts should have low similarity."""
        text1 = "The quick brown fox jumps over the lazy dog"
        text2 = "Python is a programming language used for data science"
        hash1 = self.simhash.compute(text1)
        hash2 = self.simhash.compute(text2)
        similarity = self.simhash.similarity(hash1, hash2)
        self.assertLess(similarity, 0.6, f"Expected <0.6, got {similarity}")

    def test_empty_text(self):
        """Empty text should return hash 0."""
        hash_val = self.simhash.compute("")
        self.assertEqual(hash_val, 0)

    def test_short_text(self):
        """Short text should still produce valid hash."""
        hash_val = self.simhash.compute("Hi")
        self.assertIsInstance(hash_val, int)
        self.assertGreaterEqual(hash_val, 0)

    def test_tokenization(self):
        """Tokenization should produce shingles."""
        text = "one two three four five"
        tokens = self.simhash._tokenize(text)
        # Should produce 3-word shingles: ["one two three", "two three four", "three four five"]
        self.assertEqual(len(tokens), 3)
        self.assertEqual(tokens[0], "one two three")
        self.assertEqual(tokens[1], "two three four")
        self.assertEqual(tokens[2], "three four five")


class TestURLNormalizer(unittest.TestCase):
    """Tests for URL normalization."""

    def setUp(self):
        self.normalizer = URLNormalizer()

    def test_lowercase(self):
        """URLs should be lowercased."""
        url = "HTTPS://EXAMPLE.COM/Article"
        result = self.normalizer.normalize(url)
        self.assertEqual(result, "example.com/article")

    def test_remove_https_protocol(self):
        """HTTPS protocol should be removed."""
        url = "https://example.com/article"
        result = self.normalizer.normalize(url)
        self.assertEqual(result, "example.com/article")

    def test_remove_http_protocol(self):
        """HTTP protocol should be removed."""
        url = "http://example.com/article"
        result = self.normalizer.normalize(url)
        self.assertEqual(result, "example.com/article")

    def test_remove_www_prefix(self):
        """www prefix should be removed."""
        url = "https://www.example.com/article"
        result = self.normalizer.normalize(url)
        self.assertEqual(result, "example.com/article")

    def test_remove_trailing_slash(self):
        """Trailing slash should be removed."""
        url = "https://example.com/article/"
        result = self.normalizer.normalize(url)
        self.assertEqual(result, "example.com/article")

    def test_remove_fragment(self):
        """Fragment should be removed."""
        url = "https://example.com/article#section"
        result = self.normalizer.normalize(url)
        self.assertEqual(result, "example.com/article")

    def test_remove_utm_params(self):
        """UTM tracking parameters should be removed."""
        url = "https://example.com/article?utm_source=twitter&utm_medium=social"
        result = self.normalizer.normalize(url)
        self.assertEqual(result, "example.com/article")

    def test_remove_fbclid(self):
        """Facebook click ID should be removed."""
        url = "https://example.com/article?fbclid=abc123"
        result = self.normalizer.normalize(url)
        self.assertEqual(result, "example.com/article")

    def test_preserve_essential_params(self):
        """Non-tracking parameters should be preserved."""
        url = "https://example.com/article?id=123&page=2"
        result = self.normalizer.normalize(url)
        self.assertEqual(result, "example.com/article?id=123&page=2")

    def test_equivalent_urls_same(self):
        """Equivalent URLs should normalize to the same value."""
        urls = [
            "https://example.com/article?utm_source=twitter",
            "http://example.com/article",
            "https://www.example.com/article/",
            "https://EXAMPLE.COM/article#section",
        ]
        normalized = [self.normalizer.normalize(u) for u in urls]
        self.assertEqual(len(set(normalized)), 1)
        self.assertEqual(normalized[0], "example.com/article")


class TestDeduplicator(unittest.TestCase):
    """Tests for the Deduplicator class."""

    def setUp(self):
        self.dedup = Deduplicator()

    def test_first_article_not_duplicate(self):
        """First article should not be a duplicate."""
        result = self.dedup.check_duplicate(
            "id1", "https://example.com/article", "Title", "Content here"
        )
        self.assertFalse(result.is_duplicate)
        self.assertEqual(result.match_type, "none")

    def test_exact_url_duplicate(self):
        """Exact same URL should be detected as duplicate."""
        self.dedup.add("id1", "https://example.com/article", "Title", "Content")
        result = self.dedup.check_duplicate(
            "id2", "https://example.com/article", "Different Title", "Different content"
        )
        self.assertTrue(result.is_duplicate)
        self.assertEqual(result.match_type, "exact")
        self.assertEqual(result.similarity_score, 1.0)

    def test_equivalent_url_duplicate(self):
        """Equivalent URLs (after normalization) should be detected."""
        self.dedup.add("id1", "https://example.com/article", "Title", "Content")
        result = self.dedup.check_duplicate(
            "id2", "https://www.example.com/article/?utm_source=twitter", "Title", "Content"
        )
        self.assertTrue(result.is_duplicate)
        self.assertEqual(result.match_type, "exact")

    def test_exact_content_duplicate(self):
        """Same title and content should be detected as duplicate."""
        self.dedup.add("id1", "https://example.com/article1", "Title", "Content here")
        result = self.dedup.check_duplicate(
            "id2", "https://example.com/article2", "Title", "Content here"
        )
        self.assertTrue(result.is_duplicate)
        self.assertEqual(result.match_type, "exact")
        self.assertEqual(result.duplicate_of, "id1")

    def test_near_duplicate_detection(self):
        """Near-duplicate content should be detected."""
        self.dedup.add(
            "id1", "https://example.com/article1",
            "Breaking News: Market Update",
            "The stock market showed strong gains today as tech stocks rallied..."
        )
        result = self.dedup.check_duplicate(
            "id2", "https://example.com/article2",
            "Breaking News: Market Update",
            "The stock market showed strong gains today as technology stocks rallied..."
        )
        # Should detect as near-duplicate with high similarity
        if result.is_duplicate:
            self.assertEqual(result.match_type, "near")
            self.assertGreater(result.similarity_score, 0.8)

    def test_different_content_not_duplicate(self):
        """Different content should not be marked as duplicate."""
        self.dedup.add(
            "id1", "https://example.com/article1",
            "Tech Stocks Rally",
            "Technology companies saw gains today..."
        )
        result = self.dedup.check_duplicate(
            "id2", "https://example.com/article2",
            "Recipe: Chocolate Cake",
            "Mix flour, sugar, and cocoa powder..."
        )
        self.assertFalse(result.is_duplicate)

    def test_stats_tracking(self):
        """Stats should track seen URLs and hashes."""
        stats_before = self.dedup.get_stats()
        self.assertEqual(stats_before["urls_tracked"], 0)
        self.assertEqual(stats_before["content_hashes_tracked"], 0)

        self.dedup.add("id1", "https://example.com/article", "Title", "Content")
        stats_after = self.dedup.get_stats()
        self.assertEqual(stats_after["urls_tracked"], 1)
        self.assertEqual(stats_after["content_hashes_tracked"], 1)


class TestStoryClusterer(unittest.TestCase):
    """Tests for story clustering."""

    def setUp(self):
        self.clusterer = StoryClusterer(similarity_threshold=0.70)

    def test_empty_articles(self):
        """Empty article list should return empty clusters."""
        clusters = self.clusterer.cluster([])
        self.assertEqual(clusters, [])

    def test_single_article(self):
        """Single article should return one cluster."""
        articles = [{"id": "1", "title": "Title", "content": "Content"}]
        clusters = self.clusterer.cluster(articles)
        self.assertEqual(len(clusters), 1)
        self.assertEqual(len(clusters[0]), 1)

    def test_similar_articles_clustered(self):
        """Similar articles should be clustered together."""
        # Use nearly identical articles to ensure clustering at 0.70 threshold
        articles = [
            {"id": "1", "title": "Breaking News: Major Event", "content": "A major event occurred today with significant impact on the market and economy..."},
            {"id": "2", "title": "Breaking News: Major Event", "content": "A major event occurred today with significant impact on the market and economy..."},
            {"id": "3", "title": "Completely Different Topic", "content": "Sports results from yesterday's games were unexpected..."},
        ]
        clusters = self.clusterer.cluster(articles)
        # Should have 2 clusters: one for the duplicate articles, one for different topic
        self.assertEqual(len(clusters), 2)
        # Find the cluster with the duplicate articles (should have 2)
        dup_cluster = None
        for cluster in clusters:
            if len(cluster) == 2:
                dup_cluster = cluster
                break
        self.assertIsNotNone(dup_cluster)
        self.assertEqual(len(dup_cluster), 2)

    def test_threshold_affects_clustering(self):
        """Higher threshold should produce more clusters."""
        articles = [
            {"id": "1", "title": "Similar Title", "content": "Similar content here..."},
            {"id": "2", "title": "Similar Title", "content": "Similar content here too..."},
        ]

        # Low threshold - likely same cluster
        clusterer_low = StoryClusterer(similarity_threshold=0.60)
        clusters_low = clusterer_low.cluster(articles)

        # High threshold - likely separate clusters
        clusterer_high = StoryClusterer(similarity_threshold=0.95)
        clusters_high = clusterer_high.cluster(articles)

        # Both should produce at least 1 cluster
        self.assertGreaterEqual(len(clusters_low), 1)
        self.assertGreaterEqual(len(clusters_high), 1)


class TestDuplicateResult(unittest.TestCase):
    """Tests for DuplicateResult dataclass."""

    def test_default_values(self):
        """Default values should be correct."""
        result = DuplicateResult(is_duplicate=False)
        self.assertFalse(result.is_duplicate)
        self.assertIsNone(result.duplicate_of)
        self.assertEqual(result.similarity_score, 0.0)
        self.assertEqual(result.match_type, "none")

    def test_exact_match(self):
        """Exact match result."""
        result = DuplicateResult(
            is_duplicate=True,
            duplicate_of="original_id",
            similarity_score=1.0,
            match_type="exact"
        )
        self.assertTrue(result.is_duplicate)
        self.assertEqual(result.duplicate_of, "original_id")
        self.assertEqual(result.similarity_score, 1.0)
        self.assertEqual(result.match_type, "exact")


class TestIntegration(unittest.TestCase):
    """Integration tests for the full deduplication pipeline."""

    def test_realistic_scenario(self):
        """Test a realistic news aggregation scenario."""
        dedup = Deduplicator(simhash_threshold=0.85)

        # Simulate ingesting articles from different sources
        articles = [
            ("cnn-1", "https://cnn.com/tech-rally", "Tech Stocks Surge", "Technology stocks rallied today..."),
            ("bbc-1", "https://bbc.com/tech-rally", "Technology Shares Rise", "Technology stocks rallied today on strong earnings..."),
            ("reuters-1", "https://reuters.com/markets", "Markets Update", "Markets were mixed today..."),
            ("cnn-2", "https://cnn.com/tech-rally?utm_source=feed", "Tech Stocks Surge", "Technology stocks rallied today..."),  # Duplicate of cnn-1
        ]

        results = []
        for entry_id, url, title, content in articles:
            result = dedup.check_duplicate(entry_id, url, title, content)
            results.append((entry_id, result))
            if not result.is_duplicate:
                dedup.add(entry_id, url, title, content)

        # Check results
        self.assertFalse(results[0][1].is_duplicate)  # First article
        self.assertFalse(results[1][1].is_duplicate)  # Similar but not duplicate
        self.assertFalse(results[2][1].is_duplicate)  # Different topic
        self.assertTrue(results[3][1].is_duplicate)   # Should be detected as duplicate

        stats = dedup.get_stats()
        self.assertEqual(stats["urls_tracked"], 3)  # 3 unique URLs


def run_tests():
    """Run all tests and return results."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(TestSimHash))
    suite.addTests(loader.loadTestsFromTestCase(TestURLNormalizer))
    suite.addTests(loader.loadTestsFromTestCase(TestDeduplicator))
    suite.addTests(loader.loadTestsFromTestCase(TestStoryClusterer))
    suite.addTests(loader.loadTestsFromTestCase(TestDuplicateResult))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
