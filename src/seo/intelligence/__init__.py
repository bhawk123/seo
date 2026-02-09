"""
Site Intelligence Package.

Ported from Spectrum per EPIC-SEO-INFRA-001.

Provides persistent storage and retrieval of learned site knowledge:
- Site profiles with metadata and history
- Selector libraries with confidence scoring
- AI response caching (content-addressable)
"""

from .site_profile import (
    SiteProfile,
    PageProfile,
    FormProfile,
    SelectorEntry,
    PageType,
    FormFieldType,
    ButtonIntent,
)
from .selector_library import SelectorLibrary, SelectorCandidate
from .ai_cache import AICache, CacheEntry
from .dynamic_selectors import (
    FrameworkType,
    SelectorStability,
    DynamicSelectorCandidate,
    FrameworkDetectionResult,
    DynamicSelectorLibrary,
    detect_framework,
    is_dynamic_value,
    generate_stable_selector,
    get_selector_with_fallbacks,
    analyze_selector_stability,
    dynamic_candidate_to_selector_entry,
    dynamic_candidate_to_selector_candidate,
    STABLE_ATTRIBUTES,
    DYNAMIC_PATTERNS,
)

__all__ = [
    # Site profiles
    "SiteProfile",
    "PageProfile",
    "FormProfile",
    "SelectorEntry",
    "PageType",
    "FormFieldType",
    "ButtonIntent",
    # Selectors
    "SelectorLibrary",
    "SelectorCandidate",
    # AI caching
    "AICache",
    "CacheEntry",
    # Dynamic selectors (Gap #4)
    "FrameworkType",
    "SelectorStability",
    "DynamicSelectorCandidate",
    "FrameworkDetectionResult",
    "DynamicSelectorLibrary",
    "detect_framework",
    "is_dynamic_value",
    "generate_stable_selector",
    "get_selector_with_fallbacks",
    "analyze_selector_stability",
    "dynamic_candidate_to_selector_entry",
    "dynamic_candidate_to_selector_candidate",
    "STABLE_ATTRIBUTES",
    "DYNAMIC_PATTERNS",
]
