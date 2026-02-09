"""HTML report generator using Jinja2 templates."""

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
from jinja2 import Environment, FileSystemLoader

from seo.models import TechnicalIssues, PageMetadata
from seo.resource_analyzer import ResourceAnalyzer
from seo.console_analyzer import ConsoleErrorAnalyzer
from seo.social_analyzer import SocialMetaAnalyzer
from seo.redirect_analyzer import RedirectAnalyzer
from seo.third_party_analyzer import ThirdPartyAnalyzer
from seo.lab_field_analyzer import LabFieldAnalyzer
from seo.image_analyzer import ImageAnalyzer


class ReportGenerator:
    """Generates professional HTML reports from crawl results.

    Enhanced with challenge/CAPTCHA detection metrics per STORY-INFRA-006.
    """
    """Generates professional HTML reports from crawl results."""

    # Pattern definitions with remediation steps
    PATTERNS = {
        "missing_meta_descriptions": {
            "title": "Missing Meta Descriptions",
            "priority": "critical",
            "description": "Meta descriptions are critical for click-through rates from search results. Pages without them may show random content snippets instead.",
            "remediation": [
                "Review each page and write unique 120-160 character descriptions",
                "Include target keywords naturally in the description",
                "Make descriptions compelling to encourage clicks",
                "Avoid duplicating descriptions across pages",
                "Test descriptions in SERP preview tools"
            ]
        },
        "short_meta_descriptions": {
            "title": "Meta Descriptions Too Short",
            "priority": "medium",
            "description": "Short meta descriptions (<120 characters) don't fully utilize available space in search results, potentially reducing click-through rates.",
            "remediation": [
                "Expand descriptions to 120-160 characters",
                "Add more compelling value propositions",
                "Include relevant keywords naturally",
                "Ensure descriptions are complete sentences"
            ]
        },
        "long_meta_descriptions": {
            "title": "Meta Descriptions Too Long",
            "priority": "medium",
            "description": "Meta descriptions over 160 characters get truncated in search results, cutting off important information.",
            "remediation": [
                "Trim descriptions to 120-160 characters",
                "Move the most important information to the beginning",
                "Ensure the description is complete before the cutoff",
                "Test in SERP preview tools to verify display"
            ]
        },
        "missing_titles": {
            "title": "Missing Page Titles",
            "priority": "critical",
            "description": "Title tags are one of the most important on-page SEO factors. Missing titles severely impact search visibility.",
            "remediation": [
                "Add unique, descriptive titles to all pages",
                "Keep titles between 50-60 characters",
                "Include primary keywords near the beginning",
                "Follow pattern: Primary Keyword - Secondary Keyword | Brand",
                "Make titles compelling for users"
            ]
        },
        "duplicate_titles": {
            "title": "Duplicate Title Tags",
            "priority": "high",
            "description": "Multiple pages with identical titles confuse search engines and may result in lower rankings for all affected pages.",
            "remediation": [
                "Create unique titles for each page",
                "Differentiate by including page-specific keywords",
                "Use page hierarchy in titles (e.g., Category - Subcategory)",
                "Implement canonical tags where appropriate",
                "Check for pagination issues"
            ]
        },
        "missing_h1": {
            "title": "Missing H1 Tags",
            "priority": "high",
            "description": "H1 tags provide important context about page content. Missing H1s can confuse both users and search engines.",
            "remediation": [
                "Add a single, unique H1 tag to each page",
                "Include primary target keyword in H1",
                "Make H1 descriptive of page content",
                "Ensure H1 is visually prominent for users",
                "Don't duplicate H1 content with title tag exactly"
            ]
        },
        "multiple_h1": {
            "title": "Multiple H1 Tags",
            "priority": "medium",
            "description": "Pages with multiple H1 tags dilute the primary topic signal. Best practice is one H1 per page.",
            "remediation": [
                "Identify the primary H1 for each page",
                "Change secondary H1s to H2 or H3 tags",
                "Ensure heading hierarchy is logical",
                "Verify changes don't break visual styling",
                "Update CSS if needed to maintain appearance"
            ]
        },
        "images_without_alt": {
            "title": "Images Missing Alt Text",
            "priority": "high",
            "description": "Alt text is essential for accessibility and helps search engines understand image content. Missing alt text hurts both users and SEO.",
            "remediation": [
                "Add descriptive alt text to all content images",
                "Include relevant keywords naturally",
                "Describe what's in the image, not just keywords",
                "Use empty alt=\"\" for purely decorative images",
                "Keep alt text under 125 characters"
            ]
        },
        "slow_pages": {
            "title": "Slow Page Load Times",
            "priority": "critical",
            "description": "Pages loading slower than 3 seconds see significantly higher bounce rates and lower rankings. Core Web Vitals are now a ranking factor.",
            "remediation": [
                "Optimize and compress all images (use WebP format)",
                "Minify CSS, JavaScript, and HTML",
                "Enable browser caching and gzip compression",
                "Use a CDN for static assets",
                "Implement lazy loading for images below the fold",
                "Remove unused CSS and JavaScript",
                "Consider using a faster hosting provider"
            ]
        },
        "thin_content": {
            "title": "Thin Content Pages",
            "priority": "medium",
            "description": "Pages with less than 300 words may be seen as low-quality by search engines. Thin content rarely ranks well.",
            "remediation": [
                "Expand content to at least 300-500 words minimum",
                "Add unique, valuable information users want",
                "Include relevant keywords naturally throughout",
                "Add supporting images, videos, or infographics",
                "Consider consolidating very thin pages",
                "Use noindex if page must remain thin"
            ]
        },
        "missing_canonical": {
            "title": "Missing Canonical URLs",
            "priority": "high",
            "description": "Canonical tags prevent duplicate content issues by telling search engines which version of a page is the original.",
            "remediation": [
                "Add self-referencing canonical tags to all pages",
                "Point duplicate content to canonical version",
                "Ensure canonical URLs are absolute, not relative",
                "Verify canonical chain doesn't exceed 2 hops",
                "Test with Google Search Console"
            ]
        },
        "missing_viewport": {
            "title": "Missing Viewport Meta Tag",
            "priority": "high",
            "description": "Viewport meta tags are essential for mobile-friendly pages. Missing viewport tags result in poor mobile experience.",
            "remediation": [
                "Add viewport meta tag to all pages",
                "Use standard viewport: width=device-width, initial-scale=1",
                "Test mobile rendering after adding",
                "Verify no horizontal scrolling on mobile",
                "Check mobile usability in Google Search Console"
            ]
        },
        "missing_lang": {
            "title": "Missing Language Declaration",
            "priority": "medium",
            "description": "Language attributes help search engines and assistive technologies understand page language.",
            "remediation": [
                "Add lang attribute to HTML tag",
                "Use proper language codes (en, en-US, es, etc.)",
                "Match language to actual page content",
                "Add hreflang for multi-language sites",
                "Verify with W3C validator"
            ]
        },
        "non_https": {
            "title": "Non-HTTPS Pages",
            "priority": "critical",
            "description": "HTTP pages are insecure and marked as 'Not Secure' by browsers. HTTPS is a confirmed ranking signal.",
            "remediation": [
                "Install SSL certificate for domain",
                "Redirect all HTTP URLs to HTTPS versions",
                "Update internal links to use HTTPS",
                "Update canonical tags to HTTPS",
                "Test for mixed content warnings",
                "Submit HTTPS sitemap to search engines"
            ]
        }
    }

    def __init__(self, template_dir: str = "templates"):
        """Initialize report generator.

        Args:
            template_dir: Directory containing Jinja2 templates
        """
        # Find templates directory
        template_path = Path(template_dir)
        if not template_path.exists():
            # Try relative to this file
            template_path = Path(__file__).parent.parent.parent / "templates"

        self.env = Environment(loader=FileSystemLoader(str(template_path)))
        self.env.filters['format_number'] = self._format_number
        self.env.filters['markdown'] = self._markdown_to_html
        self.env.filters['url_to_filename'] = self._url_to_filename

    def _url_to_filename(self, url):
        """Convert URL to lighthouse report filename."""
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc.replace(":", "_").replace(".", "_")
        path = parsed.path.strip("/").replace("/", "_").replace(".", "_")
        if not path:
            path = "index"
        return f"{domain}_{path}"

    def _format_number(self, value):
        """Format number with thousand separators."""
        try:
            return "{:,}".format(int(value))
        except (ValueError, TypeError):
            return value

    def _markdown_to_html(self, text):
        """Convert markdown text to HTML."""
        import markdown
        from markupsafe import Markup
        import re

        if not text:
            return ""

        # Fix common markdown issues from LLM output

        # 1. Fix code blocks within list items - convert to simple inline code
        #    Matches patterns like:  ```html\n  <code here>\n  ```
        def fix_list_code_blocks(match):
            indent = match.group(1)
            code = match.group(2).strip()
            # Convert to simple <code> tag
            escaped_code = code.replace('<', '&lt;').replace('>', '&gt;')
            return f'{indent}<code>{escaped_code}</code>'

        # Match code blocks in list items (2+ space indent)
        text = re.sub(r'(\n\s{2,})```[\w]*\n(.*?)\n\s*```', fix_list_code_blocks, text, flags=re.DOTALL)

        # 2. Fix standalone improperly nested code blocks
        text = re.sub(r'```\n([^`\n])', r'```\n\n\1', text)

        # Convert markdown to HTML with comprehensive extensions
        html = markdown.markdown(
            text,
            extensions=[
                'extra',           # Tables, fenced code blocks, etc.
                'nl2br',          # New line to <br>
                'sane_lists',     # Better list handling
                'fenced_code',    # Fenced code blocks
                'tables',         # Table support
            ]
        )

        # Return as safe HTML
        return Markup(html)

    def generate_report(
        self,
        crawl_dir: Path,
        output_path: Path,
        historical_snapshots: Optional[List[Dict]] = None,
    ) -> None:
        """Generate HTML report from crawl directory.

        Args:
            crawl_dir: Path to crawl directory
            output_path: Path to save HTML report
            historical_snapshots: Optional list of historical data snapshots
        """
        # Load data
        metadata = self._load_json(crawl_dir / "metadata.json")
        technical_issues = self._load_json(crawl_dir / "technical_issues.json")
        recommendations = self._load_text(crawl_dir / "recommendations.txt")

        # Load advanced analysis if available
        advanced_analysis_path = crawl_dir / "advanced_analysis.json"
        advanced_analysis = None
        if advanced_analysis_path.exists():
            advanced_analysis = self._load_json(advanced_analysis_path)

        # Organize into patterns
        patterns = self._organize_patterns(technical_issues)

        # Separate by priority
        critical_patterns = [p for p in patterns if p['priority'] == 'critical']
        high_patterns = [p for p in patterns if p['priority'] == 'high']
        medium_patterns = [p for p in patterns if p['priority'] == 'medium']

        # Calculate totals
        total_issues = sum(p['count'] for p in patterns)
        critical_issues = sum(p['count'] for p in critical_patterns)

        # Process advanced analysis for template
        advanced_summary = self._process_advanced_summary(advanced_analysis, metadata['total_pages'])
        content_quality = self._process_content_quality(advanced_analysis)
        security_analysis = self._process_security_analysis(advanced_analysis, metadata['total_pages'])
        mobile_analysis = self._process_mobile_analysis(advanced_analysis, metadata['total_pages'])
        url_analysis = self._process_url_analysis(advanced_analysis, metadata['total_pages'])
        international_analysis = self._process_international_analysis(advanced_analysis, metadata['total_pages'])

        # Process Core Web Vitals analysis
        metadata_list = advanced_analysis.get('metadata_list', []) if advanced_analysis else []
        cwv_analysis = self._process_cwv_analysis(metadata_list)

        # Process Lighthouse analysis
        lighthouse_analysis = self._process_lighthouse_analysis(metadata_list)

        # Process Performance statistics (aggregate stats with sortable table)
        performance_statistics = self._process_performance_statistics(metadata_list)

        # Process Structured Data analysis
        sd_analysis = self._process_structured_data_analysis(metadata_list)

        # Process Crawlability analysis
        crawlability_analysis = advanced_analysis.get('crawlability', {}) if advanced_analysis else {}

        # Process Technology analysis
        technology_analysis = advanced_analysis.get('technology', {}) if advanced_analysis else {}

        # Process Page Matrix (all pages with issue indicators)
        page_matrix = self._process_page_matrix(metadata_list)

        # Convert metadata list to dict for new analyzers
        pages_dict = self._convert_metadata_list_to_dict(metadata_list)

        # Process new Tier 1 & Tier 2 analyses in parallel
        # Each analyzer is independent, so we can run them concurrently
        analyzer_results = self._run_analyzers_parallel(pages_dict)
        resource_analysis = analyzer_results['resource']
        console_errors = analyzer_results['console']
        social_meta = analyzer_results['social']
        redirect_analysis = analyzer_results['redirect']
        third_party_analysis = analyzer_results['third_party']
        lab_field_comparison = analyzer_results['lab_field']
        image_analysis = analyzer_results['image']

        # Process challenge/CAPTCHA detection (STORY-INFRA-006)
        challenge_detection = self._process_challenge_detection(metadata_list)

        # Load PSI data for embedded modal viewer
        psi_data = self._load_psi_data(crawl_dir)

        # Render template
        template = self.env.get_template('report.html')
        html = template.render(
            domain=self._extract_domain(metadata['start_url']),
            crawled_at=self._format_date(metadata['crawled_at']),
            total_pages=metadata['total_pages'],
            total_words=metadata.get('stats', {}).get('total_words', 0),
            total_issues=total_issues,
            critical_issues=critical_issues,
            critical_patterns=critical_patterns,
            high_patterns=high_patterns,
            medium_patterns=medium_patterns,
            recommendations=recommendations,
            advanced_summary=advanced_summary,
            content_quality=content_quality,
            security_analysis=security_analysis,
            mobile_analysis=mobile_analysis,
            url_analysis=url_analysis,
            international_analysis=international_analysis,
            cwv_analysis=cwv_analysis,
            lighthouse_analysis=lighthouse_analysis,
            performance_statistics=performance_statistics,
            sd_analysis=sd_analysis,
            crawlability_analysis=crawlability_analysis,
            technology_analysis=technology_analysis,
            historical_snapshots=historical_snapshots,
            # New Tier 1 & Tier 2 analyses
            resource_analysis=resource_analysis,
            console_errors=console_errors,
            social_meta=social_meta,
            redirect_analysis=redirect_analysis,
            third_party_analysis=third_party_analysis,
            lab_field_comparison=lab_field_comparison,
            image_analysis=image_analysis,
            page_matrix=page_matrix,
            psi_data=psi_data,
            # Challenge/CAPTCHA detection (STORY-INFRA-006)
            challenge_detection=challenge_detection,
        )

        # Save report
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html, encoding='utf-8')

    def _organize_patterns(self, technical_issues: dict) -> List[dict]:
        """Organize technical issues into patterns with examples.

        Args:
            technical_issues: Technical issues dictionary

        Returns:
            List of pattern dictionaries
        """
        patterns = []

        for key, pattern_def in self.PATTERNS.items():
            issue_data = technical_issues.get(key, [])

            if not issue_data:
                continue

            # Handle different issue formats
            examples = []
            count = 0

            if isinstance(issue_data, list):
                if key == 'missing_meta_descriptions' or key == 'missing_titles' or key == 'missing_h1':
                    # List of URLs
                    count = len(issue_data)
                    examples = [{'url': url, 'detail': 'Missing'} for url in issue_data]
                elif key in ['short_meta_descriptions', 'long_meta_descriptions']:
                    # List of (url, length) tuples converted to dicts
                    count = len(issue_data)
                    examples = [
                        {'url': item['url'], 'detail': f"{item['length']} characters"}
                        for item in issue_data
                    ]
                elif key == 'multiple_h1':
                    # List of (url, count) tuples
                    count = len(issue_data)
                    examples = [
                        {'url': item['url'], 'detail': f"{item['count']} H1 tags"}
                        for item in issue_data
                    ]
                elif key == 'images_without_alt':
                    # List of (url, missing, total) tuples
                    count = len(issue_data)
                    examples = [
                        {'url': item['url'], 'detail': f"{item['missing']} of {item['total']} images"}
                        for item in issue_data
                    ]
                elif key == 'slow_pages':
                    # List of (url, load_time) tuples
                    count = len(issue_data)
                    examples = [
                        {'url': item['url'], 'detail': f"{item['load_time']:.2f}s load time"}
                        for item in issue_data
                    ]
                elif key == 'thin_content':
                    # List of (url, word_count) tuples
                    count = len(issue_data)
                    examples = [
                        {'url': item['url'], 'detail': f"Only {item['word_count']} words"}
                        for item in issue_data
                    ]
                else:
                    count = len(issue_data)
                    examples = [{'url': item, 'detail': 'Issue detected'} for item in issue_data]
            elif isinstance(issue_data, dict):
                if key == 'duplicate_titles':
                    # Dict of title -> list of URLs
                    for title, urls in issue_data.items():
                        count += len(urls)
                        for url in urls:
                            examples.append({
                                'url': url,
                                'detail': f'Duplicate: "{title}"'
                            })

            if count > 0:
                patterns.append({
                    'title': pattern_def['title'],
                    'priority': pattern_def['priority'],
                    'description': pattern_def['description'],
                    'count': count,
                    'examples': examples,
                    'remediation': pattern_def['remediation']
                })

        # Sort by priority (critical first) then by count
        priority_order = {'critical': 0, 'high': 1, 'medium': 2}
        patterns.sort(key=lambda x: (priority_order.get(x['priority'], 3), -x['count']))

        return patterns

    def _load_json(self, filepath: Path) -> dict:
        """Load JSON file.

        Args:
            filepath: Path to JSON file

        Returns:
            Loaded data
        """
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _load_psi_data(self, crawl_dir: Path) -> dict:
        """Load all PSI JSON files from lighthouse directory.

        Args:
            crawl_dir: Path to crawl directory

        Returns:
            Dictionary mapping URL keys to PSI data
        """
        lighthouse_dir = crawl_dir / "lighthouse"
        if not lighthouse_dir.exists():
            return {}

        psi_data = {}
        for json_file in lighthouse_dir.glob("*.json"):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Use the filename (without extension) as key
                    key = json_file.stem
                    psi_data[key] = data
            except (json.JSONDecodeError, IOError):
                continue

        return psi_data

    def _load_text(self, filepath: Path) -> str:
        """Load text file.

        Args:
            filepath: Path to text file

        Returns:
            File contents
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            return "No recommendations available."

    def _extract_domain(self, url: str) -> str:
        """Extract domain from URL.

        Args:
            url: Full URL

        Returns:
            Domain name
        """
        from urllib.parse import urlparse
        return urlparse(url).netloc

    def _format_date(self, date_str: str) -> str:
        """Format ISO date string to readable format.

        Args:
            date_str: ISO format date string

        Returns:
            Formatted date string
        """
        try:
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return dt.strftime('%B %d, %Y at %I:%M %p')
        except:
            return date_str

    def _process_advanced_summary(self, advanced_analysis: dict, total_pages: int) -> dict:
        """Process advanced analysis into summary metrics.

        Args:
            advanced_analysis: Advanced analysis data
            total_pages: Total pages crawled

        Returns:
            Summary dictionary
        """
        if not advanced_analysis:
            return {}

        summary = {}

        # Content quality
        content_quality = advanced_analysis.get('content_quality', [])
        if content_quality:
            avg_readability = sum(item['readability_score'] for item in content_quality) / len(content_quality)
            summary['avg_readability'] = avg_readability

        # Security
        security = advanced_analysis.get('security', [])
        if security:
            https_count = sum(1 for item in security if item['has_https'])
            avg_security_score = sum(item['security_score'] for item in security) / len(security)
            summary['https_pages'] = https_count
            summary['avg_security_score'] = avg_security_score

        # Mobile
        mobile = advanced_analysis.get('mobile', [])
        if mobile:
            avg_mobile_score = sum(item.get('mobile_score', 0) for item in mobile) / len(mobile)
            summary['avg_mobile_score'] = avg_mobile_score

        return summary

    def _process_content_quality(self, advanced_analysis: dict) -> dict:
        """Process content quality analysis.

        Args:
            advanced_analysis: Advanced analysis data

        Returns:
            Content quality dictionary
        """
        if not advanced_analysis:
            return {}

        content_quality = advanced_analysis.get('content_quality', [])
        if not content_quality:
            return {}

        avg_readability = sum(item['readability_score'] for item in content_quality) / len(content_quality)
        avg_word_count = sum(item['word_count'] for item in content_quality) / len(content_quality)
        avg_sentence_count = sum(item['sentence_count'] for item in content_quality) / len(content_quality)
        avg_unique_words = sum(item['unique_words'] for item in content_quality) / len(content_quality)

        # Determine average grade level
        grades = [item['readability_grade'] for item in content_quality]
        avg_grade = max(set(grades), key=grades.count) if grades else "N/A"

        # Identify issues
        issues = []
        low_readability = sum(1 for item in content_quality if item['readability_score'] < 50)
        if low_readability > 0:
            issues.append(f"{low_readability} pages with low readability (< 50)")

        thin_content = sum(1 for item in content_quality if item['word_count'] < 300)
        if thin_content > 0:
            issues.append(f"{thin_content} pages with thin content (< 300 words)")

        # Sort pages by readability for top pages
        sorted_pages = sorted(content_quality, key=lambda x: x['readability_score'], reverse=True)
        top_pages = sorted_pages[:10]

        return {
            'avg_readability': avg_readability,
            'avg_grade': avg_grade,
            'pages_analyzed': len(content_quality),
            'avg_word_count': avg_word_count,
            'avg_sentence_count': avg_sentence_count,
            'avg_unique_words': avg_unique_words,
            'issues': issues,
            'top_pages': top_pages
        }

    def _process_security_analysis(self, advanced_analysis: dict, total_pages: int) -> dict:
        """Process security analysis.

        Args:
            advanced_analysis: Advanced analysis data
            total_pages: Total pages

        Returns:
            Security analysis dictionary
        """
        if not advanced_analysis:
            return {}

        security = advanced_analysis.get('security', [])
        if not security:
            return {}

        https_count = sum(1 for item in security if item['has_https'])
        avg_score = sum(item['security_score'] for item in security) / len(security)

        # Count header coverage per header
        recommended_headers = [
            'strict-transport-security',
            'x-content-type-options',
            'x-frame-options',
            'content-security-policy'
        ]

        header_counts = {h: 0 for h in recommended_headers}
        for item in security:
            page_headers = item.get('security_headers', {}).keys()
            for h in recommended_headers:
                if h in page_headers:
                    header_counts[h] += 1

        total = len(security)
        # Headers missing on ALL pages
        missing_headers = [h for h in recommended_headers if header_counts[h] == 0]
        # Headers with incomplete coverage (present on some but not all)
        partial_headers = {
            h: {'count': header_counts[h], 'percentage': round(100 * header_counts[h] / total, 1)}
            for h in recommended_headers
            if 0 < header_counts[h] < total
        }
        # Headers with full coverage
        complete_headers = [h for h in recommended_headers if header_counts[h] == total]

        insecure_pages = [item['url'] for item in security if not item['has_https']]

        return {
            'https_count': https_count,
            'total_pages': len(security),
            'avg_score': avg_score,
            'missing_headers': missing_headers,
            'partial_headers': partial_headers,
            'complete_headers': complete_headers,
            'insecure_pages': insecure_pages
        }

    def _process_mobile_analysis(self, advanced_analysis: dict, total_pages: int) -> dict:
        """Process mobile SEO analysis.

        Args:
            advanced_analysis: Advanced analysis data
            total_pages: Total pages

        Returns:
            Mobile analysis dictionary
        """
        if not advanced_analysis:
            return {}

        mobile = advanced_analysis.get('mobile', [])
        if not mobile:
            return {}

        viewport_count = sum(1 for item in mobile if item.get('has_viewport', False))
        avg_score = sum(item.get('mobile_score', 0) for item in mobile) / len(mobile)

        # Collect all issues
        all_issues = set()
        for item in mobile:
            all_issues.update(item.get('issues', []))

        return {
            'viewport_count': viewport_count,
            'total_pages': len(mobile),
            'avg_score': avg_score,
            'issues': list(all_issues)
        }

    def _process_url_analysis(self, advanced_analysis: dict, total_pages: int) -> dict:
        """Process URL structure analysis.

        Args:
            advanced_analysis: Advanced analysis data
            total_pages: Total pages

        Returns:
            URL analysis dictionary
        """
        if not advanced_analysis:
            return {}

        url_structure = advanced_analysis.get('url_structure', [])
        if not url_structure:
            return {}

        with_keywords = sum(1 for item in url_structure if item['has_keywords'])
        total_issues = sum(len(item['issues']) for item in url_structure)

        # Collect common issues
        issue_counts = {}
        for item in url_structure:
            for issue in item['issues']:
                issue_counts[issue] = issue_counts.get(issue, 0) + 1

        common_issues = sorted(issue_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        common_issues = [issue for issue, count in common_issues]

        # Find problematic URLs
        problematic_urls = [
            {'url': item['url'], 'issues': item['issues']}
            for item in url_structure
            if len(item['issues']) > 0
        ]

        return {
            'with_keywords': with_keywords,
            'total_pages': len(url_structure),
            'total_issues': total_issues,
            'common_issues': common_issues,
            'problematic_urls': problematic_urls
        }

    def _process_international_analysis(self, advanced_analysis: dict, total_pages: int) -> dict:
        """Process international SEO analysis.

        Args:
            advanced_analysis: Advanced analysis data
            total_pages: Total pages

        Returns:
            International analysis dictionary
        """
        if not advanced_analysis:
            return {}

        international = advanced_analysis.get('international', [])
        if not international:
            return {}

        lang_count = sum(1 for item in international if item.get('has_lang_attribute', False))
        hreflang_count = sum(1 for item in international if item.get('has_hreflang', False))
        utf8_count = sum(1 for item in international if (item.get('charset') or '').lower() == 'utf-8')

        # Collect all issues
        all_issues = set()
        for item in international:
            all_issues.update(item.get('issues', []))

        return {
            'lang_count': lang_count,
            'hreflang_count': hreflang_count,
            'utf8_count': utf8_count,
            'total_pages': len(international),
            'issues': list(all_issues)
        }

    def _process_page_matrix(self, metadata_list: List[dict]) -> dict:
        """Process page matrix with issue indicators for all pages.

        Args:
            metadata_list: List of page metadata dictionaries

        Returns:
            Page matrix dictionary with pages and issue counts
        """
        if not metadata_list:
            return {'pages': [], 'issue_counts': {}}

        pages = []
        issue_counts = {
            'missing_title': 0,
            'missing_description': 0,
            'missing_h1': 0,
            'missing_canonical': 0,
            'thin_content': 0,
            'slow_load': 0,
            'poor_performance': 0,
            'images_no_alt': 0,
            'a11y_issues': 0,
            'security_issues': 0,
            'console_errors': 0,
            'redirected': 0,
        }

        for page in metadata_list:
            url = page.get('url', '')
            title = page.get('title', '')

            # Calculate issues for this page
            issues = []

            # SEO Basics
            if not page.get('title'):
                issues.append('title')
                issue_counts['missing_title'] += 1
            if not page.get('description'):
                issues.append('desc')
                issue_counts['missing_description'] += 1
            if not page.get('h1_tags'):
                issues.append('h1')
                issue_counts['missing_h1'] += 1
            if not page.get('canonical_url'):
                issues.append('canonical')
                issue_counts['missing_canonical'] += 1

            # Content
            word_count = page.get('word_count', 0)
            if word_count < 300:
                issues.append('thin')
                issue_counts['thin_content'] += 1

            # Performance
            load_time = page.get('load_time', 0)
            if load_time > 3.0:
                issues.append('slow')
                issue_counts['slow_load'] += 1

            perf_score = page.get('lighthouse_performance_score')
            if perf_score is not None and perf_score < 50:
                issues.append('perf')
                issue_counts['poor_performance'] += 1

            # Accessibility
            images_no_alt = page.get('images_without_alt', 0)
            buttons_no_aria = page.get('buttons_without_aria', 0)
            links_no_context = page.get('links_without_context', 0)
            forms_no_labels = page.get('form_inputs_without_labels', 0)
            a11y_total = images_no_alt + buttons_no_aria + links_no_context + forms_no_labels

            if images_no_alt > 0:
                issues.append('alt')
                issue_counts['images_no_alt'] += 1
            if a11y_total > 0:
                issue_counts['a11y_issues'] += 1

            # Security
            has_https = page.get('has_https', True)
            security_headers = page.get('security_headers', {})
            if not has_https or len(security_headers) < 3:
                issues.append('security')
                issue_counts['security_issues'] += 1

            # Technical
            console_errors = page.get('console_errors', [])
            if console_errors:
                issues.append('errors')
                issue_counts['console_errors'] += 1

            was_redirected = page.get('was_redirected', False)
            if was_redirected:
                issues.append('redirect')
                issue_counts['redirected'] += 1

            # Scores
            perf = page.get('lighthouse_performance_score')
            a11y = page.get('lighthouse_accessibility_score')
            seo = page.get('lighthouse_seo_score')

            # Calculate health score (0-100)
            issue_penalty = len(issues) * 10
            health_score = max(0, 100 - issue_penalty)

            pages.append({
                'url': url,
                'title': title[:60] + '...' if title and len(title) > 60 else (title or '(No title)'),
                'issues': issues,
                'issue_count': len(issues),
                'health_score': health_score,
                'perf_score': perf,
                'a11y_score': a11y,
                'seo_score': seo,
                'word_count': word_count,
                'load_time': round(load_time, 2) if load_time else None,
            })

        # Sort by issue count (most issues first)
        pages.sort(key=lambda x: (-x['issue_count'], x['url']))

        return {
            'pages': pages,
            'issue_counts': issue_counts,
            'total_pages': len(pages),
        }

    def _process_cwv_analysis(self, metadata_list: List[dict]) -> dict:
        """Process Core Web Vitals analysis.

        Args:
            metadata_list: List of page metadata dictionaries

        Returns:
            Core Web Vitals analysis dictionary
        """
        if not metadata_list:
            return {}

        # Calculate aggregate statistics
        lcp_good = 0
        lcp_needs_improvement = 0
        lcp_poor = 0

        inp_good = 0
        inp_needs_improvement = 0
        inp_poor = 0

        cls_good = 0
        cls_needs_improvement = 0
        cls_poor = 0

        total_blocking_scripts = 0
        total_cls_risks = 0
        total_render_blocking = 0
        lcp_estimates = []

        pages_needing_improvement = []

        for page in metadata_list:
            # LCP status
            lcp_status = page.get('cwv_lcp_status', 'unknown')
            if lcp_status == 'good':
                lcp_good += 1
            elif lcp_status == 'needs-improvement':
                lcp_needs_improvement += 1
            elif lcp_status == 'poor':
                lcp_poor += 1

            # INP status
            inp_status = page.get('cwv_inp_status', 'unknown')
            if inp_status == 'good':
                inp_good += 1
            elif inp_status == 'needs-improvement':
                inp_needs_improvement += 1
            elif inp_status == 'poor':
                inp_poor += 1

            # CLS status
            cls_status = page.get('cwv_cls_status', 'unknown')
            if cls_status == 'good':
                cls_good += 1
            elif cls_status == 'needs-improvement':
                cls_needs_improvement += 1
            elif cls_status == 'poor':
                cls_poor += 1

            # Aggregate counts
            total_blocking_scripts += page.get('cwv_blocking_scripts', 0)
            total_cls_risks += page.get('cwv_cls_risks', 0)
            total_render_blocking += page.get('cwv_render_blocking', 0)

            # LCP estimates
            if page.get('cwv_lcp_estimate'):
                lcp_estimates.append(page['cwv_lcp_estimate'])

            # Pages needing improvement (not all good)
            overall_status = page.get('cwv_overall_status', 'unknown')
            if overall_status in ['needs-improvement', 'poor']:
                pages_needing_improvement.append({
                    'url': page['url'],
                    'lcp_status': lcp_status,
                    'inp_status': inp_status,
                    'cls_status': cls_status,
                    'blocking_scripts': page.get('cwv_blocking_scripts', 0),
                    'cls_risks': page.get('cwv_cls_risks', 0),
                    'render_blocking': page.get('cwv_render_blocking', 0),
                })

        total_pages = len(metadata_list)

        # Determine overall status (majority rule)
        def get_majority_status(good, needs_improvement, poor):
            if good > total_pages * 0.75:
                return 'good'
            elif poor > total_pages * 0.25:
                return 'poor'
            else:
                return 'needs-improvement'

        return {
            'lcp_status': get_majority_status(lcp_good, lcp_needs_improvement, lcp_poor),
            'inp_status': get_majority_status(inp_good, inp_needs_improvement, inp_poor),
            'cls_status': get_majority_status(cls_good, cls_needs_improvement, cls_poor),
            'avg_lcp_estimate': sum(lcp_estimates) / len(lcp_estimates) if lcp_estimates else None,
            'total_blocking_scripts': total_blocking_scripts,
            'total_cls_risks': total_cls_risks,
            'total_render_blocking': total_render_blocking,
            'pages_needing_improvement': sorted(
                pages_needing_improvement,
                key=lambda x: (x['lcp_status'] == 'poor', x['inp_status'] == 'poor', x['cls_status'] == 'poor'),
                reverse=True
            ),
        }

    def _process_lighthouse_analysis(self, metadata_list: List[dict]) -> dict:
        """Process Lighthouse performance analysis.

        Args:
            metadata_list: List of page metadata dictionaries

        Returns:
            Lighthouse analysis dictionary with scores, metrics, and opportunities
        """
        if not metadata_list:
            return {'enabled': False}

        # Filter pages with Lighthouse data
        pages_with_lighthouse = [
            p for p in metadata_list
            if p.get('lighthouse_performance_score') is not None
        ]

        if not pages_with_lighthouse:
            return {'enabled': False}

        # Helper to safely get numeric value (handles None)
        def safe_num(val, default=0):
            return val if val is not None else default

        # Calculate average scores
        avg_performance = sum(safe_num(p.get('lighthouse_performance_score')) for p in pages_with_lighthouse) / len(pages_with_lighthouse)
        avg_accessibility = sum(safe_num(p.get('lighthouse_accessibility_score')) for p in pages_with_lighthouse) / len(pages_with_lighthouse)
        avg_best_practices = sum(safe_num(p.get('lighthouse_best_practices_score')) for p in pages_with_lighthouse) / len(pages_with_lighthouse)
        avg_seo = sum(safe_num(p.get('lighthouse_seo_score')) for p in pages_with_lighthouse) / len(pages_with_lighthouse)
        avg_pwa = sum(safe_num(p.get('lighthouse_pwa_score')) for p in pages_with_lighthouse) / len(pages_with_lighthouse)

        # Calculate average metrics (in milliseconds)
        fcp_values = [p.get('lighthouse_fcp') for p in pages_with_lighthouse if p.get('lighthouse_fcp')]
        lcp_values = [p.get('lighthouse_lcp') for p in pages_with_lighthouse if p.get('lighthouse_lcp')]
        si_values = [p.get('lighthouse_si') for p in pages_with_lighthouse if p.get('lighthouse_si')]
        tti_values = [p.get('lighthouse_tti') for p in pages_with_lighthouse if p.get('lighthouse_tti')]
        tbt_values = [p.get('lighthouse_tbt') for p in pages_with_lighthouse if p.get('lighthouse_tbt')]
        cls_values = [p.get('lighthouse_cls') for p in pages_with_lighthouse if p.get('lighthouse_cls')]

        avg_fcp = sum(fcp_values) / len(fcp_values) if fcp_values else None
        avg_lcp = sum(lcp_values) / len(lcp_values) if lcp_values else None
        avg_si = sum(si_values) / len(si_values) if si_values else None
        avg_tti = sum(tti_values) / len(tti_values) if tti_values else None
        avg_tbt = sum(tbt_values) / len(tbt_values) if tbt_values else None
        avg_cls = sum(cls_values) / len(cls_values) if cls_values else None

        # Collect all optimization opportunities across pages
        all_opportunities = {}
        for page in pages_with_lighthouse:
            opportunities = page.get('lighthouse_opportunities', [])
            for opp in opportunities:
                opp_id = opp.get('id')
                if opp_id:
                    if opp_id not in all_opportunities:
                        all_opportunities[opp_id] = {
                            'title': opp.get('title'),
                            'description': opp.get('description'),
                            'pages_affected': [],
                            'total_savings_ms': 0,
                            'total_savings_bytes': 0,
                            'item_count': 0,
                        }
                    all_opportunities[opp_id]['pages_affected'].append(page['url'])
                    all_opportunities[opp_id]['total_savings_ms'] += opp.get('savings_ms', 0)
                    all_opportunities[opp_id]['total_savings_bytes'] += opp.get('savings_bytes', 0)
                    all_opportunities[opp_id]['item_count'] += opp.get('item_count', 0)

        # Sort opportunities by total savings (time)
        top_opportunities = sorted(
            all_opportunities.values(),
            key=lambda x: x['total_savings_ms'],
            reverse=True
        )[:10]  # Top 10 opportunities

        # Find pages needing performance improvement (score < 50)
        poor_performance_pages = [
            {
                'url': p['url'],
                'performance_score': p.get('lighthouse_performance_score', 0),
                'lcp': p.get('lighthouse_lcp'),
                'cls': p.get('lighthouse_cls'),
                'tbt': p.get('lighthouse_tbt'),
            }
            for p in pages_with_lighthouse
            if p.get('lighthouse_performance_score', 100) < 50
        ]

        # Categorize scores
        def categorize_score(score):
            if score >= 90:
                return 'good'
            elif score >= 50:
                return 'needs-improvement'
            else:
                return 'poor'

        perf_category = categorize_score(avg_performance)
        accessibility_category = categorize_score(avg_accessibility)
        seo_category = categorize_score(avg_seo)

        return {
            'enabled': True,
            'pages_audited': len(pages_with_lighthouse),
            'total_pages': len(metadata_list),
            'coverage_percentage': (len(pages_with_lighthouse) / len(metadata_list)) * 100,

            # Average scores
            'avg_performance_score': round(avg_performance, 1),
            'avg_accessibility_score': round(avg_accessibility, 1),
            'avg_best_practices_score': round(avg_best_practices, 1),
            'avg_seo_score': round(avg_seo, 1),
            'avg_pwa_score': round(avg_pwa, 1),

            # Score categories
            'performance_category': perf_category,
            'accessibility_category': accessibility_category,
            'seo_category': seo_category,

            # Average metrics
            'avg_fcp': round(avg_fcp) if avg_fcp else None,
            'avg_lcp': round(avg_lcp) if avg_lcp else None,
            'avg_si': round(avg_si) if avg_si else None,
            'avg_tti': round(avg_tti) if avg_tti else None,
            'avg_tbt': round(avg_tbt) if avg_tbt else None,
            'avg_cls': round(avg_cls, 3) if avg_cls else None,

            # Opportunities
            'top_opportunities': top_opportunities,
            'total_opportunity_count': len(all_opportunities),

            # Poor performing pages
            'poor_performance_pages': sorted(
                poor_performance_pages,
                key=lambda x: x['performance_score']
            ),
        }

    def _process_performance_statistics(self, metadata_list: List[dict]) -> dict:
        """Calculate aggregate performance statistics across all pages.

        Args:
            metadata_list: List of page metadata dictionaries

        Returns:
            Performance statistics dictionary with avg, median, stddev, p90
        """
        import statistics

        if not metadata_list:
            return {'enabled': False}

        # Filter to pages with Lighthouse data
        pages = [p for p in metadata_list if p.get('lighthouse_performance_score') is not None]

        if not pages:
            return {'enabled': False}

        def calc_stats(values):
            """Calculate statistics for a list of values."""
            values = [v for v in values if v is not None]
            if not values:
                return None
            n = len(values)
            sorted_vals = sorted(values)
            return {
                'count': n,
                'avg': round(statistics.mean(values), 2),
                'median': round(statistics.median(values), 2),
                'stddev': round(statistics.stdev(values), 2) if n > 1 else 0,
                'p90': round(sorted_vals[int(n * 0.9)] if n > 0 else 0, 2),
                'min': round(min(values), 2),
                'max': round(max(values), 2),
            }

        # Build pages list for sortable table
        pages_data = []
        for page in pages:
            pages_data.append({
                'url': page.get('url', ''),
                'title': page.get('title', 'Untitled'),
                'performance_score': page.get('lighthouse_performance_score'),
                'accessibility_score': page.get('lighthouse_accessibility_score'),
                'best_practices_score': page.get('lighthouse_best_practices_score'),
                'seo_score': page.get('lighthouse_seo_score'),
                'lcp': page.get('lighthouse_lcp'),
                'fcp': page.get('lighthouse_fcp'),
                'cls': page.get('lighthouse_cls'),
                'tbt': page.get('lighthouse_tbt'),
                'si': page.get('lighthouse_si'),
            })

        return {
            'enabled': True,
            'pages_analyzed': len(pages),
            'stats': {
                'performance_score': calc_stats([p.get('lighthouse_performance_score') for p in pages]),
                'accessibility_score': calc_stats([p.get('lighthouse_accessibility_score') for p in pages]),
                'best_practices_score': calc_stats([p.get('lighthouse_best_practices_score') for p in pages]),
                'seo_score': calc_stats([p.get('lighthouse_seo_score') for p in pages]),
                'lcp': calc_stats([p.get('lighthouse_lcp') for p in pages]),
                'fcp': calc_stats([p.get('lighthouse_fcp') for p in pages]),
                'cls': calc_stats([p.get('lighthouse_cls') for p in pages]),
                'tbt': calc_stats([p.get('lighthouse_tbt') for p in pages]),
                'si': calc_stats([p.get('lighthouse_si') for p in pages]),
            },
            'pages': sorted(pages_data, key=lambda x: x['performance_score'] or 0),
        }

    def _process_structured_data_analysis(self, metadata_list: List[dict]) -> dict:
        """Process Structured Data analysis.

        Args:
            metadata_list: List of page metadata dictionaries

        Returns:
            Structured Data analysis dictionary
        """
        if not metadata_list:
            return {}

        # Aggregate schema types across all pages
        all_schema_types = set()
        total_jsonld = 0
        total_microdata = 0
        total_errors = []
        total_warnings = []
        all_rich_results = {}
        all_missing_opportunities = set()
        avg_score = 0

        pages_with_schema = []
        pages_without_schema = []
        pages_with_errors = []

        for page in metadata_list:
            # Aggregate schema types
            schema_types = page.get('sd_schema_types', [])
            all_schema_types.update(schema_types)

            # Count formats
            total_jsonld += page.get('sd_jsonld_count', 0)
            total_microdata += page.get('sd_microdata_count', 0)

            # Collect errors/warnings
            errors = page.get('sd_validation_errors', [])
            warnings = page.get('sd_validation_warnings', [])
            if errors:
                total_errors.extend(errors)
                pages_with_errors.append({
                    'url': page['url'],
                    'errors': errors[:3]  # Limit to 3 per page
                })

            if warnings:
                total_warnings.extend(warnings)

            # Aggregate rich results
            rich_results = page.get('sd_rich_results', {})
            for result_type, eligible in rich_results.items():
                if result_type not in all_rich_results:
                    all_rich_results[result_type] = 0
                if eligible:
                    all_rich_results[result_type] += 1

            # Missing opportunities
            missing = page.get('sd_missing_opportunities', [])
            all_missing_opportunities.update(missing)

            # Score
            score = page.get('sd_overall_score', 0)
            avg_score += score

            # Categorize pages
            if schema_types or total_jsonld > 0 or total_microdata > 0:
                pages_with_schema.append({
                    'url': page['url'],
                    'schema_types': schema_types,
                    'score': score
                })
            else:
                pages_without_schema.append(page['url'])

        total_pages = len(metadata_list)
        avg_score = avg_score / total_pages if total_pages > 0 else 0

        # Determine overall status
        if avg_score >= 80:
            overall_status = 'excellent'
        elif avg_score >= 60:
            overall_status = 'good'
        elif avg_score >= 40:
            overall_status = 'needs-improvement'
        else:
            overall_status = 'poor'

        return {
            'total_pages': total_pages,
            'pages_with_schema_count': len(pages_with_schema),
            'pages_without_schema_count': len(pages_without_schema),
            'schema_types': sorted(list(all_schema_types)),
            'jsonld_count': total_jsonld,
            'microdata_count': total_microdata,
            'total_errors': len(total_errors),
            'total_warnings': len(total_warnings),
            'unique_errors': list(set(total_errors))[:10],  # Top 10 unique errors
            'unique_warnings': list(set(total_warnings))[:10],  # Top 10 unique warnings
            'rich_results': all_rich_results,
            'missing_opportunities': sorted(list(all_missing_opportunities)),
            'avg_score': avg_score,
            'overall_status': overall_status,
            'pages_with_schema': sorted(pages_with_schema, key=lambda x: x['score'], reverse=True)[:10],
            'pages_without_schema': pages_without_schema[:10],
            'pages_with_errors': pages_with_errors[:10],
        }

    def _build_site_hierarchy(self, urls: list) -> dict:
        """Build hierarchical site structure from URLs.

        Args:
            urls: List of crawled URLs

        Returns:
            Dictionary containing hierarchy tree, directory count, and file count
        """
        from urllib.parse import urlparse

        if not urls:
            return {'tree': {}, 'directory_count': 0, 'file_count': 0, 'total_urls': 0}

        # Build tree structure - everything goes under a single root
        root = {'type': 'directory', 'url': None, 'children': {}}

        for url in urls:
            parsed = urlparse(url)
            path = parsed.path.strip('/')

            if not path:
                # Homepage - add as direct child
                root['children']['(homepage)'] = {
                    'type': 'file',
                    'url': url,
                    'children': {}
                }
                continue

            # Split path into parts
            parts = path.split('/')
            current = root['children']

            for i, part in enumerate(parts):
                is_last = (i == len(parts) - 1)

                if part not in current:
                    current[part] = {
                        'type': 'file' if is_last else 'directory',
                        'url': url if is_last else None,
                        'children': {}
                    }
                elif is_last and current[part]['type'] == 'directory':
                    # This path is both a directory and a page (e.g., /products and /products/item)
                    # Keep it as directory but add the URL
                    current[part]['url'] = url

                # Move to next level (only if not last or if it's a directory)
                if not is_last or current[part]['type'] == 'directory':
                    current = current[part]['children']

        # Count directories and files
        def count_nodes(node, count_self=True):
            dirs = 0
            files = 0

            if count_self:
                if node.get('type') == 'directory':
                    dirs = 1
                elif node.get('type') == 'file':
                    files = 1

            for child in node.get('children', {}).values():
                child_dirs, child_files = count_nodes(child, count_self=True)
                dirs += child_dirs
                files += child_files

            return dirs, files

        total_dirs, total_files = count_nodes(root, count_self=False)

        return {
            'tree': root['children'],
            'directory_count': total_dirs,
            'file_count': total_files,
            'total_urls': len(urls)
        }

    # =========================================================================
    # New Analyzer Processing Methods (Tier 1 & Tier 2 Enhancements)
    # =========================================================================

    def _process_resource_analysis(self, pages: Dict[str, PageMetadata]) -> Dict:
        """Process resource composition analysis for report.

        Args:
            pages: Dictionary mapping URLs to PageMetadata

        Returns:
            Dictionary with resource analysis data for template
        """
        analyzer = ResourceAnalyzer()
        analysis = analyzer.analyze(pages)

        if analysis.total_pages == 0:
            return {'enabled': False}

        return {
            'enabled': True,
            'total_pages': analysis.total_pages,

            # Size summaries (formatted)
            'total_weight_mb': round(analysis.total_all_bytes / (1024 * 1024), 2),
            'avg_weight_kb': round(analysis.avg_page_weight_bytes / 1024, 1),

            # Distribution for pie chart
            'distribution': {
                'HTML': analysis.html_percentage,
                'CSS': analysis.css_percentage,
                'JavaScript': analysis.js_percentage,
                'Images': analysis.image_percentage,
                'Fonts': analysis.font_percentage,
            },

            # Issues
            'bloated_pages': analysis.bloated_pages[:10],
            'bloated_count': len(analysis.bloated_pages),
            'large_js_pages': analysis.large_js_pages[:10],
            'large_js_count': len(analysis.large_js_pages),
            'large_css_pages': analysis.large_css_pages[:10],
            'large_css_count': len(analysis.large_css_pages),
            'large_image_pages': analysis.large_image_pages[:10],
            'large_image_count': len(analysis.large_image_pages),

            # Top heaviest
            'heaviest_pages': analysis.heaviest_pages,

            # Recommendations
            'recommendations': analysis.recommendations,

            # Scores
            'has_issues': (
                len(analysis.bloated_pages) > 0 or
                len(analysis.large_js_pages) > 0 or
                len(analysis.large_css_pages) > 0
            ),
        }

    def _process_console_errors(self, pages: Dict[str, PageMetadata]) -> Dict:
        """Process console error analysis for report.

        Args:
            pages: Dictionary mapping URLs to PageMetadata

        Returns:
            Dictionary with console error data for template
        """
        analyzer = ConsoleErrorAnalyzer()
        analysis = analyzer.analyze(pages)

        # Check if any console data was captured
        has_data = any(
            page.console_errors or page.console_warnings
            for page in pages.values()
        )

        if not has_data:
            return {'enabled': False}

        # Determine severity level
        severity = 'good'
        if analysis.pages_with_errors > 0:
            error_rate = analysis.pages_with_errors / analysis.total_pages
            if error_rate > 0.5:
                severity = 'critical'
            elif error_rate > 0.2:
                severity = 'high'
            elif error_rate > 0.1:
                severity = 'medium'
            else:
                severity = 'low'

        return {
            'enabled': True,
            'total_pages': analysis.total_pages,
            'pages_with_errors': analysis.pages_with_errors,
            'pages_with_warnings': analysis.pages_with_warnings,
            'error_free_percentage': analysis.error_free_percentage,
            'total_errors': analysis.total_errors,
            'total_warnings': analysis.total_warnings,
            'errors_by_type': analysis.errors_by_type,
            'pages_by_error_count': analysis.pages_by_error_count,
            'common_errors': analysis.common_errors,
            'has_errors': analysis.total_errors > 0,
            'severity': severity,
        }

    def _process_social_meta(self, pages: Dict[str, PageMetadata]) -> Dict:
        """Process social meta analysis for report.

        Args:
            pages: Dictionary mapping URLs to PageMetadata

        Returns:
            Dictionary with social meta data for template
        """
        analyzer = SocialMetaAnalyzer()
        analysis = analyzer.analyze(pages)

        if analysis.total_pages == 0:
            return {'enabled': False}

        return {
            'enabled': True,
            'total_pages': analysis.total_pages,

            # Open Graph
            'pages_with_og': analysis.pages_with_og,
            'og_coverage_percentage': analysis.og_coverage_percentage,
            'avg_og_score': analysis.avg_og_score,
            'common_missing_og': analysis.common_missing_og,
            'pages_missing_og': analysis.pages_missing_og[:10],

            # Twitter Card
            'pages_with_twitter': analysis.pages_with_twitter,
            'twitter_coverage_percentage': analysis.twitter_coverage_percentage,
            'avg_twitter_score': analysis.avg_twitter_score,
            'common_missing_twitter': analysis.common_missing_twitter,
            'pages_missing_twitter': analysis.pages_missing_twitter[:10],

            # Issues and pages
            'pages_with_issues': analysis.pages_with_issues[:10],
            'best_pages': analysis.best_pages,
            'worst_pages': analysis.worst_pages[:10],

            # Status
            'has_issues': (
                analysis.og_coverage_percentage < 80 or
                analysis.twitter_coverage_percentage < 80
            ),
        }

    def _process_redirect_analysis(self, pages: Dict[str, PageMetadata]) -> Dict:
        """Process redirect chain analysis for report.

        Args:
            pages: Dictionary mapping URLs to PageMetadata

        Returns:
            Dictionary with redirect data for template
        """
        analyzer = RedirectAnalyzer()
        analysis = analyzer.analyze(pages)

        if analysis.total_pages == 0:
            return {'enabled': False}

        return {
            'enabled': True,
            'total_pages': analysis.total_pages,
            'pages_with_redirects': analysis.pages_with_redirects,
            'total_chains': analysis.total_chains,
            'total_hops': analysis.total_hops,
            'avg_hops_per_chain': analysis.avg_hops_per_chain,
            'max_chain_length': analysis.max_chain_length,
            'total_time_wasted_ms': analysis.total_time_wasted_ms,
            'total_time_wasted_seconds': round(analysis.total_time_wasted_ms / 1000, 2),
            'chains_1_hop': analysis.chains_1_hop,
            'chains_2_hops': analysis.chains_2_hops,
            'chains_3_plus_hops': analysis.chains_3_plus_hops,
            'long_chains': analysis.long_chains[:10],
            'all_chains': analysis.all_chains[:20],
            'recommendations': analysis.recommendations,
            'has_issues': analysis.chains_3_plus_hops > 0 or analysis.max_chain_length > 3,
        }

    def _process_third_party_analysis(self, pages: Dict[str, PageMetadata]) -> Dict:
        """Process third-party resource analysis for report.

        Args:
            pages: Dictionary mapping URLs to PageMetadata

        Returns:
            Dictionary with third-party data for template
        """
        analyzer = ThirdPartyAnalyzer()
        analysis = analyzer.analyze(pages)

        if analysis.total_pages == 0:
            return {'enabled': False}

        return {
            'enabled': True,
            'total_pages': analysis.total_pages,
            'pages_with_third_party': analysis.pages_with_third_party,
            'total_third_party_requests': analysis.total_third_party_requests,
            'total_third_party_bytes': analysis.total_third_party_bytes,
            'total_third_party_kb': round(analysis.total_third_party_bytes / 1024, 1),
            'avg_requests_per_page': analysis.avg_third_party_requests_per_page,
            'avg_bytes_per_page': analysis.avg_third_party_bytes_per_page,
            'avg_kb_per_page': round(analysis.avg_third_party_bytes_per_page / 1024, 1),
            'weight_percentage': analysis.third_party_weight_percentage,
            'top_by_requests': analysis.top_by_requests,
            'heaviest_pages': analysis.heaviest_pages,
            'analytics_domains': analysis.analytics_domains,
            'advertising_domains': analysis.advertising_domains,
            'cdn_domains': analysis.cdn_domains,
            'social_domains': analysis.social_domains,
            'other_domains': analysis.other_domains[:10],
            'recommendations': analysis.recommendations,
            'has_issues': (
                analysis.third_party_weight_percentage > 30 or
                analysis.avg_third_party_requests_per_page > 20
            ),
        }

    def _process_lab_field_comparison(self, pages: Dict[str, PageMetadata]) -> Dict:
        """Process lab vs field performance comparison for report.

        Args:
            pages: Dictionary mapping URLs to PageMetadata

        Returns:
            Dictionary with comparison data for template
        """
        analyzer = LabFieldAnalyzer()
        comparison = analyzer.analyze(pages)

        if comparison.total_pages == 0 or comparison.pages_with_both == 0:
            return {'enabled': False}

        lcp_data = None
        if comparison.lcp_comparison:
            lcp_data = {
                'metric_name': comparison.lcp_comparison.metric_name,
                'lab_value': comparison.lcp_comparison.lab_value,
                'field_value': comparison.lcp_comparison.field_value,
                'lab_status': comparison.lcp_comparison.lab_status,
                'field_status': comparison.lcp_comparison.field_status,
                'difference_percentage': comparison.lcp_comparison.difference_percentage,
                'status_match': comparison.lcp_comparison.status_match,
            }

        cls_data = None
        if comparison.cls_comparison:
            cls_data = {
                'metric_name': comparison.cls_comparison.metric_name,
                'lab_value': comparison.cls_comparison.lab_value,
                'field_value': comparison.cls_comparison.field_value,
                'lab_status': comparison.cls_comparison.lab_status,
                'field_status': comparison.cls_comparison.field_status,
                'difference_percentage': comparison.cls_comparison.difference_percentage,
                'status_match': comparison.cls_comparison.status_match,
            }

        return {
            'enabled': True,
            'total_pages': comparison.total_pages,
            'pages_with_both': comparison.pages_with_both,
            'overall_lab_better': comparison.overall_lab_better,
            'overall_field_better': comparison.overall_field_better,
            'overall_match': comparison.overall_match,
            'lcp_comparison': lcp_data,
            'cls_comparison': cls_data,
            'status_mismatches': comparison.status_mismatches[:10],
            'pages_with_gaps': comparison.pages_with_gaps[:10],
            'insights': comparison.insights,
            'lab_tendency': comparison.lab_tendency,
            'has_issues': len(comparison.status_mismatches) > 0,
        }

    def _process_image_analysis(self, pages: Dict[str, PageMetadata]) -> Dict:
        """Process image optimization analysis for report.

        Args:
            pages: Dictionary mapping URLs to PageMetadata

        Returns:
            Dictionary with image analysis data for template
        """
        analyzer = ImageAnalyzer()
        analysis = analyzer.analyze(pages)

        if analysis.total_pages == 0 or analysis.total_images == 0:
            return {'enabled': False}

        return {
            'enabled': True,
            'total_pages': analysis.total_pages,
            'total_images': analysis.total_images,

            # Format breakdown
            'format_counts': analysis.format_counts,
            'modern_format_percentage': analysis.modern_format_percentage,

            # Size metrics
            'total_image_bytes': analysis.total_image_bytes,
            'total_image_mb': round(analysis.total_image_bytes / (1024 * 1024), 2),
            'avg_image_bytes': analysis.avg_image_bytes,
            'avg_image_kb': round(analysis.avg_image_bytes / 1024, 1),

            # Optimization opportunities
            'images_needing_modern_format': len(analysis.images_needing_modern_format),
            'images_needing_modern_format_list': analysis.images_needing_modern_format[:20],
            'images_missing_dimensions': len(analysis.images_missing_dimensions),
            'images_missing_dimensions_list': analysis.images_missing_dimensions[:20],
            'images_needing_lazy_load': len(analysis.images_needing_lazy_load),
            'images_needing_lazy_load_list': analysis.images_needing_lazy_load[:10],

            # Lazy loading stats
            'lazy_loaded_count': analysis.lazy_loaded_count,
            'eager_loaded_count': analysis.eager_loaded_count,
            'lazy_load_percentage': analysis.lazy_load_percentage,

            # Alt text stats
            'images_with_alt': analysis.images_with_alt,
            'images_without_alt': analysis.images_without_alt,
            'alt_coverage_percentage': analysis.alt_coverage_percentage,

            # Estimated savings
            'estimated_savings_bytes': analysis.estimated_total_savings_bytes,
            'estimated_savings_kb': round(analysis.estimated_total_savings_bytes / 1024, 1),
            'estimated_savings_percentage': analysis.estimated_savings_percentage,

            # Recommendations
            'recommendations': analysis.recommendations,

            # Status
            'has_issues': (
                analysis.modern_format_percentage < 50 or
                len(analysis.images_missing_dimensions) > 0 or
                analysis.alt_coverage_percentage < 90
            ),
        }

    def _convert_metadata_list_to_dict(self, metadata_list: List[dict]) -> Dict[str, PageMetadata]:
        """Convert metadata list to dictionary of PageMetadata objects.

        Args:
            metadata_list: List of page metadata dictionaries

        Returns:
            Dictionary mapping URLs to PageMetadata objects
        """
        pages = {}
        for item in metadata_list:
            url = item.get('url', '')
            if url:
                # Create PageMetadata from dict
                page = PageMetadata(url=url)
                for key, value in item.items():
                    if hasattr(page, key):
                        setattr(page, key, value)
                pages[url] = page
        return pages

    def _process_challenge_detection(self, metadata_list: List[dict]) -> Dict:
        """Process challenge/CAPTCHA detection results for report.

        Analyzes pages for reCAPTCHA and other challenge detection data
        captured during browser-based crawling (STORY-INFRA-006).

        Args:
            metadata_list: List of page metadata dictionaries

        Returns:
            Dictionary with challenge detection analysis for template
        """
        if not metadata_list:
            return {'enabled': False}

        # Collect challenge detection data
        pages_with_challenges = []
        challenge_types = {}
        pages_skipped = []
        blocking_challenges = 0
        total_challenges_detected = 0

        for page in metadata_list:
            url = page.get('url', '')

            # Check for challenge detection flags
            challenge_detected = page.get('challenge_detected', False)
            recaptcha_result = page.get('recaptcha_result', {})
            blocking_result = page.get('blocking_result', {})
            skipped = page.get('skipped_due_to_challenge', False)

            if challenge_detected:
                total_challenges_detected += 1

                # Extract challenge type/version
                version = recaptcha_result.get('version', 'unknown')
                impact = recaptcha_result.get('automation_impact', 'unknown')

                if version not in challenge_types:
                    challenge_types[version] = 0
                challenge_types[version] += 1

                pages_with_challenges.append({
                    'url': url,
                    'title': page.get('title', '(No title)'),
                    'version': version,
                    'impact': impact,
                    'blocking': blocking_result.get('is_blocking', False),
                    'indicators': recaptcha_result.get('indicators', [])[:3],
                })

                if blocking_result.get('is_blocking', False):
                    blocking_challenges += 1

            if skipped:
                pages_skipped.append({
                    'url': url,
                    'reason': blocking_result.get('reason', 'Challenge not resolved'),
                })

        total_pages = len(metadata_list)

        if total_challenges_detected == 0:
            return {
                'enabled': True,
                'total_pages': total_pages,
                'challenges_detected': 0,
                'challenge_rate': 0,
                'blocking_challenges': 0,
                'pages_skipped': 0,
                'challenge_types': {},
                'pages_with_challenges': [],
                'skipped_pages': [],
                'status': 'clear',
                'summary': 'No CAPTCHA or bot challenges detected during crawl.',
                'has_issues': False,
            }

        # Determine severity
        challenge_rate = (total_challenges_detected / total_pages) * 100
        if challenge_rate > 50:
            status = 'critical'
        elif challenge_rate > 20:
            status = 'high'
        elif challenge_rate > 5:
            status = 'medium'
        else:
            status = 'low'

        return {
            'enabled': True,
            'total_pages': total_pages,
            'challenges_detected': total_challenges_detected,
            'challenge_rate': round(challenge_rate, 1),
            'blocking_challenges': blocking_challenges,
            'pages_skipped': len(pages_skipped),
            'challenge_types': challenge_types,
            'pages_with_challenges': sorted(
                pages_with_challenges,
                key=lambda x: (x['blocking'], x['impact'] == 'high'),
                reverse=True
            )[:20],
            'skipped_pages': pages_skipped[:10],
            'status': status,
            'summary': f'{total_challenges_detected} pages ({challenge_rate:.1f}%) had CAPTCHA/bot challenges.',
            'has_issues': blocking_challenges > 0 or len(pages_skipped) > 0,
        }

    def _run_analyzers_parallel(self, pages: Dict[str, PageMetadata]) -> Dict[str, Dict]:
        """Run all Tier 1 & Tier 2 analyzers in parallel.

        Since analyzers are independent and read-only, they can safely
        execute concurrently for improved performance.

        Args:
            pages: Dictionary mapping URLs to PageMetadata

        Returns:
            Dictionary with results keyed by analyzer name
        """
        results = {}

        # Define analyzer tasks as (name, function) pairs
        analyzer_tasks = [
            ('resource', self._process_resource_analysis),
            ('console', self._process_console_errors),
            ('social', self._process_social_meta),
            ('redirect', self._process_redirect_analysis),
            ('third_party', self._process_third_party_analysis),
            ('lab_field', self._process_lab_field_comparison),
            ('image', self._process_image_analysis),
        ]

        # Run analyzers in parallel using ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=len(analyzer_tasks)) as executor:
            # Submit all tasks
            future_to_name = {
                executor.submit(func, pages): name
                for name, func in analyzer_tasks
            }

            # Collect results as they complete
            for future in as_completed(future_to_name):
                name = future_to_name[future]
                try:
                    results[name] = future.result()
                except Exception as e:
                    # If an analyzer fails, return disabled state
                    results[name] = {'enabled': False, 'error': str(e)}

        return results
