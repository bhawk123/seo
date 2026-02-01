"""Data models for SEO analysis."""

from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class PageMetadata:
    """Metadata extracted from a web page."""

    url: str
    title: Optional[str] = None
    description: Optional[str] = None
    keywords: list[str] = field(default_factory=list)
    h1_tags: list[str] = field(default_factory=list)
    h2_tags: list[str] = field(default_factory=list)
    images: list[dict[str, str]] = field(default_factory=list)
    images_without_alt: int = 0
    total_images: int = 0
    buttons_without_aria: int = 0
    links_without_context: int = 0
    form_inputs_without_labels: int = 0
    links: list[str] = field(default_factory=list)
    internal_links: int = 0
    external_links: int = 0
    word_count: int = 0
    load_time: float = 0.0
    status_code: int = 200
    canonical_url: Optional[str] = None
    robots_directives: dict[str, bool] = field(default_factory=dict)
    schema_markup: list[dict] = field(default_factory=list)
    open_graph: dict[str, str] = field(default_factory=dict)
    crawled_at: datetime = field(default_factory=datetime.now)

    # Advanced SEO fields
    viewport_meta: Optional[str] = None
    lang_attribute: Optional[str] = None
    hreflang_tags: list[dict[str, str]] = field(default_factory=list)
    charset: Optional[str] = None
    content_text: str = ""
    readability_score: float = 0.0
    has_https: bool = False
    security_headers: dict[str, str] = field(default_factory=dict)
    twitter_card: dict[str, str] = field(default_factory=dict)
    broken_links: list[str] = field(default_factory=list)
    redirect_chain: list[str] = field(default_factory=list)

    # Core Web Vitals (Basic estimates)
    cwv_lcp_estimate: Optional[float] = None  # Largest Contentful Paint (seconds)
    cwv_lcp_status: str = "unknown"  # good/needs-improvement/poor/unknown
    cwv_inp_status: str = "unknown"  # Interaction to Next Paint
    cwv_cls_status: str = "unknown"  # Cumulative Layout Shift
    cwv_overall_status: str = "unknown"  # Overall Core Web Vitals status
    cwv_blocking_scripts: int = 0  # Count of blocking scripts
    cwv_cls_risks: int = 0  # Count of CLS risk elements
    cwv_render_blocking: int = 0  # Count of render-blocking resources

    # Lighthouse Performance Metrics (Real measurements)
    lighthouse_performance_score: Optional[float] = None  # 0-100
    lighthouse_accessibility_score: Optional[float] = None  # 0-100
    lighthouse_best_practices_score: Optional[float] = None  # 0-100
    lighthouse_seo_score: Optional[float] = None  # 0-100
    lighthouse_pwa_score: Optional[float] = None  # 0-100

    # Lighthouse Core Web Vitals (Actual measurements)
    lighthouse_fcp: Optional[float] = None  # First Contentful Paint (ms)
    lighthouse_lcp: Optional[float] = None  # Largest Contentful Paint (ms)
    lighthouse_si: Optional[float] = None  # Speed Index (ms)
    lighthouse_tti: Optional[float] = None  # Time to Interactive (ms)
    lighthouse_tbt: Optional[float] = None  # Total Blocking Time (ms)
    lighthouse_cls: Optional[float] = None  # Cumulative Layout Shift (score)

    # Lighthouse Additional Metrics
    lighthouse_first_meaningful_paint: Optional[float] = None  # ms
    lighthouse_max_potential_fid: Optional[float] = None  # ms
    lighthouse_screenshot_thumbnails: list[dict] = field(default_factory=list)
    lighthouse_diagnostics: dict = field(default_factory=dict)  # Additional diagnostic info
    lighthouse_opportunities: list[dict] = field(default_factory=list)  # Optimization opportunities
    lighthouse_fetch_time: Optional[str] = None  # When Lighthouse was run

    # Chrome User Experience Report (CrUX) - Real User Data from PageSpeed Insights
    crux_lcp_percentile: Optional[int] = None  # LCP at 75th percentile (ms)
    crux_lcp_category: Optional[str] = None  # FAST/AVERAGE/SLOW
    crux_fid_percentile: Optional[int] = None  # FID at 75th percentile (ms)
    crux_fid_category: Optional[str] = None  # FAST/AVERAGE/SLOW
    crux_cls_percentile: Optional[float] = None  # CLS at 75th percentile
    crux_cls_category: Optional[str] = None  # FAST/AVERAGE/SLOW
    crux_overall_category: Optional[str] = None  # Overall site speed category

    # Structured Data
    sd_schema_types: list[str] = field(default_factory=list)  # Schema types found
    sd_jsonld_count: int = 0  # Number of JSON-LD blocks
    sd_microdata_count: int = 0  # Number of Microdata items
    sd_validation_errors: list[str] = field(default_factory=list)  # Validation errors
    sd_validation_warnings: list[str] = field(default_factory=list)  # Validation warnings
    sd_rich_results: dict[str, bool] = field(default_factory=dict)  # Rich result eligibility
    sd_missing_opportunities: list[str] = field(default_factory=list)  # Missing schemas
    sd_overall_score: int = 0  # 0-100 structured data score

    # Technology Stack Detection
    technologies: list[str] = field(default_factory=list)  # All detected technologies
    tech_by_category: dict[str, list[str]] = field(default_factory=dict)  # Categorized techs
    tech_details: dict[str, dict] = field(default_factory=dict)  # Detailed tech info
    tech_ecommerce: Optional[str] = None  # Primary ecommerce platform
    tech_cms: Optional[str] = None  # Primary CMS
    tech_web_server: Optional[str] = None  # Web server
    tech_has_cdn: bool = False  # Has CDN
    tech_has_analytics: bool = False  # Has analytics

    # Page Weight & Resources
    html_size_bytes: int = 0  # Size of HTML in bytes
    total_page_weight_bytes: int = 0  # Total page weight including resources
    css_count: int = 0  # Number of CSS files
    css_size_bytes: int = 0  # Total CSS size
    js_count: int = 0  # Number of JS files
    js_size_bytes: int = 0  # Total JS size
    image_count: int = 0  # Number of images loaded
    image_size_bytes: int = 0  # Total image size
    font_count: int = 0  # Number of font files
    font_size_bytes: int = 0  # Total font size
    text_to_html_ratio: float = 0.0  # Ratio of text to HTML

    # Redirect & URL Info
    was_redirected: bool = False  # Did the page redirect?
    final_url: Optional[str] = None  # Final URL after redirects
    redirect_count: int = 0  # Number of redirects

    # Content Analysis
    content_hash: Optional[str] = None  # MD5 hash for duplicate detection
    above_fold_word_count: int = 0  # Words visible without scrolling
    above_fold_images: int = 0  # Images visible without scrolling

    # Console & Errors
    console_errors: list[str] = field(default_factory=list)  # JS console errors
    console_warnings: list[str] = field(default_factory=list)  # JS console warnings

    # Lazy Loading
    lazy_images_count: int = 0  # Images with lazy loading
    eager_images_count: int = 0  # Images loaded immediately

    # Third-Party Resources
    third_party_domains: list[str] = field(default_factory=list)  # External domains
    third_party_request_count: int = 0  # Number of third-party requests
    third_party_size_bytes: int = 0  # Size of third-party resources

    # Fonts
    web_fonts: list[dict] = field(default_factory=list)  # Font details (name, size, format)


