"""
Scheduler Module - Phase 4

Handles automated scheduling and orchestration of daily briefings:
- Cron-compatible daily briefing generation
- End-to-end pipeline orchestration
- Error handling and retries
- Configuration management
"""

from .daily_briefing import DailyBriefingScheduler, run_daily_briefing

__all__ = [
    'DailyBriefingScheduler',
    'run_daily_briefing',
]
