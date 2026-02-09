"""Unit tests for SelectorLibrary.

Tests the selector management system ported from Spectrum per EPIC-SEO-INFRA-001.
"""

import pytest
from pathlib import Path

from seo.intelligence.selector_library import SelectorLibrary, SelectorCandidate
from seo.intelligence.site_profile import SelectorEntry


class TestSelectorEntry:
    """Tests for SelectorEntry (from site_profile)."""

    def test_create_entry(self):
        """Test creating a selector entry."""
        entry = SelectorEntry(
            selector="#submit-btn",
            selector_type="css",
            confidence=0.8,
        )

        assert entry.selector == "#submit-btn"
        assert entry.selector_type == "css"
        assert entry.confidence == 0.8

    def test_record_success(self):
        """Test recording a successful selector use."""
        entry = SelectorEntry(
            selector=".login-btn",
            selector_type="css",
            confidence=0.5,
        )

        initial_confidence = entry.confidence
        entry.record_success()

        assert entry.success_count == 1
        assert entry.last_success is not None
        assert entry.confidence >= initial_confidence

    def test_record_failure(self):
        """Test recording a failed selector use."""
        entry = SelectorEntry(
            selector=".flaky-btn",
            selector_type="css",
            confidence=0.8,
        )

        initial_confidence = entry.confidence
        entry.record_failure()

        assert entry.failure_count == 1
        assert entry.last_failure is not None
        assert entry.confidence <= initial_confidence

    def test_bayesian_confidence_with_prior(self):
        """Test that Bayesian averaging uses prior."""
        entry = SelectorEntry(
            selector=".new-btn",
            selector_type="css",
            confidence=0.5,
        )

        # Record one failure
        entry.record_failure()

        # Confidence should not drop too dramatically due to prior
        # Prior is 2 successes, 1 failure
        # After 1 actual failure: (2 + 0) / (2 + 1 + 0 + 1) = 2/4 = 0.5
        # With recency penalty: 0.5 * 0.95 = 0.475
        assert entry.confidence > 0.4

    def test_reliability_score(self):
        """Test reliability score calculation."""
        entry = SelectorEntry(
            selector=".reliable-btn",
            selector_type="css",
            confidence=0.9,
        )

        # New selector has low sample weight
        initial_reliability = entry.get_reliability_score()

        # Add many successes
        for _ in range(20):
            entry.record_success()

        # Now reliability should be closer to actual confidence
        final_reliability = entry.get_reliability_score()
        assert final_reliability > initial_reliability

    def test_to_dict(self):
        """Test serialization."""
        entry = SelectorEntry(
            selector=".test",
            selector_type="css",
            confidence=0.7,
            success_count=5,
            failure_count=1,
        )

        data = entry.to_dict()

        assert data["selector"] == ".test"
        assert data["confidence"] == 0.7
        assert data["success_count"] == 5

    def test_from_dict(self):
        """Test deserialization."""
        data = {
            "selector": ".deserialized",
            "selector_type": "xpath",
            "confidence": 0.85,
            "success_count": 10,
            "failure_count": 2,
            "last_success": None,
            "last_failure": None,
            "alternatives": [".alt1", ".alt2"],
        }

        entry = SelectorEntry.from_dict(data)

        assert entry.selector == ".deserialized"
        assert entry.selector_type == "xpath"
        assert len(entry.alternatives) == 2


class TestSelectorCandidate:
    """Tests for SelectorCandidate."""

    def test_create_candidate(self):
        """Test creating a selector candidate."""
        candidate = SelectorCandidate(
            selector="#unique-id",
            selector_type="css",
            element_type="button",
            purpose="submit",
            specificity=100,
            stability_score=0.95,
        )

        assert candidate.selector == "#unique-id"
        assert candidate.stability_score == 0.95

    def test_to_selector_entry(self):
        """Test converting candidate to entry."""
        candidate = SelectorCandidate(
            selector="[data-testid='login']",
            selector_type="css",
            element_type="button",
            purpose="login",
            specificity=50,
            stability_score=0.9,
        )

        entry = candidate.to_selector_entry(initial_confidence=0.7)

        assert isinstance(entry, SelectorEntry)
        assert entry.selector == "[data-testid='login']"
        assert entry.confidence == 0.7