@dataclass
class SEOScore:
    """SEO evaluation score and recommendations."""

    url: str
    overall_score: float
    title_score: float
    description_score: float
    content_score: float
    technical_score: float
    recommendations: list[str] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    analyzed_at: datetime = field(default_factory=datetime.now)


@dataclass
class CrawlResult:
    """Result of crawling a website."""

    url: str
    metadata: PageMetadata
    html: str
    success: bool = True
    error: Optional[str] = None


@dataclass
class TechnicalIssues:
    """Technical SEO issues found during analysis."""

    missing_titles: list[str] = field(default_factory=list)
    duplicate_titles: dict[str, list[str]] = field(default_factory=dict)
    missing_meta_descriptions: list[str] = field(default_factory=list)
    short_meta_descriptions: list[tuple[str, int]] = field(default_factory=list)
    long_meta_descriptions: list[tuple[str, int]] = field(default_factory=list)
    missing_h1: list[str] = field(default_factory=list)
    multiple_h1: list[tuple[str, int]] = field(default_factory=list)
    images_without_alt: list[tuple[str, int, int]] = field(default_factory=list)
    slow_pages: list[tuple[str, float]] = field(default_factory=list)
    thin_content: list[tuple[str, int]] = field(default_factory=list)
    missing_canonical: list[str] = field(default_factory=list)
    missing_viewport: list[str] = field(default_factory=list)
    missing_lang: list[str] = field(default_factory=list)
    non_https: list[str] = field(default_factory=list)
    broken_links: list[tuple[str, list[str]]] = field(default_factory=list)
    orphan_pages: list[str] = field(default_factory=list)
    missing_structured_data: list[str] = field(default_factory=list)
    poor_readability: list[tuple[str, float]] = field(default_factory=list)


