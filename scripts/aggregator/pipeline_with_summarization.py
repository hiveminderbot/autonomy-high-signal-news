#!/usr/bin/env python3
"""
Extended Aggregation Pipeline with Summarization

Integrates Phase 3 summarization modules into the aggregation pipeline:
- Story clustering after deduplication
- Entity extraction during content processing
- Relevance scoring for briefing prioritization
- Summary generation for clustered stories
"""

import json
import sys
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

# Import base pipeline components
from aggregator.pipeline import AggregationPipeline, PipelineResult, run_pipeline_command
from aggregator.feed_fetcher import FeedCache, FeedFetcher, FeedSource, FeedEntry
from aggregator.content_extractor import ContentExtractor
from aggregator.deduplicator import Deduplicator

# Import summarization modules
sys.path.insert(0, str(Path(__file__).parent.parent))
from summarizer.story_clusterer import StoryClusterer, ClusterResult
from summarizer.entity_extractor import EntityExtractor
from summarizer.content_summarizer import ContentSummarizer
from summarizer.relevance_scorer import RelevanceScorer, RelevanceScore


@dataclass
class SummarizationResult:
    """Result of summarization processing."""
    stories_clustered: int
    clusters_formed: int
    entities_extracted: int
    stories_scored: int
    summaries_generated: int


