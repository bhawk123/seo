"""
Browser configuration for Playwright-based crawling.

This module provides a validated Pydantic configuration model for all browser-related
settings and pre-configured instances for common use cases.
"""
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


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

    class Config:
        """Pydantic model configuration."""
        frozen = False
        validate_assignment = True


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
