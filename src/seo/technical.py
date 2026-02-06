"""Technical SEO analyzer for identifying issues."""

from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Tuple

from urllib.parse import urlparse, urlunparse

from seo.models import (
    PageMetadata,
    TechnicalIssues,
    EvidenceRecord,
    EvidenceCollection,
    ConfidenceLevel,
    EvidenceSourceType,
)
from seo.constants import (
    MAX_EVIDENCE_SAMPLES,
    REPORT_SAMPLE_LIMIT,
    SEVERITY_ESCALATION_IMAGES_THRESHOLD,
    SLOW_PAGE_CRITICAL_THRESHOLD_SECONDS,
    THIN_CONTENT_CRITICAL_THRESHOLD,
)


class TechnicalAnalyzer:
    """Analyzes technical SEO issues across crawled pages."""

    # Thresholds used for issue detection (documented for evidence)
    THRESHOLDS = {
        'meta_description_short': {'operator': '<', 'value': 120, 'unit': 'characters'},
        'meta_description_long': {'operator': '>', 'value': 160, 'unit': 'characters'},
        'load_time_slow': {'operator': '>', 'value': 3.0, 'unit': 'seconds'},
        'thin_content': {'operator': '<', 'value': 300, 'unit': 'words'},
    }

    def __init__(self):
        """Initialize the analyzer with evidence tracking."""
        self._evidence: Dict[str, EvidenceCollection] = {}

    def analyze(
        self, pages: Dict[str, PageMetadata]
    ) -> Tuple[TechnicalIssues, Dict[str, dict]]:
        """Analyze technical SEO issues across multiple pages.

        Args:
            pages: Dictionary mapping URLs to PageMetadata

        Returns:
            Tuple of (TechnicalIssues, evidence_dict) where evidence_dict maps
            issue types to their EvidenceCollection
        """
        issues = TechnicalIssues()
        self._evidence = {}  # Reset evidence for each analysis
        titles_seen = defaultdict(list)
        crawled_urls = set(pages.keys())
        linked_to_urls = set()
        possible_roots = set()

        base_domain = ""
        if pages:
            # Determine the base domain from the first URL to identify the site's root
            first_url = next(iter(pages))
            parsed_first_url = urlparse(first_url)
            base_domain = parsed_first_url.netloc
            # The root URL might be http://domain.com or http://domain.com/, we should find it
            site_root = urlunparse((parsed_first_url.scheme, base_domain, '', '', '', ''))
            # Handle both with and without trailing slash
            possible_roots = {site_root, site_root + '/'}
            
        for url, page in pages.items():
            self._check_title_issues(url, page, titles_seen, issues)
            self._check_meta_description_issues(url, page, issues)
            self._check_h1_issues(url, page, issues)
            self._check_image_issues(url, page, issues)
            self._check_performance_issues(url, page, issues)
            self._check_content_issues(url, page, issues)
            self._check_canonical_issues(url, page, issues)
            self._check_broken_links(url, page, crawled_urls, issues)
            
            # Aggregate all linked-to URLs
            for link in page.links:
                cleaned_link = link.split('#')[0]
                if urlparse(cleaned_link).netloc == base_domain:
                    linked_to_urls.add(cleaned_link)

        # Check for duplicate titles
        for title, urls in titles_seen.items():
            if len(urls) > 1:
                issues.duplicate_titles[title] = urls
        
        # Find and add orphan pages
        orphan_pages = crawled_urls - linked_to_urls
        # Exclude the root of the site from orphans
        for root_url in possible_roots:
            if root_url in orphan_pages:
                orphan_pages.remove(root_url)
        
        issues.orphan_pages = sorted(list(orphan_pages))

        # Add evidence for duplicate titles
        if issues.duplicate_titles:
            self._add_duplicate_evidence(issues.duplicate_titles)

        # Convert evidence to dict for serialization
        evidence_dict = {
            key: collection.to_dict()
            for key, collection in self._evidence.items()
        }

        return issues, evidence_dict

    def _add_evidence(
        self,
        issue_type: str,
        url: str,
        finding: str,
        evidence_string: str,
        measured_value: any = None,
        unit: str = None,
        threshold: dict = None,
        severity: str = 'warning',
    ) -> None:
        """Add an evidence record for an issue.

        Args:
            issue_type: Type of issue (e.g., 'missing_title', 'thin_content')
            url: URL where issue was found
            finding: Description of the finding
            evidence_string: The raw evidence data
            measured_value: The measured value that triggered the issue
            unit: Unit of measurement
            threshold: Threshold dict with operator, value, unit
            severity: Issue severity (critical, warning, info)
        """
        if issue_type not in self._evidence:
            self._evidence[issue_type] = EvidenceCollection(
                finding=issue_type,
                component_id='technical_seo',
            )

        record = EvidenceRecord(
            component_id='technical_seo',
            finding=finding,
            evidence_string=evidence_string,
            confidence=ConfidenceLevel.HIGH,  # Threshold-based checks are high confidence
            timestamp=datetime.now(),
            source='Threshold Check',
            source_type=EvidenceSourceType.CALCULATION,
            source_location=url,
            measured_value=measured_value,
            unit=unit,
            threshold=threshold,
            severity=severity,
        )
        self._evidence[issue_type].add_record(record)

    def _add_duplicate_evidence(self, duplicate_titles: Dict[str, List[str]]) -> None:
        """Add evidence for duplicate title findings.

        Args:
            duplicate_titles: Dict mapping title text to list of URLs
        """
        for title, urls in duplicate_titles.items():
            if 'duplicate_titles' not in self._evidence:
                self._evidence['duplicate_titles'] = EvidenceCollection(
                    finding='duplicate_titles',
                    component_id='technical_seo',
                )

            record = EvidenceRecord(
                component_id='technical_seo',
                finding='duplicate_title',
                evidence_string=title,
                confidence=ConfidenceLevel.HIGH,
                timestamp=datetime.now(),
                source='Pattern Match',
                source_type=EvidenceSourceType.PATTERN_MATCH,
                source_location=', '.join(urls[:MAX_EVIDENCE_SAMPLES]),  # First N URLs
                measured_value=len(urls),
                unit='pages',
                severity='warning' if len(urls) == 2 else 'critical',
            )
            self._evidence['duplicate_titles'].add_record(record)

    def _check_title_issues(
        self,
        url: str,
        page: PageMetadata,
        titles_seen: dict,
        issues: TechnicalIssues,
    ) -> None:
        """Check for title-related issues.

        Args:
            url: Page URL
            page: Page metadata
            titles_seen: Dictionary tracking seen titles
            issues: TechnicalIssues object to update
        """
        if not page.title:
            issues.missing_titles.append(url)
            self._add_evidence(
                issue_type='missing_titles',
                url=url,
                finding='missing_title',
                evidence_string='No title tag found',
                measured_value=None,
                threshold={'operator': '==', 'value': 0, 'unit': 'characters'},
                severity='critical',
            )
        else:
            titles_seen[page.title].append(url)

    def _check_meta_description_issues(
        self, url: str, page: PageMetadata, issues: TechnicalIssues
    ) -> None:
        """Check for meta description issues.

        Args:
            url: Page URL
            page: Page metadata
            issues: TechnicalIssues object to update
        """
        if not page.description:
            issues.missing_meta_descriptions.append(url)
            self._add_evidence(
                issue_type='missing_meta_descriptions',
                url=url,
                finding='missing_meta_description',
                evidence_string='No meta description found',
                measured_value=None,
                threshold={'operator': '==', 'value': 0, 'unit': 'characters'},
                severity='critical',
            )
        elif len(page.description) < 120:
            issues.short_meta_descriptions.append(
                (url, len(page.description))
            )
            self._add_evidence(
                issue_type='short_meta_descriptions',
                url=url,
                finding='short_meta_description',
                evidence_string=page.description[:200],  # Truncate for evidence
                measured_value=len(page.description),
                unit='characters',
                threshold=self.THRESHOLDS['meta_description_short'],
                severity='warning',
            )
        elif len(page.description) > 160:
            issues.long_meta_descriptions.append((url, len(page.description)))
            self._add_evidence(
                issue_type='long_meta_descriptions',
                url=url,
                finding='long_meta_description',
                evidence_string=page.description[:200],  # Truncate for evidence
                measured_value=len(page.description),
                unit='characters',
                threshold=self.THRESHOLDS['meta_description_long'],
                severity='warning',
            )

    def _check_h1_issues(
        self, url: str, page: PageMetadata, issues: TechnicalIssues
    ) -> None:
        """Check for H1 heading issues.

        Args:
            url: Page URL
            page: Page metadata
            issues: TechnicalIssues object to update
        """
        if not page.h1_tags:
            issues.missing_h1.append(url)
            self._add_evidence(
                issue_type='missing_h1',
                url=url,
                finding='missing_h1',
                evidence_string='No H1 tag found',
                measured_value=0,
                unit='h1_tags',
                threshold={'operator': '==', 'value': 0, 'unit': 'h1_tags'},
                severity='warning',
            )
        elif len(page.h1_tags) > 1:
            issues.multiple_h1.append((url, len(page.h1_tags)))
            self._add_evidence(
                issue_type='multiple_h1',
                url=url,
                finding='multiple_h1',
                evidence_string='; '.join(page.h1_tags[:5]),  # First 5 H1s
                measured_value=len(page.h1_tags),
                unit='h1_tags',
                threshold={'operator': '>', 'value': 1, 'unit': 'h1_tags'},
                severity='warning',
            )

    def _check_image_issues(
        self, url: str, page: PageMetadata, issues: TechnicalIssues
    ) -> None:
        """Check for image-related issues.

        Args:
            url: Page URL
            page: Page metadata
            issues: TechnicalIssues object to update
        """
        if page.images_without_alt > 0:
            issues.images_without_alt.append(
                (url, page.images_without_alt, page.total_images)
            )
            self._add_evidence(
                issue_type='images_without_alt',
                url=url,
                finding='images_without_alt',
                evidence_string=f'{page.images_without_alt} of {page.total_images} images missing alt text',
                measured_value=page.images_without_alt,
                unit='images',
                threshold={'operator': '>', 'value': 0, 'unit': 'images'},
                severity='warning' if page.images_without_alt < SEVERITY_ESCALATION_IMAGES_THRESHOLD else 'critical',
            )

    def _check_performance_issues(
        self, url: str, page: PageMetadata, issues: TechnicalIssues
    ) -> None:
        """Check for performance issues.

        Args:
            url: Page URL
            page: Page metadata
            issues: TechnicalIssues object to update
        """
        if page.load_time > 3.0:
            issues.slow_pages.append((url, page.load_time))
            self._add_evidence(
                issue_type='slow_pages',
                url=url,
                finding='slow_page',
                evidence_string=f'Page load time: {page.load_time:.2f} seconds',
                measured_value=round(page.load_time, 2),
                unit='seconds',
                threshold=self.THRESHOLDS['load_time_slow'],
                severity='critical' if page.load_time > SLOW_PAGE_CRITICAL_THRESHOLD_SECONDS else 'warning',
            )

    def _check_content_issues(
        self, url: str, page: PageMetadata, issues: TechnicalIssues
    ) -> None:
        """Check for content-related issues.

        Args:
            url: Page URL
            page: Page metadata
            issues: TechnicalIssues object to update
        """
        if page.word_count < 300:
            issues.thin_content.append((url, page.word_count))
            self._add_evidence(
                issue_type='thin_content',
                url=url,
                finding='thin_content',
                evidence_string=f'Page has {page.word_count} words',
                measured_value=page.word_count,
                unit='words',
                threshold=self.THRESHOLDS['thin_content'],
                severity='warning' if page.word_count > THIN_CONTENT_CRITICAL_THRESHOLD else 'critical',
            )

    def _check_canonical_issues(
        self, url: str, page: PageMetadata, issues: TechnicalIssues
    ) -> None:
        """Check for canonical URL issues.

        Args:
            url: Page URL
            page: Page metadata
            issues: TechnicalIssues object to update
        """
        if not page.canonical_url:
            issues.missing_canonical.append(url)
            self._add_evidence(
                issue_type='missing_canonical',
                url=url,
                finding='missing_canonical',
                evidence_string='No canonical URL specified',
                measured_value=None,
                threshold={'operator': '==', 'value': 'null', 'unit': 'url'},
                severity='warning',
            )

    def _check_broken_links(
        self, url: str, page: PageMetadata, crawled_urls: set, issues: TechnicalIssues
    ) -> None:
        """Check for broken internal links.

        Args:
            url: The source page URL
            page: The source page's metadata
            crawled_urls: A set of all successfully crawled URLs
            issues: TechnicalIssues object to update
        """
        page_domain = urlparse(url).netloc
        found_broken = []
        for link in page.links:
            # Basic cleanup: remove fragment identifiers
            cleaned_link = link.split('#')[0]
            if not cleaned_link:
                continue

            link_domain = urlparse(cleaned_link).netloc
            # Check only for internal links
            if link_domain == page_domain or not link_domain:
                if cleaned_link not in crawled_urls:
                    found_broken.append(cleaned_link)

        if found_broken:
            issues.broken_links.append((url, found_broken))
            # Add evidence for each broken link
            for broken_url in found_broken:
                self._add_evidence(
                    issue_type='broken_links',
                    url=url,
                    finding='broken_internal_link',
                    evidence_string=broken_url,
                    measured_value=broken_url,
                    unit='url',
                    severity='critical',
                )

    def format_issues_report(self, issues: TechnicalIssues) -> str:
        """Format technical issues into a readable report.

        Args:
            issues: TechnicalIssues object

        Returns:
            Formatted string report
        """
        report_lines = [
            "TECHNICAL SEO ISSUES SUMMARY",
            "=" * 60,
            "",
        ]

        if issues.missing_titles:
            report_lines.append(
                f"Missing Titles ({len(issues.missing_titles)}):"
            )
            for url in issues.missing_titles[:REPORT_SAMPLE_LIMIT]:
                report_lines.append(f"  • {url}")
            if len(issues.missing_titles) > REPORT_SAMPLE_LIMIT:
                report_lines.append(
                    f"  ... and {len(issues.missing_titles) - REPORT_SAMPLE_LIMIT} more"
                )
            report_lines.append("")

        if issues.duplicate_titles:
            report_lines.append(
                f"Duplicate Titles ({len(issues.duplicate_titles)}):"
            )
            for title, urls in list(issues.duplicate_titles.items())[:3]:
                report_lines.append(f'  Title: "{title}"')
                for url in urls[:3]:
                    report_lines.append(f"    - {url}")
            if len(issues.duplicate_titles) > 3:
                report_lines.append(
                    f"  ... and {len(issues.duplicate_titles) - 3} more"
                )
            report_lines.append("")

        if issues.missing_meta_descriptions:
            report_lines.append(
                f"Missing Meta Descriptions ({len(issues.missing_meta_descriptions)}):"
            )
            for url in issues.missing_meta_descriptions[:5]:
                report_lines.append(f"  • {url}")
            if len(issues.missing_meta_descriptions) > 5:
                report_lines.append(
                    f"  ... and {len(issues.missing_meta_descriptions) - 5} more"
                )
            report_lines.append("")
        
        if issues.broken_links:
            total_broken = sum(len(links) for _, links in issues.broken_links)
            report_lines.append(
                f"Broken Internal Links ({total_broken} total):"
            )
            for url, links in issues.broken_links[:5]:
                report_lines.append(
                    f"  • On page {url}:"
                )
                for broken in links[:3]:
                    report_lines.append(f"    - {broken}")
                if len(links) > 3:
                    report_lines.append(f"    ... and {len(links) - 3} more")
            if len(issues.broken_links) > 5:
                report_lines.append(
                    f"  ... and on {len(issues.broken_links) - 5} more pages"
                )
            report_lines.append("")
        
        if issues.orphan_pages:
            report_lines.append(
                f"Orphan Pages ({len(issues.orphan_pages)}):"
            )
            for url in issues.orphan_pages[:5]:
                report_lines.append(f"  • {url}")
            if len(issues.orphan_pages) > 5:
                report_lines.append(
                    f"  ... and {len(issues.orphan_pages) - 5} more"
                )
            report_lines.append("")

        if issues.short_meta_descriptions:
            report_lines.append(
                f"Short Meta Descriptions ({len(issues.short_meta_descriptions)}):"
            )
            for url, length in issues.short_meta_descriptions[:5]:
                report_lines.append(f"  • {url} ({length} chars)")
            if len(issues.short_meta_descriptions) > 5:
                report_lines.append(
                    f"  ... and {len(issues.short_meta_descriptions) - 5} more"
                )
            report_lines.append("")

        if issues.missing_h1:
            report_lines.append(f"Missing H1 Tags ({len(issues.missing_h1)}):")
            for url in issues.missing_h1[:5]:
                report_lines.append(f"  • {url}")
            if len(issues.missing_h1) > 5:
                report_lines.append(
                    f"  ... and {len(issues.missing_h1) - 5} more"
                )
            report_lines.append("")

        if issues.images_without_alt:
            report_lines.append(
                f"Images Without Alt Text ({len(issues.images_without_alt)}):"
            )
            for url, missing, total in issues.images_without_alt[:5]:
                report_lines.append(
                    f"  • {url} ({missing}/{total} images)"
                )
            if len(issues.images_without_alt) > 5:
                report_lines.append(
                    f"  ... and {len(issues.images_without_alt) - 5} more"
                )
            report_lines.append("")

        if issues.slow_pages:
            report_lines.append(f"Slow Pages ({len(issues.slow_pages)}):")
            for url, load_time in issues.slow_pages[:5]:
                report_lines.append(f"  • {url} ({load_time:.2f}s)")
            if len(issues.slow_pages) > 5:
                report_lines.append(
                    f"  ... and {len(issues.slow_pages) - 5} more"
                )
            report_lines.append("")

        if issues.thin_content:
            report_lines.append(
                f"Thin Content Pages ({len(issues.thin_content)}):"
            )
            for url, word_count in issues.thin_content[:5]:
                report_lines.append(f"  • {url} ({word_count} words)")
            if len(issues.thin_content) > 5:
                report_lines.append(
                    f"  ... and {len(issues.thin_content) - 5} more"
                )
            report_lines.append("")

        if issues.missing_canonical:
            report_lines.append(
                f"Missing Canonical URLs ({len(issues.missing_canonical)}):"
            )
            for url in issues.missing_canonical[:5]:
                report_lines.append(f"  • {url}")
            if len(issues.missing_canonical) > 5:
                report_lines.append(
                    f"  ... and {len(issues.missing_canonical) - 5} more"
                )
            report_lines.append("")

        return "\n".join(report_lines)
