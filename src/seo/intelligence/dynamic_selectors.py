"""
Dynamic Selector Handling for React/Vue Frameworks.

Implements Critical Gap #4: Dynamic selector handling (React/Vue).

Modern JavaScript frameworks generate dynamic class names, IDs, and attributes
that change between builds or page loads. This module provides strategies for
generating stable selectors that work across dynamic content.

Features:
- data-testid and data-cy selector detection (testing attributes)
- React-specific patterns (data-reactid, data-reactroot)
- Vue-specific patterns (data-v-*, v-bind attributes)
- CSS Modules pattern detection (hash-suffixed classes)
- Styled-components pattern detection
- Stable attribute prioritization
- Framework detection and adaptation
"""

import re
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class FrameworkType(str, Enum):
    """Detected JavaScript framework."""
    REACT = "react"
    VUE = "vue"
    ANGULAR = "angular"
    SVELTE = "svelte"
    UNKNOWN = "unknown"


class SelectorStability(str, Enum):
    """Stability level of a selector."""
    VERY_HIGH = "very_high"  # Test IDs, explicit stable attributes
    HIGH = "high"  # IDs, name attributes
    MEDIUM = "medium"  # Semantic classes, ARIA attributes
    LOW = "low"  # Generated classes, dynamic IDs
    VERY_LOW = "very_low"  # Index-based, positional


# Stable attribute patterns (in priority order)
STABLE_ATTRIBUTES = [
    # Testing attributes (highest stability)
    ("data-testid", SelectorStability.VERY_HIGH, 0.99),
    ("data-test-id", SelectorStability.VERY_HIGH, 0.99),
    ("data-cy", SelectorStability.VERY_HIGH, 0.99),  # Cypress
    ("data-test", SelectorStability.VERY_HIGH, 0.98),
    ("data-qa", SelectorStability.VERY_HIGH, 0.98),
    # Semantic attributes
    ("id", SelectorStability.HIGH, 0.90),  # Unless dynamic
    ("name", SelectorStability.HIGH, 0.92),
    ("aria-label", SelectorStability.MEDIUM, 0.85),
    ("aria-labelledby", SelectorStability.MEDIUM, 0.85),
    ("role", SelectorStability.MEDIUM, 0.80),
    ("type", SelectorStability.MEDIUM, 0.85),
    ("href", SelectorStability.MEDIUM, 0.75),
    ("placeholder", SelectorStability.MEDIUM, 0.70),
    # Framework-specific stable attributes
    ("data-action", SelectorStability.HIGH, 0.88),  # Stimulus/Rails
    ("data-controller", SelectorStability.HIGH, 0.88),
]

# Patterns indicating dynamic/unstable values
DYNAMIC_PATTERNS = [
    # CSS Modules (hash suffix)
    re.compile(r'^[a-zA-Z_-]+_[a-zA-Z0-9]{5,8}$'),
    # Styled-components
    re.compile(r'^sc-[a-zA-Z0-9]+-[a-zA-Z0-9]+$'),
    re.compile(r'^css-[a-zA-Z0-9]+$'),
    # Emotion
    re.compile(r'^css-[a-zA-Z0-9]+-[a-zA-Z0-9]+$'),
    # React/Vue generated
    re.compile(r'^[a-zA-Z]+__[a-zA-Z]+--[a-zA-Z0-9]+$'),  # BEM with hash
    re.compile(r'^_[a-zA-Z0-9]{8,}$'),  # Underscore prefix with hash
    # Random-looking IDs
    re.compile(r'^[a-f0-9]{8}-[a-f0-9]{4}-'),  # UUID prefix
    re.compile(r'^[a-zA-Z]+[0-9]{6,}$'),  # Letters then many numbers
    re.compile(r'^[0-9]+$'),  # Pure numbers
]

# Vue scoped style pattern
VUE_SCOPED_PATTERN = re.compile(r'data-v-[a-f0-9]{8}')

# React patterns
REACT_PATTERNS = {
    'root': re.compile(r'data-reactroot'),
    'id': re.compile(r'data-reactid'),
    'fiber': re.compile(r'__reactFiber'),
    'props': re.compile(r'__reactProps'),
}


@dataclass
class DynamicSelectorCandidate:
    """A selector candidate with stability analysis."""
    selector: str
    selector_type: str  # css, xpath, text
    stability: SelectorStability
    confidence: float
    attribute: Optional[str] = None
    framework_hint: Optional[FrameworkType] = None
    is_dynamic: bool = False
    dynamic_reason: Optional[str] = None


