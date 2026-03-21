#!/usr/bin/env python3
"""
Extended Aggregation Pipeline with Newsletter Support

Extends the base aggregation pipeline to include newsletter ingestion
alongside RSS feed aggregation.
"""

import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

# Import base pipeline
from aggregator.pipeline import (
    AggregationPipeline, PipelineResult, run_pipeline_command
)
from aggregator.feed_fetcher import FeedCache, FeedEntry
from aggregator.content_extractor import ContentExtractor
from aggregator.deduplicator import Deduplicator

# Import newsletter components
from aggregator.newsletter_ingester import (
    NewsletterCache, NewsletterIngester, NewsletterSource,
    load_newsletter_sources_from_catalog as load_newsletter_catalog
)


@dataclass
class ExtendedPipelineResult(PipelineResult):
    """Extended result including newsletter processing."""
    newsletter_sources_processed: int = 0
    newsletter_entries_fetched: int = 0
    newsletter_entries_stored: int = 0
    
    def to_dict(self) -> dict:
        base = super().to_dict()
        base.update({
            'newsletter_sources_processed': self.newsletter_sources_processed,
            'newsletter_entries_fetched': self.newsletter_entries_fetched,
            'newsletter_entries_stored': self.newsletter_entries_stored,
        })
        return base


class ExtendedAggregationPipeline(AggregationPipeline):
    """
    Extended pipeline that supports both RSS feeds and newsletters.
    """
    
    def __init__(
        self,
        cache: FeedCache,
        newsletter_cache: Optional[NewsletterCache] = None,
        fetcher=None,
        extractor: Optional[ContentExtractor] = None,
        deduplicator: Optional[Deduplicator] = None,
        newsletter_ingester: Optional[NewsletterIngester] = None,
        extract_content: bool = True,
        dedup_threshold: float = 0.85,
    ):
        super().__init__(
            cache=cache,
            fetcher=fetcher,
            extractor=extractor,
            deduplicator=deduplicator,
            extract_content=extract_content,
            dedup_threshold=dedup_threshold,
        )
        self.newsletter_cache = newsletter_cache
        self.newsletter_ingester = newsletter_ingester
    
    def run_with_newsletters(
        self,
        feed_sources=None,
        newsletter_sources: Optional[list[NewsletterSource]] = None,
        domain_filter: Optional[str] = None,
        limit_feed_sources: Optional[int] = None,
        limit_newsletter_sources: Optional[int] = None,
        verbose: bool = False,
    ) -> ExtendedPipelineResult:
        """
        Run pipeline with both feeds and newsletters.
        
        Args:
            feed_sources: RSS feed sources
            newsletter_sources: Newsletter sources
            domain_filter: Filter both by domain
            limit_feed_sources: Max feed sources
            limit_newsletter_sources: Max newsletter sources
            verbose: Print progress
            
        Returns:
            ExtendedPipelineResult with combined statistics
        """
        started_at = datetime.now()
        self.errors = []
        
        # Run base feed pipeline
        if verbose:
            print("\n--- Phase 1: RSS Feed Processing ---")
        
        feed_result = self.run(
            sources=feed_sources,
            domain_filter=domain_filter,
            limit_sources=limit_feed_sources,
            verbose=verbose,
        )
        
        # Process newsletters if cache and ingester available
        newsletter_entries_fetched = 0
        newsletter_entries_stored = 0
        newsletter_sources_processed = 0
        
        if self.newsletter_cache and self.newsletter_ingester and newsletter_sources is not None:
            if verbose:
                print("\n--- Phase 2: Newsletter Processing ---")
            
            if domain_filter:
                newsletter_sources = [
                    s for s in newsletter_sources 
                    if s.domain == domain_filter
                ]
            
            if limit_newsletter_sources:
                newsletter_sources = newsletter_sources[:limit_newsletter_sources]
            
            for source in newsletter_sources:
                if not source.active:
                    continue
                    
                try:
                    if verbose:
                        print(f"  Processing: {source.name} ({source.id})")
                    
                    # Ingest newsletter
                    entries = self.newsletter_ingester.ingest_source(source)
                    newsletter_entries_fetched += len(entries)
                    newsletter_sources_processed += 1
                    
                    # Process entries through deduplication
                    for entry in entries:
                        try:
                            # Convert to feed entry format for deduplication
                            feed_entry_data = self.newsletter_ingester.convert_to_feed_entries([entry])[0]
                            
                            # Check for duplicates
                            dup_check = self.deduplicator.check_duplicate(
                                feed_entry_data['id'],
                                feed_entry_data['url'],
                                feed_entry_data['title'],
                                feed_entry_data.get('summary') or feed_entry_data['title']
                            )
                            
                            if dup_check.is_duplicate:
                                feed_result.entries_deduplicated += 1
                                if verbose:
                                    print(f"    ⚠ Duplicate skipped: {feed_entry_data['title'][:50]}...")
                                continue
                            
                            # Add to deduplicator
                            self.deduplicator.add(
                                feed_entry_data['id'],
                                feed_entry_data['url'],
                                feed_entry_data['title'],
                                feed_entry_data.get('summary') or feed_entry_data['title']
                            )
                            
                            # Save to feed cache (convert format)
                            feed_entry = FeedEntry(
                                id=feed_entry_data['id'],
                                title=feed_entry_data['title'],
                                url=feed_entry_data['url'],
                                source_id=feed_entry_data['source_id'],
                                published_at=feed_entry_data.get('published_at'),
                                summary=feed_entry_data.get('summary'),
                                author=feed_entry_data.get('author'),
                                content=feed_entry_data.get('content'),
                                fetched_at=feed_entry_data['fetched_at']
                            )
                            self.cache.save_entries([feed_entry])
                            newsletter_entries_stored += 1
                            
                        except Exception as e:
                            err_msg = f"Error processing newsletter entry {entry.id}: {e}"
                            self.errors.append(err_msg)
                            if verbose:
                                print(f"    ✗ {err_msg}")
                    
                    if verbose and entries:
                        print(f"    ✓ Stored {len(entries)} newsletter entries")
                        
                except Exception as e:
                    err_msg = f"Error processing newsletter source {source.id}: {e}"
                    self.errors.append(err_msg)
                    if verbose:
                        print(f"  ✗ {err_msg}")
        
        completed_at = datetime.now()
        
        return ExtendedPipelineResult(
            started_at=started_at,
            completed_at=completed_at,
            sources_processed=feed_result.sources_processed,
            entries_fetched=feed_result.entries_fetched,
            entries_extracted=feed_result.entries_extracted,
            entries_deduplicated=feed_result.entries_deduplicated,
            entries_stored=feed_result.entries_stored,
            errors=self.errors + feed_result.errors,
            newsletter_sources_processed=newsletter_sources_processed,
            newsletter_entries_fetched=newsletter_entries_fetched,
            newsletter_entries_stored=newsletter_entries_stored,
        )


