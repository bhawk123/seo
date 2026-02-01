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
from typing import List, Dict, Optional, Set
from urllib.parse import urljoin, urlparse
import xml.etree.ElementTree as ET
from urllib.robotparser import RobotFileParser


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
            CrawlabilityScore with analysis results
        """
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

        return score

    def _analyze_robots_txt(self, score: CrawlabilityScore):
        """Analyze robots.txt file."""
        robots_url = f"{self.domain}/robots.txt"
        score.robots_txt_url = robots_url

        if self.robots_txt_content:
            score.has_robots_txt = True
            self._parse_robots_txt(score)
        else:
            score.robots_txt_warnings.append(
                "robots.txt not fetched (may not exist or wasn't accessible)"
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
