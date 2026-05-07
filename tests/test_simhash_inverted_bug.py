#!/usr/bin/env python3
"""
Bug exposure test for SimHash.similarity inverted matching_bits.
If matching_bits counts differing bits instead of matching bits,
similarity of near-duplicate texts returns LOW instead of HIGH.
The early return at line 79 masks the bug for identical hashes,
so we test near-duplicates which exercise the buggy line.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from aggregator.deduplicator import SimHash

def test_simhash_similarity_near_duplicate():
    """Near-duplicate texts should have high similarity (>0.7)."""
    s = SimHash()
    # Very similar text (single word change) should have high similarity
    h1 = s.compute("The quick brown fox jumps over the lazy dog")
    h2 = s.compute("The quick brown fox jumps over the lazy dogs")
    sim = s.similarity(h1, h2)
    assert sim > 0.7, f"Expected near-duplicate similarity > 0.7, got {sim}"

def test_simhash_similarity_different():
    """Different texts should have low similarity (<0.6)."""
    s = SimHash()
    h1 = s.compute("hello world")
    h2 = s.compute("completely different text about python programming")
    sim = s.similarity(h1, h2)
    assert sim < 0.6, f"Expected low similarity < 0.6, got {sim}"

if __name__ == "__main__":
    test_simhash_similarity_near_duplicate()
    test_simhash_similarity_different()
    print("✅ All SimHash similarity tests passed!")
