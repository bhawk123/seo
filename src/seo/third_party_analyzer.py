"""Third-party resource analyzer for performance impact assessment.

Note: Per-domain byte size analysis requires individual resource sizes from
the crawler. Currently, only aggregate page.third_party_size_bytes is available.
When per-resource sizes become available, enable per-domain byte tracking.
"""

from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional, Set, Tuple

from seo.models import (
    PageMetadata,
    ThirdPartyAnalysis,
    ThirdPartyDomain,
    EvidenceRecord,
    EvidenceCollection,
    ConfidenceLevel,
    EvidenceSourceType,
)
from seo.config import AnalysisThresholds, default_thresholds


class ThirdPartyAnalyzer:
    """Analyzes third-party resource usage and performance impact."""

    # Default known domain categories (can be extended via constructor)
    DEFAULT_ANALYTICS_DOMAINS: Set[str] = {
        'google-analytics.com', 'googletagmanager.com', 'analytics.google.com',
        'hotjar.com', 'mixpanel.com', 'segment.com', 'amplitude.com',
        'heap.io', 'fullstory.com', 'mouseflow.com', 'clarity.ms',
        'plausible.io', 'matomo.org', 'piwik.pro'
    }

    DEFAULT_ADVERTISING_DOMAINS: Set[str] = {
        'doubleclick.net', 'googlesyndication.com', 'googleadservices.com',
        'facebook.com', 'fbcdn.net', 'adsrvr.org', 'criteo.com',
        'taboola.com', 'outbrain.com', 'amazon-adsystem.com',
        'adnxs.com', 'rubiconproject.com', 'pubmatic.com'
    }

    DEFAULT_CDN_DOMAINS: Set[str] = {
        'cloudflare.com', 'cdnjs.cloudflare.com', 'jsdelivr.net',
        'unpkg.com', 'bootstrapcdn.com', 'googleapis.com', 'gstatic.com',
        'akamaized.net', 'fastly.net', 'cloudfront.net', 'azureedge.net',
        'stackpath.com', 'imgix.net', 'twimg.com'
    }

    DEFAULT_SOCIAL_DOMAINS: Set[str] = {
        'twitter.com', 'facebook.com', 'linkedin.com', 'pinterest.com',
        'instagram.com', 'youtube.com', 'tiktok.com', 'reddit.com'
    }

    def __init__(
        self,
        thresholds: Optional[AnalysisThresholds] = None,
        analytics_domains: Optional[Set[str]] = None,
        advertising_domains: Optional[Set[str]] = None,
        cdn_domains: Optional[Set[str]] = None,
        social_domains: Optional[Set[str]] = None,
    ):
        """Initialize analyzer with configurable settings.

        Args:
            thresholds: Analysis thresholds configuration
            analytics_domains: Set of known analytics domains
            advertising_domains: Set of known advertising domains
            cdn_domains: Set of known CDN domains
            social_domains: Set of known social media domains
        """
        self.thresholds = thresholds or default_thresholds
        self.analytics_domains = analytics_domains or self.DEFAULT_ANALYTICS_DOMAINS
        self.advertising_domains = advertising_domains or self.DEFAULT_ADVERTISING_DOMAINS
        self.cdn_domains = cdn_domains or self.DEFAULT_CDN_DOMAINS
        self.social_domains = social_domains or self.DEFAULT_SOCIAL_DOMAINS
        self._evidence_collection: Optional[EvidenceCollection] = None

    @property
    def high_weight_percentage(self) -> float:
        """Percentage of page weight considered 'high' for third parties."""
        return self.thresholds.third_party_high_percentage

    @property
    def high_requests_threshold(self) -> int:
        """Number of requests per page considered 'high'."""
        return self.thresholds.third_party_high_requests

    def analyze(self, pages: Dict[str, PageMetadata]) -> Tuple[ThirdPartyAnalysis, Dict]:
        """Analyze third-party resource usage.

        Args:
            pages: Dictionary mapping URLs to PageMetadata

        Returns:
            Tuple of (ThirdPartyAnalysis, evidence_dict)
        """
        self._evidence_collection = EvidenceCollection(
            finding='third_party_analysis',
            component_id='third_party_analyzer',
        )

        if not pages:
            return ThirdPartyAnalysis(), self._evidence_collection.to_dict()

        analysis = ThirdPartyAnalysis(total_pages=len(pages))

        domain_stats: Dict[str, Dict] = defaultdict(lambda: {
            'request_count': 0,
            'pages': set()
        })

        total_site_bytes = 0
        page_third_party: List[Dict] = []

        for url, page in pages.items():
            total_site_bytes += page.total_page_weight_bytes

            if page.third_party_domains:
                analysis.pages_with_third_party += 1
                analysis.total_third_party_requests += page.third_party_request_count
                analysis.total_third_party_bytes += page.third_party_size_bytes

                page_third_party.append({
                    'url': url,
                    'request_count': page.third_party_request_count,
                    'bytes': page.third_party_size_bytes,
                    'kb': round(page.third_party_size_bytes / 1024, 1),
                    'domains': page.third_party_domains[:5]
                })

                # Track per-domain stats (request count only - see docstring)
                for domain in page.third_party_domains:
                    domain_stats[domain]['pages'].add(url)
                    domain_stats[domain]['request_count'] += 1

        # Calculate averages
        if analysis.pages_with_third_party > 0:
            analysis.avg_third_party_requests_per_page = round(
                analysis.total_third_party_requests / analysis.pages_with_third_party, 1
            )
            analysis.avg_third_party_bytes_per_page = int(
                analysis.total_third_party_bytes / analysis.pages_with_third_party
            )

        # Calculate third-party weight percentage
        if total_site_bytes > 0:
            analysis.third_party_weight_percentage = round(
                analysis.total_third_party_bytes / total_site_bytes * 100, 1
            )

        # Process domain stats
        domains_list: List[ThirdPartyDomain] = []
        for domain, stats in domain_stats.items():
            domains_list.append(ThirdPartyDomain(
                domain=domain,
                request_count=stats['request_count'],
                # Note: total_bytes is 0 because crawler doesn't provide per-domain sizes
                total_bytes=0,
                pages_present=len(stats['pages'])
            ))

        # Sort by request count
        domains_list.sort(key=lambda x: x.request_count, reverse=True)
        analysis.domains = domains_list

        analysis.top_by_requests = [
            {'domain': d.domain, 'requests': d.request_count, 'pages': d.pages_present}
            for d in domains_list[:10]
        ]

        # Categorize domains using improved parsing
        for d in domains_list:
            base_domain = self._extract_base_domain(d.domain)
            if self._matches_category(base_domain, d.domain, self.analytics_domains, 'analytics'):
                analysis.analytics_domains.append(d.domain)
            elif self._matches_category(base_domain, d.domain, self.advertising_domains, 'ads'):
                analysis.advertising_domains.append(d.domain)
            elif self._matches_category(base_domain, d.domain, self.cdn_domains, 'cdn'):
                analysis.cdn_domains.append(d.domain)
            elif self._matches_category(base_domain, d.domain, self.social_domains, None):
                analysis.social_domains.append(d.domain)
            else:
                analysis.other_domains.append(d.domain)

        # Pages with most third-party resources
        page_third_party.sort(key=lambda x: x['request_count'], reverse=True)
        analysis.heaviest_pages = page_third_party[:10]

        # Generate recommendations
        analysis.recommendations = self._generate_recommendations(analysis)

        # Add evidence for domain categories and impact
        self._add_category_evidence(analysis)
        self._add_high_impact_evidence(analysis)
        self._add_summary_evidence(analysis)

        return analysis, self._evidence_collection.to_dict()

    def _extract_base_domain(self, domain: str) -> str:
        """Extract base domain, handling common TLDs.

        This is a simplified implementation. For production use with
        international domains, consider using the 'tldextract' library.

        Args:
            domain: Full domain name

        Returns:
            Base domain (e.g., 'example.com' from 'sub.example.com')
        """
        # Common multi-part TLDs
        multi_part_tlds = {
            'co.uk', 'com.au', 'co.nz', 'co.jp', 'com.br', 'co.in',
            'org.uk', 'net.au', 'com.mx', 'co.za', 'com.sg'
        }

        parts = domain.lower().split('.')

        if len(parts) < 2:
            return domain

        # Check for multi-part TLD
        if len(parts) >= 3:
            potential_tld = '.'.join(parts[-2:])
            if potential_tld in multi_part_tlds:
                # Return domain + multi-part TLD
                if len(parts) >= 3:
                    return '.'.join(parts[-3:])

        # Standard TLD - return last two parts
        return '.'.join(parts[-2:])

    def _matches_category(
        self,
        base_domain: str,
        full_domain: str,
        category_domains: Set[str],
        keyword: Optional[str]
    ) -> bool:
        """Check if domain matches a category.

        Args:
            base_domain: Extracted base domain
            full_domain: Full domain string
            category_domains: Set of known domains in category
            keyword: Optional keyword to match in domain

        Returns:
            True if domain matches category
        """
        # Check if base domain is in category
        if base_domain in category_domains:
            return True

        # Check if any category domain is a suffix of full domain
        for cat_domain in category_domains:
            if full_domain.endswith(cat_domain) or full_domain.endswith('.' + cat_domain):
                return True

        # Check for keyword in domain
        if keyword and keyword in full_domain:
            return True

        return False

    def _generate_recommendations(self, analysis: ThirdPartyAnalysis) -> List[str]:
        """Generate recommendations based on third-party analysis."""
        recommendations = []

        if analysis.third_party_weight_percentage > self.high_weight_percentage:
            recommendations.append(
                f"Third-party resources account for {analysis.third_party_weight_percentage}% "
                f"of page weight (threshold: {self.high_weight_percentage}%). "
                "Consider self-hosting critical resources."
            )

        if analysis.avg_third_party_requests_per_page > self.high_requests_threshold:
            recommendations.append(
                f"Average of {analysis.avg_third_party_requests_per_page} third-party requests "
                f"per page (threshold: {self.high_requests_threshold}). "
                "Consolidate or defer non-critical requests."
            )

        if len(analysis.analytics_domains) > 2:
            recommendations.append(
                f"Multiple analytics tools detected ({len(analysis.analytics_domains)}). "
                "Consider consolidating to reduce overhead."
            )

        if len(analysis.advertising_domains) > 5:
            recommendations.append(
                f"{len(analysis.advertising_domains)} advertising domains detected. "
                "Use lazy loading for ad scripts to improve initial load."
            )

        return recommendations

    def _add_category_evidence(self, analysis: ThirdPartyAnalysis) -> None:
        """Add evidence for third-party domain categorization.

        Args:
            analysis: The analysis object
        """
        # Build category totals
        categories = {
            'analytics': {
                'domains': analysis.analytics_domains,
                'count': len(analysis.analytics_domains),
            },
            'ads': {
                'domains': analysis.advertising_domains,
                'count': len(analysis.advertising_domains),
            },
            'cdn': {
                'domains': analysis.cdn_domains,
                'count': len(analysis.cdn_domains),
            },
            'social': {
                'domains': analysis.social_domains,
                'count': len(analysis.social_domains),
            },
            'unknown': {
                'domains': analysis.other_domains[:10],  # First 10 for brevity
                'count': len(analysis.other_domains),
            },
        }

        record = EvidenceRecord(
            component_id='third_party_analyzer',
            finding='domain_categories',
            evidence_string=f'Analytics: {len(analysis.analytics_domains)}, Ads: {len(analysis.advertising_domains)}, CDN: {len(analysis.cdn_domains)}, Social: {len(analysis.social_domains)}',
            confidence=ConfidenceLevel.HIGH,
            timestamp=datetime.now(),
            source='Third-Party Domain Analysis',
            source_type=EvidenceSourceType.CALCULATION,
            source_location='aggregate',
            measured_value=categories,
            ai_generated=False,
            reasoning='Categorized third-party domains by purpose',
            input_summary={
                'known_analytics_domains': len(self.analytics_domains),
                'known_ad_domains': len(self.advertising_domains),
                'known_cdn_domains': len(self.cdn_domains),
                'known_social_domains': len(self.social_domains),
            },
        )
        self._evidence_collection.add_record(record)

        # Add evidence for unknown domains
        if analysis.other_domains:
            record = EvidenceRecord(
                component_id='third_party_analyzer',
                finding='unknown_domains',
                evidence_string=f'{len(analysis.other_domains)} unrecognized third-party domains',
                confidence=ConfidenceLevel.HIGH,
                timestamp=datetime.now(),
                source='Third-Party Domain Analysis',
                source_type=EvidenceSourceType.MEASUREMENT,
                source_location='aggregate',
                measured_value={
                    'category': 'unknown',
                    'count': len(analysis.other_domains),
                    'domains': analysis.other_domains[:10],
                },
                ai_generated=False,
                reasoning='Domains not in known category lists',
            )
            self._evidence_collection.add_record(record)

    def _add_high_impact_evidence(self, analysis: ThirdPartyAnalysis) -> None:
        """Add evidence for high-impact third-party usage.

        Args:
            analysis: The analysis object
        """
        # Check for high page weight percentage
        if analysis.third_party_weight_percentage > self.high_weight_percentage:
            record = EvidenceRecord(
                component_id='third_party_analyzer',
                finding='high_impact_weight',
                evidence_string=f'Third-party resources account for {analysis.third_party_weight_percentage}% of page weight',
                confidence=ConfidenceLevel.HIGH,
                timestamp=datetime.now(),
                source='Third-Party Performance Analysis',
                source_type=EvidenceSourceType.CALCULATION,
                source_location='aggregate',
                measured_value={
                    'percentage': analysis.third_party_weight_percentage,
                    'threshold': self.high_weight_percentage,
                    'total_bytes': analysis.total_third_party_bytes,
                },
                ai_generated=False,
                reasoning=f'Exceeds threshold of {self.high_weight_percentage}%',
                input_summary={
                    'recommendation': 'Consider self-hosting critical resources',
                },
            )
            self._evidence_collection.add_record(record)

        # Check for high request count
        if analysis.avg_third_party_requests_per_page > self.high_requests_threshold:
            record = EvidenceRecord(
                component_id='third_party_analyzer',
                finding='high_request_count',
                evidence_string=f'Average {analysis.avg_third_party_requests_per_page} third-party requests per page',
                confidence=ConfidenceLevel.HIGH,
                timestamp=datetime.now(),
                source='Third-Party Performance Analysis',
                source_type=EvidenceSourceType.CALCULATION,
                source_location='aggregate',
                measured_value={
                    'avg_requests': analysis.avg_third_party_requests_per_page,
                    'threshold': self.high_requests_threshold,
                    'total_requests': analysis.total_third_party_requests,
                },
                ai_generated=False,
                reasoning=f'Exceeds threshold of {self.high_requests_threshold} requests',
            )
            self._evidence_collection.add_record(record)

    def _add_summary_evidence(self, analysis: ThirdPartyAnalysis) -> None:
        """Add summary evidence for third-party analysis.

        Args:
            analysis: The completed analysis object
        """
        record = EvidenceRecord(
            component_id='third_party_analyzer',
            finding='third_party_summary',
            evidence_string=f'{len(analysis.domains)} domains, {analysis.total_third_party_requests} requests, {round(analysis.total_third_party_bytes / 1024, 1)}KB',
            confidence=ConfidenceLevel.HIGH,
            timestamp=datetime.now(),
            source='Third-Party Analysis',
            source_type=EvidenceSourceType.CALCULATION,
            source_location='aggregate',
            measured_value={
                'total_domains': len(analysis.domains),
                'total_requests': analysis.total_third_party_requests,
                'total_bytes': analysis.total_third_party_bytes,
                'total_kb': round(analysis.total_third_party_bytes / 1024, 1),
                'pages_with_third_party': analysis.pages_with_third_party,
                'third_party_weight_percentage': analysis.third_party_weight_percentage,
                'avg_requests_per_page': analysis.avg_third_party_requests_per_page,
                'avg_bytes_per_page': analysis.avg_third_party_bytes_per_page,
                'top_domains': analysis.top_by_requests[:5],
            },
            ai_generated=False,
            reasoning='Summary of all third-party resource usage',
            input_summary={
                'thresholds': {
                    'high_weight_percentage': self.high_weight_percentage,
                    'high_requests_threshold': self.high_requests_threshold,
                },
            },
        )
        self._evidence_collection.add_record(record)
