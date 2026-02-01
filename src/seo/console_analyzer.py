"""Console error analyzer for JavaScript health assessment."""

import re
from collections import Counter
from typing import Dict, List, Optional, Pattern

from seo.models import PageMetadata, ConsoleErrorAnalysis
from seo.config import AnalysisThresholds, default_thresholds


class ConsoleErrorAnalyzer:
    """Analyzes JavaScript console errors and warnings from crawled pages."""

    # Default error type patterns (can be extended via constructor)
    DEFAULT_ERROR_PATTERNS: Dict[str, str] = {
        'TypeError': r'TypeError:',
        'ReferenceError': r'ReferenceError:',
        'SyntaxError': r'SyntaxError:',
        'RangeError': r'RangeError:',
        'URIError': r'URIError:',
        'NetworkError': r'(NetworkError|Failed to fetch|net::)',
        'SecurityError': r'(SecurityError|CORS|blocked)',
        'ResourceError': r'(404|Failed to load|ERR_)',
        'DeprecationWarning': r'(deprecated|Deprecation)',
    }

    def __init__(
        self,
        thresholds: Optional[AnalysisThresholds] = None,
        error_patterns: Optional[Dict[str, str]] = None,
    ):
        """Initialize analyzer with configurable settings.

        Args:
            thresholds: Analysis thresholds configuration
            error_patterns: Custom error categorization patterns
        """
        self.thresholds = thresholds or default_thresholds
        self.error_patterns = error_patterns or self.DEFAULT_ERROR_PATTERNS

        # Compile patterns for efficiency
        self._compiled_patterns: Dict[str, Pattern] = {
            name: re.compile(pattern, re.IGNORECASE)
            for name, pattern in self.error_patterns.items()
        }

    @property
    def top_errors_count(self) -> int:
        """Number of top errors to report."""
        return self.thresholds.console_error_top_count

    @property
    def top_pages_count(self) -> int:
        """Number of top pages to report."""
        return self.thresholds.console_pages_top_count

    def analyze(self, pages: Dict[str, PageMetadata]) -> ConsoleErrorAnalysis:
        """Analyze console errors across all pages.

        Args:
            pages: Dictionary mapping URLs to PageMetadata

        Returns:
            ConsoleErrorAnalysis with error metrics
        """
        if not pages:
            return ConsoleErrorAnalysis()

        analysis = ConsoleErrorAnalysis(total_pages=len(pages))

        all_errors: List[Dict] = []
        error_messages: List[str] = []
        pages_errors: List[Dict] = []

        for url, page in pages.items():
            page_error_count = 0
            page_warning_count = 0
            page_errors_list: List[str] = []

            # Process errors
            for error in page.console_errors:
                error_type = self._categorize_error(error)
                all_errors.append({
                    'url': url,
                    'message': error[:200],  # Truncate long messages
                    'type': error_type
                })
                error_messages.append(error[:100])  # For frequency analysis
                page_error_count += 1
                page_errors_list.append(error[:100])

                # Count by type
                analysis.errors_by_type[error_type] = \
                    analysis.errors_by_type.get(error_type, 0) + 1

            # Process warnings
            for warning in page.console_warnings:
                page_warning_count += 1

            # Track pages with errors
            if page_error_count > 0:
                analysis.pages_with_errors += 1
                pages_errors.append({
                    'url': url,
                    'error_count': page_error_count,
                    'warning_count': page_warning_count,
                    'errors': page_errors_list[:5]  # Top 5 errors per page
                })

            if page_warning_count > 0:
                analysis.pages_with_warnings += 1

            analysis.total_warnings += page_warning_count

        # Totals
        analysis.total_errors = len(all_errors)

        # Error-free percentage
        if analysis.total_pages > 0:
            error_free = analysis.total_pages - analysis.pages_with_errors
            analysis.error_free_percentage = round(
                error_free / analysis.total_pages * 100, 1
            )

        # Sort pages by error count and limit
        pages_errors.sort(key=lambda x: x['error_count'], reverse=True)
        analysis.pages_by_error_count = pages_errors[:self.top_pages_count]

        # Find most common errors
        error_counter = Counter(error_messages)
        analysis.common_errors = [
            {'message': msg, 'count': count}
            for msg, count in error_counter.most_common(self.top_errors_count)
        ]

        # Store all errors (limited)
        analysis.all_errors = all_errors[:100]

        return analysis

    def _categorize_error(self, error: str) -> str:
        """Categorize an error message by type.

        Args:
            error: Error message string

        Returns:
            Error type category
        """
        for error_type, pattern in self._compiled_patterns.items():
            if pattern.search(error):
                return error_type
        return 'Other'
