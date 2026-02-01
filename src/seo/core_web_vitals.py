"""
Core Web Vitals Analyzer

Analyzes performance metrics critical for Google's page experience ranking factor:
- LCP (Largest Contentful Paint): Loading performance
- FID (First Input Delay): Interactivity (legacy)
- INP (Interaction to Next Paint): Interactivity (current)
- CLS (Cumulative Layout Shift): Visual stability
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from bs4 import BeautifulSoup
import re


@dataclass
class CoreWebVitalsScore:
    """Core Web Vitals metrics and scores."""

    # LCP - Largest Contentful Paint
    lcp_estimate: Optional[float] = None  # seconds
    lcp_status: str = "unknown"  # good/needs-improvement/poor/unknown
    lcp_elements: List[str] = None  # Elements that could be LCP candidates

    # INP - Interaction to Next Paint (replacing FID)
    inp_status: str = "unknown"
    blocking_scripts: List[str] = None  # Scripts that block interactivity

    # CLS - Cumulative Layout Shift
    cls_status: str = "unknown"
    cls_risk_elements: List[str] = None  # Elements without dimensions

    # General performance indicators
    render_blocking_resources: List[str] = None
    lazy_loading_opportunities: List[str] = None

    # Overall score
    overall_status: str = "unknown"  # good/needs-improvement/poor

    def __post_init__(self):
        """Initialize empty lists."""
        if self.lcp_elements is None:
            self.lcp_elements = []
        if self.blocking_scripts is None:
            self.blocking_scripts = []
        if self.cls_risk_elements is None:
            self.cls_risk_elements = []
        if self.render_blocking_resources is None:
            self.render_blocking_resources = []
        if self.lazy_loading_opportunities is None:
            self.lazy_loading_opportunities = []


class CoreWebVitalsAnalyzer:
    """Analyze Core Web Vitals indicators from HTML."""

    # Thresholds (Google's standards)
    LCP_GOOD = 2.5  # seconds
    LCP_POOR = 4.0
    INP_GOOD = 200  # milliseconds
    INP_POOR = 500
    CLS_GOOD = 0.1
    CLS_POOR = 0.25

    def analyze(self, soup: BeautifulSoup, url: str, response_time: float = None) -> CoreWebVitalsScore:
        """
        Analyze Core Web Vitals indicators from HTML.

        Note: Without a real browser, we can only estimate/detect indicators.
        For actual CWV scores, use Google PageSpeed Insights API or Chrome User Experience Report.
        """
        score = CoreWebVitalsScore()

        # Analyze LCP candidates
        self._analyze_lcp(soup, score, response_time)

        # Analyze INP/interactivity blockers
        self._analyze_inp(soup, score)

        # Analyze CLS risks
        self._analyze_cls(soup, score)

        # Find optimization opportunities
        self._find_optimizations(soup, score)

        # Calculate overall status
        self._calculate_overall_status(score)

        return score

    def _analyze_lcp(self, soup: BeautifulSoup, score: CoreWebVitalsScore, response_time: Optional[float]):
        """
        Analyze Largest Contentful Paint candidates.

        LCP elements are typically:
        - Large images above the fold
        - Hero images
        - Large text blocks
        - Video poster images
        """
        # Find large images (likely LCP candidates)
        images = soup.find_all('img')

        for img in images[:10]:  # Check first 10 images (likely above fold)
            src = img.get('src', '')
            alt = img.get('alt', 'unnamed')
            width = img.get('width')
            height = img.get('height')
            loading = img.get('loading', '')

            # Large images without dimensions are LCP risks
            if not width or not height:
                score.lcp_elements.append(f"Image without dimensions: {alt[:50]}")

            # Hero images (common LCP element)
            if any(cls in img.get('class', []) for cls in ['hero', 'banner', 'featured']):
                score.lcp_elements.append(f"Hero image: {alt[:50]}")

        # Find large text blocks (h1, large paragraphs)
        h1_tags = soup.find_all('h1')
        if h1_tags:
            for h1 in h1_tags[:2]:
                score.lcp_elements.append(f"H1 text: {h1.get_text()[:50]}")

        # Estimate LCP status based on response time and indicators
        if response_time:
            # Very rough estimate: response_time + rendering
            estimated_lcp = response_time + 0.5  # Add estimated render time
            score.lcp_estimate = estimated_lcp

            if estimated_lcp <= self.LCP_GOOD:
                score.lcp_status = "good"
            elif estimated_lcp <= self.LCP_POOR:
                score.lcp_status = "needs-improvement"
            else:
                score.lcp_status = "poor"
        else:
            # Check for LCP optimization indicators
            if len(score.lcp_elements) == 0:
                score.lcp_status = "good"
            elif len(score.lcp_elements) <= 2:
                score.lcp_status = "needs-improvement"
            else:
                score.lcp_status = "poor"

    def _analyze_inp(self, soup: BeautifulSoup, score: CoreWebVitalsScore):
        """
        Analyze Interaction to Next Paint risks.

        INP is affected by:
        - Blocking JavaScript
        - Heavy event handlers
        - Long tasks
        """
        # Find blocking scripts
        scripts = soup.find_all('script')

        for script in scripts:
            src = script.get('src', '')
            async_attr = script.get('async')
            defer_attr = script.get('defer')

            # Scripts without async/defer are blocking
            if src and not async_attr and not defer_attr:
                # External blocking script
                script_name = src.split('/')[-1][:50]
                score.blocking_scripts.append(f"Blocking script: {script_name}")
            elif not src and script.string and len(script.string) > 1000:
                # Large inline script
                score.blocking_scripts.append("Large inline script (>1KB)")

        # Estimate INP status
        blocking_count = len(score.blocking_scripts)
        if blocking_count == 0:
            score.inp_status = "good"
        elif blocking_count <= 3:
            score.inp_status = "needs-improvement"
        else:
            score.inp_status = "poor"

    def _analyze_cls(self, soup: BeautifulSoup, score: CoreWebVitalsScore):
        """
        Analyze Cumulative Layout Shift risks.

        CLS is caused by:
        - Images without dimensions
        - Ads/embeds without reserved space
        - Fonts causing FOIT/FOUT
        - Dynamic content injection
        """
        # Images without width/height
        images = soup.find_all('img')
        for img in images:
            src = img.get('src', '')
            alt = img.get('alt', 'unnamed')
            width = img.get('width')
            height = img.get('height')
            style = img.get('style', '')

            # Check if dimensions are missing (neither attributes nor CSS)
            has_dimensions = width and height
            has_css_dimensions = 'width' in style or 'height' in style

            if not has_dimensions and not has_css_dimensions:
                score.cls_risk_elements.append(f"Image without dimensions: {alt[:50]}")

        # Iframes without dimensions (ads, embeds)
        iframes = soup.find_all('iframe')
        for iframe in iframes:
            src = iframe.get('src', '')
            width = iframe.get('width')
            height = iframe.get('height')

            if not width or not height:
                score.cls_risk_elements.append(f"Iframe without dimensions: {src[:50]}")

        # Font loading without font-display
        styles = soup.find_all('style')
        for style in styles:
            if style.string and '@font-face' in style.string:
                if 'font-display' not in style.string:
                    score.cls_risk_elements.append("Font without font-display property")

        # Estimate CLS status
        cls_risk_count = len(score.cls_risk_elements)
        if cls_risk_count == 0:
            score.cls_status = "good"
        elif cls_risk_count <= 5:
            score.cls_status = "needs-improvement"
        else:
            score.cls_status = "poor"

    def _find_optimizations(self, soup: BeautifulSoup, score: CoreWebVitalsScore):
        """Find performance optimization opportunities."""

        # Render-blocking resources in <head>
        head = soup.find('head')
        if head:
            # CSS files in head (render-blocking)
            link_tags = head.find_all('link', rel='stylesheet')
            for link in link_tags:
                href = link.get('href', '')
                media = link.get('media', '')

                # Non-critical CSS should be async or media-query loaded
                if not media or media == 'all':
                    score.render_blocking_resources.append(f"Render-blocking CSS: {href[:50]}")

            # Sync scripts in head
            scripts = head.find_all('script', src=True)
            for script in scripts:
                if not script.get('async') and not script.get('defer'):
                    src = script.get('src', '')
                    score.render_blocking_resources.append(f"Render-blocking JS: {src[:50]}")

        # Images that could use lazy loading
        images = soup.find_all('img')
        for i, img in enumerate(images):
            loading = img.get('loading', '')

            # Images beyond the 3rd (likely below fold) should be lazy loaded
            if i >= 3 and loading != 'lazy':
                alt = img.get('alt', 'unnamed')
                score.lazy_loading_opportunities.append(f"Image #{i+1}: {alt[:50]}")

    def _calculate_overall_status(self, score: CoreWebVitalsScore):
        """Calculate overall Core Web Vitals status."""
        statuses = [score.lcp_status, score.inp_status, score.cls_status]

        # If any metric is poor, overall is poor
        if 'poor' in statuses:
            score.overall_status = 'poor'
        # If any metric needs improvement, overall needs improvement
        elif 'needs-improvement' in statuses:
            score.overall_status = 'needs-improvement'
        # If all metrics are good, overall is good
        elif all(s == 'good' for s in statuses):
            score.overall_status = 'good'
        else:
            score.overall_status = 'unknown'

    def get_recommendations(self, score: CoreWebVitalsScore) -> List[str]:
        """Generate actionable recommendations based on CWV analysis."""
        recommendations = []

        # LCP recommendations
        if score.lcp_status in ['needs-improvement', 'poor']:
            recommendations.append("Optimize Largest Contentful Paint (LCP):")
            recommendations.append("  - Add explicit width/height to hero images")
            recommendations.append("  - Use responsive images with srcset")
            recommendations.append("  - Preload critical images with <link rel='preload'>")
            recommendations.append("  - Consider using a CDN for faster image delivery")

        # INP recommendations
        if score.inp_status in ['needs-improvement', 'poor']:
            recommendations.append("Improve Interaction to Next Paint (INP):")
            recommendations.append("  - Add 'async' or 'defer' to script tags")
            recommendations.append("  - Split large JavaScript bundles")
            recommendations.append("  - Minimize main thread work")
            recommendations.append("  - Use web workers for heavy computations")

        # CLS recommendations
        if score.cls_status in ['needs-improvement', 'poor']:
            recommendations.append("Reduce Cumulative Layout Shift (CLS):")
            recommendations.append("  - Add explicit dimensions to all images and iframes")
            recommendations.append("  - Reserve space for ads and embeds")
            recommendations.append("  - Use font-display: swap for web fonts")
            recommendations.append("  - Avoid inserting content above existing content")

        # General optimizations
        if score.render_blocking_resources:
            recommendations.append(f"Remove {len(score.render_blocking_resources)} render-blocking resources")

        if score.lazy_loading_opportunities:
            recommendations.append(f"Add lazy loading to {len(score.lazy_loading_opportunities)} images")

        return recommendations