@dataclass
class ContentQualityMetrics:
    """Content quality analysis metrics."""

    url: str
    readability_score: float  # Flesch Reading Ease (0-100, higher is better)
    readability_grade: str  # Grade level (e.g., "6th Grade", "College")
    word_count: int
    sentence_count: int
    avg_words_per_sentence: float
    keyword_density: dict[str, float] = field(default_factory=dict)  # keyword -> density %
    content_depth_score: float = 0.0  # 0-100 based on comprehensiveness
    unique_words: int = 0
    difficult_words: int = 0


@dataclass
class SecurityAnalysis:
    """Security analysis results."""

    url: str
    has_https: bool
    ssl_valid: bool = False
    security_headers: dict[str, str] = field(default_factory=dict)
    mixed_content_issues: list[str] = field(default_factory=list)
    security_score: float = 0.0  # 0-100


@dataclass
class URLStructureAnalysis:
    """URL structure analysis."""

    url: str
    url_length: int
    has_keywords: bool
    has_parameters: bool
    depth_level: int  # Number of slashes
    uses_https: bool
    readable: bool  # Human-readable URL
    issues: list[str] = field(default_factory=list)


@dataclass
class ICEScore:
    """ICE Framework score for prioritization."""

    action: str
    impact: float  # 1-10
    confidence: float  # 1-10
    ease: float  # 1-10
    ice_score: float = 0.0  # Impact × Confidence × Ease
    description: str = ""
    implementation_steps: list[str] = field(default_factory=list)
    expected_outcome: str = ""


@dataclass
class ComprehensiveSEOReport:
    """Comprehensive SEO analysis report."""

    domain: str
    total_pages: int
    technical_issues: TechnicalIssues
    content_quality_summary: dict = field(default_factory=dict)
    security_summary: dict = field(default_factory=dict)
    url_structure_summary: dict = field(default_factory=dict)
    recommendations: list[str] = field(default_factory=list)
    priority_actions: list[ICEScore] = field(default_factory=list)
    overall_score: float = 0.0
    report_date: datetime = field(default_factory=datetime.now)


# ============================================================================
# Resource Analysis Models
# ============================================================================

@dataclass
class ResourceBreakdown:
    """Breakdown of resources for a single page."""
    url: str
    html_bytes: int = 0
    css_bytes: int = 0
    js_bytes: int = 0
    image_bytes: int = 0
    font_bytes: int = 0
    other_bytes: int = 0
    total_bytes: int = 0

    @property
    def css_percentage(self) -> float:
        return (self.css_bytes / self.total_bytes * 100) if self.total_bytes > 0 else 0

    @property
    def js_percentage(self) -> float:
        return (self.js_bytes / self.total_bytes * 100) if self.total_bytes > 0 else 0

    @property
    def image_percentage(self) -> float:
        return (self.image_bytes / self.total_bytes * 100) if self.total_bytes > 0 else 0


@dataclass
class ResourceAnalysis:
    """Site-wide resource analysis results."""

    total_pages: int = 0

    # Aggregate sizes
    total_html_bytes: int = 0
    total_css_bytes: int = 0
    total_js_bytes: int = 0
    total_image_bytes: int = 0
    total_font_bytes: int = 0
    total_other_bytes: int = 0
    total_all_bytes: int = 0

    # Averages
    avg_page_weight_bytes: int = 0
    avg_html_bytes: int = 0
    avg_css_bytes: int = 0
    avg_js_bytes: int = 0
    avg_image_bytes: int = 0

    # Distribution percentages (site-wide)
    html_percentage: float = 0.0
    css_percentage: float = 0.0
    js_percentage: float = 0.0
    image_percentage: float = 0.0
    font_percentage: float = 0.0

    # Issues
    bloated_pages: list = field(default_factory=list)  # Pages > 2MB
    large_js_pages: list = field(default_factory=list)  # JS > 500KB
    large_css_pages: list = field(default_factory=list)  # CSS > 200KB
    large_image_pages: list = field(default_factory=list)  # Images > 1MB

    # Top heaviest pages
    heaviest_pages: list = field(default_factory=list)  # Top 10 by total weight

    # Per-page breakdown
    page_breakdowns: list = field(default_factory=list)

    # Recommendations
    recommendations: list = field(default_factory=list)


