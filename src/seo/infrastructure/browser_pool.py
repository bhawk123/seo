"""
Browser Pool Management.

Ported from Spectrum per EPIC-SEO-INFRA-001 (STORY-INFRA-001).
Enhanced with stealth backend switching per Epic 9.2.1.

This module manages a pool of browser instances for parallel crawling,
with session isolation and health monitoring.

Supports two backends:
- playwright: Standard Playwright with stealth flags
- undetected: undetected-chromedriver for maximum bot evasion
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Literal, Optional

logger = logging.getLogger(__name__)


class BrowserHealth(Enum):
    """Browser context health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    RECYCLING = "recycling"


@dataclass
class PoolStatus:
    """Current status of the browser pool."""
    total_size: int
    available: int
    in_use: int
    healthy: int
    degraded: int
    unhealthy: int
    total_requests: int
    total_errors: int
    uptime_seconds: float


@dataclass
class ContextMetrics:
    """Metrics for a browser context."""
    context_id: int
    created_at: datetime
    requests_handled: int = 0
    errors: int = 0
    last_used: datetime | None = None
    health: BrowserHealth = BrowserHealth.HEALTHY

    @property
    def error_rate(self) -> float:
        """Calculate error rate for this context."""
        if self.requests_handled == 0:
            return 0.0
        return self.errors / self.requests_handled

    def record_success(self) -> None:
        """Record a successful request."""
        self.requests_handled += 1
        self.last_used = datetime.now()

    def record_error(self) -> None:
        """Record a failed request."""
        self.requests_handled += 1
        self.errors += 1
        self.last_used = datetime.now()
        # Update health based on error rate
        if self.error_rate > 0.5:
            self.health = BrowserHealth.UNHEALTHY
        elif self.error_rate > 0.2:
            self.health = BrowserHealth.DEGRADED


class UndetectedContext:
    """
    Wrapper for undetected-chromedriver to provide Playwright-like context interface.

    Since undetected-chromedriver doesn't support isolated contexts like Playwright,
    this class provides a compatible interface while managing state clearing.
    """

    def __init__(self, browser, timeout_ms: int = 30000):
        """
        Initialize context wrapper.

        Args:
            browser: UndetectedBrowser instance
            timeout_ms: Default timeout in milliseconds
        """
        self._browser = browser
        self._timeout_ms = timeout_ms
        self._pages: list = []

    async def new_page(self):
        """Create a new page in this context."""
        page = await self._browser.new_page()
        self._pages.append(page)
        return page

    @property
    def pages(self):
        """Get all pages in this context."""
        return self._pages

    def set_default_timeout(self, timeout_ms: int) -> None:
        """Set default timeout for operations."""
        self._timeout_ms = timeout_ms

    async def clear_cookies(self) -> None:
        """Clear cookies (simulated for undetected-chromedriver)."""
        # undetected-chromedriver manages cookies at browser level
        # For true isolation, would need to delete all cookies via CDP
        logger.debug("Cookie clearing requested (undetected context)")

    async def close(self) -> None:
        """Close all pages in this context."""
        for page in self._pages:
            try:
                await page.close()
            except Exception:
                pass
        self._pages.clear()


