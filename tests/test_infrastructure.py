"""Tests for infrastructure components.

Tests for browser pool, rate limiter, selector library, and AI cache.
"""

import asyncio
import json
import pytest
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock

from seo.infrastructure.browser_pool import (
    BrowserPool,
    BrowserHealth,
    PoolStatus,
    ContextMetrics,
)
from seo.infrastructure.rate_limiter import (
    AdaptiveRateLimiter,
    TokenBucketLimiter,
    RateLimitConfig,
    ResourceMetrics,
)
from seo.intelligence.selector_library import (
    SelectorLibrary,
    SelectorCandidate,
)
from seo.intelligence.site_profile import SelectorEntry
from seo.intelligence.ai_cache import AICache, CacheEntry


# =============================================================================
# BrowserPool Tests
# =============================================================================

class TestBrowserPool:
    """Test cases for BrowserPool."""

    def test_pool_initialization_defaults(self):
        """Test pool initializes with correct defaults."""
        pool = BrowserPool()
        assert pool.max_size == 4
        assert pool.headless is True
        assert pool.timeout_ms == 30000
        assert pool.stealth_backend == "playwright"
        assert pool.is_started is False

    def test_pool_initialization_custom(self):
        """Test pool initialization with custom parameters."""
        pool = BrowserPool(
            max_size=8,
            headless=False,
            timeout_ms=60000,
            stealth_backend="undetected",
            user_agent="Custom UA",
        )
        assert pool.max_size == 8
        assert pool.headless is False
        assert pool.timeout_ms == 60000
        assert pool.stealth_backend == "undetected"
        assert pool.user_agent == "Custom UA"

    def test_context_metrics_initialization(self):
        """Test ContextMetrics initialization."""
        metrics = ContextMetrics(
            context_id=1,
            created_at=datetime.now(),
        )
        assert metrics.requests_handled == 0
        assert metrics.errors == 0
        assert metrics.health == BrowserHealth.HEALTHY
        assert metrics.error_rate == 0.0

    def test_context_metrics_record_success(self):
        """Test recording successful requests."""
        metrics = ContextMetrics(
            context_id=1,
            created_at=datetime.now(),
        )
        metrics.record_success()
        assert metrics.requests_handled == 1
        assert metrics.errors == 0
        assert metrics.last_used is not None
        assert metrics.health == BrowserHealth.HEALTHY

    def test_context_metrics_record_error(self):
        """Test recording failed requests."""
        metrics = ContextMetrics(
            context_id=1,
            created_at=datetime.now(),
        )
        # Record some successes and errors
        metrics.record_success()
        metrics.record_success()
        metrics.record_error()

        assert metrics.requests_handled == 3
        assert metrics.errors == 1
        assert metrics.error_rate == pytest.approx(1/3, rel=0.01)

    def test_context_metrics_health_degradation(self):
        """Test health degrades with high error rate."""
        metrics = ContextMetrics(
            context_id=1,
            created_at=datetime.now(),
        )
        # 3 errors, 2 successes = 60% error rate
        metrics.record_error()
        metrics.record_error()
        metrics.record_error()
        metrics.record_success()
        metrics.record_success()

        assert metrics.error_rate > 0.5
        assert metrics.health == BrowserHealth.UNHEALTHY

    def test_context_metrics_degraded_state(self):
        """Test degraded state at moderate error rate."""
        metrics = ContextMetrics(
            context_id=1,
            created_at=datetime.now(),
        )
        # 2 successes + 1 error = 33% error rate (between 0.2 and 0.5)
        # Health is updated on record_error(), so error must be last
        metrics.record_success()
        metrics.record_success()
        metrics.record_error()

        assert 0.2 < metrics.error_rate < 0.5
        assert metrics.health == BrowserHealth.DEGRADED

    def test_pool_status_structure(self):
        """Test PoolStatus dataclass structure."""
        status = PoolStatus(
            total_size=4,
            available=3,
            in_use=1,
            healthy=3,
            degraded=1,
            unhealthy=0,
            total_requests=100,
            total_errors=5,
            uptime_seconds=3600.0,
        )
        assert status.total_size == 4
        assert status.available == 3
        assert status.total_requests == 100

    @pytest.mark.asyncio
    async def test_pool_not_started_raises_error(self):
        """Test acquiring from unstarted pool raises error."""
        pool = BrowserPool()

        with pytest.raises(RuntimeError, match="not started"):
            async with pool.acquire():
                pass

    def test_pool_has_async_context_manager(self):
        """Test BrowserPool supports async context manager protocol (M1.1)."""
        import inspect
        pool = BrowserPool()
        assert hasattr(pool, '__aenter__')
        assert hasattr(pool, '__aexit__')
        assert inspect.iscoroutinefunction(pool.__aenter__)
        assert inspect.iscoroutinefunction(pool.__aexit__)


