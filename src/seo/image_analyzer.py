"""Image optimization analyzer for performance improvement."""

from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple

from seo.models import (
    PageMetadata,
    ImageAnalysis,
    ImageIssue,
    EvidenceRecord,
    EvidenceCollection,
    ConfidenceLevel,
    EvidenceSourceType,
)
from seo.config import AnalysisThresholds, default_thresholds
from seo.constants import (
    DEFAULT_LAZY_LOAD_THRESHOLD,
    MAX_IMAGE_SRC_LENGTH,
    IMAGE_EVIDENCE_SAMPLE_LIMIT,
)


class ImageAnalyzer:
    """Analyzes image optimization opportunities.

    Note: Per-image file size analysis requires individual image sizes from
    the crawler. Currently, only aggregate page.image_size_bytes is available.
    When per-image sizes become available, enable LARGE_IMAGE_THRESHOLD checks.
    """

    # Default modern formats (can be overridden via config)
    DEFAULT_MODERN_FORMATS: Set[str] = {'webp', 'avif'}

    # Default formats that can be converted to modern formats
    DEFAULT_CONVERTIBLE_FORMATS: Set[str] = {'png', 'jpg', 'jpeg', 'gif'}

    # Default estimated savings when converting to WebP (percentage)
    DEFAULT_WEBP_SAVINGS_ESTIMATE: float = 0.30  # 30% smaller on average

    # Default threshold for lazy loading (images after this position should be lazy)
    # This is a heuristic assuming first N images are above-the-fold
    DEFAULT_LAZY_LOAD_THRESHOLD: int = DEFAULT_LAZY_LOAD_THRESHOLD

    # Reserved for future use when crawler provides per-image sizes
    # LARGE_IMAGE_THRESHOLD = 200 * 1024  # 200KB

    def __init__(
        self,
        thresholds: Optional[AnalysisThresholds] = None,
        modern_formats: Optional[Set[str]] = None,
        convertible_formats: Optional[Set[str]] = None,
        webp_savings_estimate: Optional[float] = None,
    ):
        """Initialize analyzer with configurable settings.

        Args:
            thresholds: Analysis thresholds configuration
            modern_formats: Set of modern image format extensions
            convertible_formats: Set of formats that can be converted
            webp_savings_estimate: Estimated savings ratio for WebP conversion
        """
        self.thresholds = thresholds or default_thresholds
        self.modern_formats = modern_formats or self.DEFAULT_MODERN_FORMATS
        self.convertible_formats = convertible_formats or self.DEFAULT_CONVERTIBLE_FORMATS
        self.webp_savings_estimate = (
            webp_savings_estimate
            if webp_savings_estimate is not None
            else self.DEFAULT_WEBP_SAVINGS_ESTIMATE
        )
        self.lazy_load_threshold = self.thresholds.lazy_load_threshold
        self._evidence_collection: Optional[EvidenceCollection] = None

    def analyze(self, pages: Dict[str, PageMetadata]) -> Tuple[ImageAnalysis, Dict]:
        """Analyze image optimization opportunities.

        Args:
            pages: Dictionary mapping URLs to PageMetadata

        Returns:
            Tuple of (ImageAnalysis, evidence_dict)
        """
        self._evidence_collection = EvidenceCollection(
            finding='image_optimization',
            component_id='image_analyzer',
        )

        if not pages:
            return ImageAnalysis(), self._evidence_collection.to_dict()

        analysis = ImageAnalysis(total_pages=len(pages))

        format_counts: Dict[str, int] = {}
        all_issues: List[ImageIssue] = []

        # Track issues for evidence (limit samples)
        missing_alt_samples: List[Dict] = []
        missing_dimensions_samples: List[Dict] = []
        format_upgrade_samples: List[Dict] = []

        for url, page in pages.items():
            for idx, img in enumerate(page.images):
                analysis.total_images += 1

                img_src = img.get('src', '')
                img_alt = img.get('alt')

                # Determine format
                img_format = self._get_image_format(img_src)
                format_counts[img_format] = format_counts.get(img_format, 0) + 1

                # Check for modern format conversion opportunity
                if img_format in self.convertible_formats:
                    analysis.images_needing_modern_format.append({
                        'src': img_src[:MAX_IMAGE_SRC_LENGTH],
                        'page': url,
                        'format': img_format
                    })
                    # Sample for evidence
                    if len(format_upgrade_samples) < IMAGE_EVIDENCE_SAMPLE_LIMIT:
                        format_upgrade_samples.append({
                            'src': img_src[:MAX_IMAGE_SRC_LENGTH],
                            'page': url,
                            'current_format': img_format,
                            'recommended': 'webp',
                            'estimated_savings': f'{int(self.webp_savings_estimate * 100)}%',
                        })

                # Check alt text
                if img_alt:
                    analysis.images_with_alt += 1
                else:
                    analysis.images_without_alt += 1
                    # Sample for evidence
                    if len(missing_alt_samples) < IMAGE_EVIDENCE_SAMPLE_LIMIT:
                        missing_alt_samples.append({
                            'src': img_src[:MAX_IMAGE_SRC_LENGTH],
                            'page': url,
                        })

                # Check for dimensions (critical for CLS)
                has_width = 'width' in img or img.get('width')
                has_height = 'height' in img or img.get('height')
                if not has_width and not has_height:
                    analysis.images_missing_dimensions.append({
                        'src': img_src[:MAX_IMAGE_SRC_LENGTH],
                        'page': url
                    })
                    all_issues.append(ImageIssue(
                        url=img_src,
                        page_url=url,
                        issue_type='dimensions',
                        current_value='missing',
                        recommended_value='Add width and height attributes'
                    ))
                    # Sample for evidence
                    if len(missing_dimensions_samples) < IMAGE_EVIDENCE_SAMPLE_LIMIT:
                        missing_dimensions_samples.append({
                            'src': img_src[:MAX_IMAGE_SRC_LENGTH],
                            'page': url,
                        })

            # Aggregate lazy loading stats
            analysis.lazy_loaded_count += page.lazy_images_count
            analysis.eager_loaded_count += page.eager_images_count
            analysis.total_image_bytes += page.image_size_bytes

            # Check for images that should be lazy loaded
            # Heuristic: images after the threshold position are likely below-the-fold
            if page.eager_images_count > self.lazy_load_threshold:
                excess = page.eager_images_count - self.lazy_load_threshold
                analysis.images_needing_lazy_load.append({
                    'page': url,
                    'eager_count': page.eager_images_count,
                    'should_lazy': excess
                })

        # Store format counts
        analysis.format_counts = format_counts

        # Calculate modern format percentage
        modern_count = sum(
            format_counts.get(fmt, 0) for fmt in self.modern_formats
        )
        if analysis.total_images > 0:
            analysis.modern_format_percentage = round(
                modern_count / analysis.total_images * 100, 1
            )
            # Use floating-point division for accuracy
            analysis.avg_image_bytes = int(analysis.total_image_bytes / analysis.total_images)
            analysis.alt_coverage_percentage = round(
                analysis.images_with_alt / analysis.total_images * 100, 1
            )

        # Calculate lazy load percentage
        total_lazy_eager = analysis.lazy_loaded_count + analysis.eager_loaded_count
        if total_lazy_eager > 0:
            analysis.lazy_load_percentage = round(
                analysis.lazy_loaded_count / total_lazy_eager * 100, 1
            )

        # Estimate savings from format conversion
        convertible_count = sum(
            format_counts.get(fmt, 0) for fmt in self.convertible_formats
        )
        if convertible_count > 0 and analysis.total_images > 0:
            convertible_ratio = convertible_count / analysis.total_images
            estimated_convertible_bytes = int(
                analysis.total_image_bytes * convertible_ratio
            )
            analysis.estimated_total_savings_bytes = int(
                estimated_convertible_bytes * self.webp_savings_estimate
            )
            analysis.estimated_savings_percentage = round(
                analysis.estimated_total_savings_bytes / analysis.total_image_bytes * 100, 1
            ) if analysis.total_image_bytes > 0 else 0

        analysis.all_issues = all_issues[:100]  # Limit stored issues

        # Generate recommendations
        analysis.recommendations = self._generate_recommendations(analysis)

        # Add evidence for all findings
        self._add_format_evidence(format_counts, analysis, format_upgrade_samples)
        self._add_alt_text_evidence(analysis, missing_alt_samples)
        self._add_dimensions_evidence(analysis, missing_dimensions_samples)
        self._add_lazy_loading_evidence(analysis)
        self._add_savings_evidence(analysis)
        self._add_summary_evidence(analysis)

        return analysis, self._evidence_collection.to_dict()

    def _get_image_format(self, src: str) -> str:
        """Extract image format from URL.

        Args:
            src: Image source URL

        Returns:
            Detected format extension or 'unknown'
        """
        if not src:
            return 'unknown'

        # Remove query string
        path = src.split('?')[0].lower()

        # Check for common extensions
        for ext in ['webp', 'avif', 'png', 'jpg', 'jpeg', 'gif', 'svg', 'ico', 'jxl']:
            if path.endswith(f'.{ext}'):
                return ext

        # Check for format in URL path (CDN patterns)
        if 'webp' in path:
            return 'webp'
        if 'avif' in path:
            return 'avif'

        return 'unknown'

    def _generate_recommendations(self, analysis: ImageAnalysis) -> List[str]:
        """Generate recommendations based on image analysis.

        Args:
            analysis: Completed ImageAnalysis object

        Returns:
            List of actionable recommendation strings
        """
        recommendations = []

        if analysis.modern_format_percentage < 50:
            savings_pct = int(self.webp_savings_estimate * 100)
            recommendations.append(
                f"Only {analysis.modern_format_percentage}% of images use modern formats. "
                f"Convert PNG/JPEG images to WebP for ~{savings_pct}% size reduction."
            )

        if len(analysis.images_missing_dimensions) > 0:
            count = min(len(analysis.images_missing_dimensions), 100)
            recommendations.append(
                f"{count}+ images lack width/height attributes. "
                "Add explicit dimensions to prevent Cumulative Layout Shift (CLS)."
            )

        if len(analysis.images_needing_lazy_load) > 0:
            total_excess = sum(p['should_lazy'] for p in analysis.images_needing_lazy_load)
            recommendations.append(
                f"Approximately {total_excess} images may benefit from lazy loading "
                f"(estimated as images beyond position {self.lazy_load_threshold} on each page). "
                "Add loading=\"lazy\" to below-the-fold images. "
                "Note: Actual above-the-fold content depends on viewport size."
            )

        if analysis.alt_coverage_percentage < 90:
            recommendations.append(
                f"Alt text coverage is {analysis.alt_coverage_percentage}%. "
                "Add descriptive alt text to all content images for accessibility and SEO."
            )

        if analysis.estimated_total_savings_bytes > 500 * 1024:
            savings_kb = analysis.estimated_total_savings_bytes / 1024
            recommendations.append(
                f"Converting to modern formats could save approximately {savings_kb:.0f}KB "
                f"({analysis.estimated_savings_percentage}% of total image weight). "
                "Actual savings depend on image content and compression settings."
            )

        return recommendations

    def _add_format_evidence(
        self,
        format_counts: Dict[str, int],
        analysis: ImageAnalysis,
        samples: List[Dict],
    ) -> None:
        """Add evidence for image format analysis.

        Args:
            format_counts: Count of images by format
            analysis: The analysis object
            samples: Sample images needing format upgrade
        """
        # Format breakdown evidence
        total = analysis.total_images
        format_breakdown = {
            fmt: {
                'count': count,
                'percentage': round(count / total * 100, 1) if total > 0 else 0,
            }
            for fmt, count in format_counts.items()
        }

        record = EvidenceRecord(
            component_id='image_analyzer',
            finding='format_breakdown',
            evidence_string=f'{analysis.modern_format_percentage}% using modern formats',
            confidence=ConfidenceLevel.HIGH,
            timestamp=datetime.now(),
            source='Image Format Analysis',
            source_type=EvidenceSourceType.MEASUREMENT,
            source_location='aggregate',
            measured_value=format_breakdown,
            ai_generated=False,
            reasoning='Image format distribution across all analyzed pages',
            input_summary={
                'modern_formats': list(self.modern_formats),
                'convertible_formats': list(self.convertible_formats),
                'total_images': total,
            },
        )
        self._evidence_collection.add_record(record)

        # Format upgrade samples
        if samples:
            record = EvidenceRecord(
                component_id='image_analyzer',
                finding='format_upgrade',
                evidence_string=f'{len(analysis.images_needing_modern_format)} images can be converted to WebP',
                confidence=ConfidenceLevel.HIGH,
                timestamp=datetime.now(),
                source='Image Format Analysis',
                source_type=EvidenceSourceType.CALCULATION,
                source_location='aggregate',
                measured_value={
                    'total_needing_upgrade': len(analysis.images_needing_modern_format),
                    'samples': samples,
                },
                ai_generated=False,
                reasoning=f'Images in {", ".join(self.convertible_formats)} formats can be converted to WebP/AVIF',
                input_summary={
                    'estimated_savings_per_image': f'{int(self.webp_savings_estimate * 100)}%',
                    'recommended_format': 'webp',
                },
            )
            self._evidence_collection.add_record(record)

    def _add_alt_text_evidence(
        self,
        analysis: ImageAnalysis,
        samples: List[Dict],
    ) -> None:
        """Add evidence for alt text analysis.

        Args:
            analysis: The analysis object
            samples: Sample images missing alt text
        """
        if analysis.images_without_alt > 0:
            record = EvidenceRecord(
                component_id='image_analyzer',
                finding='missing_alt',
                evidence_string=f'{analysis.images_without_alt} images missing alt text',
                confidence=ConfidenceLevel.HIGH,
                timestamp=datetime.now(),
                source='Image Accessibility Analysis',
                source_type=EvidenceSourceType.MEASUREMENT,
                source_location='aggregate',
                measured_value={
                    'missing_count': analysis.images_without_alt,
                    'coverage_percentage': analysis.alt_coverage_percentage,
                    'samples': samples,
                },
                ai_generated=False,
                reasoning='Alt text is required for accessibility and SEO',
                input_summary={
                    'total_images': analysis.total_images,
                    'with_alt': analysis.images_with_alt,
                    'without_alt': analysis.images_without_alt,
                },
            )
            self._evidence_collection.add_record(record)

    def _add_dimensions_evidence(
        self,
        analysis: ImageAnalysis,
        samples: List[Dict],
    ) -> None:
        """Add evidence for missing dimensions.

        Args:
            analysis: The analysis object
            samples: Sample images missing dimensions
        """
        if len(analysis.images_missing_dimensions) > 0:
            record = EvidenceRecord(
                component_id='image_analyzer',
                finding='missing_dimensions',
                evidence_string=f'{len(analysis.images_missing_dimensions)} images without width/height',
                confidence=ConfidenceLevel.HIGH,
                timestamp=datetime.now(),
                source='Image Layout Analysis',
                source_type=EvidenceSourceType.MEASUREMENT,
                source_location='aggregate',
                measured_value={
                    'count': len(analysis.images_missing_dimensions),
                    'samples': samples,
                    'severity': 'warning',
                },
                ai_generated=False,
                reasoning='Missing dimensions cause Cumulative Layout Shift (CLS) issues',
                input_summary={
                    'cls_risk': 'Images without explicit dimensions cause layout shifts when loaded',
                    'recommendation': 'Add width and height attributes to all <img> tags',
                },
            )
            self._evidence_collection.add_record(record)

    def _add_lazy_loading_evidence(self, analysis: ImageAnalysis) -> None:
        """Add evidence for lazy loading analysis.

        Args:
            analysis: The analysis object
        """
        if len(analysis.images_needing_lazy_load) > 0:
            total_should_lazy = sum(
                p['should_lazy'] for p in analysis.images_needing_lazy_load
            )

            record = EvidenceRecord(
                component_id='image_analyzer',
                finding='missing_lazy_loading',
                evidence_string=f'~{total_should_lazy} below-fold images missing lazy loading',
                confidence=ConfidenceLevel.MEDIUM,  # Heuristic-based
                timestamp=datetime.now(),
                source='Image Loading Analysis',
                source_type=EvidenceSourceType.HEURISTIC,
                source_location='aggregate',
                measured_value={
                    'estimated_count': total_should_lazy,
                    'pages_affected': len(analysis.images_needing_lazy_load),
                    'lazy_loaded_count': analysis.lazy_loaded_count,
                    'eager_loaded_count': analysis.eager_loaded_count,
                },
                ai_generated=False,
                reasoning=f'Images after position {self.lazy_load_threshold} estimated as below-fold',
                input_summary={
                    'lazy_load_threshold': self.lazy_load_threshold,
                    'note': 'Actual above-the-fold content depends on viewport size',
                    'recommendation': 'Add loading="lazy" to below-fold images',
                },
            )
            self._evidence_collection.add_record(record)

    def _add_savings_evidence(self, analysis: ImageAnalysis) -> None:
        """Add evidence for potential savings.

        Args:
            analysis: The analysis object
        """
        if analysis.estimated_total_savings_bytes > 0:
            savings_kb = round(analysis.estimated_total_savings_bytes / 1024, 1)
            total_kb = round(analysis.total_image_bytes / 1024, 1)

            record = EvidenceRecord(
                component_id='image_analyzer',
                finding='potential_savings',
                evidence_string=f'Estimated savings: {savings_kb}KB ({analysis.estimated_savings_percentage}%)',
                confidence=ConfidenceLevel.ESTIMATE,
                timestamp=datetime.now(),
                source='Image Optimization Estimate',
                source_type=EvidenceSourceType.CALCULATION,
                source_location='aggregate',
                measured_value={
                    'potential_savings_kb': savings_kb,
                    'savings_percentage': analysis.estimated_savings_percentage,
                    'total_image_kb': total_kb,
                },
                ai_generated=False,
                reasoning='Estimated savings from converting to modern image formats',
                input_summary={
                    'calculation': 'convertible_bytes * webp_savings_estimate',
                    'webp_savings_estimate': f'{int(self.webp_savings_estimate * 100)}%',
                    'disclaimer': 'Actual savings depend on image content and compression settings',
                },
            )
            self._evidence_collection.add_record(record)

    def _add_summary_evidence(self, analysis: ImageAnalysis) -> None:
        """Add summary evidence for image analysis.

        Args:
            analysis: The analysis object
        """
        record = EvidenceRecord(
            component_id='image_analyzer',
            finding='image_analysis_summary',
            evidence_string=f'{analysis.total_images} images analyzed across {analysis.total_pages} pages',
            confidence=ConfidenceLevel.HIGH,
            timestamp=datetime.now(),
            source='Image Analysis',
            source_type=EvidenceSourceType.CALCULATION,
            source_location='aggregate',
            measured_value={
                'total_images': analysis.total_images,
                'total_pages': analysis.total_pages,
                'modern_format_percentage': analysis.modern_format_percentage,
                'alt_coverage_percentage': analysis.alt_coverage_percentage,
                'lazy_load_percentage': analysis.lazy_load_percentage,
                'issues_found': {
                    'missing_alt': analysis.images_without_alt,
                    'missing_dimensions': len(analysis.images_missing_dimensions),
                    'needing_lazy_load': len(analysis.images_needing_lazy_load),
                    'needing_format_upgrade': len(analysis.images_needing_modern_format),
                },
            },
            ai_generated=False,
            reasoning='Summary of all image optimization findings',
            input_summary={
                'thresholds': {
                    'lazy_load_threshold': self.lazy_load_threshold,
                    'modern_formats': list(self.modern_formats),
                    'convertible_formats': list(self.convertible_formats),
                },
            },
        )
        self._evidence_collection.add_record(record)
