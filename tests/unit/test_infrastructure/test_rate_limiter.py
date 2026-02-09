"""Unit tests for AdaptiveRateLimiter.

Tests the rate limiting system ported from Spectrum per EPIC-SEO-INFRA-001.
"""

import pytest
import asyncio
from datetime import datetime

pytest_plugins = ('pytest_asyncio',)

from seo.infrastructure.rate_limiter import (
    AdaptiveRateLimiter,
    TokenBucketLimiter,
    RateLimitConfig,
    ResourceMetrics,
)


class TestRateLimitConfig:
    """Tests for RateLimitConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = RateLimitConfig()

        assert config.base_delay == 1.0
        assert config.min_delay == 0.5
        assert config.max_delay == 10.0
        assert config.target_response_time == 2.0
        assert config.error_rate_threshold == 0.1
        assert config.window_size == 20

    def test_custom_config(self):
        """Test custom configuration."""
        config = RateLimitConfig(
            base_delay=2.0,
            min_delay=1.0,
            max_delay=20.0,
        )

        assert config.base_delay == 2.0
        assert config.min_delay == 1.0
        assert config.max_delay == 20.0


class TestAdaptiveRateLimiter:
    """Tests for AdaptiveRateLimiter."""

    @pytest.fixture
    def limiter(self):
        """Create a rate limiter with fast config for testing."""
        config = RateLimitConfig(
            base_delay=0.1,
            min_delay=0.05,
            max_delay=1.0,
            window_size=5,
        )
        return AdaptiveRateLimiter(config)

    @pytest.mark.asyncio
    async def test_initial_delay(self, limiter):
        """Test that initial delay matches base config."""
        assert limiter.current_delay == 0.1

    @pytest.mark.asyncio
    async def test_wait_returns_wait_time(self, limiter):
        """Test that wait() returns the actual wait time."""
        # First call should return 0 (no previous request)
        wait_time = await limiter.wait()
        assert wait_time == 0

    def test_record_success(self, limiter):
        """Test recording successful requests."""
        limiter.record_request(response_time=0.5, success=True)
        limiter.record_request(response_time=0.6, success=True)

        metrics = limiter.get_metrics()
        assert metrics.requests_in_window == 2
        assert metrics.errors_in_window == 0

    def test_record_error(self, limiter):
        """Test recording failed requests."""
        limiter.record_request(response_time=0.5, success=True)
        limiter.record_request(response_time=1.0, success=False)

        assert limiter.error_rate == 0.5

    def test_backoff_on_errors(self, limiter):
        """Test that delay increases on high error rate."""
        initial_delay = limiter.current_delay

        # Record several errors to trigger backoff
        for _ in range(5):
            limiter.record_request(response_time=0.5, success=False)

        # Delay should have increased
        assert limiter.current_delay > initial_delay

    def test_backoff_on_slow_response(self, limiter):
        """Test that delay increases on slow responses."""
        # Configure for quick response time target
        limiter.config.target_response_time = 0.5

        initial_delay = limiter.current_delay

        # Record slow responses
        for _ in range(5):
            limiter.record_request(response_time=2.0, success=True)

        # Delay should have increased
        assert limiter.current_delay > initial_delay

    def test_recovery_on_good_conditions(self, limiter):
        """Test that delay decreases when conditions improve."""
        # First, cause significant backoff by recording many errors
        for _ in range(10):
            limiter.record_request(response_time=0.5, success=False)

        high_delay = limiter.current_delay
        # Verify we actually increased the delay
        assert high_delay > limiter.config.base_delay

        # Now record many successes with fast responses to clear error history
        for _ in range(20):
            limiter.record_request(response_time=0.01, success=True)

        # Delay should have decreased toward base/min
        assert limiter.current_delay < high_delay

    def test_delay_bounded_by_max(self, limiter):
        """Test that delay never exceeds max_delay."""
        # Record many errors
        for _ in range(100):
            limiter.record_request(response_time=10.0, success=False)

        assert limiter.current_delay <= limiter.config.max_delay

    def test_delay_bounded_by_min(self, limiter):
        """Test that delay never goes below min_delay."""
        # Record many fast successes
        for _ in range(100):
            limiter.record_request(response_time=0.01, success=True)

        assert limiter.current_delay >= limiter.config.min_delay

    def test_reset(self, limiter):
        """Test resetting the limiter."""
        # Change state
        limiter.record_request(response_time=0.5, success=True)
        limiter.record_request(response_time=0.5, success=False)

        # Reset
        limiter.reset()

        assert limiter.current_delay == limiter.config.base_delay
        assert limiter.error_rate == 0.0

    def test_get_metrics(self, limiter):
        """Test metrics retrieval."""
        limiter.record_request(response_time=0.5, success=True)
        limiter.record_request(response_time=0.7, success=True)

        metrics = limiter.get_metrics()

        assert isinstance(metrics, ResourceMetrics)
        assert metrics.requests_in_window == 2
        assert metrics.avg_response_time == 0.6
        assert metrics.error_rate == 0.0
        assert metrics.total_requests == 2


class TestTokenBucketLimiter:
    """Tests for TokenBucketLimiter."""

    @pytest.fixture
    def bucket(self):
        """Create a token bucket for testing."""
        return TokenBucketLimiter(rate=10.0, capacity=5)

    def test_initial_tokens(self, bucket):
        """Test that bucket starts full."""
        assert bucket.available_tokens == 5

    @pytest.mark.asyncio
    async def test_acquire_single_token(self, bucket):
        """Test acquiring a single token."""
        wait_time = await bucket.acquire(1)
        assert wait_time == 0  # Should be instant with full bucket
        assert bucket.available_tokens < 5

    @pytest.mark.asyncio
    async def test_acquire_multiple_tokens(self, bucket):
        """Test acquiring multiple tokens at once."""
        wait_time = await bucket.acquire(3)
        assert wait_time == 0
        # Allow small float tolerance for timing
        assert bucket.available_tokens <= 2.1

    @pytest.mark.asyncio
    async def test_acquire_waits_when_empty(self, bucket):
        """Test that acquiring waits when bucket is empty."""
        # Drain the bucket
        await bucket.acquire(5)

        # Next acquire should wait
        start = asyncio.get_event_loop().time()
        await bucket.acquire(1)
        elapsed = asyncio.get_event_loop().time() - start

        # Should have waited for at least one token to regenerate
        assert elapsed > 0

    def test_refill_over_time(self, bucket):
        """Test that tokens refill over time."""
        # Drain some tokens (simulated by reducing _tokens)
        bucket._tokens = 0

        # Wait a bit (simulated by advancing last_update)
        import time
        bucket._last_update -= 0.5  # Simulate 0.5 seconds passing

        # Check available (triggers refill)
        available = bucket.available_tokens

        # Should have regenerated some tokens (0.5s * 10/s = 5 tokens)
        assert available > 0