@dataclass
class FrameworkDetectionResult:
    """Result of framework detection."""
    framework: FrameworkType
    confidence: float
    indicators: List[str] = field(default_factory=list)
    version_hint: Optional[str] = None


def detect_framework(html: str) -> FrameworkDetectionResult:
    """
    Detect which JavaScript framework is used on a page.

    Args:
        html: Page HTML content

    Returns:
        FrameworkDetectionResult with detected framework
    """
    indicators = []
    framework = FrameworkType.UNKNOWN
    confidence = 0.0

    # React detection
    react_score = 0
    if 'data-reactroot' in html:
        react_score += 0.4
        indicators.append('data-reactroot')
    if '__NEXT_DATA__' in html:
        react_score += 0.3
        indicators.append('Next.js __NEXT_DATA__')
    if 'react' in html.lower() and 'react-dom' in html.lower():
        react_score += 0.2
        indicators.append('react/react-dom scripts')
    if '_reactRootContainer' in html:
        react_score += 0.3
        indicators.append('_reactRootContainer')

    # Vue detection
    vue_score = 0
    if VUE_SCOPED_PATTERN.search(html):
        vue_score += 0.4
        indicators.append('Vue scoped styles (data-v-*)')
    if '__VUE__' in html or '__vue__' in html:
        vue_score += 0.3
        indicators.append('__VUE__ global')
    if 'v-cloak' in html or 'v-if' in html or 'v-for' in html:
        vue_score += 0.2
        indicators.append('Vue directives')
    if '__NUXT__' in html:
        vue_score += 0.3
        indicators.append('Nuxt.js __NUXT__')

    # Angular detection
    angular_score = 0
    if 'ng-version' in html:
        angular_score += 0.4
        indicators.append('ng-version')
    if '_nghost' in html or '_ngcontent' in html:
        angular_score += 0.3
        indicators.append('Angular host/content attributes')
    if 'ng-' in html and ('ng-app' in html or 'ng-controller' in html):
        angular_score += 0.2
        indicators.append('AngularJS directives')

    # Svelte detection
    svelte_score = 0
    if 'svelte' in html.lower():
        svelte_score += 0.3
        indicators.append('Svelte reference')
    if re.search(r'class="svelte-[a-z0-9]+"', html):
        svelte_score += 0.4
        indicators.append('Svelte class pattern')

    # Determine winner
    scores = {
        FrameworkType.REACT: react_score,
        FrameworkType.VUE: vue_score,
        FrameworkType.ANGULAR: angular_score,
        FrameworkType.SVELTE: svelte_score,
    }

    max_score = max(scores.values())
    if max_score > 0.3:
        for fw, score in scores.items():
            if score == max_score:
                framework = fw
                confidence = min(score, 1.0)
                break

    return FrameworkDetectionResult(
        framework=framework,
        confidence=confidence,
        indicators=indicators
    )


def is_dynamic_value(value: str) -> Tuple[bool, Optional[str]]:
    """
    Check if a value appears to be dynamically generated.

    Args:
        value: Attribute value to check

    Returns:
        (is_dynamic, reason) tuple
    """
    if not value:
        return False, None

    for pattern in DYNAMIC_PATTERNS:
        if pattern.match(value):
            return True, f"Matches dynamic pattern: {pattern.pattern}"

    # Check for very long random-looking strings
    if len(value) > 20 and not ' ' in value:
        # Count entropy-like characteristics
        digits = sum(1 for c in value if c.isdigit())
        if digits > len(value) * 0.3:
            return True, "High digit ratio suggests generated value"

    return False, None


