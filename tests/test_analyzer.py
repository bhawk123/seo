"""Tests for SEO analyzer."""

import pytest
from unittest.mock import Mock, patch
from seo.analyzer import SEOAnalyzer
from seo.models import CrawlResult, PageMetadata, SEOScore
from seo.technical import TechnicalAnalyzer


class TestSEOAnalyzer:
    """Test cases for SEOAnalyzer."""

    @patch("seo.analyzer.LLMClient")
    def test_analyzer_initialization(self, mock_llm):
        """Test analyzer can be initialized."""
        analyzer = SEOAnalyzer(llm_api_key="test-key")
        assert analyzer.crawler is not None
        assert analyzer.llm is not None

    @patch("seo.analyzer.LLMClient")
    @patch("seo.analyzer.WebCrawler")
    def test_analyze_url_success(self, mock_crawler_class, mock_llm_class):
        """Test successful URL analysis."""
        mock_crawl_result = CrawlResult(
            url="https://example.com",
            metadata=PageMetadata(
                url="https://example.com",
                title="Test Page",
                description="Test description",
                word_count=500,
            ),
            html="<html><body>Test content</body></html>",
            success=True,
        )

        mock_crawler = Mock()
        mock_crawler.crawl.return_value = mock_crawl_result
        mock_crawler_class.return_value = mock_crawler

        mock_llm = Mock()
        mock_llm.analyze_seo.return_value = {
            "overall_score": 85,
            "title_score": 90,
            "description_score": 80,
            "content_score": 85,
            "technical_score": 90,
            "strengths": ["Good title", "Clear content"],
            "weaknesses": ["Could improve meta description"],
            "recommendations": ["Add more keywords"],
        }
        mock_llm_class.return_value = mock_llm

        analyzer = SEOAnalyzer(llm_api_key="test-key")
        analyzer.llm = mock_llm
        analyzer.crawler = mock_crawler

        crawl_result, seo_score = analyzer.analyze_url(
            "https://example.com"
        )

        assert crawl_result.success is True
        assert seo_score is not None
        assert seo_score.overall_score == 85
        assert len(seo_score.recommendations) > 0

    @patch("seo.analyzer.LLMClient")
    @patch("seo.analyzer.WebCrawler")
    def test_analyze_url_crawl_failure(
        self, mock_crawler_class, mock_llm_class
    ):
        """Test URL analysis when crawling fails."""
        mock_crawl_result = CrawlResult(
            url="https://example.com",
            metadata=PageMetadata(url="https://example.com"),
            html="",
            success=False,
            error="Connection timeout",
        )

        mock_crawler = Mock()
        mock_crawler.crawl.return_value = mock_crawl_result
        mock_crawler_class.return_value = mock_crawler

        analyzer = SEOAnalyzer(llm_api_key="test-key")
        analyzer.crawler = mock_crawler

        crawl_result, seo_score = analyzer.analyze_url(
            "https://example.com"
        )

        assert crawl_result.success is False
        assert seo_score is None

    def test_technical_analyzer_finds_orphan_pages(self):
        """Test that the TechnicalAnalyzer correctly identifies orphan pages."""
        homepage_url = "https://example.com/"
        about_url = "https://example.com/about"
        orphan_url = "https://example.com/orphan"

        site_data = {
            homepage_url: PageMetadata(
                url=homepage_url,
                links=[about_url]
            ),
            about_url: PageMetadata(
                url=about_url,
                links=[homepage_url]
            ),
            orphan_url: PageMetadata(
                url=orphan_url,
                links=[homepage_url]
            )
        }

        technical_analyzer = TechnicalAnalyzer()
        result = technical_analyzer.analyze(site_data)
        # Handle both tuple return (issues, evidence) and direct return
        issues = result[0] if isinstance(result, tuple) else result

        assert len(issues.orphan_pages) == 1
        assert issues.orphan_pages[0] == orphan_url

    def test_technical_analyzer_finds_broken_links(self):
        """Test that the TechnicalAnalyzer correctly identifies broken internal links."""
        homepage_url = "https://example.com/"
        about_url = "https://example.com/about"
        broken_url = "https://example.com/contact"

        site_data = {
            homepage_url: PageMetadata(
                url=homepage_url,
                links=[about_url, broken_url, "https://external.com"]
            ),
            about_url: PageMetadata(
                url=about_url,
                links=[homepage_url]
            )
        }

        technical_analyzer = TechnicalAnalyzer()
        result = technical_analyzer.analyze(site_data)
        # Handle both tuple return (issues, evidence) and direct return
        issues = result[0] if isinstance(result, tuple) else result

        assert len(issues.broken_links) == 1
        source_page, broken_links_list = issues.broken_links[0]
        assert source_page == homepage_url
        assert len(broken_links_list) == 1
        assert broken_links_list[0] == broken_url

    @patch("seo.analyzer.LLMClient")
    def test_analyze_multiple_urls(self, mock_llm_class):
        """Test analyzing multiple URLs."""
        analyzer = SEOAnalyzer(llm_api_key="test-key")

        with patch.object(analyzer, "analyze_url") as mock_analyze:
            mock_analyze.return_value = (
                Mock(success=True),
                Mock(overall_score=80),
            )

            urls = [
                "https://example1.com",
                "https://example2.com",
            ]
            results = analyzer.analyze_multiple_urls(urls)

            assert len(results) == 2
            assert mock_analyze.call_count == 2
