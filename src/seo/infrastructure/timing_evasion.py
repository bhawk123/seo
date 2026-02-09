"""
Request Timing Signature Evasion.

Implements Critical Gap #7: Request timing signature evasion.

Automated browsers often have predictable timing patterns that can be detected:
- Perfectly consistent delays between requests
- Uniform click/type timing
- No natural variation in behavior

This module provides timing randomization to appear more human-like:
- Variable inter-request delays with natural distribution
- Humanized navigation timing
- Random jitter for all operations
- Session-based timing profiles
- Circadian rhythm simulation (optional)

Features ported from Spectrum per EPIC-SEO-INFRA-001.
"""

import asyncio
import logging
import math
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, List, Optional, Tuple

logger = logging.getLogger(__name__)


class TimingProfile(str, Enum):
    """Predefined timing profiles."""
    FAST = "fast"  # Quick but still human-like
    NORMAL = "normal"  # Average user speed
    SLOW = "slow"  # Careful/slow user
    CAUTIOUS = "cautious"  # Very slow, careful navigation
    RANDOM = "random"  # Mix of profiles


@dataclass
class TimingConfig:
    """Configuration for timing evasion."""
    # Base delays (seconds)
    min_page_delay: float = 0.5
    max_page_delay: float = 3.0
    min_click_delay: float = 0.1
    max_click_delay: float = 0.5
    min_type_delay: float = 0.05
    max_type_delay: float = 0.2

    # Jitter settings
    jitter_factor: float = 0.2  # Max percentage variation
    enable_gaussian: bool = True  # Use gaussian distribution

    # Session variation
    session_speed_variation: float = 0.3  # Per-session speed modifier

    # Circadian simulation
    enable_circadian: bool = False
    peak_hours: Tuple[int, int] = (9, 17)  # Hours of peak activity
    off_peak_slowdown: float = 1.5  # Multiplier during off-peak

    # Fatigue simulation
    enable_fatigue: bool = False
    fatigue_after_requests: int = 50
    fatigue_slowdown: float = 1.3

    # Burst behavior
    enable_burst: bool = True
    burst_probability: float = 0.1  # Chance of fast burst
    burst_speedup: float = 0.5  # Speed multiplier during burst


