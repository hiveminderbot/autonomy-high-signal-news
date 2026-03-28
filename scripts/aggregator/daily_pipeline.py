#!/usr/bin/env python3
"""
Daily Pipeline Runner - High-Signal News Aggregation

Unified command-line interface for running the complete aggregation pipeline.
Ties together all aggregator components: fetch, extract, dedupe, store, deliver.

Usage:
    python daily_pipeline.py                    # Run full pipeline
    python daily_pipeline.py --dry-run          # Simulate without changes
    python daily_pipeline.py -v                 # Verbose output
    python daily_pipeline.py --no-extract       # Skip content extraction
    python daily_pipeline.py --domain ai        # Filter to AI domain only

Environment:
    HN_BRIEFING_BOT_TOKEN    Telegram bot token for delivery
    HN_BRIEFING_CHAT_ID      Telegram chat ID for delivery
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add parent scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from .pipeline import AggregationPipeline, PipelineResult
from .feed_fetcher import FeedCache, load_sources_from_catalog
from .deduplicator import Deduplicator
from .storage import ArticleStorage


# Default paths
DEFAULT_DB_PATH = Path("data/news.db")
DEFAULT_CATALOG_PATH = Path("sources/sources-ai.json")
DEFAULT_OUTPUT_DIR = Path("output")
DEFAULT_LOG_DIR = Path("logs")


def setup_logging(verbose: bool = False, log_dir: Optional[Path] = None) -> logging.Logger:
    """Configure logging for the pipeline run."""
    logger = logging.getLogger("daily_pipeline")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    
    # Clear existing handlers
    logger.handlers = []
    
    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.DEBUG if verbose else logging.INFO)
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    ch.setFormatter(formatter)
    logger.addHandler(ch)
    
    # File handler if log_dir specified
    if log_dir:
        log_dir.mkdir(parents=True, exist_ok=True)
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = log_dir / f"pipeline_{run_id}.log"
        fh = logging.FileHandler(log_file)
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    
    return logger


def run_pipeline(
    db_path: Path,
    catalog_path: Path,
    output_dir: Path,
    extract_content: bool = True,
    dedup_threshold: float = 0.85,
    domain_filter: Optional[str] = None,
    dry_run: bool = False,
    verbose: bool = False,
) -> dict:
    """
    Run the complete aggregation pipeline.
    
    Args:
        db_path: Path to SQLite database
        catalog_path: Path to sources catalog JSON
        output_dir: Directory for output files
        extract_content: Whether to extract full article content
        dedup_threshold: Similarity threshold for deduplication (0-1)
        domain_filter: Filter to specific domain (e.g., 'ai', 'dev')
        dry_run: If True, don't write to database
        verbose: Enable verbose logging
        
    Returns:
        Dictionary with pipeline results
    """
    logger = setup_logging(verbose, output_dir / "logs" if not dry_run else None)
    
    start_time = datetime.now()
    logger.info(f"Starting daily pipeline at {start_time.isoformat()}")
    logger.info(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    
    try:
        # Initialize components
        logger.info("Initializing pipeline components...")
        
        # Ensure db_path is a Path object
        if isinstance(db_path, str):
            db_path = Path(db_path)
        
        if dry_run:
            # Create temp files for dry run that will be cleaned up
            import tempfile
            temp_dir = Path(tempfile.mkdtemp())
            cache_db = temp_dir / "cache.db"
            storage_db = temp_dir / "storage.db"
            cache = FeedCache(db_path=cache_db)
            storage = ArticleStorage(db_path=storage_db)
        else:
            cache = FeedCache(db_path=db_path)
            storage = ArticleStorage(db_path=db_path)
        
        pipeline = AggregationPipeline(
            cache=cache,
            deduplicator=Deduplicator(simhash_threshold=dedup_threshold),
            extract_content=extract_content,
        )
        
        # Load sources
        if not catalog_path.exists():
            logger.error(f"Catalog not found: {catalog_path}")
            return {"success": False, "error": f"Catalog not found: {catalog_path}"}
            
        sources = load_sources_from_catalog(str(catalog_path))
        logger.info(f"Loaded {len(sources)} sources from {catalog_path}")
        
        # Run pipeline
        logger.info("Running aggregation pipeline...")
        result: PipelineResult = pipeline.run(
            sources=sources,
            domain_filter=domain_filter,
        )
        
        duration = (datetime.now() - start_time).total_seconds()
        
        # Build result summary
        summary = {
            "success": len(result.errors) == 0,
            "started_at": result.started_at.isoformat(),
            "completed_at": result.completed_at.isoformat(),
            "duration_seconds": duration,
            "sources_processed": result.sources_processed,
            "entries_fetched": result.entries_fetched,
            "entries_extracted": result.entries_extracted,
            "entries_deduplicated": result.entries_deduplicated,
            "entries_stored": result.entries_stored,
            "error_count": len(result.errors),
            "errors": result.errors[:10],  # Limit errors in summary
            "dry_run": dry_run,
        }
        
        logger.info(f"Pipeline completed in {duration:.2f}s")
        logger.info(f"Fetched: {result.entries_fetched}, Stored: {result.entries_stored}")
        
        if result.errors:
            logger.warning(f"Pipeline completed with {len(result.errors)} errors")
            for error in result.errors[:5]:
                logger.warning(f"  - {error}")
        
        return summary
        
    except Exception as e:
        logger.exception("Pipeline failed with exception")
        return {
            "success": False,
            "error": str(e),
            "started_at": start_time.isoformat(),
            "completed_at": datetime.now().isoformat(),
            "duration_seconds": (datetime.now() - start_time).total_seconds(),
        }


def main():
    parser = argparse.ArgumentParser(
        description="High-Signal News Daily Aggregation Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                          # Run full pipeline
  %(prog)s --dry-run                # Simulate without database writes
  %(prog)s -v --domain ai           # Verbose, AI domain only
  %(prog)s --no-extract             # Skip content extraction (faster)
  %(prog)s --json                   # Output results as JSON
        """
    )
    
    parser.add_argument(
        "--db", "--database",
        type=Path,
        default=DEFAULT_DB_PATH,
        help=f"Path to SQLite database (default: {DEFAULT_DB_PATH})"
    )
    parser.add_argument(
        "--catalog",
        type=Path,
        default=DEFAULT_CATALOG_PATH,
        help=f"Path to sources catalog (default: {DEFAULT_CATALOG_PATH})"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help=f"Output directory (default: {DEFAULT_OUTPUT_DIR})"
    )
    parser.add_argument(
        "--domain",
        type=str,
        default=None,
        help="Filter to specific domain (e.g., 'ai', 'dev', 'investment')"
    )
    parser.add_argument(
        "--no-extract",
        action="store_true",
        help="Skip content extraction (faster, less data)"
    )
    parser.add_argument(
        "--dedup-threshold",
        type=float,
        default=0.85,
        help="Deduplication similarity threshold 0-1 (default: 0.85)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate pipeline without writing to database"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose output"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON"
    )
    
    args = parser.parse_args()
    
    # Run pipeline
    result = run_pipeline(
        db_path=args.db,
        catalog_path=args.catalog,
        output_dir=args.output_dir,
        extract_content=not args.no_extract,
        dedup_threshold=args.dedup_threshold,
        domain_filter=args.domain,
        dry_run=args.dry_run,
        verbose=args.verbose,
    )
    
    # Output results
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"\n{'='*60}")
        print(f"Pipeline {'SUCCEEDED' if result['success'] else 'FAILED'}")
        print(f"{'='*60}")
        print(f"Duration: {result.get('duration_seconds', 0):.2f}s")
        print(f"Sources processed: {result.get('sources_processed', 0)}")
        print(f"Entries fetched: {result.get('entries_fetched', 0)}")
        print(f"Entries extracted: {result.get('entries_extracted', 0)}")
        print(f"Entries deduplicated: {result.get('entries_deduplicated', 0)}")
        print(f"Entries stored: {result.get('entries_stored', 0)}")
        print(f"Errors: {result.get('error_count', 0)}")
        if result.get('dry_run'):
            print("\n[DRY RUN - No changes written]")
    
    # Exit with appropriate code
    sys.exit(0 if result['success'] else 1)


if __name__ == "__main__":
    main()
