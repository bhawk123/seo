"""Content quality analysis - readability, keyword density, etc."""

import re
from collections import Counter
from typing import Dict

from seo.models import ContentQualityMetrics


class ContentQualityAnalyzer:
    """Analyzes content quality metrics including readability and keyword density."""

    # Common English words to filter out
    STOP_WORDS = {
        'the', 'be', 'to', 'of', 'and', 'a', 'in', 'that', 'have', 'i',
        'it', 'for', 'not', 'on', 'with', 'he', 'as', 'you', 'do', 'at',
        'this', 'but', 'his', 'by', 'from', 'they', 'we', 'say', 'her', 'she',
        'or', 'an', 'will', 'my', 'one', 'all', 'would', 'there', 'their',
        'what', 'so', 'up', 'out', 'if', 'about', 'who', 'get', 'which', 'go',
        'me', 'when', 'make', 'can', 'like', 'time', 'no', 'just', 'him', 'know',
        'take', 'people', 'into', 'year', 'your', 'good', 'some', 'could', 'them',
        'see', 'other', 'than', 'then', 'now', 'look', 'only', 'come', 'its', 'over',
        'think', 'also', 'back', 'after', 'use', 'two', 'how', 'our', 'work',
        'first', 'well', 'way', 'even', 'new', 'want', 'because', 'any', 'these',
        'give', 'day', 'most', 'us', 'is', 'was', 'are', 'been', 'has', 'had',
        'were', 'said', 'did', 'having', 'may', 'should'
    }

    def analyze(self, url: str, text: str) -> ContentQualityMetrics:
        """Analyze content quality for a given text.

        Args:
            url: The URL being analyzed
            text: The text content to analyze

        Returns:
            ContentQualityMetrics with analysis results
        """
        # Clean and prepare text
        text = self._clean_text(text)

        # Count basic metrics
        words = text.split()
        word_count = len(words)
        sentences = self._split_sentences(text)
        sentence_count = len(sentences)

        # Calculate averages
        avg_words_per_sentence = (
            word_count / sentence_count if sentence_count > 0 else 0
        )

        # Calculate readability
        readability_score, readability_grade = self._calculate_readability(
            text, word_count, sentence_count
        )

        # Keyword density
        keyword_density = self._calculate_keyword_density(words)

        # Unique words
        unique_words = len(set(w.lower() for w in words))

        # Difficult words (more than 2 syllables)
        difficult_words = sum(
            1 for word in words if self._count_syllables(word) > 2
        )

        return ContentQualityMetrics(
            url=url,
            readability_score=readability_score,
            readability_grade=readability_grade,
            word_count=word_count,
            sentence_count=sentence_count,
            avg_words_per_sentence=avg_words_per_sentence,
            keyword_density=keyword_density,
            unique_words=unique_words,
            difficult_words=difficult_words,
        )

    def _clean_text(self, text: str) -> str:
        """Clean text for analysis.

        Args:
            text: Raw text

        Returns:
            Cleaned text
        """
        # Remove extra whitespace
        text = ' '.join(text.split())
        return text

    def _split_sentences(self, text: str) -> list[str]:
        """Split text into sentences.

        Args:
            text: Text to split

        Returns:
            List of sentences
        """
        # Simple sentence splitting on common punctuation
        sentences = re.split(r'[.!?]+', text)
        # Filter out empty sentences
        return [s.strip() for s in sentences if s.strip()]

    def _calculate_readability(
        self, text: str, word_count: int, sentence_count: int
    ) -> tuple[float, str]:
        """Calculate Flesch Reading Ease score.

        Args:
            text: Text to analyze
            word_count: Number of words
            sentence_count: Number of sentences

        Returns:
            Tuple of (readability_score, grade_level)
        """
        if word_count == 0 or sentence_count == 0:
            return 0.0, "N/A"

        # Count syllables
        words = text.split()
        total_syllables = sum(self._count_syllables(word) for word in words)

        # Flesch Reading Ease = 206.835 - 1.015 × (words/sentences) - 84.6 × (syllables/words)
        words_per_sentence = word_count / sentence_count
        syllables_per_word = total_syllables / word_count

        score = 206.835 - (1.015 * words_per_sentence) - (84.6 * syllables_per_word)

        # Clamp score between 0 and 100
        score = max(0, min(100, score))

        # Determine grade level
        grade = self._score_to_grade(score)

        return round(score, 1), grade

    def _count_syllables(self, word: str) -> int:
        """Count syllables in a word (simple approximation).

        Args:
            word: Word to analyze

        Returns:
            Estimated syllable count
        """
        word = word.lower()
        vowels = 'aeiou'
        syllable_count = 0
        previous_was_vowel = False

        for char in word:
            is_vowel = char in vowels
            if is_vowel and not previous_was_vowel:
                syllable_count += 1
            previous_was_vowel = is_vowel

        # Adjust for silent 'e'
        if word.endswith('e'):
            syllable_count -= 1

        # Every word has at least one syllable
        return max(1, syllable_count)

    def _score_to_grade(self, score: float) -> str:
        """Convert Flesch Reading Ease score to grade level.

        Args:
            score: Flesch Reading Ease score (0-100)

        Returns:
            Grade level description
        """
        if score >= 90:
            return "5th Grade"
        elif score >= 80:
            return "6th Grade"
        elif score >= 70:
            return "7th Grade"
        elif score >= 60:
            return "8-9th Grade"
        elif score >= 50:
            return "10-12th Grade"
        elif score >= 30:
            return "College"
        else:
            return "College Graduate"

    def _calculate_keyword_density(self, words: list[str]) -> Dict[str, float]:
        """Calculate keyword density for top keywords.

        Args:
            words: List of words

        Returns:
            Dictionary of keyword to density percentage
        """
        if not words:
            return {}

        # Normalize words
        normalized_words = [
            w.lower().strip('.,!?;:"()[]{}')
            for w in words
            if len(w) > 3  # Skip short words
        ]

        # Filter out stop words
        filtered_words = [
            w for w in normalized_words
            if w not in self.STOP_WORDS
        ]

        if not filtered_words:
            return {}

        # Count word frequency
        word_counts = Counter(filtered_words)

        # Get top 10 keywords
        top_keywords = word_counts.most_common(10)

        total_words = len(filtered_words)

        # Calculate density as percentage
        keyword_density = {
            word: round((count / total_words) * 100, 2)
            for word, count in top_keywords
        }

        return keyword_density
