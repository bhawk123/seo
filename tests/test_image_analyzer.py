# tests/test_image_analyzer.py
"""Tests for the image optimization analyzer."""

import pytest
from seo.image_analyzer import ImageAnalyzer
from seo.models import PageMetadata
from seo.constants import (
    DEFAULT_LAZY_LOAD_THRESHOLD,
    IMAGE_EVIDENCE_SAMPLE_LIMIT,
    MAX_IMAGE_SRC_LENGTH,
)


class TestImageAnalyzer:
    """Test suite for ImageAnalyzer."""

    @pytest.fixture
    def analyzer(self):
        """Create an ImageAnalyzer instance."""
        return ImageAnalyzer()

    @pytest.fixture
    def sample_pages(self):
        """Create sample page data for testing."""
        page1 = PageMetadata(url="https://example.com/page1")
        page1.images = [
            {"src": "image1.jpg", "alt": "Image 1"},
            {"src": "image2.png", "alt": ""},  # Missing alt
            {"src": "image3.webp", "alt": "Image 3"},
            {"src": "image4.jpg"},  # No alt key
        ]
        page1.lazy_images_count = 1
        page1.eager_images_count = 3
        page1.image_size_bytes = 500000

        page2 = PageMetadata(url="https://example.com/page2")
        page2.images = [
            {"src": "hero.jpg", "alt": "Hero"},
            {"src": "logo.png", "alt": "Logo", "width": "100", "height": "50"},
        ]
        page2.lazy_images_count = 0
        page2.eager_images_count = 2
        page2.image_size_bytes = 200000

        return {
            "https://example.com/page1": page1,
            "https://example.com/page2": page2,
        }

    def test_analyzer_initialization(self, analyzer):
        """Test that the analyzer initializes with correct defaults."""
        assert analyzer.DEFAULT_LAZY_LOAD_THRESHOLD == DEFAULT_LAZY_LOAD_THRESHOLD
        assert 'webp' in analyzer.modern_formats
        assert 'avif' in analyzer.modern_formats
        assert 'jpg' in analyzer.convertible_formats
        assert 'png' in analyzer.convertible_formats

    def test_analyze_empty_pages(self, analyzer):
        """Test analysis with empty pages dict."""
        analysis, evidence = analyzer.analyze({})

        assert analysis.total_images == 0
        assert analysis.total_pages == 0
        assert isinstance(evidence, dict)

    def test_analyze_counts_images(self, analyzer, sample_pages):
        """Test that analyzer correctly counts total images."""
        analysis, _ = analyzer.analyze(sample_pages)

        assert analysis.total_images == 6  # 4 + 2 images
        assert analysis.total_pages == 2

    def test_analyze_detects_missing_alt(self, analyzer, sample_pages):
        """Test detection of images without alt text."""
        analysis, _ = analyzer.analyze(sample_pages)

        # page1 has 2 images without alt (one with empty alt, one without key)
        assert analysis.images_without_alt >= 2

    def test_analyze_detects_modern_format_needs(self, analyzer, sample_pages):
        """Test detection of images needing modern format conversion."""
        analysis, _ = analyzer.analyze(sample_pages)

        # jpg and png images can be converted to webp
        assert len(analysis.images_needing_modern_format) > 0

    def test_analyze_detects_missing_dimensions(self, analyzer, sample_pages):
        """Test detection of images without dimensions."""
        analysis, _ = analyzer.analyze(sample_pages)

        # Most images in sample data don't have width/height
        assert len(analysis.images_missing_dimensions) > 0

    def test_get_image_format(self, analyzer):
        """Test image format detection from URL."""
        assert analyzer._get_image_format("image.jpg") == "jpg"
        assert analyzer._get_image_format("image.jpeg") == "jpeg"
        assert analyzer._get_image_format("image.png") == "png"
        assert analyzer._get_image_format("image.webp") == "webp"
        assert analyzer._get_image_format("image.avif") == "avif"
        assert analyzer._get_image_format("image.gif") == "gif"
        assert analyzer._get_image_format("image.svg") == "svg"

    def test_get_image_format_with_query_string(self, analyzer):
        """Test format detection strips query strings."""
        assert analyzer._get_image_format("image.jpg?v=123") == "jpg"
        assert analyzer._get_image_format("image.png?size=large") == "png"

    def test_get_image_format_cdn_patterns(self, analyzer):
        """Test format detection for CDN URL patterns."""
        assert analyzer._get_image_format("/cdn/images/webp/hero") == "webp"
        assert analyzer._get_image_format("/images/avif/banner") == "avif"

    def test_get_image_format_unknown(self, analyzer):
        """Test format detection returns unknown for unrecognized formats."""
        assert analyzer._get_image_format("") == "unknown"
        assert analyzer._get_image_format("/image") == "unknown"

    def test_modern_format_percentage(self, analyzer):
        """Test calculation of modern format percentage."""
        page = PageMetadata(url="https://example.com")
        page.images = [
            {"src": "image1.webp", "alt": "Modern"},
            {"src": "image2.avif", "alt": "Modern"},
            {"src": "image3.jpg", "alt": "Legacy"},
            {"src": "image4.png", "alt": "Legacy"},
        ]
        page.lazy_images_count = 0
        page.eager_images_count = 4
        page.image_size_bytes = 100000

        analysis, _ = analyzer.analyze({"https://example.com": page})

        # 2 modern (webp, avif) out of 4 = 50%
        assert analysis.modern_format_percentage == 50.0

    def test_alt_coverage_percentage(self, analyzer):
        """Test calculation of alt text coverage percentage."""
        page = PageMetadata(url="https://example.com")
        page.images = [
            {"src": "img1.jpg", "alt": "Has alt"},
            {"src": "img2.jpg", "alt": "Has alt"},
            {"src": "img3.jpg", "alt": ""},  # Empty alt
            {"src": "img4.jpg"},  # No alt
        ]
        page.lazy_images_count = 0
        page.eager_images_count = 4
        page.image_size_bytes = 50000

        analysis, _ = analyzer.analyze({"https://example.com": page})

        # 2 with alt out of 4 = 50%
        assert analysis.alt_coverage_percentage == 50.0

    def test_lazy_load_detection(self, analyzer):
        """Test detection of images needing lazy loading."""
        page = PageMetadata(url="https://example.com")
        page.images = [{"src": f"img{i}.jpg", "alt": f"Image {i}"} for i in range(10)]
        page.lazy_images_count = 0
        page.eager_images_count = 10  # All eager
        page.image_size_bytes = 500000

        analysis, _ = analyzer.analyze({"https://example.com": page})

        # Should detect that images beyond threshold should be lazy loaded
        assert len(analysis.images_needing_lazy_load) > 0

    def test_estimated_savings(self, analyzer):
        """Test estimation of savings from format conversion."""
        page = PageMetadata(url="https://example.com")
        page.images = [
            {"src": "large1.jpg", "alt": "Large"},
            {"src": "large2.png", "alt": "Large"},
        ]
        page.lazy_images_count = 0
        page.eager_images_count = 2
        page.image_size_bytes = 1000000  # 1MB

        analysis, _ = analyzer.analyze({"https://example.com": page})

        # Should estimate savings (30% of convertible images)
        assert analysis.estimated_total_savings_bytes > 0

    def test_generates_recommendations(self, analyzer, sample_pages):
        """Test that recommendations are generated."""
        analysis, _ = analyzer.analyze(sample_pages)

        # Should have recommendations for missing alt, format conversion, etc.
        assert len(analysis.recommendations) > 0

    def test_evidence_collection(self, analyzer, sample_pages):
        """Test that evidence is collected and returned."""
        analysis, evidence = analyzer.analyze(sample_pages)

        assert evidence is not None
        assert isinstance(evidence, dict)
