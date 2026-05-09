#!/usr/bin/env python3
"""
Daily Briefing Scheduler - Phase 4

Cron-compatible script for generating and delivering daily briefings.
Orchestrates the full pipeline: aggregation → summarization → briefing → delivery

Cron setup (run at 7:00 AM daily):
    0 7 * * * cd /home/exedev/autonomy/labs/high-signal-news && ./scripts/run-daily.sh >> logs/scheduler.log 2>&1

Or use the generic Nix-backed wrapper directly:
    ./scripts/run-with-nix-python.sh -m scripts.scheduler.daily_briefing

Or use the provided shell wrapper:
    ./scripts/run-daily.sh
"""

import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from briefing import (
    BriefingGenerator,
    BriefingFormat,
    MarkdownRenderer,
    MultiChannelDelivery,
    DeliveryResult
)

logger = logging.getLogger(__name__)


class DailyBriefingScheduler:
    """
    Scheduler for daily briefing generation and delivery.

    Orchestrates the full pipeline:
    1. Run aggregation pipeline (if needed)
    2. Generate briefing from latest content
    3. Render in configured format(s)
    4. Deliver via configured channels
    5. Log results and handle errors
    """

    def __init__(
        self,
        output_dir: Optional[Path] = None,
        config_path: Optional[Path] = None,
        skip_aggregation: bool = False,
        force_regenerate: bool = False
    ):
        self.output_dir = output_dir or Path('./output')
        self.config_path = config_path or Path('./config/delivery.json')
        self.skip_aggregation = skip_aggregation
        self.force_regenerate = force_regenerate

        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Initialize components
        self.generator = BriefingGenerator()
        self.renderer = MarkdownRenderer()
        self.delivery = MultiChannelDelivery()

        # Track execution
        self.run_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        self.results: dict = {}

    def setup_logging(self, log_dir: Optional[Path] = None) -> Path:
        """Setup logging for this run."""
        log_dir = log_dir or Path('./logs')
        log_dir.mkdir(parents=True, exist_ok=True)

        log_file = log_dir / f"daily_briefing_{self.run_id}.log"

        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler(sys.stdout)
            ]
        )

        return log_file

    def run_aggregation(self) -> dict:
        """Run the content aggregation pipeline."""
        logger.info("=" * 60)
        logger.info("Step 1/4: Running aggregation pipeline")
        logger.info("=" * 60)

        try:
            from aggregator.daily_pipeline import run_pipeline

            pipeline_result = run_pipeline(
                db_path=Path('./data/news.db'),
                catalog_path=Path('./sources/sources-ai.json'),
                output_dir=Path('./output'),
                extract_content=True,
                verbose=True
            )

            total_stored = pipeline_result.get('total_stored', 0)
            logger.info(f"Pipeline completed: {total_stored} entries stored")
            return {
                'success': True,
                'entries_stored': total_stored,
                'duration_seconds': pipeline_result.get('duration_seconds', 0)
            }

        except Exception as e:
            logger.exception("Aggregation pipeline failed")
            return {
                'success': False,
                'error': str(e)
            }

    def load_stories(self) -> list[dict]:
        """Load stories from the aggregation pipeline output."""
        logger.info("Loading stories from pipeline output...")

        # Try multiple sources in order of preference
        sources = [
            Path('./data/latest_stories.json'),
            Path('./data/scored_stories.json'),
            Path('./data/processed_stories.json'),
        ]

        for source in sources:
            if source.exists():
                try:
                    with open(source) as f:
                        stories = json.load(f)

                    if isinstance(stories, list):
                        logger.info(f"Loaded {len(stories)} stories from {source}")
                        return stories
                    elif isinstance(stories, dict) and 'stories' in stories:
                        logger.info(f"Loaded {len(stories['stories'])} stories from {source}")
                        return stories['stories']

                except Exception as e:
                    logger.warning(f"Failed to load from {source}: {e}")

        # Fallback 1: query ArticleStorage (articles table)
        try:
            from aggregator.storage import ArticleStorage

            storage = ArticleStorage(Path('./data/news.db'))
            articles = storage.get_recent_articles(hours=24, limit=100)
            stories = [a.__dict__ if hasattr(a, '__dict__') else a for a in articles]

            if stories:
                logger.info(f"Loaded {len(stories)} stories from ArticleStorage")
                return stories

        except Exception as e:
            logger.warning(f"Failed to load from ArticleStorage: {e}")

        # Fallback 2: query FeedCache (feed_entries table) — data is stored here by the pipeline
        try:
            from aggregator.feed_fetcher import FeedCache

            cache = FeedCache(Path('./data/news.db'))
            entries = cache.get_recent_entries(hours=24, limit=100)
            stories = []
            for entry in entries:
                story = {
                    'id': entry.id,
                    'title': entry.title,
                    'url': entry.url,
                    'source_id': entry.source_id,
                    'published_at': entry.published_at.isoformat() if entry.published_at else None,
                    'summary': entry.summary,
                    'author': entry.author,
                    'content': entry.content,
                    'fetched_at': entry.fetched_at.isoformat() if entry.fetched_at else None,
                }
                stories.append(story)

            if stories:
                logger.info(f"Loaded {len(stories)} stories from FeedCache")
                return stories

        except Exception as e:
            logger.warning(f"Failed to load from FeedCache: {e}")

        logger.error("No stories available from any source")
        return []

    def generate_briefing(self, stories: list[dict]) -> Optional[dict]:
        """Generate briefing from stories."""
        logger.info("=" * 60)
        logger.info("Step 2/4: Generating briefing")
        logger.info("=" * 60)

        if not stories:
            logger.error("No stories available for briefing generation")
            return None

        try:
            briefing = self.generator.generate(stories)

            logger.info(f"Briefing generated:")
            logger.info(f"  - Total stories: {briefing.metadata.total_stories}")
            logger.info(f"  - Must read: {briefing.metadata.must_read_count}")
            logger.info(f"  - Important: {briefing.metadata.important_count}")
            logger.info(f"  - Contextual: {briefing.metadata.contextual_count}")
            logger.info(f"  - Reading time: {briefing.metadata.reading_time_minutes} min")

            return briefing.to_dict()

        except Exception as e:
            logger.exception("Briefing generation failed")
            return None

    def render_briefing(self, briefing: dict) -> str:
        """Render briefing to markdown format."""
        logger.info("=" * 60)
        logger.info("Step 3/4: Rendering briefing")
        logger.info("=" * 60)

        try:
            # Convert dict back to BriefingResult-like structure
            from briefing.generator import BriefingResult, BriefingMetadata, BriefingSection

            metadata = BriefingMetadata(**briefing['metadata'])
            sections = [BriefingSection(**s) for s in briefing['sections']]

            # Create a simple wrapper object
            class BriefingWrapper:
                def __init__(self, metadata, sections):
                    self.metadata = metadata
                    self.sections = sections

            briefing_obj = BriefingWrapper(metadata, sections)

            rendered = self.renderer.render(briefing_obj)
            logger.info(f"Rendered {len(rendered)} characters")

            return rendered

        except Exception as e:
            logger.exception("Briefing rendering failed")
            # Fallback: simple markdown rendering
            return self._fallback_render(briefing)

    def _fallback_render(self, briefing: dict) -> str:
        """Simple fallback renderer if main renderer fails."""
        lines = [
            f"# Daily Briefing - {datetime.now().strftime('%Y-%m-%d')}",
            "",
            f"_{briefing['metadata']['total_stories']} stories | "
            f"{briefing['metadata']['reading_time_minutes']} min read_",
            "",
            "---",
            ""
        ]

        for section in briefing['sections']:
            lines.append(f"## {section['emoji']} {section['name']}")
            lines.append("")

            for story in section['stories']:
                tier_emoji = {"must_read": "🔴", "important": "🟡", "contextual": "🔵"}.get(
                    story['tier'], "⚪"
                )
                lines.append(f"### {tier_emoji} {story['title']}")
                lines.append("")
                lines.append(story['summary'])
                lines.append("")
                if story.get('url'):
                    lines.append(f"[Read more]({story['url']})")
                    lines.append("")
                lines.append("---")
                lines.append("")

        return "\n".join(lines)

    def deliver_briefing(self, content: str, subject: str) -> list[dict]:
        """Deliver briefing via configured channels."""
        logger.info("=" * 60)
        logger.info("Step 4/4: Delivering briefing")
        logger.info("=" * 60)

        configured = self.delivery.get_configured_channels()
        logger.info(f"Configured channels: {configured}")

        if not configured:
            logger.warning("No delivery channels configured, saving to file only")
            # Ensure at least file delivery
            from briefing import FileDelivery
            self.delivery = MultiChannelDelivery([FileDelivery(output_dir=self.output_dir)])

        results = self.delivery.deliver(content, subject)

        for result in results:
            status = "✓" if result.success else "✗"
            logger.info(f"{status} {result.channel}: {result.message}")
            if result.error:
                logger.error(f"  Error: {result.error}")

        return [r.to_dict() for r in results]

    def save_run_report(self) -> Path:
        """Save a report of this run."""
        report = {
            'run_id': self.run_id,
            'start_time': self.start_time.isoformat() if self.start_time else None,
            'end_time': self.end_time.isoformat() if self.end_time else None,
            'duration_seconds': (
                (self.end_time - self.start_time).total_seconds()
                if self.start_time and self.end_time else 0
            ),
            'results': self.results
        }

        report_path = self.output_dir / f"run_report_{self.run_id}.json"

        with open(report_path, 'w') as f:
            json.dump(report, f, indent=2)

        # Also save as latest
        latest_path = self.output_dir / "latest_run_report.json"
        with open(latest_path, 'w') as f:
            json.dump(report, f, indent=2)

        return report_path

    def run(self) -> dict:
        """Run the complete daily briefing workflow."""
        self.start_time = datetime.now()

        logger.info("=" * 60)
        logger.info(f"Daily Briefing Run - {self.run_id}")
        logger.info("=" * 60)

        try:
            # Step 1: Aggregation (optional)
            if not self.skip_aggregation:
                agg_result = self.run_aggregation()
                self.results['aggregation'] = agg_result

                if not agg_result['success']:
                    logger.warning("Aggregation failed, attempting to use cached stories")
            else:
                logger.info("Skipping aggregation (as requested)")
                self.results['aggregation'] = {'success': True, 'skipped': True}

            # Step 2: Load stories and generate briefing
            stories = self.load_stories()

            if not stories:
                logger.error("No stories available. Cannot generate briefing.")
                self.results['briefing'] = {'success': False, 'error': 'No stories available'}
                self.end_time = datetime.now()
                self.save_run_report()
                return self.results

            briefing = self.generate_briefing(stories)

            if not briefing:
                logger.error("Briefing generation failed")
                self.results['briefing'] = {'success': False, 'error': 'Generation failed'}
                self.end_time = datetime.now()
                self.save_run_report()
                return self.results

            self.results['briefing'] = {
                'success': True,
                'metadata': briefing['metadata']
            }

            # Step 3: Render
            rendered = self.render_briefing(briefing)
            self.results['render'] = {'success': True, 'length': len(rendered)}

            # Step 4: Deliver
            subject = f"Daily Briefing - {datetime.now().strftime('%Y-%m-%d')}"
            delivery_results = self.deliver_briefing(rendered, subject)

            self.results['delivery'] = {
                'success': any(r['success'] for r in delivery_results),
                'channels': delivery_results
            }

            # Summary
            self.end_time = datetime.now()
            duration = (self.end_time - self.start_time).total_seconds()

            logger.info("=" * 60)
            logger.info("Run Complete")
            logger.info("=" * 60)
            logger.info(f"Duration: {duration:.1f}s")
            logger.info(f"Briefing: {briefing['metadata']['total_stories']} stories, "
                       f"{briefing['metadata']['reading_time_minutes']} min read")
            logger.info(f"Delivery: {sum(1 for r in delivery_results if r['success'])}/"
                       f"{len(delivery_results)} channels succeeded")

        except Exception as e:
            logger.exception("Unexpected error in daily briefing run")
            self.results['error'] = str(e)
            self.end_time = datetime.now()

        # Save report
        report_path = self.save_run_report()
        logger.info(f"Run report saved to {report_path}")

        return self.results


