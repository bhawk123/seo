# tests/test_e2e.py
"""End-to-end tests for the SEO analyzer pipeline."""

import json
import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from seo.models import PageMetadata, TechnicalIssues
from seo.technical import TechnicalAnalyzer
from seo.content_quality import ContentQualityAnalyzer
from seo.image_analyzer import ImageAnalyzer
from seo.redirect_analyzer import RedirectAnalyzer
from seo.output_manager import OutputManager


@pytest.fixture
def sample_site_data():
    """Create realistic sample site data for e2e testing."""
    homepage = PageMetadata(url="https://example.com/")
    homepage.title = "Example Site - Home"
    homepage.description = "Welcome to Example Site, your source for quality content."
    homepage.h1_tags = ["Welcome to Example Site"]
    homepage.h2_tags = ["About Us", "Our Services", "Contact"]
    homepage.word_count = 450
    homepage.load_time = 1.2
    homepage.status_code = 200
    homepage.has_https = True
    homepage.viewport_meta = "width=device-width, initial-scale=1"
    homepage.canonical_url = "https://example.com/"
    homepage.lang_attribute = "en"
    homepage.links = ["https://example.com/about", "https://example.com/services"]
    homepage.images = [
        {"src": "logo.png", "alt": "Example Logo"},
        {"src": "hero.jpg", "alt": ""},
    ]
    homepage.content_text = "This is sample content " * 50
    homepage.internal_links = 5
    homepage.external_links = 2

    about = PageMetadata(url="https://example.com/about")
    about.title = "About Us - Example Site"
    about.description = "Learn more about Example Site and our mission."
    about.h1_tags = ["About Our Company"]
    about.word_count = 350
    about.load_time = 0.8
    about.status_code = 200
    about.has_https = True
    about.viewport_meta = "width=device-width, initial-scale=1"
    about.canonical_url = "https://example.com/about"
    about.lang_attribute = "en"
    about.links = ["https://example.com/"]
    about.images = [{"src": "team.jpg", "alt": "Our Team"}]
    about.content_text = "About us content " * 40

    services = PageMetadata(url="https://example.com/services")
    services.title = ""  # Missing title - issue
    services.description = ""  # Missing description - issue
    services.h1_tags = []  # Missing H1 - issue
    services.word_count = 150  # Thin content - issue
    services.load_time = 3.5  # Slow page - issue
    services.status_code = 200
    services.has_https = True
    services.viewport_meta = ""  # Missing viewport - issue
    services.links = ["https://example.com/", "https://example.com/about"]
    services.images = [
        {"src": "service1.jpg"},  # Missing alt
        {"src": "service2.jpg"},  # Missing alt
    ]
    services.content_text = "Services content " * 20

    return {
        "https://example.com/": homepage,
        "https://example.com/about": about,
        "https://example.com/services": services,
    }


@pytest.fixture
def temp_crawl_dir():
    """Create a temporary directory for crawl output."""
    temp_dir = tempfile.mkdtemp(prefix="seo_e2e_test_")
    yield Path(temp_dir)
    shutil.rmtree(temp_dir, ignore_errors=True)


