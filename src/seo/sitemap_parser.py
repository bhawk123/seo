"""Sitemap parser with browser support for bypassing bot protection."""

import asyncio
import logging
import re
from typing import List, Optional, Set
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree as ET

logger = logging.getLogger(__name__)


class SitemapParser:
    """
    Parse XML sitemaps to extract URLs for crawling.

    Supports:
    - Standard sitemap.xml files
    - Sitemap index files (multiple sitemaps)
    - Browser-based fetching to bypass bot protection
    """

    # XML namespaces used in sitemaps
    NAMESPACES = {
        'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9',
        'image': 'http://www.google.com/schemas/sitemap-image/1.1',
        'video': 'http://www.google.com/schemas/sitemap-video/1.1',
        'news': 'http://www.google.com/schemas/sitemap-news/0.9',
    }

    def __init__(self, use_browser: bool = False, browser_type: str = "chromium"):
        """
        Initialize the sitemap parser.

        Args:
            use_browser: Use browser-based fetching (for bot-protected sites)
            browser_type: Browser engine to use (chromium, firefox, webkit)
        """
        self.use_browser = use_browser
        self.browser_type = browser_type
        self._urls: Set[str] = set()

    def parse(self, sitemap_url: str, max_urls: Optional[int] = None) -> List[str]:
        """
        Parse a sitemap and return all URLs.

        Args:
            sitemap_url: URL to the sitemap.xml or sitemap index
            max_urls: Maximum number of URLs to return (None for all)

        Returns:
            List of URLs found in the sitemap
        """
        if self.use_browser:
            return asyncio.run(self._parse_with_browser(sitemap_url, max_urls))
        else:
            return self._parse_with_requests(sitemap_url, max_urls)

    def _parse_with_requests(self, sitemap_url: str, max_urls: Optional[int] = None) -> List[str]:
        """Parse sitemap using requests library."""
        import requests

        self._urls = set()

        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
                'Accept': 'application/xml, text/xml, */*',
            }
            response = requests.get(sitemap_url, headers=headers, timeout=30)
            response.raise_for_status()

            self._parse_sitemap_content(response.text, sitemap_url, max_urls)

        except Exception as e:
            logger.error(f"Failed to fetch sitemap {sitemap_url}: {e}")

        urls = list(self._urls)
        if max_urls:
            urls = urls[:max_urls]
        return urls

    async def _parse_with_browser(self, sitemap_url: str, max_urls: Optional[int] = None) -> List[str]:
        """Parse sitemap using browser-based fetching."""
        from .browser_config import BrowserConfig
        from .browser_crawler import BrowserCrawler

        self._urls = set()

        config = BrowserConfig(
            browser_type=self.browser_type,
            stealth_mode=True,
            headless=True,
            wait_until="networkidle",
            timeout=30000,
        )

        try:
            async with BrowserCrawler(config) as crawler:
                await self._fetch_and_parse_sitemap(crawler, sitemap_url, max_urls)
        except Exception as e:
            logger.error(f"Browser-based sitemap fetch failed: {e}")

        urls = list(self._urls)
        if max_urls:
            urls = urls[:max_urls]
        return urls

    async def _fetch_and_parse_sitemap(
        self,
        crawler,
        sitemap_url: str,
        max_urls: Optional[int],
        depth: int = 0
    ) -> None:
        """Recursively fetch and parse sitemaps."""
        if depth > 3:  # Prevent infinite recursion
            return

        if max_urls and len(self._urls) >= max_urls:
            return

        logger.info(f"Fetching sitemap: {sitemap_url}")
        result = await crawler.crawl(sitemap_url)

        if result.error:
            logger.error(f"Failed to fetch {sitemap_url}: {result.error}")
            return

        if not result.html:
            logger.warning(f"Empty response from {sitemap_url}")
            return

        # Extract XML content from the HTML (browser wraps it)
        xml_content = self._extract_xml_from_html(result.html)
        if xml_content:
            self._parse_sitemap_content(xml_content, sitemap_url, max_urls)

    def _extract_xml_from_html(self, html: str) -> Optional[str]:
        """Extract XML content that may be wrapped in HTML by the browser."""
        # Try to find XML declaration or root element
        xml_patterns = [
            r'<\?xml[^>]*\?>.*?<(urlset|sitemapindex)',
            r'<(urlset|sitemapindex)',
        ]

        for pattern in xml_patterns:
            match = re.search(pattern, html, re.DOTALL | re.IGNORECASE)
            if match:
                # Find the start of the XML
                start = html.find('<?xml')
                if start == -1:
                    start = html.find('<urlset')
                if start == -1:
                    start = html.find('<sitemapindex')

                if start != -1:
                    # Find the end tag
                    end_urlset = html.rfind('</urlset>')
                    end_sitemapindex = html.rfind('</sitemapindex>')
                    end = max(end_urlset, end_sitemapindex)

                    if end != -1:
                        end_tag = '</urlset>' if end_urlset > end_sitemapindex else '</sitemapindex>'
                        return html[start:end + len(end_tag)]

        # Return original if it looks like raw XML
        if '<urlset' in html or '<sitemapindex' in html:
            return html

        return None

    def _parse_sitemap_content(
        self,
        content: str,
        base_url: str,
        max_urls: Optional[int]
    ) -> None:
        """Parse sitemap XML content and extract URLs."""
        try:
            # Clean up any HTML wrapper
            content = self._clean_xml_content(content)
            root = ET.fromstring(content)
        except ET.ParseError as e:
            logger.error(f"Failed to parse sitemap XML: {e}")
            return

        # Get the root tag without namespace
        root_tag = root.tag.split('}')[-1] if '}' in root.tag else root.tag

        if root_tag == 'sitemapindex':
            # This is a sitemap index - parse each referenced sitemap
            self._parse_sitemap_index(root, base_url, max_urls)
        elif root_tag == 'urlset':
            # This is a regular sitemap - extract URLs
            self._parse_urlset(root, max_urls)
        else:
            logger.warning(f"Unknown sitemap root element: {root_tag}")

    def _clean_xml_content(self, content: str) -> str:
        """Clean XML content by removing any HTML wrapper."""
        # Remove DOCTYPE if present
        content = re.sub(r'<!DOCTYPE[^>]*>', '', content)

        # Remove HTML tags if the XML is wrapped
        if '<html' in content.lower():
            # Try to extract just the XML portion
            match = re.search(r'(<\?xml.*?</(?:urlset|sitemapindex)>)', content, re.DOTALL)
            if match:
                return match.group(1)

            # Try without XML declaration
            match = re.search(r'(<(?:urlset|sitemapindex).*?</(?:urlset|sitemapindex)>)', content, re.DOTALL)
            if match:
                return match.group(1)

        return content

    def _parse_sitemap_index(self, root: ET.Element, base_url: str, max_urls: Optional[int]) -> None:
        """Parse a sitemap index and recursively fetch child sitemaps."""
        # Find all sitemap entries
        for sitemap in root.iter():
            if sitemap.tag.endswith('sitemap'):
                loc = sitemap.find('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')
                if loc is None:
                    loc = sitemap.find('loc')

                if loc is not None and loc.text:
                    child_url = loc.text.strip()
                    logger.info(f"Found child sitemap: {child_url}")

                    # For now, just log the child sitemaps
                    # In async mode, we would recursively fetch them
                    if not self.use_browser:
                        self._parse_with_requests(child_url, max_urls)

    def _parse_urlset(self, root: ET.Element, max_urls: Optional[int]) -> None:
        """Parse a urlset element and extract URLs."""
        count = 0

        for url_elem in root.iter():
            if url_elem.tag.endswith('url'):
                loc = url_elem.find('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')
                if loc is None:
                    loc = url_elem.find('loc')

                if loc is not None and loc.text:
                    url = loc.text.strip()
                    self._urls.add(url)
                    count += 1

                    if max_urls and len(self._urls) >= max_urls:
                        logger.info(f"Reached max URLs limit ({max_urls})")
                        return

        logger.info(f"Extracted {count} URLs from sitemap")


def parse_sitemap(
    sitemap_url: str,
    max_urls: Optional[int] = None,
    use_browser: bool = False,
    browser_type: str = "chromium"
) -> List[str]:
    """
    Convenience function to parse a sitemap.

    Args:
        sitemap_url: URL to the sitemap
        max_urls: Maximum URLs to return
        use_browser: Use browser-based fetching
        browser_type: Browser engine to use

    Returns:
        List of URLs from the sitemap
    """
    parser = SitemapParser(use_browser=use_browser, browser_type=browser_type)
    return parser.parse(sitemap_url, max_urls)
