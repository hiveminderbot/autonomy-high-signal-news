#!/usr/bin/env python3
"""
Daily runner for the High-Signal News aggregation pipeline.

This script is designed to be run via cron (e.g., every 6 hours).
It executes the full aggregation pipeline and reports status.

Cron setup:
    0 */6 * * * cd /home/exedev/autonomy/labs/high-signal-news && ./scripts/daily_runner.py >> logs/daily_runner.log 2>&1
"""

import sys
import json
import logging
import subprocess
from datetime import datetime
from pathlib import Path

# Setup logging
LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

log_file = LOG_DIR / f"daily_runner_{datetime.now().strftime('%Y%m%d')}.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


def run_pipeline(retry_disabled: bool = False) -> dict:
    """Run the full aggregation pipeline."""
    logger.info("=" * 60)
    logger.info("Starting daily aggregation pipeline")
    if retry_disabled:
        logger.info("Mode: Retry disabled sources")
    logger.info("=" * 60)
    
    start_time = datetime.now()
    
    # Build command
    cmd = [sys.executable, "-m", "scripts.aggregator.pipeline", "--full"]
    if retry_disabled:
        cmd.append("--retry-disabled")
    
    # Run the pipeline
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent
    )
    
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    # Parse results from output
    output = result.stdout + result.stderr
    
    # Check for success indicators
    success = result.returncode == 0 and "error" not in output.lower()
    
    # Extract entry counts if available
    entries_fetched = 0
    entries_stored = 0
    for line in output.split('\n'):
        if 'entries fetched' in line.lower():
            try:
                entries_fetched = int(''.join(filter(str.isdigit, line)))
            except:
                pass
        if 'entries stored' in line.lower() or 'stored in database' in line.lower():
            try:
                entries_stored = int(''.join(filter(str.isdigit, line)))
            except:
                pass
    
    status = {
        "timestamp": start_time.isoformat(),
        "duration_seconds": duration,
        "success": success,
        "return_code": result.returncode,
        "entries_fetched": entries_fetched,
        "entries_stored": entries_stored,
        "log_file": str(log_file)
    }
    
    logger.info(f"Pipeline completed in {duration:.1f}s")
    logger.info(f"Success: {success}, Entries: {entries_fetched} fetched, {entries_stored} stored")
    
    return status


def check_source_health() -> dict:
    """Check the health of feed sources."""
    logger.info("Checking source health...")
    
    try:
        from scripts.aggregator.storage import AggregatorStorage
        
        storage = AggregatorStorage()
        stats = storage.get_stats()
        
        # Get sources with high error rates
        error_threshold = 3
        unhealthy_sources = []
        
        # Query for sources with consecutive errors
        import sqlite3
        conn = sqlite3.connect(storage.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT source_id, COUNT(*) as error_count, MAX(fetched_at)
            FROM fetch_log
            WHERE success = 0 AND fetched_at > datetime('now', '-7 days')
            GROUP BY source_id
            HAVING error_count >= ?
            ORDER BY error_count DESC
        """, (error_threshold,))
        
        for row in cursor.fetchall():
            unhealthy_sources.append({
                "source_id": row[0],
                "error_count": row[1],
                "last_error": row[2]
            })
        
        conn.close()
        
        health_status = {
            "total_entries": stats.get("total_entries", 0),
            "sources_with_errors": len(unhealthy_sources),
            "unhealthy_sources": unhealthy_sources
        }
        
        logger.info(f"Total entries in database: {health_status['total_entries']}")
        logger.info(f"Unhealthy sources: {len(unhealthy_sources)}")
        for src in unhealthy_sources:
            logger.warning(f"  - {src['source_id']}: {src['error_count']} errors")
        
        return health_status
        
    except Exception as e:
        logger.error(f"Failed to check source health: {e}")
        return {"error": str(e)}


def save_run_history(status: dict, health: dict):
    """Save run history to JSON file."""
    history_file = Path(__file__).parent.parent / "data" / "run_history.json"
    history_file.parent.mkdir(exist_ok=True)
    
    history = []
    if history_file.exists():
        try:
            with open(history_file) as f:
                history = json.load(f)
        except:
            pass
    
    history.append({
        "timestamp": status["timestamp"],
        "success": status["success"],
        "duration_seconds": status["duration_seconds"],
        "entries_fetched": status["entries_fetched"],
        "entries_stored": status["entries_stored"],
        "sources_with_errors": health.get("sources_with_errors", 0)
    })
    
    # Keep only last 30 runs
    history = history[-30:]
    
    with open(history_file, 'w') as f:
        json.dump(history, f, indent=2)
    
    logger.info(f"Run history saved to {history_file}")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Daily runner for High-Signal News aggregation')
    parser.add_argument('--retry-disabled', action='store_true',
                        help='Retry disabled sources and re-enable if successful')
    args = parser.parse_args()
    
    try:
        # Run pipeline
        status = run_pipeline(retry_disabled=args.retry_disabled)
        
        # Check health
        health = check_source_health()
        
        # Save history
        save_run_history(status, health)
        
        # Exit with appropriate code
        if status["success"]:
            logger.info("Daily run completed successfully")
            return 0
        else:
            logger.error("Daily run failed")
            return 1
            
    except Exception as e:
        logger.exception("Unexpected error in daily runner")
        return 1


if __name__ == "__main__":
    sys.exit(main())
