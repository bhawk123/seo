"""Content quality analysis - readability, keyword density, etc."""

import re
from collections import Counter
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from seo.models import (
    ContentQualityMetrics,
    EvidenceRecord,
    EvidenceCollection,
    ConfidenceLevel,
    EvidenceSourceType,
)
from seo.constants import (
    DIFFICULT_WORD_SYLLABLES,
    HIGH_KEYWORD_DENSITY_PERCENT,
    MIN_WORDS_FOR_RELIABLE_ANALYSIS,
    TOP_KEYWORDS_COUNT,
    MAX_DIFFICULT_WORD_SAMPLES,
    MIN_KEYWORD_LENGTH,
    FLESCH_FORMULA,
    GRADE_MAPPING,
)


class ContentQualityAnalyzer:
    """Analyzes content quality metrics including readability and keyword density."""

    # Import constants as class attributes for backwards compatibility
    FLESCH_FORMULA = FLESCH_FORMULA
    GRADE_MAPPING = GRADE_MAPPING
    DIFFICULT_WORD_SYLLABLES = DIFFICULT_WORD_SYLLABLES
    HIGH_KEYWORD_DENSITY = HIGH_KEYWORD_DENSITY_PERCENT
    MIN_WORDS_FOR_RELIABLE_ANALYSIS = MIN_WORDS_FOR_RELIABLE_ANALYSIS

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

    def __init__(self):
        """Initialize the content quality analyzer."""
        self._evidence_collection: Optional[EvidenceCollection] = None
        self._url: str = ""

    def analyze(self, url: str, text: str) -> Tuple[ContentQualityMetrics, Dict]:
        """Analyze content quality for a given text.

        Args:
            url: The URL being analyzed
            text: The text content to analyze

        Returns:
            Tuple of (ContentQualityMetrics, evidence_dict)
        """
        self._url = url
        self._evidence_collection = EvidenceCollection(
            finding='content_quality',
            component_id='content_quality_analyzer',
        )

        # Clean and prepare text
        original_text = text
        text = self._clean_text(text)
        html_stripped = original_text != text

        # Count basic metrics
        words = text.split()
        word_count = len(words)
        sentences = self._split_sentences(text)
        sentence_count = len(sentences)

        # Determine confidence based on content length
        confidence = ConfidenceLevel.HIGH
        if word_count < self.MIN_WORDS_FOR_RELIABLE_ANALYSIS:
            confidence = ConfidenceLevel.LOW

        # Calculate averages
        avg_words_per_sentence = (
            word_count / sentence_count if sentence_count > 0 else 0
        )

        # Calculate readability with evidence
        readability_score, readability_grade, total_syllables = self._calculate_readability(
            text, word_count, sentence_count
        )

        # Add readability evidence
        self._add_readability_evidence(
            score=readability_score,
            grade=readability_grade,
            word_count=word_count,
            sentence_count=sentence_count,
            total_syllables=total_syllables,
            avg_words_per_sentence=avg_words_per_sentence,
            confidence=confidence,
        )

        # Keyword density with evidence
        keyword_density, stop_words_excluded, analyzed_word_count = self._calculate_keyword_density(words)

        # Add keyword density evidence
        self._add_keyword_density_evidence(
            keyword_density=keyword_density,
            stop_words_excluded=stop_words_excluded,
            analyzed_word_count=analyzed_word_count,
            total_word_count=word_count,
        )

        # Unique words
        unique_words = len(set(w.lower() for w in words))

        # Difficult words with evidence
        difficult_words, difficult_word_samples = self._find_difficult_words(words)

        # Add difficult words evidence
        self._add_difficult_words_evidence(
            difficult_word_count=difficult_words,
            total_word_count=word_count,
            sample_words=difficult_word_samples,
        )

        # Add edge case evidence if applicable
        if word_count < self.MIN_WORDS_FOR_RELIABLE_ANALYSIS:
            self._add_edge_case_evidence(
                issue='insufficient_content',
                message=f'Only {word_count} words; analysis may be unreliable (minimum: {self.MIN_WORDS_FOR_RELIABLE_ANALYSIS})',
            )

        if sentence_count == 0 and word_count > 0:
            self._add_edge_case_evidence(
                issue='no_sentences',
                message='No sentence-ending punctuation found; avg_words_per_sentence set to 0',
            )

        if html_stripped:
            self._add_edge_case_evidence(
                issue='html_stripped',
                message='HTML tags and extra whitespace were stripped for analysis',
            )

        metrics = ContentQualityMetrics(
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

        return metrics, self._evidence_collection.to_dict()

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
    ) -> Tuple[float, str, int]:
        """Calculate Flesch Reading Ease score.

        Args:
            text: Text to analyze
            word_count: Number of words
            sentence_count: Number of sentences

        Returns:
            Tuple of (readability_score, grade_level, total_syllables)
        """
        if word_count == 0 or sentence_count == 0:
            return 0.0, "N/A", 0

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

        return round(score, 1), grade, total_syllables

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

    def _calculate_keyword_density(self, words: List[str]) -> Tuple[Dict[str, float], int, int]:
        """Calculate keyword density for top keywords.

        Args:
            words: List of words

        Returns:
            Tuple of (keyword_density_dict, stop_words_excluded, analyzed_word_count)
        """
        if not words:
            return {}, 0, 0

        # Normalize words
        normalized_words = [
            w.lower().strip('.,!?;:"()[]{}')
            for w in words
            if len(w) > MIN_KEYWORD_LENGTH  # Skip short words
        ]

        # Count stop words that will be filtered
        stop_words_excluded = sum(
            1 for w in normalized_words if w in self.STOP_WORDS
        )

        # Filter out stop words
        filtered_words = [
            w for w in normalized_words
            if w not in self.STOP_WORDS
        ]

        if not filtered_words:
            return {}, stop_words_excluded, 0

        # Count word frequency
        word_counts = Counter(filtered_words)

        # Get top keywords
        top_keywords = word_counts.most_common(TOP_KEYWORDS_COUNT)

        analyzed_word_count = len(filtered_words)

        # Calculate density as percentage
        keyword_density = {
            word: round((count / analyzed_word_count) * 100, 2)
            for word, count in top_keywords
        }

        return keyword_density, stop_words_excluded, analyzed_word_count

    def _find_difficult_words(self, words: List[str]) -> Tuple[int, List[Dict[str, int]]]:
        """Find difficult words (3+ syllables) with samples.

        Args:
            words: List of words

        Returns:
            Tuple of (difficult_word_count, sample_words_with_syllables)
        """
        difficult_words = []

        for word in words:
            cleaned_word = word.lower().strip('.,!?;:"()[]{}')
            if len(cleaned_word) < 3:
                continue
            syllable_count = self._count_syllables(cleaned_word)
            if syllable_count >= self.DIFFICULT_WORD_SYLLABLES:
                difficult_words.append({
                    'word': cleaned_word,
                    'syllables': syllable_count,
                })

        # Get unique difficult words for sampling
        seen = set()
        unique_samples = []
        for item in difficult_words:
            if item['word'] not in seen:
                seen.add(item['word'])
                unique_samples.append(item)
                if len(unique_samples) >= MAX_DIFFICULT_WORD_SAMPLES:
                    break

        return len(difficult_words), unique_samples

    def _get_grade_range(self, score: float) -> str:
        """Get the grade range that a score falls into.

        Args:
            score: Flesch Reading Ease score

        Returns:
            String describing the score range
        """
        for (low, high), grade in self.GRADE_MAPPING.items():
            if low <= score <= high:
                return f"{low}-{high} maps to {grade}"
        return "Unknown range"

    def _add_readability_evidence(
        self,
        score: float,
        grade: str,
        word_count: int,
        sentence_count: int,
        total_syllables: int,
        avg_words_per_sentence: float,
        confidence: ConfidenceLevel,
    ) -> None:
        """Add evidence for readability score calculation.

        Args:
            score: Calculated Flesch Reading Ease score
            grade: Corresponding grade level
            word_count: Total word count
            sentence_count: Total sentence count
            total_syllables: Total syllable count
            avg_words_per_sentence: Average words per sentence
            confidence: Confidence level based on content length
        """
        avg_syllables_per_word = total_syllables / word_count if word_count > 0 else 0

        record = EvidenceRecord(
            component_id='content_quality_analyzer',
            finding='readability_score',
            evidence_string=f'Flesch Reading Ease: {score} ({grade})',
            confidence=confidence,
            timestamp=datetime.now(),
            source='Flesch Reading Ease Formula',
            source_type=EvidenceSourceType.CALCULATION,
            source_location=self._url,
            measured_value=score,
            ai_generated=False,
            reasoning=f'Score {score} falls in range: {self._get_grade_range(score)}',
            input_summary={
                'formula': self.FLESCH_FORMULA,
                'formula_components': {
                    'total_words': word_count,
                    'total_sentences': sentence_count,
                    'total_syllables': total_syllables,
                    'avg_words_per_sentence': round(avg_words_per_sentence, 2),
                    'avg_syllables_per_word': round(avg_syllables_per_word, 2),
                },
                'grade_mapping': self.GRADE_MAPPING,
                'calculated_grade': grade,
            },
        )
        self._evidence_collection.add_record(record)

    def _add_keyword_density_evidence(
        self,
        keyword_density: Dict[str, float],
        stop_words_excluded: int,
        analyzed_word_count: int,
        total_word_count: int,
    ) -> None:
        """Add evidence for keyword density calculation.

        Args:
            keyword_density: Dictionary of keyword to density percentage
            stop_words_excluded: Number of stop words filtered out
            analyzed_word_count: Word count after filtering
            total_word_count: Original word count
        """
        # Build ranked keyword list for evidence
        ranked_keywords = [
            {'rank': i + 1, 'keyword': kw, 'density': density}
            for i, (kw, density) in enumerate(keyword_density.items())
        ]

        # Check for high density warnings
        high_density_keywords = [
            kw for kw, density in keyword_density.items()
            if density > self.HIGH_KEYWORD_DENSITY
        ]

        record = EvidenceRecord(
            component_id='content_quality_analyzer',
            finding='keyword_density',
            evidence_string=f'Top {len(keyword_density)} keywords analyzed from {analyzed_word_count} words',
            confidence=ConfidenceLevel.HIGH,
            timestamp=datetime.now(),
            source='Keyword Density Calculation',
            source_type=EvidenceSourceType.CALCULATION,
            source_location=self._url,
            measured_value=keyword_density,
            ai_generated=False,
            reasoning='Keyword density = (occurrences / analyzed_word_count) * 100',
            input_summary={
                'formula': '(keyword_occurrences / analyzed_word_count) * 100',
                'total_word_count': total_word_count,
                'stop_words_excluded': stop_words_excluded,
                'analyzed_word_count': analyzed_word_count,
                'ranked_keywords': ranked_keywords,
                'high_density_threshold': self.HIGH_KEYWORD_DENSITY,
                'high_density_warnings': high_density_keywords if high_density_keywords else None,
            },
        )
        self._evidence_collection.add_record(record)

        # Add separate warning evidence for high density keywords
        if high_density_keywords:
            warning_record = EvidenceRecord(
                component_id='content_quality_analyzer',
                finding='keyword_stuffing_risk',
                evidence_string=f'Keywords exceeding {self.HIGH_KEYWORD_DENSITY}% density: {", ".join(high_density_keywords)}',
                confidence=ConfidenceLevel.HIGH,
                timestamp=datetime.now(),
                source='Keyword Density Analysis',
                source_type=EvidenceSourceType.CALCULATION,
                source_location=self._url,
                measured_value=high_density_keywords,
                ai_generated=False,
                reasoning=f'Keyword density above {self.HIGH_KEYWORD_DENSITY}% may indicate keyword stuffing',
            )
            self._evidence_collection.add_record(warning_record)

    def _add_difficult_words_evidence(
        self,
        difficult_word_count: int,
        total_word_count: int,
        sample_words: List[Dict[str, int]],
    ) -> None:
        """Add evidence for difficult word analysis.

        Args:
            difficult_word_count: Number of difficult words found
            total_word_count: Total word count
            sample_words: Sample difficult words with syllable counts
        """
        percentage = (difficult_word_count / total_word_count * 100) if total_word_count > 0 else 0

        record = EvidenceRecord(
            component_id='content_quality_analyzer',
            finding='difficult_words',
            evidence_string=f'{difficult_word_count} difficult words ({percentage:.1f}% of content)',
            confidence=ConfidenceLevel.HIGH,
            timestamp=datetime.now(),
            source='Syllable Analysis',
            source_type=EvidenceSourceType.CALCULATION,
            source_location=self._url,
            measured_value=difficult_word_count,
            ai_generated=False,
            reasoning=f'Words with >= {self.DIFFICULT_WORD_SYLLABLES} syllables are considered difficult',
            input_summary={
                'threshold': f'>= {self.DIFFICULT_WORD_SYLLABLES} syllables',
                'difficult_word_count': difficult_word_count,
                'total_word_count': total_word_count,
                'percentage': round(percentage, 1),
                'sample_words': sample_words if sample_words else None,
            },
        )
        self._evidence_collection.add_record(record)

    def _add_edge_case_evidence(self, issue: str, message: str) -> None:
        """Add evidence for edge case handling.

        Args:
            issue: Type of edge case
            message: Description of the issue
        """
        record = EvidenceRecord(
            component_id='content_quality_analyzer',
            finding=f'edge_case_{issue}',
            evidence_string=message,
            confidence=ConfidenceLevel.LOW,
            timestamp=datetime.now(),
            source='Content Analysis',
            source_type=EvidenceSourceType.HEURISTIC,
            source_location=self._url,
            ai_generated=False,
            reasoning='Edge case detected during content analysis',
        )
        self._evidence_collection.add_record(record)
