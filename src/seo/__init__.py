"""SEO Crawler and Analyzer using LLM."""

__version__ = "0.1.0"

from seo.crawler import WebCrawler
from seo.site_crawler import SiteCrawler
from seo.analyzer import SEOAnalyzer
from seo.llm import LLMClient
from seo.technical import TechnicalAnalyzer
from seo.content_quality import ContentQualityAnalyzer
from seo.advanced_analyzer import (
    SecurityAnalyzer,
    URLStructureAnalyzer,
    MobileSEOAnalyzer,
    InternationalSEOAnalyzer,
)
from seo.models import (
    PageMetadata,
    SEOScore,
    CrawlResult,
    TechnicalIssues,
    ContentQualityMetrics,
    SecurityAnalysis,
    URLStructureAnalysis,
    ICEScore,
    ComprehensiveSEOReport,
)
from seo.config import settings

# Infrastructure (ported from Spectrum per EPIC-SEO-INFRA-001)
from seo.infrastructure import (
    BrowserPool,
    BrowserHealth,
    PoolStatus,
    ContextMetrics,
    AdaptiveRateLimiter,
    TokenBucketLimiter,
    RateLimitConfig,
    ResourceMetrics,
)

# Intelligence (ported from Spectrum per EPIC-SEO-INFRA-001)
from seo.intelligence import (
    SiteProfile,
    PageProfile,
    FormProfile,
    SelectorEntry,
    SelectorLibrary,
    AICache,
    CacheEntry,
)

# Utils (ported from Spectrum per EPIC-SEO-INFRA-001)
from seo.utils import (
    detect_challenge,
    is_challenge_page,
    handle_challenge_if_present,
)

__all__ = [
    # Core
    "WebCrawler",
    "SiteCrawler",
    "SEOAnalyzer",
    "LLMClient",
    "TechnicalAnalyzer",
    "ContentQualityAnalyzer",
    "SecurityAnalyzer",
    "URLStructureAnalyzer",
    "MobileSEOAnalyzer",
    "InternationalSEOAnalyzer",
    # Models
    "PageMetadata",
    "SEOScore",
    "CrawlResult",
    "TechnicalIssues",
    "ContentQualityMetrics",
    "SecurityAnalysis",
    "URLStructureAnalysis",
    "ICEScore",
    "ComprehensiveSEOReport",
    "settings",
    # Infrastructure
    "BrowserPool",
    "BrowserHealth",
    "PoolStatus",
    "ContextMetrics",
    "AdaptiveRateLimiter",
    "TokenBucketLimiter",
    "RateLimitConfig",
    "ResourceMetrics",
    # Intelligence
    "SiteProfile",
    "PageProfile",
    "FormProfile",
    "SelectorEntry",
    "SelectorLibrary",
    "AICache",
    "CacheEntry",
    # Utils
    "detect_challenge",
    "is_challenge_page",
    "handle_challenge_if_present",
]
