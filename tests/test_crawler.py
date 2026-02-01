"""Tests for web crawler."""

import pytest
from seo.crawler import WebCrawler
from seo.models import PageMetadata


class TestWebCrawler:
    """Test cases for WebCrawler."""

    def test_crawler_initialization(self):
        """Test crawler can be initialized."""
        crawler = WebCrawler()
        assert crawler.user_agent == "SEO-Analyzer-Bot/1.0"

    def test_crawler_custom_user_agent(self):
        """Test crawler with custom user agent."""
        custom_agent = "CustomBot/1.0"
        crawler = WebCrawler(user_agent=custom_agent)
        assert crawler.user_agent == custom_agent

    @pytest.mark.integration
    def test_crawl_valid_url(self):
        """Test crawling a valid URL."""
        crawler = WebCrawler()
        result = crawler.crawl("https://example.com")

        assert result.success is True
        assert result.metadata.url == "https://example.com"
        assert result.metadata.status_code == 200
        assert result.html != ""

    def test_crawl_invalid_url(self):
        """Test crawling an invalid URL."""
        crawler = WebCrawler()
        result = crawler.crawl("https://this-domain-does-not-exist-12345.com")

        assert result.success is False
        assert result.error is not None

    def test_extract_metadata(self):
        """Test metadata extraction from HTML."""
        crawler = WebCrawler()
        html = """
        <html>
            <head>
                <title>Test Page</title>
                <meta name="description" content="Test description">
                <meta name="keywords" content="test, seo, keywords">
            </head>
            <body>
                <h1>Main Heading</h1>
                <h2>Subheading</h2>
                <img src="test.jpg" alt="Test image">
                <a href="/page">Link</a>
                <p>Some content here</p>
            </body>
        </html>
        """

        metadata = crawler._extract_metadata(
            "https://example.com", html, 200, 0.5
        )

        assert metadata.title == "Test Page"
        assert metadata.description == "Test description"
        assert "test" in metadata.keywords
        assert "Main Heading" in metadata.h1_tags
        assert "Subheading" in metadata.h2_tags
        assert len(metadata.images) == 1
        assert metadata.word_count > 0
