"""Image optimization analyzer for performance improvement."""

from typing import Dict, List, Optional, Set

from seo.models import PageMetadata, ImageAnalysis, ImageIssue
from seo.config import AnalysisThresholds, default_thresholds


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
    DEFAULT_LAZY_LOAD_THRESHOLD: int = 3

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

    def analyze(self, pages: Dict[str, PageMetadata]) -> ImageAnalysis:
        """Analyze image optimization opportunities.

        Args:
            pages: Dictionary mapping URLs to PageMetadata

        Returns:
            ImageAnalysis with optimization metrics
        """
        if not pages:
            return ImageAnalysis()

        analysis = ImageAnalysis(total_pages=len(pages))

        format_counts: Dict[str, int] = {}
        all_issues: List[ImageIssue] = []

        for url, page in pages.items():
            for img in page.images:
                analysis.total_images += 1

                img_src = img.get('src', '')
                img_alt = img.get('alt')

                # Determine format
                img_format = self._get_image_format(img_src)
                format_counts[img_format] = format_counts.get(img_format, 0) + 1

                # Check for modern format conversion opportunity
                if img_format in self.convertible_formats:
                    analysis.images_needing_modern_format.append({
                        'src': img_src[:100],
                        'page': url,
                        'format': img_format
                    })

                # Check alt text
                if img_alt:
                    analysis.images_with_alt += 1
                else:
                    analysis.images_without_alt += 1

                # Check for dimensions (critical for CLS)
                has_width = 'width' in img or img.get('width')
                has_height = 'height' in img or img.get('height')
                if not has_width and not has_height:
                    analysis.images_missing_dimensions.append({
                        'src': img_src[:100],
                        'page': url
                    })
                    all_issues.append(ImageIssue(
                        url=img_src,
                        page_url=url,
                        issue_type='dimensions',
                        current_value='missing',
                        recommended_value='Add width and height attributes'
                    ))

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

        return analysis

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
