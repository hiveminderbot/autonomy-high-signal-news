#!/usr/bin/env python3
"""
Aggregation Pipeline for High-Signal News

Unified pipeline that orchestrates feed fetching, content extraction,
deduplication, and storage into a single workflow.
"""

import json
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

# Import aggregator modules
from aggregator.feed_fetcher import FeedCache, FeedFetcher, FeedSource, FeedEntry, load_sources_from_catalog
from aggregator.content_extractor import ContentExtractor, ExtractedContent
from aggregator.deduplicator import Deduplicator, DuplicateResult


@dataclass
class PipelineResult:
    """Result of a pipeline run."""
    started_at: datetime
    completed_at: datetime
    sources_processed: int
    entries_fetched: int
    entries_extracted: int
    entries_deduplicated: int
    entries_stored: int
    errors: list[str]
    
    def to_dict(self) -> dict:
        return {
            'started_at': self.started_at.isoformat(),
            'completed_at': self.completed_at.isoformat(),
            'duration_seconds': (self.completed_at - self.started_at).total_seconds(),
            'sources_processed': self.sources_processed,
            'entries_fetched': self.entries_fetched,
            'entries_extracted': self.entries_extracted,
            'entries_deduplicated': self.entries_deduplicated,
            'entries_stored': self.entries_stored,
            'errors': self.errors,
        }


class AggregationPipeline:
    """
    End-to-end pipeline for aggregating, extracting, deduplicating,
    and storing news articles from multiple sources.
    """
    
    def __init__(
        self,
        cache: FeedCache,
        fetcher: Optional[FeedFetcher] = None,
        extractor: Optional[ContentExtractor] = None,
        deduplicator: Optional[Deduplicator] = None,
        extract_content: bool = True,
        dedup_threshold: float = 0.85,
    ):
        self.cache = cache
        self.fetcher = fetcher or FeedFetcher(cache)
        self.extractor = extractor or ContentExtractor() if extract_content else None
        self.deduplicator = deduplicator or Deduplicator(simhash_threshold=dedup_threshold)
        self.extract_content = extract_content
        self.errors: list[str] = []
    
    def run(
        self,
        sources: Optional[list[FeedSource]] = None,
        domain_filter: Optional[str] = None,
        limit_sources: Optional[int] = None,
        verbose: bool = False,
    ) -> PipelineResult:
        """
        Run the complete aggregation pipeline.
        
        Args:
            sources: List of sources to process (or None to use all from cache)
            domain_filter: Optional domain to filter sources (e.g., 'ai', 'software_development')
            limit_sources: Maximum number of sources to process
            verbose: Print progress information
            
        Returns:
            PipelineResult with statistics about the run
        """
        started_at = datetime.now()
        self.errors = []
        
        # Load sources if not provided
        if sources is None:
            sources = self.cache.get_sources(domain=domain_filter)
        
        if limit_sources:
            sources = sources[:limit_sources]
        
        if verbose:
            print(f"Pipeline starting: {len(sources)} sources to process")
        
        entries_fetched = 0
        entries_extracted = 0
        entries_deduplicated = 0
        entries_stored = 0
        
        for source in sources:
            if not source.active:
                continue
                
            try:
                if verbose:
                    print(f"  Processing: {source.name} ({source.id})")
                
                # Step 1: Fetch entries from source
                entries = self._fetch_from_source(source, verbose)
                entries_fetched += len(entries)
                
                # Step 2: Process each entry (extract + dedup)
                processed_entries = []
                for entry in entries:
                    try:
                        # Check for duplicates
                        dup_check = self.deduplicator.check_duplicate(
                            entry.id, entry.url, entry.title, entry.summary or entry.title
                        )
                        
                        if dup_check.is_duplicate:
                            entries_deduplicated += 1
                            if verbose:
                                print(f"    ⚠ Duplicate skipped: {entry.title[:50]}...")
                            continue
                        
                        # Extract content if enabled
                        if self.extract_content and self.extractor:
                            extracted = self._extract_content(entry, verbose)
                            if extracted:
                                entry = self._merge_extracted_content(entry, extracted)
                                entries_extracted += 1
                        
                        # Mark as tracked in deduplicator
                        self.deduplicator.add(
                            entry.id, entry.url, entry.title, entry.summary or entry.title
                        )
                        
                        processed_entries.append(entry)
                        
                    except Exception as e:
                        err_msg = f"Error processing entry {entry.id}: {e}"
                        self.errors.append(err_msg)
                        if verbose:
                            print(f"    ✗ {err_msg}")
                
                # Step 3: Store processed entries
                if processed_entries:
                    self.cache.save_entries(processed_entries)
                    entries_stored += len(processed_entries)
                    if verbose:
                        print(f"    ✓ Stored {len(processed_entries)} entries")
                
            except Exception as e:
                err_msg = f"Error processing source {source.id}: {e}"
                self.errors.append(err_msg)
                if verbose:
                    print(f"  ✗ {err_msg}")
        
        completed_at = datetime.now()
        
        return PipelineResult(
            started_at=started_at,
            completed_at=completed_at,
            sources_processed=len(sources),
            entries_fetched=entries_fetched,
            entries_extracted=entries_extracted,
            entries_deduplicated=entries_deduplicated,
            entries_stored=entries_stored,
            errors=self.errors,
        )
    
    def _fetch_from_source(self, source: FeedSource, verbose: bool) -> list[FeedEntry]:
        """Fetch entries from a single source."""
        if not self.cache.should_fetch(source.id):
            if verbose:
                print(f"    (skipped - fetched recently)")
            return []
        
        entries = self.fetcher.fetch_source(source)
        
        # Log the fetch
        self.cache.log_fetch(
            source_id=source.id,
            entries_count=len(entries),
            success=True,
        )
        
        return entries
    
    def _extract_content(self, entry: FeedEntry, verbose: bool) -> Optional[ExtractedContent]:
        """Extract full content from an entry URL."""
        if not self.extractor:
            return None
        
        try:
            extracted = self.extractor.extract(entry.url)
            
            if extracted.extraction_error:
                if verbose:
                    print(f"    ⚠ Extraction warning for {entry.url}: {extracted.extraction_error}")
            
            return extracted
            
        except Exception as e:
            if verbose:
                print(f"    ✗ Extraction failed for {entry.url}: {e}")
            return None
    
    def _merge_extracted_content(self, entry: FeedEntry, extracted: ExtractedContent) -> FeedEntry:
        """Merge extracted content into a feed entry."""
        # Update entry with extracted content (only if better than existing)
        if extracted.title and (not entry.title or len(extracted.title) > len(entry.title)):
            entry.title = extracted.title
        
        if extracted.author and not entry.author:
            entry.author = extracted.author
        
        if extracted.published_at and not entry.published_at:
            entry.published_at = extracted.published_at
        
        # Use extracted text as content
        if extracted.content_text:
            entry.content = extracted.content_text
        
        return entry
    
    def get_stats(self) -> dict:
        """Get pipeline statistics."""
        return {
            'deduplicator': self.deduplicator.get_stats(),
            'errors_count': len(self.errors),
            'recent_errors': self.errors[-5:] if self.errors else [],
        }


