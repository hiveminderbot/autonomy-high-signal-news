#!/usr/bin/env python3
"""
Feed Health Monitoring System for High-Signal News

Tracks fetch success/failure rates per source, marks unhealthy sources,
and generates health reports.
"""

import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass
from typing import Optional


@dataclass
class FeedHealth:
    """Health status for a single feed source."""
    source_id: str
    source_name: str
    url: str
    total_fetches: int
    successful_fetches: int
    failed_fetches: int
    success_rate: float
    avg_response_time_ms: float
    last_fetch_at: Optional[datetime]
    last_error: Optional[str]
    consecutive_failures: int
    is_healthy: bool
    status: str  # 'healthy', 'degraded', 'unhealthy'


class FeedHealthMonitor:
    """Monitor feed health and generate reports."""

    # Health thresholds
    HEALTHY_THRESHOLD = 0.8  # 80% success rate for healthy
    UNHEALTHY_THRESHOLD = 0.5  # Below 50% is unhealthy
    MAX_CONSECUTIVE_FAILURES = 3  # Auto-disable after this many failures

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._ensure_tables()

    def _ensure_tables(self):
        """Ensure health tracking tables exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS feed_health_status (
                    source_id TEXT PRIMARY KEY,
                    consecutive_failures INTEGER DEFAULT 0,
                    is_healthy BOOLEAN DEFAULT 1,
                    status TEXT DEFAULT 'healthy',
                    last_status_change TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_health_status
                    ON feed_health_status(status);
            """)

    def get_feed_health(self, source_id: str, window_hours: int = 24) -> Optional[FeedHealth]:
        """Get health statistics for a specific feed."""
        with sqlite3.connect(self.db_path) as conn:
            # Get source info
            source_row = conn.execute(
                """SELECT id, name, url, last_fetched, last_error
                   FROM feed_sources WHERE id = ?""",
                (source_id,)
            ).fetchone()

            if not source_row:
                return None

            # Get fetch statistics from window
            since = (datetime.now() - timedelta(hours=window_hours)).isoformat()
            stats = conn.execute(
                """SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful,
                    AVG(response_time_ms) as avg_response
                   FROM fetch_log
                   WHERE source_id = ? AND fetched_at > ?""",
                (source_id, since)
            ).fetchone()

            # Get consecutive failures
            health_row = conn.execute(
                """SELECT consecutive_failures, is_healthy, status
                   FROM feed_health_status WHERE source_id = ?""",
                (source_id,)
            ).fetchone()

            total = stats[0] or 0
            successful = stats[1] or 0
            failed = total - successful
            success_rate = successful / total if total > 0 else 1.0
            avg_response = stats[2] or 0

            consecutive_failures = health_row[0] if health_row else 0
            is_healthy = bool(health_row[1]) if health_row else True
            status = health_row[2] if health_row else 'healthy'

            # Determine status if not set
            if not health_row:
                if success_rate >= self.HEALTHY_THRESHOLD:
                    status = 'healthy'
                    is_healthy = True
                elif success_rate >= self.UNHEALTHY_THRESHOLD:
                    status = 'degraded'
                    is_healthy = True
                else:
                    status = 'unhealthy'
                    is_healthy = False

            return FeedHealth(
                source_id=source_row[0],
                source_name=source_row[1],
                url=source_row[2],
                total_fetches=total,
                successful_fetches=successful,
                failed_fetches=failed,
                success_rate=success_rate,
                avg_response_time_ms=avg_response,
                last_fetch_at=datetime.fromisoformat(source_row[3]) if source_row[3] else None,
                last_error=source_row[4],
                consecutive_failures=consecutive_failures,
                is_healthy=is_healthy,
                status=status
            )

    def update_health_status(self, source_id: str, fetch_success: bool, error_message: str = None):
        """Update health status after a fetch attempt."""
        with sqlite3.connect(self.db_path) as conn:
            # Get current status
            row = conn.execute(
                "SELECT consecutive_failures, is_healthy FROM feed_health_status WHERE source_id = ?",
                (source_id,)
            ).fetchone()

            if row:
                consecutive_failures = row[0]
                was_healthy = bool(row[1])
            else:
                consecutive_failures = 0
                was_healthy = True

            # Update consecutive failures
            if fetch_success:
                consecutive_failures = 0
            else:
                consecutive_failures += 1

            # Determine new status
            if consecutive_failures >= self.MAX_CONSECUTIVE_FAILURES:
                status = 'unhealthy'
                is_healthy = False
            elif consecutive_failures > 0:
                status = 'degraded'
                is_healthy = True
            else:
                status = 'healthy'
                is_healthy = True

            # Insert or update
            conn.execute(
                """INSERT OR REPLACE INTO feed_health_status
                   (source_id, consecutive_failures, is_healthy, status, last_status_change, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (source_id, consecutive_failures, is_healthy, status,
                 datetime.now().isoformat() if status != 'healthy' or not was_healthy else None,
                 datetime.now().isoformat())
            )

            # If too many consecutive failures, mark source as inactive
            if consecutive_failures >= self.MAX_CONSECUTIVE_FAILURES:
                conn.execute(
                    "UPDATE feed_sources SET active = 0 WHERE id = ?",
                    (source_id,)
                )
                return False  # Source was disabled

            return True  # Source still active

    def get_all_health(self, domain: str = None, window_hours: int = 24) -> list[FeedHealth]:
        """Get health for all feeds, optionally filtered by domain."""
        with sqlite3.connect(self.db_path) as conn:
            query = "SELECT id FROM feed_sources WHERE 1=1"
            params = []
            if domain:
                query += " AND domain = ?"
                params.append(domain)

            rows = conn.execute(query, params).fetchall()

        health_list = []
        for (source_id,) in rows:
            health = self.get_feed_health(source_id, window_hours)
            if health:
                health_list.append(health)

        return health_list

    def generate_health_report(self, domain: str = None, window_hours: int = 24) -> dict:
        """Generate a comprehensive health report."""
        health_list = self.get_all_health(domain, window_hours)

        total = len(health_list)
        healthy = sum(1 for h in health_list if h.status == 'healthy')
        degraded = sum(1 for h in health_list if h.status == 'degraded')
        unhealthy = sum(1 for h in health_list if h.status == 'unhealthy')

        avg_success_rate = sum(h.success_rate for h in health_list) / total if total > 0 else 0

        # Find problematic feeds
        problematic = [
            {
                'source_id': h.source_id,
                'source_name': h.source_name,
                'status': h.status,
                'success_rate': f"{h.success_rate:.1%}",
                'consecutive_failures': h.consecutive_failures,
                'last_error': h.last_error
            }
            for h in health_list if h.status != 'healthy'
        ]

        # Top slowest feeds
        slowest = sorted(
            [h for h in health_list if h.avg_response_time_ms > 0],
            key=lambda h: h.avg_response_time_ms,
            reverse=True
        )[:5]

        return {
            'generated_at': datetime.now().isoformat(),
            'window_hours': window_hours,
            'domain_filter': domain,
            'summary': {
                'total_feeds': total,
                'healthy': healthy,
                'degraded': degraded,
                'unhealthy': unhealthy,
                'avg_success_rate': f"{avg_success_rate:.1%}"
            },
            'problematic_feeds': problematic,
            'slowest_feeds': [
                {
                    'source_id': h.source_id,
                    'source_name': h.source_name,
                    'avg_response_ms': int(h.avg_response_time_ms)
                }
                for h in slowest
            ],
            'recommendations': self._generate_recommendations(health_list)
        }

    def _generate_recommendations(self, health_list: list[FeedHealth]) -> list[str]:
        """Generate recommendations based on health data."""
        recommendations = []

        unhealthy = [h for h in health_list if h.status == 'unhealthy']
        degraded = [h for h in health_list if h.status == 'degraded']

        if unhealthy:
            recommendations.append(
                f"{len(unhealthy)} feed(s) are unhealthy and have been auto-disabled. "
                "Review and fix or remove these sources."
            )

        if degraded:
            recommendations.append(
                f"{len(degraded)} feed(s) are degraded (intermittent failures). "
                "Monitor these sources for stability issues."
            )

        # Check for Cloudflare-protected feeds
        cloudflare_feeds = [
            h for h in health_list
            if h.last_error and ('cloudflare' in h.last_error.lower() or '403' in str(h.last_error))
        ]
        if cloudflare_feeds:
            recommendations.append(
                f"{len(cloudflare_feeds)} feed(s) appear to be Cloudflare-protected. "
                "Consider using RSSHub alternatives or manual ingestion."
            )

        # Check for feeds with no recent fetches
        stale_feeds = [
            h for h in health_list
            if h.last_fetch_at and (datetime.now() - h.last_fetch_at).days > 7
        ]
        if stale_feeds:
            recommendations.append(
                f"{len(stale_feeds)} feed(s) haven't been fetched in over 7 days. "
                "Verify these sources are still active."
            )

        return recommendations

    def validate_feed(self, url: str) -> dict:
        """Validate a feed URL before adding to catalog.

        Returns validation results including:
        - Whether the URL is reachable
        - Whether the content is valid RSS/Atom
        - Detected format and version
        """
        import requests

        result = {
            'url': url,
            'valid': False,
            'reachable': False,
            'format': None,
            'error': None,
            'warnings': []
        }

        try:
            headers = {
                'User-Agent': 'HighSignalNews/1.0 (Feed Validator; https://github.com/exedev/high-signal-news)'
            }
            response = requests.get(url, headers=headers, timeout=30, allow_redirects=True)
            response.raise_for_status()
            result['reachable'] = True

            content_type = response.headers.get('Content-Type', '')
            content = response.content

            # Try to parse with feedparser
            try:
                import feedparser
                parsed = feedparser.parse(content)

                if hasattr(parsed, 'version') and parsed.version:
                    result['format'] = parsed.version
                    result['valid'] = True
                elif hasattr(parsed, 'feed') and parsed.feed:
                    # Has feed data but no version - probably valid
                    result['valid'] = True
                    result['warnings'].append('Feed parsed but version not detected')
                else:
                    result['error'] = 'Content does not appear to be a valid RSS/Atom feed'

                    # Check if it's HTML (common issue)
                    if b'<html' in content[:1000].lower() or 'text/html' in content_type:
                        result['error'] = 'URL returns HTML instead of RSS/Atom feed'
                        result['warnings'].append('The URL may be a website homepage, not a feed URL')

                # Check for bozo (formatting errors)
                if hasattr(parsed, 'bozo') and parsed.bozo:
                    bozo_exception = getattr(parsed, 'bozo_exception', None)
                    if bozo_exception:
                        result['warnings'].append(f'Feed has formatting issues: {bozo_exception}')

                # Count entries
                if hasattr(parsed, 'entries'):
                    result['entry_count'] = len(parsed.entries)

            except ImportError:
                result['error'] = 'feedparser not available for validation'

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                result['error'] = 'Access forbidden (403) - may be Cloudflare protected'
            elif e.response.status_code == 404:
                result['error'] = 'Feed not found (404)'
            else:
                result['error'] = f'HTTP error: {e.response.status_code}'
        except requests.exceptions.Timeout:
            result['error'] = 'Request timed out'
        except requests.exceptions.ConnectionError:
            result['error'] = 'Connection error - host may be unreachable'
        except Exception as e:
            result['error'] = f'Validation error: {str(e)}'

        return result


def main():
    """CLI for health monitoring."""
    import argparse

    parser = argparse.ArgumentParser(description='Feed Health Monitor')
    parser.add_argument('--db', default='state/feeds.db', help='Database path')
    parser.add_argument('--domain', help='Filter by domain')
    parser.add_argument('--window', type=int, default=24, help='Hours to look back')
    parser.add_argument('--validate', help='Validate a feed URL')
    parser.add_argument('--json', action='store_true', help='Output as JSON')

    args = parser.parse_args()

    db_path = Path(args.db)

    if args.validate:
        monitor = FeedHealthMonitor(db_path)
        result = monitor.validate_feed(args.validate)
        print(json.dumps(result, indent=2))
        return 0 if result['valid'] else 1

    if not db_path.exists():
        print(f"Database not found: {db_path}")
        return 1

    monitor = FeedHealthMonitor(db_path)
    report = monitor.generate_health_report(args.domain, args.window)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print("=" * 60)
        print("📊 Feed Health Report")
        print("=" * 60)
        print(f"Generated: {report['generated_at']}")
        print(f"Window: Last {report['window_hours']} hours")
        if report['domain_filter']:
            print(f"Domain: {report['domain_filter']}")
        print()

        summary = report['summary']
        print(f"Total Feeds: {summary['total_feeds']}")
        print(f"  🟢 Healthy: {summary['healthy']}")
        print(f"  🟡 Degraded: {summary['degraded']}")
        print(f"  🔴 Unhealthy: {summary['unhealthy']}")
        print(f"Avg Success Rate: {summary['avg_success_rate']}")
        print()

        if report['problematic_feeds']:
            print("Problematic Feeds:")
            for feed in report['problematic_feeds']:
                icon = "🟡" if feed['status'] == 'degraded' else "🔴"
                print(f"  {icon} {feed['source_name']} ({feed['source_id']})")
                print(f"     Status: {feed['status']}, Success: {feed['success_rate']}")
                if feed['last_error']:
                    print(f"     Last error: {feed['last_error'][:60]}...")
            print()

        if report['recommendations']:
            print("Recommendations:")
            for rec in report['recommendations']:
                print(f"  💡 {rec}")
            print()

    return 0


if __name__ == '__main__':
    exit(main())
