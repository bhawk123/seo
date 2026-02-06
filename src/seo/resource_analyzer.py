"""Resource composition analyzer for page weight optimization."""

from datetime import datetime
from typing import Dict, List, Optional, Tuple

from seo.models import (
    PageMetadata,
    ResourceAnalysis,
    ResourceBreakdown,
    EvidenceRecord,
    EvidenceCollection,
    ConfidenceLevel,
    EvidenceSourceType,
)
from seo.config import AnalysisThresholds, default_thresholds


class ResourceAnalyzer:
    """Analyzes page resource composition and identifies optimization opportunities."""

    # Weight distribution thresholds for recommendations
    HIGH_IMAGE_PERCENTAGE = 50.0  # Images > 50% of page weight warrants optimization
    HIGH_JS_PERCENTAGE = 30.0  # JS > 30% of page weight warrants code splitting
    HIGH_AVG_PAGE_KB = 1500  # Average page > 1.5MB is above recommended

    def __init__(self, thresholds: Optional[AnalysisThresholds] = None):
        """Initialize analyzer with configurable thresholds.

        Args:
            thresholds: Analysis thresholds configuration
        """
        self.thresholds = thresholds or default_thresholds
        self._evidence_collection: Optional[EvidenceCollection] = None

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

    def analyze(self, pages: Dict[str, PageMetadata]) -> Tuple[ResourceAnalysis, Dict]:
        """Analyze resource composition across all pages.

        Args:
            pages: Dictionary mapping URLs to PageMetadata

        Returns:
            Tuple of (ResourceAnalysis, evidence_dict)
        """
        self._evidence_collection = EvidenceCollection(
            finding='resource_analysis',
            component_id='resource_analyzer',
        )

        if not pages:
            return ResourceAnalysis(), self._evidence_collection.to_dict()

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

        # Add evidence for resource analysis
        self._add_bloated_page_evidence(analysis)
        self._add_resource_breakdown_evidence(page_breakdowns, analysis)
        self._add_summary_evidence(analysis)

        return analysis, self._evidence_collection.to_dict()

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

    def _add_bloated_page_evidence(self, analysis: ResourceAnalysis) -> None:
        """Add evidence for pages exceeding weight thresholds.

        Args:
            analysis: The analysis object
        """
        # Evidence for bloated pages (total weight)
        for page_info in analysis.bloated_pages:
            record = EvidenceRecord(
                component_id='resource_analyzer',
                finding='bloated_page',
                evidence_string=f'Page weight {page_info["total_mb"]:.2f}MB exceeds threshold',
                confidence=ConfidenceLevel.HIGH,
                timestamp=datetime.now(),
                source='Resource Weight Analysis',
                source_type=EvidenceSourceType.MEASUREMENT,
                source_location=page_info['url'],
                measured_value={
                    'total_bytes': page_info['total_bytes'],
                    'total_mb': page_info['total_mb'],
                    'threshold_bytes': self.bloated_page_threshold,
                    'threshold_mb': round(self.bloated_page_threshold / (1024 * 1024), 2),
                    'overage_bytes': page_info['total_bytes'] - self.bloated_page_threshold,
                },
                ai_generated=False,
                reasoning=f'Page exceeds {self.bloated_page_threshold / (1024 * 1024):.1f}MB threshold',
                input_summary={
                    'impact': 'Slow load on mobile connections',
                    'recommendation': 'Reduce largest resource categories',
                },
            )
            self._evidence_collection.add_record(record)

        # Evidence for large JS bundles
        for page_info in analysis.large_js_pages:
            record = EvidenceRecord(
                component_id='resource_analyzer',
                finding='large_js_bundle',
                evidence_string=f'JavaScript {page_info["js_kb"]:.1f}KB exceeds threshold',
                confidence=ConfidenceLevel.HIGH,
                timestamp=datetime.now(),
                source='JavaScript Size Analysis',
                source_type=EvidenceSourceType.MEASUREMENT,
                source_location=page_info['url'],
                measured_value={
                    'js_bytes': page_info['js_bytes'],
                    'js_kb': page_info['js_kb'],
                    'threshold_bytes': self.large_js_threshold,
                    'threshold_kb': round(self.large_js_threshold / 1024, 1),
                },
                ai_generated=False,
                reasoning=f'JS bundle exceeds {self.large_js_threshold / 1024:.0f}KB threshold',
                input_summary={
                    'recommendation': 'Code splitting, tree shaking, dynamic imports',
                },
            )
            self._evidence_collection.add_record(record)

        # Evidence for large CSS
        for page_info in analysis.large_css_pages:
            record = EvidenceRecord(
                component_id='resource_analyzer',
                finding='large_css',
                evidence_string=f'CSS {page_info["css_kb"]:.1f}KB exceeds threshold',
                confidence=ConfidenceLevel.HIGH,
                timestamp=datetime.now(),
                source='CSS Size Analysis',
                source_type=EvidenceSourceType.MEASUREMENT,
                source_location=page_info['url'],
                measured_value={
                    'css_bytes': page_info['css_bytes'],
                    'css_kb': page_info['css_kb'],
                    'threshold_bytes': self.large_css_threshold,
                    'threshold_kb': round(self.large_css_threshold / 1024, 1),
                },
                ai_generated=False,
                reasoning=f'CSS exceeds {self.large_css_threshold / 1024:.0f}KB threshold',
                input_summary={
                    'recommendation': 'Remove unused CSS, critical CSS extraction',
                },
            )
            self._evidence_collection.add_record(record)

        # Evidence for large images
        for page_info in analysis.large_image_pages:
            record = EvidenceRecord(
                component_id='resource_analyzer',
                finding='large_images',
                evidence_string=f'Images {page_info["image_mb"]:.2f}MB exceed threshold',
                confidence=ConfidenceLevel.HIGH,
                timestamp=datetime.now(),
                source='Image Size Analysis',
                source_type=EvidenceSourceType.MEASUREMENT,
                source_location=page_info['url'],
                measured_value={
                    'image_bytes': page_info['image_bytes'],
                    'image_mb': page_info['image_mb'],
                    'threshold_bytes': self.large_image_threshold,
                    'threshold_mb': round(self.large_image_threshold / (1024 * 1024), 2),
                },
                ai_generated=False,
                reasoning=f'Images exceed {self.large_image_threshold / (1024 * 1024):.1f}MB threshold',
                input_summary={
                    'recommendation': 'Compress, resize, convert to WebP/AVIF',
                },
            )
            self._evidence_collection.add_record(record)

    def _add_resource_breakdown_evidence(
        self,
        page_breakdowns: List[ResourceBreakdown],
        analysis: ResourceAnalysis,
    ) -> None:
        """Add evidence for resource breakdown on heaviest pages.

        Args:
            page_breakdowns: List of per-page breakdowns
            analysis: The analysis object
        """
        # Add detailed evidence for top 5 heaviest pages
        for breakdown in page_breakdowns[:5]:
            # Calculate percentage breakdown for this page
            total = breakdown.total_bytes or 1  # Avoid division by zero
            percentages = {
                'html': round(breakdown.html_bytes / total * 100, 1),
                'css': round(breakdown.css_bytes / total * 100, 1),
                'js': round(breakdown.js_bytes / total * 100, 1),
                'images': round(breakdown.image_bytes / total * 100, 1),
                'fonts': round(breakdown.font_bytes / total * 100, 1),
                'other': round(breakdown.other_bytes / total * 100, 1),
            }

            # Identify dominant resource type
            dominant_type = max(percentages, key=percentages.get)
            dominant_pct = percentages[dominant_type]

            record = EvidenceRecord(
                component_id='resource_analyzer',
                finding='page_resource_breakdown',
                evidence_string=f'{round(breakdown.total_bytes / 1024, 1)}KB total, {dominant_type} dominant ({dominant_pct}%)',
                confidence=ConfidenceLevel.HIGH,
                timestamp=datetime.now(),
                source='Page Weight Breakdown',
                source_type=EvidenceSourceType.MEASUREMENT,
                source_location=breakdown.url,
                measured_value={
                    'total_bytes': breakdown.total_bytes,
                    'total_kb': round(breakdown.total_bytes / 1024, 1),
                    'breakdown_bytes': {
                        'html': breakdown.html_bytes,
                        'css': breakdown.css_bytes,
                        'js': breakdown.js_bytes,
                        'images': breakdown.image_bytes,
                        'fonts': breakdown.font_bytes,
                        'other': breakdown.other_bytes,
                    },
                    'breakdown_kb': {
                        'html': round(breakdown.html_bytes / 1024, 1),
                        'css': round(breakdown.css_bytes / 1024, 1),
                        'js': round(breakdown.js_bytes / 1024, 1),
                        'images': round(breakdown.image_bytes / 1024, 1),
                        'fonts': round(breakdown.font_bytes / 1024, 1),
                        'other': round(breakdown.other_bytes / 1024, 1),
                    },
                    'percentage_breakdown': percentages,
                    'dominant_resource': dominant_type,
                    'dominant_percentage': dominant_pct,
                },
                ai_generated=False,
                reasoning=f'Detailed breakdown showing {dominant_type} as largest resource type',
            )
            self._evidence_collection.add_record(record)

    def _add_summary_evidence(self, analysis: ResourceAnalysis) -> None:
        """Add summary evidence for overall resource analysis.

        Args:
            analysis: The completed analysis object
        """
        # Calculate issue counts
        issue_summary = {
            'bloated_pages': len(analysis.bloated_pages),
            'large_js_pages': len(analysis.large_js_pages),
            'large_css_pages': len(analysis.large_css_pages),
            'large_image_pages': len(analysis.large_image_pages),
        }
        total_issues = sum(issue_summary.values())

        record = EvidenceRecord(
            component_id='resource_analyzer',
            finding='resource_summary',
            evidence_string=f'{analysis.total_pages} pages analyzed, avg {round(analysis.avg_page_weight_bytes / 1024, 1)}KB, {total_issues} threshold violations',
            confidence=ConfidenceLevel.HIGH,
            timestamp=datetime.now(),
            source='Resource Composition Analysis',
            source_type=EvidenceSourceType.CALCULATION,
            source_location='aggregate',
            measured_value={
                'total_pages': analysis.total_pages,
                'total_weight_bytes': analysis.total_all_bytes,
                'total_weight_mb': round(analysis.total_all_bytes / (1024 * 1024), 2),
                'averages': {
                    'page_weight_bytes': analysis.avg_page_weight_bytes,
                    'page_weight_kb': round(analysis.avg_page_weight_bytes / 1024, 1),
                    'html_bytes': analysis.avg_html_bytes,
                    'css_bytes': analysis.avg_css_bytes,
                    'js_bytes': analysis.avg_js_bytes,
                    'image_bytes': analysis.avg_image_bytes,
                },
                'distribution_percentages': {
                    'html': analysis.html_percentage,
                    'css': analysis.css_percentage,
                    'js': analysis.js_percentage,
                    'images': analysis.image_percentage,
                    'fonts': analysis.font_percentage,
                },
                'issue_counts': issue_summary,
                'total_threshold_violations': total_issues,
            },
            ai_generated=False,
            reasoning='Aggregate resource composition across all pages',
            input_summary={
                'thresholds': {
                    'bloated_page_bytes': self.bloated_page_threshold,
                    'large_js_bytes': self.large_js_threshold,
                    'large_css_bytes': self.large_css_threshold,
                    'large_image_bytes': self.large_image_threshold,
                },
                'warning_percentages': {
                    'high_image_pct': self.HIGH_IMAGE_PERCENTAGE,
                    'high_js_pct': self.HIGH_JS_PERCENTAGE,
                    'high_avg_page_kb': self.HIGH_AVG_PAGE_KB,
                },
            },
        )
        self._evidence_collection.add_record(record)

        # Add distribution warning evidence if thresholds exceeded
        if analysis.image_percentage > self.HIGH_IMAGE_PERCENTAGE:
            record = EvidenceRecord(
                component_id='resource_analyzer',
                finding='high_image_percentage',
                evidence_string=f'Images account for {analysis.image_percentage}% of page weight',
                confidence=ConfidenceLevel.HIGH,
                timestamp=datetime.now(),
                source='Resource Distribution Analysis',
                source_type=EvidenceSourceType.CALCULATION,
                source_location='aggregate',
                measured_value={
                    'percentage': analysis.image_percentage,
                    'threshold': self.HIGH_IMAGE_PERCENTAGE,
                    'total_image_bytes': analysis.total_image_bytes,
                    'total_image_mb': round(analysis.total_image_bytes / (1024 * 1024), 2),
                },
                ai_generated=False,
                reasoning=f'Images exceed {self.HIGH_IMAGE_PERCENTAGE}% of total weight',
                input_summary={
                    'recommendation': 'Convert to WebP/AVIF, implement lazy loading',
                },
            )
            self._evidence_collection.add_record(record)

        if analysis.js_percentage > self.HIGH_JS_PERCENTAGE:
            record = EvidenceRecord(
                component_id='resource_analyzer',
                finding='high_js_percentage',
                evidence_string=f'JavaScript accounts for {analysis.js_percentage}% of page weight',
                confidence=ConfidenceLevel.HIGH,
                timestamp=datetime.now(),
                source='Resource Distribution Analysis',
                source_type=EvidenceSourceType.CALCULATION,
                source_location='aggregate',
                measured_value={
                    'percentage': analysis.js_percentage,
                    'threshold': self.HIGH_JS_PERCENTAGE,
                    'total_js_bytes': analysis.total_js_bytes,
                    'total_js_kb': round(analysis.total_js_bytes / 1024, 1),
                },
                ai_generated=False,
                reasoning=f'JavaScript exceeds {self.HIGH_JS_PERCENTAGE}% of total weight',
                input_summary={
                    'recommendation': 'Code splitting, tree shaking, defer non-critical scripts',
                },
            )
            self._evidence_collection.add_record(record)

        avg_kb = analysis.avg_page_weight_bytes / 1024
        if avg_kb > self.HIGH_AVG_PAGE_KB:
            record = EvidenceRecord(
                component_id='resource_analyzer',
                finding='high_average_page_weight',
                evidence_string=f'Average page weight {avg_kb:.0f}KB exceeds {self.HIGH_AVG_PAGE_KB}KB',
                confidence=ConfidenceLevel.HIGH,
                timestamp=datetime.now(),
                source='Resource Weight Analysis',
                source_type=EvidenceSourceType.CALCULATION,
                source_location='aggregate',
                measured_value={
                    'avg_page_kb': round(avg_kb, 1),
                    'threshold_kb': self.HIGH_AVG_PAGE_KB,
                    'overage_kb': round(avg_kb - self.HIGH_AVG_PAGE_KB, 1),
                },
                ai_generated=False,
                reasoning=f'Average weight above recommended {self.HIGH_AVG_PAGE_KB}KB',
                input_summary={
                    'recommendation': 'Focus on reducing largest resource categories',
                },
            )
            self._evidence_collection.add_record(record)
