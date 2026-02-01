"""Web crawler for extracting page content and metadata."""

import time
import json
import random
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from typing import Optional

from seo.models import PageMetadata, CrawlResult


class WebCrawler:
    """Crawls websites and extracts metadata for SEO analysis."""

    # Realistic browser user agents (rotate to avoid detection)
    BROWSER_USER_AGENTS = [
        # Chrome on Windows
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        # Chrome on macOS
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        # Firefox on Windows
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
        # Safari on macOS
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
        # Edge on Windows
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0",
    ]

    def __init__(self, user_agent: Optional[str] = None, respect_robots: bool = True):
        """Initialize the web crawler.

        Args:
            user_agent: Custom user agent string for requests (uses realistic browser UA if None)
            respect_robots: Whether to identify as a bot (False uses browser UAs)
        """
        # Use realistic browser user agent by default, or custom one
        if user_agent:
            self.user_agent = user_agent
        else:
            # Use SEO-Analyzer-Bot if respect_robots=True, otherwise random browser UA
            if respect_robots:
                self.user_agent = "Mozilla/5.0 (compatible; SEO-Analyzer/1.0; +https://github.com/yourusername/seo-analyzer)"
            else:
                self.user_agent = random.choice(self.BROWSER_USER_AGENTS)

        self.session = requests.Session()

        # Set comprehensive browser-like headers
        self.session.headers.update({
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",  # Do Not Track
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
        })

    def crawl(self, url: str, timeout: int = 30, max_retries: int = 3) -> CrawlResult:
        """Crawl a single URL and extract metadata with retry logic.

        Args:
            url: The URL to crawl
            timeout: Request timeout in seconds
            max_retries: Maximum number of retry attempts for failed requests

        Returns:
            CrawlResult containing metadata and HTML content
        """
        last_error = None

        for attempt in range(max_retries):
            try:
                # Add small random delay between retries to avoid rate limiting
                if attempt > 0:
                    delay = (2 ** attempt) + random.uniform(0, 1)  # Exponential backoff
                    time.sleep(delay)

                start_time = time.time()
                response = self.session.get(
                    url,
                    timeout=timeout,
                    allow_redirects=True,
                    verify=True  # Verify SSL certificates
                )
                load_time = time.time() - start_time

                # Check for success
                response.raise_for_status()

                html = response.text
                headers = dict(response.headers)  # Convert to dict
                metadata = self._extract_metadata(
                    url, html, response.status_code, load_time, headers
                )

                return CrawlResult(
                    url=url, metadata=metadata, html=html, success=True
                )

            except requests.exceptions.HTTPError as e:
                # For 403/401 errors, try rotating user agent on retry
                if e.response.status_code in [403, 401] and attempt < max_retries - 1:
                    # Rotate to a different browser user agent
                    new_ua = random.choice(self.BROWSER_USER_AGENTS)
                    self.session.headers.update({"User-Agent": new_ua})
                    last_error = str(e)
                    continue
                else:
                    last_error = str(e)

            except requests.exceptions.Timeout:
                last_error = f"Request timeout after {timeout}s"

            except requests.exceptions.ConnectionError as e:
                last_error = f"Connection error: {str(e)}"

            except Exception as e:
                last_error = str(e)

        # All retries failed
        return CrawlResult(
            url=url,
            metadata=PageMetadata(url=url),
            html="",
            success=False,
            error=f"Failed after {max_retries} attempts: {last_error}",
        )

    def _extract_metadata(
        self, url: str, html: str, status_code: int, load_time: float, headers: dict
    ) -> PageMetadata:
        """Extract metadata from HTML content.

        Args:
            url: The page URL
            html: HTML content
            status_code: HTTP status code
            load_time: Page load time in seconds
            headers: HTTP response headers

        Returns:
            PageMetadata object with extracted information
        """
        soup = BeautifulSoup(html, "html.parser")
        base_domain = urlparse(url).netloc

        # Title
        title = soup.find("title")
        title_text = title.get_text(strip=True) if title else None

        # Meta description
        description_tag = soup.find("meta", attrs={"name": "description"})
        description = (
            description_tag.get("content") if description_tag else None
        )

        # Meta keywords
        keywords = []
        for meta in soup.find_all("meta", attrs={"name": "keywords"}):
            if meta.get("content"):
                keywords.extend(
                    [k.strip() for k in meta.get("content").split(",")]
                )

        # Headers
        h1_tags = [h1.get_text(strip=True) for h1 in soup.find_all("h1")]
        h2_tags = [h2.get_text(strip=True) for h2 in soup.find_all("h2")]

        # Images
        all_images = soup.find_all("img")
        images = [
            {
                "src": img.get("src", ""),
                "alt": img.get("alt", ""),
            }
            for img in all_images
        ]
        images_without_alt = sum(1 for img in all_images if not img.get("alt"))
        total_images = len(all_images)

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
            # Check http-equiv content-type
            content_type_tag = soup.find("meta", attrs={"http-equiv": "Content-Type"})
            if content_type_tag:
                content = content_type_tag.get("content", "")
                if "charset=" in content:
                    charset = content.split("charset=")[-1].strip()

        # Twitter Card
        twitter_card = {}
        for meta in soup.find_all("meta", attrs={"name": lambda x: x and x.startswith("twitter:")}):
            twitter_card[meta["name"]] = meta.get("content", "")

        # Content text (for readability analysis)
        content_text = text

        # Check if HTTPS
        has_https = url.startswith("https://")

        # Extract security headers
        security_headers = {
            k.lower(): v for k, v in headers.items()
            if k.lower() in [
                'strict-transport-security',
                'x-content-type-options',
                'x-frame-options',
                'x-xss-protection',
                'content-security-policy',
                'referrer-policy',
            ]
        }

        # Detect technologies
        from seo.technology_detector import detect_technologies
        tech_results = detect_technologies(url, html, headers)

        tech_summary = {}
        if tech_results:
            from seo.technology_detector import TechnologyDetector
            detector = TechnologyDetector()
            tech_summary = detector.get_summary_stats(tech_results)

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
            content_text=content_text,
            has_https=has_https,
            twitter_card=twitter_card,
            security_headers=security_headers,
            # Technology detection
            technologies=tech_results.get('all_technologies', []),
            tech_by_category=tech_results.get('by_category', {}),
            tech_details=tech_results.get('details', {}),
            tech_ecommerce=tech_summary.get('primary_ecommerce'),
            tech_cms=tech_summary.get('primary_cms'),
            tech_web_server=tech_summary.get('web_server'),
            tech_has_cdn=tech_summary.get('has_cdn', False),
            tech_has_analytics=tech_summary.get('has_analytics', False),
        )
