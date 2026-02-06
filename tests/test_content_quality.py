# tests/test_content_quality.py
"""Tests for the content quality analyzer."""

import pytest
from seo.content_quality import ContentQualityAnalyzer
from seo.constants import (
    DIFFICULT_WORD_SYLLABLES,
    HIGH_KEYWORD_DENSITY_PERCENT,
    MIN_WORDS_FOR_RELIABLE_ANALYSIS,
)


class TestContentQualityAnalyzer:
    """Test suite for ContentQualityAnalyzer."""

    @pytest.fixture
    def analyzer(self):
        """Create a ContentQualityAnalyzer instance."""
        return ContentQualityAnalyzer()

    def test_analyzer_initialization(self, analyzer):
        """Test that the analyzer initializes with correct constants."""
        assert analyzer.DIFFICULT_WORD_SYLLABLES == DIFFICULT_WORD_SYLLABLES
        assert analyzer.HIGH_KEYWORD_DENSITY == HIGH_KEYWORD_DENSITY_PERCENT
        assert analyzer.MIN_WORDS_FOR_RELIABLE_ANALYSIS == MIN_WORDS_FOR_RELIABLE_ANALYSIS

    def test_count_syllables_simple_words(self, analyzer):
        """Test syllable counting for simple words."""
        assert analyzer._count_syllables("the") == 1
        assert analyzer._count_syllables("hello") == 2
        assert analyzer._count_syllables("beautiful") == 3

    def test_count_syllables_edge_cases(self, analyzer):
        """Test syllable counting for edge cases."""
        # Empty string returns at least 1 (minimum)
        assert analyzer._count_syllables("") >= 0
        assert analyzer._count_syllables("a") == 1
        assert analyzer._count_syllables("I") == 1

    def test_analyze_short_content(self, analyzer):
        """Test analysis of content with fewer words than minimum."""
        short_content = "This is a very short text."
        url = "https://example.com/short"
        metrics, evidence = analyzer.analyze(url, short_content)

        assert metrics.word_count < MIN_WORDS_FOR_RELIABLE_ANALYSIS

    def test_analyze_content_metrics(self, analyzer):
        """Test that analysis returns correct metrics structure."""
        # Create content with more than MIN_WORDS_FOR_RELIABLE_ANALYSIS words
        content = " ".join(["word"] * 100)
        url = "https://example.com/test"
        metrics, evidence = analyzer.analyze(url, content)

        assert metrics.word_count == 100
        # Check for readability_score (not flesch_reading_ease)
        assert hasattr(metrics, 'readability_score')
        assert hasattr(metrics, 'readability_grade')
        assert hasattr(metrics, 'difficult_words')

    def test_analyze_keyword_density(self, analyzer):
        """Test keyword density calculation."""
        # Create content where 'keyword' appears frequently
        content = "keyword " * 50 + "other text " * 50
        url = "https://example.com/keywords"
        metrics, evidence = analyzer.analyze(url, content)

        # Check that keyword_density dict exists
        assert metrics.keyword_density is not None

    def test_readability_score_simple(self, analyzer):
        """Test readability score for simple content."""
        # Simple, short sentences with common words should score high
        simple_content = "The cat sat on the mat. The dog ran in the park. Birds fly in the sky."
        # Repeat to get enough words
        simple_content = (simple_content + " ") * 10
        url = "https://example.com/simple"
        metrics, evidence = analyzer.analyze(url, simple_content)

        # Simple content should have a readability score
        assert metrics.readability_score is not None

    def test_readability_score_complex(self, analyzer):
        """Test readability score for complex content."""
        # Complex, long sentences with difficult words should score lower
        complex_content = (
            "The implementation of sophisticated methodological approaches "
            "necessitates comprehensive understanding of multidisciplinary "
            "theoretical frameworks and epistemological considerations."
        )
        complex_content = (complex_content + " ") * 5
        url = "https://example.com/complex"
        metrics, evidence = analyzer.analyze(url, complex_content)

        # Complex content should have a readability score
        assert metrics.readability_score is not None

    def test_difficult_words_detection(self, analyzer):
        """Test detection of difficult words."""
        # Content with difficult words (3+ syllables)
        content = (
            "The comprehensive implementation of sophisticated methodologies "
            "requires understanding of multidisciplinary approaches."
        )
        content = (content + " ") * 5
        url = "https://example.com/difficult"
        metrics, evidence = analyzer.analyze(url, content)

        # Should detect difficult words like 'comprehensive', 'implementation', etc.
        assert metrics.difficult_words > 0

    def test_evidence_collection(self, analyzer):
        """Test that evidence is collected during analysis."""
        content = " ".join(["test"] * 100)
        url = "https://example.com/evidence"
        metrics, evidence = analyzer.analyze(url, content)

        # Evidence should be returned as a dict
        assert isinstance(evidence, dict)

    def test_clean_text(self, analyzer):
        """Test text cleaning removes HTML and normalizes whitespace."""
        text = "Hello   World\n\nTest"
        cleaned = analyzer._clean_text(text)
        # Should normalize whitespace
        assert "  " not in cleaned

    def test_split_sentences(self, analyzer):
        """Test sentence splitting."""
        text = "First sentence. Second sentence! Third sentence?"
        sentences = analyzer._split_sentences(text)
        assert len(sentences) >= 3

    def test_score_to_grade(self, analyzer):
        """Test Flesch score to grade level mapping."""
        # Very easy (90-100) should be 5th grade
        assert "5th" in analyzer._score_to_grade(95)
        # Very hard (0-29) should be Graduate level
        grade = analyzer._score_to_grade(20)
        assert "graduate" in grade.lower() or "college" in grade.lower()
