#!/usr/bin/env python3
"""
Tests for the content summarizer module.

Run with: python tests/test_content_summarizer.py
"""

import sys
from pathlib import Path

# Add scripts to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'scripts'))

from summarizer.content_summarizer import ContentSummarizer, SummaryResult


def test_split_sentences():
    """Test sentence splitting."""
    summarizer = ContentSummarizer(min_sentence_length=10)
    
    text = "First sentence here. Second sentence here! Third sentence here?"
    sentences = summarizer._split_sentences(text)
    
    assert len(sentences) == 3, f"Expected 3 sentences, got {len(sentences)}"
    print("✅ test_split_sentences passed")


def test_split_sentences_handles_abbreviations():
    """Test sentence splitting handles abbreviations like Mr. Dr. etc."""
    summarizer = ContentSummarizer(min_sentence_length=10)
    
    text = "Dr. Smith went to Washington. Mr. Jones stayed home."
    sentences = summarizer._split_sentences(text)
    
    assert len(sentences) == 2, f"Expected 2 sentences, got {len(sentences)}: {sentences}"
    print("✅ test_split_sentences_handles_abbreviations passed")


def test_split_sentences_filters_short():
    """Test that very short sentences are filtered out."""
    summarizer = ContentSummarizer(min_sentence_length=20)
    
    text = "Hi. This is a longer sentence that should be kept. Ok."
    sentences = summarizer._split_sentences(text)
    
    # "Hi" and "Ok" should be filtered out
    assert len(sentences) == 1, f"Expected 1 sentence after filtering, got {len(sentences)}"
    print("✅ test_split_sentences_filters_short passed")


def test_tokenize_words():
    """Test word tokenization."""
    summarizer = ContentSummarizer()
    
    text = "Hello World! Testing 12345."
    words = summarizer._tokenize_words(text)
    
    assert 'hello' in words, f"Expected 'hello' in words"
    assert 'world' in words, f"Expected 'world' in words"
    assert 'testing' in words, f"Expected 'testing' in words"
    assert '12' not in words, f"Short tokens should be filtered"
    print("✅ test_tokenize_words passed")


def test_score_sentences_empty():
    """Test scoring empty sentence list."""
    summarizer = ContentSummarizer()
    
    scored = summarizer._score_sentences([], "Title")
    
    assert scored == [], f"Expected empty list for empty input"
    print("✅ test_score_sentences_empty passed")


def test_score_sentences_returns_scores():
    """Test that scoring returns sentences with scores."""
    summarizer = ContentSummarizer()
    
    sentences = [
        "This is the first sentence about OpenAI.",
        "This is the second sentence about GPT-5.",
        "This is the third sentence about AI."
    ]
    title = "OpenAI GPT-5 Release"
    
    scored = summarizer._score_sentences(sentences, title)
    
    assert len(scored) == 3, f"Expected 3 scored sentences, got {len(scored)}"
    for sentence, score in scored:
        assert isinstance(score, float), f"Expected float score, got {type(score)}"
        assert score > 0, f"Expected positive score, got {score}"
    print("✅ test_score_sentences_returns_scores passed")


def test_score_sentences_position_boost():
    """Test that earlier sentences get position boost."""
    summarizer = ContentSummarizer()
    
    sentences = [
        "First sentence about OpenAI and GPT-5.",
        "Second sentence about something else entirely different."
    ]
    title = "OpenAI GPT-5"
    
    scored = summarizer._score_sentences(sentences, title)
    
    # First sentence should generally score higher due to position
    assert scored[0][1] >= scored[1][1] * 0.5, \
        f"First sentence should score reasonably high"
    print("✅ test_score_sentences_position_boost passed")


def test_summarize_empty():
    """Test summarizing empty content falls back to title."""
    summarizer = ContentSummarizer()
    
    result = summarizer.summarize("", "Fallback Title")
    
    assert isinstance(result, SummaryResult), f"Expected SummaryResult"
    # Empty content falls back to title
    assert result.summary == "Fallback Title", f"Expected title fallback, got {result.summary}"
    print("✅ test_summarize_empty passed")


