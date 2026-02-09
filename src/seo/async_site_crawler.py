"""Asynchronous site crawler with breadth-first search for multi-page analysis."""

import asyncio
from contextlib import asynccontextmanager
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
from seo.infrastructure import BrowserPool, AdaptiveRateLimiter, RateLimitConfig
from seo.constants import (
    DEFAULT_REQUEST_TIMEOUT_SECONDS,
    DEFAULT_MAX_PAGES_TO_CRAWL,
    DEFAULT_RATE_LIMIT_SECONDS,
    DEFAULT_MAX_CONCURRENT_REQUESTS,
    MAX_SESSION_ERRORS_BEFORE_ABORT,
    DEFAULT_PSI_SAMPLE_RATE,
    PSI_COVERAGE_THRESHOLD,
    MAX_PAGE_POOL_RETRIES,
    CRAWL_STATE_VERSION,
    DESKTOP_VIEWPORT_WIDTH,
    DESKTOP_VIEWPORT_HEIGHT,
    LCP_GOOD_SECONDS,
    LCP_POOR_SECONDS,
    CLS_GOOD_THRESHOLD,
    CLS_POOR_THRESHOLD,
    DEFAULT_MAX_RETRIES,
    EXPONENTIAL_BACKOFF_BASE,
    INITIAL_BACKOFF_DELAY_SECONDS,
    MAX_BACKOFF_DELAY_SECONDS,
)

logger = logging.getLogger(__name__)


