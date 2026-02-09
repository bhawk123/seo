"""
Infrastructure Package.

Ported from Spectrum per EPIC-SEO-INFRA-001.
Enhanced with stealth browser backend per Epic 9.2.1.

Provides browser pooling and rate limiting for reliable parallel crawling.
"""

from .browser_pool import (
    BrowserPool,
    BrowserHealth,
    PoolStatus,
    ContextMetrics,
    UndetectedContext,
)
from .rate_limiter import (
    AdaptiveRateLimiter,
    TokenBucketLimiter,
    RateLimitConfig,
    ResourceMetrics,
)
from .undetected_browser import (
    UndetectedBrowser,
    UndetectedBrowserConfig,
    UndetectedBrowserPage,
    verify_stealth,
    get_stealth_script,
    STEALTH_SCRIPTS,
    COMBINED_STEALTH_SCRIPT,
)
from .performance_metrics import (
    BrowserPerformanceMetrics,
    LayoutShiftEntry,
    LongTaskEntry,
    ResourceTiming,
    inject_performance_observers,
    collect_performance_metrics,
    measure_page_performance,
)
from .proxy_rotation import (
    ProxyPool,
    ProxyPoolConfig,
    ProxyConfig,
    ProxyEntry,
    ProxyType,
    ProxyHealth,
    RotationStrategy,
    ProxyStats,
    load_proxies_from_file,
    create_proxy_pool_from_env,
)
from .timing_evasion import (
    TimingEvasion,
    TimingConfig,
    TimingProfile,
    TIMING_PROFILES,
    create_timing_evasion,
)
from .cross_browser import (
    CrossBrowserRunner,
    CrossBrowserConfig,
    CrossBrowserResult,
    BrowserResult,
    BrowserEngine,
    BrowserCapability,
    BROWSER_CAPABILITIES,
    has_capability,
    get_unsupported_capabilities,
    create_cross_browser_runner,
)

__all__ = [
    # Browser Pool
    "BrowserPool",
    "BrowserHealth",
    "PoolStatus",
    "ContextMetrics",
    "UndetectedContext",
    # Undetected Browser (Epic 9.2.1)
    "UndetectedBrowser",
    "UndetectedBrowserConfig",
    "UndetectedBrowserPage",
    "verify_stealth",
    "get_stealth_script",
    "STEALTH_SCRIPTS",
    "COMBINED_STEALTH_SCRIPT",
    # Rate Limiter
    "AdaptiveRateLimiter",
    "TokenBucketLimiter",
    "RateLimitConfig",
    "ResourceMetrics",
    # Performance Metrics (Gap #2)
    "BrowserPerformanceMetrics",
    "LayoutShiftEntry",
    "LongTaskEntry",
    "ResourceTiming",
    "inject_performance_observers",
    "collect_performance_metrics",
    "measure_page_performance",
    # Proxy Rotation (Gap #6)
    "ProxyPool",
    "ProxyPoolConfig",
    "ProxyConfig",
    "ProxyEntry",
    "ProxyType",
    "ProxyHealth",
    "RotationStrategy",
    "ProxyStats",
    "load_proxies_from_file",
    "create_proxy_pool_from_env",
    # Timing Evasion (Gap #7)
    "TimingEvasion",
    "TimingConfig",
    "TimingProfile",
    "TIMING_PROFILES",
    "create_timing_evasion",
    # Cross-Browser Testing (Gap #3)
    "CrossBrowserRunner",
    "CrossBrowserConfig",
    "CrossBrowserResult",
    "BrowserResult",
    "BrowserEngine",
    "BrowserCapability",
    "BROWSER_CAPABILITIES",
    "has_capability",
    "get_unsupported_capabilities",
    "create_cross_browser_runner",
]