class BrowserPool:
    """
    Manages pool of browser instances for parallel crawling.

    Features:
    - Async context acquisition with automatic release
    - Session isolation (cookies, storage cleared between uses)
    - Health monitoring and automatic recycling
    - Graceful shutdown
    - Backend switching between Playwright and undetected-chromedriver (Epic 9.2.1)
    """

    # Maximum requests before recycling a context
    MAX_REQUESTS_PER_CONTEXT = 100
    # Error rate threshold for recycling
    ERROR_RATE_RECYCLE_THRESHOLD = 0.3

    def __init__(
        self,
        max_size: int = 4,
        headless: bool = True,
        timeout_ms: int = 30000,
        user_agent: str | None = None,
        stealth_backend: Literal["playwright", "undetected"] = "playwright",
        chrome_version_main: Optional[int] = None,
    ):
        """
        Initialize browser pool.

        Args:
            max_size: Maximum number of browser contexts in pool
            headless: Run browsers in headless mode
            timeout_ms: Default navigation timeout
            user_agent: Custom user agent string
            stealth_backend: Browser backend ('playwright' or 'undetected')
            chrome_version_main: Chrome version for undetected-chromedriver
        """
        self.max_size = max_size
        self.headless = headless
        self.timeout_ms = timeout_ms
        self.user_agent = user_agent
        self.stealth_backend = stealth_backend
        self.chrome_version_main = chrome_version_main

        self._playwright = None
        self._browser = None
        self._undetected_browser = None  # UndetectedBrowser instance for 'undetected' mode
        self._contexts: dict[int, Any] = {}  # context_id -> BrowserContext
        self._metrics: dict[int, ContextMetrics] = {}  # context_id -> metrics
        self._available: asyncio.Queue[int] = asyncio.Queue()
        self._lock = asyncio.Lock()
        self._started = False
        self._start_time: datetime | None = None
        self._total_requests = 0
        self._total_errors = 0
        self._next_context_id = 0

    async def start(self) -> None:
        """
        Initialize browser pool.

        Creates the browser instance and initializes all contexts.
        Uses the configured stealth_backend (playwright or undetected).
        """
        if self._started:
            return

        if self.stealth_backend == "undetected":
            await self._start_undetected()
        else:
            await self._start_playwright()

        self._start_time = datetime.now()

        # Create initial contexts
        for _ in range(self.max_size):
            await self._create_context()

        self._started = True
        logger.info(
            f"Browser pool started with {self.max_size} contexts "
            f"(backend: {self.stealth_backend})"
        )

    async def _start_playwright(self) -> None:
        """Start browser pool using Playwright backend."""
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            raise ImportError(
                "playwright package not installed. "
                "Install with: pip install playwright && playwright install"
            )

        self._playwright = await async_playwright().start()

        # Launch browser with stealth options
        launch_options = {
            "headless": self.headless,
        }

        self._browser = await self._playwright.chromium.launch(**launch_options)
        logger.info("Browser pool using Playwright backend")

    async def _start_undetected(self) -> None:
        """Start browser pool using undetected-chromedriver backend."""
        try:
            from .undetected_browser import UndetectedBrowser, UndetectedBrowserConfig
        except ImportError:
            raise ImportError(
                "undetected_browser module not found. "
                "Ensure infrastructure/undetected_browser.py exists."
            )

        config = UndetectedBrowserConfig(
            headless=self.headless,
            version_main=self.chrome_version_main,
            user_agent=self.user_agent,
            timeout_ms=self.timeout_ms,
        )

        self._undetected_browser = UndetectedBrowser(config)
        await self._undetected_browser.start()
        logger.info("Browser pool using undetected-chromedriver backend")

    async def stop(self) -> None:
        """
        Shutdown browser pool gracefully.

        Closes all contexts and the browser instance.
        """
        if not self._started:
            return

        # Close all contexts
        for context_id, context in list(self._contexts.items()):
            try:
                if hasattr(context, 'close'):
                    await context.close()
            except Exception as e:
                logger.warning(f"Error closing context {context_id}: {e}")

        self._contexts.clear()
        self._metrics.clear()

        # Close browser based on backend
        if self.stealth_backend == "undetected" and self._undetected_browser:
            try:
                await self._undetected_browser.close()
            except Exception as e:
                logger.warning(f"Error closing undetected browser: {e}")
            self._undetected_browser = None
        else:
            # Playwright backend
            if self._browser:
                try:
                    await self._browser.close()
                except Exception as e:
                    logger.warning(f"Error closing browser: {e}")

            if self._playwright:
                try:
                    await self._playwright.stop()
                except Exception as e:
                    logger.warning(f"Error stopping playwright: {e}")

        self._started = False
        logger.info("Browser pool stopped")

    async def _create_context(self) -> int:
        """
        Create a new browser context.

        Returns:
            Context ID
        """
        if self.stealth_backend == "undetected":
            context = await self._create_undetected_context()
        else:
            context = await self._create_playwright_context()

        # Assign ID
        context_id = self._next_context_id
        self._next_context_id += 1

        self._contexts[context_id] = context
        self._metrics[context_id] = ContextMetrics(
            context_id=context_id,
            created_at=datetime.now(),
        )

        # Add to available queue
        await self._available.put(context_id)

        logger.debug(f"Created browser context {context_id} (backend: {self.stealth_backend})")
        return context_id

    async def _create_playwright_context(self) -> Any:
        """Create a Playwright browser context."""
        context_options: dict[str, Any] = {
            "ignore_https_errors": True,
        }

        if self.user_agent:
            context_options["user_agent"] = self.user_agent

        context = await self._browser.new_context(**context_options)

        # Set default timeout
        context.set_default_timeout(self.timeout_ms)

        return context

    async def _create_undetected_context(self) -> Any:
        """
        Create an undetected-chromedriver context.

        For undetected-chromedriver, we use a wrapper object that provides
        a similar interface to Playwright's BrowserContext.
        """
        # For undetected mode, each "context" is actually the browser itself
        # since undetected-chromedriver doesn't support multiple isolated contexts
        # We return a wrapper that tracks state
        return UndetectedContext(self._undetected_browser, self.timeout_ms)

    async def _recycle_context(self, context_id: int) -> None:
        """
        Recycle a browser context by closing and creating a new one.
        """
        async with self._lock:
            old_context = self._contexts.pop(context_id, None)
            self._metrics.pop(context_id, None)

            if old_context:
                try:
                    await old_context.close()
                except Exception as e:
                    logger.warning(f"Error closing context {context_id}: {e}")

            # Create replacement
            new_id = await self._create_context()
            logger.info(f"Recycled context {context_id} -> {new_id}")

    async def _clear_context_state(self, context_id: int) -> None:
        """
        Clear cookies and storage for a context.
        """
        context = self._contexts.get(context_id)
        if not context:
            return

        try:
            # Clear cookies
            await context.clear_cookies()

            # Clear storage for all pages
            for page in context.pages:
                try:
                    await page.evaluate("() => { localStorage.clear(); sessionStorage.clear(); }")
                except Exception:
                    pass  # Page might be closed or navigating
        except Exception as e:
            logger.warning(f"Error clearing context {context_id} state: {e}")

    @asynccontextmanager
    async def acquire(self, clear_state: bool = True):
        """
        Acquire a browser context from pool.

        Usage:
            async with pool.acquire() as (context, page):
                await page.goto(url)

        Args:
            clear_state: Clear cookies/storage before use

        Yields:
            Tuple of (BrowserContext, Page)
        """
        if not self._started:
            raise RuntimeError("Browser pool not started. Call start() first.")

        context_id = await self._available.get()
        context = self._contexts.get(context_id)
        metrics = self._metrics.get(context_id)

        if not context or not metrics:
            # Context was recycled, get another
            await self._available.put(context_id)
            context_id = await self._available.get()
            context = self._contexts.get(context_id)
            metrics = self._metrics.get(context_id)

        try:
            # Clear state if requested
            if clear_state:
                await self._clear_context_state(context_id)

            # Create a new page for this request
            page = await context.new_page()

            self._total_requests += 1

            try:
                yield context, page
                metrics.record_success()
            except Exception as e:
                metrics.record_error()
                self._total_errors += 1
                raise
            finally:
                # Close the page
                try:
                    await page.close()
                except Exception:
                    pass

        finally:
            # Check if context needs recycling
            should_recycle = (
                metrics.requests_handled >= self.MAX_REQUESTS_PER_CONTEXT or
                metrics.error_rate > self.ERROR_RATE_RECYCLE_THRESHOLD or
                metrics.health == BrowserHealth.UNHEALTHY
            )

            if should_recycle:
                # Recycle in background
                asyncio.create_task(self._recycle_context(context_id))
            else:
                # Return to pool
                await self._available.put(context_id)

    def check_health(self, context_id: int) -> BrowserHealth:
        """
        Check health of a specific context.
        """
        metrics = self._metrics.get(context_id)
        if not metrics:
            return BrowserHealth.UNHEALTHY

        return metrics.health

    def get_status(self) -> PoolStatus:
        """Get current pool status."""
        healthy = sum(1 for m in self._metrics.values() if m.health == BrowserHealth.HEALTHY)
        degraded = sum(1 for m in self._metrics.values() if m.health == BrowserHealth.DEGRADED)
        unhealthy = sum(1 for m in self._metrics.values() if m.health == BrowserHealth.UNHEALTHY)

        uptime = 0.0
        if self._start_time:
            uptime = (datetime.now() - self._start_time).total_seconds()

        return PoolStatus(
            total_size=len(self._contexts),
            available=self._available.qsize(),
            in_use=len(self._contexts) - self._available.qsize(),
            healthy=healthy,
            degraded=degraded,
            unhealthy=unhealthy,
            total_requests=self._total_requests,
            total_errors=self._total_errors,
            uptime_seconds=uptime,
        )

    @property
    def available_count(self) -> int:
        """Number of available contexts."""
        return self._available.qsize()

    @property
    def is_started(self) -> bool:
        """Whether pool has been started."""
        return self._started
