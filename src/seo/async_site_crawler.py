"""Asynchronous site crawler with breadth-first search for multi-page analysis."""

import asyncio
import hashlib
import random
import time
import json
import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, Set, Optional, List
from urllib.parse import urlparse, urljoin
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup
from rebrowser_playwright.async_api import async_playwright, Browser, BrowserContext, Page

from seo.models import PageMetadata
from seo.core_web_vitals import CoreWebVitalsAnalyzer
from seo.structured_data import StructuredDataAnalyzer
from seo.external.pagespeed_insights import PageSpeedInsightsAPI
from seo.technology_detector import TechnologyDetector

logger = logging.getLogger(__name__)


@dataclass
class ResourceMetrics:
    """Tracks resource loading metrics during page load."""
    css_files: List[dict] = field(default_factory=list)
    js_files: List[dict] = field(default_factory=list)
    images: List[dict] = field(default_factory=list)
    fonts: List[dict] = field(default_factory=list)
    third_party: List[dict] = field(default_factory=list)
    redirects: List[str] = field(default_factory=list)
    console_errors: List[str] = field(default_factory=list)
    console_warnings: List[str] = field(default_factory=list)


@dataclass
class TimingMetrics:
    """Tracks timing for each phase of page crawling."""
    url: str = ""
    page_get_time: float = 0.0        # Time to get page from pool
    navigation_time: float = 0.0       # Time for page.goto (actual page load)
    human_delay_time: float = 0.0      # Sleep after load
    mouse_movement_time: float = 0.0   # Human-like mouse movement
    scroll_time: float = 0.0           # Scroll + delay
    form_fill_time: float = 0.0        # Address form detection/filling
    content_extract_time: float = 0.0  # HTML extraction + metadata parsing
    link_extract_time: float = 0.0     # Finding and queueing links
    page_return_time: float = 0.0      # Returning page to pool
    total_time: float = 0.0            # Total wall clock time

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "page_get_ms": round(self.page_get_time * 1000, 1),
            "navigation_ms": round(self.navigation_time * 1000, 1),
            "human_delay_ms": round(self.human_delay_time * 1000, 1),
            "mouse_movement_ms": round(self.mouse_movement_time * 1000, 1),
            "scroll_ms": round(self.scroll_time * 1000, 1),
            "form_fill_ms": round(self.form_fill_time * 1000, 1),
            "content_extract_ms": round(self.content_extract_time * 1000, 1),
            "link_extract_ms": round(self.link_extract_time * 1000, 1),
            "page_return_ms": round(self.page_return_time * 1000, 1),
            "total_ms": round(self.total_time * 1000, 1),
            "stealth_overhead_ms": round((self.human_delay_time + self.mouse_movement_time + self.scroll_time) * 1000, 1),
            "automation_overhead_ms": round((self.page_get_time + self.form_fill_time + self.content_extract_time + self.link_extract_time + self.page_return_time) * 1000, 1),
        }

    def log_summary(self):
        """Log a summary of timing breakdown."""
        stealth = self.human_delay_time + self.mouse_movement_time + self.scroll_time
        automation = self.page_get_time + self.form_fill_time + self.content_extract_time + self.link_extract_time + self.page_return_time
        logger.info(
            f"  ⏱  Timing: nav={self.navigation_time*1000:.0f}ms, "
            f"stealth={stealth*1000:.0f}ms, "
            f"form={self.form_fill_time*1000:.0f}ms, "
            f"total={self.total_time*1000:.0f}ms"
        )