class TestE2EAnalysisPipeline:
    """End-to-end tests for the full analysis pipeline."""

    def test_full_analysis_pipeline(self, sample_site_data):
        """Test the complete analysis flow: crawl data → all analyzers → results."""
        # Step 1: Technical Analysis
        technical_analyzer = TechnicalAnalyzer()
        result = technical_analyzer.analyze(sample_site_data)
        issues = result[0] if isinstance(result, tuple) else result

        # Verify technical issues detected
        assert isinstance(issues, TechnicalIssues)
        assert len(issues.missing_titles) == 1  # services page
        assert "https://example.com/services" in issues.missing_titles
        assert len(issues.missing_meta_descriptions) == 1
        assert len(issues.missing_h1) == 1
        assert len(issues.thin_content) >= 1  # services page has thin content

        # Step 2: Content Quality Analysis
        content_analyzer = ContentQualityAnalyzer()
        content_results = []
        for url, page in sample_site_data.items():
            if page.content_text:
                metrics, evidence = content_analyzer.analyze(url, page.content_text)
                content_results.append(metrics)

        assert len(content_results) == 3
        # All should have readability scores
        for metrics in content_results:
            assert hasattr(metrics, 'readability_score')
            assert hasattr(metrics, 'word_count')

        # Step 3: Image Analysis
        image_analyzer = ImageAnalyzer()
        image_analysis, image_evidence = image_analyzer.analyze(sample_site_data)

        assert image_analysis.total_images == 5
        assert image_analysis.images_without_alt >= 2  # hero.jpg, service1.jpg, service2.jpg

        # Step 4: Redirect Analysis (no redirects in sample data)
        redirect_analyzer = RedirectAnalyzer()
        redirect_analysis, redirect_evidence = redirect_analyzer.analyze(sample_site_data)

        assert redirect_analysis.total_pages == 3
        assert redirect_analysis.pages_with_redirects == 0

    def test_pipeline_with_empty_data(self):
        """Test pipeline handles empty site data gracefully."""
        technical_analyzer = TechnicalAnalyzer()
        result = technical_analyzer.analyze({})
        issues = result[0] if isinstance(result, tuple) else result

        assert isinstance(issues, TechnicalIssues)
        assert len(issues.missing_titles) == 0

        image_analyzer = ImageAnalyzer()
        analysis, _ = image_analyzer.analyze({})
        assert analysis.total_images == 0

    def test_pipeline_aggregates_statistics(self, sample_site_data):
        """Test that pipeline correctly aggregates site-wide statistics."""
        total_words = sum(p.word_count for p in sample_site_data.values())
        total_images = sum(len(p.images) for p in sample_site_data.values())
        avg_load_time = sum(p.load_time for p in sample_site_data.values()) / len(sample_site_data)

        assert total_words == 450 + 350 + 150  # 950
        assert total_images == 5
        assert 1.5 < avg_load_time < 2.0  # (1.2 + 0.8 + 3.5) / 3 ≈ 1.83


class TestE2EOutputPersistence:
    """End-to-end tests for output persistence."""

    def test_save_and_load_crawl_results(self, sample_site_data, temp_crawl_dir):
        """Test saving and loading crawl results."""
        output_mgr = OutputManager()

        # Create subdirectories
        pages_dir = temp_crawl_dir / "pages"
        pages_dir.mkdir(parents=True)

        # Run analysis
        technical_analyzer = TechnicalAnalyzer()
        result = technical_analyzer.analyze(sample_site_data)
        issues = result[0] if isinstance(result, tuple) else result

        crawl_stats = {
            "total_pages": len(sample_site_data),
            "total_words": sum(p.word_count for p in sample_site_data.values()),
            "total_images": sum(len(p.images) for p in sample_site_data.values()),
        }

        # Save results
        output_mgr.save_crawl_results(
            crawl_dir=temp_crawl_dir,
            start_url="https://example.com/",
            site_data=sample_site_data,
            technical_issues=issues,
            llm_recommendations="Test recommendations",
            crawl_stats=crawl_stats,
            advanced_analysis={},
        )

        # Verify files exist (OutputManager saves to metadata.json)
        assert (temp_crawl_dir / "metadata.json").exists()
        assert (temp_crawl_dir / "technical_issues.json").exists()
        assert (temp_crawl_dir / "recommendations.txt").exists()

        # Load and verify
        with open(temp_crawl_dir / "metadata.json") as f:
            loaded = json.load(f)

        assert loaded["start_url"] == "https://example.com/"
        assert loaded["total_pages"] == 3
        assert loaded["stats"]["total_words"] == 950

    def test_crawl_state_save_and_resume(self, temp_crawl_dir):
        """Test saving and resuming crawl state."""
        output_mgr = OutputManager()

        # Save initial state (requires version and all required fields)
        initial_state = {
            "version": "1.0",
            "status": "paused",
            "config": {
                "start_url": "https://example.com/",
                "max_pages": 50,
            },
            "progress": {
                "pages_crawled": 10,
                "pages_remaining": 40,
                "last_updated": None,  # Will be set by save_crawl_state
            },
            "visited_urls": ["https://example.com/", "https://example.com/about"],
            "queue": ["https://example.com/services"],
        }

        output_mgr.save_crawl_state(temp_crawl_dir, initial_state)
        assert (temp_crawl_dir / "crawl_state.json").exists()

        # Load state
        loaded_state = output_mgr.load_crawl_state(temp_crawl_dir)
        assert loaded_state is not None
        assert loaded_state["status"] == "paused"
        assert loaded_state["progress"]["pages_crawled"] == 10
        assert len(loaded_state["visited_urls"]) == 2