def generate_stable_selector(
    element: Dict[str, Any],
    framework: Optional[FrameworkType] = None,
    prefer_test_ids: bool = True
) -> List[DynamicSelectorCandidate]:
    """
    Generate stable selector candidates for an element.

    Args:
        element: Dict with 'tag', 'attributes', 'text', 'parent' keys
        framework: Detected framework (affects selector strategy)
        prefer_test_ids: Prioritize testing attributes

    Returns:
        List of selector candidates ordered by stability
    """
    candidates = []
    tag = element.get('tag', 'div').lower()
    attrs = element.get('attributes', {})
    text = element.get('text', '').strip()

    # Check stable attributes first
    for attr_name, stability, base_confidence in STABLE_ATTRIBUTES:
        if attr_name in attrs:
            value = attrs[attr_name]
            is_dynamic, reason = is_dynamic_value(value)

            if is_dynamic:
                # Skip dynamic values for high-stability attributes
                if stability in (SelectorStability.VERY_HIGH, SelectorStability.HIGH):
                    continue
                confidence = base_confidence * 0.5
            else:
                confidence = base_confidence

            # Build selector
            if attr_name == 'id' and not is_dynamic:
                selector = f"#{value}"
            else:
                selector = f"[{attr_name}=\"{value}\"]"

            candidates.append(DynamicSelectorCandidate(
                selector=selector,
                selector_type='css',
                stability=stability,
                confidence=confidence,
                attribute=attr_name,
                framework_hint=framework,
                is_dynamic=is_dynamic,
                dynamic_reason=reason
            ))

    # Check classes for stable ones
    classes = attrs.get('class', '').split()
    stable_classes = []
    for cls in classes:
        is_dynamic, reason = is_dynamic_value(cls)
        if not is_dynamic:
            # Check if it's a semantic class
            semantic_patterns = [
                r'^(btn|button|input|form|nav|header|footer|main|article|section)',
                r'^(container|wrapper|content|sidebar|menu|modal|dialog)',
                r'^(primary|secondary|success|danger|warning|info)',
                r'^(active|disabled|hidden|visible|selected|checked)',
            ]
            is_semantic = any(re.match(p, cls, re.I) for p in semantic_patterns)
            if is_semantic:
                stable_classes.append((cls, SelectorStability.MEDIUM, 0.70))
            else:
                stable_classes.append((cls, SelectorStability.LOW, 0.50))

    for cls, stability, confidence in stable_classes[:3]:  # Top 3 stable classes
        candidates.append(DynamicSelectorCandidate(
            selector=f".{cls}",
            selector_type='css',
            stability=stability,
            confidence=confidence,
            attribute='class',
            framework_hint=framework
        ))

    # Text-based selector (for buttons, links)
    if text and tag in ('button', 'a', 'label', 'span') and len(text) < 50:
        # Escape quotes in text
        safe_text = text.replace('"', '\\"')
        candidates.append(DynamicSelectorCandidate(
            selector=f'{tag}:has-text("{safe_text}")',
            selector_type='css',
            stability=SelectorStability.MEDIUM,
            confidence=0.75,
            attribute='text'
        ))

    # Framework-specific selectors
    if framework == FrameworkType.VUE:
        # Look for Vue ref or v-bind attributes
        for attr, value in attrs.items():
            if attr.startswith('v-') or attr == 'ref':
                candidates.append(DynamicSelectorCandidate(
                    selector=f"[{attr}=\"{value}\"]",
                    selector_type='css',
                    stability=SelectorStability.MEDIUM,
                    confidence=0.65,
                    attribute=attr,
                    framework_hint=FrameworkType.VUE
                ))

    # Sort by confidence
    candidates.sort(key=lambda c: c.confidence, reverse=True)

    return candidates


def get_selector_with_fallbacks(
    element: Dict[str, Any],
    html: Optional[str] = None,
    max_fallbacks: int = 3
) -> List[str]:
    """
    Get selector with fallbacks, auto-detecting framework.

    Args:
        element: Element dict with tag, attributes, text
        html: Optional page HTML for framework detection
        max_fallbacks: Maximum number of fallback selectors

    Returns:
        List of selectors in priority order
    """
    framework = None
    if html:
        detection = detect_framework(html)
        if detection.confidence > 0.5:
            framework = detection.framework
            logger.debug(f"Detected framework: {framework.value} (confidence: {detection.confidence})")

    candidates = generate_stable_selector(element, framework)

    # Return top selectors
    return [c.selector for c in candidates[:max_fallbacks]]