def run_extended_pipeline(
    feed_catalog_path: Path,
    newsletter_catalog_path: Path,
    db_path: Path,
    domain: Optional[str] = None,
    limit_feeds: Optional[int] = None,
    limit_newsletters: Optional[int] = None,
    extract: bool = True,
    verbose: bool = False,
) -> ExtendedPipelineResult:
    """
    Run the extended pipeline with both feeds and newsletters.
    
    Args:
        feed_catalog_path: Path to RSS sources catalog
        newsletter_catalog_path: Path to newsletter sources catalog
        db_path: Path to SQLite database
        domain: Optional domain filter
        limit_feeds: Max RSS sources
        limit_newsletters: Max newsletter sources
        extract: Whether to extract full content
        verbose: Print progress
        
    Returns:
        ExtendedPipelineResult
    """
    # Initialize caches
    feed_cache = FeedCache(db_path)
    newsletter_cache = NewsletterCache(db_path)
    
    # Load RSS sources
    if feed_catalog_path.exists():
        from aggregator.feed_fetcher import load_sources_from_catalog
        feed_sources = load_sources_from_catalog(feed_catalog_path)
        for source in feed_sources:
            feed_cache.save_source(source)
        if verbose:
            print(f"Loaded {len(feed_sources)} RSS sources from catalog")
    else:
        feed_sources = []
    
    # Load newsletter sources
    if newsletter_catalog_path.exists():
        newsletter_sources = load_newsletter_catalog(newsletter_catalog_path)
        for source in newsletter_sources:
            newsletter_cache.save_source(source)
        if verbose:
            print(f"Loaded {len(newsletter_sources)} newsletter sources from catalog")
    else:
        newsletter_sources = []
    
    # Create ingester
    newsletter_ingester = NewsletterIngester(newsletter_cache)
    
    # Create and run extended pipeline
    pipeline = ExtendedAggregationPipeline(
        cache=feed_cache,
        newsletter_cache=newsletter_cache,
        newsletter_ingester=newsletter_ingester,
        extract_content=extract,
    )
    
    result = pipeline.run_with_newsletters(
        feed_sources=feed_sources,
        newsletter_sources=newsletter_sources,
        domain_filter=domain,
        limit_feed_sources=limit_feeds,
        limit_newsletter_sources=limit_newsletters,
        verbose=verbose,
    )
    
    return result