class WAFBlockedException(Exception):
    """Raised when the crawler is blocked by a WAF/CDN."""
    def __init__(self, message: str, status_code: int = None, waf_provider: str = None):
        self.message = message
        self.status_code = status_code
        self.waf_provider = waf_provider
        super().__init__(message)


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
        max_pages: int = DEFAULT_MAX_PAGES_TO_CRAWL,
        max_depth: Optional[int] = None,
        rate_limit: float = DEFAULT_RATE_LIMIT_SECONDS,
        user_agent: Optional[str] = None,
        max_concurrent: int = DEFAULT_MAX_CONCURRENT_REQUESTS,
        timeout: int = DEFAULT_REQUEST_TIMEOUT_SECONDS,
        headless: bool = True,
        resume_state: Optional[dict] = None,
        output_manager: Optional["OutputManager"] = None,
        crawl_dir: Optional[Path] = None,
        enable_psi: bool = False,
        psi_api_key: Optional[str] = None,
        psi_strategy: str = "mobile",
        psi_sample_rate: float = DEFAULT_PSI_SAMPLE_RATE,
        address_config: Optional[dict] = None,
        ignore_robots: bool = False,
        browser_pool: Optional[BrowserPool] = None,
        rate_limiter: Optional[AdaptiveRateLimiter] = None,
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
            ignore_robots: Ignore robots.txt restrictions
            browser_pool: Optional BrowserPool for managed browser contexts (Epic 9)
            rate_limiter: Optional AdaptiveRateLimiter for intelligent rate limiting (Epic 10)
        """
        self.max_pages = max_pages
        self.max_depth = max_depth
        self.rate_limit = rate_limit
        self.user_agent = user_agent
        self.max_concurrent = max_concurrent
        self.timeout = timeout * 1000  # Playwright uses milliseconds
        self.headless = headless
        self.ignore_robots = ignore_robots

        # Epic 9/10: Optional infrastructure components
        self._browser_pool = browser_pool
        self._rate_limiter = rate_limiter
        self._using_pool = browser_pool is not None

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
            # Restore failed URLs and retry counts
            self.failed_urls = resume_state.get("failed_urls", {})
            self.retry_counts = resume_state.get("retry_counts", {})
            logger.info(
                f"Resuming crawl with {len(self.visited_urls)} pages crawled, "
                f"{len(self.failed_urls)} failed"
            )
        else:
            self.visited_urls: Set[str] = set()
            self.queue: deque = deque()
            self._started_at = datetime.now().isoformat()

        self.site_data: Dict[str, PageMetadata] = {}
        self.failed_urls: Dict[str, dict] = {}  # Track permanently failed URLs
        self.retry_counts: Dict[str, int] = {}  # Track retry attempts per URL
        self.max_retries = DEFAULT_MAX_RETRIES

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
        self._max_session_errors: int = MAX_SESSION_ERRORS_BEFORE_ABORT

        # Store playwright instance for browser recovery
        self._playwright = None
        self._launch_args = None

        # PageSpeed Insights API integration
        self.enable_psi = enable_psi and psi_api_key is not None
        self.psi_sample_rate = max(0.0, min(1.0, psi_sample_rate))
        self.psi_strategy = psi_strategy
        self._psi_api: Optional[PageSpeedInsightsAPI] = None
        self._psi_count = 0
        self._psi_results: Dict[str, dict] = {}  # Store raw PSI results for saving
        self._psi_failures: Dict[str, str] = {}  # Track failed PSI requests with error reasons
        self._psi_sampled_urls: List[str] = []   # URLs that were sampled for PSI analysis
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

        # WAF/CDN blocking detection
        self._waf_blocked: bool = False
        self._waf_provider: Optional[str] = None
        self._waf_status_code: Optional[int] = None

        # Set Chrome user agent early so it's consistent everywhere
        self._chrome_user_agent = self.user_agent or (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        )

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

    def get_psi_coverage(self) -> Dict[str, any]:
        """Get PageSpeed Insights coverage statistics.

        Returns:
            Dictionary with comprehensive PSI coverage data for reporting:
            - total_pages: Total pages crawled
            - pages_sampled: Number of pages selected for PSI analysis
            - pages_with_psi: Number of pages with successful PSI data
            - pages_failed: Number of pages where PSI analysis failed
            - pages_skipped: Number of pages not sampled
            - coverage_percentage: Percentage of crawled pages with PSI data
            - sample_coverage_percentage: Percentage of sampled pages with PSI data
            - failed_urls: Dict mapping failed URLs to error messages
            - skipped_urls: List of URLs not sampled for PSI
            - meets_threshold: Whether coverage meets configured threshold (default 90%)
            - threshold: The configured coverage threshold percentage
        """
        total_pages = len(self.site_data) if self.site_data else 0
        pages_sampled = len(self._psi_sampled_urls)
        pages_with_psi = self._psi_count
        pages_failed = len(self._psi_failures)

        # Calculate skipped URLs (not sampled)
        sampled_set = set(self._psi_sampled_urls)
        skipped_urls = [url for url in (self.site_data or {}).keys() if url not in sampled_set]

        # Calculate coverage percentages
        coverage_pct = (pages_with_psi / total_pages * 100) if total_pages > 0 else 0
        sample_coverage_pct = (pages_with_psi / pages_sampled * 100) if pages_sampled > 0 else 0

        return {
            'total_pages': total_pages,
            'pages_sampled': pages_sampled,
            'pages_with_psi': pages_with_psi,
            'pages_failed': pages_failed,
            'pages_skipped': len(skipped_urls),
            'coverage_percentage': round(coverage_pct, 1),
            'sample_coverage_percentage': round(sample_coverage_pct, 1),
            'sample_rate': self.psi_sample_rate,
            'failed_urls': self._psi_failures.copy(),
            'skipped_urls': skipped_urls,
            'meets_threshold': coverage_pct >= PSI_COVERAGE_THRESHOLD,
            'threshold': PSI_COVERAGE_THRESHOLD,
        }

    def get_state(self, status: str = "running") -> dict:
        """Get the current crawl state for checkpointing/resume.

        Args:
            status: Current status ("running", "paused", or "completed")

        Returns:
            State dictionary suitable for saving
        """
        return {
            "version": CRAWL_STATE_VERSION,
            "status": status,
            "config": {
                "start_url": self._start_url,
                "max_pages": self.max_pages,
                "max_depth": self.max_depth,
                "rate_limit": self.rate_limit,
            },
            "progress": {
                "pages_crawled": len(self.visited_urls),
                "pages_failed": len(self.failed_urls),
                "started_at": self._started_at,
                "last_updated": datetime.now().isoformat(),
            },
            "visited_urls": list(self.visited_urls),
            "queue": [
                {"url": url, "depth": depth} for url, depth in self.queue
            ],
            "failed_urls": self.failed_urls,
            "retry_counts": self.retry_counts,
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

        # Epic 9: Use BrowserPool when available
        if self._using_pool and self._browser_pool:
            logger.info(f"Using BrowserPool (Epic 9 infrastructure)\n")
            await self._crawl_with_pool(start_url, base_domain)
        else:
            logger.info(f"Using rebrowser-playwright (undetected chromium)\n")
            await self._crawl_with_internal_pool(start_url, base_domain)

        # Run PageSpeed Insights analysis on sampled pages
        if self.enable_psi and self._psi_api:
            await self._run_psi_analysis()

        # Save final checkpoint with completed status
        self._save_checkpoint("completed")

        logger.info(f"\n{'=' * 60}")
        logger.info(f"Crawl complete! Processed {len(self.site_data)} pages")
        if self.failed_urls:
            logger.info(f"Failed pages: {len(self.failed_urls)} (after retries)")
        if sum(self.retry_counts.values()) > 0:
            logger.info(
                f"Retry stats: {sum(self.retry_counts.values())} retries "
                f"across {len(self.retry_counts)} URLs"
            )
        if self._psi_count > 0 or self._psi_failures:
            coverage = self.get_psi_coverage()
            logger.info(f"PageSpeed Insights: {coverage['pages_with_psi']}/{coverage['total_pages']} pages ({coverage['coverage_percentage']:.1f}% coverage)")
            if coverage['pages_failed'] > 0:
                logger.warning(f"PSI failures: {coverage['pages_failed']} pages failed")
            if not coverage['meets_threshold']:
                logger.warning(f"PSI coverage below {PSI_COVERAGE_THRESHOLD}% threshold")
        logger.info(f"{'=' * 60}\n")

        return self.site_data

    async def _crawl_with_pool(self, start_url: str, base_domain: str) -> None:
        """Execute crawl using BrowserPool (Epic 9).

        Args:
            start_url: Starting URL for the crawl
            base_domain: Base domain for internal link detection
        """
        try:
            # Start the browser pool
            await self._browser_pool.start()
            logger.info(f"BrowserPool started with {self._browser_pool.max_size} contexts")

            await self._execute_crawl_loop(base_domain)

        except WAFBlockedException:
            raise  # Re-raise WAF exceptions
        finally:
            # Cleanup pool
            if self._browser_pool:
                await self._browser_pool.stop()

    async def _crawl_with_internal_pool(self, start_url: str, base_domain: str) -> None:
        """Execute crawl using internal page pool (legacy mode).

        Args:
            start_url: Starting URL for the crawl
            base_domain: Base domain for internal link detection
        """
        # Launch Playwright browser
        async with async_playwright() as p:
            # Store playwright instance for recovery
            self._playwright = p

            # Minimal launch args - avoid anything that looks like automation
            self._launch_args = [
                "--disable-blink-features=AutomationControlled",
            ]

            # Launch browser and create context
            await self._launch_browser()

            try:
                await self._execute_crawl_loop(base_domain)
            except WAFBlockedException:
                raise  # Re-raise WAF exceptions
            finally:
                # Cleanup - close all pooled pages first
                await self._drain_page_pool()
                if self._context:
                    await self._context.close()
                if self._browser:
                    await self._browser.close()

    async def _execute_crawl_loop(self, base_domain: str) -> None:
        """Execute the main crawl loop (shared by pool and internal pool modes).

        Args:
            base_domain: Base domain for internal link detection
        """
        current_level = 1

        while self.queue and len(self.visited_urls) < self.max_pages:
            # Collect batch of URLs at current level
            batch = []
            while self.queue and len(batch) < self.max_concurrent:
                url, level = self.queue.popleft()

                if url in self.visited_urls:
                    continue
                if self.max_depth is not None and level > self.max_depth:
                    continue
                if not self._can_crawl(url):
                    logger.warning(f"Skipping {url} (disallowed by robots.txt)")
                    continue

                batch.append((url, level))

            if not batch:
                continue

            level = batch[0][1]
            if level > current_level:
                logger.info(f"\n--- Moving to Level {level} ---\n")
                current_level = level

            tasks = [
                self._crawl_page(url, level, base_domain)
                for url, level in batch
            ]

            await asyncio.gather(*tasks, return_exceptions=True)

            # Check for WAF blocking
            if self._waf_blocked:
                logger.error(f"\n{'=' * 60}")
                logger.error(f"🛑 CRAWL ABORTED: Blocked by {self._waf_provider}")
                logger.error(f"   Status code: {self._waf_status_code}")
                logger.error(f"   This site is protected by WAF/CDN that blocks crawlers.")
                logger.error(f"{'=' * 60}\n")
                raise WAFBlockedException(
                    f"Blocked by {self._waf_provider}",
                    status_code=self._waf_status_code,
                    waf_provider=self._waf_provider,
                )

            if len(self.visited_urls) % 10 == 0:
                self._save_checkpoint("running")

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

        # Track which URLs were sampled for coverage reporting
        self._psi_sampled_urls = sampled_urls.copy()

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
                        if lcp_seconds <= LCP_GOOD_SECONDS:
                            metadata.cwv_lcp_status = "good"
                        elif lcp_seconds <= LCP_POOR_SECONDS:
                            metadata.cwv_lcp_status = "needs-improvement"
                        else:
                            metadata.cwv_lcp_status = "poor"

                    if metadata.lighthouse_cls is not None:
                        if metadata.lighthouse_cls <= CLS_GOOD_THRESHOLD:
                            metadata.cwv_cls_status = "good"
                        elif metadata.lighthouse_cls <= CLS_POOR_THRESHOLD:
                            metadata.cwv_cls_status = "needs-improvement"
                        else:
                            metadata.cwv_cls_status = "poor"

                    self._psi_count += 1
                    perf = metadata.lighthouse_performance_score
                    logger.info(f"  ✓ Performance: {perf if perf else 'N/A'}")

            except Exception as e:
                error_msg = str(e) if str(e) else type(e).__name__
                self._psi_failures[url] = error_msg
                logger.warning(f"  ⚠ PSI failed for {url}: {error_msg}")

    async def _launch_browser(self) -> None:
        """Launch browser and create context with stealth settings."""
        # Use installed Chrome instead of Playwright's Chromium for better stealth
        # Chrome has a legitimate TLS fingerprint that WAFs trust
        self._browser = await self._playwright.chromium.launch(
            headless=self.headless,
            args=self._launch_args,
            channel="chrome",  # Use installed Chrome, not bundled Chromium
        )

        self._context = await self._browser.new_context(
            viewport={"width": DESKTOP_VIEWPORT_WIDTH, "height": DESKTOP_VIEWPORT_HEIGHT},
            user_agent=self._chrome_user_agent,
            locale="en-US",
            timezone_id="America/New_York",
            device_scale_factor=1,
            has_touch=False,
            is_mobile=False,
            java_script_enabled=True,
            color_scheme="light",
            extra_http_headers={
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Sec-Ch-Ua": '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
                "Sec-Ch-Ua-Mobile": "?0",
                "Sec-Ch-Ua-Platform": '"macOS"',
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1",
                "Upgrade-Insecure-Requests": "1",
            },
        )

        # Add stealth scripts to hide automation indicators
        await self._context.add_init_script("""
            // Override webdriver property
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });

            // Override plugins to look like a real browser
            Object.defineProperty(navigator, 'plugins', {
                get: () => [
                    { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
                    { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: '' },
                    { name: 'Native Client', filename: 'internal-nacl-plugin', description: '' },
                ],
            });

            // Override languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en'],
            });

            // Fix permissions query
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );

            // Override chrome runtime
            window.chrome = {
                runtime: {},
            };

            // Remove automation-related properties
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
        """)

        logger.info("Browser launched successfully")

    @asynccontextmanager
    async def _acquire_page(self):
        """Acquire a page for crawling using BrowserPool or internal pool (Epic 9).

        This context manager provides a unified interface for page acquisition.
        When BrowserPool is available, uses pool.acquire() for managed contexts.
        Otherwise, falls back to the internal page pool.

        Yields:
            Tuple of (page, from_pool) where from_pool indicates cleanup method
        """
        if self._using_pool and self._browser_pool:
            # Epic 9: Use BrowserPool for managed contexts
            async with self._browser_pool.acquire() as (context, page):
                yield page, False  # Pool handles cleanup
        else:
            # Fallback: Use internal page pool
            page = await self._get_page_from_pool()
            try:
                yield page, True  # We handle cleanup
            finally:
                await self._return_page_to_pool(page)

    async def _get_page_from_pool(self, max_retries: int = MAX_PAGE_POOL_RETRIES) -> Page:
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
                    viewport={"width": DESKTOP_VIEWPORT_WIDTH, "height": DESKTOP_VIEWPORT_HEIGHT},
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

    def _calculate_backoff_delay(self, retry_count: int) -> float:
        """Calculate exponential backoff delay with jitter.

        Args:
            retry_count: Number of retries already attempted (0-indexed)

        Returns:
            Delay in seconds before next retry
        """
        # Exponential backoff: base_delay * (2 ^ retry_count)
        delay = INITIAL_BACKOFF_DELAY_SECONDS * (EXPONENTIAL_BACKOFF_BASE ** retry_count)
        # Cap at maximum delay
        delay = min(delay, MAX_BACKOFF_DELAY_SECONDS)
        # Add jitter (±25%) to prevent thundering herd
        jitter = delay * random.uniform(-0.25, 0.25)
        return delay + jitter

    def _should_retry(self, url: str, error: Exception) -> bool:
        """Determine if a failed URL should be retried.

        Args:
            url: The URL that failed
            error: The exception that occurred

        Returns:
            True if the URL should be retried
        """
        # Don't retry if max retries exceeded
        current_retries = self.retry_counts.get(url, 0)
        if current_retries >= self.max_retries:
            return False

        # Don't retry for certain error types that won't resolve
        error_str = str(error).lower()

        # These errors are unlikely to resolve with retry
        non_retryable_patterns = [
            "net::err_name_not_resolved",  # DNS failure
            "net::err_connection_refused",  # Server not accepting connections
            "invalid url",
            "protocol error",
        ]

        for pattern in non_retryable_patterns:
            if pattern in error_str:
                return False

        # Retry for timeouts, connection resets, and other transient errors
        return True

    def _record_failure(self, url: str, error: Exception, level: int) -> None:
        """Record a permanently failed URL.

        Args:
            url: The URL that failed
            error: The exception that occurred
            level: The crawl level where failure occurred
        """
        self.failed_urls[url] = {
            "url": url,
            "error": str(error)[:500],
            "error_type": type(error).__name__,
            "level": level,
            "retries": self.retry_counts.get(url, 0),
            "failed_at": datetime.now().isoformat(),
        }
        logger.warning(
            f"  ❌ Permanently failed after {self.retry_counts.get(url, 0)} retries: {url}"
        )

    async def _handle_crawl_error(
        self, url: str, error: Exception, level: int
    ) -> None:
        """Handle a crawl error with retry logic.

        Args:
            url: The URL that failed
            error: The exception that occurred
            level: The crawl level where failure occurred
        """
        # Remove from visited so it can be retried
        self.visited_urls.discard(url)

        if self._should_retry(url, error):
            # Increment retry count
            current_retries = self.retry_counts.get(url, 0)
            self.retry_counts[url] = current_retries + 1

            # Calculate backoff delay
            backoff_delay = self._calculate_backoff_delay(current_retries)

            logger.info(
                f"  🔄 Will retry ({current_retries + 1}/{self.max_retries}) "
                f"after {backoff_delay:.1f}s: {url}"
            )

            # Wait for backoff delay before requeuing
            await asyncio.sleep(backoff_delay)

            # Add back to queue at the same level (prioritize retries)
            self.queue.appendleft((url, level))
        else:
            # Record permanent failure
            self._record_failure(url, error, level)

    async def _execute_crawl(
        self,
        page: Page,
        url: str,
        level: int,
        base_domain: str,
        resources: ResourceMetrics,
        original_url: str,
    ) -> None:
        """Execute the crawl logic on an acquired page (Epic 9 helper).

        This method contains the core crawl logic extracted to support both
        BrowserPool and internal page pool modes.

        Args:
            page: Playwright page instance
            url: URL to crawl
            level: Current level in BFS
            base_domain: Base domain for internal link detection
            resources: ResourceMetrics instance to populate
            original_url: Original URL before any redirects
        """
        console_handler = None
        response_handler = None

        try:
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

                    headers = response.headers
                    size = int(headers.get("content-length", 0))

                    resource_info = {
                        "url": resp_url[:200],
                        "size": size,
                        "status": response.status,
                    }

                    if resource_type == "stylesheet":
                        resources.css_files.append(resource_info)
                    elif resource_type == "script":
                        resources.js_files.append(resource_info)
                    elif resource_type in ("image", "img"):
                        resources.images.append(resource_info)
                    elif resource_type == "font":
                        resources.fonts.append(resource_info)

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
                wait_until="load",
                timeout=self.timeout
            )
            timing.navigation_time = time.time() - nav_start
            load_time = timing.navigation_time

            # Record metrics for rate limiter (Epic 10)
            if response:
                self._record_request_metrics(load_time, True, response.status)

            # Human-like behavior after page loads
            delay_start = time.time()
            await asyncio.sleep(random.uniform(2.0, 3.5))
            timing.human_delay_time = time.time() - delay_start

            mouse_start = time.time()
            await self._human_mouse_movement(page)
            timing.mouse_movement_time = time.time() - mouse_start

            scroll_start = time.time()
            await page.evaluate("window.scrollTo(0, 300)")
            await asyncio.sleep(random.uniform(0.5, 1.0))
            await page.evaluate("window.scrollTo(0, 0)")
            await asyncio.sleep(random.uniform(0.3, 0.6))
            timing.scroll_time = time.time() - scroll_start

            await self._handle_popups(page)

            form_start = time.time()
            await self._try_fill_address(page)
            timing.form_fill_time = time.time() - form_start

            if response is None:
                logger.warning(f"  ⚠️  No response received")
                return

            final_url = page.url
            was_redirected = final_url != original_url
            if was_redirected:
                resources.redirects = [original_url, final_url]
                if self._should_skip_url("", final_url):
                    logger.info(f"  → Skipping payment/external redirect: {final_url}")
                    return

            # Check for WAF/CDN blocking
            try:
                page_html = await page.content()
                resp_headers = await response.all_headers()
                waf_provider = self._detect_waf_block(response.status, page_html, resp_headers)

                if waf_provider:
                    logger.info(f"  ⏳ Potential WAF challenge detected, waiting for resolution...")
                    await asyncio.sleep(3.0)
                    await self._human_mouse_movement(page)
                    await asyncio.sleep(1.0)

                    page_html = await page.content()
                    waf_provider = self._detect_waf_block(response.status, page_html, resp_headers)

                    if waf_provider:
                        self._waf_blocked = True
                        self._waf_provider = waf_provider
                        self._waf_status_code = response.status
                        logger.error(f"  🛑 WAF/CDN BLOCKED by {waf_provider} (status: {response.status})")
                        return
                    else:
                        logger.info(f"  ✓ WAF challenge passed!")
            except Exception as e:
                logger.debug(f"WAF detection check failed: {e}")

            if response.status != 200:
                logger.warning(f"  ⚠️  Non-200 status: {response.status}")
                return

            response_headers = await response.all_headers()

            content_start = time.time()
            html = await page.content()
            above_fold_data = await self._get_above_fold_metrics(page)

            metadata = self._extract_metadata(
                url, html, response.status, load_time, response_headers,
                resources, was_redirected, final_url, above_fold_data
            )
            timing.content_extract_time = time.time() - content_start

            self.site_data[url] = metadata
            self._save_page_to_disk(url, metadata)

            total_kb = metadata.total_page_weight_bytes / 1024
            logger.info(
                f"  ✓ Success - {metadata.word_count} words, "
                f"{metadata.internal_links} links, "
                f"{total_kb:.0f}KB, {load_time:.2f}s"
            )

            link_start = time.time()
            if len(self.visited_urls) < self.max_pages:
                new_links = self._extract_internal_links(
                    url, metadata.links, base_domain
                )
                for link in new_links:
                    if link not in self.visited_urls:
                        self.queue.append((link, level + 1))
                if new_links:
                    logger.info(f"  → Queued {len(new_links)} new links for L{level + 1}")

            timing.link_extract_time = time.time() - link_start
            timing.total_time = time.time() - total_start

            self.timing_data.append(timing)
            timing.log_summary()

        except asyncio.TimeoutError as e:
            logger.error(f"  ⚠️  Timeout crawling {url}")
            # M1.3: Timeouts indicate network congestion, trigger moderate backoff
            self._record_request_metrics(30.0, False, 0, error_type="timeout")
            await self._handle_crawl_error(url, e, level)
        except Exception as e:
            error_str = str(e).lower()
            if "target" in error_str and "closed" in error_str:
                # M1.3: Browser crashes are infrastructure issues, no rate impact
                self._record_request_metrics(0.0, False, 0, error_type="browser_crash")
                self._session_errors += 3
                logger.warning(f"  ⚠️  Session crashed: {url}")
                await self._handle_crawl_error(url, e, level)
            elif "name resolution" in error_str or "dns" in error_str:
                # M1.3: DNS failures may indicate network issues
                self._record_request_metrics(0.0, False, 0, error_type="dns")
                logger.error(f"  ⚠️  DNS resolution failed for {url}: {e}")
                await self._handle_crawl_error(url, e, level)
            elif "connection" in error_str or "reset" in error_str:
                # M1.3: Connection errors trigger light backoff
                self._record_request_metrics(0.0, False, 0, error_type="network")
                logger.error(f"  ⚠️  Network error crawling {url}: {e}")
                await self._handle_crawl_error(url, e, level)
            else:
                # M1.3: Unknown errors don't trigger rate limiting backoff
                self._record_request_metrics(0.0, False, 0, error_type="unknown")
                logger.error(f"  ⚠️  Unexpected error crawling {url}: {e}")
                await self._handle_crawl_error(url, e, level)
        finally:
            if page:
                try:
                    if console_handler:
                        page.remove_listener("console", console_handler)
                    if response_handler:
                        page.remove_listener("response", response_handler)
                except Exception:
                    pass

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

            resources = ResourceMetrics()
            original_url = url

            # Epic 9: Use BrowserPool when available
            if self._using_pool and self._browser_pool:
                async with self._browser_pool.acquire() as (context, page):
                    await self._execute_crawl(
                        page, url, level, base_domain, resources, original_url
                    )
                return

            # Fallback: Use internal page pool
            page: Optional[Page] = None

            try:
                page = await self._get_page_from_pool()
                await self._execute_crawl(
                    page, url, level, base_domain, resources, original_url
                )
            finally:
                if page:
                    await self._return_page_to_pool(page)

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

    async def _handle_popups(self, page: Page) -> bool:
        """Detect and dismiss modal popups (newsletter signups, cookie banners, etc.).

        Args:
            page: Playwright page instance

        Returns:
            True if a popup was handled
        """
        handled = False

        # Common close button selectors for modals
        close_selectors = [
            # X buttons
            'button[aria-label="Close"]',
            'button[aria-label="close"]',
            'button[aria-label="Dismiss"]',
            '[aria-label="Close"]',
            '[aria-label="close"]',
            '.close-button',
            '.modal-close',
            '.popup-close',
            '.dialog-close',
            'button.close',
            '[data-dismiss="modal"]',
            '[data-close]',
            '.modal button svg',  # X icon buttons
            '.modal [class*="close"]',
            '[class*="modal"] [class*="close"]',
            '[class*="popup"] [class*="close"]',
            '[role="dialog"] button[class*="close"]',
            '[role="dialog"] [aria-label*="close" i]',
            # Specific patterns
            'button:has(svg[class*="close"])',
            '[class*="newsletter"] button[class*="close"]',
            '[class*="signup"] button[class*="close"]',
        ]

        # Cookie consent buttons
        cookie_selectors = [
            'button:has-text("Accept")',
            'button:has-text("Accept All")',
            'button:has-text("Accept Cookies")',
            'button:has-text("Allow")',
            'button:has-text("Allow All")',
            'button:has-text("Got it")',
            'button:has-text("OK")',
            'button:has-text("Agree")',
            'button:has-text("I Agree")',
            '[id*="cookie"] button',
            '[class*="cookie"] button',
            '[id*="consent"] button',
            '[class*="consent"] button',
            '#onetrust-accept-btn-handler',
            '.cc-accept',
            '.cookie-accept',
        ]

        # "No thanks" / decline newsletter buttons
        decline_selectors = [
            'button:has-text("No thanks")',
            'button:has-text("No, thanks")',
            'button:has-text("Maybe later")',
            'button:has-text("Not now")',
            'button:has-text("Skip")',
            'button:has-text("Close")',
            'a:has-text("No thanks")',
            'a:has-text("Maybe later")',
            '[class*="modal"] button:has-text("No")',
        ]

        all_selectors = close_selectors + cookie_selectors + decline_selectors

        for selector in all_selectors:
            try:
                elements = await page.query_selector_all(selector)
                for element in elements:
                    if await element.is_visible():
                        await element.click()
                        logger.info(f"  → Dismissed popup: {selector}")
                        handled = True
                        await asyncio.sleep(0.5)
                        break
                if handled:
                    break
            except Exception:
                continue

        return handled

    async def _respect_rate_limit(self, domain: str) -> float:
        """Ensure minimum delay between requests to same domain.

        Args:
            domain: Domain to rate limit

        Returns:
            Time waited in seconds
        """
        # Use AdaptiveRateLimiter when available (Epic 10)
        if self._rate_limiter:
            wait_time = await self._rate_limiter.wait()
            return wait_time

        # Fallback to simple rate limiting
        wait_time = 0.0
        if domain in self.last_request_time:
            elapsed = time.time() - self.last_request_time[domain]
            if elapsed < self.rate_limit:
                # Add random jitter to rate limit
                jitter = random.uniform(0, 0.5)
                wait_time = self.rate_limit - elapsed + jitter
                await asyncio.sleep(wait_time)

        self.last_request_time[domain] = time.time()
        return wait_time

    def _record_request_metrics(
        self,
        response_time: float,
        success: bool,
        status_code: int = 200,
        error_type: str | None = None,
    ) -> None:
        """Record request metrics in rate limiter when available (Epic 10).

        Provides comprehensive error feedback to the rate limiter for intelligent
        backoff decisions per M1.3 recommendations.

        Args:
            response_time: Time taken for the request
            success: Whether the request succeeded
            status_code: HTTP status code
            error_type: Classification of error (network, timeout, browser, etc.)

        Error classification and rate limiter impact:
        - HTTP 429/503: Rate limiting errors, trigger full backoff
        - HTTP 500-599: Server errors, trigger moderate backoff
        - HTTP 400-499 (except 429): Client errors, no rate impact
        - timeout: Network congestion, trigger moderate backoff
        - network: Connection issues, trigger light backoff
        - browser_crash: Infrastructure error, no rate impact
        """
        if not self._rate_limiter:
            return

        # Determine if this error should affect rate limiting
        # Per M1.3: Error types have different weights for rate limiting
        should_trigger_backoff = False

        if not success:
            # HTTP 429 and 503 are explicit rate limiting signals
            if status_code in (429, 503):
                should_trigger_backoff = True
            # Other 5xx errors indicate server issues
            elif 500 <= status_code < 600:
                should_trigger_backoff = True
            # Timeouts and network errors suggest congestion
            elif error_type in ("timeout", "network", "dns"):
                should_trigger_backoff = True
            # Browser crashes are infrastructure issues, not server issues
            elif error_type == "browser_crash":
                should_trigger_backoff = False
            # Client errors (4xx except 429) don't affect rate limiting
            elif 400 <= status_code < 500:
                should_trigger_backoff = False

        self._rate_limiter.record_request(
            response_time=response_time,
            success=success and not should_trigger_backoff,
        )

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
                "User-Agent": self._chrome_user_agent,
                "Accept": "text/plain,text/html,*/*",
                "Accept-Language": "en-US,en;q=0.9",
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
                    # Only store parser if we actually parsed content
                    self.robots_parsers[base_url] = rp
                else:
                    logger.info(f"No robots.txt found at {robots_url} (status: {response.status_code})")
        except Exception as e:
            logger.warning(f"Could not load robots.txt: {e}")

    def _can_crawl(self, url: str) -> bool:
        """Check if URL can be crawled according to robots.txt.

        Args:
            url: URL to check

        Returns:
            True if URL can be crawled
        """
        if self.ignore_robots:
            return True

        parsed = urlparse(url)
        base_url = f"{parsed.scheme}://{parsed.netloc}"

        if base_url not in self.robots_parsers:
            return True  # If no robots.txt, allow

        user_agent = self.user_agent or self._chrome_user_agent or "*"
        return self.robots_parsers[base_url].can_fetch(user_agent, url)

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
                    # Skip certain paths, file types, and payment domains
                    if self._should_skip_url(parsed.path, normalized_url):
                        continue

                    # Only add if not already visited
                    if normalized_url not in self.visited_urls:
                        internal_links.add(normalized_url)

            except Exception:
                continue

        return internal_links

    def _should_skip_url(self, path: str, full_url: str = None) -> bool:
        """Check if URL should be skipped based on path or domain.

        Args:
            path: URL path
            full_url: Optional full URL for domain checking

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
        skip_path_patterns = {
            '/policies/',
            '/checkout/',
            '/cart/',
            '/payment/',
            '/pay/',
            '/order/',
            '/account/login',
            '/account/register',
            '/signin',
            '/signup',
            '/login',
            '/register',
        }

        # Skip external payment/third-party domains
        skip_domains = {
            'payments.klarna.com',
            'klarna.com',
            'paypal.com',
            'pay.google.com',
            'apple.com/pay',
            'affirm.com',
            'afterpay.com',
            'sezzle.com',
            'stripe.com',
            'checkout.shopify.com',
        }

        path_lower = path.lower()

        # Check path patterns
        if any(pattern in path_lower for pattern in skip_path_patterns):
            return True

        # Check extensions
        if any(path_lower.endswith(ext) for ext in skip_extensions):
            return True

        # Check domain if full URL provided
        if full_url:
            url_lower = full_url.lower()
            for domain in skip_domains:
                if domain in url_lower:
                    return True

        return False

    def _detect_waf_block(self, status_code: int, html: str, response_headers: dict) -> Optional[str]:
        """Detect if the response indicates WAF/CDN blocking.

        Args:
            status_code: HTTP status code
            html: Page HTML content
            response_headers: Response headers

        Returns:
            WAF provider name if blocked, None otherwise
        """
        html_lower = html.lower() if html else ""

        # Check status codes that typically indicate blocking
        blocking_status_codes = {403, 503, 429, 406, 451}

        # Block page content patterns (these indicate actual blocking, not just CDN usage)
        block_content_patterns = {
            "cloudflare": [
                "attention required! | cloudflare",
                "checking your browser before accessing",
                "enable javascript and cookies to continue",
                "ray id:",  # Only in body, not headers
                "performance & security by cloudflare",
                "please turn javascript on and reload the page",
            ],
            "akamai": [
                "access denied</title>",
                "you don't have permission to access",
                "reference #",  # Akamai error reference
                "your request has been blocked",
                "akamai ghost",
            ],
            "sucuri": [
                "sucuri website firewall",
                "access denied - sucuri",
                "blocked by sucuri",
            ],
            "imperva": [
                "incapsula incident",
                "request blocked",
                "incident id:",
                "powered by incapsula",
            ],
            "aws_waf": [
                "request blocked by aws waf",
                "this request was blocked by the security rules",
            ],
            "datadome": [
                "blocked by datadome",
                "datadome captcha",
            ],
            "perimeterx": [
                "human challenge",
                "press & hold",
                "perimeterx",
            ],
        }

        # Generic block indicators (content that suggests blocking regardless of provider)
        generic_block_indicators = [
            "access denied</title>",
            "403 forbidden</title>",
            "blocked</title>",
            "robot or bot",
            "automated access",
            "please verify you are human",
            "suspicious activity detected",
            "rate limit exceeded",
            "too many requests",
            "you have been blocked",
            "your ip has been blocked",
            "security challenge",
            "complete the captcha",
            "prove you are not a robot",
        ]

        # For blocking status codes, check body content
        if status_code in blocking_status_codes:
            # Check for specific WAF block pages
            for waf_name, patterns in block_content_patterns.items():
                for pattern in patterns:
                    if pattern in html_lower:
                        return waf_name

            # Check generic block indicators
            for indicator in generic_block_indicators:
                if indicator in html_lower:
                    return "waf_block"

            # If we got a blocking status code but page has real content, might not be blocked
            # Check if page has meaningful content (e.g., a real 403 page vs WAF block)
            if len(html_lower) < 5000 and ("denied" in html_lower or "blocked" in html_lower or "forbidden" in html_lower):
                return "waf_block"

        # For 200 status, only flag if we see a challenge/interstitial page
        # These are pages that load but require human interaction
        challenge_page_indicators = [
            "please wait while we verify your browser",
            "checking if the site connection is secure",
            "please enable javascript and cookies",
            "just a moment...</title>",
            "ddos protection by",
            "please complete the security check to access",
            "one more step</title>",
            "browser verification</title>",
        ]

        if status_code == 200:
            for indicator in challenge_page_indicators:
                if indicator in html_lower:
                    # Identify the WAF if possible
                    for waf_name, patterns in block_content_patterns.items():
                        for pattern in patterns:
                            if pattern in html_lower:
                                return waf_name
                    return "challenge_page"

        return None

    def get_crawl_summary(self) -> dict:
        """Get a summary of the crawl results.

        Returns:
            Dictionary with crawl statistics
        """
        if not self.site_data:
            return {
                'total_pages': 0,
                'failed_pages': len(self.failed_urls),
                'failed_urls': list(self.failed_urls.keys()),
            }

        total_words = sum(page.word_count for page in self.site_data.values())
        total_images = sum(page.total_images for page in self.site_data.values())
        pages_with_issues = sum(
            1 for page in self.site_data.values()
            if not page.title or not page.description or not page.h1_tags
        )

        # Group failed URLs by error type
        failed_by_type: Dict[str, int] = {}
        for info in self.failed_urls.values():
            error_type = info.get("error_type", "Unknown")
            failed_by_type[error_type] = failed_by_type.get(error_type, 0) + 1

        return {
            'total_pages': len(self.site_data),
            'total_words': total_words,
            'avg_words_per_page': total_words // len(self.site_data) if self.site_data else 0,
            'total_images': total_images,
            'pages_with_issues': pages_with_issues,
            'urls_crawled': list(self.site_data.keys()),
            'failed_pages': len(self.failed_urls),
            'failed_urls': list(self.failed_urls.keys()),
            'failed_by_error_type': failed_by_type,
            'retry_stats': {
                'total_retries': sum(self.retry_counts.values()),
                'urls_retried': len(self.retry_counts),
            },
        }
