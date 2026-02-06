"""
Core Web Vitals Analyzer

Analyzes performance metrics critical for Google's page experience ranking factor:
- LCP (Largest Contentful Paint): Loading performance
- FID (First Input Delay): Interactivity (legacy)
- INP (Interaction to Next Paint): Interactivity (current)
- CLS (Cumulative Layout Shift): Visual stability
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple
from bs4 import BeautifulSoup
import re

from seo.models import (
    EvidenceRecord,
    EvidenceCollection,
    ConfidenceLevel,
    EvidenceSourceType,
)
from seo.constants import (
    LCP_GOOD_SECONDS,
    LCP_POOR_SECONDS,
    INP_GOOD_MS,
    INP_POOR_MS,
    CLS_GOOD_THRESHOLD,
    CLS_POOR_THRESHOLD,
    MAX_LCP_CANDIDATE_IMAGES,
    MAX_LCP_CANDIDATE_H1S,
    BASE_RENDER_TIME_ESTIMATE_SECONDS,
    BLOCKING_SCRIPTS_THRESHOLD,
    CLS_RISK_ELEMENTS_THRESHOLD,
    LAZY_LOAD_IMAGE_POSITION_THRESHOLD,
)


@dataclass
class CoreWebVitalsScore:
    """Core Web Vitals metrics and scores."""

    # LCP - Largest Contentful Paint
    lcp_estimate: Optional[float] = None  # seconds
    lcp_status: str = "unknown"  # good/needs-improvement/poor/unknown
    lcp_elements: List[str] = field(default_factory=list)  # Elements that could be LCP candidates

    # INP - Interaction to Next Paint (replacing FID)
    inp_status: str = "unknown"
    blocking_scripts: List[str] = field(default_factory=list)  # Scripts that block interactivity

    # CLS - Cumulative Layout Shift
    cls_status: str = "unknown"
    cls_risk_elements: List[str] = field(default_factory=list)  # Elements without dimensions

    # General performance indicators
    render_blocking_resources: List[str] = field(default_factory=list)
    lazy_loading_opportunities: List[str] = field(default_factory=list)

    # Overall score
    overall_status: str = "unknown"  # good/needs-improvement/poor

    # Evidence trail
    evidence: Dict[str, Any] = field(default_factory=dict)


class CoreWebVitalsAnalyzer:
    """Analyze Core Web Vitals indicators from HTML."""

    # Thresholds (Google's standards) - imported from constants
    LCP_GOOD = LCP_GOOD_SECONDS
    LCP_POOR = LCP_POOR_SECONDS
    INP_GOOD = INP_GOOD_MS
    INP_POOR = INP_POOR_MS
    CLS_GOOD = CLS_GOOD_THRESHOLD
    CLS_POOR = CLS_POOR_THRESHOLD

    # Evidence disclaimer for estimates
    ESTIMATE_DISCLAIMER = "Without a real browser, we can only estimate. Use PageSpeed Insights for actual measurements."

    def __init__(self):
        """Initialize analyzer with evidence tracking."""
        self._evidence_collection: Optional[EvidenceCollection] = None
        self._url: str = ""

    def analyze(self, soup: BeautifulSoup, url: str, response_time: float = None) -> CoreWebVitalsScore:
        """
        Analyze Core Web Vitals indicators from HTML.

        Note: Without a real browser, we can only estimate/detect indicators.
        For actual CWV scores, use Google PageSpeed Insights API or Chrome User Experience Report.

        Returns:
            CoreWebVitalsScore with evidence trail
        """
        self._url = url
        self._evidence_collection = EvidenceCollection(
            finding='core_web_vitals',
            component_id='cwv_analyzer',
        )

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

        # Attach evidence to score
        score.evidence = self._evidence_collection.to_dict()

        return score

    def _add_estimate_evidence(
        self,
        metric: str,
        estimated_value: Any,
        status: str,
        methodology: str,
        contributing_factors: Dict[str, Any],
    ) -> None:
        """Add evidence for an estimated metric.

        Args:
            metric: Name of the metric (lcp, inp, cls)
            estimated_value: The estimated value
            status: The status (good/needs-improvement/poor)
            methodology: How the estimate was calculated
            contributing_factors: Dict of factors that contributed to the estimate
        """
        record = EvidenceRecord(
            component_id='cwv_analyzer',
            finding=f'{metric}_estimate',
            evidence_string=f'{metric.upper()} estimate: {estimated_value}',
            confidence=ConfidenceLevel.ESTIMATE,
            timestamp=datetime.now(),
            source='Heuristic Analysis',
            source_type=EvidenceSourceType.HEURISTIC,
            source_location=self._url,
            measured_value=estimated_value,
            ai_generated=False,
            reasoning=methodology,
            input_summary={
                'is_estimate': True,
                'estimation_methodology': methodology,
                'contributing_factors': contributing_factors,
                'thresholds': {
                    'good': getattr(self, f'{metric.upper()}_GOOD', None),
                    'poor': getattr(self, f'{metric.upper()}_POOR', None),
                },
                'status': status,
                'disclaimer': self.ESTIMATE_DISCLAIMER,
            },
        )
        self._evidence_collection.add_record(record)

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

        for img in images[:MAX_LCP_CANDIDATE_IMAGES]:  # Check likely above fold images
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
            for h1 in h1_tags[:MAX_LCP_CANDIDATE_H1S]:
                score.lcp_elements.append(f"H1 text: {h1.get_text()[:50]}")

        # Estimate LCP status based on response time and indicators
        contributing_factors = {
            'lcp_candidate_elements': len(score.lcp_elements),
            'response_time': response_time,
        }

        if response_time:
            # Very rough estimate: response_time + rendering
            render_penalty = BASE_RENDER_TIME_ESTIMATE_SECONDS
            estimated_lcp = response_time + render_penalty
            score.lcp_estimate = estimated_lcp

            contributing_factors['render_penalty_seconds'] = render_penalty
            contributing_factors['formula'] = 'response_time + render_penalty'

            if estimated_lcp <= self.LCP_GOOD:
                score.lcp_status = "good"
            elif estimated_lcp <= self.LCP_POOR:
                score.lcp_status = "needs-improvement"
            else:
                score.lcp_status = "poor"

            # Add evidence for response-time based estimate
            self._add_estimate_evidence(
                metric='lcp',
                estimated_value=round(estimated_lcp, 2),
                status=score.lcp_status,
                methodology='Response time plus estimated render time',
                contributing_factors=contributing_factors,
            )
        else:
            # Check for LCP optimization indicators
            if len(score.lcp_elements) == 0:
                score.lcp_status = "good"
            elif len(score.lcp_elements) <= 2:
                score.lcp_status = "needs-improvement"
            else:
                score.lcp_status = "poor"

            # Add evidence for heuristic-based estimate
            self._add_estimate_evidence(
                metric='lcp',
                estimated_value=None,
                status=score.lcp_status,
                methodology='Heuristic based on LCP candidate element count',
                contributing_factors=contributing_factors,
            )

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
        elif blocking_count <= BLOCKING_SCRIPTS_THRESHOLD:
            score.inp_status = "needs-improvement"
        else:
            score.inp_status = "poor"

        # Add evidence for INP estimate
        contributing_factors = {
            'blocking_script_count': blocking_count,
            'blocking_scripts': score.blocking_scripts[:5],  # First 5 for brevity
            'thresholds': {
                'good': '0 blocking scripts',
                'needs_improvement': '1-3 blocking scripts',
                'poor': '> 3 blocking scripts',
            },
        }

        self._add_estimate_evidence(
            metric='inp',
            estimated_value=blocking_count,
            status=score.inp_status,
            methodology='Heuristic based on blocking script count',
            contributing_factors=contributing_factors,
        )

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
        elif cls_risk_count <= CLS_RISK_ELEMENTS_THRESHOLD:
            score.cls_status = "needs-improvement"
        else:
            score.cls_status = "poor"

        # Add evidence for CLS estimate
        contributing_factors = {
            'cls_risk_element_count': cls_risk_count,
            'risk_elements': score.cls_risk_elements[:5],  # First 5 for brevity
            'thresholds': {
                'good': '0 risk elements',
                'needs_improvement': '1-5 risk elements',
                'poor': '> 5 risk elements',
            },
        }

        self._add_estimate_evidence(
            metric='cls',
            estimated_value=cls_risk_count,
            status=score.cls_status,
            methodology='Heuristic based on elements missing dimensions',
            contributing_factors=contributing_factors,
        )

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

            # Images beyond the threshold (likely below fold) should be lazy loaded
            if i >= LAZY_LOAD_IMAGE_POSITION_THRESHOLD and loading != 'lazy':
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
