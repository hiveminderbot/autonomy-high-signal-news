#!/usr/bin/env python3
"""
Daily Aggregation Runner for High-Signal News

Executes the full aggregation pipeline including:
- RSS feed fetching
- Newsletter ingestion
- Content extraction
- Deduplication
- Storage

Designed to be run as a daily cron job.
"""

import json
import sys
import logging
from datetime import datetime
from pathlib import Path

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent))

from aggregator.pipeline_extended import ExtendedAggregationPipeline, ExtendedPipelineResult
from aggregator.feed_fetcher import FeedCache, load_sources_from_catalog
from aggregator.newsletter_ingester import NewsletterCache, NewsletterIngester, load_newsletter_sources_from_catalog


# Configuration
DEFAULT_DB_PATH = Path("state/aggregation.db")
DEFAULT_NEWSLETTER_DB_PATH = Path("state/newsletters.db")
DEFAULT_CATALOG_PATH = Path("sources/sources-ai.json")
DEFAULT_NEWSLETTER_CATALOG_PATH = Path("sources/newsletter_catalog.json")
DEFAULT_OUTPUT_DIR = Path("output")
DEFAULT_LOG_DIR = Path("logs")


def setup_logging(log_dir: Path, run_id: str) -> logging.Logger:
    """Configure logging for the daily run."""
    log_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger("daily_aggregation")
    logger.setLevel(logging.INFO)

    # File handler
    log_file = log_dir / f"aggregation_{run_id}.log"
    fh = logging.FileHandler(log_file)
    fh.setLevel(logging.INFO)

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)

    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)

    logger.addHandler(fh)
    logger.addHandler(ch)

    return logger