def analyze_selector_stability(selector: str, html: str) -> DynamicSelectorCandidate:
    """
    Analyze an existing selector for stability.

    Args:
        selector: CSS selector to analyze
        html: Page HTML for context

    Returns:
        DynamicSelectorCandidate with stability analysis
    """
    stability = SelectorStability.MEDIUM
    confidence = 0.5
    is_dynamic = False
    reason = None

    # Check for test ID patterns
    if 'data-testid' in selector or 'data-cy' in selector or 'data-test' in selector:
        stability = SelectorStability.VERY_HIGH
        confidence = 0.98

    # Check for ID selector
    elif selector.startswith('#'):
        id_value = selector[1:].split('[')[0].split('.')[0]
        is_dynamic, reason = is_dynamic_value(id_value)
        if is_dynamic:
            stability = SelectorStability.LOW
            confidence = 0.4
        else:
            stability = SelectorStability.HIGH
            confidence = 0.90

    # Check for class selector
    elif selector.startswith('.'):
        class_name = selector[1:].split('[')[0].split('.')[0]
        is_dynamic, reason = is_dynamic_value(class_name)
        if is_dynamic:
            stability = SelectorStability.VERY_LOW
            confidence = 0.3
        else:
            stability = SelectorStability.MEDIUM
            confidence = 0.60

    # Check for attribute selector
    elif '[' in selector:
        match = re.search(r'\[([^=]+)=', selector)
        if match:
            attr = match.group(1)
            for attr_name, attr_stability, attr_conf in STABLE_ATTRIBUTES:
                if attr == attr_name:
                    stability = attr_stability
                    confidence = attr_conf
                    break

    # Detect framework from HTML
    detection = detect_framework(html)

    return DynamicSelectorCandidate(
        selector=selector,
        selector_type='css',
        stability=stability,
        confidence=confidence,
        is_dynamic=is_dynamic,
        dynamic_reason=reason,
        framework_hint=detection.framework if detection.confidence > 0.5 else None
    )


# =============================================================================
# SelectorLibrary Integration (HIGH Priority - Gemini Recommendation #4)
# =============================================================================

def dynamic_candidate_to_selector_entry(
    candidate: DynamicSelectorCandidate,
) -> "SelectorEntry":
    """
    Convert a DynamicSelectorCandidate to a SelectorEntry for library storage.

    Args:
        candidate: The dynamic selector candidate

    Returns:
        SelectorEntry compatible with SelectorLibrary
    """
    from .site_profile import SelectorEntry

    return SelectorEntry(
        selector=candidate.selector,
        selector_type=candidate.selector_type,
        confidence=candidate.confidence,
    )


def dynamic_candidate_to_selector_candidate(
    candidate: DynamicSelectorCandidate,
    element_type: str = "unknown",
    purpose: str = "unknown",
) -> "SelectorCandidate":
    """
    Convert a DynamicSelectorCandidate to a SelectorCandidate.

    Args:
        candidate: The dynamic selector candidate
        element_type: Type of element (button, input, etc.)
        purpose: Purpose of the selector

    Returns:
        SelectorCandidate compatible with SelectorLibrary
    """
    from .selector_library import SelectorCandidate

    # Map stability to specificity score
    specificity_map = {
        SelectorStability.VERY_HIGH: 100,
        SelectorStability.HIGH: 80,
        SelectorStability.MEDIUM: 50,
        SelectorStability.LOW: 30,
        SelectorStability.VERY_LOW: 10,
    }

    return SelectorCandidate(
        selector=candidate.selector,
        selector_type=candidate.selector_type,
        element_type=element_type,
        purpose=purpose,
        specificity=specificity_map.get(candidate.stability, 50),
        stability_score=candidate.confidence,
        attributes={candidate.attribute: ""} if candidate.attribute else {},
    )


