"""
Human-like interaction simulator for browser automation.

Implements Epic 9.2.4: Human-like Interaction from the Browser Infrastructure epic.

Features:
- Variable typing delays (50-150ms per character)
- Typo simulation with backspace correction
- Human pause simulation (0.3-1.5s random)
- Mouse movement with slight random offset
- Fast mode for skipping all human simulation
"""

import asyncio
import random
import logging
from dataclasses import dataclass
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class HumanSimulatorConfig:
    """Configuration for human-like interaction simulation."""

    # Typing configuration
    min_char_delay_ms: int = 50
    max_char_delay_ms: int = 150
    typo_rate: float = 0.05  # 5% chance of typo per character
    typo_correction_delay_ms: int = 100  # Delay before correcting typo

    # Pause configuration
    min_pause_seconds: float = 0.3
    max_pause_seconds: float = 1.5

    # Click configuration
    pre_click_delay_ms: int = 100
    max_click_offset_px: int = 3  # Random offset added to click position

    # Mouse movement configuration
    mouse_move_steps: int = 10  # Number of intermediate steps in mouse movement
    mouse_move_jitter_px: int = 2  # Random jitter added to each step

    # Mode flags
    fast_mode: bool = False  # Skip all human simulation when True


# Common typo character substitutions
TYPO_SUBSTITUTIONS = {
    'a': ['s', 'q', 'z'],
    'b': ['v', 'n', 'g'],
    'c': ['x', 'v', 'd'],
    'd': ['s', 'f', 'e'],
    'e': ['w', 'r', 'd'],
    'f': ['d', 'g', 'r'],
    'g': ['f', 'h', 't'],
    'h': ['g', 'j', 'y'],
    'i': ['u', 'o', 'k'],
    'j': ['h', 'k', 'u'],
    'k': ['j', 'l', 'i'],
    'l': ['k', ';', 'o'],
    'm': ['n', ',', 'j'],
    'n': ['b', 'm', 'h'],
    'o': ['i', 'p', 'l'],
    'p': ['o', '[', ';'],
    'q': ['w', 'a', '1'],
    'r': ['e', 't', 'f'],
    's': ['a', 'd', 'w'],
    't': ['r', 'y', 'g'],
    'u': ['y', 'i', 'j'],
    'v': ['c', 'b', 'f'],
    'w': ['q', 'e', 's'],
    'x': ['z', 'c', 's'],
    'y': ['t', 'u', 'h'],
    'z': ['a', 'x', 's'],
    '1': ['2', 'q'],
    '2': ['1', '3', 'w'],
    '3': ['2', '4', 'e'],
    '4': ['3', '5', 'r'],
    '5': ['4', '6', 't'],
    '6': ['5', '7', 'y'],
    '7': ['6', '8', 'u'],
    '8': ['7', '9', 'i'],
    '9': ['8', '0', 'o'],
    '0': ['9', '-', 'p'],
}


