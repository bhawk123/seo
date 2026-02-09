"""
Cross-Browser Testing Support.

Implements Critical Gap #3: Cross-browser testing (Chrome/Firefox/Safari).

Provides utilities for running crawls across multiple browser engines
to ensure consistent behavior and catch browser-specific issues.

Features:
- Multi-browser configuration
- Browser capability detection
- Result comparison utilities
- Browser-specific workarounds
- Parallel browser execution

Ported from Spectrum per EPIC-SEO-INFRA-001.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class BrowserEngine(str, Enum):
    """Supported browser engines."""
    CHROMIUM = "chromium"
    FIREFOX = "firefox"
    WEBKIT = "webkit"  # Safari


class BrowserCapability(str, Enum):
    """Browser capabilities that may vary."""
    WEBP_SUPPORT = "webp"
    AVIF_SUPPORT = "avif"
    CSS_GRID = "css_grid"
    CSS_SUBGRID = "css_subgrid"
    WEBGL2 = "webgl2"
    SERVICE_WORKERS = "service_workers"
    WEB_COMPONENTS = "web_components"
    INTERSECTION_OBSERVER = "intersection_observer"
    RESIZE_OBSERVER = "resize_observer"
    CSS_CONTAINER_QUERIES = "container_queries"
    CSS_HAS_SELECTOR = "css_has"
    VIEW_TRANSITIONS = "view_transitions"


# Browser capability matrix
BROWSER_CAPABILITIES: Dict[BrowserEngine, Set[BrowserCapability]] = {
    BrowserEngine.CHROMIUM: {
        BrowserCapability.WEBP_SUPPORT,
        BrowserCapability.AVIF_SUPPORT,
        BrowserCapability.CSS_GRID,
        BrowserCapability.CSS_SUBGRID,
        BrowserCapability.WEBGL2,
        BrowserCapability.SERVICE_WORKERS,
        BrowserCapability.WEB_COMPONENTS,
        BrowserCapability.INTERSECTION_OBSERVER,
        BrowserCapability.RESIZE_OBSERVER,
        BrowserCapability.CSS_CONTAINER_QUERIES,
        BrowserCapability.CSS_HAS_SELECTOR,
        BrowserCapability.VIEW_TRANSITIONS,
    },
    BrowserEngine.FIREFOX: {
        BrowserCapability.WEBP_SUPPORT,
        BrowserCapability.AVIF_SUPPORT,
        BrowserCapability.CSS_GRID,
        BrowserCapability.CSS_SUBGRID,
        BrowserCapability.WEBGL2,
        BrowserCapability.SERVICE_WORKERS,
        BrowserCapability.WEB_COMPONENTS,
        BrowserCapability.INTERSECTION_OBSERVER,
        BrowserCapability.RESIZE_OBSERVER,
        BrowserCapability.CSS_CONTAINER_QUERIES,
        BrowserCapability.CSS_HAS_SELECTOR,
        # VIEW_TRANSITIONS not fully supported in Firefox
    },
    BrowserEngine.WEBKIT: {
        BrowserCapability.WEBP_SUPPORT,
        # AVIF support limited in Safari
        BrowserCapability.CSS_GRID,
        BrowserCapability.CSS_SUBGRID,
        BrowserCapability.WEBGL2,
        BrowserCapability.SERVICE_WORKERS,
        BrowserCapability.WEB_COMPONENTS,
        BrowserCapability.INTERSECTION_OBSERVER,
        BrowserCapability.RESIZE_OBSERVER,
        BrowserCapability.CSS_CONTAINER_QUERIES,
        BrowserCapability.CSS_HAS_SELECTOR,
        # VIEW_TRANSITIONS partial in Safari
    },
}


@dataclass
class BrowserResult:
    """Result from a single browser run."""
    browser: BrowserEngine
    success: bool
    data: Any = None
    error: Optional[str] = None
    duration_ms: float = 0.0
    screenshots: List[bytes] = field(default_factory=list)
    console_logs: List[str] = field(default_factory=list)
    network_errors: List[str] = field(default_factory=list)


@dataclass
class CrossBrowserResult:
    """Combined result from all browsers."""
    results: Dict[BrowserEngine, BrowserResult] = field(default_factory=dict)
    discrepancies: List[str] = field(default_factory=list)
    all_passed: bool = True

    def add_result(self, result: BrowserResult) -> None:
        """Add a browser result."""
        self.results[result.browser] = result
        if not result.success:
            self.all_passed = False

    def check_discrepancies(self) -> List[str]:
        """Check for discrepancies between browser results."""
        discrepancies = []

        browsers = list(self.results.keys())
        if len(browsers) < 2:
            return discrepancies

        # Compare results
        reference = self.results[browsers[0]]

        for browser in browsers[1:]:
            result = self.results[browser]

            # Check success status
            if result.success != reference.success:
                discrepancies.append(
                    f"{browser.value} success={result.success} differs from "
                    f"{browsers[0].value} success={reference.success}"
                )

            # Compare data if both succeeded
            if result.success and reference.success and result.data and reference.data:
                if result.data != reference.data:
                    discrepancies.append(
                        f"{browser.value} data differs from {browsers[0].value}"
                    )

        self.discrepancies = discrepancies
        return discrepancies


@dataclass
class CrossBrowserConfig:
    """Configuration for cross-browser testing."""
    browsers: List[BrowserEngine] = field(
        default_factory=lambda: [BrowserEngine.CHROMIUM]
    )
    parallel: bool = True
    capture_screenshots: bool = False
    capture_console: bool = True
    compare_results: bool = True
    fail_on_any_error: bool = False  # Fail if any browser fails
    fail_on_discrepancy: bool = False  # Fail if results differ


class CrossBrowserRunner:
    """
    Run operations across multiple browser engines.

    Provides utilities for cross-browser testing and comparison.
    """

    def __init__(self, config: Optional[CrossBrowserConfig] = None):
        self.config = config or CrossBrowserConfig()
        self._playwright = None
        self._browsers: Dict[BrowserEngine, Any] = {}

    async def start(self) -> None:
        """Start browsers for testing."""
        try:
            from playwright.async_api import async_playwright
            self._playwright = await async_playwright().start()

            for engine in self.config.browsers:
                browser = await self._launch_browser(engine)
                if browser:
                    self._browsers[engine] = browser
                    logger.info(f"Started {engine.value} browser")
        except ImportError:
            logger.error("Playwright not installed. Run: pip install playwright")
            raise

    async def stop(self) -> None:
        """Stop all browsers."""
        for engine, browser in self._browsers.items():
            try:
                await browser.close()
                logger.debug(f"Closed {engine.value} browser")
            except Exception as e:
                logger.warning(f"Error closing {engine.value}: {e}")

        if self._playwright:
            await self._playwright.stop()

    async def _launch_browser(self, engine: BrowserEngine) -> Optional[Any]:
        """Launch a specific browser engine."""
        try:
            if engine == BrowserEngine.CHROMIUM:
                return await self._playwright.chromium.launch(headless=True)
            elif engine == BrowserEngine.FIREFOX:
                return await self._playwright.firefox.launch(headless=True)
            elif engine == BrowserEngine.WEBKIT:
                return await self._playwright.webkit.launch(headless=True)
        except Exception as e:
            logger.error(f"Failed to launch {engine.value}: {e}")
            return None

    async def run_on_browser(
        self,
        engine: BrowserEngine,
        operation: Callable,
        *args,
        **kwargs
    ) -> BrowserResult:
        """
        Run an operation on a specific browser.

        Args:
            engine: Browser engine to use
            operation: Async function to run (receives page as first arg)
            *args: Additional args for operation
            **kwargs: Additional kwargs for operation

        Returns:
            BrowserResult with operation outcome
        """
        import time

        result = BrowserResult(browser=engine, success=False)

        if engine not in self._browsers:
            result.error = f"Browser {engine.value} not started"
            return result

        browser = self._browsers[engine]
        start_time = time.time()

        try:
            context = await browser.new_context()
            page = await context.new_page()

            # Capture console if enabled
            if self.config.capture_console:
                page.on("console", lambda msg: result.console_logs.append(
                    f"[{msg.type}] {msg.text}"
                ))

            # Run the operation
            result.data = await operation(page, *args, **kwargs)
            result.success = True

            # Capture screenshot if enabled
            if self.config.capture_screenshots:
                screenshot = await page.screenshot()
                result.screenshots.append(screenshot)

            await context.close()

        except Exception as e:
            result.error = str(e)
            logger.error(f"Error in {engine.value}: {e}")

        result.duration_ms = (time.time() - start_time) * 1000
        return result

    async def run_all(
        self,
        operation: Callable,
        *args,
        **kwargs
    ) -> CrossBrowserResult:
        """
        Run an operation on all configured browsers.

        Args:
            operation: Async function to run on each browser
            *args: Additional args for operation
            **kwargs: Additional kwargs for operation

        Returns:
            CrossBrowserResult with all browser outcomes
        """
        combined = CrossBrowserResult()

        if self.config.parallel:
            # Run all browsers in parallel
            tasks = [
                self.run_on_browser(engine, operation, *args, **kwargs)
                for engine in self.config.browsers
                if engine in self._browsers
            ]
            results = await asyncio.gather(*tasks)
            for result in results:
                combined.add_result(result)
        else:
            # Run sequentially
            for engine in self.config.browsers:
                if engine in self._browsers:
                    result = await self.run_on_browser(engine, operation, *args, **kwargs)
                    combined.add_result(result)

        # Check for discrepancies
        if self.config.compare_results:
            combined.check_discrepancies()

        return combined

    async def __aenter__(self):
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.stop()


def has_capability(engine: BrowserEngine, capability: BrowserCapability) -> bool:
    """
    Check if a browser engine has a specific capability.

    Args:
        engine: Browser engine to check
        capability: Capability to check for

    Returns:
        True if capability is supported
    """
    return capability in BROWSER_CAPABILITIES.get(engine, set())


def get_unsupported_capabilities(
    engines: List[BrowserEngine]
) -> Dict[BrowserEngine, Set[BrowserCapability]]:
    """
    Get capabilities not universally supported across engines.

    Args:
        engines: List of browser engines to check

    Returns:
        Dict mapping engines to their missing capabilities
    """
    if not engines:
        return {}

    # Find all capabilities from all engines
    all_caps = set()
    for engine in engines:
        all_caps.update(BROWSER_CAPABILITIES.get(engine, set()))

    # Find what each engine is missing
    missing = {}
    for engine in engines:
        engine_caps = BROWSER_CAPABILITIES.get(engine, set())
        engine_missing = all_caps - engine_caps
        if engine_missing:
            missing[engine] = engine_missing

    return missing


def create_cross_browser_runner(
    browsers: Optional[List[str]] = None,
    parallel: bool = True
) -> CrossBrowserRunner:
    """
    Create a cross-browser runner with specified browsers.

    Args:
        browsers: List of browser names ("chromium", "firefox", "webkit")
        parallel: Run browsers in parallel

    Returns:
        Configured CrossBrowserRunner
    """
    if browsers is None:
        browsers = ["chromium"]

    engines = []
    for name in browsers:
        try:
            engines.append(BrowserEngine(name.lower()))
        except ValueError:
            logger.warning(f"Unknown browser: {name}")

    config = CrossBrowserConfig(
        browsers=engines,
        parallel=parallel,
    )
    return CrossBrowserRunner(config)
