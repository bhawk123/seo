"""Advanced SEO analyzers - security, URL structure, mobile, etc."""

import re
from urllib.parse import urlparse, parse_qs
from typing import Dict

from seo.models import SecurityAnalysis, URLStructureAnalysis, PageMetadata


class SecurityAnalyzer:
    """Analyzes security-related SEO factors."""

    RECOMMENDED_HEADERS = {
        'strict-transport-security',
        'x-content-type-options',
        'x-frame-options',
        'x-xss-protection',
        'content-security-policy',
    }

    def analyze(self, url: str, page_metadata: PageMetadata, response_headers: Dict[str, str] = None) -> SecurityAnalysis:
        """Analyze security aspects of a page.

        Args:
            url: Page URL
            page_metadata: Page metadata
            response_headers: HTTP response headers (optional)

        Returns:
            SecurityAnalysis with security metrics
        """
        has_https = url.startswith('https://')

        # Security headers
        security_headers = {}
        if response_headers:
            for header in self.RECOMMENDED_HEADERS:
                if header in response_headers:
                    security_headers[header] = response_headers[header]

        # Calculate security score
        score = 0
        if has_https:
            score += 40
        if 'strict-transport-security' in security_headers:
            score += 20
        if 'x-content-type-options' in security_headers:
            score += 10
        if 'x-frame-options' in security_headers:
            score += 10
        if 'content-security-policy' in security_headers:
            score += 20

        return SecurityAnalysis(
            url=url,
            has_https=has_https,
            security_headers=security_headers,
            security_score=score,
        )


class URLStructureAnalyzer:
    """Analyzes URL structure and optimization."""

    COMMON_STOP_WORDS = {
        'and', 'or', 'but', 'the', 'a', 'an', 'of', 'to', 'for', 'with',
        'on', 'at', 'from', 'by', 'about', 'as', 'into', 'through', 'is',
        'are', 'was', 'were', 'been', 'be', 'have', 'has', 'had', 'do',
        'does', 'did', 'will', 'would', 'should', 'could', 'may', 'might'
    }

    def analyze(self, url: str) -> URLStructureAnalysis:
        """Analyze URL structure and quality.

        Args:
            url: URL to analyze

        Returns:
            URLStructureAnalysis with URL metrics
        """
        parsed = urlparse(url)
        path = parsed.path

        # Calculate metrics
        url_length = len(url)
        uses_https = url.startswith('https://')
        has_parameters = bool(parsed.query)

        # Calculate depth (number of path segments)
        path_segments = [s for s in path.split('/') if s]
        depth_level = len(path_segments)

        # Check for keywords in URL
        has_keywords = self._has_meaningful_keywords(path)

        # Check readability
        readable = self._is_readable(path)

        # Identify issues
        issues = []
        if url_length > 100:
            issues.append("URL too long (>100 characters)")
        if not uses_https:
            issues.append("Not using HTTPS")
        if has_parameters:
            params = parse_qs(parsed.query)
            if len(params) > 3:
                issues.append(f"Too many URL parameters ({len(params)})")
        if depth_level > 4:
            issues.append(f"URL too deep ({depth_level} levels)")
        if not has_keywords:
            issues.append("No descriptive keywords in URL")
        if not readable:
            issues.append("URL not human-readable")
        if '_' in path:
            issues.append("Uses underscores instead of hyphens")

        return URLStructureAnalysis(
            url=url,
            url_length=url_length,
            has_keywords=has_keywords,
            has_parameters=has_parameters,
            depth_level=depth_level,
            uses_https=uses_https,
            readable=readable,
            issues=issues,
        )

    def _has_meaningful_keywords(self, path: str) -> bool:
        """Check if URL path contains meaningful keywords.

        Args:
            path: URL path

        Returns:
            True if path has meaningful keywords
        """
        # Extract words from path
        words = re.findall(r'[a-z]+', path.lower())

        # Filter out stop words
        meaningful_words = [w for w in words if w not in self.COMMON_STOP_WORDS]

        return len(meaningful_words) > 0

    def _is_readable(self, path: str) -> bool:
        """Check if URL is human-readable.

        Args:
            path: URL path

        Returns:
            True if URL is readable
        """
        # Check for common patterns that make URLs unreadable
        if re.search(r'\d{5,}', path):  # Long number sequences
            return False
        if re.search(r'[A-Z]{3,}', path):  # Long uppercase sequences
            return False
        if path.count('_') > 2:  # Too many underscores
            return False

        # Check if path has readable segments
        segments = [s for s in path.split('/') if s]
        for segment in segments:
            # Check if segment is mostly alphanumeric with hyphens
            if not re.match(r'^[a-z0-9-]+$', segment.lower()):
                if not segment.endswith(('.html', '.htm', '.php')):
                    return False

        return True


class MobileSEOAnalyzer:
    """Analyzes mobile SEO factors."""

    def analyze(self, page_metadata: PageMetadata) -> Dict:
        """Analyze mobile SEO factors.

        Args:
            page_metadata: Page metadata

        Returns:
            Dictionary with mobile SEO analysis
        """
        issues = []
        score = 100

        # Check viewport meta tag
        if not page_metadata.viewport_meta:
            issues.append("Missing viewport meta tag")
            score -= 40
        elif 'width=device-width' not in page_metadata.viewport_meta:
            issues.append("Viewport not set to device width")
            score -= 20

        # Check responsive indicators
        if page_metadata.total_images > 10:
            images_with_srcset = sum(
                1 for img in page_metadata.images
                if 'srcset' in img.get('src', '')
            )
            if images_with_srcset == 0:
                issues.append("No responsive images (missing srcset)")
                score -= 20

        return {
            'has_viewport': bool(page_metadata.viewport_meta),
            'viewport_content': page_metadata.viewport_meta,
            'mobile_score': max(0, score),
            'issues': issues,
        }