class TimingEvasion:
    """
    Request timing signature evasion.

    Provides human-like timing variation to avoid bot detection.
    """

    def __init__(self, config: Optional[TimingConfig] = None, profile: TimingProfile = TimingProfile.NORMAL):
        self.config = config or TimingConfig()
        self.profile = profile
        self._session_modifier = self._generate_session_modifier()
        self._request_count = 0
        self._last_request_time = 0.0
        self._in_burst = False
        self._burst_remaining = 0

        # Profile-based speed modifiers
        self._profile_modifiers = {
            TimingProfile.FAST: 0.5,
            TimingProfile.NORMAL: 1.0,
            TimingProfile.SLOW: 1.8,
            TimingProfile.CAUTIOUS: 3.0,
            TimingProfile.RANDOM: 1.0,  # Will vary per request
        }

    def _generate_session_modifier(self) -> float:
        """Generate a per-session speed modifier."""
        variation = self.config.session_speed_variation
        return 1.0 + random.uniform(-variation, variation)

    def _get_profile_modifier(self) -> float:
        """Get current profile speed modifier."""
        if self.profile == TimingProfile.RANDOM:
            # Random profile per request
            profiles = [TimingProfile.FAST, TimingProfile.NORMAL, TimingProfile.SLOW]
            weights = [0.2, 0.6, 0.2]  # Favor normal speed
            chosen = random.choices(profiles, weights=weights)[0]
            return self._profile_modifiers[chosen]
        return self._profile_modifiers[self.profile]

    def _apply_jitter(self, value: float) -> float:
        """Apply random jitter to a value."""
        if self.config.enable_gaussian:
            # Gaussian distribution centered on value
            std_dev = value * self.config.jitter_factor
            return max(0, random.gauss(value, std_dev))
        else:
            # Uniform distribution
            jitter_range = value * self.config.jitter_factor
            return value + random.uniform(-jitter_range, jitter_range)

    def _get_circadian_modifier(self) -> float:
        """Get modifier based on time of day."""
        if not self.config.enable_circadian:
            return 1.0

        hour = time.localtime().tm_hour
        start, end = self.config.peak_hours

        if start <= hour < end:
            return 1.0  # Peak hours, normal speed
        else:
            return self.config.off_peak_slowdown  # Slower during off-peak

    def _get_fatigue_modifier(self) -> float:
        """Get modifier based on request fatigue."""
        if not self.config.enable_fatigue:
            return 1.0

        if self._request_count > self.config.fatigue_after_requests:
            # Gradually slow down
            excess = self._request_count - self.config.fatigue_after_requests
            factor = min(self.config.fatigue_slowdown, 1.0 + (excess / 100))
            return factor

        return 1.0

    def _check_burst(self) -> float:
        """Check and update burst state, return speed modifier."""
        if not self.config.enable_burst:
            return 1.0

        if self._in_burst:
            self._burst_remaining -= 1
            if self._burst_remaining <= 0:
                self._in_burst = False
                logger.debug("Burst ended")
            return self.config.burst_speedup

        # Check for new burst
        if random.random() < self.config.burst_probability:
            self._in_burst = True
            self._burst_remaining = random.randint(3, 8)
            logger.debug(f"Starting burst of {self._burst_remaining} requests")
            return self.config.burst_speedup

        return 1.0

    def _calculate_delay(self, min_delay: float, max_delay: float) -> float:
        """Calculate final delay with all modifiers."""
        # Base delay
        base = random.uniform(min_delay, max_delay)

        # Apply modifiers
        delay = base
        delay *= self._session_modifier
        delay *= self._get_profile_modifier()
        delay *= self._get_circadian_modifier()
        delay *= self._get_fatigue_modifier()
        delay *= self._check_burst()

        # Apply jitter
        delay = self._apply_jitter(delay)

        # Ensure minimum delay
        return max(0.01, delay)

    async def wait_between_pages(self) -> float:
        """
        Wait appropriate time between page navigations.

        Returns:
            Actual delay in seconds
        """
        delay = self._calculate_delay(
            self.config.min_page_delay,
            self.config.max_page_delay
        )
        self._request_count += 1
        self._last_request_time = time.time()

        logger.debug(f"Page delay: {delay:.2f}s (request #{self._request_count})")
        await asyncio.sleep(delay)
        return delay

    async def wait_before_click(self) -> float:
        """
        Wait before clicking an element.

        Returns:
            Actual delay in seconds
        """
        delay = self._calculate_delay(
            self.config.min_click_delay,
            self.config.max_click_delay
        )

        logger.debug(f"Click delay: {delay:.3f}s")
        await asyncio.sleep(delay)
        return delay

    async def wait_between_keystrokes(self) -> float:
        """
        Wait between individual keystrokes.

        Returns:
            Actual delay in seconds
        """
        delay = self._calculate_delay(
            self.config.min_type_delay,
            self.config.max_type_delay
        )

        await asyncio.sleep(delay)
        return delay

    def get_type_delays(self, text: str) -> List[float]:
        """
        Get a list of delays for typing a string.

        Creates natural typing pattern with variable speeds
        for different character types.

        Args:
            text: Text to type

        Returns:
            List of delays (one per character)
        """
        delays = []
        prev_char = None

        for char in text:
            base_delay = random.uniform(
                self.config.min_type_delay,
                self.config.max_type_delay
            )

            # Adjust for character type
            if char == ' ':
                # Slightly longer pause after words
                base_delay *= 1.3
            elif char in '.,!?':
                # Longer pause after punctuation
                base_delay *= 1.5
            elif char.isupper():
                # Longer for capitals (shift key)
                base_delay *= 1.2
            elif char.isdigit():
                # Numbers take longer
                base_delay *= 1.1

            # Repeated characters are faster
            if prev_char == char:
                base_delay *= 0.7

            delays.append(self._apply_jitter(base_delay))
            prev_char = char

        return delays

    def get_mouse_movement_points(
        self,
        start: Tuple[float, float],
        end: Tuple[float, float],
        steps: int = 10
    ) -> List[Tuple[float, float]]:
        """
        Generate human-like mouse movement path.

        Uses bezier curve with random control points for natural movement.

        Args:
            start: Starting (x, y) position
            end: Target (x, y) position
            steps: Number of intermediate points

        Returns:
            List of (x, y) points along the path
        """
        x1, y1 = start
        x2, y2 = end

        # Generate control points for bezier curve
        # Add some randomness to make it curved
        distance = math.sqrt((x2 - x1)**2 + (y2 - y1)**2)

        # Control point offset based on distance
        offset = distance * random.uniform(0.1, 0.3)

        # Random control point
        cx = (x1 + x2) / 2 + random.uniform(-offset, offset)
        cy = (y1 + y2) / 2 + random.uniform(-offset, offset)

        points = []
        for i in range(steps + 1):
            t = i / steps

            # Quadratic bezier curve
            x = (1 - t)**2 * x1 + 2 * (1 - t) * t * cx + t**2 * x2
            y = (1 - t)**2 * y1 + 2 * (1 - t) * t * cy + t**2 * y2

            # Add micro-jitter
            jitter = 2  # pixels
            x += random.uniform(-jitter, jitter)
            y += random.uniform(-jitter, jitter)

            points.append((x, y))

        return points

    def get_scroll_pattern(self, total_distance: int) -> List[Tuple[int, float]]:
        """
        Generate human-like scroll pattern.

        Returns variable scroll amounts with pauses.

        Args:
            total_distance: Total pixels to scroll

        Returns:
            List of (scroll_amount, delay) tuples
        """
        pattern = []
        remaining = total_distance
        direction = 1 if total_distance > 0 else -1

        while abs(remaining) > 0:
            # Variable scroll amount (100-400 pixels typical)
            max_scroll = min(abs(remaining), random.randint(100, 400))
            scroll = direction * max_scroll

            # Variable delay (humans pause while reading)
            if random.random() < 0.3:
                # Longer pause (reading)
                delay = random.uniform(0.5, 2.0)
            else:
                # Quick scroll
                delay = random.uniform(0.05, 0.2)

            pattern.append((scroll, delay))
            remaining -= scroll

        return pattern

    def reset_session(self) -> None:
        """Reset session state for a new browsing session."""
        self._session_modifier = self._generate_session_modifier()
        self._request_count = 0
        self._last_request_time = 0.0
        self._in_burst = False
        self._burst_remaining = 0
        logger.debug("Timing session reset")

    def get_stats(self) -> dict:
        """Get timing statistics."""
        return {
            "profile": self.profile.value,
            "session_modifier": self._session_modifier,
            "request_count": self._request_count,
            "in_burst": self._in_burst,
            "fatigue_active": self._request_count > self.config.fatigue_after_requests,
        }


