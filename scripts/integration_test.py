#!/usr/bin/env python3
"""
Integration test for the High-Signal News aggregation pipeline.

Tests the complete pipeline with real source fetching and measures performance.
Run: python scripts/integration_test.py
"""

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent))

from aggregator.feed_fetcher import FeedFetcher, FeedEntry, FeedCache, FeedSource
from aggregator.deduplicator import Deduplicator, URLNormalizer
from aggregator.content_extractor import ContentExtractor
from aggregator.storage import ArticleStorage


class IntegrationTest:
    """Integration test suite for the aggregation pipeline."""

    def __init__(self):
        self.results = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tests": {},
            "summary": {}
        }

    def load_sources(self) -> dict:
        """Load all source catalogs."""
        sources_dir = Path(__file__).parent.parent / "sources"
        sources = {
            "ai": json.loads((sources_dir / "sources-ai.json").read_text()),
            "dev": json.loads((sources_dir / "sources-dev.json").read_text()),
            "investment": json.loads((sources_dir / "sources-investment.json").read_text()),
            "newsletters": json.loads((sources_dir / "newsletter_catalog.json").read_text())
        }
        return sources

    def count_sources(self, sources: dict) -> dict:
        """Count sources by type."""
        counts = {"rss": 0, "newsletter": 0, "github": 0, "total": 0}

        # AI sources
        counts["rss"] += len(sources["ai"].get("rss_feeds", []))
        counts["newsletter"] += len(sources["ai"].get("newsletters", []))
        counts["github"] += len(sources["ai"].get("github", []))

        # Dev sources (count RSS from language_specific)
        for lang, feeds in sources["dev"].get("language_specific", {}).items():
            counts["rss"] += len(feeds)
        counts["rss"] += len(sources["dev"].get("frameworks", []))
        counts["rss"] += len(sources["dev"].get("dev_blogs", []))

        # Investment sources
        for category, feeds in sources["investment"].get("public_markets", {}).items():
            counts["rss"] += len(feeds)
        counts["rss"] += len(sources["investment"].get("vc_funding", []))
        counts["newsletter"] += len(sources["investment"].get("newsletters", []))

        # Newsletter catalog
        counts["newsletter"] += len(sources["newsletters"].get("newsletters", []))

        counts["total"] = counts["rss"] + counts["newsletter"] + counts["github"]
        return counts

    def test_source_catalog_completeness(self) -> dict:
        """Test that we have 50+ sources configured."""
        print("\n🧪 Testing source catalog completeness...")

        sources = self.load_sources()
        counts = self.count_sources(sources)

        result = {
            "passed": counts["total"] >= 50,
            "counts": counts,
            "message": f"Found {counts['total']} sources (target: 50+)"
        }

        status = "✅" if result["passed"] else "❌"
        print(f"  {status} {result['message']}")
        print(f"     - RSS feeds: {counts['rss']}")
        print(f"     - Newsletters: {counts['newsletter']}")
        print(f"     - GitHub: {counts['github']}")

        return result

    def test_feed_fetcher_with_real_sources(self) -> dict:
        """Test feed fetching with a sample of real RSS feeds."""
        print("\n🧪 Testing feed fetcher with real sources...")

        # Use a small sample of reliable feeds for testing
        test_feeds = [
            {"name": "arXiv cs.AI", "url": "https://rss.arxiv.org/rss/cs.AI"},
            {"name": "Papers with Code", "url": "https://paperswithcode.com/rss"},
            {"name": "Python Weekly", "url": "https://www.pythonweekly.com/rss.xml"},
        ]

        # Create temporary cache
        import tempfile
        import os
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            cache_path = tmp.name

        successful = 0
        failed = 0
        total_entries = 0
        errors = []

        try:
            cache = FeedCache(cache_path)
            fetcher = FeedFetcher(cache)

            for feed in test_feeds:
                try:
                    source = FeedSource(
                        id=feed["name"].lower().replace(" ", "-"),
                        name=feed["name"],
                        url=feed["url"],
                        format="RSS",
                        category="test",
                        domain="test",
                        signal_quality="High",
                        active=True
                    )
                    entries = fetcher.fetch_rss(source)
                    if entries:
                        successful += 1
                        total_entries += len(entries)
                        print(f"  ✅ {feed['name']}: {len(entries)} entries")
                    else:
                        failed += 1
                        errors.append(f"{feed['name']}: No entries returned")
                        print(f"  ⚠️  {feed['name']}: No entries")
                except Exception as e:
                    failed += 1
                    errors.append(f"{feed['name']}: {str(e)}")
                    print(f"  ❌ {feed['name']}: {str(e)[:50]}")
        finally:
            os.unlink(cache_path)

        result = {
            "passed": successful >= 2,  # At least 2/3 should succeed
            "successful": successful,
            "failed": failed,
            "total_entries": total_entries,
            "errors": errors,
            "message": f"Fetched {total_entries} entries from {successful}/{len(test_feeds)} feeds"
        }

        status = "✅" if result["passed"] else "❌"
        print(f"  {status} {result['message']}")

        return result

    def test_deduplication_accuracy(self) -> dict:
        """Test deduplication with real-world scenarios."""
        print("\n🧪 Testing deduplication accuracy...")

        from aggregator.deduplicator import Deduplicator, DuplicateResult

        dedup = Deduplicator(simhash_threshold=0.85)

        # Test cases: exact duplicates, near-duplicates, unique articles
        test_entries = [
            {"id": "test-1", "title": "OpenAI Releases GPT-5", "url": "https://example.com/gpt5", "content": "New model announcement"},
            {"id": "test-2", "title": "OpenAI Releases GPT-5", "url": "https://example.com/gpt5", "content": "New model announcement"},  # Exact duplicate
            {"id": "test-3", "title": "OpenAI Releases GPT-5", "url": "https://example.com/gpt5?ref=rss", "content": "New model announcement"},  # Near-duplicate
            {"id": "test-4", "title": "Google Announces Gemini Update", "url": "https://example.com/gemini", "content": "Different announcement"},  # Unique
        ]

        # Process entries
        duplicates = 0
        unique = 0

        for entry in test_entries:
            result = dedup.check_duplicate(
                entry_id=entry["id"],
                url=entry["url"],
                title=entry["title"],
                content=entry["content"]
            )
            if result.is_duplicate:
                duplicates += 1
            else:
                unique += 1
                # Add to dedup store
                dedup.add(entry["id"], entry["url"], entry["title"], entry["content"])

        # We expect 2 duplicates (test-2 exact URL match, test-3 near-duplicate) and 2 unique
        expected_duplicates = 2
        expected_unique = 2

        result = {
            "passed": duplicates == expected_duplicates and unique == expected_unique,
            "duplicates_detected": duplicates,
            "unique_entries": unique,
            "message": f"Detected {duplicates} duplicates, {unique} unique entries"
        }

        status = "✅" if result["passed"] else "❌"
        print(f"  {status} {result['message']}")

        return result

    def test_content_extraction(self) -> dict:
        """Test content extraction capabilities."""
        print("\n🧪 Testing content extraction...")

        from aggregator.content_extractor import ContentExtractor, ExtractedContent

        extractor = ContentExtractor()

        # Test that extractor initializes correctly
        checks = [
            (extractor is not None, "ContentExtractor initialization"),
            (hasattr(extractor, 'extract'), "Has extract method"),
            (hasattr(extractor, 'extract_batch'), "Has extract_batch method"),
        ]

        passed = sum(1 for check, _ in checks if check)
        total = len(checks)

        result = {
            "passed": passed == total,
            "checks_passed": passed,
            "total_checks": total,
            "message": f"{passed}/{total} extraction checks passed"
        }

        for check, name in checks:
            status = "✅" if check else "❌"
            print(f"  {status} {name}")

        return result

    def test_storage_operations(self) -> dict:
        """Test storage with temporary database."""
        print("\n🧪 Testing storage operations...")

        import tempfile
        import os

        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            db_path = Path(tmp.name)

        try:
            storage = ArticleStorage(db_path)

            # Test article insertion using Article dataclass
            from aggregator.storage import Article
            now = datetime.now(timezone.utc)
            article = Article(
                id="test-article-1",
                url="https://example.com/test-article",
                title="Test Article",
                source_id="test",
                source_name="Test Source",
                domain="test",
                published_at=now,
                fetched_at=now,
                summary="Test summary",
                content="Test content"
            )
            saved = storage.save_article(article)

            # Test retrieval using the original article ID
            article = storage.get_article("test-article-1")

            # Test search
            results = storage.search_articles("Test")

            # Test stats
            stats = storage.get_stats()

            checks = [
                (saved, "Article saved"),
                (article is not None, "Article retrieved"),
                (len(results) > 0, "Search works"),
                (stats["total_articles"] == 1, "Stats accurate"),
            ]

            passed = sum(1 for check, _ in checks if check)
            total = len(checks)

            result = {
                "passed": passed == total,
                "checks_passed": passed,
                "total_checks": total,
                "message": f"{passed}/{total} storage checks passed"
            }

            for check, name in checks:
                status = "✅" if check else "❌"
                print(f"  {status} {name}")

        finally:
            os.unlink(db_path)

        return result

    def test_performance_requirements(self) -> dict:
        """Test that pipeline operations meet performance targets."""
        print("\n🧪 Testing performance requirements...")

        # Target: Complete daily run in < 5 minutes (300 seconds)
        target_seconds = 300

        # Simulate a small pipeline run
        start = time.time()

        # Deduplication simulation (100 entries) - most CPU intensive part
        dedup = Deduplicator()
        for i in range(100):
            result = dedup.check_duplicate(
                entry_id=f"perf-{i}",
                url=f"https://example.com/{i}",
                title=f"Test Article {i}",
                content=f"Test content for article {i} with some variability"
            )
            if not result.is_duplicate:
                dedup.add(f"perf-{i}", f"https://example.com/{i}", f"Test Article {i}", f"Test content")

        elapsed = time.time() - start

        # Extrapolate to full run (50 sources, ~500 entries)
        # Current test is ~20% of full load, so multiply by 5
        estimated_full_run = elapsed * 5

        result = {
            "passed": estimated_full_run < target_seconds,
            "test_duration": round(elapsed, 2),
            "estimated_full_run": round(estimated_full_run, 2),
            "target_seconds": target_seconds,
            "message": f"Estimated full run: {round(estimated_full_run, 1)}s (target: <{target_seconds}s)"
        }

        status = "✅" if result["passed"] else "❌"
        print(f"  {status} {result['message']}")
        print(f"     (Test duration: {result['test_duration']}s)")

        return result

    def run_all(self) -> dict:
        """Run all integration tests."""
        print("=" * 60)
        print("🔬 High-Signal News Integration Test Suite")
        print("=" * 60)

        self.results["tests"]["source_catalog"] = self.test_source_catalog_completeness()
        self.results["tests"]["feed_fetcher"] = self.test_feed_fetcher_with_real_sources()
        self.results["tests"]["deduplication"] = self.test_deduplication_accuracy()
        self.results["tests"]["content_extraction"] = self.test_content_extraction()
        self.results["tests"]["storage"] = self.test_storage_operations()
        self.results["tests"]["performance"] = self.test_performance_requirements()

        # Calculate summary
        total = len(self.results["tests"])
        passed = sum(1 for t in self.results["tests"].values() if t["passed"])

        self.results["summary"] = {
            "total_tests": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": f"{passed}/{total}"
        }

        print("\n" + "=" * 60)
        print("📊 Test Summary")
        print("=" * 60)
        print(f"  Total: {total}")
        print(f"  Passed: {passed} ✅")
        print(f"  Failed: {total - passed} {'❌' if total > passed else ''}")

        return self.results


def main():
    """Run integration tests."""
    test = IntegrationTest()
    results = test.run_all()

    # Save results
    output_dir = Path(__file__).parent.parent / "test-output"
    output_dir.mkdir(exist_ok=True)

    output_file = output_dir / f"integration-test-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.json"
    output_file.write_text(json.dumps(results, indent=2))
    print(f"\n📝 Results saved to: {output_file}")

    # Exit with error code if any tests failed
    if results["summary"]["failed"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