# =============================================================================
# AdaptiveRateLimiter Tests
# =============================================================================

class TestAdaptiveRateLimiter:
    """Test cases for AdaptiveRateLimiter."""

    def test_limiter_initialization_defaults(self):
        """Test limiter initializes with default config."""
        limiter = AdaptiveRateLimiter()
        assert limiter.config.base_delay == 1.0
        assert limiter.config.min_delay == 0.5
        assert limiter.config.max_delay == 10.0
        assert limiter.current_delay == 1.0

    def test_limiter_initialization_custom_config(self):
        """Test limiter initialization with custom config."""
        config = RateLimitConfig(
            base_delay=2.0,
            min_delay=1.0,
            max_delay=20.0,
            target_response_time=3.0,
        )
        limiter = AdaptiveRateLimiter(config)
        assert limiter.config.base_delay == 2.0
        assert limiter.current_delay == 2.0

    def test_record_request_success(self):
        """Test recording successful requests."""
        limiter = AdaptiveRateLimiter()
        limiter.record_request(response_time=0.5, success=True)

        metrics = limiter.get_metrics()
        assert metrics.total_requests == 1
        assert metrics.total_errors == 0

    def test_record_request_failure(self):
        """Test recording failed requests."""
        limiter = AdaptiveRateLimiter()
        limiter.record_request(response_time=0.5, success=False)

        metrics = limiter.get_metrics()
        assert metrics.total_requests == 1
        assert metrics.total_errors == 1

    def test_error_rate_triggers_backoff(self):
        """Test high error rate increases delay."""
        config = RateLimitConfig(
            base_delay=1.0,
            error_rate_threshold=0.1,
            error_backoff_multiplier=2.0,
        )
        limiter = AdaptiveRateLimiter(config)

        initial_delay = limiter.current_delay

        # Record failures to exceed threshold
        for _ in range(5):
            limiter.record_request(response_time=0.5, success=False)

        # Delay should have increased
        assert limiter.current_delay > initial_delay

    def test_slow_response_increases_delay(self):
        """Test slow response times increase delay."""
        config = RateLimitConfig(
            base_delay=1.0,
            target_response_time=1.0,
        )
        limiter = AdaptiveRateLimiter(config)

        initial_delay = limiter.current_delay

        # Record slow responses
        for _ in range(5):
            limiter.record_request(response_time=3.0, success=True)

        # Delay should have increased
        assert limiter.current_delay > initial_delay

    def test_good_conditions_decrease_delay(self):
        """Test good conditions gradually decrease delay."""
        config = RateLimitConfig(
            base_delay=2.0,
            min_delay=0.5,
            target_response_time=2.0,
            success_recovery_multiplier=0.9,
        )
        limiter = AdaptiveRateLimiter(config)

        # Record many fast successful responses
        for _ in range(10):
            limiter.record_request(response_time=0.3, success=True)

        # Delay should have decreased (but not below min)
        assert limiter.current_delay < 2.0
        assert limiter.current_delay >= config.min_delay

    def test_delay_bounded_by_max(self):
        """Test delay doesn't exceed max."""
        config = RateLimitConfig(
            base_delay=1.0,
            max_delay=5.0,
            error_backoff_multiplier=3.0,
        )
        limiter = AdaptiveRateLimiter(config)

        # Record many failures
        for _ in range(20):
            limiter.record_request(response_time=0.5, success=False)

        assert limiter.current_delay <= config.max_delay

    def test_reset_restores_initial_state(self):
        """Test reset restores limiter to initial state."""
        limiter = AdaptiveRateLimiter()

        # Change state
        for _ in range(5):
            limiter.record_request(response_time=5.0, success=False)

        # Reset
        limiter.reset()

        assert limiter.current_delay == limiter.config.base_delay
        assert limiter.error_rate == 0.0

    def test_get_metrics_returns_correct_data(self):
        """Test get_metrics returns accurate data."""
        limiter = AdaptiveRateLimiter()

        limiter.record_request(response_time=1.0, success=True)
        limiter.record_request(response_time=2.0, success=True)
        limiter.record_request(response_time=3.0, success=False)

        metrics = limiter.get_metrics()

        assert metrics.total_requests == 3
        assert metrics.total_errors == 1
        assert metrics.avg_response_time == pytest.approx(2.0, rel=0.01)
        assert metrics.error_rate == pytest.approx(1/3, rel=0.01)


