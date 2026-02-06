# src/seo/constants.py
"""Centralized constants for the SEO analyzer.

This module contains magic numbers and configuration values that are used
across multiple modules. For user-configurable thresholds, see config.py
and AnalysisThresholds.
"""

# =============================================================================
# Content Quality Constants
# =============================================================================

# Syllable threshold for classifying words as "difficult"
DIFFICULT_WORD_SYLLABLES = 3

# Percentage above which keyword density is considered too high (stuffing)
HIGH_KEYWORD_DENSITY_PERCENT = 3.0

# Minimum words needed for reliable readability analysis
MIN_WORDS_FOR_RELIABLE_ANALYSIS = 50

# Minimum word length to be considered a keyword
MIN_KEYWORD_LENGTH = 3

# Number of top keywords to track in analysis
TOP_KEYWORDS_COUNT = 10

# Maximum difficult word samples to include in evidence
MAX_DIFFICULT_WORD_SAMPLES = 10

# Flesch Reading Ease formula components (for documentation)
FLESCH_FORMULA = "206.835 - 1.015 * (words/sentences) - 84.6 * (syllables/words)"

# Grade level mapping for Flesch scores
GRADE_MAPPING = {
    (90, 100): "5th Grade",
    (80, 89): "6th Grade",
    (70, 79): "7th Grade",
    (60, 69): "8th-9th Grade",
    (50, 59): "10th-12th Grade",
    (30, 49): "College",
    (0, 29): "Graduate",
}


# =============================================================================
# Technical SEO Constants
# =============================================================================

# Maximum samples to include in evidence records
MAX_EVIDENCE_SAMPLES = 5

# Sample limit for report displays
REPORT_SAMPLE_LIMIT = 5

# Threshold for escalating image alt text severity
SEVERITY_ESCALATION_IMAGES_THRESHOLD = 5

# Page load time (seconds) for critical severity
SLOW_PAGE_CRITICAL_THRESHOLD_SECONDS = 5.0

# Word count threshold for critical thin content
THIN_CONTENT_CRITICAL_THRESHOLD = 100


# =============================================================================
# Crawler Constants
# =============================================================================

# Default request timeout in seconds
DEFAULT_REQUEST_TIMEOUT_SECONDS = 30

# Default maximum retries for failed requests
DEFAULT_MAX_RETRIES = 3

# Base for exponential backoff calculation
EXPONENTIAL_BACKOFF_BASE = 2

# Initial backoff delay in seconds
INITIAL_BACKOFF_DELAY_SECONDS = 2.0

# Maximum backoff delay in seconds (cap for exponential growth)
MAX_BACKOFF_DELAY_SECONDS = 30.0

# HTTP status codes that trigger user-agent rotation
HTTP_CODES_TRIGGER_UA_ROTATION = [401, 403]

# Default pages to crawl in site mode
DEFAULT_MAX_PAGES_TO_CRAWL = 50

# Default rate limit between requests (seconds)
DEFAULT_RATE_LIMIT_SECONDS = 0.5

# Default concurrent requests for async crawler
DEFAULT_MAX_CONCURRENT_REQUESTS = 10

# Maximum session errors before aborting crawl
MAX_SESSION_ERRORS_BEFORE_ABORT = 5

# Default PageSpeed Insights sample rate
DEFAULT_PSI_SAMPLE_RATE = 0.1

# Maximum page pool retries
MAX_PAGE_POOL_RETRIES = 3

# Crawl state file version
CRAWL_STATE_VERSION = 1


# =============================================================================
# Viewport and Display Constants
# =============================================================================

# Desktop viewport dimensions for browser crawling
DESKTOP_VIEWPORT_WIDTH = 1920
DESKTOP_VIEWPORT_HEIGHT = 1080

# Mobile viewport dimensions
MOBILE_VIEWPORT_WIDTH = 375
MOBILE_VIEWPORT_HEIGHT = 812