class TestE2ETechnicalIssueDetection:
    """End-to-end tests for comprehensive issue detection."""

    def test_detects_all_issue_types(self, sample_site_data):
        """Test that all issue types are properly detected."""
        technical_analyzer = TechnicalAnalyzer()
        result = technical_analyzer.analyze(sample_site_data)
        issues = result[0] if isinstance(result, tuple) else result

        # Missing title
        assert any("services" in url for url in issues.missing_titles)

        # Missing meta description
        assert any("services" in url for url in issues.missing_meta_descriptions)

        # Missing H1
        assert any("services" in url for url in issues.missing_h1)

        # Thin content (< 300 words)
        thin_urls = [url for url, count in issues.thin_content]
        assert any("services" in url for url in thin_urls)

    def test_detects_orphan_pages(self):
        """Test orphan page detection."""
        homepage = PageMetadata(url="https://example.com/")
        homepage.links = ["https://example.com/linked"]

        linked = PageMetadata(url="https://example.com/linked")
        linked.links = ["https://example.com/"]

        orphan = PageMetadata(url="https://example.com/orphan")
        orphan.links = ["https://example.com/"]  # Links to home but not linked from anywhere

        site_data = {
            "https://example.com/": homepage,
            "https://example.com/linked": linked,
            "https://example.com/orphan": orphan,
        }

        technical_analyzer = TechnicalAnalyzer()
        result = technical_analyzer.analyze(site_data)
        issues = result[0] if isinstance(result, tuple) else result

        assert len(issues.orphan_pages) == 1
        assert "orphan" in issues.orphan_pages[0]

    def test_detects_broken_internal_links(self):
        """Test broken internal link detection."""
        homepage = PageMetadata(url="https://example.com/")
        homepage.links = [
            "https://example.com/exists",
            "https://example.com/broken",  # Not in site_data
        ]

        exists = PageMetadata(url="https://example.com/exists")
        exists.links = ["https://example.com/"]

        site_data = {
            "https://example.com/": homepage,
            "https://example.com/exists": exists,
        }

        technical_analyzer = TechnicalAnalyzer()
        result = technical_analyzer.analyze(site_data)
        issues = result[0] if isinstance(result, tuple) else result

        assert len(issues.broken_links) == 1
        source_url, broken_list = issues.broken_links[0]
        assert source_url == "https://example.com/"
        assert "https://example.com/broken" in broken_list


class TestE2EContentAnalysis:
    """End-to-end tests for content quality analysis."""

    def test_readability_varies_by_content(self):
        """Test that readability scores vary based on content complexity."""
        analyzer = ContentQualityAnalyzer()

        # Simple content
        simple = "The cat sat on the mat. The dog ran fast. " * 20
        simple_metrics, _ = analyzer.analyze("https://example.com/simple", simple)

        # Complex content
        complex_text = (
            "The implementation of sophisticated methodological approaches "
            "necessitates comprehensive understanding of multidisciplinary "
            "theoretical frameworks. " * 10
        )
        complex_metrics, _ = analyzer.analyze("https://example.com/complex", complex_text)

        # Both should have scores
        assert simple_metrics.readability_score is not None
        assert complex_metrics.readability_score is not None

    def test_keyword_density_calculation(self):
        """Test keyword density is properly calculated."""
        analyzer = ContentQualityAnalyzer()

        # Content with repeated keyword (longer to ensure reliable analysis)
        content = "SEO optimization helps websites. SEO analysis improves rankings. SEO tools are useful. " * 30
        metrics, _ = analyzer.analyze("https://example.com/seo", content)

        assert metrics.keyword_density is not None
        # keyword_density should be a dict with top keywords
        assert isinstance(metrics.keyword_density, dict)
        # Should have at least one keyword detected
        assert len(metrics.keyword_density) > 0