# Profile presets
TIMING_PROFILES = {
    TimingProfile.FAST: TimingConfig(
        min_page_delay=0.3,
        max_page_delay=1.5,
        min_click_delay=0.05,
        max_click_delay=0.2,
        enable_fatigue=False,
        enable_burst=True,
    ),
    TimingProfile.NORMAL: TimingConfig(
        min_page_delay=0.5,
        max_page_delay=3.0,
        min_click_delay=0.1,
        max_click_delay=0.5,
        enable_fatigue=True,
    ),
    TimingProfile.SLOW: TimingConfig(
        min_page_delay=1.5,
        max_page_delay=5.0,
        min_click_delay=0.3,
        max_click_delay=1.0,
        enable_fatigue=True,
        enable_circadian=True,
    ),
    TimingProfile.CAUTIOUS: TimingConfig(
        min_page_delay=3.0,
        max_page_delay=10.0,
        min_click_delay=0.5,
        max_click_delay=2.0,
        enable_fatigue=True,
        enable_circadian=True,
        enable_burst=False,
    ),
}


def create_timing_evasion(profile: TimingProfile = TimingProfile.NORMAL) -> TimingEvasion:
    """
    Create a TimingEvasion instance with a preset profile.

    Args:
        profile: Timing profile to use

    Returns:
        Configured TimingEvasion instance
    """
    config = TIMING_PROFILES.get(profile, TimingConfig())
    return TimingEvasion(config=config, profile=profile)
