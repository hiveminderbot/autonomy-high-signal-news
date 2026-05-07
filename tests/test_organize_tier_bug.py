"""Test that exposes the swapped limit bug in BriefingGenerator.organize_by_tier."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from briefing.generator import BriefingGenerator, BriefingItem


def test_must_read_limited_by_max_must_read_total():
    """must_read items should be limited by max_must_read_total, not max_important_total."""
    generator = BriefingGenerator(max_must_read_total=2, max_important_total=10)
    items = [
        BriefingItem(title=f'M{i}', summary='s', sources=['S'], tier='must_read')
        for i in range(5)
    ]
    must_read, _, _ = generator.organize_by_tier(items)
    assert len(must_read) == 2, f"Expected 2 must_read items, got {len(must_read)}"


def test_important_limited_by_max_important_total():
    """important items should be limited by max_important_total, not max_must_read_total."""
    generator = BriefingGenerator(max_must_read_total=2, max_important_total=3)
    items = [
        BriefingItem(title=f'I{i}', summary='s', sources=['S'], tier='important')
        for i in range(5)
    ]
    _, important, _ = generator.organize_by_tier(items)
    assert len(important) == 3, f"Expected 3 important items, got {len(important)}"


if __name__ == "__main__":
    test_must_read_limited_by_max_must_read_total()
    test_important_limited_by_max_important_total()
    print("BUG_EXPOSED_TESTS_PASS")