def run_pipeline_command(
    catalog_path: Path,
    db_path: Path,
    domain: Optional[str] = None,
    limit: Optional[int] = None,
    extract: bool = True,
    verbose: bool = False,
) -> PipelineResult:
    """
    Command-line interface to run the pipeline.
    
    Args:
        catalog_path: Path to sources catalog JSON
        db_path: Path to SQLite database
        domain: Optional domain filter
        limit: Maximum sources to process
        extract: Whether to extract full content
        verbose: Print progress
        
    Returns:
        PipelineResult
    """
    # Initialize components
    cache = FeedCache(db_path)
    
    # Load sources from catalog into cache
    if catalog_path.exists():
        sources = load_sources_from_catalog(catalog_path)
        for source in sources:
            cache.save_source(source)
        if verbose:
            print(f"Loaded {len(sources)} sources from catalog")
    
    # Create and run pipeline
    pipeline = AggregationPipeline(
        cache=cache,
        extract_content=extract,
    )
    
    result = pipeline.run(
        domain_filter=domain,
        limit_sources=limit,
        verbose=verbose,
    )
    
    return result


def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='High-Signal News Aggregation Pipeline'
    )
    parser.add_argument(
        '--catalog', '-c',
        type=Path,
        default=Path('sources/catalog.json'),
        help='Path to sources catalog JSON'
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
        '--limit', '-l',
        type=int,
        help='Maximum number of sources to process'
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
    
    result = run_pipeline_command(
        catalog_path=args.catalog,
        db_path=args.db,
        domain=args.domain,
        limit=args.limit,
        extract=not args.no_extract,
        verbose=args.verbose,
    )
    
    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(f"\n{'='*50}")
        print(f"Pipeline Complete")
        print(f"{'='*50}")
        print(f"Duration: {result.to_dict()['duration_seconds']:.2f}s")
        print(f"Sources processed: {result.sources_processed}")
        print(f"Entries fetched: {result.entries_fetched}")
        print(f"Entries extracted: {result.entries_extracted}")
        print(f"Duplicates filtered: {result.entries_deduplicated}")
        print(f"Entries stored: {result.entries_stored}")
        if result.errors:
            print(f"Errors: {len(result.errors)}")
            for err in result.errors[:5]:
                print(f"  - {err}")


if __name__ == '__main__':
    main()
