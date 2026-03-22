#!/usr/bin/env python3
"""
Test the rate-limited content extractor with live RSS feeds.

This script tests the new rate-limited extractor against the same
feeds that failed in the original content extraction test.

Usage:
    python scripts/test_rate_limited_pipeline.py
"""

import sys
import json
import time
from pathlib import Path
from datetime import datetime

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent))

from aggregator.feed_fetcher import FeedCache, load_sources_from_catalog, FeedSource
from aggregator.rate_limited_extractor import create_rate_limited_extractor


def test_rate_limited_extraction():
    """Test content extraction with rate limiting on problematic feeds."""
    
    print("=" * 60)
    print("Rate-Limited Content Extraction Test")
    print("=" * 60)
    print(f"Started at: {datetime.now().isoformat()}")
    print()
    
    # Load test sources
    catalog_path = Path("sources/sources-test.json")
    if not catalog_path.exists():
        print(f"❌ Catalog not found: {catalog_path}")
        print("Creating minimal test with hardcoded sources...")
        sources = [
            FeedSource(
                id="hacker-news",
                name="Hacker News",
                url="https://news.ycombinator.com/rss",
                type="rss",
                domain="software_development",
            ),
        ]
    else:
        sources = load_sources_from_catalog(catalog_path)
        print(f"📚 Loaded {len(sources)} sources from {catalog_path}")
    
    # Limit to 3 sources for testing
    sources = sources[:3]
    print(f"🧪 Testing with {len(sources)} sources:")
    for s in sources:
        print(f"   - {s.name} ({s.id})")
    print()
    
    # Create rate-limited extractor
    print("⚙️  Creating rate-limited extractor...")
    extractor = create_rate_limited_extractor(
        min_success_rate=30.0,  # Lower threshold for testing
        enable_metrics=True,
    )
    print(f"   Default rate limit: {extractor.default_rate_limit.requests_per_second} req/sec")
    print(f"   Min success rate: {extractor.min_success_rate}%")
    print()
    
    # Initialize cache
    db_path = Path("state/test_aggregation.db")
    db_path.parent.mkdir(parents=True, exist_ok=True)
    cache = FeedCache(db_path)
    
    # Test extraction on a few entries per source
    max_entries_per_source = 5
    total_entries = 0
    successful_extractions = 0
    failed_extractions = 0
    skipped_extractions = 0
    
    print("🚀 Starting extraction test...")
    print()
    
    start_time = time.time()
    
    for source in sources:
        print(f"📡 Processing: {source.name}")
        
        try:
            # Fetch feed entries
            from aggregator.feed_fetcher import FeedFetcher
            fetcher = FeedFetcher(cache)
            entries = fetcher.fetch_source(source)
            
            print(f"   Fetched {len(entries)} entries")
            
            # Test extraction on first N entries
            test_entries = entries[:max_entries_per_source]
            
            for i, entry in enumerate(test_entries, 1):
                print(f"   [{i}/{len(test_entries)}] Extracting: {entry.title[:50]}...")
                
                result = extractor.extract(entry.url)
                total_entries += 1
                
                if result.extraction_error:
                    if "skipped" in result.extraction_error.lower():
                        skipped_extractions += 1
                        print(f"      ⚠️  Skipped: {result.extraction_error[:60]}")
                    else:
                        failed_extractions += 1
                        print(f"      ❌ Failed: {result.extraction_error[:60]}")
                else:
                    successful_extractions += 1
                    print(f"      ✅ Success: {result.word_count} words")
                
                # Small delay between entries
                time.sleep(0.5)
            
            print()
            
        except Exception as e:
            print(f"   ❌ Error fetching feed: {e}")
            print()
    
    elapsed = time.time() - start_time
    
    # Print results
    print("=" * 60)
    print("Test Results")
    print("=" * 60)
    print(f"Duration: {elapsed:.1f}s")
    print(f"Total entries tested: {total_entries}")
    print(f"Successful: {successful_extractions} ({successful_extractions/total_entries*100:.1f}%)")
    print(f"Failed: {failed_extractions} ({failed_extractions/total_entries*100:.1f}%)")
    print(f"Skipped (low success rate): {skipped_extractions}")
    print()
    
    # Print metrics summary
    print("📊 Domain Metrics:")
    print("-" * 60)
    metrics_summary = extractor.get_metrics_summary()
    
    for domain, metrics in metrics_summary.get('domain_details', {}).items():
        print(f"\n{domain}:")
        print(f"   Requests: {metrics['total_requests']}")
        print(f"   Success rate: {metrics['success_rate']:.1f}%")
        print(f"   Rate limited: {metrics['rate_limited_count']}")
        print(f"   Timeouts: {metrics['timeout_count']}")
        print(f"   Avg latency: {metrics['average_latency_ms']:.0f}ms")
        if metrics['last_error']:
            print(f"   Last error: {metrics['last_error'][:50]}...")
    
    print()
    print(f"Overall success rate: {metrics_summary['overall_success_rate']:.1f}%")
    
    if metrics_summary['domains_with_low_success']:
        print(f"\n⚠️  Domains with low success rate: {metrics_summary['domains_with_low_success']}")
    
    # Save detailed results
    output_dir = Path("test-output")
    output_dir.mkdir(exist_ok=True)
    
    results_file = output_dir / f"rate_limited_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(results_file, 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'duration_seconds': elapsed,
            'sources_tested': [s.id for s in sources],
            'total_entries': total_entries,
            'successful': successful_extractions,
            'failed': failed_extractions,
            'skipped': skipped_extractions,
            'success_rate': successful_extractions / total_entries * 100 if total_entries > 0 else 0,
            'metrics': metrics_summary,
        }, f, indent=2)
    
    print()
    print(f"📁 Detailed results saved to: {results_file}")
    print()
    
    # Return success if we achieved >80% extraction rate (non-skipped)
    if total_entries > 0:
        actual_attempts = total_entries - skipped_extractions
        if actual_attempts > 0:
            success_rate = successful_extractions / actual_attempts * 100
            if success_rate >= 80:
                print("✅ TEST PASSED: Extraction success rate >= 80%")
                return 0
            else:
                print(f"⚠️  TEST INCOMPLETE: Extraction success rate {success_rate:.1f}% < 80%")
                return 1
    
    print("⚠️  No entries tested")
    return 1


if __name__ == '__main__':
    sys.exit(test_rate_limited_extraction())
