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

# Import aggregator modules (relative imports for package usage)
from .feed_fetcher import FeedCache, FeedFetcher, FeedSource, FeedEntry, load_sources_from_catalog
from .content_extractor import ContentExtractor, ExtractedContent
from .rate_limited_extractor import RateLimitedContentExtractor, create_rate_limited_extractor
from .deduplicator import Deduplicator, DuplicateResult
from .blog_scraper import BlogScraper, BlogEntry, load_blog_sources_from_catalog
from .newsletter_ingester import NewsletterIngester, NewsletterCache, load_newsletter_sources_from_catalog


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
        blog_scraper: Optional[BlogScraper] = None,
        blog_catalog_path: Optional[Path] = None,
        extract_content: bool = True,
        dedup_threshold: float = 0.85,
        enable_blog_scraping: bool = True,
        enable_newsletter_ingestion: bool = False,
        newsletter_catalog_path: Optional[Path] = None,
    ):
        self.cache = cache
        self.fetcher = fetcher or FeedFetcher(cache)

        # Use rate-limited extractor for production, fall back to basic extractor if provided
        if extract_content:
            if extractor:
                self.extractor = extractor
            else:
                # Use rate-limited extractor with sensible defaults
                self.extractor = create_rate_limited_extractor(
                    min_success_rate=50.0,
                    enable_metrics=True,
                )
        else:
            self.extractor = None

        self.deduplicator = deduplicator or Deduplicator(simhash_threshold=dedup_threshold)
        self.blog_scraper = blog_scraper or BlogScraper() if enable_blog_scraping else None
        self.blog_catalog_path = blog_catalog_path
        self.extract_content = extract_content
        self.enable_blog_scraping = enable_blog_scraping
        self.enable_newsletter_ingestion = enable_newsletter_ingestion
        self.newsletter_catalog_path = newsletter_catalog_path
        self.errors: list[str] = []

    def run(
        self,
        sources: Optional[list[FeedSource]] = None,
        domain_filter: Optional[str] = None,
        limit_sources: Optional[int] = None,
        verbose: bool = False,
        include_disabled: bool = False,
    ) -> PipelineResult:
        """
        Run the complete aggregation pipeline.

        Args:
            sources: List of sources to process (or None to use all from cache)
            domain_filter: Optional domain to filter sources (e.g., 'ai', 'software_development')
            limit_sources: Maximum number of sources to process
            verbose: Print progress information
            include_disabled: If True, also fetch disabled sources (for retry mode)

        Returns:
            PipelineResult with statistics about the run
        """
        started_at = datetime.now()
        self.errors = []

        # Load sources if not provided
        if sources is None:
            sources = self.cache.get_sources(domain=domain_filter, active_only=not include_disabled)

        if limit_sources:
            sources = sources[:limit_sources]

        if verbose:
            print(f"Pipeline starting: {len(sources)} sources to process")

        entries_fetched = 0
        entries_extracted = 0
        entries_deduplicated = 0
        entries_stored = 0
        auto_disabled_sources = []
        reenabled_sources = []

        for source in sources:
            # Skip inactive sources unless in retry mode
            if not source.active and not include_disabled:
                continue

            try:
                if verbose:
                    print(f"  Processing: {source.name} ({source.id})")

                # Step 1: Fetch entries from source
                entries = self._fetch_from_source(source, verbose)
                entries_fetched += len(entries)

                # If retry mode and fetch succeeded, re-enable the source
                if include_disabled and not source.active and len(entries) > 0:
                    self.cache.reenable_source(source.id)
                    reenabled_sources.append(source.id)
                    if verbose:
                        print(f"    ✅ Re-enabled {source.id} (fetch succeeded)")

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

                # Check if source should be automatically disabled
                if not include_disabled:  # Don't auto-disable during retry mode
                    error_count = self.cache.get_source_error_count(source.id)
                    if error_count >= FeedFetcher.ERROR_THRESHOLD:
                        self.cache.disable_source(
                            source.id,
                            f"Auto-disabled after {error_count} consecutive failures: {str(e)[:100]}"
                        )
                        auto_disabled_sources.append(source.id)
                        if verbose:
                            print(f"    ⚠️ AUTO-DISABLED after {error_count} failures")

        # Print auto-disable summary
        if auto_disabled_sources:
            print(f"\n⚠️  {len(auto_disabled_sources)} source(s) auto-disabled due to repeated failures:")
            for sid in auto_disabled_sources:
                print(f"    - {sid}")
            print(f"\nUse --retry-disabled to attempt fetching these sources again.")

        # Print re-enable summary
        if reenabled_sources:
            print(f"\n✅ {len(reenabled_sources)} source(s) re-enabled after successful fetch:")
            for sid in reenabled_sources:
                print(f"    - {sid}")

        # Step 4: Scrape blog sources (after RSS feeds)
        if self.enable_blog_scraping and self.blog_scraper and self.blog_catalog_path:
            try:
                blog_result = self._scrape_blog_sources(domain_filter, limit_sources, verbose)
                entries_fetched += blog_result['entries_fetched']
                entries_extracted += blog_result['entries_extracted']
                entries_deduplicated += blog_result['entries_deduplicated']
                entries_stored += blog_result['entries_stored']
            except Exception as e:
                err_msg = f"Error scraping blog sources: {e}"
                self.errors.append(err_msg)
                if verbose:
                    print(f"  ✗ {err_msg}")

        # Step 5: Ingest newsletters (after blog scraping)
        if self.enable_newsletter_ingestion and self.newsletter_catalog_path:
            try:
                newsletter_result = self._ingest_newsletters(domain_filter, limit_sources, verbose)
                entries_fetched += newsletter_result['entries_fetched']
                entries_extracted += newsletter_result['entries_extracted']
                entries_deduplicated += newsletter_result['entries_deduplicated']
                entries_stored += newsletter_result['entries_stored']
            except Exception as e:
                err_msg = f"Error ingesting newsletters: {e}"
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

    def _blog_entry_to_feed_entry(self, blog_entry: BlogEntry) -> FeedEntry:
        """Convert a BlogEntry to FeedEntry format."""
        return FeedEntry(
            id=blog_entry.id,
            title=blog_entry.title,
            url=blog_entry.url,
            source_id=blog_entry.source_id,
            published_at=blog_entry.published_at,
            summary=blog_entry.summary,
            author=blog_entry.author,
            content=blog_entry.content,
            fetched_at=blog_entry.scraped_at
        )

    def _scrape_blog_sources(
        self,
        domain_filter: Optional[str] = None,
        limit_sources: Optional[int] = None,
        verbose: bool = False
    ) -> dict:
        """Scrape blog sources and process them through the pipeline."""
        if not self.blog_scraper or not self.blog_catalog_path:
            return {'entries_fetched': 0, 'entries_extracted': 0, 'entries_deduplicated': 0, 'entries_stored': 0}

        # Load blog sources from catalog
        blog_sources = load_blog_sources_from_catalog(self.blog_catalog_path)

        if domain_filter:
            blog_sources = [s for s in blog_sources if s.domain == domain_filter]

        if limit_sources:
            blog_sources = blog_sources[:limit_sources]

        if verbose:
            print(f"Blog scraping: {len(blog_sources)} sources to scrape")

        entries_fetched = 0
        entries_extracted = 0
        entries_deduplicated = 0
        entries_stored = 0

        for source in blog_sources:
            if not source.active:
                continue

            try:
                if verbose:
                    print(f"  Scraping: {source.name} ({source.id})")

                # Scrape entries from source (with content extraction)
                blog_entries = self.blog_scraper.scrape_source(source, extract_content=self.extract_content)
                entries_fetched += len(blog_entries)

                # Process each entry (dedup + store)
                processed_entries = []
                for blog_entry in blog_entries:
                    try:
                        # Check for duplicates using URL and title
                        dup_check = self.deduplicator.check_duplicate(
                            blog_entry.id, blog_entry.url, blog_entry.title, blog_entry.summary or blog_entry.title
                        )

                        if dup_check.is_duplicate:
                            entries_deduplicated += 1
                            if verbose:
                                print(f"    ⚠ Duplicate skipped: {blog_entry.title[:50]}...")
                            continue

                        # Track content extraction
                        if blog_entry.content:
                            entries_extracted += 1

                        # Mark as tracked in deduplicator
                        self.deduplicator.add(
                            blog_entry.id, blog_entry.url, blog_entry.title, blog_entry.summary or blog_entry.title
                        )

                        # Convert to FeedEntry and add to processed list
                        feed_entry = self._blog_entry_to_feed_entry(blog_entry)
                        processed_entries.append(feed_entry)

                    except Exception as e:
                        err_msg = f"Error processing blog entry {blog_entry.id}: {e}"
                        self.errors.append(err_msg)
                        if verbose:
                            print(f"    ✗ {err_msg}")

                # Store processed entries
                if processed_entries:
                    self.cache.save_entries(processed_entries)
                    entries_stored += len(processed_entries)
                    if verbose:
                        print(f"    ✓ Stored {len(processed_entries)} entries")

            except Exception as e:
                err_msg = f"Error scraping blog source {source.id}: {e}"
                self.errors.append(err_msg)
                if verbose:
                    print(f"  ✗ {err_msg}")

        return {
            'entries_fetched': entries_fetched,
            'entries_extracted': entries_extracted,
            'entries_deduplicated': entries_deduplicated,
            'entries_stored': entries_stored
        }

    def _ingest_newsletters(
        self,
        domain_filter: Optional[str] = None,
        limit_sources: Optional[int] = None,
        verbose: bool = False
    ) -> dict:
        """Ingest newsletters from configured sources."""
        if not self.newsletter_catalog_path:
            return {'entries_fetched': 0, 'entries_extracted': 0, 'entries_deduplicated': 0, 'entries_stored': 0}

        # Load newsletter sources from catalog
        newsletter_sources = load_newsletter_sources_from_catalog(self.newsletter_catalog_path)

        if domain_filter:
            newsletter_sources = [s for s in newsletter_sources if s.domain == domain_filter]

        if limit_sources:
            newsletter_sources = newsletter_sources[:limit_sources]

        if verbose:
            print(f"Newsletter ingestion: {len(newsletter_sources)} sources to process")

        # Create newsletter ingester with shared cache
        newsletter_cache = NewsletterCache(self.cache.db_path)
        ingester = NewsletterIngester(newsletter_cache)

        entries_fetched = 0
        entries_extracted = 0
        entries_deduplicated = 0
        entries_stored = 0

        for source in newsletter_sources:
            if not source.active:
                continue

            try:
                if verbose:
                    print(f"  Ingesting: {source.name} ({source.id})")

                # Ingest entries from source
                newsletter_entries = ingester.ingest_source(source)
                entries_fetched += len(newsletter_entries)

                # Process each entry (dedup + convert to feed entries + store)
                processed_entries = []
                for nl_entry in newsletter_entries:
                    try:
                        # Check for duplicates using URL and title
                        dup_check = self.deduplicator.check_duplicate(
                            nl_entry.id, nl_entry.url, nl_entry.title, nl_entry.content_text or nl_entry.title
                        )

                        if dup_check.is_duplicate:
                            entries_deduplicated += 1
                            if verbose:
                                print(f"    ⚠ Duplicate skipped: {nl_entry.title[:50]}...")
                            continue

                        # Track content extraction (newsletters already have content)
                        if nl_entry.content_text:
                            entries_extracted += 1

                        # Mark as tracked in deduplicator
                        self.deduplicator.add(
                            nl_entry.id, nl_entry.url, nl_entry.title, nl_entry.content_text or nl_entry.title
                        )

                        # Convert to FeedEntry format
                        feed_entry = FeedEntry(
                            id=nl_entry.id,
                            title=nl_entry.title,
                            url=nl_entry.url,
                            source_id=nl_entry.newsletter_id,
                            published_at=nl_entry.published_at,
                            summary=nl_entry.content_text[:500] if nl_entry.content_text else None,
                            author=nl_entry.author,
                            content=nl_entry.content_text,
                            fetched_at=nl_entry.fetched_at
                        )
                        processed_entries.append(feed_entry)

                    except Exception as e:
                        err_msg = f"Error processing newsletter entry {nl_entry.id}: {e}"
                        self.errors.append(err_msg)
                        if verbose:
                            print(f"    ✗ {err_msg}")

                # Store processed entries
                if processed_entries:
                    self.cache.save_entries(processed_entries)
                    entries_stored += len(processed_entries)
                    if verbose:
                        print(f"    ✓ Stored {len(processed_entries)} entries")

            except Exception as e:
                err_msg = f"Error ingesting newsletter source {source.id}: {e}"
                self.errors.append(err_msg)
                if verbose:
                    print(f"  ✗ {err_msg}")

        return {
            'entries_fetched': entries_fetched,
            'entries_extracted': entries_extracted,
            'entries_deduplicated': entries_deduplicated,
            'entries_stored': entries_stored
        }

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
    blog_catalog_path: Optional[Path] = None,
    enable_blog_scraping: bool = True,
    enable_newsletter_ingestion: bool = False,
    newsletter_catalog_path: Optional[Path] = None,
    retry_disabled: bool = False,
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
        blog_catalog_path: Path to blog scraper catalog JSON
        enable_blog_scraping: Whether to enable blog scraping
        enable_newsletter_ingestion: Whether to enable newsletter ingestion
        newsletter_catalog_path: Path to newsletter catalog JSON
        retry_disabled: Whether to retry disabled sources and re-enable if successful

    Returns:
        PipelineResult
    """
    # Initialize components
    cache = FeedCache(db_path)

    # Load RSS sources from catalog into cache
    if catalog_path.exists():
        sources = load_sources_from_catalog(catalog_path)
        for source in sources:
            cache.save_source(source)
        if verbose:
            print(f"Loaded {len(sources)} RSS sources from catalog")

    # Handle retry-disabled mode
    if retry_disabled:
        disabled = cache.get_disabled_sources()
        if disabled:
            print(f"\n🔁 Retrying {len(disabled)} disabled source(s)...")
            for src in disabled:
                print(f"  - {src.id} ({src.name})")
            print()
        else:
            print("No disabled sources to retry.")

    # Create and run pipeline
    pipeline = AggregationPipeline(
        cache=cache,
        extract_content=extract,
        blog_catalog_path=blog_catalog_path,
        enable_blog_scraping=enable_blog_scraping,
        enable_newsletter_ingestion=enable_newsletter_ingestion,
        newsletter_catalog_path=newsletter_catalog_path,
    )

    result = pipeline.run(
        domain_filter=domain,
        limit_sources=limit,
        verbose=verbose,
        include_disabled=retry_disabled,
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
    parser.add_argument(
        '--blog-catalog',
        type=Path,
        default=Path('sources/blog_scraper_catalog.json'),
        help='Path to blog scraper catalog JSON'
    )
    parser.add_argument(
        '--no-blog-scraping',
        action='store_true',
        help='Skip blog scraping (RSS only)'
    )
    parser.add_argument(
        '--enable-newsletter-ingestion',
        action='store_true',
        help='Enable newsletter ingestion from configured sources'
    )
    parser.add_argument(
        '--newsletter-catalog',
        type=Path,
        default=Path('sources/newsletter_catalog.json'),
        help='Path to newsletter catalog JSON'
    )
    parser.add_argument(
        '--retry-disabled',
        action='store_true',
        help='Retry disabled sources and re-enable if successful'
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
        blog_catalog_path=args.blog_catalog,
        enable_blog_scraping=not args.no_blog_scraping,
        enable_newsletter_ingestion=args.enable_newsletter_ingestion,
        newsletter_catalog_path=args.newsletter_catalog,
        retry_disabled=args.retry_disabled,
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