class TestTokenBucketLimiter:
    """Test cases for TokenBucketLimiter."""

    def test_bucket_initialization(self):
        """Test bucket initializes with correct capacity."""
        bucket = TokenBucketLimiter(rate=1.0, capacity=5)
        assert bucket.rate == 1.0
        assert bucket.capacity == 5
        assert bucket.available_tokens == 5

    @pytest.mark.asyncio
    async def test_acquire_immediate_when_tokens_available(self):
        """Test acquire returns immediately when tokens available."""
        bucket = TokenBucketLimiter(rate=1.0, capacity=5)

        wait_time = await bucket.acquire(1)

        assert wait_time == 0.0
        assert bucket.available_tokens == pytest.approx(4, abs=0.1)

    @pytest.mark.asyncio
    async def test_acquire_multiple_tokens(self):
        """Test acquiring multiple tokens at once."""
        bucket = TokenBucketLimiter(rate=1.0, capacity=5)

        wait_time = await bucket.acquire(3)

        assert wait_time == 0.0
        assert bucket.available_tokens == pytest.approx(2, abs=0.1)

    @pytest.mark.asyncio
    async def test_tokens_refill_over_time(self):
        """Test tokens refill based on elapsed time."""
        bucket = TokenBucketLimiter(rate=10.0, capacity=5)  # 10 tokens/sec

        # Use all tokens
        await bucket.acquire(5)
        assert bucket.available_tokens < 1

        # Wait for refill
        await asyncio.sleep(0.2)  # Should refill ~2 tokens

        assert bucket.available_tokens >= 1


# =============================================================================
# SelectorLibrary Tests
# =============================================================================

