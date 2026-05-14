"""Regression tests for daily cron orchestration."""
from pathlib import Path


def test_daily_cron_generates_briefing_after_successful_aggregation():
    script = Path("scripts/daily_cron.sh").read_text()

    aggregation_call = 'scripts/run_daily_aggregation.py "$@"'
    briefing_call = 'scripts/generate_high_signal_briefing.py --days "$BRIEFING_DAYS" --format all'

    assert aggregation_call in script
    assert briefing_call in script
    assert script.index(aggregation_call) < script.index(briefing_call)
    assert "HIGH_SIGNAL_SKIP_BRIEFING_GENERATION" in script
