"""Resource composition analyzer for page weight optimization."""

from typing import Dict, List, Optional

from seo.models import PageMetadata, ResourceAnalysis, ResourceBreakdown
from seo.config import AnalysisThresholds, default_thresholds


class ResourceAnalyzer:
    """Analyzes page resource composition and identifies optimization opportunities."""

    def __init__(self, thresholds: Optional[AnalysisThresholds] = None):
        """Initialize analyzer with configurable thresholds.

        Args:
            thresholds: Analysis thresholds configuration
        """
        self.thresholds = thresholds or default_thresholds

    @property
    def bloated_page_threshold(self) -> int:
        """Page weight threshold for 'bloated' classification."""
        return self.thresholds.max_page_weight

    @property
    def large_js_threshold(self) -> int:
        """JavaScript size threshold."""
        return self.thresholds.max_js_size

    @property
    def large_css_threshold(self) -> int:
        """CSS size threshold."""
        return self.thresholds.max_css_size

    @property
    def large_image_threshold(self) -> int:
        """Image size threshold."""
        return self.thresholds.max_image_size

    def analyze(self, pages: Dict[str, PageMetadata]) -> ResourceAnalysis:
        """Analyze resource composition across all pages.

        Args:
            pages: Dictionary mapping URLs to PageMetadata

        Returns:
            ResourceAnalysis with site-wide resource metrics
        """
        if not pages:
            return ResourceAnalysis()

        analysis = ResourceAnalysis(total_pages=len(pages))
        page_breakdowns = []

        for url, page in pages.items():
            breakdown = self._analyze_page(url, page)
            page_breakdowns.append(breakdown)

            # Aggregate totals
            analysis.total_html_bytes += breakdown.html_bytes
            analysis.total_css_bytes += breakdown.css_bytes
            analysis.total_js_bytes += breakdown.js_bytes
            analysis.total_image_bytes += breakdown.image_bytes
            analysis.total_font_bytes += breakdown.font_bytes
            analysis.total_other_bytes += breakdown.other_bytes
            analysis.total_all_bytes += breakdown.total_bytes

            # Check for issues using configurable thresholds
            if breakdown.total_bytes > self.bloated_page_threshold:
                analysis.bloated_pages.append({
                    'url': url,
                    'total_bytes': breakdown.total_bytes,
                    'total_mb': round(breakdown.total_bytes / (1024 * 1024), 2)
                })

            if breakdown.js_bytes > self.large_js_threshold:
                analysis.large_js_pages.append({
                    'url': url,
                    'js_bytes': breakdown.js_bytes,
                    'js_kb': round(breakdown.js_bytes / 1024, 1)
                })

            if breakdown.css_bytes > self.large_css_threshold:
                analysis.large_css_pages.append({
                    'url': url,
                    'css_bytes': breakdown.css_bytes,
                    'css_kb': round(breakdown.css_bytes / 1024, 1)
                })

            if breakdown.image_bytes > self.large_image_threshold:
                analysis.large_image_pages.append({
                    'url': url,
                    'image_bytes': breakdown.image_bytes,
                    'image_mb': round(breakdown.image_bytes / (1024 * 1024), 2)
                })

        # Calculate averages using floating-point division
        if analysis.total_pages > 0:
            analysis.avg_page_weight_bytes = int(analysis.total_all_bytes / analysis.total_pages)
            analysis.avg_html_bytes = int(analysis.total_html_bytes / analysis.total_pages)
            analysis.avg_css_bytes = int(analysis.total_css_bytes / analysis.total_pages)
            analysis.avg_js_bytes = int(analysis.total_js_bytes / analysis.total_pages)
            analysis.avg_image_bytes = int(analysis.total_image_bytes / analysis.total_pages)

        # Calculate distribution percentages
        if analysis.total_all_bytes > 0:
            analysis.html_percentage = round(
                analysis.total_html_bytes / analysis.total_all_bytes * 100, 1
            )
            analysis.css_percentage = round(
                analysis.total_css_bytes / analysis.total_all_bytes * 100, 1
            )
            analysis.js_percentage = round(
                analysis.total_js_bytes / analysis.total_all_bytes * 100, 1
            )
            analysis.image_percentage = round(
                analysis.total_image_bytes / analysis.total_all_bytes * 100, 1
            )
            analysis.font_percentage = round(
                analysis.total_font_bytes / analysis.total_all_bytes * 100, 1
            )

        # Sort and get top 10 heaviest pages
        page_breakdowns.sort(key=lambda x: x.total_bytes, reverse=True)
        analysis.heaviest_pages = [
            {
                'url': b.url,
                'total_bytes': b.total_bytes,
                'total_kb': round(b.total_bytes / 1024, 1),
                'html_kb': round(b.html_bytes / 1024, 1),
                'css_kb': round(b.css_bytes / 1024, 1),
                'js_kb': round(b.js_bytes / 1024, 1),
                'image_kb': round(b.image_bytes / 1024, 1),
            }
            for b in page_breakdowns[:10]
        ]

        analysis.page_breakdowns = page_breakdowns

        # Generate recommendations
        analysis.recommendations = self._generate_recommendations(analysis)

        return analysis

    def _analyze_page(self, url: str, page: PageMetadata) -> ResourceBreakdown:
        """Analyze resource breakdown for a single page."""
        breakdown = ResourceBreakdown(
            url=url,
            html_bytes=page.html_size_bytes,
            css_bytes=page.css_size_bytes,
            js_bytes=page.js_size_bytes,
            image_bytes=page.image_size_bytes,
            font_bytes=page.font_size_bytes,
        )

        # Calculate other and total
        known_bytes = (
            breakdown.html_bytes +
            breakdown.css_bytes +
            breakdown.js_bytes +
            breakdown.image_bytes +
            breakdown.font_bytes
        )

        if page.total_page_weight_bytes > known_bytes:
            breakdown.other_bytes = page.total_page_weight_bytes - known_bytes

        breakdown.total_bytes = page.total_page_weight_bytes or known_bytes

        return breakdown

    def _generate_recommendations(self, analysis: ResourceAnalysis) -> List[str]:
        """Generate actionable recommendations based on analysis."""
        recommendations = []

        # Image optimization
        if analysis.image_percentage > 50:
            recommendations.append(
                f"Images account for {analysis.image_percentage}% of page weight. "
                "Consider converting to WebP/AVIF format and implementing lazy loading."
            )

        if analysis.large_image_pages:
            threshold_mb = self.large_image_threshold / (1024 * 1024)
            recommendations.append(
                f"{len(analysis.large_image_pages)} pages have images exceeding {threshold_mb:.1f}MB. "
                "Compress and resize images to appropriate dimensions."
            )

        # JavaScript optimization
        if analysis.js_percentage > 30:
            recommendations.append(
                f"JavaScript accounts for {analysis.js_percentage}% of page weight. "
                "Consider code splitting, tree shaking, and deferring non-critical scripts."
            )

        if analysis.large_js_pages:
            threshold_kb = self.large_js_threshold / 1024
            recommendations.append(
                f"{len(analysis.large_js_pages)} pages have JavaScript bundles exceeding {threshold_kb:.0f}KB. "
                "Audit for unused code and consider dynamic imports."
            )

        # CSS optimization
        if analysis.large_css_pages:
            threshold_kb = self.large_css_threshold / 1024
            recommendations.append(
                f"{len(analysis.large_css_pages)} pages have CSS exceeding {threshold_kb:.0f}KB. "
                "Remove unused CSS and consider critical CSS extraction."
            )

        # Overall page weight
        if analysis.bloated_pages:
            threshold_mb = self.bloated_page_threshold / (1024 * 1024)
            recommendations.append(
                f"{len(analysis.bloated_pages)} pages exceed {threshold_mb:.1f}MB total weight. "
                "These pages will load slowly on mobile connections."
            )

        avg_kb = analysis.avg_page_weight_bytes / 1024
        if avg_kb > 1500:
            recommendations.append(
                f"Average page weight is {avg_kb:.0f}KB, above the recommended 1.5MB. "
                "Focus on reducing the largest resource categories."
            )

        return recommendations
