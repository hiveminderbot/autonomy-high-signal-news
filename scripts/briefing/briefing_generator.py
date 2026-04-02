#!/usr/bin/env python3
"""Morning briefing generator - assembles high-signal news into readable format."""

import json
import sqlite3
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "aggregator"))
sys.path.insert(0, str(Path(__file__).parent.parent / "summarizer"))


@dataclass
class BriefingStory:
    title: str
    url: str
    source: str
    domain: str  # ai, dev, investment
    summary: str
    relevance_score: float
    published_at: str
    priority: str = "📰"  # 🔥 breaking, ⭐ important, 📰 regular


class BriefingGenerator:
    """Generate morning briefings from aggregated news."""

    def __init__(self, db_path: str = "news.db", output_dir: str = "output"):
        self.db_path = db_path
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

    def fetch_recent_stories(self, hours: int = 24) -> List[BriefingStory]:
        """Fetch stories from last N hours, scored and prioritized."""
        cutoff = datetime.now() - timedelta(hours=hours)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT a.title, a.url, a.source, a.domain, s.summary, s.relevance_score, a.published_at
            FROM articles a
            JOIN summaries s ON a.id = s.article_id
            WHERE a.published_at > ?
            AND s.relevance_score > 0.5
            ORDER BY s.relevance_score DESC, a.published_at DESC
        """, (cutoff.isoformat(),))

        stories = []
        for row in cursor.fetchall():
            title, url, source, domain, summary, score, published = row

            # Determine priority
            if score > 0.9:
                priority = "🔥"
            elif score > 0.75:
                priority = "⭐"
            else:
                priority = "📰"

            stories.append(BriefingStory(
                title=title,
                url=url,
                source=source,
                domain=domain,
                summary=summary[:200] + "..." if len(summary) > 200 else summary,
                relevance_score=score,
                published_at=published,
                priority=priority
            ))

        conn.close()
        return stories

    def select_top_stories(self, stories: List[BriefingStory], max_per_domain: int = 5) -> List[BriefingStory]:
        """Select top stories with domain diversity."""
        selected = []
        domain_counts = {"ai": 0, "software_development": 0, "investment": 0}

        for story in stories:
            if domain_counts.get(story.domain, 0) < max_per_domain:
                selected.append(story)
                domain_counts[story.domain] = domain_counts.get(story.domain, 0) + 1

        return selected[:15]  # Max 15 total stories

    def generate_markdown(self, stories: List[BriefingStory]) -> str:
        """Generate markdown briefing."""
        today = datetime.now().strftime("%Y-%m-%d")

        lines = [
            f"# Morning Briefing - {today}",
            "",
            "*High-signal news for AI practitioners, software developers, and tech investors*",
            "",
            "---",
            "",
        ]

        # Group by domain
        by_domain = {"ai": [], "software_development": [], "investment": []}
        for story in stories:
            by_domain.get(story.domain, []).append(story)

        # AI Section
        if by_domain["ai"]:
            lines.extend([
                "## 🤖 Artificial Intelligence",
                "",
            ])
            for story in by_domain["ai"][:5]:
                lines.extend([
                    f"{story.priority} **{story.title}**",
                    f"   Source: {story.source} | [Read more]({story.url})",
                    f"   > {story.summary}",
                    "",
                ])

        # Dev Section
        if by_domain["software_development"]:
            lines.extend([
                "## 💻 Software Development",
                "",
            ])
            for story in by_domain["software_development"][:5]:
                lines.extend([
                    f"{story.priority} **{story.title}**",
                    f"   Source: {story.source} | [Read more]({story.url})",
                    f"   > {story.summary}",
                    "",
                ])

        # Investment Section
        if by_domain["investment"]:
            lines.extend([
                "## 💰 Investment & Markets",
                "",
            ])
            for story in by_domain["investment"][:5]:
                lines.extend([
                    f"{story.priority} **{story.title}**",
                    f"   Source: {story.source} | [Read more]({story.url})",
                    f"   > {story.summary}",
                    "",
                ])

        # Footer
        lines.extend([
            "---",
            "",
            f"*Generated: {datetime.now().strftime('%H:%M')} | {len(stories)} stories from {len(set(s.source for s in stories))} sources*",
            "",
            "**Priority indicators:** 🔥 Breaking / Very High Signal | ⭐ Important | 📰 Regular",
        ])

        return "\n".join(lines)

    def generate_telegram(self, stories: List[BriefingStory]) -> str:
        """Generate Telegram-formatted briefing (compact)."""
        today = datetime.now().strftime("%Y-%m-%d")

        lines = [f"📰 <b>Morning Briefing - {today}</b>\n"]

        # Only top story per domain for Telegram
        by_domain = {"ai": [], "software_development": [], "investment": []}
        for story in stories:
            by_domain.get(story.domain, []).append(story)

        if by_domain["ai"]:
            lines.append("🤖 <b>AI</b>")
            for story in by_domain["ai"][:3]:
                lines.append(f"{story.priority} {story.title}\n   {story.url}")
            lines.append("")

        if by_domain["software_development"]:
            lines.append("💻 <b>Dev</b>")
            for story in by_domain["software_development"][:3]:
                lines.append(f"{story.priority} {story.title}\n   {story.url}")
            lines.append("")

        if by_domain["investment"]:
            lines.append("💰 <b>Investment</b>")
            for story in by_domain["investment"][:3]:
                lines.append(f"{story.priority} {story.title}\n   {story.url}")

        return "\n".join(lines)

    def generate(self, hours: int = 24, format: str = "markdown") -> str:
        """Generate briefing in specified format."""
        stories = self.fetch_recent_stories(hours)
        top_stories = self.select_top_stories(stories)

        if format == "markdown":
            content = self.generate_markdown(top_stories)
        elif format == "telegram":
            content = self.generate_telegram(top_stories)
        else:
            raise ValueError(f"Unknown format: {format}")

        # Save to file
        timestamp = datetime.now().strftime("%Y-%m-%d")
        output_file = self.output_dir / f"briefing-{timestamp}.{format.replace('markdown', 'md')}"
        output_file.write_text(content)

        return content


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Generate morning briefing")
    parser.add_argument("--hours", type=int, default=24, help="Hours of news to include")
    parser.add_argument("--format", choices=["markdown", "telegram"], default="markdown")
    parser.add_argument("--db", default="news.db", help="SQLite database path")
    parser.add_argument("--output", default="output", help="Output directory")

    args = parser.parse_args()

    generator = BriefingGenerator(args.db, args.output)
    briefing = generator.generate(args.hours, args.format)

    print(briefing)


if __name__ == "__main__":
    main()
