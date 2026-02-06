"""Advanced SEO analyzers - security, URL structure, mobile, etc."""

import re
from datetime import datetime
from urllib.parse import urlparse, parse_qs
from typing import Dict, List, Optional, Tuple

from seo.models import (
    SecurityAnalysis,
    URLStructureAnalysis,
    PageMetadata,
    EvidenceRecord,
    EvidenceCollection,
    ConfidenceLevel,
    EvidenceSourceType,
)


class SecurityAnalyzer:
    """Analyzes security-related SEO factors."""

    RECOMMENDED_HEADERS = {
        'strict-transport-security',
        'x-content-type-options',
        'x-frame-options',
        'x-xss-protection',
        'content-security-policy',
    }

    # Point values for security scoring
    SCORE_COMPONENTS = {
        'https': 40,
        'strict-transport-security': 20,
        'x-content-type-options': 10,
        'x-frame-options': 10,
        'x-xss-protection': 0,  # Deprecated, no points
        'content-security-policy': 20,
    }

    def __init__(self):
        """Initialize the security analyzer."""
        self._evidence_collection: Optional[EvidenceCollection] = None
        self._url: str = ""

    def analyze(
        self, url: str, page_metadata: PageMetadata, response_headers: Dict[str, str] = None
    ) -> Tuple[SecurityAnalysis, Dict]:
        """Analyze security aspects of a page.

        Args:
            url: Page URL
            page_metadata: Page metadata
            response_headers: HTTP response headers (optional)

        Returns:
            Tuple of (SecurityAnalysis, evidence_dict)
        """
        self._url = url
        self._evidence_collection = EvidenceCollection(
            finding='security_analysis',
            component_id='security_analyzer',
        )

        has_https = url.startswith('https://')

        # Track score components for evidence
        score_breakdown = {'https': self.SCORE_COMPONENTS['https'] if has_https else 0}

        # Add HTTPS evidence
        if has_https:
            self._add_header_evidence(
                header='https',
                status='present',
                value='HTTPS protocol in use',
                points=self.SCORE_COMPONENTS['https'],
            )
        else:
            self._add_header_evidence(
                header='https',
                status='missing',
                value=None,
                points=0,
                severity='critical',
            )

        # Security headers
        security_headers = {}
        headers_points = 0

        for header in self.RECOMMENDED_HEADERS:
            header_lower = header.lower()
            present = False
            value = None

            if response_headers:
                # Check case-insensitive
                for h, v in response_headers.items():
                    if h.lower() == header_lower:
                        present = True
                        value = v
                        security_headers[header] = v
                        break

            points = self.SCORE_COMPONENTS.get(header, 0) if present else 0
            headers_points += points
            score_breakdown[header] = points

            self._add_header_evidence(
                header=header,
                status='present' if present else 'missing',
                value=value,
                points=points,
            )

        # Calculate total security score
        score = score_breakdown['https'] + headers_points

        # Add aggregate evidence
        self._add_score_evidence(score, score_breakdown)

        result = SecurityAnalysis(
            url=url,
            has_https=has_https,
            security_headers=security_headers,
            security_score=score,
        )

        return result, self._evidence_collection.to_dict()

    def _add_header_evidence(
        self,
        header: str,
        status: str,
        value: Optional[str],
        points: int,
        severity: str = 'warning',
    ) -> None:
        """Add evidence for a security header check.

        Args:
            header: Header name
            status: 'present' or 'missing'
            value: Header value if present
            points: Points awarded
            severity: Severity level for missing headers
        """
        finding = f'{header.replace("-", "_")}_{status}'
        evidence_string = f'{header}: {value}' if value else f'{header} not found'

        record = EvidenceRecord(
            component_id='security_analyzer',
            finding=finding,
            evidence_string=evidence_string,
            confidence=ConfidenceLevel.HIGH,
            timestamp=datetime.now(),
            source='HTTP Response Headers',
            source_type=EvidenceSourceType.MEASUREMENT,
            source_location=self._url,
            measured_value={'status': status, 'value': value, 'points': points},
            ai_generated=False,
            reasoning=f'Header {"present with value" if value else "not present in response"}',
            input_summary={
                'header': header,
                'max_points': self.SCORE_COMPONENTS.get(header, 0),
                'points_awarded': points,
                'severity': severity if status == 'missing' else None,
            },
        )
        self._evidence_collection.add_record(record)

    def _add_score_evidence(self, total_score: int, breakdown: Dict[str, int]) -> None:
        """Add evidence for the overall security score.

        Args:
            total_score: Total security score
            breakdown: Score breakdown by component
        """
        record = EvidenceRecord(
            component_id='security_analyzer',
            finding='security_score',
            evidence_string=f'Security score: {total_score}/100',
            confidence=ConfidenceLevel.HIGH,
            timestamp=datetime.now(),
            source='Security Analysis',
            source_type=EvidenceSourceType.CALCULATION,
            source_location=self._url,
            measured_value=total_score,
            ai_generated=False,
            reasoning='Sum of points for HTTPS and security headers',
            input_summary={
                'score_breakdown': breakdown,
                'max_possible': sum(self.SCORE_COMPONENTS.values()),
                'formula': 'https_points + sum(header_points)',
            },
        )
        self._evidence_collection.add_record(record)