def run_daily_briefing(
    skip_aggregation: bool = False,
    config_path: Optional[str] = None,
    output_dir: Optional[str] = None
) -> dict:
    """
    Convenience function to run the daily briefing.

    Args:
        skip_aggregation: Skip the aggregation pipeline (use cached stories)
        config_path: Path to delivery configuration file
        output_dir: Directory for output files

    Returns:
        Dict with run results
    """
    scheduler = DailyBriefingScheduler(
        output_dir=Path(output_dir) if output_dir else None,
        config_path=Path(config_path) if config_path else None,
        skip_aggregation=skip_aggregation
    )

    scheduler.setup_logging()
    return scheduler.run()


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Generate and deliver daily briefing',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Full run (aggregation + briefing + delivery)
    ./scripts/run-with-nix-python.sh -m scripts.scheduler.daily_briefing

    # Skip aggregation, use cached stories
    ./scripts/run-with-nix-python.sh -m scripts.scheduler.daily_briefing --skip-aggregation

    # Custom config and output
    ./scripts/run-with-nix-python.sh -m scripts.scheduler.daily_briefing \
        --config config/delivery.json \
        --output ./custom_output
        """
    )

    parser.add_argument('--skip-aggregation', action='store_true',
                        help='Skip aggregation pipeline, use cached stories')
    parser.add_argument('--config', type=str, default='./config/delivery.json',
                        help='Path to delivery configuration file')
    parser.add_argument('--output', type=str, default='./output',
                        help='Output directory for briefing files')
    parser.add_argument('--log-dir', type=str, default='./logs',
                        help='Directory for log files')

    args = parser.parse_args()

    # Run
    scheduler = DailyBriefingScheduler(
        output_dir=Path(args.output),
        config_path=Path(args.config) if args.config else None,
        skip_aggregation=args.skip_aggregation
    )

    log_file = scheduler.setup_logging(Path(args.log_dir))
    print(f"Logging to: {log_file}", file=sys.stderr)

    results = scheduler.run()

    # Exit with appropriate code
    success = (
        results.get('briefing', {}).get('success', False) and
        results.get('delivery', {}).get('success', False)
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
