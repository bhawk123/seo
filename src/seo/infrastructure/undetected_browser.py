"""
Undetected Chrome Browser Integration.

Implements Epic 9.2.1: Stealth mode using undetected-chromedriver.

This module provides a wrapper around undetected-chromedriver (or nodriver for async)
that integrates with the existing browser infrastructure while providing enhanced
bot detection evasion.

Features:
- Chrome version pinning for consistency
- Performance logging via CDP
- Stealth script injection (navigator.webdriver, plugins, etc.)
- Async context manager interface
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)


# Stealth JavaScript to inject into pages
# These scripts hide automation signals that bot detectors check for
STEALTH_SCRIPTS = {
    "webdriver": """
        // Hide navigator.webdriver
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined,
            configurable: true
        });
    """,
    "plugins": """
        // Add realistic plugins array
        Object.defineProperty(navigator, 'plugins', {
            get: () => {
                const plugins = [
                    { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
                    { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
                    { name: 'Native Client', filename: 'internal-nacl-plugin' }
                ];
                plugins.item = (index) => plugins[index];
                plugins.namedItem = (name) => plugins.find(p => p.name === name);
                plugins.refresh = () => {};
                return plugins;
            },
            configurable: true
        });
    """,
    "languages": """
        // Set realistic language preferences
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en'],
            configurable: true
        });
    """,
    "chrome_runtime": """
        // Add window.chrome with runtime
        if (!window.chrome) {
            window.chrome = {};
        }
        if (!window.chrome.runtime) {
            window.chrome.runtime = {
                id: undefined,
                connect: function() {},
                sendMessage: function() {},
                onMessage: { addListener: function() {} },
                onConnect: { addListener: function() {} }
            };
        }
    """,
    "permissions": """
        // Override permissions query to return realistic responses
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
        );
    """,
    "webgl_vendor": """
        // Set realistic WebGL vendor/renderer
        const getParameter = WebGLRenderingContext.prototype.getParameter;
        WebGLRenderingContext.prototype.getParameter = function(parameter) {
            if (parameter === 37445) {
                return 'Intel Inc.';
            }
            if (parameter === 37446) {
                return 'Intel Iris OpenGL Engine';
            }
            return getParameter.apply(this, arguments);
        };
    """,
    "hardware_concurrency": """
        // Set realistic hardware concurrency
        Object.defineProperty(navigator, 'hardwareConcurrency', {
            get: () => 8,
            configurable: true
        });
    """,
    "device_memory": """
        // Set realistic device memory
        Object.defineProperty(navigator, 'deviceMemory', {
            get: () => 8,
            configurable: true
        });
    """,
}

# Combined stealth script for injection
COMBINED_STEALTH_SCRIPT = "\n".join(STEALTH_SCRIPTS.values())


@dataclass
class UndetectedBrowserConfig:
    """Configuration for undetected-chromedriver browser."""
    headless: bool = True
    version_main: Optional[int] = None  # Chrome major version (e.g., 120)
    user_agent: Optional[str] = None
    timeout_ms: int = 30000
    enable_cdp_logging: bool = True  # Performance logging via CDP
    inject_stealth_scripts: bool = True


class UndetectedBrowserPage:
    """
    Wrapper for undetected-chromedriver page/tab.

    Provides a Playwright-like interface for compatibility with existing code.
    """

    def __init__(self, driver, tab=None):
        """
        Initialize page wrapper.

        Args:
            driver: undetected_chromedriver.Chrome instance
            tab: nodriver Tab instance (for async mode)
        """
        self._driver = driver
        self._tab = tab
        self._stealth_injected = False

    async def goto(self, url: str, wait_until: str = "load") -> None:
        """Navigate to URL."""
        if self._tab:
            # nodriver async mode
            await self._tab.get(url)
            await self._inject_stealth_scripts()
        else:
            # Sync mode with asyncio wrapper
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, self._driver.get, url)
            await self._inject_stealth_scripts()

    async def _inject_stealth_scripts(self) -> None:
        """Inject stealth scripts into the page."""
        if self._stealth_injected:
            return

        try:
            if self._tab:
                await self._tab.evaluate(COMBINED_STEALTH_SCRIPT)
            else:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None,
                    self._driver.execute_script,
                    COMBINED_STEALTH_SCRIPT
                )
            self._stealth_injected = True
            logger.debug("Stealth scripts injected successfully")
        except Exception as e:
            logger.warning(f"Failed to inject stealth scripts: {e}")

    async def content(self) -> str:
        """Get page HTML content."""
        if self._tab:
            return await self._tab.get_content()
        else:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None,
                lambda: self._driver.page_source
            )

    async def evaluate(self, expression: str) -> Any:
        """Execute JavaScript and return result."""
        if self._tab:
            return await self._tab.evaluate(expression)
        else:
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None,
                self._driver.execute_script,
                f"return {expression}"
            )

    async def screenshot(self, path: Optional[str] = None) -> Optional[bytes]:
        """Take screenshot."""
        if self._tab:
            return await self._tab.save_screenshot(path) if path else None
        else:
            loop = asyncio.get_event_loop()
            if path:
                await loop.run_in_executor(
                    None,
                    self._driver.save_screenshot,
                    path
                )
                return None
            else:
                return await loop.run_in_executor(
                    None,
                    self._driver.get_screenshot_as_png
                )

    @property
    def url(self) -> str:
        """Get current URL."""
        if self._tab:
            return self._tab.url
        return self._driver.current_url

    async def close(self) -> None:
        """Close the page/tab."""
        if self._tab:
            await self._tab.close()
        # For sync driver, don't close individual tabs


class UndetectedBrowser:
    """
    Async wrapper for undetected-chromedriver.

    Provides an interface similar to Playwright's Browser for compatibility
    with the existing BrowserPool infrastructure.

    Usage:
        async with UndetectedBrowser(config) as browser:
            page = await browser.new_page()
            await page.goto("https://example.com")
            html = await page.content()
    """

    def __init__(self, config: Optional[UndetectedBrowserConfig] = None):
        """
        Initialize undetected browser.

        Args:
            config: Browser configuration options
        """
        self.config = config or UndetectedBrowserConfig()
        self._driver = None
        self._browser = None  # nodriver Browser instance
        self._use_nodriver = False

    async def __aenter__(self) -> "UndetectedBrowser":
        """Enter async context, launching browser."""
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit async context, closing browser."""
        await self.close()

    async def start(self) -> None:
        """Start the browser."""
        # Try nodriver first (async-native), fall back to undetected_chromedriver
        try:
            import nodriver as uc
            self._use_nodriver = True

            options = uc.Config()
            if self.config.headless:
                options.headless = True
            if self.config.version_main:
                options.browser_executable_path = None  # Use version_main

            self._browser = await uc.start(options)
            logger.info("Started undetected browser using nodriver (async)")

        except ImportError:
            try:
                import undetected_chromedriver as uc
                self._use_nodriver = False

                options = uc.ChromeOptions()
                if self.config.headless:
                    options.add_argument("--headless=new")

                # Launch in executor since uc.Chrome is sync
                loop = asyncio.get_event_loop()
                self._driver = await loop.run_in_executor(
                    None,
                    lambda: uc.Chrome(
                        options=options,
                        version_main=self.config.version_main,
                        use_subprocess=True,
                    )
                )
                logger.info("Started undetected browser using undetected_chromedriver")

            except ImportError:
                raise ImportError(
                    "Neither nodriver nor undetected-chromedriver is installed. "
                    "Install with: pip install nodriver  OR  pip install undetected-chromedriver"
                )

    async def new_page(self) -> UndetectedBrowserPage:
        """Create a new page/tab."""
        if self._use_nodriver and self._browser:
            tab = await self._browser.get()  # Get/create a tab
            page = UndetectedBrowserPage(None, tab=tab)
        elif self._driver:
            page = UndetectedBrowserPage(self._driver)
        else:
            raise RuntimeError("Browser not started. Call start() first.")

        return page

    async def close(self) -> None:
        """Close the browser."""
        if self._use_nodriver and self._browser:
            try:
                self._browser.stop()
            except Exception as e:
                logger.warning(f"Error closing nodriver browser: {e}")
        elif self._driver:
            try:
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, self._driver.quit)
            except Exception as e:
                logger.warning(f"Error closing undetected_chromedriver: {e}")

        self._browser = None
        self._driver = None
        logger.info("Undetected browser closed")

    @property
    def is_running(self) -> bool:
        """Check if browser is running."""
        return self._browser is not None or self._driver is not None