class URLStructureAnalyzer:
    """Analyzes URL structure and optimization."""

    COMMON_STOP_WORDS = {
        'and', 'or', 'but', 'the', 'a', 'an', 'of', 'to', 'for', 'with',
        'on', 'at', 'from', 'by', 'about', 'as', 'into', 'through', 'is',
        'are', 'was', 'were', 'been', 'be', 'have', 'has', 'had', 'do',
        'does', 'did', 'will', 'would', 'should', 'could', 'may', 'might'
    }

    # Thresholds for URL quality
    THRESHOLDS = {
        'url_length': {'operator': '>', 'value': 75, 'unit': 'characters'},
        'url_length_warning': {'operator': '>', 'value': 100, 'unit': 'characters'},
        'depth_level': {'operator': '>', 'value': 4, 'unit': 'levels'},
        'max_parameters': {'operator': '>', 'value': 3, 'unit': 'parameters'},
    }

    def __init__(self):
        """Initialize the URL structure analyzer."""
        self._evidence_collection: Optional[EvidenceCollection] = None
        self._url: str = ""

    def analyze(self, url: str) -> Tuple[URLStructureAnalysis, Dict]:
        """Analyze URL structure and quality.

        Args:
            url: URL to analyze

        Returns:
            Tuple of (URLStructureAnalysis, evidence_dict)
        """
        self._url = url
        self._evidence_collection = EvidenceCollection(
            finding='url_structure',
            component_id='url_structure_analyzer',
        )

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

        # Check for specific issues
        has_underscores = '_' in path
        has_encoded_chars = '%' in url
        encoded_chars = re.findall(r'%[0-9A-Fa-f]{2}', url) if has_encoded_chars else []

        # Identify issues with evidence
        issues = []

        # URL length check
        if url_length > self.THRESHOLDS['url_length']['value']:
            issues.append(f"URL too long (>{self.THRESHOLDS['url_length']['value']} characters)")
            self._add_issue_evidence(
                finding='url_too_long',
                measured_value=url_length,
                threshold=self.THRESHOLDS['url_length'],
            )

        # HTTPS check
        if not uses_https:
            issues.append("Not using HTTPS")
            self._add_issue_evidence(
                finding='not_https',
                measured_value='http',
                threshold={'expected': 'https'},
            )

        # Parameters check
        if has_parameters:
            params = parse_qs(parsed.query)
            if len(params) > self.THRESHOLDS['max_parameters']['value']:
                issues.append(f"Too many URL parameters ({len(params)})")
                self._add_issue_evidence(
                    finding='too_many_parameters',
                    measured_value=len(params),
                    threshold=self.THRESHOLDS['max_parameters'],
                )

        # Depth check
        if depth_level > self.THRESHOLDS['depth_level']['value']:
            issues.append(f"URL too deep ({depth_level} levels)")
            self._add_issue_evidence(
                finding='url_too_deep',
                measured_value=depth_level,
                threshold=self.THRESHOLDS['depth_level'],
            )

        # Keywords check
        if not has_keywords:
            issues.append("No descriptive keywords in URL")
            self._add_issue_evidence(
                finding='no_keywords',
                measured_value=0,
                threshold={'expected': '> 0 meaningful keywords'},
            )

        # Readability check
        if not readable:
            issues.append("URL not human-readable")
            self._add_issue_evidence(
                finding='not_readable',
                measured_value=path,
                threshold={'expected': 'alphanumeric with hyphens'},
            )

        # Underscores check
        if has_underscores:
            issues.append("Uses underscores instead of hyphens")
            self._add_issue_evidence(
                finding='underscores_in_url',
                measured_value=path.count('_'),
                threshold={'recommendation': 'Use hyphens (-) instead of underscores (_)'},
            )

        # Encoded characters check
        if has_encoded_chars:
            self._add_issue_evidence(
                finding='contains_encoded_characters',
                measured_value=encoded_chars,
                threshold={'recommendation': 'Avoid URL-encoded characters'},
            )

        # Add summary evidence
        self._add_summary_evidence(
            url_length=url_length,
            depth_level=depth_level,
            has_keywords=has_keywords,
            readable=readable,
            has_underscores=has_underscores,
            uses_https=uses_https,
            issue_count=len(issues),
        )

        result = URLStructureAnalysis(
            url=url,
            url_length=url_length,
            has_keywords=has_keywords,
            has_parameters=has_parameters,
            depth_level=depth_level,
            uses_https=uses_https,
            readable=readable,
            issues=issues,
        )

        return result, self._evidence_collection.to_dict()

    def _add_issue_evidence(
        self,
        finding: str,
        measured_value,
        threshold: Dict,
    ) -> None:
        """Add evidence for a URL structure issue.

        Args:
            finding: Issue type
            measured_value: The measured value
            threshold: Threshold information
        """
        record = EvidenceRecord(
            component_id='url_structure_analyzer',
            finding=finding,
            evidence_string=f'{finding}: {measured_value}',
            confidence=ConfidenceLevel.HIGH,
            timestamp=datetime.now(),
            source='URL Analysis',
            source_type=EvidenceSourceType.MEASUREMENT,
            source_location=self._url,
            measured_value=measured_value,
            ai_generated=False,
            reasoning=f'Value {measured_value} compared against threshold',
            input_summary={'threshold': threshold},
        )
        self._evidence_collection.add_record(record)

    def _add_summary_evidence(
        self,
        url_length: int,
        depth_level: int,
        has_keywords: bool,
        readable: bool,
        has_underscores: bool,
        uses_https: bool,
        issue_count: int,
    ) -> None:
        """Add summary evidence for URL structure analysis.

        Args:
            url_length: URL character count
            depth_level: Path depth
            has_keywords: Whether URL has meaningful keywords
            readable: Whether URL is human-readable
            has_underscores: Whether URL contains underscores
            uses_https: Whether URL uses HTTPS
            issue_count: Number of issues found
        """
        status = 'good' if issue_count == 0 else 'needs_improvement'

        record = EvidenceRecord(
            component_id='url_structure_analyzer',
            finding='url_structure_summary',
            evidence_string=f'URL structure: {status} ({issue_count} issues)',
            confidence=ConfidenceLevel.HIGH,
            timestamp=datetime.now(),
            source='URL Analysis',
            source_type=EvidenceSourceType.CALCULATION,
            source_location=self._url,
            measured_value={
                'url_length': url_length,
                'depth_level': depth_level,
                'has_keywords': has_keywords,
                'readable': readable,
                'uses_hyphens': not has_underscores,
                'uses_https': uses_https,
            },
            ai_generated=False,
            reasoning=f'{issue_count} URL structure issues detected',
            input_summary={
                'thresholds': self.THRESHOLDS,
                'checks_performed': [
                    'url_length', 'depth_level', 'keywords', 'readability',
                    'underscores', 'https', 'parameters', 'encoded_chars'
                ],
            },
        )
        self._evidence_collection.add_record(record)

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

    # Score deductions for mobile issues
    SCORE_DEDUCTIONS = {
        'missing_viewport': 40,
        'fixed_viewport': 20,
        'no_responsive_images': 20,
        'small_text': 10,
        'small_touch_targets': 10,
    }

    # Thresholds
    THRESHOLDS = {
        'min_base_font': {'value': 16, 'unit': 'px'},
        'min_touch_target': {'value': 48, 'unit': 'px'},
        'responsive_image_threshold': 10,  # Check srcset if > 10 images
    }

    def __init__(self):
        """Initialize the mobile SEO analyzer."""
        self._evidence_collection: Optional[EvidenceCollection] = None
        self._url: str = ""

    def analyze(self, page_metadata: PageMetadata, url: str = "") -> Tuple[Dict, Dict]:
        """Analyze mobile SEO factors.

        Args:
            page_metadata: Page metadata
            url: Page URL for evidence

        Returns:
            Tuple of (analysis_dict, evidence_dict)
        """
        self._url = url or getattr(page_metadata, 'url', '')
        self._evidence_collection = EvidenceCollection(
            finding='mobile_seo',
            component_id='mobile_seo_analyzer',
        )

        issues = []
        score = 100
        score_breakdown = {}

        # Check viewport meta tag
        if not page_metadata.viewport_meta:
            issues.append("Missing viewport meta tag")
            deduction = self.SCORE_DEDUCTIONS['missing_viewport']
            score -= deduction
            score_breakdown['viewport'] = -deduction

            self._add_issue_evidence(
                finding='viewport_missing',
                severity='critical',
                evidence_string='No viewport meta tag found',
                deduction=deduction,
            )
        elif 'width=device-width' not in page_metadata.viewport_meta:
            # Check for fixed width viewport
            if re.search(r'width=\d+', page_metadata.viewport_meta):
                issues.append("Viewport set to fixed width")
                deduction = self.SCORE_DEDUCTIONS['fixed_viewport']
                score -= deduction
                score_breakdown['viewport'] = -deduction

                self._add_issue_evidence(
                    finding='fixed_viewport',
                    severity='warning',
                    evidence_string=page_metadata.viewport_meta,
                    deduction=deduction,
                    recommendation='Use width=device-width for responsive design',
                )
            else:
                issues.append("Viewport not set to device width")
                deduction = self.SCORE_DEDUCTIONS['fixed_viewport']
                score -= deduction
                score_breakdown['viewport'] = -deduction

                self._add_issue_evidence(
                    finding='viewport_not_responsive',
                    severity='warning',
                    evidence_string=page_metadata.viewport_meta,
                    deduction=deduction,
                )
        else:
            # Viewport is good
            self._add_pass_evidence(
                finding='viewport_present',
                evidence_string=page_metadata.viewport_meta,
            )

        # Check responsive indicators
        if page_metadata.total_images > self.THRESHOLDS['responsive_image_threshold']:
            images_with_srcset = sum(
                1 for img in page_metadata.images
                if 'srcset' in str(img.get('srcset', '')) or 'srcset' in str(img.get('src', ''))
            )
            if images_with_srcset == 0:
                issues.append("No responsive images (missing srcset)")
                deduction = self.SCORE_DEDUCTIONS['no_responsive_images']
                score -= deduction
                score_breakdown['responsive_images'] = -deduction

                self._add_issue_evidence(
                    finding='no_responsive_images',
                    severity='warning',
                    evidence_string=f'0 of {page_metadata.total_images} images have srcset',
                    deduction=deduction,
                    threshold={'images_checked': page_metadata.total_images},
                )

        # Add summary evidence
        self._add_summary_evidence(
            score=max(0, score),
            score_breakdown=score_breakdown,
            issue_count=len(issues),
            has_viewport=bool(page_metadata.viewport_meta),
        )

        result = {
            'has_viewport': bool(page_metadata.viewport_meta),
            'viewport_content': page_metadata.viewport_meta,
            'mobile_score': max(0, score),
            'issues': issues,
        }

        return result, self._evidence_collection.to_dict()

    def _add_issue_evidence(
        self,
        finding: str,
        severity: str,
        evidence_string: str,
        deduction: int,
        recommendation: str = None,
        threshold: Dict = None,
    ) -> None:
        """Add evidence for a mobile SEO issue.

        Args:
            finding: Issue type
            severity: 'critical' or 'warning'
            evidence_string: Description of the issue
            deduction: Points deducted
            recommendation: Optional recommendation
            threshold: Optional threshold info
        """
        record = EvidenceRecord(
            component_id='mobile_seo_analyzer',
            finding=finding,
            evidence_string=evidence_string,
            confidence=ConfidenceLevel.HIGH,
            timestamp=datetime.now(),
            source='Mobile SEO Analysis',
            source_type=EvidenceSourceType.MEASUREMENT,
            source_location=self._url,
            measured_value={'severity': severity, 'deduction': deduction},
            ai_generated=False,
            reasoning=recommendation or f'Mobile SEO issue detected: {finding}',
            input_summary={
                'severity': severity,
                'points_deducted': deduction,
                'threshold': threshold,
            },
        )
        self._evidence_collection.add_record(record)

    def _add_pass_evidence(self, finding: str, evidence_string: str) -> None:
        """Add evidence for a passing check.

        Args:
            finding: Check type
            evidence_string: The value that passed
        """
        record = EvidenceRecord(
            component_id='mobile_seo_analyzer',
            finding=finding,
            evidence_string=evidence_string,
            confidence=ConfidenceLevel.HIGH,
            timestamp=datetime.now(),
            source='Mobile SEO Analysis',
            source_type=EvidenceSourceType.MEASUREMENT,
            source_location=self._url,
            measured_value={'status': 'pass'},
            ai_generated=False,
            reasoning='Check passed',
        )
        self._evidence_collection.add_record(record)

    def _add_summary_evidence(
        self,
        score: int,
        score_breakdown: Dict[str, int],
        issue_count: int,
        has_viewport: bool,
    ) -> None:
        """Add summary evidence for mobile SEO analysis.

        Args:
            score: Final mobile score
            score_breakdown: Score deductions by category
            issue_count: Number of issues found
            has_viewport: Whether viewport tag exists
        """
        record = EvidenceRecord(
            component_id='mobile_seo_analyzer',
            finding='mobile_score',
            evidence_string=f'Mobile SEO score: {score}/100 ({issue_count} issues)',
            confidence=ConfidenceLevel.HIGH,
            timestamp=datetime.now(),
            source='Mobile SEO Analysis',
            source_type=EvidenceSourceType.CALCULATION,
            source_location=self._url,
            measured_value=score,
            ai_generated=False,
            reasoning='Score starts at 100 with deductions for issues',
            input_summary={
                'base_score': 100,
                'deductions': score_breakdown,
                'final_score': score,
                'thresholds': self.THRESHOLDS,
            },
        )
        self._evidence_collection.add_record(record)


