# tests/test_redirect_analyzer.py
"""Tests for the redirect chain analyzer."""

import pytest
from seo.redirect_analyzer import RedirectAnalyzer
from seo.models import PageMetadata
from seo.constants import (
    MAX_CHAIN_URLS_IN_EVIDENCE,
    MAX_ALL_CHAINS_TO_STORE,
    HIGH_REDIRECT_PERCENTAGE_THRESHOLD,
)


class TestRedirectAnalyzer:
    """Test suite for RedirectAnalyzer."""

    @pytest.fixture
    def analyzer(self):
        """Create a RedirectAnalyzer instance."""
        return RedirectAnalyzer()

    @pytest.fixture
    def pages_no_redirects(self):
        """Create sample pages with no redirects."""
        page1 = PageMetadata(url="https://example.com/page1")
        page1.was_redirected = False
        page1.redirect_chain = []

        page2 = PageMetadata(url="https://example.com/page2")
        page2.was_redirected = False
        page2.redirect_chain = []

        return {
            "https://example.com/page1": page1,
            "https://example.com/page2": page2,
        }

    @pytest.fixture
    def pages_with_redirects(self):
        """Create sample pages with redirect chains."""
        page1 = PageMetadata(url="https://example.com/old")
        page1.was_redirected = True
        page1.final_url = "https://example.com/new"
        page1.redirect_chain = ["https://example.com/old", "https://example.com/new"]

        page2 = PageMetadata(url="https://example.com/legacy")
        page2.was_redirected = True
        page2.final_url = "https://example.com/current"
        page2.redirect_chain = [
            "https://example.com/legacy",
            "https://example.com/temp",
            "https://example.com/current",
        ]

        page3 = PageMetadata(url="https://example.com/direct")
        page3.was_redirected = False
        page3.redirect_chain = []

        return {
            "https://example.com/old": page1,
            "https://example.com/legacy": page2,
            "https://example.com/direct": page3,
        }

    @pytest.fixture
    def pages_with_long_chain(self):
        """Create sample pages with a long redirect chain."""
        chain = [f"https://example.com/hop{i}" for i in range(6)]
        page = PageMetadata(url="https://example.com/start")
        page.was_redirected = True
        page.final_url = chain[-1]
        page.redirect_chain = chain

        return {"https://example.com/start": page}

    def test_analyzer_initialization(self, analyzer):
        """Test that the analyzer initializes correctly."""
        assert analyzer.thresholds is not None
        assert analyzer.ms_per_redirect > 0

    def test_analyze_empty_pages(self, analyzer):
        """Test analysis with empty pages dict."""
        analysis, evidence = analyzer.analyze({})

        assert analysis.total_pages == 0
        assert analysis.total_chains == 0
        assert isinstance(evidence, dict)

    def test_analyze_no_redirects(self, analyzer, pages_no_redirects):
        """Test analysis when no pages have redirects."""
        analysis, _ = analyzer.analyze(pages_no_redirects)

        assert analysis.total_pages == 2
        assert analysis.pages_with_redirects == 0
        assert analysis.total_chains == 0

    def test_analyze_counts_redirects(self, analyzer, pages_with_redirects):
        """Test that redirects are correctly counted."""
        analysis, _ = analyzer.analyze(pages_with_redirects)

        assert analysis.total_pages == 3
        assert analysis.pages_with_redirects == 2
        assert analysis.total_chains == 2

    def test_analyze_hop_counts(self, analyzer, pages_with_redirects):
        """Test that hop counts are categorized correctly."""
        analysis, _ = analyzer.analyze(pages_with_redirects)

        # Chain length = len(redirect_chain)
        # First chain: ["old", "new"] = 2 entries
        # Second chain: ["legacy", "temp", "current"] = 3 entries
        assert analysis.chains_2_hops == 1
        assert analysis.chains_3_plus_hops == 1

    def test_long_chain_detection(self, analyzer, pages_with_long_chain):
        """Test detection of long redirect chains."""
        analysis, _ = analyzer.analyze(pages_with_long_chain)

        assert analysis.chains_3_plus_hops == 1
        assert len(analysis.long_chains) == 1
        assert analysis.max_chain_length == 6

    def test_time_waste_calculation(self, analyzer, pages_with_redirects):
        """Test calculation of wasted time from redirects."""
        analysis, _ = analyzer.analyze(pages_with_redirects)

        # Total hops: 2 (chain of 2) + 3 (chain of 3) = 5
        assert analysis.total_hops == 5
        expected_time = 5 * analyzer.ms_per_redirect
        assert analysis.total_time_wasted_ms == expected_time

    def test_average_hops_calculation(self, analyzer, pages_with_redirects):
        """Test calculation of average hops per chain."""
        analysis, _ = analyzer.analyze(pages_with_redirects)

        # 5 total hops across 2 chains = 2.5 average
        assert analysis.avg_hops_per_chain == 2.5

    def test_generates_recommendations(self, analyzer, pages_with_long_chain):
        """Test that recommendations are generated for long chains."""
        analysis, _ = analyzer.analyze(pages_with_long_chain)

        assert len(analysis.recommendations) > 0
        # Should recommend fixing long chains
        assert any("chain" in rec.lower() for rec in analysis.recommendations)

    def test_all_chains_limited(self, analyzer):
        """Test that all_chains list is limited."""
        # Create many pages with redirects
        pages = {}
        for i in range(100):
            page = PageMetadata(url=f"https://example.com/page{i}")
            page.was_redirected = True
            page.final_url = f"https://example.com/final{i}"
            page.redirect_chain = [
                f"https://example.com/page{i}",
                f"https://example.com/final{i}",
            ]
            pages[f"https://example.com/page{i}"] = page

        analysis, _ = analyzer.analyze(pages)

        # Should be limited to MAX_ALL_CHAINS_TO_STORE
        assert len(analysis.all_chains) <= MAX_ALL_CHAINS_TO_STORE

    def test_high_redirect_percentage_detection(self, analyzer):
        """Test detection of high redirect percentage."""
        # Create pages where >10% have redirects
        pages = {}
        for i in range(10):
            page = PageMetadata(url=f"https://example.com/redirect{i}")
            page.was_redirected = True
            page.final_url = f"https://example.com/target{i}"
            page.redirect_chain = [
                f"https://example.com/redirect{i}",
                f"https://example.com/target{i}",
            ]
            pages[f"https://example.com/redirect{i}"] = page

        # Add some non-redirect pages (less than redirects to trigger threshold)
        for i in range(5):
            page = PageMetadata(url=f"https://example.com/direct{i}")
            page.was_redirected = False
            page.redirect_chain = []
            pages[f"https://example.com/direct{i}"] = page

        analysis, _ = analyzer.analyze(pages)

        # 10 out of 15 pages = ~67% > 10%
        redirect_percentage = (analysis.pages_with_redirects / analysis.total_pages) * 100
        assert redirect_percentage > HIGH_REDIRECT_PERCENTAGE_THRESHOLD

    def test_evidence_collection(self, analyzer, pages_with_redirects):
        """Test that evidence is collected."""
        analysis, evidence = analyzer.analyze(pages_with_redirects)

        assert evidence is not None
        assert isinstance(evidence, dict)
