"""
Browser configuration for Playwright-based crawling.

This module provides a validated Pydantic configuration model for all browser-related
settings and pre-configured instances for common use cases.

Enhanced with stealth features ported from Spectrum per EPIC-SEO-INFRA-001.
"""
import random
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


# User agent pool for rotation (ported from Spectrum)
USER_AGENTS = [
    # Chrome on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    # Chrome on Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    # Firefox on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    # Firefox on Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
    # Safari on Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
]


def get_random_user_agent() -> str:
    """Get a random user agent from the pool."""
    return random.choice(USER_AGENTS)


class BrowserConfig(BaseModel):
    """
    Configuration for the Playwright-based BrowserCrawler.

    All fields are validated by Pydantic to ensure type safety and valid values.
    """

    headless: bool = Field(
        default=True,
        description="Run browser in headless mode (no visible UI)"
    )

    stealth_mode: bool = Field(
        default=True,
        description="Apply anti-detection measures to avoid bot blocking"
    )

    stealth_backend: Literal["playwright", "undetected"] = Field(
        default="playwright",
        description="Browser backend: 'playwright' for Playwright with stealth, 'undetected' for undetected-chromedriver"
    )

    chrome_version_main: Optional[int] = Field(
        default=None,
        description="Chrome major version for undetected-chromedriver (e.g., 120). None for auto-detect."
    )

    browser_type: Literal["chromium", "firefox", "webkit"] = Field(
        default="chromium",
        description="Browser engine to use for crawling"
    )

    timeout: int = Field(
        default=30000,
        description="Page load timeout in milliseconds",
        ge=1000,
        le=300000
    )

    wait_until: Literal["load", "domcontentloaded", "networkidle", "commit"] = Field(
        default="networkidle",
        description="When to consider navigation complete"
    )

    mobile: bool = Field(
        default=False,
        description="Use mobile viewport and user agent"
    )

    capture_screenshots: bool = Field(
        default=False,
        description="Capture screenshot of each crawled page"
    )

    capture_network: bool = Field(
        default=False,
        description="Log all network requests made by the page"
    )

    block_resources: List[str] = Field(
        default_factory=list,
        description="Resource types to block (e.g., 'image', 'font', 'stylesheet')"
    )

    launch_args: List[str] = Field(
        default_factory=list,
        description="Additional browser launch arguments (e.g., '--disable-http2')"
    )

    # Stealth options (ported from Spectrum per EPIC-SEO-INFRA-001)
    user_agent: Optional[str] = Field(
        default=None,
        description="Custom user agent. If None and rotate_user_agent=True, a random one is used."
    )

    rotate_user_agent: bool = Field(
        default=True,
        description="Rotate user agent on each new context"
    )

    disable_webrtc: bool = Field(
        default=True,
        description="Disable WebRTC to prevent IP leakage"
    )

    challenge_detection: bool = Field(
        default=True,
        description="Enable CAPTCHA/challenge detection and pause for human intervention"
    )

    challenge_auto_timeout: float = Field(
        default=5.0,
        description="Seconds to wait for challenges to auto-resolve before pausing"
    )

    class Config:
        """Pydantic model configuration."""
        frozen = False
        validate_assignment = True

    def get_user_agent(self) -> str:
        """Get the user agent to use for this config."""
        if self.user_agent:
            return self.user_agent
        if self.rotate_user_agent:
            return get_random_user_agent()
        return USER_AGENTS[0]  # Default to first agent


# --- Pre-configured Instances for Common Use Cases ---

FAST_CONFIG = BrowserConfig(
    headless=True,
    stealth_mode=True,
    wait_until="domcontentloaded",
    timeout=15000,
    capture_screenshots=False,
    capture_network=False,
    block_resources=["image", "font", "stylesheet", "media"],
)
"""
Fast configuration optimized for speed.

Blocks heavy resources and uses faster page load detection.
Best for crawling many pages quickly when full rendering isn't needed.
"""

FULL_CONFIG = BrowserConfig(
    headless=False,
    stealth_mode=True,
    wait_until="networkidle",
    timeout=30000,
    capture_screenshots=True,
    capture_network=True,
    block_resources=[],
)
"""
Full configuration for comprehensive debugging and analysis.

Runs with visible browser, captures screenshots and network activity.
Best for debugging crawl issues or detailed page analysis.
"""

STEALTH_CONFIG = BrowserConfig(
    headless=True,
    stealth_mode=True,
    wait_until="networkidle",
    timeout=45000,
    capture_screenshots=False,
    capture_network=False,
    block_resources=[],
    rotate_user_agent=True,
    disable_webrtc=True,
    challenge_detection=True,
    launch_args=[
        "--disable-http2",  # Bypass HTTP/2 fingerprinting
        "--disable-blink-features=AutomationControlled",
        "--disable-features=IsolateOrigins,site-per-process",
        "--no-first-run",
        "--no-default-browser-check",
    ],
)
"""
Stealth configuration optimized for avoiding bot detection.

Uses longer timeouts and full stealth measures.
Best for crawling sites with aggressive anti-bot protection.
"""


# Enhanced stealth config using Playwright with maximum stealth flags
UNDETECTED_PLAYWRIGHT_CONFIG = BrowserConfig(
    headless=True,
    stealth_mode=True,
    stealth_backend="playwright",
    wait_until="networkidle",
    timeout=60000,  # Longer timeout for heavily protected sites
    capture_screenshots=False,
    capture_network=True,  # Enable for API capture like Spectrum
    block_resources=[],
    rotate_user_agent=True,
    disable_webrtc=True,
    challenge_detection=True,
    challenge_auto_timeout=5.0,
    launch_args=[
        # Core anti-detection
        "--disable-blink-features=AutomationControlled",
        "--disable-features=IsolateOrigins,site-per-process",
        # Fingerprint evasion
        "--disable-http2",
        "--disable-quic",
        "--disable-features=TranslateUI",
        # Reduce automation signals
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-background-networking",
        "--disable-sync",
        # GPU/rendering (match real browser)
        "--disable-gpu",
        "--no-sandbox",
        "--disable-dev-shm-usage",
        # Window size (common resolution)
        "--window-size=1920,1080",
    ],
)
"""
Playwright with maximum stealth flags.

Best for sites with moderate anti-bot protection.
"""

# True undetected configuration using undetected-chromedriver backend (Epic 9.2.1)
UNDETECTED_CONFIG = BrowserConfig(
    headless=True,
    stealth_mode=True,
    stealth_backend="undetected",
    chrome_version_main=None,  # Auto-detect Chrome version
    wait_until="networkidle",
    timeout=60000,  # Longer timeout for heavily protected sites
    capture_screenshots=False,
    capture_network=True,
    block_resources=[],
    rotate_user_agent=True,
    disable_webrtc=True,
    challenge_detection=True,
    challenge_auto_timeout=5.0,
    launch_args=[],  # undetected-chromedriver handles args internally
)
"""
Undetected configuration - maximum stealth for bot-protected sites.

Uses undetected-chromedriver (or nodriver) backend instead of Playwright.
Features:
- Chrome driver patching to avoid detection
- Automatic stealth script injection
- navigator.webdriver = undefined
- Realistic browser plugins and runtime
- User agent rotation
- CAPTCHA/challenge detection with human intervention

Best for sites with Akamai, Cloudflare, PerimeterX, or similar protection.
Requires: pip install nodriver  OR  pip install undetected-chromedriver
"""