class InternationalSEOAnalyzer:
    """Analyzes international SEO factors."""

    # Valid ISO 639-1 language codes (subset of common ones)
    VALID_LANG_CODES = {
        'en', 'es', 'fr', 'de', 'it', 'pt', 'nl', 'ru', 'ja', 'zh', 'ko',
        'ar', 'hi', 'th', 'vi', 'id', 'ms', 'pl', 'uk', 'cs', 'ro', 'hu',
        'el', 'sv', 'da', 'fi', 'no', 'tr', 'he', 'fa', 'bn', 'ta', 'te',
    }

    def __init__(self):
        """Initialize the international SEO analyzer."""
        self._evidence_collection: Optional[EvidenceCollection] = None
        self._url: str = ""

    def analyze(self, page_metadata: PageMetadata, url: str = "") -> Tuple[Dict, Dict]:
        """Analyze international SEO factors.

        Args:
            page_metadata: Page metadata
            url: Page URL for evidence

        Returns:
            Tuple of (analysis_dict, evidence_dict)
        """
        self._url = url or getattr(page_metadata, 'url', '')
        self._evidence_collection = EvidenceCollection(
            finding='international_seo',
            component_id='international_seo_analyzer',
        )

        issues = []

        # Check language declaration
        has_lang = bool(page_metadata.lang_attribute)
        if not has_lang:
            issues.append("Missing lang attribute on <html> tag")
            self._add_issue_evidence(
                finding='missing_lang',
                severity='warning',
                evidence_string='No lang attribute on <html> tag',
            )
        else:
            # Validate the lang code
            lang_code = page_metadata.lang_attribute.split('-')[0].lower()
            if lang_code not in self.VALID_LANG_CODES:
                self._add_issue_evidence(
                    finding='invalid_lang_code',
                    severity='warning',
                    evidence_string=page_metadata.lang_attribute,
                    recommendation=f'Use valid ISO 639-1 code instead of "{lang_code}"',
                )
            else:
                self._add_pass_evidence(
                    finding='lang_attribute',
                    evidence_string=page_metadata.lang_attribute,
                )

        # Check hreflang tags
        has_hreflang = len(page_metadata.hreflang_tags) > 0
        if has_hreflang:
            self._add_hreflang_evidence(page_metadata.hreflang_tags)

            # Check for self-reference
            has_self_reference = any(
                tag.get('href', '').rstrip('/') == self._url.rstrip('/')
                for tag in page_metadata.hreflang_tags
            )
            if not has_self_reference and self._url:
                issues.append("Missing hreflang self-reference")
                self._add_issue_evidence(
                    finding='missing_self_reference',
                    severity='warning',
                    evidence_string='Current page not included in hreflang tags',
                    recommendation='Add hreflang tag referencing the current URL',
                )

            # Validate hreflang codes
            for tag in page_metadata.hreflang_tags:
                hreflang = tag.get('hreflang', '')
                lang_part = hreflang.split('-')[0].lower()
                if lang_part != 'x-default' and lang_part not in self.VALID_LANG_CODES:
                    issues.append(f"Invalid hreflang code: {hreflang}")
                    self._add_issue_evidence(
                        finding='invalid_hreflang',
                        severity='warning',
                        evidence_string=hreflang,
                        recommendation=f'Use valid ISO 639-1 code instead of "{lang_part}"',
                    )

        # Check charset
        has_charset = bool(page_metadata.charset)
        if not has_charset:
            issues.append("Missing charset declaration")
            self._add_issue_evidence(
                finding='missing_charset',
                severity='warning',
                evidence_string='No charset meta tag found',
            )
        elif page_metadata.charset.lower() != 'utf-8':
            issues.append(f"Non-UTF-8 charset: {page_metadata.charset}")
            self._add_issue_evidence(
                finding='non_utf8_charset',
                severity='info',
                evidence_string=page_metadata.charset,
                recommendation='Use UTF-8 for best compatibility',
            )
        else:
            self._add_pass_evidence(
                finding='charset',
                evidence_string=page_metadata.charset,
            )

        # Add summary evidence
        self._add_summary_evidence(
            has_lang=has_lang,
            lang=page_metadata.lang_attribute,
            has_hreflang=has_hreflang,
            hreflang_count=len(page_metadata.hreflang_tags),
            charset=page_metadata.charset,
            issue_count=len(issues),
        )

        result = {
            'has_lang_attribute': has_lang,
            'lang': page_metadata.lang_attribute,
            'has_hreflang': has_hreflang,
            'hreflang_count': len(page_metadata.hreflang_tags),
            'charset': page_metadata.charset,
            'issues': issues,
        }

        return result, self._evidence_collection.to_dict()

    def _add_issue_evidence(
        self,
        finding: str,
        severity: str,
        evidence_string: str,
        recommendation: str = None,
    ) -> None:
        """Add evidence for an international SEO issue.

        Args:
            finding: Issue type
            severity: 'critical', 'warning', or 'info'
            evidence_string: Description of the issue
            recommendation: Optional recommendation
        """
        record = EvidenceRecord(
            component_id='international_seo_analyzer',
            finding=finding,
            evidence_string=evidence_string,
            confidence=ConfidenceLevel.HIGH,
            timestamp=datetime.now(),
            source='International SEO Analysis',
            source_type=EvidenceSourceType.MEASUREMENT,
            source_location=self._url,
            measured_value={'severity': severity},
            ai_generated=False,
            reasoning=recommendation or f'International SEO issue: {finding}',
        )
        self._evidence_collection.add_record(record)

    def _add_pass_evidence(self, finding: str, evidence_string: str) -> None:
        """Add evidence for a passing check.

        Args:
            finding: Check type
            evidence_string: The value that passed
        """
        record = EvidenceRecord(
            component_id='international_seo_analyzer',
            finding=finding,
            evidence_string=evidence_string,
            confidence=ConfidenceLevel.HIGH,
            timestamp=datetime.now(),
            source='International SEO Analysis',
            source_type=EvidenceSourceType.MEASUREMENT,
            source_location=self._url,
            measured_value={'status': 'pass'},
            ai_generated=False,
            reasoning='Check passed',
        )
        self._evidence_collection.add_record(record)

    def _add_hreflang_evidence(self, hreflang_tags: List[Dict]) -> None:
        """Add evidence for hreflang tag configuration.

        Args:
            hreflang_tags: List of hreflang tag dictionaries
        """
        hreflang_list = [
            {'hreflang': tag.get('hreflang', ''), 'href': tag.get('href', '')}
            for tag in hreflang_tags
        ]

        record = EvidenceRecord(
            component_id='international_seo_analyzer',
            finding='hreflang_tags',
            evidence_string=f'{len(hreflang_tags)} hreflang tags configured',
            confidence=ConfidenceLevel.HIGH,
            timestamp=datetime.now(),
            source='International SEO Analysis',
            source_type=EvidenceSourceType.MEASUREMENT,
            source_location=self._url,
            measured_value=hreflang_list,
            ai_generated=False,
            reasoning='Hreflang tags found in page',
        )
        self._evidence_collection.add_record(record)

    def _add_summary_evidence(
        self,
        has_lang: bool,
        lang: Optional[str],
        has_hreflang: bool,
        hreflang_count: int,
        charset: Optional[str],
        issue_count: int,
    ) -> None:
        """Add summary evidence for international SEO analysis.

        Args:
            has_lang: Whether lang attribute exists
            lang: Language code
            has_hreflang: Whether hreflang tags exist
            hreflang_count: Number of hreflang tags
            charset: Character set
            issue_count: Number of issues found
        """
        record = EvidenceRecord(
            component_id='international_seo_analyzer',
            finding='international_seo_summary',
            evidence_string=f'International SEO: {issue_count} issues found',
            confidence=ConfidenceLevel.HIGH,
            timestamp=datetime.now(),
            source='International SEO Analysis',
            source_type=EvidenceSourceType.CALCULATION,
            source_location=self._url,
            measured_value={
                'has_lang': has_lang,
                'lang': lang,
                'has_hreflang': has_hreflang,
                'hreflang_count': hreflang_count,
                'charset': charset,
                'issue_count': issue_count,
            },
            ai_generated=False,
            reasoning='Summary of international SEO checks',
            input_summary={
                'valid_lang_codes': 'ISO 639-1 standard',
                'recommended_charset': 'UTF-8',
            },
        )
        self._evidence_collection.add_record(record)


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