class HumanSimulator:
    """
    Simulates human-like interactions for browser automation.

    Usage:
        simulator = HumanSimulator()

        # Type with human-like delays and occasional typos
        await simulator.type_text(page, "#email", "user@example.com")

        # Click with mouse movement
        await simulator.click_element(page, "#submit-button")

        # Add a thinking pause
        await simulator.human_pause()
    """

    def __init__(self, config: Optional[HumanSimulatorConfig] = None):
        """
        Initialize the human simulator.

        Args:
            config: Configuration options. Uses defaults if not provided.
        """
        self.config = config or HumanSimulatorConfig()
        self._rng = random.Random()

    def _get_char_delay(self) -> float:
        """Get random delay between characters in seconds."""
        delay_ms = self._rng.uniform(
            self.config.min_char_delay_ms,
            self.config.max_char_delay_ms
        )
        return delay_ms / 1000.0

    def _should_make_typo(self) -> bool:
        """Determine if a typo should occur based on typo_rate."""
        return self._rng.random() < self.config.typo_rate

    def _get_typo_char(self, char: str) -> str:
        """Get a typo character for the given character."""
        lower_char = char.lower()
        if lower_char in TYPO_SUBSTITUTIONS:
            typo = self._rng.choice(TYPO_SUBSTITUTIONS[lower_char])
            # Preserve case
            return typo.upper() if char.isupper() else typo
        # If no substitution available, return a random adjacent key
        return char  # Fallback: no typo

    async def type_text(
        self,
        page,
        selector: str,
        text: str,
        clear_first: bool = True,
    ) -> Tuple[int, int]:
        """
        Type text with human-like characteristics.

        Args:
            page: Playwright page object
            selector: CSS selector for the input element
            text: Text to type
            clear_first: Clear the field before typing

        Returns:
            Tuple of (total_chars_typed, typos_made)
        """
        if self.config.fast_mode:
            # Fast mode: immediate typing, no human simulation
            element = await page.query_selector(selector)
            if element:
                if clear_first:
                    await element.fill("")
                await element.type(text)
            return len(text), 0

        element = await page.query_selector(selector)
        if not element:
            logger.warning(f"Element not found: {selector}")
            return 0, 0

        if clear_first:
            await element.fill("")

        typos_made = 0
        chars_typed = 0

        for char in text:
            # Check for typo
            if self._should_make_typo() and char.isalnum():
                typo_char = self._get_typo_char(char)
                if typo_char != char:
                    # Type the wrong character
                    await element.type(typo_char)
                    await asyncio.sleep(self._get_char_delay())

                    # Pause before realizing mistake
                    await asyncio.sleep(self.config.typo_correction_delay_ms / 1000.0)

                    # Backspace to correct
                    await element.press("Backspace")
                    await asyncio.sleep(self._get_char_delay())

                    typos_made += 1

            # Type the correct character
            await element.type(char)
            chars_typed += 1

            # Variable delay between characters
            await asyncio.sleep(self._get_char_delay())

        logger.debug(f"Typed {chars_typed} chars with {typos_made} typos: {selector}")
        return chars_typed, typos_made

    async def human_pause(self, reason: str = "thinking") -> float:
        """
        Pause for a human-like duration.

        Args:
            reason: Reason for the pause (for logging)

        Returns:
            Actual pause duration in seconds
        """
        if self.config.fast_mode:
            return 0.0

        pause_duration = self._rng.uniform(
            self.config.min_pause_seconds,
            self.config.max_pause_seconds
        )
        logger.debug(f"Human pause ({reason}): {pause_duration:.2f}s")
        await asyncio.sleep(pause_duration)
        return pause_duration

    async def click_element(
        self,
        page,
        selector: str,
        move_mouse: bool = True,
    ) -> bool:
        """
        Click an element with human-like mouse movement.

        Args:
            page: Playwright page object
            selector: CSS selector for the element
            move_mouse: Whether to move mouse before clicking

        Returns:
            True if click was successful
        """
        element = await page.query_selector(selector)
        if not element:
            logger.warning(f"Element not found for click: {selector}")
            return False

        if self.config.fast_mode:
            await element.click()
            return True

        # Get element bounding box
        box = await element.bounding_box()
        if not box:
            # Fallback to simple click if bounding box not available
            await element.click()
            return True

        # Calculate target position with slight random offset
        offset_x = self._rng.uniform(-self.config.max_click_offset_px, self.config.max_click_offset_px)
        offset_y = self._rng.uniform(-self.config.max_click_offset_px, self.config.max_click_offset_px)

        target_x = box['x'] + box['width'] / 2 + offset_x
        target_y = box['y'] + box['height'] / 2 + offset_y

        if move_mouse:
            # Move mouse to element with intermediate steps
            await self._move_mouse_to(page, target_x, target_y)

        # Small delay before click
        await asyncio.sleep(self.config.pre_click_delay_ms / 1000.0)

        # Click at the target position
        await page.mouse.click(target_x, target_y)

        logger.debug(f"Clicked element: {selector}")
        return True

    async def _move_mouse_to(
        self,
        page,
        target_x: float,
        target_y: float,
    ) -> None:
        """
        Move mouse to target position with human-like movement.

        Args:
            page: Playwright page object
            target_x: Target X coordinate
            target_y: Target Y coordinate
        """
        # Get current mouse position (start from viewport center if unknown)
        viewport = page.viewport_size
        start_x = viewport['width'] / 2 if viewport else 500
        start_y = viewport['height'] / 2 if viewport else 300

        steps = self.config.mouse_move_steps

        for i in range(1, steps + 1):
            # Linear interpolation with jitter
            progress = i / steps
            x = start_x + (target_x - start_x) * progress
            y = start_y + (target_y - start_y) * progress

            # Add jitter (less jitter near the end for accuracy)
            jitter_factor = 1 - progress  # Reduces as we approach target
            jitter_x = self._rng.uniform(
                -self.config.mouse_move_jitter_px,
                self.config.mouse_move_jitter_px
            ) * jitter_factor
            jitter_y = self._rng.uniform(
                -self.config.mouse_move_jitter_px,
                self.config.mouse_move_jitter_px
            ) * jitter_factor

            await page.mouse.move(x + jitter_x, y + jitter_y)

            # Small delay between steps
            await asyncio.sleep(0.01)

    async def scroll_like_human(
        self,
        page,
        direction: str = "down",
        amount: int = 300,
    ) -> None:
        """
        Scroll the page with human-like behavior.

        Args:
            page: Playwright page object
            direction: "up" or "down"
            amount: Scroll amount in pixels
        """
        if self.config.fast_mode:
            scroll_amount = -amount if direction == "up" else amount
            await page.evaluate(f"window.scrollBy(0, {scroll_amount})")
            return

        # Scroll in smaller increments
        steps = self._rng.randint(3, 6)
        step_amount = amount // steps

        for _ in range(steps):
            scroll_amount = -step_amount if direction == "up" else step_amount
            # Add some variation
            variation = self._rng.uniform(0.8, 1.2)
            actual_scroll = int(scroll_amount * variation)

            await page.evaluate(f"window.scrollBy(0, {actual_scroll})")
            await asyncio.sleep(self._rng.uniform(0.05, 0.15))

        logger.debug(f"Scrolled {direction} ~{amount}px in {steps} steps")


