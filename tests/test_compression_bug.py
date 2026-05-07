#!/usr/bin/env python3
"""
Test to reveal the compression_ratio bug on the concise path.
When content is already concise (<= max_sentences), the code takes
a shortcut path that inverts the ratio: len(content)/len(summary)
instead of len(summary)/len(content). For identical summary and
content this is 1.0, but for a truncated summary it should be < 1.0.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from summarizer.content_summarizer import ContentSummarizer

def test_compression_ratio_concise_path():
    """Concise-path compression ratio must be <= 1.0."""
    summarizer = ContentSummarizer(max_sentences=5, min_sentence_length=5)
    text = "One. Two. Three. Four. Five."
    result = summarizer.summarize("T", text)

    print(f"original_length: {result.original_length}")
    print(f"summary_length: {result.summary_length}")
    print(f"compression_ratio: {result.compression_ratio}")

    # Summary should be <= original length, so ratio must be <= 1.0
    assert result.compression_ratio <= 1.0, \
        f"Expected compression_ratio <= 1.0, got {result.compression_ratio}"
    print("✅ test_compression_ratio_concise_path passed")

if __name__ == "__main__":
    test_compression_ratio_concise_path()
    print("\n✅ All compression bug tests passed!")