class AsyncSiteCrawler:
    """Asynchronously crawls entire sites using breadth-first search (BFS).

    This high-performance crawler can handle large sites efficiently by:
    - Using async/await for concurrent requests
    - Respecting robots.txt
    - Implementing per-domain rate limiting
    - Tracking visited URLs to avoid duplicates
    - Processing pages level by level (L1, L2, L3...)
    """

    def __init__(
        self,
        max_pages: int = 50,
        max_depth: Optional[int] = None,
        rate_limit: float = 0.5,
        user_agent: Optional[str] = None,
        max_concurrent: int = 3,
        timeout: int = 30,
        headless: bool = True,
        resume_state: Optional[dict] = None,
        output_manager: Optional["OutputManager"] = None,
        crawl_dir: Optional[Path] = None,
        enable_psi: bool = False,
        psi_api_key: Optional[str] = None,
        psi_strategy: str = "mobile",
        psi_sample_rate: float = 0.1,
        address_config: Optional[dict] = None,
    ):
        """Initialize the async site crawler.

        Args:
            max_pages: Maximum number of pages to crawl
            max_depth: Maximum depth to crawl (None = unlimited)
            rate_limit: Minimum seconds between requests to same domain
            user_agent: Custom user agent string
            max_concurrent: Maximum concurrent browser pages
            timeout: Request timeout in seconds
            headless: Run browser in headless mode
            resume_state: Optional state dict to resume from a previous crawl
            output_manager: OutputManager instance for saving checkpoints
            crawl_dir: Directory to save checkpoints to
            enable_psi: Enable PageSpeed Insights API for Lighthouse/CrUX data
            psi_api_key: Google API key for PageSpeed Insights
            psi_strategy: PSI strategy - 'mobile' or 'desktop'
            psi_sample_rate: Fraction of pages to analyze with PSI (0.0-1.0)
        """
        self.max_pages = max_pages
        self.max_depth = max_depth
        self.rate_limit = rate_limit
        self.user_agent = user_agent
        self.max_concurrent = max_concurrent
        self.timeout = timeout * 1000  # Playwright uses milliseconds
        self.headless = headless

        # Resume state support
        self._output_manager = output_manager
        self._crawl_dir = crawl_dir
        self._start_url: Optional[str] = None
        self._started_at: Optional[str] = None
        self._checkpoint_callback: Optional[Callable[[dict], None]] = None

        # Initialize from resume state or empty
        if resume_state:
            self.visited_urls = set(resume_state.get("visited_urls", []))
            self.queue = deque(
                (item["url"], item["depth"]) for item in resume_state.get("queue", [])
            )
            self._started_at = resume_state.get("progress", {}).get("started_at")
            logger.info(f"Resuming crawl with {len(self.visited_urls)} pages already crawled")
        else:
            self.visited_urls: Set[str] = set()
            self.queue: deque = deque()
            self._started_at = datetime.now().isoformat()

        self.site_data: Dict[str, PageMetadata] = {}

        # Load existing page data from disk when resuming
        if resume_state and crawl_dir:
            self._load_page_data_from_disk(crawl_dir)
            logger.info(f"Restored {len(self.site_data)} pages from disk")
        self.timing_data: List[TimingMetrics] = []  # Timing for each page
        self.robots_parsers: Dict[str, RobotFileParser] = {}
        self.last_request_time: Dict[str, float] = {}
        self.robots_txt_content: Optional[str] = None
        self.robots_txt_url: Optional[str] = None

        # Semaphore to limit concurrent requests
        self.semaphore = asyncio.Semaphore(max_concurrent)

        # Browser instances (set during crawl)
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None

        # Page pool for reusing browser tabs
        self._page_pool: asyncio.Queue = asyncio.Queue()
        self._page_pool_size: int = max_concurrent
        self._pages_created: int = 0
        self._page_lock: asyncio.Lock = asyncio.Lock()

        # Track session errors for context recovery
        self._session_errors: int = 0
        self._max_session_errors: int = 5

        # Store playwright instance for browser recovery
        self._playwright = None
        self._launch_args = None
        self._chrome_user_agent = None

        # PageSpeed Insights API integration
        self.enable_psi = enable_psi and psi_api_key is not None
        self.psi_sample_rate = max(0.0, min(1.0, psi_sample_rate))
        self.psi_strategy = psi_strategy
        self._psi_api: Optional[PageSpeedInsightsAPI] = None
        self._psi_count = 0
        self._psi_results: Dict[str, dict] = {}  # Store raw PSI results for saving
        if self.enable_psi and psi_api_key:
            self._psi_api = PageSpeedInsightsAPI(
                api_key=psi_api_key,
                strategy=psi_strategy,
            )
            logger.info(f"PageSpeed Insights API enabled ({psi_strategy}, {psi_sample_rate*100:.0f}% sample)")

        # Address configuration for auto-filling address prompts
        self.address_config = address_config
        if address_config:
            logger.info(f"Address config loaded: {address_config.get('address')}")

    def set_checkpoint_callback(self, callback: Callable[[dict], None]) -> None:
        """Set a callback function that will be called on each checkpoint.

        Args:
            callback: Function that receives the current state dict
        """
        self._checkpoint_callback = callback

    def get_psi_results(self) -> Dict[str, dict]:
        """Get raw PageSpeed Insights results for all analyzed pages.

        Returns:
            Dictionary mapping URL to raw PSI result data
        """
        return self._psi_results

    def get_state(self, status: str = "running") -> dict:
        """Get the current crawl state for checkpointing/resume.

        Args:
            status: Current status ("running", "paused", or "completed")

        Returns:
            State dictionary suitable for saving
        """
        return {
            "version": 1,
            "status": status,
            "config": {
                "start_url": self._start_url,
                "max_pages": self.max_pages,
                "max_depth": self.max_depth,
                "rate_limit": self.rate_limit,
            },
            "progress": {
                "pages_crawled": len(self.visited_urls),
                "started_at": self._started_at,
                "last_updated": datetime.now().isoformat(),
            },
            "visited_urls": list(self.visited_urls),
            "queue": [
                {"url": url, "depth": depth} for url, depth in self.queue
            ],
        }

    def _save_checkpoint(self, status: str = "running") -> None:
        """Save a checkpoint of the current crawl state.

        Args:
            status: Current status to save
        """
        if self._output_manager and self._crawl_dir:
            state = self.get_state(status)
            self._output_manager.save_crawl_state(self._crawl_dir, state)
            logger.debug(f"Checkpoint saved: {len(self.visited_urls)} pages crawled")

        if self._checkpoint_callback:
            self._checkpoint_callback(self.get_state(status))

    def _load_page_data_from_disk(self, crawl_dir: Path) -> None:
        """Load existing page data from the pages/ directory.

        This enables proper resume by restoring site_data from previously
        saved page JSON files.

        Args:
            crawl_dir: The crawl directory containing pages/ subdirectory
        """
        from dataclasses import fields
        pages_dir = crawl_dir / "pages"
        if not pages_dir.exists():
            return

        for page_file in pages_dir.glob("*.json"):
            try:
                with open(page_file, "r", encoding="utf-8") as f:
                    data = json.load(f)

                url = data.get("url")
                if not url:
                    continue

                # Convert datetime string back to datetime
                if data.get("crawled_at"):
                    try:
                        data["crawled_at"] = datetime.fromisoformat(data["crawled_at"])
                    except (ValueError, TypeError):
                        data["crawled_at"] = datetime.now()

                # Handle content_text_length field (content_text was removed during save)
                if "content_text_length" in data and "content_text" not in data:
                    data["content_text"] = ""  # Set empty - we don't have it anymore
                    del data["content_text_length"]

                # Get valid field names for PageMetadata
                valid_fields = {f.name for f in fields(PageMetadata)}
                filtered_data = {k: v for k, v in data.items() if k in valid_fields}

                # Create PageMetadata from filtered data
                self.site_data[url] = PageMetadata(**filtered_data)

            except Exception as e:
                logger.warning(f"Failed to load page data from {page_file}: {e}")

    def _save_page_to_disk(self, url: str, metadata: PageMetadata) -> None:
        """Save a single page's metadata to disk immediately.

        This ensures page data is persisted as soon as it's crawled,
        preventing data loss on interruption.

        Args:
            url: The page URL
            metadata: The PageMetadata to save
        """
        if not self._output_manager or not self._crawl_dir:
            return

        try:
            from dataclasses import asdict
            pages_dir = self._crawl_dir / "pages"
            pages_dir.mkdir(exist_ok=True)

            # Convert to dict
            page_data = asdict(metadata)

            # Convert datetime to ISO format
            if page_data.get("crawled_at"):
                page_data["crawled_at"] = metadata.crawled_at.isoformat()

            # Remove large content_text to keep files smaller
            if "content_text" in page_data:
                page_data["content_text_length"] = len(page_data.get("content_text", ""))
                del page_data["content_text"]

            # Create safe filename
            filename = self._output_manager._url_to_filename(url)
            filepath = pages_dir / f"{filename}.json"

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(page_data, f, indent=2, ensure_ascii=False)

        except Exception as e:
            logger.warning(f"Failed to save page to disk: {url} - {e}")

    async def crawl_site(self, start_url: str) -> Dict[str, PageMetadata]:
        """Crawl entire site starting from a URL using async BFS with Playwright.

        Args:
            start_url: The starting URL to crawl from

        Returns:
            Dictionary mapping URLs to PageMetadata for all crawled pages
        """
        start_url = self._normalize_url(start_url)
        self._start_url = start_url
        base_domain = urlparse(start_url).netloc

        # Initialize robots.txt parser
        await self._load_robots_txt(start_url)

        # Only add start URL to queue if not resuming (queue already populated)
        if not self.queue:
            self.queue.append((start_url, 1))

        logger.info(f"Starting async site crawl from: {start_url}")
        logger.info(f"Max pages: {self.max_pages}, Max concurrent: {self.max_concurrent}")
        logger.info(f"Rate limit: {self.rate_limit}s per domain")
        logger.info(f"Using rebrowser-playwright (undetected chromium)\n")

        # Launch Playwright browser
        async with async_playwright() as p:
            # Store playwright instance for recovery
            self._playwright = p

            # Minimal launch args - keep it simple
            self._launch_args = [
                "--disable-blink-features=AutomationControlled",
                "--disable-http2",
            ]

            # Realistic Chrome user agent
            self._chrome_user_agent = self.user_agent or (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            )

            # Launch browser and create context
            await self._launch_browser()

            current_level = 1

            while self.queue and len(self.visited_urls) < self.max_pages:
                # Collect batch of URLs at current level
                batch = []
                while self.queue and len(batch) < self.max_concurrent:
                    url, level = self.queue.popleft()

                    # Skip if already visited
                    if url in self.visited_urls:
                        continue

                    # Check max depth
                    if self.max_depth is not None and level > self.max_depth:
                        continue

                    # Check robots.txt
                    if not self._can_crawl(url):
                        logger.warning(f"Skipping {url} (disallowed by robots.txt)")
                        continue

                    batch.append((url, level))

                if not batch:
                    continue

                # Update level indicator
                level = batch[0][1]
                if level > current_level:
                    logger.info(f"\n--- Moving to Level {level} ---\n")
                    current_level = level

                # Crawl batch concurrently
                tasks = [
                    self._crawl_page(url, level, base_domain)
                    for url, level in batch
                ]

                await asyncio.gather(*tasks, return_exceptions=True)

                # Save checkpoint every 10 pages
                if len(self.visited_urls) % 10 == 0:
                    self._save_checkpoint("running")

            # Cleanup - close all pooled pages first
            await self._drain_page_pool()
            await self._context.close()
            await self._browser.close()

        # Run PageSpeed Insights analysis on sampled pages
        if self.enable_psi and self._psi_api:
            await self._run_psi_analysis()

        # Save final checkpoint with completed status
        self._save_checkpoint("completed")

        logger.info(f"\n{'=' * 60}")
        logger.info(f"Crawl complete! Processed {len(self.site_data)} pages")
        if self._psi_count > 0:
            logger.info(f"PageSpeed Insights: {self._psi_count} pages analyzed")
        logger.info(f"{'=' * 60}\n")

        return self.site_data

    async def _run_psi_analysis(self) -> None:
        """Run PageSpeed Insights analysis on a sample of crawled pages."""
        if not self._psi_api or not self.site_data:
            return

        # Select pages to analyze based on sample rate
        urls = list(self.site_data.keys())
        # Always include homepage if present
        homepage_urls = [u for u in urls if u.rstrip('/').endswith(urlparse(u).netloc)]
        other_urls = [u for u in urls if u not in homepage_urls]

        # Sample other URLs
        import random
        sample_size = max(1, int(len(other_urls) * self.psi_sample_rate))
        sampled_urls = homepage_urls + random.sample(other_urls, min(sample_size, len(other_urls)))

        logger.info(f"\n{'=' * 60}")
        logger.info(f"Running PageSpeed Insights on {len(sampled_urls)} pages...")
        logger.info(f"{'=' * 60}\n")

        for i, url in enumerate(sampled_urls, 1):
            try:
                logger.info(f"[PSI {i}/{len(sampled_urls)}] Analyzing: {url}")
                psi_data = await self._psi_api.analyze(url, strategy=self.psi_strategy)

                # Store raw PSI result for saving to disk
                if psi_data:
                    self._psi_results[url] = psi_data

                if psi_data and url in self.site_data:
                    metadata = self.site_data[url]

                    # Lighthouse scores (lab data)
                    metadata.lighthouse_performance_score = psi_data.get('performance_score')
                    metadata.lighthouse_accessibility_score = psi_data.get('accessibility_score')
                    metadata.lighthouse_best_practices_score = psi_data.get('best_practices_score')
                    metadata.lighthouse_seo_score = psi_data.get('seo_score')
                    metadata.lighthouse_pwa_score = psi_data.get('pwa_score')

                    # Core Web Vitals from Lighthouse
                    metadata.lighthouse_fcp = psi_data.get('fcp')
                    metadata.lighthouse_lcp = psi_data.get('lcp')
                    metadata.lighthouse_cls = psi_data.get('cls')
                    metadata.lighthouse_tbt = psi_data.get('tbt')
                    metadata.lighthouse_si = psi_data.get('si')
                    metadata.lighthouse_tti = psi_data.get('tti')

                    # CrUX data (field data - real users)
                    crux_data = psi_data.get('crux_data')
                    if crux_data:
                        if 'lcp' in crux_data:
                            metadata.crux_lcp_percentile = crux_data['lcp'].get('percentile')
                            metadata.crux_lcp_category = crux_data['lcp'].get('category')
                        if 'fid' in crux_data:
                            metadata.crux_fid_percentile = crux_data['fid'].get('percentile')
                            metadata.crux_fid_category = crux_data['fid'].get('category')
                        if 'cls' in crux_data:
                            metadata.crux_cls_percentile = crux_data['cls'].get('percentile')
                            metadata.crux_cls_category = crux_data['cls'].get('category')
                        metadata.crux_overall_category = crux_data.get('overall_category')

                    # Update CWV status based on Lighthouse data
                    if metadata.lighthouse_lcp:
                        lcp_seconds = metadata.lighthouse_lcp / 1000
                        if lcp_seconds <= 2.5:
                            metadata.cwv_lcp_status = "good"
                        elif lcp_seconds <= 4.0:
                            metadata.cwv_lcp_status = "needs-improvement"
                        else:
                            metadata.cwv_lcp_status = "poor"

                    if metadata.lighthouse_cls is not None:
                        if metadata.lighthouse_cls <= 0.1:
                            metadata.cwv_cls_status = "good"
                        elif metadata.lighthouse_cls <= 0.25:
                            metadata.cwv_cls_status = "needs-improvement"
                        else:
                            metadata.cwv_cls_status = "poor"

                    self._psi_count += 1
                    perf = metadata.lighthouse_performance_score
                    logger.info(f"  ✓ Performance: {perf if perf else 'N/A'}")

            except Exception as e:
                error_msg = str(e) if str(e) else type(e).__name__
                logger.warning(f"  ⚠ PSI failed for {url}: {error_msg}")

    async def _launch_browser(self) -> None:
        """Launch browser and create context."""
        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
            args=self._launch_args,
        )

        self._context = await self._browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent=self._chrome_user_agent,
            locale="en-US",
            timezone_id="America/New_York",
        )

        logger.info("Browser launched successfully")

    async def _get_page_from_pool(self, max_retries: int = 3) -> Page:
        """Get a page from the pool, creating one if needed.

        Args:
            max_retries: Maximum attempts to get a valid page

        Returns:
            A reusable Page instance

        Raises:
            Exception: If unable to get a valid page after retries
        """
        for attempt in range(max_retries):
            # Check if we need to recover the context
            if self._session_errors >= self._max_session_errors:
                await self._recover_context()

            # Try to get an existing page from the pool
            try:
                page = self._page_pool.get_nowait()
                # Verify page is still usable
                try:
                    await page.evaluate("1 + 1")
                    return page
                except Exception as e:
                    # Page session is dead, decrement count and try again
                    self._session_errors += 1
                    logger.debug(f"Page session dead ({e}), errors={self._session_errors}")
                    async with self._page_lock:
                        self._pages_created = max(0, self._pages_created - 1)
                    try:
                        await page.close()
                    except Exception:
                        pass
                    continue
            except asyncio.QueueEmpty:
                pass

            # Create new page if pool is empty or page was dead
            async with self._page_lock:
                if self._pages_created < self._page_pool_size:
                    try:
                        page = await self._context.new_page()
                        self._pages_created += 1
                        logger.debug(f"Created new page ({self._pages_created}/{self._page_pool_size})")
                        return page
                    except Exception as e:
                        self._session_errors += 1
                        logger.warning(f"Failed to create page: {e}")
                        continue

            # Pool is at capacity, wait for a page to be returned
            try:
                page = await asyncio.wait_for(self._page_pool.get(), timeout=30.0)
                try:
                    await page.evaluate("1 + 1")
                    return page
                except Exception:
                    # Page died while waiting, try again
                    self._session_errors += 1
                    async with self._page_lock:
                        self._pages_created = max(0, self._pages_created - 1)
                    continue
            except asyncio.TimeoutError:
                logger.warning("Timeout waiting for page from pool")
                continue

        # All retries failed
        raise Exception("Unable to get a valid page after retries")

    async def _recover_context(self) -> None:
        """Recreate browser context (or entire browser) when too many session errors occur."""
        logger.warning(f"Recovering after {self._session_errors} session errors")

        async with self._page_lock:
            # Drain existing pool
            await self._drain_page_pool()

            # Try to close old context
            try:
                await self._context.close()
            except Exception:
                pass

            # Try to create new context
            try:
                self._context = await self._browser.new_context(
                    viewport={"width": 1920, "height": 1080},
                    user_agent=self._chrome_user_agent,
                    locale="en-US",
                    timezone_id="America/New_York",
                )
                logger.info("Browser context recovered")
            except Exception as e:
                # Browser itself is dead, need full relaunch
                logger.warning(f"Context creation failed ({e}), relaunching browser")
                try:
                    await self._browser.close()
                except Exception:
                    pass

                # Relaunch browser
                await self._launch_browser()
                logger.info("Browser relaunched successfully")

            # Reset error count
            self._session_errors = 0
            self._pages_created = 0

    async def _return_page_to_pool(self, page: Page) -> None:
        """Return a page to the pool after cleaning its state.

        Args:
            page: Page to return to pool
        """
        try:
            # Clear page state for reuse
            # Navigate to blank page to reset state
            await page.goto("about:blank", timeout=5000)
            # Remove all event listeners by recreating them on next use
            await self._page_pool.put(page)
        except Exception as e:
            # Page is dead, decrement count so a new one can be created
            logger.debug(f"Page cleanup failed, discarding: {e}")
            async with self._page_lock:
                self._pages_created = max(0, self._pages_created - 1)
            try:
                await page.close()
            except Exception:
                pass

    async def _drain_page_pool(self) -> None:
        """Close all pages in the pool."""
        while not self._page_pool.empty():
            try:
                page = self._page_pool.get_nowait()
                await page.close()
            except Exception:
                pass
        self._pages_created = 0

    async def _crawl_page(
        self,
        url: str,
        level: int,
        base_domain: str
    ) -> None:
        """Crawl a single page asynchronously using Playwright.

        Args:
            url: URL to crawl
            level: Current level in BFS
            base_domain: Base domain for internal link detection
        """
        async with self.semaphore:
            # Mark as visited
            self.visited_urls.add(url)

            # Respect rate limiting
            await self._respect_rate_limit(base_domain)

            logger.info(f"[L{level}] Crawling ({len(self.visited_urls)}/{self.max_pages}): {url}")

            page: Optional[Page] = None
            resources = ResourceMetrics()
            original_url = url
            page_from_pool = False

            # Handlers need to be defined outside try block for removal
            console_handler = None
            response_handler = None

            try:
                # Get page from pool (reuses existing tabs)
                page = await self._get_page_from_pool()
                page_from_pool = True

                # Set up console listener for errors/warnings
                def console_handler(msg):
                    if msg.type == "error":
                        resources.console_errors.append(msg.text[:500])
                    elif msg.type == "warning":
                        resources.console_warnings.append(msg.text[:500])

                page.on("console", console_handler)

                # Set up request listener for resource tracking
                def response_handler(response):
                    try:
                        resp_url = response.url
                        resp_domain = urlparse(resp_url).netloc
                        resource_type = response.request.resource_type

                        # Try to get content length
                        headers = response.headers
                        size = int(headers.get("content-length", 0))

                        resource_info = {
                            "url": resp_url[:200],
                            "size": size,
                            "status": response.status,
                        }

                        # Track by resource type
                        if resource_type == "stylesheet":
                            resources.css_files.append(resource_info)
                        elif resource_type == "script":
                            resources.js_files.append(resource_info)
                        elif resource_type in ("image", "img"):
                            resources.images.append(resource_info)
                        elif resource_type == "font":
                            resources.fonts.append(resource_info)

                        # Track third-party resources
                        if resp_domain and resp_domain != base_domain:
                            resource_info["domain"] = resp_domain
                            resources.third_party.append(resource_info)

                    except Exception:
                        pass

                page.on("response", response_handler)

                total_start = time.time()
                timing = TimingMetrics(url=url)

                # Navigate to the page
                nav_start = time.time()
                response = await page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=self.timeout
                )
                timing.navigation_time = time.time() - nav_start
                load_time = timing.navigation_time

                # Human-like behavior after page loads
                delay_start = time.time()
                await asyncio.sleep(random.uniform(1.0, 2.0))
                timing.human_delay_time = time.time() - delay_start

                mouse_start = time.time()
                await self._human_mouse_movement(page)
                timing.mouse_movement_time = time.time() - mouse_start

                scroll_start = time.time()
                await page.evaluate("window.scrollTo(0, 300)")
                await asyncio.sleep(random.uniform(0.3, 0.6))
                timing.scroll_time = time.time() - scroll_start

                # Try to fill address if prompted
                form_start = time.time()
                await self._try_fill_address(page)
                timing.form_fill_time = time.time() - form_start

                if response is None:
                    logger.warning(f"  ⚠️  No response received")
                    return

                # Track redirects
                final_url = page.url
                was_redirected = final_url != original_url
                if was_redirected:
                    resources.redirects = [original_url, final_url]

                if response.status != 200:
                    logger.warning(f"  ⚠️  Non-200 status: {response.status}")
                    if response.status in [403, 503]:
                        try:
                            body = await page.content()
                            if "captcha" in body.lower() or "robot" in body.lower():
                                logger.warning(f"  ⚠️  Likely bot detection triggered")
                        except Exception:
                            pass
                    return

                # Capture response headers
                response_headers = await response.all_headers()

                # Get rendered HTML content and extract metadata
                content_start = time.time()
                html = await page.content()

                # Get above-the-fold metrics
                above_fold_data = await self._get_above_fold_metrics(page)

                # Extract metadata with resource info
                metadata = self._extract_metadata(
                    url, html, response.status, load_time, response_headers,
                    resources, was_redirected, final_url, above_fold_data
                )
                timing.content_extract_time = time.time() - content_start

                # Store the page data
                self.site_data[url] = metadata

                # Save to disk immediately for resume capability
                self._save_page_to_disk(url, metadata)

                # Log with resource info
                total_kb = metadata.total_page_weight_bytes / 1024
                logger.info(
                    f"  ✓ Success - {metadata.word_count} words, "
                    f"{metadata.internal_links} links, "
                    f"{total_kb:.0f}KB, {load_time:.2f}s"
                )

                # Extract and queue internal links
                link_start = time.time()
                if len(self.visited_urls) < self.max_pages:
                    new_links = self._extract_internal_links(
                        url, metadata.links, base_domain
                    )

                    # Add new links to queue at next level
                    for link in new_links:
                        if link not in self.visited_urls:
                            self.queue.append((link, level + 1))

                    if new_links:
                        logger.info(f"  → Queued {len(new_links)} new links for L{level + 1}")

                timing.link_extract_time = time.time() - link_start
                timing.total_time = time.time() - total_start

                # Store and log timing
                self.timing_data.append(timing)
                timing.log_summary()

            except asyncio.TimeoutError:
                logger.error(f"  ⚠️  Timeout crawling {url}")
            except Exception as e:
                error_str = str(e).lower()
                # Detect browser/session crashes
                if "target" in error_str and "closed" in error_str:
                    self._session_errors += 3  # Fast-track recovery
                    logger.warning(f"  ⚠️  Session crashed: {url}")
                else:
                    logger.exception(f"  ⚠️  Unexpected error crawling {url}: {e}")
            finally:
                # Remove event handlers to prevent memory leaks
                if page:
                    try:
                        if console_handler:
                            page.remove_listener("console", console_handler)
                        if response_handler:
                            page.remove_listener("response", response_handler)
                    except Exception:
                        pass

                page_return_start = time.time()
                if page and page_from_pool:
                    # Return page to pool for reuse instead of closing
                    await self._return_page_to_pool(page)
                # Note: page_return_time not captured in timing since it's in finally

    async def _get_above_fold_metrics(self, page: Page) -> dict:
        """Get metrics for above-the-fold content.

        Args:
            page: Playwright page instance

        Returns:
            Dictionary with above-fold metrics
        """
        try:
            return await page.evaluate("""() => {
                const viewportHeight = window.innerHeight;
                const viewportWidth = window.innerWidth;

                // Get text content above fold
                const elements = document.body.querySelectorAll('p, h1, h2, h3, h4, h5, h6, li, span, a');
                let aboveFoldText = '';
                let aboveFoldImages = 0;

                elements.forEach(el => {
                    const rect = el.getBoundingClientRect();
                    if (rect.top < viewportHeight && rect.bottom > 0) {
                        aboveFoldText += ' ' + (el.textContent || '');
                    }
                });

                // Count images above fold
                document.querySelectorAll('img').forEach(img => {
                    const rect = img.getBoundingClientRect();
                    if (rect.top < viewportHeight && rect.bottom > 0) {
                        aboveFoldImages++;
                    }
                });

                return {
                    wordCount: aboveFoldText.trim().split(/\\s+/).filter(w => w.length > 0).length,
                    imageCount: aboveFoldImages
                };
            }""")
        except Exception:
            return {"wordCount": 0, "imageCount": 0}

    async def _respect_rate_limit(self, domain: str) -> None:
        """Ensure minimum delay between requests to same domain.

        Args:
            domain: Domain to rate limit
        """
        if domain in self.last_request_time:
            elapsed = time.time() - self.last_request_time[domain]
            if elapsed < self.rate_limit:
                # Add random jitter to rate limit
                jitter = random.uniform(0, 0.5)
                await asyncio.sleep(self.rate_limit - elapsed + jitter)

        self.last_request_time[domain] = time.time()

    async def _human_mouse_movement(self, page: Page) -> None:
        """Simulate human-like mouse movements on the page.

        Args:
            page: Playwright page instance
        """
        try:
            viewport = page.viewport_size
            if not viewport:
                return

            # Generate random points for mouse movement
            num_moves = random.randint(2, 5)
            for _ in range(num_moves):
                x = random.randint(100, viewport["width"] - 100)
                y = random.randint(100, viewport["height"] - 100)

                # Move mouse with random speed (steps)
                steps = random.randint(5, 15)
                await page.mouse.move(x, y, steps=steps)

                # Random micro-pause between movements
                await asyncio.sleep(random.uniform(0.05, 0.2))

            # Occasionally hover over a random element
            if random.random() < 0.3:
                try:
                    links = await page.query_selector_all("a")
                    if links:
                        link = random.choice(links)
                        await link.hover()
                        await asyncio.sleep(random.uniform(0.1, 0.3))
                except Exception:
                    pass
        except Exception:
            pass  # Don't fail crawl if mouse movement fails

    async def _try_fill_address(self, page: Page) -> bool:
        """Try to detect and fill address forms if address config is set.

        Args:
            page: Playwright page instance

        Returns:
            True if address was filled, False otherwise
        """
        if not self.address_config:
            return False

        try:
            # Common address input selectors
            address_selectors = [
                'input[name*="address" i]',
                'input[id*="address" i]',
                'input[placeholder*="address" i]',
                'input[aria-label*="address" i]',
                'input[name*="street" i]',
                'input[id*="street" i]',
            ]

            zip_selectors = [
                'input[name*="zip" i]',
                'input[id*="zip" i]',
                'input[name*="postal" i]',
                'input[id*="postal" i]',
                'input[placeholder*="zip" i]',
                'input[aria-label*="zip" i]',
            ]

            city_selectors = [
                'input[name*="city" i]',
                'input[id*="city" i]',
                'input[placeholder*="city" i]',
            ]

            filled = False

            # Try to fill address field
            for selector in address_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element and await element.is_visible():
                        await element.fill(self.address_config.get('address', ''))
                        logger.info(f"  → Filled address: {self.address_config.get('address')}")
                        filled = True
                        break
                except Exception:
                    continue

            # Try to fill zip code
            for selector in zip_selectors:
                try:
                    element = await page.query_selector(selector)
                    if element and await element.is_visible():
                        await element.fill(self.address_config.get('zip', ''))
                        logger.info(f"  → Filled zip: {self.address_config.get('zip')}")
                        filled = True
                        break
                except Exception:
                    continue

            # Try to fill city if available
            if self.address_config.get('city'):
                for selector in city_selectors:
                    try:
                        element = await page.query_selector(selector)
                        if element and await element.is_visible():
                            await element.fill(self.address_config.get('city', ''))
                            logger.info(f"  → Filled city: {self.address_config.get('city')}")
                            filled = True
                            break
                    except Exception:
                        continue

            # If we filled something, try to submit
            if filled:
                await asyncio.sleep(0.5)
                # Try common submit buttons
                submit_selectors = [
                    'button[type="submit"]',
                    'input[type="submit"]',
                    'button:has-text("Check")',
                    'button:has-text("Submit")',
                    'button:has-text("Continue")',
                    'button:has-text("Search")',
                ]
                for selector in submit_selectors:
                    try:
                        btn = await page.query_selector(selector)
                        if btn and await btn.is_visible():
                            await btn.click()
                            logger.info(f"  → Submitted address form")
                            await asyncio.sleep(2.0)  # Wait for response
                            break
                    except Exception:
                        continue

            return filled

        except Exception as e:
            logger.debug(f"Address fill failed: {e}")
            return False

    async def _load_robots_txt(self, start_url: str) -> None:
        """Load and parse robots.txt for the domain.

        Args:
            start_url: Starting URL to get domain from
        """
        parsed = urlparse(start_url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        robots_url = f"{base_url}/robots.txt"

        # Store robots.txt URL
        self.robots_txt_url = robots_url

        rp = RobotFileParser()
        rp.set_url(robots_url)

        try:
            # Fetch robots.txt using httpx with browser-like headers
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Accept": "text/plain,*/*",
            }
            async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
                response = await client.get(robots_url, headers=headers)
                if response.status_code == 200:
                    content = response.text
                    # Store robots.txt content
                    self.robots_txt_content = content
                    # Parse the content
                    rp.parse(content.splitlines())
                    logger.info(f"Loaded robots.txt from {robots_url}")
                    # Check if our user agent is blocked
                    if not rp.can_fetch("*", start_url):
                        logger.warning(f"robots.txt may block crawling of {start_url}")
                else:
                    logger.info(f"No robots.txt found at {robots_url} (status: {response.status_code})")
        except Exception as e:
            logger.warning(f"Could not load robots.txt: {e}")

        self.robots_parsers[base_url] = rp

    def _can_crawl(self, url: str) -> bool:
        """Check if URL can be crawled according to robots.txt.

        Args:
            url: URL to check

        Returns:
            True if URL can be crawled
        """
        parsed = urlparse(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"

        if base_url not in self.robots_parsers:
            return True  # If no robots.txt, allow

        return self.robots_parsers[base_url].can_fetch(self.user_agent, url)

    def _extract_metadata(
        self,
        url: str,
        html: str,
        status_code: int,
        load_time: float,
        response_headers: Dict[str, str],
        resources: Optional[ResourceMetrics] = None,
        was_redirected: bool = False,
        final_url: Optional[str] = None,
        above_fold_data: Optional[dict] = None,
    ) -> PageMetadata:
        """Extract metadata from HTML content.

        Args:
            url: The page URL
            html: HTML content
            status_code: HTTP status code
            load_time: Page load time in seconds
            response_headers: HTTP response headers
            resources: Resource loading metrics
            was_redirected: Whether page redirected
            final_url: Final URL after redirects
            above_fold_data: Above-fold content metrics

        Returns:
            PageMetadata object with extracted information
        """
        resources = resources or ResourceMetrics()
        above_fold_data = above_fold_data or {}
        soup = BeautifulSoup(html, "lxml")  # Use lxml for better performance
        base_domain = urlparse(url).netloc

        # Title
        title = soup.find("title")
        title_text = title.get_text(strip=True) if title else None

        # Meta description
        description_tag = soup.find("meta", attrs={"name": "description"})
        description = description_tag.get("content") if description_tag else None

        # Meta keywords
        keywords = []
        for meta in soup.find_all("meta", attrs={"name": "keywords"}):
            if meta.get("content"):
                keywords.extend([k.strip() for k in meta.get("content").split(",")])

        # Headers
        h1_tags = [h1.get_text(strip=True) for h1 in soup.find_all("h1")]
        h2_tags = [h2.get_text(strip=True) for h2 in soup.find_all("h2")]

        # Images
        all_images = soup.find_all("img")
        images = [
            {"src": img.get("src", ""), "alt": img.get("alt", "")}
            for img in all_images
        ]
        images_without_alt = sum(1 for img in all_images if not img.get("alt"))
        total_images = len(all_images)

        # Accessibility checks
        # Buttons without aria-label
        all_buttons = soup.find_all("button")
        buttons_without_aria = sum(
            1 for btn in all_buttons
            if not btn.get("aria-label") and not btn.get_text(strip=True)
        )

        # Links without context (no text, no aria-label, no title)
        all_links = soup.find_all("a", href=True)
        links_without_context = sum(
            1 for link in all_links
            if not link.get_text(strip=True) and not link.get("aria-label") and not link.get("title")
        )

        # Form inputs without labels
        all_inputs = soup.find_all("input")
        form_inputs_without_labels = sum(
            1 for inp in all_inputs
            if inp.get("type") not in ["hidden", "submit", "button"]
            and not inp.get("aria-label")
            and not inp.get("id")  # ID could connect to a label element
        )

        # Links
        links = []
        internal_links = 0
        external_links = 0

        for link in soup.find_all("a", href=True):
            href = link["href"]
            absolute_url = urljoin(url, href)
            links.append(absolute_url)

            if href.startswith("http"):
                link_domain = urlparse(href).netloc
                if link_domain == base_domain:
                    internal_links += 1
                else:
                    external_links += 1
            else:
                internal_links += 1

        # Word count
        text = soup.get_text(separator=" ", strip=True)
        word_count = len(text.split())

        # Canonical URL
        canonical = soup.find("link", attrs={"rel": "canonical"})
        canonical_url = canonical.get("href") if canonical else None

        # Robots meta directives
        robots_meta = soup.find("meta", attrs={"name": "robots"})
        robots_directives = {}
        if robots_meta:
            content = robots_meta.get("content", "").lower()
            robots_directives = {
                "noindex": "noindex" in content,
                "nofollow": "nofollow" in content,
                "noarchive": "noarchive" in content,
            }

        # Schema markup
        schema_scripts = soup.find_all("script", type="application/ld+json")
        schema_markup = []
        for script in schema_scripts:
            try:
                if script.string:
                    schema_data = json.loads(script.string)
                    schema_markup.append(schema_data)
            except (json.JSONDecodeError, ValueError):
                pass

        # Open Graph
        open_graph = {}
        for meta in soup.find_all("meta", property=True):
            if meta.get("property", "").startswith("og:"):
                open_graph[meta["property"]] = meta.get("content", "")

        # Viewport meta tag
        viewport_meta = None
        viewport_tag = soup.find("meta", attrs={"name": "viewport"})
        if viewport_tag:
            viewport_meta = viewport_tag.get("content")

        # Language attribute
        html_tag = soup.find("html")
        lang_attribute = html_tag.get("lang") if html_tag else None

        # Hreflang tags
        hreflang_tags = []
        for link in soup.find_all("link", rel="alternate", hreflang=True):
            hreflang_tags.append({
                "hreflang": link.get("hreflang"),
                "href": link.get("href"),
            })

        # Charset
        charset = None
        charset_tag = soup.find("meta", charset=True)
        if charset_tag:
            charset = charset_tag.get("charset")
        else:
            content_type_tag = soup.find("meta", attrs={"http-equiv": "Content-Type"})
            if content_type_tag:
                content = content_type_tag.get("content", "")
                if "charset=" in content:
                    charset = content.split("charset=")[-1].strip()

        # Twitter Card
        twitter_card = {}
        for meta in soup.find_all("meta", attrs={"name": lambda x: x and x.startswith("twitter:")}):
            twitter_card[meta["name"]] = meta.get("content", "")

        # Extract security headers
        security_headers = {
            k.lower(): v for k, v in response_headers.items()
            if k.lower() in [
                'strict-transport-security',
                'x-content-type-options',
                'x-frame-options',
                'x-xss-protection',
                'content-security-policy',
            ]
        }

        # Check HTTPS
        has_https = url.startswith("https://")

        # Analyze Core Web Vitals
        cwv_analyzer = CoreWebVitalsAnalyzer()
        cwv_score = cwv_analyzer.analyze(soup, url, load_time)

        # Analyze Structured Data
        sd_analyzer = StructuredDataAnalyzer()
        sd_score = sd_analyzer.analyze(soup, url)

        # Calculate resource metrics
        html_size = len(html.encode('utf-8'))
        css_size = sum(r.get("size", 0) for r in resources.css_files)
        js_size = sum(r.get("size", 0) for r in resources.js_files)
        img_size = sum(r.get("size", 0) for r in resources.images)
        font_size = sum(r.get("size", 0) for r in resources.fonts)
        third_party_size = sum(r.get("size", 0) for r in resources.third_party)
        total_weight = html_size + css_size + js_size + img_size + font_size

        # Text to HTML ratio
        text_to_html_ratio = len(text) / len(html) if html else 0

        # Content hash for duplicate detection
        content_hash = hashlib.md5(text.encode('utf-8')).hexdigest()

        # Third-party domains (unique)
        third_party_domains = list(set(
            r.get("domain", "") for r in resources.third_party if r.get("domain")
        ))

        # Lazy vs eager images
        lazy_images = sum(1 for img in all_images if img.get("loading") == "lazy")
        eager_images = total_images - lazy_images

        # Web fonts info
        web_fonts = [
            {"url": f.get("url", "")[:100], "size": f.get("size", 0)}
            for f in resources.fonts
        ]

        # Technology detection
        tech_detector = TechnologyDetector()
        tech_results = tech_detector.detect(url, html, response_headers or {})
        tech_summary = tech_detector.get_summary_stats(tech_results)

        return PageMetadata(
            url=url,
            title=title_text,
            description=description,
            keywords=keywords,
            h1_tags=h1_tags,
            h2_tags=h2_tags,
            images=images,
            images_without_alt=images_without_alt,
            total_images=total_images,
            buttons_without_aria=buttons_without_aria,
            links_without_context=links_without_context,
            form_inputs_without_labels=form_inputs_without_labels,
            links=links,
            internal_links=internal_links,
            external_links=external_links,
            word_count=word_count,
            load_time=load_time,
            status_code=status_code,
            canonical_url=canonical_url,
            robots_directives=robots_directives,
            schema_markup=schema_markup,
            open_graph=open_graph,
            viewport_meta=viewport_meta,
            lang_attribute=lang_attribute,
            hreflang_tags=hreflang_tags,
            charset=charset,
            content_text=text,
            has_https=has_https,
            security_headers=security_headers,
            twitter_card=twitter_card,
            redirect_chain=resources.redirects,
            # Core Web Vitals
            cwv_lcp_estimate=cwv_score.lcp_estimate,
            cwv_lcp_status=cwv_score.lcp_status,
            cwv_inp_status=cwv_score.inp_status,
            cwv_cls_status=cwv_score.cls_status,
            cwv_overall_status=cwv_score.overall_status,
            cwv_blocking_scripts=len(cwv_score.blocking_scripts),
            cwv_cls_risks=len(cwv_score.cls_risk_elements),
            cwv_render_blocking=len(cwv_score.render_blocking_resources),
            # Structured Data
            sd_schema_types=sd_score.schema_types,
            sd_jsonld_count=sd_score.jsonld_count,
            sd_microdata_count=sd_score.microdata_count,
            sd_validation_errors=sd_score.validation_errors,
            sd_validation_warnings=sd_score.validation_warnings,
            sd_rich_results=sd_score.rich_results_eligible,
            sd_missing_opportunities=sd_score.missing_opportunities,
            sd_overall_score=sd_score.overall_score,
            # Page Weight & Resources
            html_size_bytes=html_size,
            total_page_weight_bytes=total_weight,
            css_count=len(resources.css_files),
            css_size_bytes=css_size,
            js_count=len(resources.js_files),
            js_size_bytes=js_size,
            image_count=len(resources.images),
            image_size_bytes=img_size,
            font_count=len(resources.fonts),
            font_size_bytes=font_size,
            text_to_html_ratio=text_to_html_ratio,
            # Redirect & URL Info
            was_redirected=was_redirected,
            final_url=final_url,
            redirect_count=len(resources.redirects) - 1 if resources.redirects else 0,
            # Content Analysis
            content_hash=content_hash,
            above_fold_word_count=above_fold_data.get("wordCount", 0),
            above_fold_images=above_fold_data.get("imageCount", 0),
            # Console & Errors
            console_errors=resources.console_errors[:10],  # Limit to 10
            console_warnings=resources.console_warnings[:10],
            # Lazy Loading
            lazy_images_count=lazy_images,
            eager_images_count=eager_images,
            # Third-Party Resources
            third_party_domains=third_party_domains[:20],  # Limit to 20
            third_party_request_count=len(resources.third_party),
            third_party_size_bytes=third_party_size,
            # Fonts
            web_fonts=web_fonts,
            # Technology Detection
            technologies=tech_results.get('all_technologies', []),
            tech_by_category=tech_results.get('by_category', {}),
            tech_details=tech_results.get('details', {}),
            tech_ecommerce=tech_summary.get('primary_ecommerce'),
            tech_cms=tech_summary.get('primary_cms'),
            tech_web_server=tech_summary.get('web_server'),
            tech_has_cdn=tech_summary.get('has_cdn', False),
            tech_has_analytics=tech_summary.get('has_analytics', False),
        )

    def _normalize_url(self, url: str) -> str:
        """Normalize URL by removing fragments and trailing slashes.

        Args:
            url: URL to normalize

        Returns:
            Normalized URL
        """
        parsed = urlparse(url)
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        if parsed.query:
            normalized += f"?{parsed.query}"
        if normalized.endswith('/') and len(parsed.path) > 1:
            normalized = normalized[:-1]
        return normalized

    def _extract_internal_links(
        self, current_url: str, links: list[str], base_domain: str
    ) -> Set[str]:
        """Extract internal links from a list of URLs.

        Args:
            current_url: The current page URL
            links: List of all links found on the page
            base_domain: The base domain to match against

        Returns:
            Set of internal links that haven't been visited
        """
        internal_links = set()

        for link in links:
            try:
                absolute_url = urljoin(current_url, link)
                normalized_url = self._normalize_url(absolute_url)
                parsed = urlparse(normalized_url)

                # Check if it's internal
                if parsed.netloc == base_domain:
                    # Skip certain file types
                    if self._should_skip_url(parsed.path):
                        continue

                    # Only add if not already visited
                    if normalized_url not in self.visited_urls:
                        internal_links.add(normalized_url)

            except Exception:
                continue

        return internal_links

    def _should_skip_url(self, path: str) -> bool:
        """Check if URL should be skipped based on path.

        Args:
            path: URL path

        Returns:
            True if URL should be skipped
        """
        skip_extensions = {
            '.pdf', '.jpg', '.jpeg', '.png', '.gif', '.svg', '.webp',
            '.zip', '.tar', '.gz', '.mp4', '.mp3', '.avi', '.mov',
            '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
            '.css', '.js', '.xml', '.json', '.ico', '.woff', '.woff2', '.ttf'
        }

        # Skip slow/unimportant paths
        skip_patterns = {
            '/policies/',
        }

        path_lower = path.lower()
        if any(pattern in path_lower for pattern in skip_patterns):
            return True
        return any(path_lower.endswith(ext) for ext in skip_extensions)

    def get_crawl_summary(self) -> dict:
        """Get a summary of the crawl results.

        Returns:
            Dictionary with crawl statistics
        """
        if not self.site_data:
            return {}

        total_words = sum(page.word_count for page in self.site_data.values())
        total_images = sum(page.total_images for page in self.site_data.values())
        pages_with_issues = sum(
            1 for page in self.site_data.values()
            if not page.title or not page.description or not page.h1_tags
        )

        return {
            'total_pages': len(self.site_data),
            'total_words': total_words,
            'avg_words_per_page': total_words // len(self.site_data) if self.site_data else 0,
            'total_images': total_images,
            'pages_with_issues': pages_with_issues,
            'urls_crawled': list(self.site_data.keys()),
        }