def test_summarize_short_content():
    """Test summarizing content shorter than max_sentences."""
    summarizer = ContentSummarizer(max_sentences=5)
    
    text = "This is a short article. It only has two sentences."
    result = summarizer.summarize(text, "Short Article")
    
    assert len(result.key_sentences) <= 2, f"Expected at most 2 sentences, got {len(result.key_sentences)}"
    assert result.compression_ratio >= 1.0, f"Expected compression >= 1.0 for short content"
    print("✅ test_summarize_short_content passed")


def test_summarize_long_content():
    """Test summarizing longer content reduces sentences."""
    summarizer = ContentSummarizer(max_sentences=2, min_sentence_length=10)
    
    # Create content with many sentences (each must be >10 chars)
    text = (
        "Sentence one about OpenAI releasing new features for developers everywhere. "
        "Sentence two about machine learning improvements in the latest model update. "
        "Sentence three about developer reactions to the announcement from the company. "
        "Sentence four about industry impact and competitive responses from rivals. "
        "Sentence five about future roadmap and upcoming feature releases planned."
    )
    result = summarizer.summarize(text, "Test Title")
    
    # Should have at most max_sentences
    assert len(result.key_sentences) <= 2, f"Expected at most 2 sentences, got {len(result.key_sentences)}"
    # Should return a summary
    assert result.summary != "", f"Expected non-empty summary"
    print("✅ test_summarize_long_content passed")


def test_summarize_title_overlap_boost():
    """Test that sentences with title word overlap score higher."""
    summarizer = ContentSummarizer(max_sentences=1)
    
    text = (
        "Random sentence about unrelated topics. "
        "OpenAI announced the new GPT-5 model today."
    )
    result = summarizer.summarize(text, "OpenAI GPT-5 Release")
    
    # The summary should contain the relevant sentence
    assert "OpenAI" in result.summary or "GPT-5" in result.summary, \
        f"Expected summary to contain key terms, got: {result.summary}"
    print("✅ test_summarize_title_overlap_boost passed")


def test_summarize_batch():
    """Test batch summarization of multiple stories."""
    summarizer = ContentSummarizer()
    
    stories = [
        {'id': '1', 'title': 'Story One', 'content': 'First story content here with sufficient length.'},
        {'id': '2', 'title': 'Story Two', 'content': 'Second story content here with sufficient length.'},
    ]
    
    results = summarizer.summarize_batch(stories)
    
    assert '1' in results, f"Expected result for story '1'"
    assert '2' in results, f"Expected result for story '2'"
    assert isinstance(results['1'], SummaryResult), f"Expected SummaryResult"
    print("✅ test_summarize_batch passed")


def test_compression_ratio_calculation():
    """Test that compression ratio is calculated correctly."""
    summarizer = ContentSummarizer(max_sentences=1)
    
    text = "Sentence one. Sentence two. Sentence three. Sentence four."
    result = summarizer.summarize(text, "Title")
    
    expected_ratio = result.summary_length / result.original_length
    assert abs(result.compression_ratio - expected_ratio) < 0.01, \
        f"Expected ratio {expected_ratio}, got {result.compression_ratio}"
    print("✅ test_compression_ratio_calculation passed")


def test_word_count():
    """Test that word count is calculated correctly."""
    summarizer = ContentSummarizer(min_sentence_length=5)
    
    text = "This summary has exactly five words in it for testing."
    result = summarizer.summarize(text, "Title")
    
    # Word count should be non-negative
    assert result.word_count >= 0, f"Expected non-negative word count, got {result.word_count}"
    print("✅ test_word_count passed")


if __name__ == "__main__":
    test_split_sentences()
    test_split_sentences_handles_abbreviations()
    test_split_sentences_filters_short()
    test_tokenize_words()
    test_score_sentences_empty()
    test_score_sentences_returns_scores()
    test_score_sentences_position_boost()
    test_summarize_empty()
    test_summarize_short_content()
    test_summarize_long_content()
    test_summarize_title_overlap_boost()
    test_summarize_batch()
    test_compression_ratio_calculation()
    test_word_count()
    
    print("\n✅ All content summarizer tests passed!")