def run_daily_aggregation(
    db_path: Path = DEFAULT_DB_PATH,
    newsletter_db_path: Path = DEFAULT_NEWSLETTER_DB_PATH,
    catalog_path: Path = DEFAULT_CATALOG_PATH,
    newsletter_catalog_path: Path = DEFAULT_NEWSLETTER_CATALOG_PATH,
    output_dir: Path = DEFAULT_OUTPUT_DIR,
    log_dir: Path = DEFAULT_LOG_DIR,
    domain: str = None,
    limit_feeds: int = None,
    limit_newsletters: int = None,
    extract_content: bool = True,
) -> ExtendedPipelineResult:
    """
    Run the complete daily aggregation pipeline.

    Args:
        db_path: Path to feed database
        newsletter_db_path: Path to newsletter database
        catalog_path: Path to feed sources catalog
        newsletter_catalog_path: Path to newsletter sources catalog
        output_dir: Directory for output files
        log_dir: Directory for log files
        domain: Optional domain filter (e.g., 'ai', 'software_development')
        limit_feeds: Maximum feed sources to process
        limit_newsletters: Maximum newsletter sources to process
        extract_content: Whether to extract full article content

    Returns:
        ExtendedPipelineResult with full statistics
    """
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    logger = setup_logging(log_dir, run_id)

    logger.info(f"Starting daily aggregation run: {run_id}")
    logger.info(f"Domain filter: {domain or 'all'}")
    logger.info(f"Feed limit: {limit_feeds or 'unlimited'}")
    logger.info(f"Newsletter limit: {limit_newsletters or 'unlimited'}")

    try:
        # Initialize caches
        logger.info("Initializing databases...")
        feed_cache = FeedCache(db_path)
        newsletter_cache = NewsletterCache(newsletter_db_path)

        # Load sources from catalogs
        logger.info(f"Loading feed sources from {catalog_path}...")
        feed_sources = load_sources_from_catalog(catalog_path)
        logger.info(f"Loaded {len(feed_sources)} feed sources")

        logger.info(f"Loading newsletter sources from {newsletter_catalog_path}...")
        newsletter_sources = load_newsletter_sources_from_catalog(newsletter_catalog_path)
        logger.info(f"Loaded {len(newsletter_sources)} newsletter sources")

        # Create and run pipeline
        logger.info("Initializing aggregation pipeline...")
        newsletter_ingester = NewsletterIngester(newsletter_cache)
        pipeline = ExtendedAggregationPipeline(
            cache=feed_cache,
            newsletter_cache=newsletter_cache,
            newsletter_ingester=newsletter_ingester,
            extract_content=extract_content,
        )

        logger.info("Running aggregation pipeline...")
        result = pipeline.run_with_newsletters(
            feed_sources=feed_sources,
            newsletter_sources=newsletter_sources,
            domain_filter=domain,
            limit_feed_sources=limit_feeds,
            limit_newsletter_sources=limit_newsletters,
            verbose=True,
        )

        # Save results
        output_dir.mkdir(parents=True, exist_ok=True)
        results_file = output_dir / f"aggregation_results_{run_id}.json"

        with open(results_file, 'w') as f:
            json.dump(result.to_dict(), f, indent=2)

        logger.info(f"Results saved to {results_file}")

        # Print summary
        logger.info("=" * 50)
        logger.info("DAILY AGGREGATION COMPLETE")
        logger.info("=" * 50)
        logger.info(f"Duration: {result.to_dict()['duration_seconds']:.1f}s")
        logger.info(f"Feed sources processed: {result.sources_processed}")
        logger.info(f"Feed entries fetched: {result.entries_fetched}")
        logger.info(f"Feed entries stored: {result.entries_stored}")
        logger.info(f"Newsletter sources processed: {result.newsletter_sources_processed}")
        logger.info(f"Newsletter entries fetched: {result.newsletter_entries_fetched}")
        logger.info(f"Newsletter entries stored: {result.newsletter_entries_stored}")
        logger.info(f"Total entries stored: {result.entries_stored + result.newsletter_entries_stored}")
        logger.info(f"Errors: {len(result.errors)}")

        if result.errors:
            logger.warning("Errors encountered:")
            for error in result.errors[:10]:  # Show first 10
                logger.warning(f"  - {error}")

        return result

    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        raise


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Daily aggregation runner for high-signal news"
    )
    parser.add_argument(
        "--db", type=Path, default=DEFAULT_DB_PATH,
        help="Path to feed database"
    )
    parser.add_argument(
        "--newsletter-db", type=Path, default=DEFAULT_NEWSLETTER_DB_PATH,
        help="Path to newsletter database"
    )
    parser.add_argument(
        "--catalog", type=Path, default=DEFAULT_CATALOG_PATH,
        help="Path to feed sources catalog"
    )
    parser.add_argument(
        "--newsletter-catalog", type=Path, default=DEFAULT_NEWSLETTER_CATALOG_PATH,
        help="Path to newsletter sources catalog"
    )
    parser.add_argument(
        "--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR,
        help="Directory for output files"
    )
    parser.add_argument(
        "--log-dir", type=Path, default=DEFAULT_LOG_DIR,
        help="Directory for log files"
    )
    parser.add_argument(
        "--domain", type=str, default=None,
        help="Filter by domain (e.g., 'ai', 'software_development')"
    )
    parser.add_argument(
        "--limit-feeds", type=int, default=None,
        help="Maximum number of feed sources to process"
    )
    parser.add_argument(
        "--limit-newsletters", type=int, default=None,
        help="Maximum number of newsletter sources to process"
    )
    parser.add_argument(
        "--no-extract", action="store_true",
        help="Skip full content extraction"
    )

    args = parser.parse_args()

    result = run_daily_aggregation(
        db_path=args.db,
        newsletter_db_path=args.newsletter_db,
        catalog_path=args.catalog,
        newsletter_catalog_path=args.newsletter_catalog,
        output_dir=args.output_dir,
        log_dir=args.log_dir,
        domain=args.domain,
        limit_feeds=args.limit_feeds,
        limit_newsletters=args.limit_newsletters,
        extract_content=not args.no_extract,
    )

    # Exit with error only for pipeline-level failures, not per-source errors
    # Per-source errors (429 rate limits, missing scraper modules) are non-fatal
    fatal_error = False
    if result.errors:
        # Check if any error indicates a pipeline-level failure
        for err in result.errors:
            err_lower = err.lower()
            if any(fatal in err_lower for fatal in ['database', 'disk full', 'permission denied', 'pipeline', 'uncaught exception', 'zero entries']):
                fatal_error = True
                break
        if not fatal_error:
            print(f"WARNING: Non-fatal source errors ({len(result.errors)}), treating as success for systemd", file=sys.stderr)
    sys.exit(1 if fatal_error else 0)


if __name__ == "__main__":
    main()