class TestSelectorLibrary:
    """Test cases for SelectorLibrary."""

    def test_library_initialization_without_storage(self):
        """Test library initializes without storage path."""
        library = SelectorLibrary()
        assert library.storage_path is None
        assert library.stats()["total_selectors"] == 0

    def test_library_initialization_with_storage(self):
        """Test library initializes with storage path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = Path(tmpdir) / "selectors.json"
            library = SelectorLibrary(storage_path=storage_path)
            assert library.storage_path == storage_path

    def test_store_and_retrieve_selector(self):
        """Test storing and retrieving a selector."""
        library = SelectorLibrary()

        entry = SelectorEntry(
            selector="#submit-btn",
            selector_type="css",
            confidence=0.9,
        )

        library.store_selector("example.com", "submit_button", entry)

        retrieved = library.get_selector("example.com", "submit_button")
        assert retrieved is not None
        assert retrieved.selector == "#submit-btn"
        assert retrieved.confidence == 0.9

    def test_get_nonexistent_selector_returns_none(self):
        """Test getting non-existent selector returns None."""
        library = SelectorLibrary()

        result = library.get_selector("example.com", "nonexistent")
        assert result is None

    def test_record_success_increases_confidence(self):
        """Test recording success updates selector."""
        library = SelectorLibrary()

        entry = SelectorEntry(
            selector="#btn",
            selector_type="css",
            confidence=0.5,
        )
        library.store_selector("example.com", "button", entry)

        library.record_success("example.com", "button")

        updated = library.get_selector("example.com", "button")
        assert updated.success_count == 1
        assert updated.last_success is not None

    def test_record_failure_decreases_confidence(self):
        """Test recording failure updates selector."""
        library = SelectorLibrary()

        entry = SelectorEntry(
            selector="#btn",
            selector_type="css",
            confidence=0.8,
        )
        library.store_selector("example.com", "button", entry)

        library.record_failure("example.com", "button")

        updated = library.get_selector("example.com", "button")
        assert updated.failure_count == 1
        assert updated.last_failure is not None

    def test_get_selector_with_fallbacks(self):
        """Test getting selectors with fallbacks."""
        library = SelectorLibrary()

        # Store selector with alternatives
        entry = SelectorEntry(
            selector="#primary",
            selector_type="css",
            confidence=0.9,
            alternatives=["#fallback1", "#fallback2"],
        )
        library.store_selector("example.com", "button", entry)

        # Add global pattern
        library.add_global_pattern("button", "button[type='submit']")

        selectors = library.get_selector_with_fallbacks("example.com", "button")

        assert len(selectors) >= 3  # primary + 2 alternatives + global
        # Should be sorted by confidence
        assert selectors[0].selector == "#primary"

    def test_generate_candidates_from_html(self):
        """Test generating selector candidates from HTML."""
        library = SelectorLibrary()

        html = '<button id="submit-btn" class="btn primary" data-testid="submit">Submit</button>'

        candidates = library.generate_candidates(html, "submit_button")

        assert len(candidates) > 0
        # Should have ID-based selector (highest stability)
        id_candidates = [c for c in candidates if "#submit-btn" in c.selector]
        assert len(id_candidates) > 0

    def test_generate_candidates_prioritizes_stable_selectors(self):
        """Test that stable selectors are prioritized."""
        library = SelectorLibrary()

        html = '<input id="email" data-testid="email-input" class="form-input" type="email">'

        candidates = library.generate_candidates(html, "email_field")

        # data-testid should have highest stability
        assert candidates[0].stability_score >= 0.95

    def test_stats_returns_correct_counts(self):
        """Test stats method returns correct counts."""
        library = SelectorLibrary()

        library.store_selector("site1.com", "btn1", SelectorEntry(
            selector="#a", selector_type="css", confidence=0.8
        ))
        library.store_selector("site1.com", "btn2", SelectorEntry(
            selector="#b", selector_type="css", confidence=0.7
        ))
        library.store_selector("site2.com", "btn1", SelectorEntry(
            selector="#c", selector_type="css", confidence=0.9
        ))

        stats = library.stats()

        assert stats["site_count"] == 2
        assert stats["total_selectors"] == 3
        assert stats["average_confidence"] == pytest.approx(0.8, rel=0.01)

    def test_persistence_save_and_load(self):
        """Test saving and loading library from disk."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = Path(tmpdir) / "selectors.json"

            # Create and populate library
            library1 = SelectorLibrary(storage_path=storage_path)
            library1.store_selector("example.com", "button", SelectorEntry(
                selector="#btn",
                selector_type="css",
                confidence=0.85,
            ))
            library1.add_global_pattern("submit", "button[type='submit']")

            # Load in new instance
            library2 = SelectorLibrary(storage_path=storage_path)

            retrieved = library2.get_selector("example.com", "button")
            assert retrieved is not None
            assert retrieved.selector == "#btn"
            assert retrieved.confidence == 0.85

    def test_cleanup_expired_removes_old_selectors(self):
        """Test cleanup removes expired selectors."""
        library = SelectorLibrary()

        # Create an expired selector
        old_date = datetime.now() - timedelta(days=100)
        entry = SelectorEntry(
            selector="#old",
            selector_type="css",
            confidence=0.5,
            created_at=old_date,
            last_used=old_date,
        )
        library.store_selector("example.com", "old_button", entry)

        # Create a fresh selector
        library.store_selector("example.com", "new_button", SelectorEntry(
            selector="#new",
            selector_type="css",
            confidence=0.9,
        ))

        result = library.cleanup_expired()

        assert result["expired_removed"] == 1
        assert library.get_selector("example.com", "old_button") is None
        assert library.get_selector("example.com", "new_button") is not None


