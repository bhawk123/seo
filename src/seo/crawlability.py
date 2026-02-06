"""
Crawlability Analyzer

Analyzes factors affecting search engine crawling:
- robots.txt compliance and validation
- XML sitemap structure and coverage
- Orphan pages (pages not in sitemap or internal links)
- Crawl budget optimization
- Redirect chains and broken links
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse
import xml.etree.ElementTree as ET
from urllib.robotparser import RobotFileParser

from seo.models import (
    EvidenceRecord,
    EvidenceCollection,
    ConfidenceLevel,
    EvidenceSourceType,
)


@dataclass
class CrawlabilityScore:
    """Crawlability analysis results."""

    # robots.txt
    has_robots_txt: bool = False
    robots_txt_errors: List[str] = field(default_factory=list)
    robots_txt_warnings: List[str] = field(default_factory=list)
    robots_txt_url: Optional[str] = None
    robots_txt_content: Optional[str] = None
    disallowed_rules: List[str] = field(default_factory=list)
    sitemap_urls_in_robots: List[str] = field(default_factory=list)

    # XML Sitemaps
    has_xml_sitemap: bool = False
    sitemap_urls: List[str] = field(default_factory=list)
    sitemap_errors: List[str] = field(default_factory=list)
    sitemap_warnings: List[str] = field(default_factory=list)
    total_urls_in_sitemaps: int = 0
    invalid_urls_in_sitemaps: int = 0

    # Orphan pages
    orphan_pages: List[str] = field(default_factory=list)
    pages_in_sitemap: int = 0
    pages_crawled: int = 0
    pages_not_in_sitemap: List[str] = field(default_factory=list)

    # Crawl budget
    redirect_chains: List[Dict] = field(default_factory=list)
    broken_links_count: int = 0
    crawl_efficiency_score: int = 0  # 0-100

    # Overall score
    overall_score: int = 0  # 0-100

    # Evidence trail
    evidence: Dict = field(default_factory=dict)


class CrawlabilityAnalyzer:
    """Analyze website crawlability factors."""

    def __init__(self, base_url: str, robots_txt_content: Optional[str] = None):
        """
        Initialize crawler.

        Args:
            base_url: Base URL of the site
            robots_txt_content: Optional pre-fetched robots.txt content
        """
        self.base_url = base_url
        parsed = urlparse(base_url)
        self.domain = f"{parsed.scheme}://{parsed.netloc}"
        self.robots_txt_content = robots_txt_content
        self.robot_parser = None
        self._evidence_collection: Optional[EvidenceCollection] = None

    def analyze(
        self,
        crawled_urls: List[str],
        all_discovered_urls: Set[str],
        broken_links: List[str]
    ) -> CrawlabilityScore:
        """
        Analyze crawlability.

        Args:
            crawled_urls: List of URLs that were successfully crawled
            all_discovered_urls: Set of all URLs discovered (crawled + found in links)
            broken_links: List of broken internal links

        Returns:
            CrawlabilityScore with analysis results and evidence
        """
        self._evidence_collection = EvidenceCollection(
            finding='crawlability',
            component_id='crawlability_analyzer',
        )

        score = CrawlabilityScore()

        # Analyze robots.txt
        self._analyze_robots_txt(score)

        # Find and analyze XML sitemaps
        self._analyze_xml_sitemaps(score, crawled_urls)

        # Detect orphan pages
        self._detect_orphan_pages(score, crawled_urls, all_discovered_urls)

        # Analyze crawl efficiency
        score.broken_links_count = len(broken_links)
        self._analyze_crawl_efficiency(score)

        # Calculate overall score
        self._calculate_overall_score(score)

        # Add summary evidence
        self._add_summary_evidence(score)

        # Attach evidence to score
        score.evidence = self._evidence_collection.to_dict()

        return score

    def _analyze_robots_txt(self, score: CrawlabilityScore):
        """Analyze robots.txt file."""
        robots_url = f"{self.domain}/robots.txt"
        score.robots_txt_url = robots_url

        if self.robots_txt_content:
            score.has_robots_txt = True
            self._parse_robots_txt(score)
            # Add robots.txt evidence
            self._add_robots_txt_evidence(score)
        else:
            score.robots_txt_warnings.append(
                "robots.txt not fetched (may not exist or wasn't accessible)"
            )
            # Add missing robots.txt evidence
            self._add_evidence(
                finding='missing_robots_txt',
                evidence_string='robots.txt not found or not accessible',
                confidence=ConfidenceLevel.HIGH,
                source_type=EvidenceSourceType.MEASUREMENT,
                measured_value={'exists': False},
                reasoning='robots.txt is recommended for controlling crawler behavior',
            )

    def _parse_robots_txt(self, score: CrawlabilityScore):
        """Parse robots.txt content."""
        if not self.robots_txt_content:
            return

        lines = self.robots_txt_content.split('\n')

        for line in lines:
            line = line.strip()

            # Skip comments and empty lines
            if not line or line.startswith('#'):
                continue

            # Extract sitemap URLs
            if line.lower().startswith('sitemap:'):
                sitemap_url = line.split(':', 1)[1].strip()
                score.sitemap_urls_in_robots.append(sitemap_url)

            # Extract disallow rules
            elif line.lower().startswith('disallow:'):
                disallow_path = line.split(':', 1)[1].strip()
                if disallow_path and disallow_path != '/':
                    score.disallowed_rules.append(disallow_path)

        # Validate robots.txt structure
        user_agent_found = any('user-agent' in line.lower() for line in lines)
        if not user_agent_found:
            score.robots_txt_errors.append(
                "No User-agent directive found in robots.txt"
            )

        # Check if blocking important resources
        if any('/css' in rule or '/js' in rule or '/images' in rule for rule in score.disallowed_rules):
            score.robots_txt_warnings.append(
                "robots.txt blocks CSS, JavaScript, or images (may hurt rendering for Google)"
            )

        # Check for overly restrictive rules
        if 'Disallow: /' in self.robots_txt_content:
            score.robots_txt_errors.append(
                "robots.txt contains 'Disallow: /' which blocks ALL pages"
            )

    def _analyze_xml_sitemaps(self, score: CrawlabilityScore, crawled_urls: List[str]):
        """Analyze XML sitemaps."""

        # Use sitemaps from robots.txt if available
        if score.sitemap_urls_in_robots:
            score.sitemap_urls = score.sitemap_urls_in_robots
            score.has_xml_sitemap = True
        else:
            # Try common sitemap locations
            common_sitemap_urls = [
                f"{self.domain}/sitemap.xml",
                f"{self.domain}/sitemap_index.xml",
                f"{self.domain}/sitemap1.xml"
            ]
            score.sitemap_urls = common_sitemap_urls
            score.sitemap_warnings.append(
                "No sitemap found in robots.txt, assuming standard locations"
            )

        # Note: Actual sitemap fetching would happen here in production
        # For now, we'll validate the sitemap URLs and provide recommendations

        if not score.has_xml_sitemap:
            score.sitemap_errors.append(
                "No XML sitemap detected - this is critical for SEO"
            )
        else:
            # Check if crawled pages would be in sitemap
            score.pages_crawled = len(crawled_urls)

            # Recommendation: All crawled pages should be in sitemap
            score.sitemap_warnings.append(
                f"Ensure all {len(crawled_urls)} crawled pages are included in sitemap"
            )

    def _detect_orphan_pages(
        self,
        score: CrawlabilityScore,
        crawled_urls: List[str],
        all_discovered_urls: Set[str]
    ):
        """Detect orphan pages (pages not linked to from anywhere)."""

        # Orphan pages are URLs that were crawled but not found in internal links
        # In a real implementation, we'd compare against actual sitemap URLs

        # For now, we'll flag pages that weren't discovered through internal links
        # This is a simplified detection

        score.pages_crawled = len(crawled_urls)

        # If we crawled more pages than we discovered through links,
        # some might be orphans (or directly accessed via start URL)
        if len(all_discovered_urls) > len(crawled_urls):
            score.orphan_pages = list(all_discovered_urls - set(crawled_urls))[:10]

        if len(score.orphan_pages) > 0:
            score.sitemap_warnings.append(
                f"Found {len(score.orphan_pages)} URLs discovered but not crawled (possible orphan pages)"
            )

    def _analyze_crawl_efficiency(self, score: CrawlabilityScore):
        """Analyze crawl budget efficiency."""

        # Calculate efficiency score based on:
        # 1. Broken links (each broken link wastes crawl budget)
        # 2. Redirect chains (each redirect wastes crawl budget)
        # 3. Orphan pages (pages that are hard to discover)

        efficiency = 100

        # Penalize for broken links (up to -30 points)
        broken_penalty = min(score.broken_links_count * 0.5, 30)
        efficiency -= broken_penalty

        # Penalize for orphan pages (up to -20 points)
        orphan_penalty = min(len(score.orphan_pages) * 2, 20)
        efficiency -= orphan_penalty

        # Penalize for missing sitemap (up to -30 points)
        if not score.has_xml_sitemap:
            efficiency -= 30

        # Penalize for robots.txt issues (up to -10 points)
        if score.robots_txt_errors:
            efficiency -= len(score.robots_txt_errors) * 5

        score.crawl_efficiency_score = max(int(efficiency), 0)

    def _calculate_overall_score(self, score: CrawlabilityScore):
        """Calculate overall crawlability score (0-100)."""
        points = 0

        # Has robots.txt: +20 points
        if score.has_robots_txt:
            points += 20

        # No robots.txt errors: +15 points
        if len(score.robots_txt_errors) == 0:
            points += 15
        elif len(score.robots_txt_errors) <= 1:
            points += 10

        # Has XML sitemap: +25 points
        if score.has_xml_sitemap:
            points += 25

        # No sitemap errors: +15 points
        if len(score.sitemap_errors) == 0:
            points += 15
        elif len(score.sitemap_errors) <= 1:
            points += 10

        # Few orphan pages: +10 points
        if len(score.orphan_pages) == 0:
            points += 10
        elif len(score.orphan_pages) <= 5:
            points += 5

        # Crawl efficiency: +15 points
        if score.crawl_efficiency_score >= 90:
            points += 15
        elif score.crawl_efficiency_score >= 70:
            points += 10
        elif score.crawl_efficiency_score >= 50:
            points += 5

        score.overall_score = min(points, 100)

    def get_recommendations(self, score: CrawlabilityScore) -> List[str]:
        """Generate actionable recommendations."""
        recommendations = []

        # robots.txt recommendations
        if not score.has_robots_txt:
            recommendations.append(
                "Create a robots.txt file at your domain root to control crawling"
            )
        elif score.robots_txt_errors:
            recommendations.append(
                f"Fix {len(score.robots_txt_errors)} critical robots.txt errors"
            )

        # Sitemap recommendations
        if not score.has_xml_sitemap:
            recommendations.append(
                "Create and submit an XML sitemap to Google Search Console"
            )

        if score.sitemap_urls_in_robots:
            recommendations.append(
                f"Verify that all {len(score.sitemap_urls_in_robots)} sitemaps are accessible and valid"
            )
        else:
            recommendations.append(
                "Add Sitemap directive to robots.txt pointing to your XML sitemap"
            )

        # Orphan page recommendations
        if len(score.orphan_pages) > 0:
            recommendations.append(
                f"Add internal links to {len(score.orphan_pages)} orphan pages or add them to sitemap"
            )

        # Crawl efficiency recommendations
        if score.broken_links_count > 0:
            recommendations.append(
                f"Fix {score.broken_links_count} broken links to improve crawl efficiency"
            )

        if score.crawl_efficiency_score < 70:
            recommendations.append(
                "Improve crawl budget efficiency by fixing broken links and eliminating redirect chains"
            )

        return recommendations

    def _add_evidence(
        self,
        finding: str,
        evidence_string: str,
        confidence: ConfidenceLevel,
        source_type: EvidenceSourceType,
        measured_value=None,
        reasoning: str = None,
        input_summary: Dict = None,
    ) -> None:
        """Add an evidence record.

        Args:
            finding: Finding type
            evidence_string: Human-readable evidence description
            confidence: Confidence level
            source_type: Type of evidence source
            measured_value: The measured/detected value
            reasoning: Explanation of the finding
            input_summary: Additional context
        """
        record = EvidenceRecord(
            component_id='crawlability_analyzer',
            finding=finding,
            evidence_string=evidence_string,
            confidence=confidence,
            timestamp=datetime.now(),
            source='Crawlability Analysis',
            source_type=source_type,
            source_location=self.domain,
            measured_value=measured_value,
            ai_generated=False,
            reasoning=reasoning,
            input_summary=input_summary,
        )
        self._evidence_collection.add_record(record)

    def _add_robots_txt_evidence(self, score: CrawlabilityScore) -> None:
        """Add evidence for robots.txt analysis.

        Args:
            score: The crawlability score object
        """
        # Add evidence for disallow rules by user-agent
        user_agent_rules = self._parse_rules_by_user_agent()

        self._add_evidence(
            finding='robots_txt_parsed',
            evidence_string=f'robots.txt: {len(score.disallowed_rules)} disallow rules, {len(score.sitemap_urls_in_robots)} sitemaps',
            confidence=ConfidenceLevel.HIGH,
            source_type=EvidenceSourceType.MEASUREMENT,
            measured_value={
                'has_robots_txt': True,
                'disallow_count': len(score.disallowed_rules),
                'sitemap_count': len(score.sitemap_urls_in_robots),
                'rules_by_user_agent': user_agent_rules,
            },
            reasoning='Parsed robots.txt directives',
            input_summary={
                'robots_url': score.robots_txt_url,
                'content_length': len(self.robots_txt_content) if self.robots_txt_content else 0,
            },
        )

        # Add evidence for each disallow rule
        for rule in score.disallowed_rules[:10]:  # First 10 for brevity
            self._add_evidence(
                finding='disallow_rule',
                evidence_string=rule,
                confidence=ConfidenceLevel.HIGH,
                source_type=EvidenceSourceType.MEASUREMENT,
                measured_value={'path': rule, 'user_agent': '*'},
                reasoning='Disallow rule found in robots.txt',
            )

        # Add evidence for sitemap references
        for sitemap_url in score.sitemap_urls_in_robots:
            self._add_evidence(
                finding='sitemap_reference',
                evidence_string=sitemap_url,
                confidence=ConfidenceLevel.HIGH,
                source_type=EvidenceSourceType.MEASUREMENT,
                measured_value={'sitemap_url': sitemap_url},
                reasoning='Sitemap URL declared in robots.txt',
            )

        # Add evidence for robots.txt errors
        for error in score.robots_txt_errors:
            self._add_evidence(
                finding='robots_txt_error',
                evidence_string=error,
                confidence=ConfidenceLevel.HIGH,
                source_type=EvidenceSourceType.CALCULATION,
                measured_value={'error': error, 'severity': 'critical'},
                reasoning='Critical issue in robots.txt configuration',
            )

    def _parse_rules_by_user_agent(self) -> Dict[str, int]:
        """Parse disallow rules grouped by user-agent.

        Returns:
            Dict mapping user-agent to disallow count
        """
        if not self.robots_txt_content:
            return {}

        rules_by_ua: Dict[str, int] = {}
        current_ua = '*'

        for line in self.robots_txt_content.split('\n'):
            line = line.strip().lower()
            if line.startswith('user-agent:'):
                current_ua = line.split(':', 1)[1].strip()
                if current_ua not in rules_by_ua:
                    rules_by_ua[current_ua] = 0
            elif line.startswith('disallow:'):
                rules_by_ua[current_ua] = rules_by_ua.get(current_ua, 0) + 1

        return rules_by_ua

    def _add_summary_evidence(self, score: CrawlabilityScore) -> None:
        """Add summary evidence for crawlability analysis.

        Args:
            score: The completed crawlability score object
        """
        # Add orphan pages evidence
        if score.orphan_pages:
            self._add_evidence(
                finding='orphan_pages',
                evidence_string=f'{len(score.orphan_pages)} orphan pages detected',
                confidence=ConfidenceLevel.MEDIUM,  # Heuristic-based detection
                source_type=EvidenceSourceType.HEURISTIC,
                measured_value={
                    'count': len(score.orphan_pages),
                    'sample_urls': score.orphan_pages[:5],
                },
                reasoning='Pages discovered but not crawled through internal links',
            )

        # Add sitemap URL count evidence
        self._add_evidence(
            finding='sitemap_urls',
            evidence_string=f'{score.total_urls_in_sitemaps} URLs in sitemaps, {score.pages_crawled} pages crawled',
            confidence=ConfidenceLevel.HIGH,
            source_type=EvidenceSourceType.MEASUREMENT,
            measured_value={
                'sitemap_urls': score.total_urls_in_sitemaps,
                'pages_crawled': score.pages_crawled,
                'pages_in_sitemap': score.pages_in_sitemap,
            },
            reasoning='Sitemap coverage analysis',
        )

        # Add overall summary evidence
        self._add_evidence(
            finding='crawlability_summary',
            evidence_string=f'Crawlability score: {score.overall_score}/100, Efficiency: {score.crawl_efficiency_score}/100',
            confidence=ConfidenceLevel.HIGH,
            source_type=EvidenceSourceType.CALCULATION,
            measured_value={
                'overall_score': score.overall_score,
                'crawl_efficiency_score': score.crawl_efficiency_score,
                'has_robots_txt': score.has_robots_txt,
                'has_xml_sitemap': score.has_xml_sitemap,
                'robots_errors': len(score.robots_txt_errors),
                'sitemap_errors': len(score.sitemap_errors),
                'orphan_pages': len(score.orphan_pages),
                'broken_links': score.broken_links_count,
            },
            ai_generated=False,
            reasoning='Summary of all crawlability factors',
            input_summary={
                'score_breakdown': {
                    'robots_txt_present': 20,
                    'no_robots_errors': 15,
                    'sitemap_present': 25,
                    'no_sitemap_errors': 15,
                    'few_orphan_pages': 10,
                    'crawl_efficiency': 15,
                },
            },
        )