# ============================================================================
# Console Error Analysis Models
# ============================================================================

@dataclass
class ConsoleErrorAnalysis:
    """Analysis of JavaScript console errors and warnings."""

    total_pages: int = 0
    pages_with_errors: int = 0
    pages_with_warnings: int = 0
    error_free_percentage: float = 0.0

    # Error counts by category
    total_errors: int = 0
    total_warnings: int = 0

    # Categorized errors
    errors_by_type: dict = field(default_factory=dict)  # TypeError: 5, ReferenceError: 3

    # Pages with most errors
    pages_by_error_count: list = field(default_factory=list)  # [{url, error_count, errors}]

    # Common error patterns
    common_errors: list = field(default_factory=list)  # Most frequent error messages

    # All errors with URLs
    all_errors: list = field(default_factory=list)  # [{url, error, type}]


# ============================================================================
# Third-Party Analysis Models
# ============================================================================

@dataclass
class ThirdPartyDomain:
    """Analysis of a single third-party domain."""
    domain: str
    request_count: int = 0
    total_bytes: int = 0
    pages_present: int = 0
    resource_types: list = field(default_factory=list)  # ['script', 'image', 'font']


@dataclass
class ThirdPartyAnalysis:
    """Analysis of third-party resources across site."""

    total_pages: int = 0
    pages_with_third_party: int = 0

    # Aggregate metrics
    total_third_party_requests: int = 0
    total_third_party_bytes: int = 0
    avg_third_party_requests_per_page: float = 0.0
    avg_third_party_bytes_per_page: int = 0

    # Percentage of page weight from third parties
    third_party_weight_percentage: float = 0.0

    # Per-domain breakdown
    domains: list = field(default_factory=list)  # List of ThirdPartyDomain

    # Top domains by impact
    top_by_requests: list = field(default_factory=list)
    top_by_bytes: list = field(default_factory=list)

    # Pages with most third-party resources
    heaviest_pages: list = field(default_factory=list)

    # Categorized domains
    analytics_domains: list = field(default_factory=list)
    advertising_domains: list = field(default_factory=list)
    cdn_domains: list = field(default_factory=list)
    social_domains: list = field(default_factory=list)
    other_domains: list = field(default_factory=list)

    # Recommendations
    recommendations: list = field(default_factory=list)


# ============================================================================
# Social Meta Analysis Models
# ============================================================================

@dataclass
class SocialMetaPageResult:
    """Social meta analysis for a single page."""
    url: str

    # Open Graph
    og_present: bool = False
    og_properties: dict = field(default_factory=dict)
    og_missing: list = field(default_factory=list)
    og_score: int = 0  # 0-100

    # Twitter Card
    twitter_present: bool = False
    twitter_properties: dict = field(default_factory=dict)
    twitter_missing: list = field(default_factory=list)
    twitter_score: int = 0  # 0-100

    # Issues
    issues: list = field(default_factory=list)


@dataclass
class SocialMetaAnalysis:
    """Site-wide social meta analysis."""

    total_pages: int = 0

    # Open Graph coverage
    pages_with_og: int = 0
    og_coverage_percentage: float = 0.0
    avg_og_score: float = 0.0

    # Twitter Card coverage
    pages_with_twitter: int = 0
    twitter_coverage_percentage: float = 0.0
    avg_twitter_score: float = 0.0

    # Common missing properties
    common_missing_og: dict = field(default_factory=dict)  # property: count
    common_missing_twitter: dict = field(default_factory=dict)

    # Pages with issues
    pages_missing_og: list = field(default_factory=list)
    pages_missing_twitter: list = field(default_factory=list)
    pages_with_issues: list = field(default_factory=list)

    # Best/worst pages
    best_pages: list = field(default_factory=list)
    worst_pages: list = field(default_factory=list)

    # Per-page results
    page_results: list = field(default_factory=list)