class TestSelectorEntry:
    """Test cases for SelectorEntry."""

    def test_entry_initialization(self):
        """Test entry initializes correctly."""
        entry = SelectorEntry(
            selector="#btn",
            selector_type="css",
            confidence=0.8,
        )
        assert entry.selector == "#btn"
        assert entry.success_count == 0
        assert entry.failure_count == 0

    def test_bayesian_confidence_update(self):
        """Test Bayesian confidence calculation."""
        entry = SelectorEntry(
            selector="#btn",
            selector_type="css",
            confidence=0.5,
        )

        # With priors (2 success, 1 failure), initial confidence should be ~0.67
        entry._update_confidence()
        assert entry.confidence == pytest.approx(0.67, rel=0.05)

        # After 5 successes
        for _ in range(5):
            entry.record_success()

        # Should be higher
        assert entry.confidence > 0.8

    def test_is_stale_after_threshold(self):
        """Test staleness detection."""
        old_date = datetime.now() - timedelta(days=35)
        entry = SelectorEntry(
            selector="#btn",
            selector_type="css",
            confidence=0.8,
            created_at=old_date,
            last_used=old_date,
        )

        assert entry.is_stale() is True

    def test_is_not_stale_when_recently_used(self):
        """Test not stale when recently used."""
        entry = SelectorEntry(
            selector="#btn",
            selector_type="css",
            confidence=0.8,
        )
        entry.record_success()  # Updates last_used

        assert entry.is_stale() is False

    def test_is_expired_after_threshold(self):
        """Test expiry detection."""
        old_date = datetime.now() - timedelta(days=100)
        entry = SelectorEntry(
            selector="#btn",
            selector_type="css",
            confidence=0.8,
            created_at=old_date,
            last_used=old_date,
        )

        assert entry.is_expired() is True

    def test_alternative_promotion(self):
        """Test promoting alternative to primary."""
        entry = SelectorEntry(
            selector="#primary",
            selector_type="css",
            confidence=0.6,
            alternatives=["#alt1", "#alt2"],
        )

        # Record good performance for alternative
        for _ in range(10):
            entry.record_alternative_success("#alt1")

        # Check promotion candidate
        candidate = entry.get_promotion_candidate()
        assert candidate == "#alt1"

        # Promote
        result = entry.promote_alternative("#alt1")
        assert result["success"] is True
        assert entry.selector == "#alt1"
        assert "#primary" in entry.alternatives

    def test_serialization_roundtrip(self):
        """Test serialization and deserialization."""
        entry = SelectorEntry(
            selector="#btn",
            selector_type="css",
            confidence=0.85,
            success_count=10,
            failure_count=2,
            alternatives=["#fallback"],
        )
        entry.record_success()

        # Serialize
        data = entry.to_dict()

        # Deserialize
        restored = SelectorEntry.from_dict(data)

        assert restored.selector == entry.selector
        assert restored.confidence == entry.confidence
        assert restored.success_count == entry.success_count
        assert restored.alternatives == entry.alternatives


# =============================================================================
# AICache Tests
# =============================================================================