class InternationalSEOAnalyzer:
    """Analyzes international SEO factors."""

    def analyze(self, page_metadata: PageMetadata) -> Dict:
        """Analyze international SEO factors.

        Args:
            page_metadata: Page metadata

        Returns:
            Dictionary with international SEO analysis
        """
        issues = []

        # Check language declaration
        has_lang = bool(page_metadata.lang_attribute)
        if not has_lang:
            issues.append("Missing lang attribute on <html> tag")

        # Check hreflang tags
        has_hreflang = len(page_metadata.hreflang_tags) > 0

        # Check charset
        has_charset = bool(page_metadata.charset)
        if not has_charset:
            issues.append("Missing charset declaration")
        elif page_metadata.charset.lower() != 'utf-8':
            issues.append(f"Non-UTF-8 charset: {page_metadata.charset}")

        return {
            'has_lang_attribute': has_lang,
            'lang': page_metadata.lang_attribute,
            'has_hreflang': has_hreflang,
            'hreflang_count': len(page_metadata.hreflang_tags),
            'charset': page_metadata.charset,
            'issues': issues,
        }


class TechnologyAnalyzer:
    """Analyzes technology stack across site pages."""

    def analyze_site_technologies(self, site_data: Dict[str, PageMetadata]) -> Dict:
        """Analyze technologies used across the entire site.

        Args:
            site_data: Dictionary mapping URLs to PageMetadata objects

        Returns:
            Dictionary with technology analysis results
        """
        if not site_data:
            return {'enabled': False}

        all_technologies = set()
        by_category = {}
        technology_counts = {}
        pages_by_technology = {}

        # Aggregate technologies from all pages
        for url, metadata in site_data.items():
            if metadata.technologies:
                all_technologies.update(metadata.technologies)

                # Count technology occurrences
                for tech in metadata.technologies:
                    technology_counts[tech] = technology_counts.get(tech, 0) + 1

                    # Track which pages use each technology
                    if tech not in pages_by_technology:
                        pages_by_technology[tech] = []
                    pages_by_technology[tech].append(url)

                # Aggregate categories
                for category, techs in metadata.tech_by_category.items():
                    if category not in by_category:
                        by_category[category] = set()
                    by_category[category].update(techs)

        # Convert sets to sorted lists
        for category in by_category:
            by_category[category] = sorted(list(by_category[category]))

        # Find most common technologies
        sorted_techs = sorted(
            technology_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )

        # Detect primary platforms
        ecommerce_platforms = set()
        cms_platforms = set()
        web_servers = set()
        cdns = set()
        analytics = set()
        js_frameworks = set()
        css_frameworks = set()

        for url, metadata in site_data.items():
            if metadata.tech_ecommerce:
                ecommerce_platforms.add(metadata.tech_ecommerce)
            if metadata.tech_cms:
                cms_platforms.add(metadata.tech_cms)
            if metadata.tech_web_server:
                web_servers.add(metadata.tech_web_server)

        # Get from categories
        if 'CDN' in by_category:
            cdns = set(by_category['CDN'])
        if 'Analytics' in by_category:
            analytics = set(by_category['Analytics'])
        if 'JavaScript Frameworks' in by_category:
            js_frameworks = set(by_category['JavaScript Frameworks'])
        if 'CSS Frameworks' in by_category:
            css_frameworks = set(by_category['CSS Frameworks'])

        # Calculate coverage percentage for top technologies
        total_pages = len(site_data)
        technology_coverage = {}
        for tech, count in sorted_techs[:20]:  # Top 20
            percentage = round((count / total_pages) * 100, 1)
            technology_coverage[tech] = {
                'count': count,
                'percentage': percentage,
                'pages': pages_by_technology[tech][:10]  # First 10 pages
            }

        return {
            'enabled': True,
            'total_technologies': len(all_technologies),
            'all_technologies': sorted(list(all_technologies)),
            'by_category': by_category,
            'technology_counts': dict(sorted_techs),
            'technology_coverage': technology_coverage,
            'top_10_technologies': sorted_techs[:10],
            # Platform summaries
            'ecommerce_platforms': sorted(list(ecommerce_platforms)),
            'cms_platforms': sorted(list(cms_platforms)),
            'web_servers': sorted(list(web_servers)),
            'cdns': sorted(list(cdns)),
            'analytics_tools': sorted(list(analytics)),
            'js_frameworks': sorted(list(js_frameworks)),
            'css_frameworks': sorted(list(css_frameworks)),
            # Key indicators
            'has_ecommerce': len(ecommerce_platforms) > 0,
            'has_cms': len(cms_platforms) > 0,
            'has_cdn': len(cdns) > 0,
            'has_analytics': len(analytics) > 0,
            'has_google_analytics': any('Google Analytics' in t for t in all_technologies),
            'has_google_tag_manager': any('Google Tag Manager' in t for t in all_technologies),
            'uses_react': any('React' in t for t in all_technologies),
            'uses_vue': any('Vue' in t for t in all_technologies),
            'uses_angular': any('Angular' in t for t in all_technologies),
            'total_pages_analyzed': total_pages,
        }
