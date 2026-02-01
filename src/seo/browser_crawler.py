"""
Browser-based crawler using Playwright for JavaScript-rendered content.

This module provides a BrowserCrawler class that uses Playwright to crawl
web pages with full JavaScript execution, enabling analysis of SPAs and
other JavaScript-heavy websites.
"""
import asyncio
import logging
import random
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

try:
    from playwright_stealth import stealth_async
    HAS_STEALTH = True
except ImportError:
    HAS_STEALTH = False

from .browser_config import BrowserConfig

logger = logging.getLogger(__name__)


@dataclass
class BrowserCrawlResult:
    """Result from a single browser-based crawl attempt."""

    url: str
    final_url: Optional[str] = None
    html: Optional[str] = None
    status_code: int = 0
    load_time: float = 0.0
    headers: Dict[str, str] = field(default_factory=dict)
    performance_metrics: Dict[str, float] = field(default_factory=dict)
    console_errors: List[str] = field(default_factory=list)
    network_requests: List[Dict[str, Any]] = field(default_factory=list)
    screenshot: Optional[bytes] = None
    error: Optional[str] = None


class BrowserCrawler:
    """
    Playwright-based crawler for JavaScript-rendered websites.

    This class is designed to be used as an async context manager, managing
    its own browser lifecycle:

        async with BrowserCrawler(config) as crawler:
            result = await crawler.crawl("https://example.com")

    Features:
    - Full JavaScript execution
    - Configurable wait strategies
    - Stealth mode to avoid bot detection
    - Session isolation between crawls
    - Performance metrics collection
    - Screenshot capture
    """

    # Realistic viewport sizes for desktop
    DESKTOP_VIEWPORTS = [
        {"width": 1920, "height": 1080},
        {"width": 1366, "height": 768},
        {"width": 1536, "height": 864},
        {"width": 1440, "height": 900},
    ]

    # Mobile viewport sizes
    MOBILE_VIEWPORTS = [
        {"width": 390, "height": 844},  # iPhone 14
        {"width": 412, "height": 915},  # Pixel 7
        {"width": 428, "height": 926},  # iPhone 14 Pro Max
    ]

    # Realistic browser user agents
    DESKTOP_USER_AGENTS = [
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    ]

    MOBILE_USER_AGENTS = [
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (Linux; Android 14; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
    ]

    def __init__(self, config: BrowserConfig):
        """
        Initialize the browser crawler.

        Args:
            config: BrowserConfig instance with crawler settings
        """
        self._config = config
        self._playwright = None
        self._browser = None

        logger.debug(f"BrowserCrawler initialized with config: {config}")

    async def __aenter__(self) -> "BrowserCrawler":
        """Enter async context manager, launching browser."""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            raise ImportError(
                "Playwright is required for browser-based crawling. "
                "Install with: poetry install -E browser"
            )

        logger.info(f"Launching {self._config.browser_type} browser (headless={self._config.headless})")

        self._playwright = await async_playwright().start()
        browser_launcher = getattr(self._playwright, self._config.browser_type)

        # Build launch options
        launch_options = {"headless": self._config.headless}
        if self._config.launch_args:
            launch_options["args"] = self._config.launch_args

        self._browser = await browser_launcher.launch(**launch_options)

        logger.info("Browser launched successfully")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context manager, closing browser."""
        if self._browser:
            logger.info("Closing browser")
            await self._browser.close()
            self._browser = None

        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

        logger.info("Browser closed successfully")

    async def crawl(self, url: str) -> BrowserCrawlResult:
        """
        Crawl a single URL with full JavaScript rendering.

        Each call creates an isolated browser context to prevent
        cross-contamination of sessions, cookies, or localStorage.

        Args:
            url: URL to crawl

        Returns:
            BrowserCrawlResult with rendered HTML and metrics

        Raises:
            RuntimeError: If browser is not running (not in context manager)
            playwright.TimeoutError: If page load exceeds configured timeout
        """
        if not self._browser:
            raise RuntimeError(
                "Browser is not running. Use BrowserCrawler as an async context manager: "
                "async with BrowserCrawler(config) as crawler:"
            )

        console_errors: List[str] = []
        network_requests: List[Dict[str, Any]] = []
        start_time = time.time()

        # Create isolated browser context for this crawl
        context = await self._create_context()

        try:
            page = await context.new_page()

            # Set up console error capture
            page.on("console", lambda msg: (
                console_errors.append(f"{msg.type}: {msg.text}")
                if msg.type == "error" else None
            ))

            # Set up network capture if enabled
            if self._config.capture_network:
                page.on("request", lambda req: network_requests.append({
                    "url": req.url,
                    "method": req.method,
                    "resource_type": req.resource_type,
                }))

            # Block unwanted resources if configured
            if self._config.block_resources:
                await page.route(
                    "**/*",
                    lambda route: (
                        route.abort()
                        if route.request.resource_type in self._config.block_resources
                        else route.continue_()
                    )
                )

            # Apply stealth measures if enabled
            if self._config.stealth_mode:
                if HAS_STEALTH:
                    await stealth_async(page)
                    logger.debug("Applied playwright-stealth measures")
                else:
                    await self._apply_stealth(page)

            logger.info(f"Crawling: {url}")

            # Navigate to page
            response = await page.goto(
                url,
                wait_until=self._config.wait_until,
                timeout=self._config.timeout
            )

            # Wait for dynamic content to settle
            await self._wait_for_content(page)

            load_time = time.time() - start_time

            # Get rendered HTML
            html = await page.content()

            # Get performance metrics
            performance_metrics = await self._get_performance_metrics(page)

            # Capture screenshot if enabled
            screenshot = None
            if self._config.capture_screenshots:
                screenshot = await page.screenshot(full_page=True)

            # Get response details
            status_code = response.status if response else 0
            headers = dict(response.headers) if response else {}
            final_url = page.url

            logger.info(f"Crawl complete: {url} (status={status_code}, time={load_time:.2f}s)")

            return BrowserCrawlResult(
                url=url,
                final_url=final_url,
                html=html,
                status_code=status_code,
                load_time=load_time,
                headers=headers,
                performance_metrics=performance_metrics,
                console_errors=console_errors,
                network_requests=network_requests,
                screenshot=screenshot,
            )

        except Exception as e:
            load_time = time.time() - start_time
            logger.error(f"Crawl failed for {url}: {e}")

            return BrowserCrawlResult(
                url=url,
                load_time=load_time,
                console_errors=console_errors,
                network_requests=network_requests,
                error=str(e),
            )

        finally:
            # Always close context to ensure isolation
            await context.close()

    async def _create_context(self):
        """Create a new, isolated browser context with appropriate settings."""
        viewport = random.choice(
            self.MOBILE_VIEWPORTS if self._config.mobile else self.DESKTOP_VIEWPORTS
        )

        user_agent = random.choice(
            self.MOBILE_USER_AGENTS if self._config.mobile else self.DESKTOP_USER_AGENTS
        )

        context = await self._browser.new_context(
            viewport=viewport,
            user_agent=user_agent,
            locale="en-US",
            timezone_id="America/New_York",
            java_script_enabled=True,
            has_touch=self._config.mobile,
            is_mobile=self._config.mobile,
            device_scale_factor=2 if self._config.mobile else 1,
        )

        return context

    async def _apply_stealth(self, page) -> None:
        """Apply stealth measures to avoid bot detection."""
        # Comprehensive stealth script to mask automation indicators
        stealth_script = """
            // Mask webdriver property
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });

            // Add chrome runtime object
            window.chrome = {
                runtime: {}
            };

            // Mask permissions query
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );

            // Add realistic plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [
                    {
                        name: 'Chrome PDF Plugin',
                        filename: 'internal-pdf-viewer',
                        description: 'Portable Document Format'
                    },
                    {
                        name: 'Chrome PDF Viewer',
                        filename: 'internal-pdf-viewer',
                        description: 'Portable Document Format'
                    },
                    {
                        name: 'Native Client',
                        filename: 'internal-nacl-plugin',
                        description: ''
                    }
                ]
            });

            // Mask languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });

            // Mask WebGL vendor
            try {
                const getParameter = WebGLRenderingContext.prototype.getParameter;
                WebGLRenderingContext.prototype.getParameter = function(parameter) {
                    // UNMASKED_VENDOR_WEBGL
                    if (parameter === 37445) {
                        return 'Intel Open Source Technology Center';
                    }
                    // UNMASKED_RENDERER_WEBGL
                    if (parameter === 37446) {
                        return 'Mesa DRI Intel(R) Ivybridge Mobile';
                    }
                    return getParameter(parameter);
                };
            } catch (e) {}

            // Mask connection property
            Object.defineProperty(navigator, 'connection', {
                get: () => ({
                    effectiveType: '4g',
                    rtt: 50,
                    downlink: 10,
                    saveData: false
                })
            });

            // Mask hardware concurrency
            Object.defineProperty(navigator, 'hardwareConcurrency', {
                get: () => 8
            });

            // Mask device memory
            Object.defineProperty(navigator, 'deviceMemory', {
                get: () => 8
            });
        """

        await page.add_init_script(stealth_script)
        logger.debug("Stealth measures applied")

    async def _wait_for_content(self, page) -> None:
        """
        Wait for dynamic content to load.

        Uses multiple strategies to ensure JavaScript content is rendered,
        especially for heavy SPAs that load content after initial page load.
        """
        # Strategy 1: Wait for network to be idle (initial load complete)
        try:
            await page.wait_for_load_state("networkidle", timeout=15000)
        except Exception:
            pass

        # Strategy 2: Wait for body to have meaningful content
        try:
            await page.wait_for_function(
                "document.body && document.body.innerText.length > 500",
                timeout=10000
            )
        except Exception:
            pass  # Continue even if this check fails

        # Strategy 3: Wait for common SPA content indicators
        spa_selectors = [
            'nav a[href]',           # Navigation links
            'main',                   # Main content area
            'header nav',             # Header navigation
            '[data-testid]',          # React test IDs
            '[class*="product"]',     # Product elements
            '[class*="menu"]',        # Menu elements
            'a[href^="/"]',           # Internal links
        ]

        for selector in spa_selectors:
            try:
                await page.wait_for_selector(selector, timeout=3000)
                logger.debug(f"Found SPA content: {selector}")
                break
            except Exception:
                continue

        # Strategy 4: Scroll to trigger lazy loading
        try:
            await page.evaluate("""
                async () => {
                    // Scroll down in steps to trigger lazy loading
                    const scrollHeight = document.body.scrollHeight;
                    const viewportHeight = window.innerHeight;

                    for (let y = 0; y < scrollHeight; y += viewportHeight) {
                        window.scrollTo(0, y);
                        await new Promise(r => setTimeout(r, 100));
                    }

                    // Scroll back to top
                    window.scrollTo(0, 0);
                }
            """)
        except Exception:
            pass

        # Strategy 5: Wait for DOM mutations to settle
        try:
            await page.wait_for_function(
                """
                () => {
                    return new Promise(resolve => {
                        let lastMutation = Date.now();
                        const observer = new MutationObserver(() => {
                            lastMutation = Date.now();
                        });

                        observer.observe(document.body, {
                            childList: true,
                            subtree: true,
                            attributes: true
                        });

                        // Check if mutations have settled (200ms of quiet)
                        const checkSettled = () => {
                            if (Date.now() - lastMutation > 200) {
                                observer.disconnect();
                                resolve(true);
                            } else {
                                setTimeout(checkSettled, 100);
                            }
                        };

                        setTimeout(checkSettled, 500);

                        // Timeout after 5 seconds regardless
                        setTimeout(() => {
                            observer.disconnect();
                            resolve(true);
                        }, 5000);
                    });
                }
                """,
                timeout=10000
            )
        except Exception:
            pass

        # Final delay for any remaining rendering
        await page.wait_for_timeout(1000)

    async def _get_performance_metrics(self, page) -> Dict[str, float]:
        """
        Extract Web Vitals and performance metrics.

        Note: FID (First Input Delay) is deprecated and cannot be measured in a lab.
        Its successor, INP (Interaction to Next Paint), is a field metric only.
        """
        try:
            metrics = await page.evaluate("""
                () => {
                    const timing = performance.timing;
                    const navigation = performance.getEntriesByType('navigation')[0];

                    return {
                        // Navigation timing
                        dns_lookup: timing.domainLookupEnd - timing.domainLookupStart,
                        tcp_connect: timing.connectEnd - timing.connectStart,
                        ttfb: timing.responseStart - timing.requestStart,
                        dom_interactive: timing.domInteractive - timing.navigationStart,
                        dom_complete: timing.domComplete - timing.navigationStart,
                        load_complete: timing.loadEventEnd - timing.navigationStart,

                        // Resource counts
                        resource_count: performance.getEntriesByType('resource').length,

                        // Transfer size (if available)
                        transfer_size: navigation ? navigation.transferSize : 0,
                        encoded_body_size: navigation ? navigation.encodedBodySize : 0,
                        decoded_body_size: navigation ? navigation.decodedBodySize : 0,
                    };
                }
            """)
        except Exception as e:
            logger.warning(f"Failed to get basic performance metrics: {e}")
            metrics = {}

        # Try to get Core Web Vitals (LCP, CLS)
        try:
            web_vitals = await page.evaluate("""
                () => new Promise((resolve) => {
                    let lcp = 0, cls = 0;

                    // LCP observer
                    try {
                        new PerformanceObserver((list) => {
                            const entries = list.getEntries();
                            if (entries.length > 0) {
                                lcp = entries[entries.length - 1].startTime;
                            }
                        }).observe({type: 'largest-contentful-paint', buffered: true});
                    } catch (e) {}

                    // CLS observer
                    try {
                        new PerformanceObserver((list) => {
                            for (const entry of list.getEntries()) {
                                if (!entry.hadRecentInput) {
                                    cls += entry.value;
                                }
                            }
                        }).observe({type: 'layout-shift', buffered: true});
                    } catch (e) {}

                    // Give time for metrics to be captured
                    setTimeout(() => resolve({ lcp, cls }), 1000);
                })
            """)
            metrics.update(web_vitals)
        except Exception as e:
            logger.warning(f"Failed to get Core Web Vitals: {e}")
            metrics.update({'lcp': 0, 'cls': 0})

        return metrics


def crawl_sync(config: BrowserConfig, url: str) -> BrowserCrawlResult:
    """
    Synchronous wrapper for crawling a single URL.

    Convenience function for non-async contexts.

    Args:
        config: BrowserConfig instance
        url: URL to crawl

    Returns:
        BrowserCrawlResult
    """
    async def _crawl():
        async with BrowserCrawler(config) as crawler:
            return await crawler.crawl(url)

    return asyncio.run(_crawl())