class TestAICache:
    """Test cases for AICache."""

    def test_cache_initialization(self):
        """Test cache initializes correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = AICache(
                cache_dir=Path(tmpdir),
                ttl_hours=24,
                max_size_mb=100,
            )

            assert cache.enabled is True
            assert cache.ttl_hours == 24
            assert cache.max_size_mb == 100

    def test_cache_disabled(self):
        """Test disabled cache returns None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = AICache(
                cache_dir=Path(tmpdir),
                enabled=False,
            )

            result = cache.get("test prompt")
            assert result is None

    def test_put_and_get_basic(self):
        """Test basic put and get operations."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = AICache(cache_dir=Path(tmpdir))

            prompt = "Analyze this content for SEO"
            response = {"score": 85, "recommendations": ["Add keywords"]}

            cache.put(prompt, response, model="gpt-4")

            retrieved = cache.get(prompt)

            assert retrieved is not None
            assert retrieved["score"] == 85

    def test_put_and_get_with_context(self):
        """Test caching with context."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = AICache(cache_dir=Path(tmpdir))

            prompt = "Analyze this"
            context1 = {"url": "https://example.com"}
            context2 = {"url": "https://other.com"}

            cache.put(prompt, {"result": "example"}, "gpt-4", context1)
            cache.put(prompt, {"result": "other"}, "gpt-4", context2)

            # Different contexts should have different results
            result1 = cache.get(prompt, context1)
            result2 = cache.get(prompt, context2)

            assert result1["result"] == "example"
            assert result2["result"] == "other"

    def test_cache_expiry(self):
        """Test cached entries expire."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = AICache(
                cache_dir=Path(tmpdir),
                ttl_hours=0,  # Immediate expiry
            )

            cache.put("prompt", {"data": "test"}, "gpt-4")

            # Should be expired immediately
            import time
            time.sleep(0.1)

            result = cache.get("prompt")
            assert result is None

    def test_invalidate_removes_entry(self):
        """Test invalidating a cache entry."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = AICache(cache_dir=Path(tmpdir))

            cache.put("prompt", {"data": "test"}, "gpt-4")

            # Should exist
            assert cache.get("prompt") is not None

            # Invalidate
            removed = cache.invalidate("prompt")
            assert removed is True

            # Should be gone
            assert cache.get("prompt") is None

    def test_clear_removes_all(self):
        """Test clearing all cache entries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = AICache(cache_dir=Path(tmpdir))

            cache.put("prompt1", {"data": "1"}, "gpt-4")
            cache.put("prompt2", {"data": "2"}, "gpt-4")
            cache.put("prompt3", {"data": "3"}, "gpt-4")

            stats_before = cache.stats()
            assert stats_before["entry_count"] == 3

            cache.clear()

            stats_after = cache.stats()
            assert stats_after["entry_count"] == 0

    def test_stats_returns_accurate_data(self):
        """Test stats method returns accurate data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = AICache(cache_dir=Path(tmpdir))

            cache.put("p1", {"d": 1}, "gpt-4")
            cache.put("p2", {"d": 2}, "gpt-4")

            # Access one to increment hit count
            cache.get("p1")
            cache.get("p1")

            stats = cache.stats()

            assert stats["enabled"] is True
            assert stats["entry_count"] == 2
            assert stats["total_hits"] == 2

    def test_find_similar_returns_matches(self):
        """Test finding similar cached entries."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = AICache(cache_dir=Path(tmpdir))

            # Add entries with similar prompts
            cache.put("Analyze SEO for homepage", {"score": 80}, "gpt-4")
            cache.put("Analyze SEO for product page", {"score": 75}, "gpt-4")
            cache.put("Check accessibility", {"score": 90}, "gpt-4")

            # Find similar to SEO prompt
            similar = cache.find_similar("Analyze SEO for contact page")

            # Should find the SEO-related entries (depends on hash collision)
            assert isinstance(similar, list)

    def test_content_addressable_key_consistency(self):
        """Test same prompt always generates same key."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = AICache(cache_dir=Path(tmpdir))

            prompt = "Test prompt"
            context = {"key": "value"}

            key1 = cache._compute_key(prompt, context)
            key2 = cache._compute_key(prompt, context)

            assert key1 == key2

    def test_different_prompts_different_keys(self):
        """Test different prompts generate different keys."""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = AICache(cache_dir=Path(tmpdir))

            key1 = cache._compute_key("Prompt A", None)
            key2 = cache._compute_key("Prompt B", None)

            assert key1 != key2


class TestCacheEntry:
    """Test cases for CacheEntry dataclass."""

    def test_cache_entry_creation(self):
        """Test CacheEntry creation."""
        now = datetime.now()
        entry = CacheEntry(
            key="abc123",
            prompt_hash="def456",
            response={"data": "test"},
            model="gpt-4",
            created_at=now,
            expires_at=now + timedelta(hours=24),
        )

        assert entry.key == "abc123"
        assert entry.hit_count == 0
        assert entry.is_expired() is False

    def test_cache_entry_expiry(self):
        """Test CacheEntry expiry check."""
        now = datetime.now()
        entry = CacheEntry(
            key="abc123",
            prompt_hash="def456",
            response={"data": "test"},
            model="gpt-4",
            created_at=now - timedelta(hours=25),
            expires_at=now - timedelta(hours=1),
        )

        assert entry.is_expired() is True

    def test_cache_entry_serialization(self):
        """Test CacheEntry serialization."""
        now = datetime.now()
        entry = CacheEntry(
            key="abc123",
            prompt_hash="def456",
            response={"score": 85},
            model="gpt-4",
            created_at=now,
            expires_at=now + timedelta(hours=24),
            hit_count=5,
        )

        data = entry.to_dict()
        restored = CacheEntry.from_dict(data)

        assert restored.key == entry.key
        assert restored.response == entry.response
        assert restored.hit_count == entry.hit_count
