"""Technical SEO analyzer for identifying issues."""

from collections import defaultdict
from typing import Dict
from urllib.parse import urlparse, urlunparse

from seo.models import PageMetadata, TechnicalIssues


class TechnicalAnalyzer:
    """Analyzes technical SEO issues across crawled pages."""

    def analyze(
        self, pages: Dict[str, PageMetadata]
    ) -> TechnicalIssues:
        """Analyze technical SEO issues across multiple pages.

        Args:
            pages: Dictionary mapping URLs to PageMetadata

        Returns:
            TechnicalIssues object containing all found issues
        """
        issues = TechnicalIssues()
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

        return issues

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
        elif len(page.description) < 120:
            issues.short_meta_descriptions.append(
                (url, len(page.description))
            )
        elif len(page.description) > 160:
            issues.long_meta_descriptions.append((url, len(page.description)))

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
        elif len(page.h1_tags) > 1:
            issues.multiple_h1.append((url, len(page.h1_tags)))

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
            for url in issues.missing_titles[:5]:
                report_lines.append(f"  • {url}")
            if len(issues.missing_titles) > 5:
                report_lines.append(
                    f"  ... and {len(issues.missing_titles) - 5} more"
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
