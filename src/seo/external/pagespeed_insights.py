"""
Google PageSpeed Insights API Client

Provides access to Google's Lighthouse performance data and Chrome User Experience Report (CrUX).
API Documentation: https://developers.google.com/speed/docs/insights/v5/get-started

Rate Limits:
- 400 requests per 100 seconds
- 25,000 requests per day (free tier)
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from collections import deque
import httpx

logger = logging.getLogger(__name__)


class PageSpeedInsightsAPI:
    """Client for Google PageSpeed Insights API v5"""

    API_URL = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
    RATE_LIMIT_REQUESTS = 400  # Max requests per 100 seconds
    RATE_LIMIT_WINDOW = 100  # Seconds

    def __init__(
        self,
        api_key: str,
        strategy: str = "mobile",  # 'mobile' or 'desktop'
        categories: Optional[List[str]] = None,
        locale: str = "en"
    ):
        """
        Initialize PageSpeed Insights API client.

        Args:
            api_key: Google API key with PageSpeed Insights API enabled
            strategy: 'mobile' or 'desktop' analysis
            categories: List of categories to analyze (default: all)
            locale: Locale for results (default: 'en')
        """
        self.api_key = api_key
        self.strategy = strategy
        self.categories = categories or [
            'performance',
            'accessibility',
            'best-practices',
            'seo',
            'pwa'
        ]
        self.locale = locale

        # Rate limiting
        self.request_times: deque = deque()
        self.semaphore = asyncio.Semaphore(4)  # Max 4 concurrent requests
        self.total_requests = 0
        self.failed_requests = 0

    async def analyze(
        self,
        url: str,
        strategy: Optional[str] = None,
        categories: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Analyze a URL with PageSpeed Insights.

        Args:
            url: URL to analyze
            strategy: Override default strategy ('mobile' or 'desktop')
            categories: Override default categories

        Returns:
            Dictionary with parsed Lighthouse and CrUX data

        Raises:
            httpx.HTTPStatusError: If API returns error status
            Exception: For other errors
        """
        await self._enforce_rate_limit()

        params = {
            'url': url,
            'key': self.api_key,
            'strategy': strategy or self.strategy,
            'category': categories or self.categories,
            'locale': self.locale
        }

        try:
            async with self.semaphore:
                async with httpx.AsyncClient(timeout=120.0) as client:
                    logger.info(f"[PSI] Analyzing {url} ({self.strategy})")
                    response = await client.get(self.API_URL, params=params)
                    response.raise_for_status()

                    self.total_requests += 1
                    data = response.json()

                    return self._parse_response(data, url)

        except httpx.TimeoutException:
            self.failed_requests += 1
            logger.error(f"[PSI] Timeout analyzing {url} (>120s)")
            raise Exception(f"PageSpeed Insights timeout for {url}")

        except httpx.HTTPStatusError as e:
            self.failed_requests += 1
            if e.response.status_code == 429:
                logger.error(f"[PSI] Rate limit exceeded for {url}")
                raise Exception("PageSpeed Insights rate limit exceeded. Try again later.")
            elif e.response.status_code == 400:
                logger.error(f"[PSI] Invalid URL or parameters: {url}")
                raise Exception(f"Invalid URL for PageSpeed Insights: {url}")
            else:
                logger.error(f"[PSI] API error {e.response.status_code} for {url}")
                raise

        except Exception as e:
            self.failed_requests += 1
            error_msg = str(e) if str(e) else type(e).__name__
            logger.error(f"[PSI] Error analyzing {url}: {error_msg}")
            raise

    async def _enforce_rate_limit(self):
        """Enforce rate limit of 400 requests per 100 seconds"""
        now = datetime.now()

        # Remove requests older than 100 seconds
        while self.request_times and (now - self.request_times[0]) > timedelta(seconds=self.RATE_LIMIT_WINDOW):
            self.request_times.popleft()

        # Wait if at limit
        if len(self.request_times) >= self.RATE_LIMIT_REQUESTS:
            oldest_request = self.request_times[0]
            wait_time = self.RATE_LIMIT_WINDOW - (now - oldest_request).total_seconds()

            if wait_time > 0:
                logger.warning(f"[PSI] Rate limit reached. Waiting {wait_time:.1f}s...")
                await asyncio.sleep(wait_time)

                # Clear old requests after waiting
                now = datetime.now()
                while self.request_times and (now - self.request_times[0]) > timedelta(seconds=self.RATE_LIMIT_WINDOW):
                    self.request_times.popleft()

        self.request_times.append(now)

    def _parse_response(self, data: Dict, url: str) -> Dict[str, Any]:
        """
        Parse PageSpeed Insights API response.

        Args:
            data: Raw API response
            url: URL that was analyzed

        Returns:
            Parsed data with Lighthouse scores and metrics
        """
        lighthouse = data.get('lighthouseResult', {})
        loading_experience = data.get('loadingExperience', {})

        # Extract category scores (0-1 scale, convert to 0-100)
        categories = lighthouse.get('categories', {})
        scores = {
            'performance': self._extract_score(categories.get('performance')),
            'accessibility': self._extract_score(categories.get('accessibility')),
            'best_practices': self._extract_score(categories.get('best-practices')),
            'seo': self._extract_score(categories.get('seo')),
            'pwa': self._extract_score(categories.get('pwa')),
        }

        # Extract performance metrics
        audits = lighthouse.get('audits', {})
        metrics = {
            'fcp': self._extract_metric_ms(audits.get('first-contentful-paint')),
            'lcp': self._extract_metric_ms(audits.get('largest-contentful-paint')),
            'si': self._extract_metric_ms(audits.get('speed-index')),
            'tti': self._extract_metric_ms(audits.get('interactive')),
            'tbt': self._extract_metric_ms(audits.get('total-blocking-time')),
            'cls': self._extract_cls(audits.get('cumulative-layout-shift')),
        }

        # Extract optimization opportunities
        opportunities = self._extract_opportunities(audits)

        # Extract CrUX (field) data if available
        crux_data = self._extract_crux_data(loading_experience)

        result = {
            'url': url,
            'strategy': self.strategy,
            'fetch_time': lighthouse.get('fetchTime'),

            # Lighthouse metadata for evidence
            'lighthouse_version': lighthouse.get('lighthouseVersion'),
            'user_agent': lighthouse.get('userAgent'),
            'requested_url': lighthouse.get('requestedUrl'),
            'final_url': lighthouse.get('finalUrl'),
            'run_warnings': lighthouse.get('runWarnings', []),

            # Lighthouse scores (0-100)
            'performance_score': scores['performance'],
            'accessibility_score': scores['accessibility'],
            'best_practices_score': scores['best_practices'],
            'seo_score': scores['seo'],
            'pwa_score': scores['pwa'],

            # Performance metrics (milliseconds)
            'fcp': metrics['fcp'],
            'lcp': metrics['lcp'],
            'si': metrics['si'],
            'tti': metrics['tti'],
            'tbt': metrics['tbt'],
            'cls': metrics['cls'],

            # Optimization opportunities
            'opportunities': opportunities,

            # CrUX (real user) data
            'crux_data': crux_data,
        }

        logger.info(f"[PSI] ✓ {url}: Performance={scores['performance']}, "
                   f"LCP={metrics['lcp']}ms, CLS={metrics['cls']}")

        return result

    def _extract_score(self, category: Optional[Dict]) -> Optional[float]:
        """Extract score from category (convert 0-1 to 0-100)"""
        if not category or 'score' not in category:
            return None
        score = category['score']
        if score is None:
            return None
        return round(score * 100, 1)

    def _extract_metric_ms(self, audit: Optional[Dict]) -> Optional[int]:
        """Extract metric value in milliseconds"""
        if not audit or 'numericValue' not in audit:
            return None
        return int(audit['numericValue'])

    def _extract_cls(self, audit: Optional[Dict]) -> Optional[float]:
        """Extract CLS score (already in correct scale)"""
        if not audit or 'numericValue' not in audit:
            return None
        return round(audit['numericValue'], 3)

    def _extract_opportunities(self, audits: Dict) -> List[Dict]:
        """
        Extract optimization opportunities from audits.

        Returns:
            List of opportunities with potential savings
        """
        opportunities = []

        # List of audit IDs that represent opportunities
        opportunity_audits = [
            'render-blocking-resources',
            'unused-css-rules',
            'unused-javascript',
            'modern-image-formats',
            'offscreen-images',
            'unminified-css',
            'unminified-javascript',
            'efficient-animated-content',
            'duplicated-javascript',
            'legacy-javascript',
            'total-byte-weight',
            'uses-long-cache-ttl',
            'uses-optimized-images',
            'uses-text-compression',
            'uses-responsive-images',
        ]

        for audit_id in opportunity_audits:
            audit = audits.get(audit_id)
            if not audit:
                continue

            # Only include opportunities with savings
            if audit.get('score') is not None and audit['score'] < 1:
                opportunity = {
                    'id': audit_id,
                    'title': audit.get('title', ''),
                    'description': audit.get('description', ''),
                    'score': audit.get('score'),
                    'savings_ms': int(audit.get('metricSavings', {}).get('LCP', 0) or 0),
                    'savings_bytes': int(audit.get('details', {}).get('overallSavingsBytes', 0) or 0),
                    'item_count': len(audit.get('details', {}).get('items', [])),
                }

                opportunities.append(opportunity)

        # Sort by time savings
        opportunities.sort(key=lambda x: x['savings_ms'], reverse=True)

        return opportunities

    def _extract_crux_data(self, loading_experience: Dict) -> Optional[Dict]:
        """
        Extract Chrome User Experience Report (CrUX) data.

        CrUX provides real-world data from actual Chrome users.
        Note: CrUX data represents a 28-day rolling window of real user measurements.
        """
        if not loading_experience or 'metrics' not in loading_experience:
            return None

        metrics = loading_experience.get('metrics', {})

        crux = {
            # CrUX metadata for evidence
            'origin_fallback': loading_experience.get('origin_fallback', False),
            'initial_url': loading_experience.get('initial_url'),
            # Note: CrUX uses a 28-day rolling window, data is typically 1-2 days old
            'collection_period': '28-day rolling window',
            'data_freshness': 'Real user data from last 28 days',
        }

        # Largest Contentful Paint
        if 'LARGEST_CONTENTFUL_PAINT_MS' in metrics:
            lcp = metrics['LARGEST_CONTENTFUL_PAINT_MS']
            crux['lcp'] = {
                'percentile': lcp.get('percentile'),
                'category': lcp.get('category'),  # FAST/AVERAGE/SLOW
            }

        # First Input Delay
        if 'FIRST_INPUT_DELAY_MS' in metrics:
            fid = metrics['FIRST_INPUT_DELAY_MS']
            crux['fid'] = {
                'percentile': fid.get('percentile'),
                'category': fid.get('category'),
            }

        # Cumulative Layout Shift
        if 'CUMULATIVE_LAYOUT_SHIFT_SCORE' in metrics:
            cls = metrics['CUMULATIVE_LAYOUT_SHIFT_SCORE']
            crux['cls'] = {
                'percentile': cls.get('percentile'),
                'category': cls.get('category'),
            }

        # Overall category
        crux['overall_category'] = loading_experience.get('overall_category')

        return crux if crux else None

    def get_stats(self) -> Dict[str, int]:
        """Get API usage statistics"""
        return {
            'total_requests': self.total_requests,
            'failed_requests': self.failed_requests,
            'success_rate': (
                round((self.total_requests - self.failed_requests) / self.total_requests * 100, 1)
                if self.total_requests > 0 else 0
            ),
            'requests_in_window': len(self.request_times),
        }