# Convenience function for quick access
def create_human_simulator(
    fast_mode: bool = False,
    typo_rate: float = 0.05,
) -> HumanSimulator:
    """
    Create a configured HumanSimulator instance.

    Args:
        fast_mode: Skip all human simulation (for testing)
        typo_rate: Probability of typo per character (0.0 to 1.0)

    Returns:
        Configured HumanSimulator instance
    """
    config = HumanSimulatorConfig(
        fast_mode=fast_mode,
        typo_rate=typo_rate,
    )
    return HumanSimulator(config)


def create_human_simulator_from_thresholds(thresholds) -> HumanSimulator:
    """
    Create a HumanSimulator from AnalysisThresholds configuration.

    This allows all human simulation parameters to be configured via
    config.py or environment variables (SEO_THRESHOLD_HUMAN_SIM_*).

    Args:
        thresholds: AnalysisThresholds instance with human_sim_* fields

    Returns:
        Configured HumanSimulator instance
    """
    config = HumanSimulatorConfig(
        min_char_delay_ms=getattr(thresholds, 'human_sim_min_char_delay_ms', 50),
        max_char_delay_ms=getattr(thresholds, 'human_sim_max_char_delay_ms', 150),
        typo_rate=getattr(thresholds, 'human_sim_typo_rate', 0.05),
        typo_correction_delay_ms=getattr(thresholds, 'human_sim_typo_correction_delay_ms', 100),
        min_pause_seconds=getattr(thresholds, 'human_sim_min_pause_seconds', 0.3),
        max_pause_seconds=getattr(thresholds, 'human_sim_max_pause_seconds', 1.5),
        pre_click_delay_ms=getattr(thresholds, 'human_sim_pre_click_delay_ms', 100),
        max_click_offset_px=getattr(thresholds, 'human_sim_max_click_offset_px', 3),
        mouse_move_steps=getattr(thresholds, 'human_sim_mouse_move_steps', 10),
        mouse_move_jitter_px=getattr(thresholds, 'human_sim_mouse_move_jitter_px', 2),
        fast_mode=getattr(thresholds, 'human_sim_fast_mode', False),
    )
    return HumanSimulator(config)
