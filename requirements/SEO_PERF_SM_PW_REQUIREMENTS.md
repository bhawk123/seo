# SEO Performance & Advanced Crawling Enhancement Requirements

**Document Version:** 1.0
**Date:** November 23, 2025
**Author:** SEO Analyzer Enhancement Team
**Status:** DRAFT - Pending Review & Implementation

---

## Executive Summary

This document outlines requirements for three high-impact enhancements to the SEO Analyzer:

1. **Google PageSpeed Insights API Integration** - Real-world Core Web Vitals data from actual Chrome users
2. **advertools Library Integration** - Comprehensive SEO utilities for sitemaps, robots.txt, and analytics
3. **Playwright Integration** - JavaScript rendering for Single Page Applications (SPAs)

**Expected Impact:**
- **Performance Analysis**: Real user data vs. synthetic tests (30-50% more accurate)
- **Site Discovery**: Automated sitemap parsing and validation (saves 2-4 hours per audit)
- **SPA Support**: Crawl React/Vue/Angular sites that currently fail (expands addressable market by 40%)

**Estimated Implementation Time:** 3-4 weeks (60-80 hours)

**Cost:** $0-50/month (PageSpeed Insights API is free, Playwright is free, advertools is free)

---

## Table of Contents

1. [Motivation & Business Case](#1-motivation--business-case)
2. [Technical Requirements](#2-technical-requirements)
3. [Integration 1: Google PageSpeed Insights API](#3-integration-1-google-pagespeed-insights-api)
4. [Integration 2: advertools Library](#4-integration-2-advertools-library)
5. [Integration 3: Playwright for JavaScript Rendering](#5-integration-3-playwright-for-javascript-rendering)
6. [Architecture & Design](#6-architecture--design)
7. [Implementation Plan](#7-implementation-plan)
8. [Testing Strategy](#8-testing-strategy)
9. [Risks & Mitigation](#9-risks--mitigation)
10. [Success Metrics](#10-success-metrics)
11. [Future Enhancements](#11-future-enhancements)

---

## 1. Motivation & Business Case

### 1.1 Current Limitations

**Performance Analysis Gap:**
- Current Core Web Vitals analysis is **synthetic** (estimated from HTML analysis)
- Does NOT use real user data from Chrome User Experience Report
- Cannot measure actual JavaScript execution impact
- Missing Google's official performance scores

**Sitemap & Robots.txt Gap:**
- Manual robots.txt parsing (limited validation)
- No XML sitemap downloading or parsing
- Cannot validate sitemap coverage vs. crawled pages
- Missing sitemap index support

**JavaScript Rendering Gap:**
- Cannot crawl Single Page Applications (React, Vue, Angular, Next.js)
- Misses content loaded via JavaScript
- Reports incomplete data for modern web apps
- Loses ~40% of potential client base

### 1.2 Why These Three Integrations?

| Integration | Problem It Solves | Value Proposition |
|------------|------------------|-------------------|
| **PageSpeed Insights** | Synthetic vs. Real Data | Google's official scores, actual user metrics, actionable recommendations |
| **advertools** | Manual sitemap work | Automated parsing, validation, analytics integration, keyword research |
| **Playwright** | Can't crawl SPAs | Full JavaScript support, screenshots, console logs, modern web compatibility |

### 1.3 Competitive Advantage

**Current Competitors:**
- **Screaming Frog**: Handles JS but expensive ($259/year), no real user metrics
- **Sitebulb**: Great reports but Windows-only, expensive ($35/month)
- **Ahrefs/SEMrush**: Enterprise pricing ($99-500/month), overkill for many users

**Our Advantage with These Integrations:**
- ✅ Free/low-cost (open source + free APIs)
- ✅ Python-based (easy to extend)
- ✅ Real Google data (PageSpeed Insights)
- ✅ Modern web support (Playwright)
- ✅ Comprehensive reporting (advertools analytics)

---

## 2. Technical Requirements

### 2.1 Dependencies

```toml
# pyproject.toml additions

[tool.poetry.dependencies]
# Existing dependencies...

# New requirements
playwright = "^1.40.0"              # JavaScript rendering
advertools = "^0.14.0"              # SEO utilities
httpx = "^0.25.0"                   # Modern async HTTP (for PSI API)
pandas = "^2.0.0"                   # Data analysis (advertools dependency)
```

### 2.2 API Keys & Credentials

**Google PageSpeed Insights API:**
- **Required**: Google Cloud API Key
- **Setup**: https://developers.google.com/speed/docs/insights/v5/get-started
- **Cost**: FREE (25,000 requests/day, 240,000/day with billing enabled)
- **Rate Limit**: 400 requests/100 seconds/user (4 req/sec max)
- **Environment Variable**: `GOOGLE_PSI_API_KEY`

**Playwright:**
- **Required**: Browser binaries installation
- **Setup**: `playwright install chromium`
- **Cost**: FREE
- **Disk Space**: ~300MB for Chromium binary

**advertools:**
- **Required**: None (no API key needed for basic features)
- **Optional**: Google Analytics credentials for GA integration
- **Cost**: FREE

### 2.3 System Requirements

- **Python**: 3.10+ (already required)
- **RAM**: +500MB (for Playwright browser)
- **Disk**: +300MB (Chromium binary)
- **Network**: Outbound HTTPS access to:
  - `googleapis.com` (PageSpeed Insights)
  - `googlechrome.com` (Playwright browser downloads)

---

## 3. Integration 1: Google PageSpeed Insights API

### 3.1 Overview

**What it provides:**
- Real Core Web Vitals from Chrome User Experience Report (CrUX)
- Lab data (synthetic tests similar to Lighthouse)
- Mobile and desktop performance scores
- Screenshot of page
- Specific optimization opportunities with estimated savings
- Technology stack detection

**API Endpoint:**
```
GET https://www.googleapis.com/pagespeedonline/v5/runPagespeed
```

### 3.2 API Request Parameters

```python
params = {
    'url': 'https://example.com',           # Required
    'key': GOOGLE_PSI_API_KEY,              # Required
    'strategy': 'mobile',                   # 'mobile' or 'desktop'
    'category': [                           # Optional categories
        'performance',
        'accessibility',
        'best-practices',
        'seo',
        'pwa'
    ],
    'locale': 'en',                         # Optional
}
```

### 3.3 API Response Structure

**Key Data Points:**
```json
{
  "lighthouseResult": {
    "categories": {
      "performance": {"score": 0.92},
      "accessibility": {"score": 0.88},
      "best-practices": {"score": 0.93},
      "seo": {"score": 1.0},
      "pwa": {"score": 0.5}
    },
    "audits": {
      "first-contentful-paint": {
        "displayValue": "0.8 s",
        "score": 1.0
      },
      "largest-contentful-paint": {
        "displayValue": "1.2 s",
        "score": 1.0
      },
      "cumulative-layout-shift": {
        "displayValue": "0.01",
        "score": 1.0
      },
      "total-blocking-time": {
        "displayValue": "150 ms",
        "score": 0.9
      },
      "speed-index": {
        "displayValue": "1.4 s",
        "score": 1.0
      }
    }
  },
  "loadingExperience": {
    "metrics": {
      "LARGEST_CONTENTFUL_PAINT_MS": {
        "percentile": 1847,
        "category": "FAST"
      }
    }
  }
}
```

### 3.4 Rate Limiting Strategy

**Constraints:**
- 400 requests per 100 seconds
- 25,000 requests per day (free tier)

**Implementation:**
```python
import asyncio
from datetime import datetime, timedelta

class PageSpeedInsightsAPI:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.requests_per_100s = 0
        self.last_request_window = datetime.now()
        self.semaphore = asyncio.Semaphore(4)  # Max 4 concurrent

    async def rate_limit_check(self):
        """Enforce rate limits"""
        now = datetime.now()
        if (now - self.last_request_window) > timedelta(seconds=100):
            self.requests_per_100s = 0
            self.last_request_window = now

        if self.requests_per_100s >= 400:
            wait_time = 100 - (now - self.last_request_window).seconds
            await asyncio.sleep(wait_time)
            self.requests_per_100s = 0
            self.last_request_window = datetime.now()

        self.requests_per_100s += 1
```

### 3.5 Data Model Extensions

**Add to PageMetadata:**
```python
@dataclass
class PageMetadata:
    # ... existing fields ...

    # PageSpeed Insights - Lab Data
    lighthouse_performance_score: Optional[float] = None  # 0-100
    lighthouse_accessibility_score: Optional[float] = None
    lighthouse_best_practices_score: Optional[float] = None
    lighthouse_seo_score: Optional[float] = None
    lighthouse_pwa_score: Optional[float] = None

    # PageSpeed Insights - Metrics (milliseconds)
    lighthouse_fcp: Optional[int] = None  # First Contentful Paint
    lighthouse_lcp: Optional[int] = None  # Largest Contentful Paint
    lighthouse_si: Optional[int] = None   # Speed Index
    lighthouse_tti: Optional[int] = None  # Time to Interactive
    lighthouse_tbt: Optional[int] = None  # Total Blocking Time
    lighthouse_cls: Optional[float] = None  # Cumulative Layout Shift

    # PageSpeed Insights - Opportunities
    lighthouse_opportunities: List[Dict] = field(default_factory=list)

    # Field Data (Real Users from CrUX)
    crux_lcp_percentile: Optional[int] = None
    crux_lcp_category: Optional[str] = None  # FAST/AVERAGE/SLOW
    crux_fid_percentile: Optional[int] = None
    crux_fid_category: Optional[str] = None
    crux_cls_percentile: Optional[float] = None
    crux_cls_category: Optional[str] = None
```

### 3.6 Integration Points

**1. Crawler Integration:**
```python
# src/seo/async_site_crawler.py

from seo.pagespeed_insights import PageSpeedInsightsAPI

class AsyncSiteCrawler:
    def __init__(self, ..., psi_api_key: Optional[str] = None):
        self.psi_api = PageSpeedInsightsAPI(psi_api_key) if psi_api_key else None

    async def _crawl_page_with_psi(self, url: str):
        # 1. Normal crawl
        page_metadata = await self._crawl_page(url)

        # 2. Optional: Get PageSpeed Insights data
        if self.psi_api:
            psi_data = await self.psi_api.analyze(url, strategy='mobile')
            page_metadata = self._merge_psi_data(page_metadata, psi_data)

        return page_metadata
```

**2. Report Integration:**
```python
# src/seo/report_generator.py

def _process_lighthouse_analysis(self, metadata_list: List[dict]) -> dict:
    """Process Lighthouse/PSI data for reporting"""
    # Calculate averages
    # Identify poor performers
    # Aggregate opportunities
    # Return formatted data for template
```

**3. CLI Flag:**
```python
# crawl.py

parser.add_argument(
    '--enable-lighthouse',
    action='store_true',
    help='Enable Google PageSpeed Insights analysis (requires API key)'
)
```

### 3.7 Report Additions

**New Report Section (Tab 5):**
- Lighthouse score gauges (5 circular charts)
- Performance metrics bar chart
- Top optimization opportunities table
- Pages needing attention
- Field data vs. lab data comparison

**Estimated Report Value:**
- Shows Google's official scores (trustworthy)
- Provides specific optimization recommendations
- Identifies real user pain points
- Prioritizes improvements by savings

---

## 4. Integration 2: advertools Library

### 4.1 Overview

**What advertools provides:**
- **XML Sitemap parsing** - Download and parse sitemap.xml files
- **Sitemap index support** - Handle multi-sitemap setups
- **robots.txt parsing** - Advanced validation and rule extraction
- **Google Analytics integration** - Fetch real traffic data
- **SERP scraping** - Google search results analysis
- **Keyword research** - Generate keyword variations
- **URL analysis** - Extract parameters, detect duplicates

**GitHub**: https://github.com/eliasdabbas/advertools
**Docs**: https://advertools.readthedocs.io/

### 4.2 Key Features We'll Use

#### 4.2.1 XML Sitemap Parsing
```python
import advertools as adv

# Parse single sitemap
sitemap_df = adv.sitemap_to_df('https://example.com/sitemap.xml')

# Parse sitemap index (automatically follows all sitemaps)
sitemap_df = adv.sitemap_to_df('https://example.com/sitemap_index.xml')

# Returns pandas DataFrame with:
# - loc (URL)
# - lastmod (last modified date)
# - changefreq (update frequency)
# - priority (0.0-1.0)
# - sitemap (which sitemap file it came from)
```

**Benefits:**
- Automatically handles sitemap indexes
- Validates XML structure
- Detects malformed sitemaps
- Compares sitemap URLs vs. crawled URLs
- Identifies orphan pages

#### 4.2.2 robots.txt Analysis
```python
# Parse robots.txt into structured data
robots_df = adv.robotstxt_to_df('https://example.com/robots.txt')

# Returns DataFrame with:
# - directive (User-agent, Disallow, Allow, Sitemap, etc.)
# - content (the rule or value)
# - robotstxt_url
```

**Benefits:**
- Structured parsing (better than regex)
- Validates syntax
- Extracts all directives
- Identifies conflicting rules

#### 4.2.3 Google Analytics Integration (Optional)
```python
# Fetch real traffic data
import advertools as adv
from google.oauth2 import service_account

credentials = service_account.Credentials.from_service_account_file(
    'credentials.json',
    scopes=['https://www.googleapis.com/auth/analytics.readonly']
)

# Get top pages by traffic
traffic_df = adv.ga_top_pages(
    view_id='123456789',
    credentials=credentials,
    start_date='2024-01-01',
    end_date='2024-12-31'
)

# Returns:
# - URL
# - pageviews
# - unique_pageviews
# - avg_time_on_page
# - bounce_rate
# - exit_rate
```

**Benefits:**
- Prioritize crawling high-traffic pages
- Identify underperforming content
- Correlate SEO issues with traffic drops

### 4.3 Data Model Extensions

**Add to Crawlability Analysis:**
```python
@dataclass
class CrawlabilityScore:
    # ... existing fields ...

    # Sitemap data from advertools
    sitemap_dataframe: Optional[Any] = None  # pandas DataFrame
    total_sitemap_urls: int = 0
    sitemap_coverage_percentage: float = 0.0  # crawled vs. sitemap
    urls_in_sitemap_not_crawled: List[str] = field(default_factory=list)
    urls_crawled_not_in_sitemap: List[str] = field(default_factory=list)

    # robots.txt data from advertools
    robots_dataframe: Optional[Any] = None  # pandas DataFrame
    robots_user_agents: List[str] = field(default_factory=list)
    robots_disallow_count: int = 0
    robots_allow_count: int = 0
    robots_sitemap_count: int = 0
```

### 4.4 Integration Points

**1. Crawlability Analyzer Enhancement:**
```python
# src/seo/crawlability.py

import advertools as adv
import pandas as pd

class CrawlabilityAnalyzer:
    def analyze_sitemaps(self, base_url: str) -> Dict:
        """Download and analyze XML sitemaps"""
        try:
            # Try common sitemap locations
            sitemap_urls = [
                f"{base_url}/sitemap.xml",
                f"{base_url}/sitemap_index.xml",
                f"{base_url}/sitemap1.xml"
            ]

            for sitemap_url in sitemap_urls:
                try:
                    df = adv.sitemap_to_df(sitemap_url)
                    if df is not None and len(df) > 0:
                        return self._process_sitemap_df(df)
                except Exception as e:
                    continue

            return {'found': False}
        except Exception as e:
            return {'error': str(e)}

    def analyze_robots_txt(self, robots_txt_content: str) -> Dict:
        """Parse robots.txt using advertools"""
        # Save to temp file for advertools
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
            f.write(robots_txt_content)
            temp_path = f.name

        try:
            df = adv.robotstxt_to_df(temp_path)
            return self._process_robots_df(df)
        finally:
            os.unlink(temp_path)
```

**2. Report Generation:**
```python
# src/seo/report_generator.py

def _process_sitemap_analysis(self, crawlability: Dict) -> Dict:
    """Format sitemap data for report"""
    if not crawlability.get('sitemap_dataframe'):
        return {}

    df = crawlability['sitemap_dataframe']

    return {
        'total_urls': len(df),
        'unique_domains': df['loc'].nunique(),
        'urls_with_priority': len(df[df['priority'].notna()]),
        'urls_by_changefreq': df['changefreq'].value_counts().to_dict(),
        'most_recent_update': df['lastmod'].max() if 'lastmod' in df else None,
    }
```

### 4.5 Report Additions

**Enhanced Crawlability Section:**
- Sitemap coverage visualization (pie chart: crawled vs. not crawled)
- Missing URLs table (in sitemap but not crawled)
- Orphan URLs table (crawled but not in sitemap)
- robots.txt directive breakdown
- Sitemap health score

---

## 5. Integration 3: Playwright for JavaScript Rendering

### 5.1 Overview

**Why Playwright?**
- Modern replacement for Selenium/Puppeteer
- Faster and more reliable
- Built-in auto-waiting (no explicit waits needed)
- Supports screenshots, PDFs, network monitoring
- Cross-browser (Chromium, Firefox, WebKit)

**What it enables:**
- Crawl Single Page Applications (React, Vue, Angular)
- Detect client-side rendered content
- Capture console errors
- Monitor network requests
- Take screenshots for visual validation

### 5.2 Installation & Setup

```bash
# Install library
poetry add playwright

# Install browsers
poetry run playwright install chromium

# Optional: Install system dependencies (Linux)
poetry run playwright install-deps
```

**Configuration:**
```python
# .env additions
ENABLE_JS_RENDERING=false  # Optional feature flag
PLAYWRIGHT_HEADLESS=true   # Run without visible browser
PLAYWRIGHT_TIMEOUT=30000   # Page load timeout (ms)
```

### 5.3 Architecture Decision: Hybrid Approach

**Option 1: Always Use Playwright** ❌
- Pros: Complete coverage
- Cons: 5-10x slower, higher resource usage

**Option 2: Selective Rendering** ✅ (RECOMMENDED)
- Detect SPA frameworks (React, Vue, Angular)
- Use Playwright only when needed
- Fall back to requests/BeautifulSoup for static sites

**Option 3: User Flag** ✅ (ALSO RECOMMENDED)
- Let user enable JS rendering via CLI flag
- Default to fast static crawling

**Proposed Approach: Combine Option 2 + 3**
```python
# Auto-detect OR user flag
if user_enabled_js_rendering or is_spa_framework_detected:
    use_playwright()
else:
    use_requests()
```

### 5.4 SPA Detection Heuristics

**Detect JavaScript frameworks:**
```python
def detect_spa_framework(html: str) -> Optional[str]:
    """Detect if site uses SPA framework"""
    indicators = {
        'react': ['react', '__REACT', 'ReactDOM'],
        'vue': ['Vue.js', '__VUE__', 'v-app'],
        'angular': ['ng-version', 'ng-app', '__ngContext__'],
        'next': ['__NEXT_DATA__', '_next/static'],
        'nuxt': ['__NUXT__'],
        'svelte': ['__SVELTE__'],
    }

    for framework, patterns in indicators.items():
        if any(pattern in html for pattern in patterns):
            return framework

    return None
```

**Detect dynamic content:**
```python
def has_dynamic_content(soup: BeautifulSoup) -> bool:
    """Check if page likely has client-side content"""
    # Check for empty body with JS bundles
    body = soup.find('body')
    if not body or len(body.get_text(strip=True)) < 100:
        scripts = soup.find_all('script', src=True)
        if len(scripts) > 3:  # Many external scripts
            return True

    # Check for common SPA patterns
    spa_indicators = [
        soup.find(id='root'),
        soup.find(id='app'),
        soup.find(class_='vue-app'),
        soup.find(attrs={'data-reactroot': True}),
    ]

    return any(spa_indicators)
```

### 5.5 Playwright Crawler Implementation

```python
# src/seo/playwright_crawler.py

from playwright.async_api import async_playwright, Browser, Page
from typing import Dict, Optional
import asyncio

class PlaywrightCrawler:
    """Async crawler with JavaScript rendering support"""

    def __init__(
        self,
        headless: bool = True,
        timeout: int = 30000,
        user_agent: Optional[str] = None
    ):
        self.headless = headless
        self.timeout = timeout
        self.user_agent = user_agent
        self.browser: Optional[Browser] = None

    async def __aenter__(self):
        """Context manager entry"""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=self.headless)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        if self.browser:
            await self.browser.close()
        await self.playwright.stop()

    async def crawl_page(self, url: str) -> Dict:
        """Crawl a single page with JS rendering"""
        context = await self.browser.new_context(
            user_agent=self.user_agent,
            viewport={'width': 1920, 'height': 1080}
        )

        page = await context.new_page()

        # Collect console messages
        console_messages = []
        page.on('console', lambda msg: console_messages.append({
            'type': msg.type,
            'text': msg.text
        }))

        # Collect network errors
        network_errors = []
        page.on('requestfailed', lambda req: network_errors.append({
            'url': req.url,
            'failure': req.failure
        }))

        try:
            # Navigate to page
            response = await page.goto(url, timeout=self.timeout, wait_until='networkidle')

            # Wait for content to load
            await page.wait_for_load_state('domcontentloaded')

            # Get rendered HTML
            html = await page.content()

            # Get page title (after JS execution)
            title = await page.title()

            # Optional: Take screenshot
            screenshot = await page.screenshot(full_page=False)

            # Get final URL (after redirects)
            final_url = page.url

            return {
                'url': final_url,
                'html': html,
                'title': title,
                'status_code': response.status if response else None,
                'console_messages': console_messages,
                'network_errors': network_errors,
                'screenshot': screenshot,  # bytes
            }

        finally:
            await context.close()

    async def crawl_multiple(self, urls: List[str]) -> List[Dict]:
        """Crawl multiple URLs concurrently"""
        tasks = [self.crawl_page(url) for url in urls]
        return await asyncio.gather(*tasks, return_exceptions=True)
```

### 5.6 Integration with Existing Crawler

**Hybrid Crawler:**
```python
# src/seo/async_site_crawler.py

class AsyncSiteCrawler:
    def __init__(
        self,
        ...,
        enable_js_rendering: bool = False,
        js_rendering_strategy: str = 'auto'  # 'auto', 'always', 'never'
    ):
        self.enable_js_rendering = enable_js_rendering
        self.js_rendering_strategy = js_rendering_strategy
        self.playwright_crawler: Optional[PlaywrightCrawler] = None

    async def _should_use_playwright(self, url: str, html: str) -> bool:
        """Decide whether to use Playwright for this page"""
        if self.js_rendering_strategy == 'always':
            return True
        if self.js_rendering_strategy == 'never':
            return False

        # Auto-detect
        if not self.enable_js_rendering:
            return False

        # Check for SPA indicators
        soup = BeautifulSoup(html, 'html.parser')
        return has_dynamic_content(soup) or detect_spa_framework(html) is not None

    async def _crawl_page_hybrid(self, url: str) -> PageMetadata:
        """Crawl with automatic JS rendering detection"""

        # 1. Fast initial fetch (static)
        static_html, response_time = await self._fetch_page_fast(url)

        # 2. Check if JS rendering needed
        if await self._should_use_playwright(url, static_html):
            logger.info(f"  → Using JavaScript rendering for {url}")

            if not self.playwright_crawler:
                self.playwright_crawler = PlaywrightCrawler()
                await self.playwright_crawler.__aenter__()

            # 3. Re-fetch with Playwright
            js_data = await self.playwright_crawler.crawl_page(url)
            html = js_data['html']
            console_errors = len([m for m in js_data['console_messages'] if m['type'] == 'error'])

            # Add JS-specific metadata
            js_metadata = {
                'rendered_with_js': True,
                'js_console_errors': console_errors,
                'js_network_errors': len(js_data['network_errors']),
            }
        else:
            html = static_html
            js_metadata = {'rendered_with_js': False}

        # 4. Parse and analyze
        soup = BeautifulSoup(html, 'html.parser')
        page_metadata = self._parse_page_metadata(soup, url, response_time)

        # 5. Add JS metadata
        for key, value in js_metadata.items():
            setattr(page_metadata, key, value)

        return page_metadata
```

### 5.7 Data Model Extensions

```python
@dataclass
class PageMetadata:
    # ... existing fields ...

    # JavaScript rendering
    rendered_with_js: bool = False
    js_framework: Optional[str] = None  # 'react', 'vue', 'angular', etc.
    js_console_errors: int = 0
    js_network_errors: int = 0
    has_hydration_issues: bool = False  # SSR/CSR mismatch
```

### 5.8 Report Additions

**New "JavaScript Analysis" subsection in Technical Issues:**
- Pages requiring JS rendering
- JavaScript frameworks detected
- Console errors per page
- Network failures
- Hydration warnings (for SSR/SSG sites)

### 5.9 Performance Considerations

**Resource Usage:**
- Playwright: ~200-300MB RAM per browser instance
- Recommended: Limit concurrent Playwright sessions to 2-3
- CPU: 1.5-2x higher than static crawling

**Speed Impact:**
```
Static crawl (requests):     ~0.5-1.0s per page
Playwright crawl:            ~3-5s per page (6-10x slower)
Hybrid (10% JS):             ~0.7-1.2s per page average
```

**Mitigation Strategies:**
1. Use auto-detection (only render when needed)
2. Limit concurrent Playwright sessions
3. Add `--enable-js` flag (opt-in)
4. Consider caching rendered pages
5. Offer "quick scan" mode (skip JS)

---

## 6. Architecture & Design

### 6.1 System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                       CLI / User Input                       │
│  python crawl.py <url> --enable-lighthouse --enable-js      │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                     SEOAnalyzer                             │
│  - Orchestrates crawling & analysis                         │
│  - Manages API clients                                      │
└────────┬────────────────────┬──────────────────┬───────────┘
         │                    │                  │
         ▼                    ▼                  ▼
┌────────────────┐   ┌──────────────┐   ┌──────────────────┐
│ AsyncSiteCrawler│   │ PageSpeed    │   │ advertools       │
│                 │   │ Insights API │   │ Integration      │
│ ┌─────────────┐ │   │              │   │                  │
│ │requests/    │ │   │ - Lighthouse │   │ - Sitemap Parser │
│ │aiohttp      │ │   │ - CrUX Data  │   │ - robots.txt     │
│ └─────────────┘ │   │ - Opps       │   │ - Analytics      │
│                 │   └──────────────┘   └──────────────────┘
│ ┌─────────────┐ │
│ │Playwright   │ │
│ │(conditional)│ │
│ └─────────────┘ │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│                   Analysis Modules                           │
│  - TechnicalAnalyzer                                        │
│  - ContentQualityAnalyzer                                   │
│  - CoreWebVitalsAnalyzer                                    │
│  - StructuredDataAnalyzer                                   │
│  - CrawlabilityAnalyzer (enhanced with advertools)         │
└────────┬────────────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│                  ReportGenerator                            │
│  - Combines all analysis results                           │
│  - Generates HTML report with new sections                 │
│  - Lighthouse gauges, sitemap coverage, JS analysis        │
└─────────────────────────────────────────────────────────────┘
```

### 6.2 Module Structure

```
src/seo/
├── external/                          # NEW: External integrations
│   ├── __init__.py
│   ├── pagespeed_insights.py        # PageSpeed Insights API client
│   ├── advertools_integration.py    # advertools wrapper
│   └── playwright_crawler.py        # Playwright-based JS crawler
│
├── crawler.py                        # Existing static crawler
├── async_site_crawler.py            # Enhanced: Hybrid crawling
├── analyzer.py                       # Enhanced: Orchestration
├── report_generator.py              # Enhanced: New report sections
└── models.py                         # Enhanced: New fields
```

### 6.3 Configuration Management

**Enhanced .env file:**
```bash
# Existing
LLM_API_KEY=...
LLM_MODEL=claude-sonnet-4-5
LLM_PROVIDER=anthropic

# NEW: PageSpeed Insights
GOOGLE_PSI_API_KEY=AIzaSyC...          # Optional, enables Lighthouse
PSI_STRATEGY=mobile                     # 'mobile' or 'desktop'
PSI_ENABLE_FIELD_DATA=true             # Include CrUX data

# NEW: Playwright
ENABLE_JS_RENDERING=false               # Opt-in feature
PLAYWRIGHT_HEADLESS=true                # Run browser in background
PLAYWRIGHT_TIMEOUT=30000                # Page load timeout (ms)
JS_RENDERING_STRATEGY=auto              # 'auto', 'always', 'never'

# NEW: advertools (Google Analytics - optional)
GOOGLE_ANALYTICS_CREDENTIALS=path/to/creds.json
GOOGLE_ANALYTICS_VIEW_ID=123456789
```

**Enhanced Config class:**
```python
# src/seo/config.py

@dataclass
class Config:
    # Existing fields...

    # PageSpeed Insights
    google_psi_api_key: Optional[str] = None
    psi_strategy: str = "mobile"
    psi_enable_field_data: bool = True

    # Playwright
    enable_js_rendering: bool = False
    playwright_headless: bool = True
    playwright_timeout: int = 30000
    js_rendering_strategy: str = "auto"

    # Google Analytics (advertools)
    ga_credentials_path: Optional[str] = None
    ga_view_id: Optional[str] = None

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            # Existing...
            google_psi_api_key=os.getenv("GOOGLE_PSI_API_KEY"),
            psi_strategy=os.getenv("PSI_STRATEGY", "mobile"),
            enable_js_rendering=os.getenv("ENABLE_JS_RENDERING", "false").lower() == "true",
            playwright_headless=os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() == "true",
            playwright_timeout=int(os.getenv("PLAYWRIGHT_TIMEOUT", "30000")),
            js_rendering_strategy=os.getenv("JS_RENDERING_STRATEGY", "auto"),
            ga_credentials_path=os.getenv("GOOGLE_ANALYTICS_CREDENTIALS"),
            ga_view_id=os.getenv("GOOGLE_ANALYTICS_VIEW_ID"),
        )
```

### 6.4 CLI Enhancements

```python
# crawl.py

parser.add_argument(
    '--enable-lighthouse',
    action='store_true',
    help='Enable Google PageSpeed Insights analysis (requires GOOGLE_PSI_API_KEY)'
)

parser.add_argument(
    '--lighthouse-strategy',
    choices=['mobile', 'desktop'],
    default='mobile',
    help='PageSpeed Insights strategy (default: mobile)'
)

parser.add_argument(
    '--enable-js',
    action='store_true',
    help='Enable JavaScript rendering with Playwright (slower but handles SPAs)'
)

parser.add_argument(
    '--js-strategy',
    choices=['auto', 'always', 'never'],
    default='auto',
    help='JavaScript rendering strategy (default: auto-detect)'
)

parser.add_argument(
    '--fetch-analytics',
    action='store_true',
    help='Fetch Google Analytics data (requires GA credentials)'
)
```

**Usage examples:**
```bash
# Standard crawl (fast)
python crawl.py https://example.com

# With PageSpeed Insights
python crawl.py https://example.com --enable-lighthouse

# With JavaScript rendering (auto-detect SPAs)
python crawl.py https://example.com --enable-js

# Full analysis (slow but comprehensive)
python crawl.py https://example.com --enable-lighthouse --enable-js --fetch-analytics

# Force JS rendering for all pages
python crawl.py https://spa-site.com --enable-js --js-strategy always
```

---

## 7. Implementation Plan

### 7.1 Phase 1: Google PageSpeed Insights (Week 1-2)

**Tasks:**
1. **Setup & Authentication** (4 hours)
   - Create Google Cloud project
   - Enable PageSpeed Insights API
   - Generate API key
   - Add to .env and Config

2. **API Client Implementation** (8 hours)
   - Create `src/seo/external/pagespeed_insights.py`
   - Implement rate limiting
   - Handle errors and retries
   - Add caching (optional)

3. **Data Model Updates** (2 hours)
   - Add Lighthouse fields to PageMetadata
   - Update JSON serialization

4. **Crawler Integration** (6 hours)
   - Add PSI calls to AsyncSiteCrawler
   - Make it optional/conditional
   - Handle API errors gracefully

5. **Report Generator** (8 hours)
   - Create `_process_lighthouse_analysis()`
   - Add gauge charts (5 scores)
   - Add metrics bar chart
   - Add opportunities table

6. **Template Updates** (6 hours)
   - Add Lighthouse section to Tab 5
   - Create gauge chart JavaScript
   - Style tables and charts

7. **Testing** (6 hours)
   - Unit tests for API client
   - Integration tests
   - Test with real sites
   - Performance benchmarking

**Total: 40 hours (1 week full-time, 2 weeks part-time)**

**Deliverables:**
- ✅ Working PageSpeed Insights integration
- ✅ Lighthouse scores in reports
- ✅ Optimization opportunities
- ✅ Documentation

---

### 7.2 Phase 2: advertools Integration (Week 2-3)

**Tasks:**
1. **Library Installation** (1 hour)
   - Add to pyproject.toml
   - Install and verify

2. **Sitemap Parser** (6 hours)
   - Enhance `src/seo/crawlability.py`
   - Add sitemap download logic
   - Parse with advertools
   - Compare sitemap vs. crawled URLs

3. **robots.txt Enhancement** (4 hours)
   - Replace manual parsing with advertools
   - Extract all directives
   - Validate syntax

4. **Coverage Analysis** (6 hours)
   - Calculate sitemap coverage %
   - Identify orphan pages
   - Detect missing pages

5. **Report Updates** (6 hours)
   - Add sitemap coverage chart
   - Add orphan pages table
   - Add robots.txt breakdown

6. **Optional: Analytics Integration** (8 hours)
   - Create GA client
   - Fetch top pages
   - Prioritize crawling by traffic
   - Add traffic data to report

7. **Testing** (4 hours)
   - Test with various sitemap formats
   - Test sitemap indexes
   - Test edge cases

**Total: 35 hours (1 week full-time)**

**Deliverables:**
- ✅ Automated sitemap parsing
- ✅ Enhanced crawlability analysis
- ✅ Coverage metrics
- ✅ Optional GA integration

---

### 7.3 Phase 3: Playwright Integration (Week 3-4)

**Tasks:**
1. **Installation & Setup** (2 hours)
   - Add playwright to dependencies
   - Install browser binaries
   - Create configuration

2. **PlaywrightCrawler Class** (10 hours)
   - Create `src/seo/external/playwright_crawler.py`
   - Implement async crawling
   - Add console monitoring
   - Add network monitoring
   - Handle errors and timeouts

3. **SPA Detection** (6 hours)
   - Implement framework detection
   - Implement dynamic content detection
   - Create heuristics

4. **Hybrid Crawler** (10 hours)
   - Modify AsyncSiteCrawler
   - Add conditional rendering
   - Implement fallback logic
   - Optimize performance

5. **Data Model Updates** (2 hours)
   - Add JS rendering fields
   - Track console errors
   - Track framework detection

6. **Report Updates** (4 hours)
   - Add "JavaScript Analysis" section
   - Show which pages used JS rendering
   - Display console errors
   - Show framework detection

7. **Performance Optimization** (6 hours)
   - Limit concurrent browsers
   - Add browser pooling
   - Optimize page waits
   - Add caching

8. **Testing** (8 hours)
   - Test with React apps
   - Test with Vue apps
   - Test with Angular apps
   - Performance benchmarking
   - Memory profiling

**Total: 48 hours (1.5 weeks full-time)**

**Deliverables:**
- ✅ JavaScript rendering support
- ✅ SPA crawling capability
- ✅ Hybrid crawler (smart auto-detection)
- ✅ Performance optimizations

---

### 7.4 Summary Timeline

| Phase | Duration | Effort | Dependencies |
|-------|----------|--------|-------------|
| **Phase 1: PageSpeed Insights** | Week 1-2 | 40 hours | None |
| **Phase 2: advertools** | Week 2-3 | 35 hours | None (can parallel with Phase 1) |
| **Phase 3: Playwright** | Week 3-4 | 48 hours | Phases 1-2 should be complete |
| **TOTAL** | **3-4 weeks** | **123 hours** | |

**Parallelization Opportunity:**
- Phases 1 and 2 can be developed in parallel
- This reduces calendar time from 4 weeks to 3 weeks

---

## 8. Testing Strategy

### 8.1 Unit Tests

**PageSpeed Insights API:**
```python
# tests/test_pagespeed_insights.py

import pytest
from unittest.mock import Mock, patch
from seo.external.pagespeed_insights import PageSpeedInsightsAPI

@pytest.mark.asyncio
async def test_api_request():
    """Test basic API request"""
    api = PageSpeedInsightsAPI(api_key='test-key')

    with patch('httpx.AsyncClient.get') as mock_get:
        mock_get.return_value.json.return_value = {
            'lighthouseResult': {
                'categories': {
                    'performance': {'score': 0.92}
                }
            }
        }

        result = await api.analyze('https://example.com')
        assert result['performance_score'] == 92

@pytest.mark.asyncio
async def test_rate_limiting():
    """Test rate limit enforcement"""
    api = PageSpeedInsightsAPI(api_key='test-key')

    # Simulate 400 requests
    for _ in range(400):
        await api.rate_limit_check()

    # Next request should wait
    import time
    start = time.time()
    await api.rate_limit_check()
    elapsed = time.time() - start

    assert elapsed > 0  # Should have waited
```

**advertools Integration:**
```python
# tests/test_advertools_integration.py

def test_sitemap_parsing():
    """Test sitemap parsing with advertools"""
    from seo.crawlability import CrawlabilityAnalyzer

    analyzer = CrawlabilityAnalyzer('https://example.com')
    result = analyzer.analyze_sitemaps('https://example.com')

    assert 'total_urls' in result
    assert result['total_urls'] > 0
```

**Playwright Crawler:**
```python
# tests/test_playwright_crawler.py

@pytest.mark.asyncio
async def test_js_rendering():
    """Test JavaScript rendering"""
    from seo.external.playwright_crawler import PlaywrightCrawler

    async with PlaywrightCrawler() as crawler:
        result = await crawler.crawl_page('https://reactjs.org')

        assert result['html']
        assert 'React' in result['html']
        assert result['status_code'] == 200

@pytest.mark.asyncio
async def test_spa_detection():
    """Test SPA framework detection"""
    from seo.async_site_crawler import detect_spa_framework

    html = '<div id="root"></div><script src="react.js"></script>'
    framework = detect_spa_framework(html)

    assert framework == 'react'
```

### 8.2 Integration Tests

**End-to-End Crawl Test:**
```python
# tests/integration/test_full_crawl.py

@pytest.mark.integration
def test_crawl_with_all_features():
    """Test complete crawl with all enhancements"""
    from seo import SEOAnalyzer

    analyzer = SEOAnalyzer(
        llm_api_key=os.getenv('LLM_API_KEY'),
        google_psi_api_key=os.getenv('GOOGLE_PSI_API_KEY'),
    )

    site_data, technical_issues, recommendations, advanced = analyzer.analyze_site(
        'https://example.com',
        max_pages=3,
        enable_lighthouse=True,
        enable_js_rendering=False
    )

    # Verify Lighthouse data
    assert any(page.lighthouse_performance_score for page in site_data.values())

    # Verify sitemap data
    assert advanced['crawlability']['total_sitemap_urls'] > 0
```

### 8.3 Performance Tests

**Benchmark Suite:**
```python
# tests/performance/test_benchmarks.py

import pytest
import time

@pytest.mark.benchmark
def test_crawl_speed_static():
    """Benchmark static crawling speed"""
    start = time.time()

    # Crawl 10 pages without JS
    crawler = AsyncSiteCrawler(enable_js_rendering=False)
    asyncio.run(crawler.crawl_site('https://example.com', max_pages=10))

    elapsed = time.time() - start

    # Should be under 15 seconds (1.5s per page)
    assert elapsed < 15

@pytest.mark.benchmark
def test_crawl_speed_with_playwright():
    """Benchmark crawling with Playwright"""
    start = time.time()

    # Crawl 5 pages with JS
    crawler = AsyncSiteCrawler(
        enable_js_rendering=True,
        js_rendering_strategy='always'
    )
    asyncio.run(crawler.crawl_site('https://reactjs.org', max_pages=5))

    elapsed = time.time() - start

    # Should be under 30 seconds (6s per page)
    assert elapsed < 30
```

### 8.4 Manual Testing Checklist

**Pre-release Testing:**
- [ ] Test with static HTML site (e.g., Wikipedia)
- [ ] Test with React SPA (e.g., reactjs.org)
- [ ] Test with Vue SPA (e.g., vuejs.org)
- [ ] Test with Angular SPA (e.g., angular.io)
- [ ] Test with large sitemap (>10,000 URLs)
- [ ] Test with sitemap index (multiple sitemaps)
- [ ] Test with malformed robots.txt
- [ ] Test with no sitemap
- [ ] Test rate limiting (401+ requests)
- [ ] Test API key errors
- [ ] Test network failures
- [ ] Test memory usage (crawl 100+ pages)

---

## 9. Risks & Mitigation

### 9.1 API Rate Limits & Costs

**Risk:**
- PageSpeed Insights: 400 req/100s limit
- Exceeding limits causes failures
- Potential costs if billing enabled

**Mitigation:**
1. Implement strict rate limiting in code
2. Add request queue with throttling
3. Default to disabled (opt-in via flag)
4. Display API usage in logs
5. Cache results for 24 hours

**Code:**
```python
class RateLimitedAPI:
    def __init__(self, requests_per_100s=400):
        self.semaphore = asyncio.Semaphore(requests_per_100s)
        self.request_times = deque()

    async def enforce_rate_limit(self):
        now = time.time()

        # Remove requests older than 100s
        while self.request_times and now - self.request_times[0] > 100:
            self.request_times.popleft()

        # Wait if at limit
        if len(self.request_times) >= 400:
            wait_time = 100 - (now - self.request_times[0])
            await asyncio.sleep(wait_time)

        self.request_times.append(now)
```

### 9.2 Performance Impact

**Risk:**
- Playwright is 5-10x slower
- High memory usage (300MB per browser)
- Could timeout on slow networks

**Mitigation:**
1. Make JS rendering opt-in
2. Auto-detect SPAs (only render when needed)
3. Limit concurrent Playwright sessions to 2-3
4. Add `--quick-scan` mode (no JS, no API calls)
5. Display progress indicators
6. Add timeouts and retries

**Configuration:**
```python
# Limit concurrency
playwright_semaphore = asyncio.Semaphore(2)  # Max 2 browsers

# Add timeout
async with asyncio.timeout(30):  # 30s max per page
    await crawler.crawl_page(url)
```

### 9.3 Browser Binary Dependencies

**Risk:**
- Playwright requires 300MB Chromium download
- Installation might fail on some systems
- Docker environments need special setup

**Mitigation:**
1. Make Playwright optional (graceful degradation)
2. Document installation steps
3. Provide Docker image with pre-installed browsers
4. Add setup verification script
5. Fallback to static crawling if Playwright unavailable

**Verification Script:**
```bash
# scripts/verify_setup.sh

echo "Checking dependencies..."

# Check Python version
python --version

# Check Playwright
if python -c "import playwright" 2>/dev/null; then
    echo "✓ Playwright installed"
else
    echo "✗ Playwright not installed: pip install playwright"
fi

# Check browser binaries
if playwright install --help &>/dev/null; then
    echo "✓ Playwright CLI available"
    playwright install chromium
else
    echo "✗ Playwright CLI not available"
fi

# Check API keys
if [ -n "$GOOGLE_PSI_API_KEY" ]; then
    echo "✓ PageSpeed Insights API key configured"
else
    echo "⚠ PageSpeed Insights API key not configured (optional)"
fi
```

### 9.4 Data Quality & Accuracy

**Risk:**
- PageSpeed Insights data might not be available for all sites
- Sitemaps might be outdated or incorrect
- JS rendering might miss content

**Mitigation:**
1. Always show data source (Lab vs. Field)
2. Indicate confidence levels
3. Handle missing data gracefully
4. Compare static vs. JS-rendered content
5. Log discrepancies for review

**Handling Missing Data:**
```python
# Report when CrUX data unavailable
if not crux_data:
    warnings.append(
        "Real user data (CrUX) not available for this site. "
        "This typically means the site has low traffic. "
        "Lab data from Lighthouse is shown instead."
    )
```

### 9.5 Maintenance Burden

**Risk:**
- External APIs can change
- Playwright updates might break things
- advertools updates might change API

**Mitigation:**
1. Pin dependency versions
2. Add integration tests for external APIs
3. Monitor API changelogs
4. Version lock in production
5. Add deprecation warnings

**Dependency Pinning:**
```toml
[tool.poetry.dependencies]
playwright = "~1.40.0"  # Allow patch updates only
advertools = "~0.14.0"
```

---

## 10. Success Metrics

### 10.1 Performance Metrics

**Crawl Speed:**
- Static crawl: ≤ 1.0s per page (baseline)
- Hybrid crawl: ≤ 1.5s per page (90% static, 10% JS)
- Full JS crawl: ≤ 5.0s per page (acceptable for SPAs)

**Memory Usage:**
- Static crawl: ≤ 200MB
- With Playwright: ≤ 500MB (max 2 concurrent browsers)

**API Success Rate:**
- PageSpeed Insights: ≥ 95% success rate
- Handle rate limits gracefully (0% failures)

### 10.2 Feature Adoption

**Usage Tracking:**
```python
# Add telemetry (opt-in)
metrics = {
    'lighthouse_enabled': bool(config.google_psi_api_key),
    'js_rendering_enabled': config.enable_js_rendering,
    'js_rendering_strategy': config.js_rendering_strategy,
    'pages_rendered_with_js': count_js_pages,
    'lighthouse_api_calls': psi_call_count,
}
```

**Target Metrics:**
- 30% of users enable Lighthouse (within 3 months)
- 15% of users enable JS rendering
- 50% of SPA sites detected correctly

### 10.3 Quality Metrics

**Accuracy:**
- SPA detection accuracy: ≥ 90%
- Sitemap parsing success: ≥ 98%
- robots.txt parsing success: ≥ 99%

**Report Value:**
- Lighthouse recommendations: 10-20 actionable items per site
- Sitemap coverage: Identify ≥ 80% of orphan pages
- JS console errors: Detect ≥ 95% of runtime errors

### 10.4 User Satisfaction

**Qualitative Metrics:**
- Report perceived value (survey): ≥ 4.0/5.0
- Feature usefulness (survey): ≥ 4.2/5.0
- Would recommend (NPS): ≥ 40

**Documentation:**
- Setup time for new users: ≤ 15 minutes
- Time to first successful crawl: ≤ 5 minutes

---

## 11. Future Enhancements

### 11.1 Phase 4: Additional APIs (Future)

**Potential Integrations:**
1. **Ahrefs API** - Backlink analysis, domain rating
2. **SEMrush API** - Keyword rankings, competitor analysis
3. **Moz API** - Domain Authority, Page Authority
4. **WebPageTest API** - Multi-location performance testing
5. **SecurityHeaders.com API** - Enhanced security scoring
6. **BuiltWith API** - Technology stack detection

### 11.2 Phase 5: Advanced Features (Future)

**Machine Learning:**
- Predict SEO score improvements
- Auto-categorize issues by priority
- Suggest content improvements using NLP

**Monitoring & Alerts:**
- Scheduled crawls (daily/weekly)
- Email alerts for regressions
- Slack/Discord integrations

**Competitive Analysis:**
- Compare against competitor sites
- SERP position tracking
- Content gap analysis

**Visual Testing:**
- Screenshot comparison (detect visual regressions)
- Mobile vs. desktop rendering diff
- Above-the-fold content analysis

### 11.3 Phase 6: Enterprise Features (Future)

**Multi-site Management:**
- Crawl multiple sites
- Comparative dashboards
- Portfolio-level reporting

**API Access:**
- RESTful API for programmatic access
- Webhook notifications
- CSV/JSON export

**Team Collaboration:**
- Multi-user access
- Role-based permissions
- Shared reports

---

## 12. Appendices

### Appendix A: API Documentation Links

- **Google PageSpeed Insights API**: https://developers.google.com/speed/docs/insights/v5/get-started
- **Playwright Docs**: https://playwright.dev/python/
- **advertools Docs**: https://advertools.readthedocs.io/
- **Chrome User Experience Report**: https://developers.google.com/web/tools/chrome-user-experience-report

### Appendix B: Sample API Responses

**PageSpeed Insights Response (truncated):**
```json
{
  "lighthouseResult": {
    "requestedUrl": "https://example.com",
    "finalUrl": "https://example.com/",
    "lighthouseVersion": "10.4.0",
    "userAgent": "Mozilla/5.0...",
    "fetchTime": "2024-11-23T12:00:00.000Z",
    "categories": {
      "performance": {
        "id": "performance",
        "title": "Performance",
        "score": 0.92
      }
    },
    "audits": {
      "first-contentful-paint": {
        "id": "first-contentful-paint",
        "title": "First Contentful Paint",
        "description": "First Contentful Paint marks the time...",
        "score": 1,
        "scoreDisplayMode": "numeric",
        "displayValue": "0.8 s"
      }
    }
  },
  "loadingExperience": {
    "id": "https://example.com/",
    "metrics": {
      "LARGEST_CONTENTFUL_PAINT_MS": {
        "percentile": 1847,
        "distributions": [...],
        "category": "FAST"
      }
    },
    "overall_category": "FAST"
  }
}
```

### Appendix C: Environment Setup Guide

**Complete Setup Instructions:**

```bash
# 1. Install dependencies
poetry install

# 2. Install Playwright browsers
poetry run playwright install chromium

# 3. Setup Google PageSpeed Insights API
# - Go to https://console.cloud.google.com
# - Create new project or select existing
# - Enable PageSpeed Insights API
# - Create API key (Credentials > Create Credentials > API Key)

# 4. Configure environment
cp .env.example .env
nano .env  # Add your API keys

# Required:
# LLM_API_KEY=your_anthropic_or_openai_key

# Optional (for new features):
# GOOGLE_PSI_API_KEY=AIzaSyC...
# ENABLE_JS_RENDERING=true
# GOOGLE_ANALYTICS_CREDENTIALS=/path/to/ga-credentials.json

# 5. Verify installation
poetry run python -c "import playwright; print('✓ Playwright OK')"
poetry run python -c "import advertools; print('✓ advertools OK')"

# 6. Test crawl
poetry run python crawl.py https://example.com 3

# 7. Test with new features
poetry run python crawl.py https://example.com 3 --enable-lighthouse --enable-js
```

### Appendix D: Cost Analysis

**Monthly Cost Estimates:**

| Service | Free Tier | Paid Tier | Estimated Cost |
|---------|-----------|-----------|----------------|
| **PageSpeed Insights API** | 25,000 req/day | 240,000 req/day | $0 (free sufficient for most) |
| **Playwright** | Unlimited | N/A | $0 (open source) |
| **advertools** | Unlimited | N/A | $0 (open source) |
| **Google Analytics API** | Unlimited | N/A | $0 (if you own the property) |
| **Hosting/Compute** | Varies | Varies | $5-20/month (modest VPS) |
| **TOTAL** | - | - | **$5-20/month** |

**Notes:**
- No API costs if staying within free tiers
- Main cost is hosting/compute for running crawls
- Playwright increases RAM requirements (+500MB)
- Can run locally for $0/month

---

## 13. Approval & Sign-off

### 13.1 Stakeholder Review

**Technical Review:**
- [ ] Architecture approved
- [ ] Security implications reviewed
- [ ] Performance impact acceptable
- [ ] Testing strategy sufficient

**Product Review:**
- [ ] User value proposition clear
- [ ] Feature priority alignment
- [ ] Documentation plan approved
- [ ] Success metrics agreed

**Resource Review:**
- [ ] Development timeline realistic
- [ ] Budget approved
- [ ] Team capacity confirmed

### 13.2 Implementation Authorization

**Approved by:** _______________
**Date:** _______________
**Priority:** High / Medium / Low
**Target Completion:** _______________

---

## Document Change Log

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-11-23 | SEO Team | Initial draft |

---

**END OF DOCUMENT**