# ============================================================================
# Lab vs Field Comparison Models
# ============================================================================

@dataclass
class MetricComparison:
    """Comparison of a single metric between lab and field."""
    metric_name: str
    lab_value: float = 0.0
    field_value: float = 0.0
    lab_status: str = "unknown"  # good/needs-improvement/poor
    field_status: str = "unknown"
    difference_percentage: float = 0.0
    status_match: bool = True
    insight: str = ""


@dataclass
class LabFieldComparison:
    """Comparison between Lighthouse (lab) and CrUX (field) data."""

    total_pages: int = 0
    pages_with_both: int = 0  # Pages that have both lab and field data

    # Overall comparison
    overall_lab_better: int = 0
    overall_field_better: int = 0
    overall_match: int = 0

    # Per-metric comparisons (aggregated)
    lcp_comparison: Optional[MetricComparison] = None
    fid_inp_comparison: Optional[MetricComparison] = None
    cls_comparison: Optional[MetricComparison] = None

    # Status mismatches (where lab and field disagree)
    status_mismatches: list = field(default_factory=list)

    # Pages with significant gaps
    pages_with_gaps: list = field(default_factory=list)

    # Insights
    insights: list = field(default_factory=list)

    # Is lab optimistic or pessimistic overall?
    lab_tendency: str = "neutral"  # optimistic/pessimistic/neutral


# ============================================================================
# Redirect Analysis Models
# ============================================================================

@dataclass
class RedirectChain:
    """A single redirect chain analysis."""
    source_url: str
    final_url: str
    chain: list = field(default_factory=list)  # List of URLs in chain
    hop_count: int = 0
    estimated_time_ms: int = 0  # Estimated time cost


@dataclass
class RedirectAnalysis:
    """Site-wide redirect chain analysis."""

    total_pages: int = 0
    pages_with_redirects: int = 0

    # Chain statistics
    total_chains: int = 0
    total_hops: int = 0
    avg_hops_per_chain: float = 0.0
    max_chain_length: int = 0

    # Time impact
    total_time_wasted_ms: int = 0
    avg_time_per_redirect_ms: int = 100  # Estimated ms per redirect

    # Chains by length
    chains_1_hop: int = 0
    chains_2_hops: int = 0
    chains_3_plus_hops: int = 0

    # Problem chains (3+ hops)
    long_chains: list = field(default_factory=list)

    # All chains
    all_chains: list = field(default_factory=list)

    # Recommendations
    recommendations: list = field(default_factory=list)


# ============================================================================
# Image Analysis Models
# ============================================================================

@dataclass
class ImageIssue:
    """A single image optimization issue."""
    url: str
    page_url: str
    issue_type: str  # 'format', 'size', 'dimensions', 'lazy', 'alt'
    current_value: str
    recommended_value: str
    estimated_savings_bytes: int = 0


@dataclass
class ImageAnalysis:
    """Site-wide image optimization analysis."""

    total_pages: int = 0
    total_images: int = 0

    # Format breakdown
    format_counts: dict = field(default_factory=dict)  # {'png': 50, 'jpg': 100}
    modern_format_percentage: float = 0.0  # WebP + AVIF percentage

    # Size metrics
    total_image_bytes: int = 0
    avg_image_bytes: int = 0
    largest_images: list = field(default_factory=list)

    # Optimization opportunities
    images_needing_modern_format: list = field(default_factory=list)
    images_missing_dimensions: list = field(default_factory=list)
    images_needing_lazy_load: list = field(default_factory=list)
    images_oversized: list = field(default_factory=list)

    # Lazy loading stats
    lazy_loaded_count: int = 0
    eager_loaded_count: int = 0
    lazy_load_percentage: float = 0.0

    # Alt text stats
    images_with_alt: int = 0
    images_without_alt: int = 0
    alt_coverage_percentage: float = 0.0

    # Estimated savings
    estimated_total_savings_bytes: int = 0
    estimated_savings_percentage: float = 0.0

    # All issues
    all_issues: list = field(default_factory=list)

    # Recommendations
    recommendations: list = field(default_factory=list)