# =============================================================================
# Image Analysis Constants
# =============================================================================

# Default position after which images should use lazy loading
DEFAULT_LAZY_LOAD_THRESHOLD = 3

# Maximum characters for truncating image src in evidence
MAX_IMAGE_SRC_LENGTH = 100

# Sample limit for image evidence records
IMAGE_EVIDENCE_SAMPLE_LIMIT = 10


# =============================================================================
# Core Web Vitals Constants
# =============================================================================

# LCP thresholds (seconds)
LCP_GOOD_SECONDS = 2.5
LCP_POOR_SECONDS = 4.0

# INP thresholds (milliseconds)
INP_GOOD_MS = 200
INP_POOR_MS = 500

# CLS thresholds
CLS_GOOD_THRESHOLD = 0.1
CLS_POOR_THRESHOLD = 0.25

# Maximum LCP candidate elements to check
MAX_LCP_CANDIDATE_IMAGES = 10
MAX_LCP_CANDIDATE_H1S = 2

# Base render time estimate (seconds) for LCP calculation
BASE_RENDER_TIME_ESTIMATE_SECONDS = 0.5

# Threshold for "few blocking scripts" warning
BLOCKING_SCRIPTS_THRESHOLD = 3

# Threshold for "few CLS risks" warning
CLS_RISK_ELEMENTS_THRESHOLD = 5

# Image position after which lazy loading is expected
LAZY_LOAD_IMAGE_POSITION_THRESHOLD = 3


# =============================================================================
# URL Structure Constants
# =============================================================================

# URL length warning threshold (characters)
URL_LENGTH_WARNING_CHARS = 75

# URL length critical threshold (characters)
URL_LENGTH_CRITICAL_CHARS = 100


# =============================================================================
# Mobile SEO Constants
# =============================================================================

# Minimum base font size for readability (pixels)
MIN_BASE_FONT_SIZE_PX = 16

# Minimum touch target size for accessibility (pixels)
MIN_TOUCH_TARGET_SIZE_PX = 48

# Threshold for responsive image percentage
RESPONSIVE_IMAGE_THRESHOLD = 10


# =============================================================================
# Resource Analysis Constants
# =============================================================================

# Percentage thresholds for resource distribution warnings
HIGH_IMAGE_PERCENTAGE = 50.0
HIGH_JS_PERCENTAGE = 30.0

# Average page weight threshold (KB)
HIGH_AVG_PAGE_KB = 1500

# Limit for top heaviest pages in report
TOP_HEAVIEST_PAGES_LIMIT = 10


# =============================================================================
# Redirect Analysis Constants
# =============================================================================

# Maximum chain URLs to include in evidence
MAX_CHAIN_URLS_IN_EVIDENCE = 5

# Maximum redirect chains to store in analysis
MAX_ALL_CHAINS_TO_STORE = 50

# Percentage of pages with redirects considered high
HIGH_REDIRECT_PERCENTAGE_THRESHOLD = 10


# =============================================================================
# Social Meta Constants
# =============================================================================

# Scoring point values for Open Graph properties
OG_REQUIRED_POINTS = 15
OG_RECOMMENDED_POINTS = 5

# Scoring point values for Twitter Card properties
TWITTER_REQUIRED_POINTS = 25
TWITTER_RECOMMENDED_POINTS = 10


# =============================================================================
# Structured Data Constants
# =============================================================================

# Minimum rich results for "multiple" classification
MIN_RICH_RESULTS_THRESHOLD = 2

# Single rich result threshold
SINGLE_RICH_RESULT_THRESHOLD = 1


# =============================================================================
# Evidence and Reporting Constants
# =============================================================================

# General evidence sample limit
EVIDENCE_SAMPLE_LIMIT = 10

# Truncation length for URLs in evidence
MAX_URL_LENGTH_IN_EVIDENCE = 100

# Truncation length for content snippets
MAX_CONTENT_SNIPPET_LENGTH = 200