def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Extended High-Signal News Aggregation Pipeline (with Newsletters)'
    )
    parser.add_argument(
        '--feed-catalog', '-c',
        type=Path,
        default=Path('sources/catalog.json'),
        help='Path to RSS sources catalog JSON'
    )
    parser.add_argument(
        '--newsletter-catalog', '-n',
        type=Path,
        default=Path('sources/newsletter_catalog.json'),
        help='Path to newsletter sources catalog JSON'
    )
    parser.add_argument(
        '--db', '-d',
        type=Path,
        default=Path('data/aggregator.db'),
        help='Path to SQLite database'
    )
    parser.add_argument(
        '--domain',
        help='Filter sources by domain (ai, software_development, investment)'
    )
    parser.add_argument(
        '--limit-feeds',
        type=int,
        help='Maximum number of RSS sources to process'
    )
    parser.add_argument(
        '--limit-newsletters',
        type=int,
        help='Maximum number of newsletter sources to process'
    )
    parser.add_argument(
        '--no-extract',
        action='store_true',
        help='Skip content extraction (faster)'
    )
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Print progress information'
    )
    parser.add_argument(
        '--json',
        action='store_true',
        help='Output results as JSON'
    )
    
    args = parser.parse_args()
    
    # Ensure data directory exists
    args.db.parent.mkdir(parents=True, exist_ok=True)
    
    result = run_extended_pipeline(
        feed_catalog_path=args.feed_catalog,
        newsletter_catalog_path=args.newsletter_catalog,
        db_path=args.db,
        domain=args.domain,
        limit_feeds=args.limit_feeds,
        limit_newsletters=args.limit_newsletters,
        extract=not args.no_extract,
        verbose=args.verbose,
    )
    
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(f"\n{'='*50}")
        print(f"Extended Pipeline Complete")
        print(f"{'='*50}")
        print(f"Duration: {result.to_dict()['duration_seconds']:.2f}s")
        print(f"\nRSS Feeds:")
        print(f"  Sources processed: {result.sources_processed}")
        print(f"  Entries fetched: {result.entries_fetched}")
        print(f"  Entries extracted: {result.entries_extracted}")
        print(f"  Duplicates filtered: {result.entries_deduplicated}")
        print(f"  Entries stored: {result.entries_stored}")
        print(f"\nNewsletters:")
        print(f"  Sources processed: {result.newsletter_sources_processed}")
        print(f"  Entries fetched: {result.newsletter_entries_fetched}")
        print(f"  Entries stored: {result.newsletter_entries_stored}")
        print(f"\nTotal entries stored: {result.entries_stored + result.newsletter_entries_stored}")
        if result.errors:
            print(f"Errors: {len(result.errors)}")
            for err in result.errors[:5]:
                print(f"  - {err}")


if __name__ == '__main__':
    main()
