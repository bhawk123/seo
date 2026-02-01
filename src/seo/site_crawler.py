"""Site crawler with breadth-first search for multi-page analysis."""

import asyncio
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Set

from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
import logging

from seo.crawler import WebCrawler
from seo.models import PageMetadata
from seo.lighthouse_runner import LighthouseRunner

logger = logging.getLogger(__name__)


class SiteCrawler:
    """Crawls entire sites using breadth-first search (BFS).

    Processes pages level by level:
    - L1: Starting page
    - L2: All pages linked from L1
    - L3: All pages linked from L2
    - etc.

    This ensures the most significant pages (closest to the root) are crawled first.

    Supports sitemap-based URL seeding for sites with bot protection.
    """

    def __init__(
        self,
        max_pages: int = 50,
        rate_limit: float = 0.5,
        user_agent: Optional[str] = None,
        enable_lighthouse: bool = True,
        lighthouse_sample_rate: float = 0.1,
        stealth_mode: bool = False,
        render_js: bool = False,
        browser_type: str = "chromium",
        on_progress: Optional[Callable[[int, int, str], None]] = None,
        seed_urls: Optional[list[str]] = None,
        resume_state: Optional[dict] = None,
        output_manager: Optional["OutputManager"] = None,
        crawl_dir: Optional[Path] = None,
    ):
        """Initialize the site crawler.

        Args:
            max_pages: Maximum number of pages to crawl
            rate_limit: Seconds to wait between requests
            user_agent: Custom user agent string
            enable_lighthouse: Whether to run Lighthouse audits on pages
            lighthouse_sample_rate: Fraction of pages to audit (0.0-1.0).
                                    Default 0.1 = 10% sample, 0.5 = half, 1.0 = all pages
            stealth_mode: Use browser-like headers to avoid bot detection (default: False)
            render_js: Use browser-based crawling with JavaScript rendering (default: False)
            browser_type: Browser engine to use when render_js=True (chromium, firefox, webkit)
            on_progress: Optional callback for progress updates (pages_crawled, max_pages, url)
            seed_urls: Optional list of URLs to seed the crawl queue (from sitemap, etc.)
            resume_state: Optional state dict to resume from a previous crawl
            output_manager: OutputManager instance for saving checkpoints
            crawl_dir: Directory to save checkpoints to
        """
        self.max_pages = max_pages
        self.rate_limit = rate_limit
        self.enable_lighthouse = enable_lighthouse
        self.lighthouse_sample_rate = max(0.0, min(1.0, lighthouse_sample_rate))
        self.render_js = render_js
        self.browser_type = browser_type
        self.stealth_mode = stealth_mode
        self.on_progress = on_progress
        self.seed_urls = seed_urls or []

        # Resume state support
        self._output_manager = output_manager
        self._crawl_dir = crawl_dir
        self._start_url: Optional[str] = None
        self._started_at: Optional[str] = None
        self._checkpoint_callback: Optional[Callable[[dict], None]] = None

        # Initialize the appropriate crawler based on render_js flag
        if render_js:
            # Browser crawler will be initialized when crawl_site is called
            self.crawler = None
            logger.info(f"SiteCrawler initialized with browser-based crawling (engine: {browser_type})")
        else:
            self.crawler = WebCrawler(user_agent=user_agent, respect_robots=not stealth_mode)
            logger.info("SiteCrawler initialized with requests-based crawling")

        # Initialize Lighthouse runner if enabled
        self.lighthouse_runner = LighthouseRunner() if enable_lighthouse else None
        self.lighthouse_count = 0

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

    def set_checkpoint_callback(self, callback: Callable[[dict], None]) -> None:
        """Set a callback function that will be called on each checkpoint.

        Args:
            callback: Function that receives the current state dict
        """
        self._checkpoint_callback = callback

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

    def crawl_site(self, start_url: str) -> Dict[str, PageMetadata]:
        """Crawl entire site starting from a URL using BFS.

        Args:
            start_url: The starting URL to crawl from

        Returns:
            Dictionary mapping URLs to PageMetadata for all crawled pages
        """
        if self.render_js:
            # Use browser-based crawling
            return asyncio.run(self._crawl_site_browser(start_url))
        else:
            # Use request-based crawling
            return self._crawl_site_requests(start_url)

    def _crawl_site_requests(self, start_url: str) -> Dict[str, PageMetadata]:
        """Crawl site using request-based crawler (original implementation).

        Args:
            start_url: The starting URL to crawl from

        Returns:
            Dictionary mapping URLs to PageMetadata for all crawled pages
        """
        # Normalize the start URL
        start_url = self._normalize_url(start_url)
        self._start_url = start_url
        base_domain = urlparse(start_url).netloc

        # Only add start URL to queue if not resuming (queue already populated)
        if not self.queue:
            self.queue.append((start_url, 1))

        print(f"Starting site crawl from: {start_url}")
        print(f"Max pages: {self.max_pages}")
        print(f"Rate limit: {self.rate_limit}s between requests\n")

        current_level = 1

        while self.queue and len(self.visited_urls) < self.max_pages:
            url, level = self.queue.popleft()

            # Skip if already visited
            if url in self.visited_urls:
                continue

            # Print level changes
            if level > current_level:
                print(f"\n--- Moving to Level {level} ---\n")
                current_level = level

            # Mark as visited
            self.visited_urls.add(url)

            # Crawl the page
            print(f"[L{level}] Crawling ({len(self.visited_urls)}/{self.max_pages}): {url}")
            crawl_result = self.crawler.crawl(url)

            if not crawl_result.success:
                print(f"  ⚠️  Failed: {crawl_result.error}")
                continue

            # Store the page data
            self.site_data[url] = crawl_result.metadata
            print(f"  ✓ Success - {crawl_result.metadata.word_count} words, {crawl_result.metadata.internal_links} internal links")

            # Run Lighthouse if enabled and within sample rate
            if self.enable_lighthouse and self._should_run_lighthouse():
                print(f"  🔍 Running Lighthouse audit...")
                self._run_lighthouse_for_page(url, crawl_result.metadata)

            # Extract and queue internal links (only if we haven't hit max_pages)
            if len(self.visited_urls) < self.max_pages:
                new_links = self._extract_internal_links(
                    url, crawl_result.metadata.links, base_domain
                )

                # Add new links to queue at next level
                for link in new_links:
                    if link not in self.visited_urls:
                        self.queue.append((link, level + 1))

                if new_links:
                    print(f"  → Queued {len(new_links)} new links for L{level + 1}")

            # Save checkpoint every 10 pages
            if len(self.visited_urls) % 10 == 0:
                self._save_checkpoint("running")

            # Rate limiting
            if len(self.visited_urls) < self.max_pages and self.queue:
                time.sleep(self.rate_limit)

        # Save final checkpoint with completed status
        self._save_checkpoint("completed")

        print(f"\n{'=' * 60}")
        print(f"Crawl complete! Processed {len(self.site_data)} pages")
        print(f"{'=' * 60}\n")

        return self.site_data

    def _normalize_url(self, url: str) -> str:
        """Normalize URL by removing fragments and trailing slashes.

        Args:
            url: URL to normalize

        Returns:
            Normalized URL
        """
        parsed = urlparse(url)
        # Remove fragment
        normalized = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        if parsed.query:
            normalized += f"?{parsed.query}"
        # Remove trailing slash (except for root)
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
            Set of internal links (same domain) that haven't been visited
        """
        internal_links = set()

        for link in links:
            try:
                # Resolve relative URLs
                absolute_url = urljoin(current_url, link)
                normalized_url = self._normalize_url(absolute_url)

                # Parse the URL
                parsed = urlparse(normalized_url)

                # Check if it's internal (same domain)
                if parsed.netloc == base_domain:
                    # Skip certain file types
                    if self._should_skip_url(parsed.path):
                        continue

                    # Only add if not already visited
                    if normalized_url not in self.visited_urls:
                        internal_links.add(normalized_url)

            except Exception:
                # Skip malformed URLs
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

        path_lower = path.lower()
        return any(path_lower.endswith(ext) for ext in skip_extensions)

    def _should_run_lighthouse(self) -> bool:
        """Determine if Lighthouse should run for this page based on sample rate.

        Returns:
            True if Lighthouse should run
        """
        if not self.lighthouse_runner:
            return False

        # Always run on first page
        if len(self.site_data) == 1:
            return True

        # Use sample rate for subsequent pages
        import random
        return random.random() < self.lighthouse_sample_rate

    def _run_lighthouse_for_page(self, url: str, metadata: PageMetadata) -> None:
        """Run Lighthouse audit and merge results into page metadata.

        Args:
            url: URL to audit
            metadata: PageMetadata object to update with Lighthouse results
        """
        try:
            results = self.lighthouse_runner.run_lighthouse(url)

            if not results:
                print(f"  ⚠️  Lighthouse audit failed")
                return

            # Extract scores
            scores = results.get('scores', {})
            metadata.lighthouse_performance_score = scores.get('performance')
            metadata.lighthouse_accessibility_score = scores.get('accessibility')
            metadata.lighthouse_best_practices_score = scores.get('best_practices')
            metadata.lighthouse_seo_score = scores.get('seo')
            metadata.lighthouse_pwa_score = scores.get('pwa')

            # Extract metrics
            metrics = results.get('metrics', {})
            metadata.lighthouse_fcp = metrics.get('fcp')
            metadata.lighthouse_lcp = metrics.get('lcp')
            metadata.lighthouse_si = metrics.get('si')
            metadata.lighthouse_tti = metrics.get('tti')
            metadata.lighthouse_tbt = metrics.get('tbt')
            metadata.lighthouse_cls = metrics.get('cls')
            metadata.lighthouse_first_meaningful_paint = metrics.get('fmp')
            metadata.lighthouse_max_potential_fid = metrics.get('max_potential_fid')

            # Extract opportunities and diagnostics
            metadata.lighthouse_opportunities = results.get('opportunities', [])
            metadata.lighthouse_diagnostics = results.get('diagnostics', {})
            metadata.lighthouse_screenshot_thumbnails = results.get('screenshots', [])
            metadata.lighthouse_fetch_time = results.get('fetch_time')

            # Update CWV status with real data
            if metadata.lighthouse_lcp:
                lcp_seconds = metadata.lighthouse_lcp / 1000
                metadata.cwv_lcp_estimate = lcp_seconds
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

            # Calculate overall CWV status
            statuses = [metadata.cwv_lcp_status, metadata.cwv_inp_status, metadata.cwv_cls_status]
            if 'poor' in statuses:
                metadata.cwv_overall_status = 'poor'
            elif 'needs-improvement' in statuses:
                metadata.cwv_overall_status = 'needs-improvement'
            elif all(s == 'good' for s in statuses):
                metadata.cwv_overall_status = 'good'

            self.lighthouse_count += 1

            # Print summary
            perf_score = scores.get('performance', 0)
            lcp_ms = metrics.get('lcp', 0)
            print(f"  ✓ Lighthouse: Performance {perf_score:.0f}/100, LCP {lcp_ms:.0f}ms")

        except Exception as e:
            logger.error(f"Error running Lighthouse for {url}: {e}")
            print(f"  ⚠️  Lighthouse error: {e}")

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

        summary = {
            'total_pages': len(self.site_data),
            'total_words': total_words,
            'avg_words_per_page': total_words // len(self.site_data) if self.site_data else 0,
            'total_images': total_images,
            'pages_with_issues': pages_with_issues,
            'urls_crawled': list(self.site_data.keys()),
        }

        # Add Lighthouse summary if enabled
        if self.enable_lighthouse:
            summary['lighthouse_enabled'] = True
            summary['lighthouse_audits_run'] = self.lighthouse_count

            # Calculate average Lighthouse scores
            pages_with_lighthouse = [
                p for p in self.site_data.values()
                if p.lighthouse_performance_score is not None
            ]

            if pages_with_lighthouse:
                summary['avg_performance_score'] = sum(
                    p.lighthouse_performance_score for p in pages_with_lighthouse
                ) / len(pages_with_lighthouse)
                summary['avg_seo_score'] = sum(
                    p.lighthouse_seo_score or 0 for p in pages_with_lighthouse
                ) / len(pages_with_lighthouse)

        return summary

    async def _crawl_site_browser(self, start_url: str) -> Dict[str, PageMetadata]:
        """Crawl site using browser-based crawler with JavaScript rendering.

        Args:
            start_url: The starting URL to crawl from

        Returns:
            Dictionary mapping URLs to PageMetadata for all crawled pages
        """
        from .browser_config import BrowserConfig
        from .browser_crawler import BrowserCrawler

        # Configure browser crawler
        launch_args = []
        if self.stealth_mode:
            launch_args = [
                "--disable-http2",  # Bypass HTTP/2 fingerprinting
                "--disable-blink-features=AutomationControlled",
                "--disable-features=IsolateOrigins,site-per-process",
                "--no-first-run",
                "--no-default-browser-check",
            ]

        config = BrowserConfig(
            browser_type=self.browser_type,
            stealth_mode=self.stealth_mode,
            headless=True,
            wait_until="networkidle",
            timeout=30000,
            launch_args=launch_args,
        )

        # Normalize start URL
        start_url = self._normalize_url(start_url)
        self._start_url = start_url
        base_domain = urlparse(start_url).netloc

        # Only reset state if not resuming (visited_urls would be populated)
        if not self.visited_urls:
            self.visited_urls = set()
            self.site_data = {}

        queue: asyncio.Queue = asyncio.Queue()

        # If resuming, populate async queue from deque
        if self.queue:
            for url, depth in self.queue:
                await queue.put((url, depth))
            self.queue.clear()  # Clear deque since we've moved to async queue
        else:
            # Add start URL to queue only if not resuming
            await queue.put((start_url, 1))
            self.visited_urls.add(start_url)

        # Add seed URLs to queue (from sitemap, etc.)
        if self.seed_urls:
            seed_count = 0
            for seed_url in self.seed_urls:
                # Normalize and filter to same domain
                normalized = self._normalize_url(seed_url)
                parsed = urlparse(normalized)
                if parsed.netloc == base_domain and normalized not in self.visited_urls:
                    await queue.put((normalized, 1))
                    self.visited_urls.add(normalized)
                    seed_count += 1
            if seed_count > 0:
                print(f"Seeded queue with {seed_count} URLs from sitemap")

        print(f"Starting browser-based site crawl from: {start_url}")
        print(f"Max pages: {self.max_pages}")
        print(f"Rate limit: {self.rate_limit}s between requests")
        print(f"Browser: {self.browser_type}\n")

        current_level = 1

        async with BrowserCrawler(config) as crawler:
            while not queue.empty() and len(self.site_data) < self.max_pages:
                url, level = await queue.get()

                # Print level changes
                if level > current_level:
                    print(f"\n--- Moving to Level {level} ---\n")
                    current_level = level

                # Crawl the page
                print(f"[L{level}] Crawling ({len(self.site_data) + 1}/{self.max_pages}): {url}")

                result = await crawler.crawl(url)

                if result.error:
                    print(f"  ⚠️  Failed: {result.error}")
                    continue

                # Parse the HTML and create PageMetadata
                metadata = self._parse_browser_result(result, url)
                self.site_data[url] = metadata

                print(f"  ✓ Success - {metadata.word_count} words, {metadata.internal_links} internal links")

                # Call progress callback if provided
                if self.on_progress:
                    self.on_progress(len(self.site_data), self.max_pages, url)

                # Run Lighthouse if enabled and within sample rate
                if self.enable_lighthouse and self._should_run_lighthouse():
                    print(f"  🔍 Running Lighthouse audit...")
                    self._run_lighthouse_for_page(url, metadata)

                # Extract and queue internal links
                if len(self.site_data) < self.max_pages and result.html:
                    new_links = self._find_internal_links_bs(result.html, url, base_domain)

                    for link in new_links:
                        if link not in self.visited_urls:
                            self.visited_urls.add(link)
                            await queue.put((link, level + 1))

                    if new_links:
                        print(f"  → Queued {len(new_links)} new links for L{level + 1}")

                # Save checkpoint every 10 pages
                if len(self.site_data) % 10 == 0:
                    # Sync queue back to deque for state saving
                    temp_queue = []
                    while not queue.empty():
                        try:
                            item = queue.get_nowait()
                            temp_queue.append(item)
                        except asyncio.QueueEmpty:
                            break
                    self.queue = deque(temp_queue)
                    for item in temp_queue:
                        await queue.put(item)
                    self._save_checkpoint("running")

                # Rate limiting
                if len(self.site_data) < self.max_pages and not queue.empty():
                    await asyncio.sleep(self.rate_limit)

        # Save final checkpoint with completed status
        self._save_checkpoint("completed")

        print(f"\n{'=' * 60}")
        print(f"Crawl complete! Processed {len(self.site_data)} pages")
        print(f"{'=' * 60}\n")

        return self.site_data

    def _parse_browser_result(self, result, url: str) -> PageMetadata:
        """Parse browser crawl result into PageMetadata.

        Args:
            result: BrowserCrawlResult from the crawler
            url: The crawled URL

        Returns:
            PageMetadata object populated from the HTML
        """
        from .crawler import WebCrawler

        # Use the existing WebCrawler's _extract_metadata method to parse HTML
        temp_crawler = WebCrawler()
        metadata = temp_crawler._extract_metadata(
            url=url,
            html=result.html or "",
            status_code=result.status_code,
            load_time=result.load_time,
            headers=result.headers,
        )

        return metadata

    def _find_internal_links_bs(self, html: str, base_url: str, base_domain: str) -> Set[str]:
        """Find internal links using BeautifulSoup.

        This method is used by the browser crawler to extract links from
        JavaScript-rendered HTML content.

        Args:
            html: The HTML content to parse
            base_url: The base URL for resolving relative links
            base_domain: The domain to filter internal links

        Returns:
            Set of internal link URLs
        """
        soup = BeautifulSoup(html, 'html.parser')
        links = set()

        for a in soup.find_all('a', href=True):
            href = a['href']

            # Skip non-crawlable links
            if href.startswith(('mailto:', 'tel:', 'javascript:', '#')):
                continue

            try:
                # Resolve relative URLs
                absolute_url = urljoin(base_url, href)
                normalized_url = self._normalize_url(absolute_url)

                # Parse and validate
                parsed = urlparse(normalized_url)

                # Check if internal (same domain)
                if parsed.netloc == base_domain:
                    # Skip certain file types
                    if self._should_skip_url(parsed.path):
                        continue

                    # Only add if not already visited
                    if normalized_url not in self.visited_urls:
                        links.add(normalized_url)

            except Exception:
                continue

        return links
