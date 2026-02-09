"""
Adaptive Rate Limiter.

Ported from Spectrum per EPIC-SEO-INFRA-001 (STORY-INFRA-002).

This module provides intelligent rate limiting that adapts to server
response times and error rates.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Deque
from collections import deque

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Configuration for rate limiter."""
    # Base delay between requests (seconds)
    base_delay: float = 1.0

    # Minimum delay (even under ideal conditions)
    min_delay: float = 0.5

    # Maximum delay (under worst conditions)
    max_delay: float = 10.0

    # Target response time (seconds) - we'll slow down if exceeded
    target_response_time: float = 2.0

    # Error rate threshold - above this we slow down significantly
    error_rate_threshold: float = 0.1

    # Window size for calculating moving averages
    window_size: int = 20

    # Backoff multiplier when errors occur
    error_backoff_multiplier: float = 2.0

    # Recovery multiplier when things are going well
    success_recovery_multiplier: float = 0.9


@dataclass
class ResourceMetrics:
    """Current resource usage metrics."""
    current_delay: float
    avg_response_time: float
    error_rate: float
    requests_in_window: int
    errors_in_window: int
    last_request_time: datetime | None
    total_requests: int
    total_errors: int
    total_wait_time: float


@dataclass
class RequestRecord:
    """Record of a single request for metrics calculation."""
    timestamp: datetime
    response_time: float  # seconds
    success: bool


class AdaptiveRateLimiter:
    """
    Adaptive rate limiter that adjusts based on server response.

    Features:
    - Adaptive delay based on response times
    - Automatic backoff on errors
    - Gradual recovery when conditions improve
    - Resource monitoring
    """

    def __init__(self, config: RateLimitConfig | None = None):
        """
        Initialize rate limiter.

        Args:
            config: Rate limit configuration
        """
        self.config = config or RateLimitConfig()

        self._current_delay = self.config.base_delay
        self._last_request_time: float | None = None
        self._request_history: Deque[RequestRecord] = deque(
            maxlen=self.config.window_size
        )
        self._lock = asyncio.Lock()

        # Statistics
        self._total_requests = 0
        self._total_errors = 0
        self._total_wait_time = 0.0

    async def wait(self) -> float:
        """
        Wait for rate limit delay.

        Returns:
            Actual time waited (seconds)
        """
        async with self._lock:
            now = time.time()

            # Calculate time since last request
            if self._last_request_time is not None:
                elapsed = now - self._last_request_time
                wait_time = max(0, self._current_delay - elapsed)
            else:
                wait_time = 0

            if wait_time > 0:
                await asyncio.sleep(wait_time)
                self._total_wait_time += wait_time

            self._last_request_time = time.time()
            return wait_time

    def record_request(
        self,
        response_time: float,
        success: bool = True,
    ) -> None:
        """
        Record a completed request for metrics.

        Args:
            response_time: Time taken for request (seconds)
            success: Whether request was successful
        """
        record = RequestRecord(
            timestamp=datetime.now(),
            response_time=response_time,
            success=success,
        )

        self._request_history.append(record)
        self._total_requests += 1

        if not success:
            self._total_errors += 1

        # Adjust delay based on new data
        self._adjust_delay()

    def _adjust_delay(self) -> None:
        """
        Adjust delay based on recent request history.
        """
        if len(self._request_history) < 3:
            return  # Not enough data

        # Calculate metrics from recent history
        recent = list(self._request_history)
        avg_response_time = sum(r.response_time for r in recent) / len(recent)
        error_count = sum(1 for r in recent if not r.success)
        error_rate = error_count / len(recent)

        # Determine adjustment
        new_delay = self._current_delay

        # Error-based adjustment (highest priority)
        if error_rate > self.config.error_rate_threshold:
            # Significant errors - back off
            new_delay *= self.config.error_backoff_multiplier
            logger.debug(
                f"Rate limiter: errors high ({error_rate:.2%}), "
                f"backing off to {new_delay:.2f}s"
            )

        # Response time adjustment
        elif avg_response_time > self.config.target_response_time:
            # Server is slow - increase delay proportionally
            ratio = avg_response_time / self.config.target_response_time
            new_delay *= min(ratio, 2.0)  # Cap at 2x increase
            logger.debug(
                f"Rate limiter: response time high ({avg_response_time:.2f}s), "
                f"increasing to {new_delay:.2f}s"
            )

        # Recovery adjustment (when things are going well)
        elif error_rate == 0 and avg_response_time < self.config.target_response_time * 0.5:
            # Everything is great - gradually speed up
            new_delay *= self.config.success_recovery_multiplier
            logger.debug(
                f"Rate limiter: conditions good, "
                f"recovering to {new_delay:.2f}s"
            )

        # Apply bounds
        self._current_delay = max(
            self.config.min_delay,
            min(self.config.max_delay, new_delay)
        )

    def get_metrics(self) -> ResourceMetrics:
        """
        Get current resource metrics.

        Returns:
            ResourceMetrics snapshot
        """
        recent = list(self._request_history)

        if recent:
            avg_response_time = sum(r.response_time for r in recent) / len(recent)
            errors = sum(1 for r in recent if not r.success)
            error_rate = errors / len(recent)
        else:
            avg_response_time = 0.0
            errors = 0
            error_rate = 0.0

        return ResourceMetrics(
            current_delay=self._current_delay,
            avg_response_time=avg_response_time,
            error_rate=error_rate,
            requests_in_window=len(recent),
            errors_in_window=errors,
            last_request_time=datetime.fromtimestamp(self._last_request_time)
                if self._last_request_time else None,
            total_requests=self._total_requests,
            total_errors=self._total_errors,
            total_wait_time=self._total_wait_time,
        )

    def reset(self) -> None:
        """Reset rate limiter to initial state."""
        self._current_delay = self.config.base_delay
        self._last_request_time = None
        self._request_history.clear()
        self._total_requests = 0
        self._total_errors = 0
        self._total_wait_time = 0.0

    @property
    def current_delay(self) -> float:
        """Current delay between requests."""
        return self._current_delay

    @property
    def error_rate(self) -> float:
        """Current error rate from recent history."""
        if not self._request_history:
            return 0.0
        errors = sum(1 for r in self._request_history if not r.success)
        return errors / len(self._request_history)


class TokenBucketLimiter:
    """
    Token bucket rate limiter for burst handling.

    Allows short bursts while maintaining average rate.
    """

    def __init__(
        self,
        rate: float = 1.0,  # Tokens per second
        capacity: int = 5,  # Max burst size
    ):
        """
        Initialize token bucket.

        Args:
            rate: Token generation rate (per second)
            capacity: Maximum tokens in bucket
        """
        self.rate = rate
        self.capacity = capacity
        self._tokens = capacity
        self._last_update = time.time()
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: int = 1) -> float:
        """
        Acquire tokens, waiting if necessary.

        Args:
            tokens: Number of tokens to acquire

        Returns:
            Time waited (seconds)
        """
        async with self._lock:
            wait_time = 0.0

            while True:
                self._refill()

                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return wait_time

                # Calculate wait time for enough tokens
                needed = tokens - self._tokens
                wait = needed / self.rate

                await asyncio.sleep(wait)
                wait_time += wait

    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self._last_update

        # Add tokens based on elapsed time
        new_tokens = elapsed * self.rate
        self._tokens = min(self.capacity, self._tokens + new_tokens)
        self._last_update = now

    @property
    def available_tokens(self) -> float:
        """Current available tokens."""
        self._refill()
        return self._tokens