class DynamicSelectorLibrary:
    """
    Integration layer between dynamic selector analysis and SelectorLibrary.

    Combines framework-aware selector generation with library persistence
    and confidence tracking. Discovered stable selectors are automatically
    fed into the SelectorLibrary for cross-session learning.

    Supports manual framework overrides for hybrid sites or when auto-detection
    fails (Gemini recommendation #5).
    """

    def __init__(self, library: Optional["SelectorLibrary"] = None):
        """
        Initialize with optional SelectorLibrary.

        Args:
            library: Existing SelectorLibrary instance, or None to create new
        """
        if library is None:
            from .selector_library import SelectorLibrary
            library = SelectorLibrary()
        self._library = library
        self._framework_cache: Dict[str, FrameworkDetectionResult] = {}
        self._framework_overrides: Dict[str, FrameworkType] = {}  # Manual overrides

    @property
    def library(self) -> "SelectorLibrary":
        """Get the underlying SelectorLibrary."""
        return self._library

    def set_framework_override(self, site_id: str, framework: FrameworkType) -> None:
        """
        Manually override framework detection for a site.

        Use this when auto-detection fails or for hybrid sites that use
        multiple frameworks. The override takes precedence over auto-detection.

        Args:
            site_id: Site identifier
            framework: Framework to use for this site
        """
        self._framework_overrides[site_id] = framework
        # Clear cached detection so override takes effect
        if site_id in self._framework_cache:
            del self._framework_cache[site_id]
        logger.info(f"Framework override set for {site_id}: {framework.value}")

    def clear_framework_override(self, site_id: str) -> None:
        """
        Clear manual framework override for a site.

        Removes the override and allows auto-detection to resume.

        Args:
            site_id: Site identifier
        """
        if site_id in self._framework_overrides:
            del self._framework_overrides[site_id]
            # Clear cache so next detection is fresh
            if site_id in self._framework_cache:
                del self._framework_cache[site_id]
            logger.info(f"Framework override cleared for {site_id}")

    def get_framework_override(self, site_id: str) -> Optional[FrameworkType]:
        """
        Get the manual framework override for a site, if any.

        Args:
            site_id: Site identifier

        Returns:
            FrameworkType if override is set, None otherwise
        """
        return self._framework_overrides.get(site_id)

    def detect_and_cache_framework(self, site_id: str, html: str) -> FrameworkDetectionResult:
        """
        Detect framework and cache result for site.

        Respects manual overrides - if an override is set, returns that
        framework with 1.0 confidence instead of auto-detecting.

        Args:
            site_id: Site identifier
            html: Page HTML content

        Returns:
            FrameworkDetectionResult
        """
        # Check for manual override first
        if site_id in self._framework_overrides:
            override = self._framework_overrides[site_id]
            return FrameworkDetectionResult(
                framework=override,
                confidence=1.0,
                indicators=[f"Manual override: {override.value}"],
            )

        # Auto-detect if not cached
        if site_id not in self._framework_cache:
            self._framework_cache[site_id] = detect_framework(html)
        return self._framework_cache[site_id]

    def generate_and_store_selectors(
        self,
        site_id: str,
        purpose: str,
        element: Dict[str, Any],
        html: Optional[str] = None,
    ) -> List[DynamicSelectorCandidate]:
        """
        Generate stable selectors and store the best one in the library.

        Args:
            site_id: Site identifier for storage
            purpose: Purpose of the selector (e.g., "submit_button", "email_field")
            element: Element dict with tag, attributes, text
            html: Optional page HTML for framework detection

        Returns:
            List of generated candidates
        """
        # Detect framework if HTML provided
        framework = None
        if html:
            detection = self.detect_and_cache_framework(site_id, html)
            if detection.confidence > 0.5:
                framework = detection.framework

        # Generate candidates
        candidates = generate_stable_selector(element, framework)

        if not candidates:
            return []

        # Store the best (highest confidence) non-dynamic selector
        for candidate in candidates:
            if not candidate.is_dynamic:
                entry = dynamic_candidate_to_selector_entry(candidate)

                # Add alternatives from other candidates
                entry.alternatives = [
                    c.selector for c in candidates[1:4]
                    if not c.is_dynamic and c.selector != candidate.selector
                ]

                self._library.store_selector(site_id, purpose, entry)
                logger.debug(
                    f"Stored selector for {site_id}/{purpose}: {candidate.selector} "
                    f"(confidence: {candidate.confidence:.2f})"
                )
                break

        return candidates

    def get_best_selector(
        self,
        site_id: str,
        purpose: str,
        element: Optional[Dict[str, Any]] = None,
        html: Optional[str] = None,
    ) -> Optional[str]:
        """
        Get the best selector, using library or generating new.

        Args:
            site_id: Site identifier
            purpose: Selector purpose
            element: Element dict (if generation needed)
            html: Page HTML (for framework detection)

        Returns:
            Best selector string or None
        """
        # Try library first
        entry = self._library.get_selector(site_id, purpose)
        if entry and entry.confidence > 0.5:
            return entry.selector

        # Generate new if element provided
        if element:
            candidates = self.generate_and_store_selectors(site_id, purpose, element, html)
            if candidates:
                return candidates[0].selector

        return None

    def record_success(self, site_id: str, purpose: str, selector: str) -> None:
        """
        Record successful selector usage.

        Updates confidence in both library and logs success for analytics.

        Args:
            site_id: Site identifier
            purpose: Selector purpose
            selector: The selector that succeeded
        """
        self._library.record_success(site_id, purpose)
        logger.debug(f"Recorded success for {site_id}/{purpose}: {selector}")

    def record_failure(self, site_id: str, purpose: str, selector: str) -> None:
        """
        Record failed selector usage.

        Updates confidence and may trigger fallback discovery.

        Args:
            site_id: Site identifier
            purpose: Selector purpose
            selector: The selector that failed
        """
        self._library.record_failure(site_id, purpose)
        logger.info(f"Recorded failure for {site_id}/{purpose}: {selector}")

    def analyze_and_update(
        self,
        site_id: str,
        purpose: str,
        selector: str,
        html: str,
    ) -> Dict[str, Any]:
        """
        Analyze existing selector and return ranked alternatives if unstable.

        If the selector is detected as dynamic/unstable, returns a ranked list
        of alternative selectors from the library, sorted by confidence.

        Args:
            site_id: Site identifier
            purpose: Selector purpose
            selector: Current selector to analyze
            html: Page HTML for analysis

        Returns:
            Dict with analysis result and ranked alternatives:
            {
                'analysis': DynamicSelectorCandidate,
                'is_unstable': bool,
                'alternatives': [  # Ranked list, best first
                    {'selector': str, 'confidence': float, 'reason': str},
                    ...
                ],
                'recommended_action': str  # 'keep', 'replace', 'review'
            }
        """
        analysis = analyze_selector_stability(selector, html)
        result = {
            'analysis': analysis,
            'is_unstable': False,
            'alternatives': [],
            'recommended_action': 'keep',
        }

        if analysis.is_dynamic or analysis.stability in (
            SelectorStability.LOW,
            SelectorStability.VERY_LOW
        ):
            result['is_unstable'] = True
            logger.warning(
                f"Unstable selector detected for {site_id}/{purpose}: {selector} "
                f"(reason: {analysis.dynamic_reason})"
            )

            # Build ranked list of alternatives from library
            fallbacks = self._library.get_selector_with_fallbacks(site_id, purpose)
            ranked_alternatives = []

            for fallback in fallbacks:
                if fallback.selector != selector:
                    fb_analysis = analyze_selector_stability(fallback.selector, html)
                    ranked_alternatives.append({
                        'selector': fallback.selector,
                        'confidence': fb_analysis.confidence,
                        'stability': fb_analysis.stability.value,
                        'is_dynamic': fb_analysis.is_dynamic,
                        'reason': f"Library fallback (original confidence: {fallback.confidence:.2f})",
                    })

            # Sort by confidence (highest first)
            ranked_alternatives.sort(key=lambda x: x['confidence'], reverse=True)
            result['alternatives'] = ranked_alternatives

            # Determine recommended action
            if ranked_alternatives and ranked_alternatives[0]['confidence'] > analysis.confidence:
                result['recommended_action'] = 'replace'
                best_alt = ranked_alternatives[0]
                logger.info(
                    f"Recommended replacement: {best_alt['selector']} "
                    f"(confidence: {best_alt['confidence']:.2f} vs {analysis.confidence:.2f})"
                )
            elif ranked_alternatives:
                result['recommended_action'] = 'review'
            else:
                result['recommended_action'] = 'review'  # No alternatives, needs manual review

        return result

    def add_framework_patterns(self, framework: FrameworkType) -> None:
        """
        Add global patterns specific to a framework.

        Populates the library with common patterns for React, Vue, etc.

        Args:
            framework: Detected framework
        """
        patterns = {
            FrameworkType.REACT: {
                "submit_button": [
                    "[data-testid='submit']",
                    "button[type='submit']",
                    "[role='button'][type='submit']",
                ],
                "input_field": [
                    "[data-testid='input']",
                    "input[name]",
                    "[role='textbox']",
                ],
                "form": [
                    "form[data-testid]",
                    "form[name]",
                    "[role='form']",
                ],
            },
            FrameworkType.VUE: {
                "submit_button": [
                    "[data-cy='submit']",
                    "button[type='submit']",
                    ".v-btn[type='submit']",
                ],
                "input_field": [
                    "[data-cy='input']",
                    ".v-text-field input",
                    "input[name]",
                ],
            },
        }

        framework_patterns = patterns.get(framework, {})
        for purpose, selectors in framework_patterns.items():
            for selector in selectors:
                self._library.add_global_pattern(purpose, selector)

        logger.debug(f"Added global patterns for {framework.value}")

    def stats(self) -> Dict[str, Any]:
        """Get combined statistics including override information."""
        lib_stats = self._library.stats()
        return {
            **lib_stats,
            "frameworks_cached": len(self._framework_cache),
            "frameworks_overridden": len(self._framework_overrides),
            "framework_details": {
                site: {
                    "framework": det.framework.value,
                    "confidence": det.confidence,
                    "is_override": site in self._framework_overrides,
                }
                for site, det in self._framework_cache.items()
            },
            "overrides": {
                site: framework.value
                for site, framework in self._framework_overrides.items()
            },
        }