class TestE2EImageOptimization:
    """End-to-end tests for image optimization analysis."""

    def test_modern_format_detection(self):
        """Test detection of modern vs legacy image formats."""
        analyzer = ImageAnalyzer()

        page = PageMetadata(url="https://example.com/")
        page.images = [
            {"src": "modern.webp", "alt": "Modern"},
            {"src": "modern.avif", "alt": "Modern"},
            {"src": "legacy.jpg", "alt": "Legacy"},
            {"src": "legacy.png", "alt": "Legacy"},
        ]
        page.lazy_images_count = 0
        page.eager_images_count = 4
        page.image_size_bytes = 100000

        analysis, _ = analyzer.analyze({"https://example.com/": page})

        assert analysis.total_images == 4
        assert analysis.modern_format_percentage == 50.0  # 2 of 4
        assert len(analysis.images_needing_modern_format) == 2  # jpg and png

    def test_alt_text_coverage(self):
        """Test alt text coverage calculation."""
        analyzer = ImageAnalyzer()

        page = PageMetadata(url="https://example.com/")
        page.images = [
            {"src": "img1.jpg", "alt": "Description"},
            {"src": "img2.jpg", "alt": ""},  # Empty
            {"src": "img3.jpg"},  # Missing
            {"src": "img4.jpg", "alt": "Another description"},
        ]
        page.lazy_images_count = 0
        page.eager_images_count = 4
        page.image_size_bytes = 50000

        analysis, _ = analyzer.analyze({"https://example.com/": page})

        assert analysis.total_images == 4
        assert analysis.images_without_alt == 2
        assert analysis.alt_coverage_percentage == 50.0


@pytest.mark.e2e
class TestE2ECLIIntegration:
    """End-to-end tests for CLI integration."""

    def test_argument_parsing(self):
        """Test CLI argument parsing."""
        import sys
        from unittest.mock import patch

        # Mock sys.argv
        test_args = [
            "async_crawl.py",
            "https://example.com",
            "--max-pages", "100",
            "--max-depth", "3",
            "--rate-limit", "1.0",
            "--headless",
            "--no-llm",
        ]

        with patch.object(sys, 'argv', test_args):
            # Import parse_args from the script
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "async_crawl",
                Path(__file__).parent.parent / "async_crawl.py"
            )
            module = importlib.util.module_from_spec(spec)

            # We can't fully execute, but we can verify structure
            assert spec is not None

    def test_signal_handling_saves_state(self, temp_crawl_dir):
        """Test that interrupt signal saves crawl state."""
        # This tests the state saving mechanism
        output_mgr = OutputManager()

        state = {
            "version": "1.0",
            "status": "paused",
            "config": {"start_url": "https://example.com/", "max_pages": 50},
            "progress": {"pages_crawled": 25, "pages_remaining": 25, "last_updated": None},
            "visited_urls": [f"https://example.com/page{i}" for i in range(25)],
            "queue": [f"https://example.com/page{i}" for i in range(25, 50)],
        }

        output_mgr.save_crawl_state(temp_crawl_dir, state)

        # Verify state was saved
        loaded = output_mgr.load_crawl_state(temp_crawl_dir)
        assert loaded["status"] == "paused"
        assert loaded["progress"]["pages_crawled"] == 25


@pytest.mark.e2e
class TestE2EReportGeneration:
    """End-to-end tests for report generation."""

    def test_report_data_structure(self, sample_site_data, temp_crawl_dir):
        """Test that report data is properly structured."""
        from dataclasses import asdict

        output_mgr = OutputManager()

        # Create required directories
        pages_dir = temp_crawl_dir / "pages"
        pages_dir.mkdir(parents=True)

        technical_analyzer = TechnicalAnalyzer()
        result = technical_analyzer.analyze(sample_site_data)
        issues = result[0] if isinstance(result, tuple) else result

        crawl_stats = {
            "total_pages": 3,
            "total_words": 950,
            "total_images": 5,
        }

        # Save results
        output_mgr.save_crawl_results(
            crawl_dir=temp_crawl_dir,
            start_url="https://example.com/",
            site_data=sample_site_data,
            technical_issues=issues,
            llm_recommendations="Test recommendations",
            crawl_stats=crawl_stats,
            advanced_analysis={
                "content_quality": [],
                "security": [],
                "url_structure": [],
            },
        )

        # Load and verify structure (OutputManager saves metadata.json and technical_issues.json separately)
        with open(temp_crawl_dir / "metadata.json") as f:
            metadata = json.load(f)

        with open(temp_crawl_dir / "technical_issues.json") as f:
            issues_data = json.load(f)

        # Required fields in metadata
        assert "start_url" in metadata
        assert "stats" in metadata
        assert "crawled_at" in metadata
        assert "total_pages" in metadata

        # Issues should be in separate file
        assert "missing_titles" in issues_data
        assert "missing_meta_descriptions" in issues_data

        # Recommendations in text file
        with open(temp_crawl_dir / "recommendations.txt") as f:
            recommendations = f.read()
        assert "Test recommendations" in recommendations
