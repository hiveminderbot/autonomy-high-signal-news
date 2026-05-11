"""Test that exposes the retry-count bug in DeliveryChannel._retry_wrapper."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from briefing.delivery import DeliveryChannel, DeliveryResult


class FailingThenSucceedingChannel(DeliveryChannel):
    """Channel that fails first N attempts then succeeds."""

    def __init__(self, fail_count=2):
        super().__init__(max_retries=3, retry_delay=0.01)
        self.fail_count = fail_count
        self.attempts = 0

    def deliver(self, content: str, subject=None) -> DeliveryResult:
        """This method is NOT used by _retry_wrapper; we call _retry_wrapper directly."""
        pass

    def _make_result(self, success):
        self.attempts += 1
        return DeliveryResult(
            success=success,
            channel='mock',
            timestamp='2026-05-07T00:00:00',
            message='success' if success else 'fail',
            error=None if success else 'simulated failure'
        )


def test_retry_count_reported_correctly():
    """After 2 failures and 1 success, retries should be 2, not 0."""
    channel = FailingThenSucceedingChannel(fail_count=2)

    def _deliver_fn(content, subject=None):
        success = channel.attempts >= channel.fail_count
        return channel._make_result(success)

    result = channel._retry_wrapper(_deliver_fn, "test content")
    assert result.success is True
    assert result.retries == 2, f"Expected retries=2 after 2 failures, got retries={result.retries}"


if __name__ == "__main__":
    test_retry_count_reported_correctly()
    print("RETRY_BUG_TEST_PASS")