class TestSelectorLibrary:
    """Tests for SelectorLibrary."""

    @pytest.fixture
    def library(self, tmp_path):
        """Create a selector library for testing."""
        return SelectorLibrary(storage_path=tmp_path / "selectors.json")

    @pytest.fixture
    def memory_library(self):
        """Create an in-memory selector library."""
        return SelectorLibrary(storage_path=None)

    def test_store_and_get_selector(self, memory_library):
        """Test storing and retrieving a selector."""
        entry = SelectorEntry(
            selector="#checkout-btn",
            selector_type="css",
            confidence=0.9,
        )

        memory_library.store_selector("example.com", "checkout_button", entry)
        retrieved = memory_library.get_selector("example.com", "checkout_button")

        assert retrieved is not None
        assert retrieved.selector == "#checkout-btn"

    def test_get_selector_not_found(self, memory_library):
        """Test getting non-existent selector returns None."""
        result = memory_library.get_selector("unknown.com", "unknown_purpose")
        assert result is None

    def test_get_selector_with_fallbacks(self, memory_library):
        """Test getting selector with fallback alternatives."""
        entry = SelectorEntry(
            selector="#primary",
            selector_type="css",
            confidence=0.9,
            alternatives=[".secondary", ".tertiary"],
        )

        memory_library.store_selector("test.com", "button", entry)
        fallbacks = memory_library.get_selector_with_fallbacks("test.com", "button")

        assert len(fallbacks) == 3  # Primary + 2 alternatives
        assert fallbacks[0].selector == "#primary"
        assert fallbacks[0].confidence > fallbacks[1].confidence

    def test_global_pattern_fallback(self, memory_library):
        """Test global pattern fallback."""
        # Add global pattern
        memory_library.add_global_pattern("add_to_cart", ".add-to-cart")
        memory_library.add_global_pattern("add_to_cart", "[data-action='add']")

        # Get fallbacks for unknown site
        fallbacks = memory_library.get_selector_with_fallbacks("newsite.com", "add_to_cart")

        # Should return global patterns
        assert len(fallbacks) >= 2
        assert any(f.selector == ".add-to-cart" for f in fallbacks)

    def test_record_success(self, memory_library):
        """Test recording selector success."""
        entry = SelectorEntry(
            selector="#btn",
            selector_type="css",
            confidence=0.5,
        )

        memory_library.store_selector("test.com", "button", entry)
        memory_library.record_success("test.com", "button")

        updated = memory_library.get_selector("test.com", "button")
        assert updated.success_count == 1

    def test_record_failure(self, memory_library):
        """Test recording selector failure."""
        entry = SelectorEntry(
            selector="#flaky-btn",
            selector_type="css",
            confidence=0.8,
        )

        memory_library.store_selector("test.com", "button", entry)
        memory_library.record_failure("test.com", "button")

        updated = memory_library.get_selector("test.com", "button")
        assert updated.failure_count == 1
        assert updated.confidence < 0.8

    def test_generate_candidates_from_id(self, memory_library):
        """Test generating candidates from element with ID."""
        html = '<button id="submit-form">Submit</button>'
        candidates = memory_library.generate_candidates(html, "submit")

        # Should have ID-based candidate
        id_candidates = [c for c in candidates if "#submit-form" in c.selector]
        assert len(id_candidates) > 0
        assert id_candidates[0].stability_score > 0.9

    def test_generate_candidates_from_data_testid(self, memory_library):
        """Test generating candidates from data-testid."""
        html = '<button data-testid="checkout-btn">Checkout</button>'
        candidates = memory_library.generate_candidates(html, "checkout")

        # Should have data-testid candidate with high stability
        testid_candidates = [c for c in candidates if "data-testid" in c.selector]
        assert len(testid_candidates) > 0
        assert testid_candidates[0].stability_score >= 0.9

    def test_generate_candidates_from_class(self, memory_library):
        """Test generating candidates from class."""
        html = '<button class="btn primary-action">Click</button>'
        candidates = memory_library.generate_candidates(html, "action")

        # Should have class-based candidate
        class_candidates = [c for c in candidates if "." in c.selector]
        assert len(class_candidates) > 0

    def test_stats(self, memory_library):
        """Test library statistics."""
        memory_library.store_selector("site1.com", "btn1", SelectorEntry(
            selector="#a", selector_type="css", confidence=0.9
        ))
        memory_library.store_selector("site1.com", "btn2", SelectorEntry(
            selector="#b", selector_type="css", confidence=0.8
        ))
        memory_library.store_selector("site2.com", "btn1", SelectorEntry(
            selector="#c", selector_type="css", confidence=0.7
        ))

        stats = memory_library.stats()

        assert stats["site_count"] == 2
        assert stats["total_selectors"] == 3
        assert 0.7 <= stats["average_confidence"] <= 0.9

    def test_persistence(self, tmp_path):
        """Test that library persists to disk."""
        storage_path = tmp_path / "persist_test.json"

        # First session
        lib1 = SelectorLibrary(storage_path=storage_path)
        lib1.store_selector("test.com", "button", SelectorEntry(
            selector="#persistent",
            selector_type="css",
            confidence=0.9,
        ))

        # Second session
        lib2 = SelectorLibrary(storage_path=storage_path)
        entry = lib2.get_selector("test.com", "button")

        assert entry is not None
        assert entry.selector == "#persistent"