class AggregationPipelineWithSummarization(AggregationPipeline):
    """
    Extended pipeline that adds summarization capabilities:
    - Story clustering after deduplication
    - Entity extraction from content
    - Relevance scoring for prioritization
    - Summary generation for output
    """
    
    def __init__(
        self,
        cache: FeedCache,
        fetcher: Optional[FeedFetcher] = None,
        extractor: Optional[ContentExtractor] = None,
        deduplicator: Optional[Deduplicator] = None,
        blog_catalog_path: Optional[Path] = None,
        extract_content: bool = True,
        dedup_threshold: float = 0.85,
        enable_blog_scraping: bool = True,
        enable_newsletter_ingestion: bool = False,
        newsletter_catalog_path: Optional[Path] = None,
        # Summarization options
        enable_clustering: bool = True,
        enable_entity_extraction: bool = True,
        enable_relevance_scoring: bool = True,
        enable_summarization: bool = True,
        cluster_similarity_threshold: float = 0.35,
        min_cluster_size: int = 2,
    ):
        super().__init__(
            cache=cache,
            fetcher=fetcher,
            extractor=extractor,
            deduplicator=deduplicator,
            blog_catalog_path=blog_catalog_path,
            extract_content=extract_content,
            dedup_threshold=dedup_threshold,
            enable_blog_scraping=enable_blog_scraping,
            enable_newsletter_ingestion=enable_newsletter_ingestion,
            newsletter_catalog_path=newsletter_catalog_path,
        )
        
        # Initialize summarization components
        self.enable_clustering = enable_clustering
        self.enable_entity_extraction = enable_entity_extraction
        self.enable_relevance_scoring = enable_relevance_scoring
        self.enable_summarization = enable_summarization
        
        self.clusterer = StoryClusterer(
            similarity_threshold=cluster_similarity_threshold,
            min_cluster_size=min_cluster_size
        ) if enable_clustering else None
        
        self.entity_extractor = EntityExtractor() if enable_entity_extraction else None
        self.relevance_scorer = RelevanceScorer() if enable_relevance_scoring else None
        self.summarizer = ContentSummarizer() if enable_summarization else None
        
        self.summarization_stats = SummarizationResult(
            stories_clustered=0,
            clusters_formed=0,
            entities_extracted=0,
            stories_scored=0,
            summaries_generated=0
        )
    
    def run(
        self,
        sources: Optional[list[FeedSource]] = None,
        domain_filter: Optional[str] = None,
        limit_sources: Optional[int] = None,
        verbose: bool = False,
        include_disabled: bool = False,
    ) -> PipelineResult:
        """
        Run the pipeline with summarization.
        
        Steps:
        1. Run base aggregation pipeline
        2. Apply story clustering to stored entries
        3. Extract entities from content
        4. Score relevance for briefing prioritization
        5. Generate summaries for top stories
        """
        # Step 1: Run base pipeline
        result = super().run(
            sources=sources,
            domain_filter=domain_filter,
            limit_sources=limit_sources,
            verbose=verbose,
            include_disabled=include_disabled,
        )
        
        if result.entries_stored == 0:
            if verbose:
                print("\nNo entries to process for summarization.")
            return result
        
        # Step 2-5: Apply summarization to newly stored entries
        if verbose:
            print(f"\n{'='*50}")
            print("Phase 3: Summarization Processing")
            print(f"{'='*50}")
        
        # Get recent entries that need summarization
        recent_entries = self._get_recent_entries(limit=1000)
        
        if not recent_entries:
            if verbose:
                print("No recent entries found for summarization.")
            return result
        
        if verbose:
            print(f"Processing {len(recent_entries)} entries for summarization...")
        
        # Step 2: Story Clustering
        if self.enable_clustering and self.clusterer:
            self._apply_clustering(recent_entries, verbose)
        
        # Step 3: Entity Extraction
        if self.enable_entity_extraction and self.entity_extractor:
            self._apply_entity_extraction(recent_entries, verbose)
        
        # Step 4: Relevance Scoring
        if self.enable_relevance_scoring and self.relevance_scorer:
            self._apply_relevance_scoring(recent_entries, verbose)
        
        # Step 5: Summary Generation
        if self.enable_summarization and self.summarizer:
            self._apply_summarization(recent_entries, verbose)
        
        if verbose:
            print(f"\n{'='*50}")
            print("Summarization Complete")
            print(f"{'='*50}")
            print(f"Stories clustered: {self.summarization_stats.stories_clustered}")
            print(f"Clusters formed: {self.summarization_stats.clusters_formed}")
            print(f"Entities extracted: {self.summarization_stats.entities_extracted}")
            print(f"Stories scored: {self.summarization_stats.stories_scored}")
            print(f"Summaries generated: {self.summarization_stats.summaries_generated}")
        
        return result
    
    def _get_recent_entries(self, limit: int = 1000) -> list[FeedEntry]:
        """Get recent entries from the cache that need summarization."""
        import sqlite3
        
        entries = []
        with sqlite3.connect(self.cache.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT * FROM feed_entries 
                WHERE fetched_at > datetime('now', '-24 hours')
                ORDER BY published_at DESC
                LIMIT ?
            """, (limit,)).fetchall()
            
            for row in rows:
                entry = FeedEntry(
                    id=row['id'],
                    title=row['title'],
                    url=row['url'],
                    source_id=row['source_id'],
                    published_at=datetime.fromisoformat(row['published_at']) if row['published_at'] else None,
                    summary=row['summary'],
                    author=row['author'],
                    content=row['content'],
                    fetched_at=datetime.fromisoformat(row['fetched_at']),
                    cluster_id=row['cluster_id'],
                    relevance_score=row['relevance_score'],
                    relevance_tier=row['relevance_tier'],
                    entities=row['entities'],
                    generated_summary=row['generated_summary'],
                )
                entries.append(entry)
        
        return entries
    
    def _apply_clustering(self, entries: list[FeedEntry], verbose: bool):
        """Apply story clustering to entries."""
        if verbose:
            print("\n  → Clustering stories...")
        
        # Convert entries to story format for clusterer
        stories = []
        for entry in entries:
            story = {
                'id': entry.id,
                'title': entry.title,
                'content': entry.content or entry.summary or '',
                'url': entry.url,
                'source': entry.source_id,
                'domain': '',
                'published_at': entry.published_at.isoformat() if entry.published_at else None,
            }
            stories.append(story)
        
        # Run clustering
        cluster_result = self.clusterer.cluster_stories(stories)
        
        # Update entries with cluster IDs
        cluster_map = {}
        for cluster in cluster_result.clusters:
            for story in cluster.stories:
                cluster_map[story.get('id')] = cluster.id
        
        updated_entries = []
        for entry in entries:
            if entry.id in cluster_map:
                entry.cluster_id = cluster_map[entry.id]
                updated_entries.append(entry)
        
        # Save updated entries
        if updated_entries:
            self.cache.save_entries(updated_entries)
        
        self.summarization_stats.stories_clustered = len(updated_entries)
        self.summarization_stats.clusters_formed = len(cluster_result.clusters)
        
        if verbose:
            print(f"    ✓ Clustered {len(updated_entries)} stories into {len(cluster_result.clusters)} clusters")
    
    def _apply_entity_extraction(self, entries: list[FeedEntry], verbose: bool):
        """Extract entities from entry content."""
        if verbose:
            print("\n  → Extracting entities...")
        
        updated_entries = []
        total_entities = 0
        
        for entry in entries:
            if entry.entities:  # Skip if already has entities
                continue
            
            content = entry.content or entry.summary or ''
            if not content:
                continue
            
            entities = self.entity_extractor.extract_entities(
                title=entry.title,
                content=content,
                source=entry.source_id
            )
            
            if entities:
                # Store as JSON
                entry.entities = json.dumps([
                    {
                        'name': e.name,
                        'type': e.entity_type,
                        'confidence': e.confidence,
                        'mentions': e.mention_count
                    }
                    for e in entities
                ])
                updated_entries.append(entry)
                total_entities += len(entities)
        
        # Save updated entries
        if updated_entries:
            self.cache.save_entries(updated_entries)
        
        self.summarization_stats.entities_extracted = total_entities
        
        if verbose:
            print(f"    ✓ Extracted {total_entities} entities from {len(updated_entries)} stories")
    
    def _apply_relevance_scoring(self, entries: list[FeedEntry], verbose: bool):
        """Apply relevance scoring to entries."""
        if verbose:
            print("\n  → Scoring relevance...")
        
        updated_entries = []
        
        for entry in entries:
            if entry.relevance_score is not None:  # Skip if already scored
                continue
            
            content = entry.content or entry.summary or ''
            
            story = {
                'id': entry.id,
                'title': entry.title,
                'content': content,
                'url': entry.url,
                'source': entry.source_id,
                'published_at': entry.published_at.isoformat() if entry.published_at else None,
            }
            
            score = self.relevance_scorer.score_story(story)
            
            entry.relevance_score = score.overall_score
            entry.relevance_tier = score.ranking_tier
            updated_entries.append(entry)
        
        # Save updated entries
        if updated_entries:
            self.cache.save_entries(updated_entries)
        
        self.summarization_stats.stories_scored = len(updated_entries)
        
        if verbose:
            tier_counts = {}
            for entry in updated_entries:
                tier = entry.relevance_tier or 'unknown'
                tier_counts[tier] = tier_counts.get(tier, 0) + 1
            print(f"    ✓ Scored {len(updated_entries)} stories")
            for tier, count in sorted(tier_counts.items()):
                print(f"      - {tier}: {count}")
    
    def _apply_summarization(self, entries: list[FeedEntry], verbose: bool):
        """Generate summaries for entries."""
        if verbose:
            print("\n  → Generating summaries...")
        
        updated_entries = []
        
        for entry in entries:
            if entry.generated_summary:  # Skip if already has summary
                continue
            
            content = entry.content or entry.summary or ''
            if len(content) < 200:  # Skip short content
                continue
            
            summary_result = self.summarizer.summarize(
                content=content,
                title=entry.title
            )
            
            if summary_result.summary:
                entry.generated_summary = summary_result.summary
                updated_entries.append(entry)
        
        # Save updated entries
        if updated_entries:
            self.cache.save_entries(updated_entries)
        
        self.summarization_stats.summaries_generated = len(updated_entries)
        
        if verbose:
            print(f"    ✓ Generated {len(updated_entries)} summaries")
    
    def get_summarization_stats(self) -> dict:
        """Get summarization statistics."""
        return asdict(self.summarization_stats)


def run_pipeline_with_summarization(
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
    # Summarization options
    enable_clustering: bool = True,
    enable_entity_extraction: bool = True,
    enable_relevance_scoring: bool = True,
    enable_summarization: bool = True,
) -> PipelineResult:
    """
    Command-line interface to run the pipeline with summarization.
    """
    # Initialize components
    cache = FeedCache(db_path)
    
    # Load RSS sources from catalog into cache
    if catalog_path.exists():
        from aggregator.feed_fetcher import load_sources_from_catalog
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
    
    # Create and run pipeline with summarization
    pipeline = AggregationPipelineWithSummarization(
        cache=cache,
        extract_content=extract,
        blog_catalog_path=blog_catalog_path,
        enable_blog_scraping=enable_blog_scraping,
        enable_newsletter_ingestion=enable_newsletter_ingestion,
        newsletter_catalog_path=newsletter_catalog_path,
        enable_clustering=enable_clustering,
        enable_entity_extraction=enable_entity_extraction,
        enable_relevance_scoring=enable_relevance_scoring,
        enable_summarization=enable_summarization,
    )
    
    result = pipeline.run(
        domain_filter=domain,
        limit_sources=limit,
        verbose=verbose,
        include_disabled=retry_disabled,
    )
    
    return result


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(
        description='High-Signal News Aggregation Pipeline with Summarization'
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
        '--retry-disabled',
        action='store_true',
        help='Retry disabled sources and re-enable if successful'
    )
    # Summarization flags
    parser.add_argument(
        '--no-clustering',
        action='store_true',
        help='Skip story clustering'
    )
    parser.add_argument(
        '--no-entity-extraction',
        action='store_true',
        help='Skip entity extraction'
    )
    parser.add_argument(
        '--no-relevance-scoring',
        action='store_true',
        help='Skip relevance scoring'
    )
    parser.add_argument(
        '--no-summarization',
        action='store_true',
        help='Skip summary generation'
    )
    
    args = parser.parse_args()
    
    # Ensure data directory exists
    args.db.parent.mkdir(parents=True, exist_ok=True)
    
    result = run_pipeline_with_summarization(
        catalog_path=args.catalog,
        db_path=args.db,
        domain=args.domain,
        limit=args.limit,
        extract=not args.no_extract,
        verbose=args.verbose,
        blog_catalog_path=args.blog_catalog,
        enable_blog_scraping=not args.no_blog_scraping,
        retry_disabled=args.retry_disabled,
        enable_clustering=not args.no_clustering,
        enable_entity_extraction=not args.no_entity_extraction,
        enable_relevance_scoring=not args.no_relevance_scoring,
        enable_summarization=not args.no_summarization,
    )
    
    if args.json:
        import json
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(f"\n{'='*50}")
        print(f"Pipeline Complete (with Summarization)")
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