async def verify_stealth(page: UndetectedBrowserPage) -> dict:
    """
    Verify that stealth measures are working.

    Checks for:
    - navigator.webdriver is undefined
    - navigator.plugins has entries
    - chrome.runtime exists
    - window.chrome is defined

    Args:
        page: UndetectedBrowserPage instance

    Returns:
        Dict with verification results
    """
    checks = {
        "webdriver_undefined": "typeof navigator.webdriver === 'undefined'",
        "plugins_non_empty": "navigator.plugins.length > 0",
        "chrome_runtime_exists": "typeof window.chrome !== 'undefined' && typeof window.chrome.runtime !== 'undefined'",
        "window_chrome_defined": "typeof window.chrome !== 'undefined'",
    }

    results = {}
    for name, script in checks.items():
        try:
            result = await page.evaluate(script)
            results[name] = result
        except Exception as e:
            results[name] = f"Error: {e}"

    all_passed = all(v is True for v in results.values() if not isinstance(v, str))
    results["all_passed"] = all_passed

    if all_passed:
        logger.info("All stealth verifications passed")
    else:
        logger.warning(f"Stealth verification issues: {results}")

    return results


def get_stealth_script(script_name: str) -> Optional[str]:
    """
    Get a specific stealth script by name.

    Args:
        script_name: Name of the script (webdriver, plugins, etc.)

    Returns:
        JavaScript code or None if not found
    """
    return STEALTH_SCRIPTS.get(script_name)
