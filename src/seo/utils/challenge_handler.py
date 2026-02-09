"""
Challenge/CAPTCHA detection and human intervention handler.

Ported from Spectrum per EPIC-SEO-INFRA-001 (STORY-INFRA-006).
Enhanced per Epic 9.2.2 and 9.2.3 for reCAPTCHA version detection and blocking check.

This module provides utilities for detecting bot challenges (CAPTCHA, Akamai, etc.)
and pausing test execution for manual intervention.

Usage:
    pytest tests/ --headed --pause-on-challenge

When a challenge is detected, the test will pause and display instructions
for the human operator to solve it manually.
"""
import os
import sys
import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List

from playwright.sync_api import Page

logger = logging.getLogger(__name__)


# =============================================================================
# reCAPTCHA Detection Result (Epic 9.2.2)
# =============================================================================

@dataclass
class RecaptchaDetectionResult:
    """
    Structured result of reCAPTCHA detection.

    Implements Epic 9.2.2 requirements for version identification
    and automation impact assessment.
    """
    detected: bool = False
    version: Optional[str] = None  # v2_checkbox, v2_invisible, v3, enterprise, None
    automation_impact: str = "none"  # none, low, medium, high
    indicators: List[str] = field(default_factory=list)
    timestamp: Optional[datetime] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization or evidence."""
        return {
            "detected": self.detected,
            "version": self.version,
            "automation_impact": self.automation_impact,
            "indicators": self.indicators,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }


@dataclass
class BlockingCheckResult:
    """
    Result of reCAPTCHA blocking check (Epic 9.2.3).
    """
    blocked: bool = False
    challenge_visible: bool = False
    should_skip: bool = False
    message: Optional[str] = None
    wait_time_seconds: float = 0.0
    resolved: bool = False
    timestamp: Optional[datetime] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization or evidence."""
        return {
            "blocked": self.blocked,
            "challenge_visible": self.challenge_visible,
            "should_skip": self.should_skip,
            "message": self.message,
            "wait_time_seconds": self.wait_time_seconds,
            "resolved": self.resolved,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }


# =============================================================================
# Challenge Detection Selectors
# =============================================================================

CHALLENGE_INDICATORS = {
    # reCAPTCHA
    "recaptcha_iframe": "iframe[src*='recaptcha'], iframe[title*='reCAPTCHA']",
    "recaptcha_checkbox": ".recaptcha-checkbox, #recaptcha-anchor",
    "recaptcha_challenge": ".recaptcha-challenge, #rc-imageselect",

    # hCaptcha
    "hcaptcha_iframe": "iframe[src*='hcaptcha']",
    "hcaptcha_checkbox": ".hcaptcha-box, #hcaptcha",

    # Akamai Bot Manager
    "akamai_challenge": "#sec-cpt-if, #ak-challenge",
    "akamai_wait": "[class*='ak-challenge'], [class*='akamai']",

    # Generic challenge indicators
    "challenge_text": "text=/verify you('re| are) human/i, text=/bot detection/i",
    "blocked_text": "text=/access denied/i, text=/blocked/i, text=/suspicious activity/i",

    # Cloudflare
    "cloudflare_challenge": "#cf-challenge-running, .cf-browser-verification",
    "cloudflare_turnstile": "iframe[src*='challenges.cloudflare']",
}

# URL patterns that indicate a challenge page
CHALLENGE_URL_PATTERNS = [
    "captcha",
    "challenge",
    "verify",
    "blocked",
    "security-check",
]


# =============================================================================
# Challenge Detection
# =============================================================================

def detect_challenge(page: Page) -> Optional[str]:
    """
    Detect if the current page has a CAPTCHA or bot challenge.

    Args:
        page: Playwright Page instance

    Returns:
        Name of detected challenge type, or None if no challenge found
    """
    # Check URL patterns
    current_url = page.url.lower()
    for pattern in CHALLENGE_URL_PATTERNS:
        if pattern in current_url:
            return f"url_pattern:{pattern}"

    # Check for challenge elements
    for name, selector in CHALLENGE_INDICATORS.items():
        try:
            if page.locator(selector).count() > 0:
                return name
        except Exception:
            continue

    return None


def is_challenge_page(page: Page) -> bool:
    """Check if current page has any challenge."""
    return detect_challenge(page) is not None


# =============================================================================
# Human Intervention
# =============================================================================

def pause_for_human(
    page: Page,
    reason: str = "Challenge detected",
    instructions: Optional[str] = None
) -> None:
    """
    Pause test execution for human intervention.

    Displays a message in the console and waits for the user to press Enter
    after manually resolving the challenge in the browser.

    Args:
        page: Playwright Page instance
        reason: Why the pause was triggered
        instructions: Optional specific instructions for the user
    """
    # Build the message
    border = "=" * 70
    message = f"""
{border}
MANUAL INTERVENTION REQUIRED
{border}

Reason: {reason}
Current URL: {page.url}

"""
    if instructions:
        message += f"Instructions:\n{instructions}\n\n"
    else:
        message += """Instructions:
1. Look at the browser window
2. Complete the CAPTCHA or challenge manually
3. Wait for the page to load after solving
4. Return here and press ENTER to continue

"""
    message += f"{border}\n"

    # Print to console
    print(message, file=sys.stderr)

    # Wait for user input
    try:
        input(">>> Press ENTER when ready to continue...")
    except EOFError:
        # Running in non-interactive mode, wait a bit and continue
        print("Non-interactive mode - waiting 30 seconds...", file=sys.stderr)
        page.wait_for_timeout(30000)

    print("\nContinuing test execution...\n", file=sys.stderr)


def handle_challenge_if_present(
    page: Page,
    auto_pause: bool = True
) -> bool:
    """
    Check for challenges and optionally pause for human intervention.

    Args:
        page: Playwright Page instance
        auto_pause: Whether to automatically pause if challenge detected

    Returns:
        True if a challenge was detected (and handled), False otherwise
    """
    challenge = detect_challenge(page)

    if challenge:
        if auto_pause:
            pause_for_human(
                page,
                reason=f"Challenge detected: {challenge}",
                instructions=get_challenge_instructions(challenge)
            )
        return True

    return False


def get_challenge_instructions(challenge_type: str) -> str:
    """Get specific instructions for a challenge type."""
    instructions = {
        "recaptcha_iframe": "Click the reCAPTCHA checkbox and complete any image challenges.",
        "recaptcha_checkbox": "Click the 'I'm not a robot' checkbox.",
        "recaptcha_challenge": "Complete the image selection challenge.",
        "hcaptcha_iframe": "Complete the hCaptcha challenge.",
        "hcaptcha_checkbox": "Click the hCaptcha checkbox.",
        "akamai_challenge": "Wait for Akamai verification to complete, or solve any puzzle.",
        "akamai_wait": "Wait for Akamai bot detection to complete.",
        "cloudflare_challenge": "Wait for Cloudflare verification to complete.",
        "cloudflare_turnstile": "Complete the Cloudflare Turnstile challenge.",
        "challenge_text": "Complete the human verification challenge shown.",
        "blocked_text": "The page indicates access is blocked. Try refreshing or check if IP is blocked.",
    }

    for key, instruction in instructions.items():
        if key in challenge_type:
            return instruction

    return "Complete any challenge shown in the browser window."


# =============================================================================
# Enhanced reCAPTCHA Detection (Epic 9.2.2)
# =============================================================================

# Version-specific selectors for reCAPTCHA
RECAPTCHA_VERSION_SELECTORS = {
    "v2_checkbox": [
        ".g-recaptcha",
        "iframe[src*='recaptcha/api2/anchor']",
        "#recaptcha-anchor",
        ".recaptcha-checkbox",
    ],
    "v2_invisible": [
        ".g-recaptcha[data-size='invisible']",
        "iframe[src*='recaptcha/api2/bframe']",
        ".grecaptcha-badge",
    ],
    "v3": [
        "script[src*='recaptcha/api.js?render=']",
        "script[src*='recaptcha/enterprise.js?render=']",
        "[data-sitekey]:not(.g-recaptcha)",  # v3 uses sitekey without .g-recaptcha
    ],
    "enterprise": [
        "script[src*='recaptcha/enterprise.js']",
        ".grecaptcha-enterprise",
        "iframe[src*='recaptcha/enterprise']",
    ],
}

# Automation impact by version
RECAPTCHA_IMPACT = {
    "v2_checkbox": "medium",
    "v2_invisible": "medium",
    "v3": "low",  # v3 is score-based, less blocking
    "enterprise": "high",  # Enterprise has advanced detection
}


def detect_recaptcha(page: Page) -> RecaptchaDetectionResult:
    """
    Detect reCAPTCHA with version identification.

    Implements Epic 9.2.2 requirements for structured detection result.

    Args:
        page: Playwright Page instance

    Returns:
        RecaptchaDetectionResult with version and automation impact
    """
    result = RecaptchaDetectionResult()

    # Check each version in order of specificity
    for version, selectors in RECAPTCHA_VERSION_SELECTORS.items():
        for selector in selectors:
            try:
                if page.locator(selector).count() > 0:
                    result.indicators.append(selector)
                    if result.version is None:
                        # Use first detected version (most specific wins)
                        result.version = version
            except Exception:
                continue

    # Set detection status and impact
    if result.version:
        result.detected = True
        result.automation_impact = RECAPTCHA_IMPACT.get(result.version, "medium")
    else:
        # Check for generic reCAPTCHA indicators
        generic_selectors = [
            "iframe[src*='recaptcha']",
            "iframe[title*='reCAPTCHA']",
            "script[src*='recaptcha']",
        ]
        for selector in generic_selectors:
            try:
                if page.locator(selector).count() > 0:
                    result.detected = True
                    result.indicators.append(selector)
                    result.automation_impact = "medium"
                    break
            except Exception:
                continue

    if result.detected:
        logger.info(
            f"reCAPTCHA detected: version={result.version}, "
            f"impact={result.automation_impact}"
        )

    return result


# =============================================================================
# reCAPTCHA Blocking Check (Epic 9.2.3)
# =============================================================================

def check_recaptcha_blocking(
    page: Page,
    auto_resolve_timeout: float = 5.0,
    ci_behavior: str = "skip_in_ci",
) -> BlockingCheckResult:
    """
    Check if a reCAPTCHA challenge is actively blocking progress.

    Implements Epic 9.2.3 requirements for blocking detection with timeout.

    Args:
        page: Playwright Page instance
        auto_resolve_timeout: Seconds to wait for auto-resolution
        ci_behavior: How to behave in CI ("skip_in_ci", "fail_in_ci")

    Returns:
        BlockingCheckResult with blocking status
    """
    result = BlockingCheckResult()

    # Check if running in CI
    is_ci = os.environ.get("CI", "").lower() in ("true", "1", "yes")

    # Check for visible challenge
    challenge_selectors = [
        ".recaptcha-challenge:visible",
        "#rc-imageselect:visible",
        "iframe[src*='recaptcha/api2/bframe']:visible",
    ]

    for selector in challenge_selectors:
        try:
            if page.locator(selector).count() > 0:
                result.challenge_visible = True
                break
        except Exception:
            continue

    if not result.challenge_visible:
        # No visible challenge, not blocking
        return result

    # Challenge is visible - check CI behavior
    if is_ci and ci_behavior == "skip_in_ci":
        result.blocked = True
        result.should_skip = True
        result.message = "reCAPTCHA challenge detected in CI environment - skipping"
        logger.warning(result.message)
        return result

    # Wait for auto-resolution
    logger.info(f"reCAPTCHA challenge visible, waiting {auto_resolve_timeout}s for resolution...")

    start_time = asyncio.get_event_loop().time() if asyncio.get_event_loop().is_running() else 0
    wait_interval = 0.5
    elapsed = 0.0

    while elapsed < auto_resolve_timeout:
        try:
            page.wait_for_timeout(int(wait_interval * 1000))
        except Exception:
            pass

        elapsed += wait_interval
        result.wait_time_seconds = elapsed

        # Check if challenge resolved
        still_visible = False
        for selector in challenge_selectors:
            try:
                if page.locator(selector).count() > 0:
                    still_visible = True
                    break
            except Exception:
                continue

        if not still_visible:
            result.resolved = True
            result.blocked = False
            result.message = f"reCAPTCHA challenge resolved after {elapsed:.1f}s"
            logger.info(result.message)
            return result

    # Timeout exceeded
    result.blocked = True
    result.should_skip = True
    result.message = f"reCAPTCHA challenge not resolved after {auto_resolve_timeout}s timeout"
    logger.warning(result.message)

    return result


async def check_recaptcha_blocking_async(
    page,
    auto_resolve_timeout: float = 5.0,
    ci_behavior: str = "skip_in_ci",
) -> BlockingCheckResult:
    """
    Async version of reCAPTCHA blocking check.

    Args:
        page: Async Playwright Page instance
        auto_resolve_timeout: Seconds to wait for auto-resolution
        ci_behavior: How to behave in CI ("skip_in_ci", "fail_in_ci")

    Returns:
        BlockingCheckResult with blocking status
    """
    result = BlockingCheckResult()

    # Check if running in CI
    is_ci = os.environ.get("CI", "").lower() in ("true", "1", "yes")

    # Check for visible challenge
    challenge_selectors = [
        ".recaptcha-challenge",
        "#rc-imageselect",
        "iframe[src*='recaptcha/api2/bframe']",
    ]

    for selector in challenge_selectors:
        try:
            count = await page.locator(selector).count()
            if count > 0:
                result.challenge_visible = True
                break
        except Exception:
            continue

    if not result.challenge_visible:
        return result

    # Challenge is visible - check CI behavior
    if is_ci and ci_behavior == "skip_in_ci":
        result.blocked = True
        result.should_skip = True
        result.message = "reCAPTCHA challenge detected in CI environment - skipping"
        logger.warning(result.message)
        return result

    # Wait for auto-resolution
    logger.info(f"reCAPTCHA challenge visible, waiting {auto_resolve_timeout}s for resolution...")

    wait_interval = 0.5
    elapsed = 0.0

    while elapsed < auto_resolve_timeout:
        await asyncio.sleep(wait_interval)
        elapsed += wait_interval
        result.wait_time_seconds = elapsed

        # Check if challenge resolved
        still_visible = False
        for selector in challenge_selectors:
            try:
                count = await page.locator(selector).count()
                if count > 0:
                    still_visible = True
                    break
            except Exception:
                continue

        if not still_visible:
            result.resolved = True
            result.blocked = False
            result.message = f"reCAPTCHA challenge resolved after {elapsed:.1f}s"
            logger.info(result.message)
            return result

    # Timeout exceeded
    result.blocked = True
    result.should_skip = True
    result.message = f"reCAPTCHA challenge not resolved after {auto_resolve_timeout}s timeout"
    logger.warning(result.message)

    return result


# =============================================================================
# Evidence Capture for reCAPTCHA Detection (Gemini Recommendation #1)
# =============================================================================

def create_recaptcha_evidence(
    detection_result: RecaptchaDetectionResult,
    page_url: str,
    component_id: str = "browser_automation",
) -> dict:
    """
    Create an EvidenceRecord-compatible dict from reCAPTCHA detection results.

    This function captures the full reCAPTCHA detection output for the evidence
    trail, enabling complete audit of automation blocking events.

    Args:
        detection_result: Result from detect_recaptcha()
        page_url: URL where detection occurred
        component_id: Component identifier for evidence trail

    Returns:
        Dictionary compatible with EvidenceRecord fields
    """
    finding = "no_recaptcha_detected"
    severity = "info"

    if detection_result.detected:
        finding = f"recaptcha_detected:{detection_result.version or 'unknown'}"
        if detection_result.automation_impact == "high":
            severity = "critical"
        elif detection_result.automation_impact == "medium":
            severity = "warning"
        else:
            severity = "info"

    return {
        "component_id": component_id,
        "finding": finding,
        "evidence_string": ", ".join(detection_result.indicators) if detection_result.indicators else "none",
        "confidence": "High" if detection_result.detected else "Medium",
        "source": "browser_recaptcha_detection",
        "source_location": page_url,
        "measured_value": detection_result.to_dict(),
        "severity": severity,
        "recommendation": _get_recaptcha_recommendation(detection_result),
    }


def create_blocking_evidence(
    blocking_result: BlockingCheckResult,
    page_url: str,
    component_id: str = "browser_automation",
) -> dict:
    """
    Create an EvidenceRecord-compatible dict from blocking check results.

    This function captures the full blocking check output for the evidence
    trail, enabling complete audit of crawl interruptions.

    Args:
        blocking_result: Result from check_recaptcha_blocking()
        page_url: URL where blocking check occurred
        component_id: Component identifier for evidence trail

    Returns:
        Dictionary compatible with EvidenceRecord fields
    """
    if blocking_result.blocked:
        finding = "crawl_blocked_by_recaptcha"
        severity = "critical"
    elif blocking_result.resolved:
        finding = "recaptcha_challenge_resolved"
        severity = "info"
    elif blocking_result.challenge_visible:
        finding = "recaptcha_challenge_visible"
        severity = "warning"
    else:
        finding = "no_blocking_detected"
        severity = "info"

    return {
        "component_id": component_id,
        "finding": finding,
        "evidence_string": blocking_result.message or "none",
        "confidence": "High",
        "source": "browser_blocking_check",
        "source_location": page_url,
        "measured_value": blocking_result.to_dict(),
        "unit": "seconds" if blocking_result.wait_time_seconds > 0 else None,
        "severity": severity,
        "recommendation": _get_blocking_recommendation(blocking_result),
    }


def _get_recaptcha_recommendation(result: RecaptchaDetectionResult) -> Optional[str]:
    """Get actionable recommendation based on reCAPTCHA detection."""
    if not result.detected:
        return None

    recommendations = {
        "v2_checkbox": "Consider using human simulation or proxy rotation to handle v2 checkbox challenges.",
        "v2_invisible": "Invisible reCAPTCHA may trigger on suspicious behavior. Reduce request rate and use human-like delays.",
        "v3": "reCAPTCHA v3 uses scoring. Ensure human-like interaction patterns to maintain high scores.",
        "enterprise": "Enterprise reCAPTCHA has advanced detection. Consider manual intervention or alternative data sources.",
    }

    base_rec = recommendations.get(result.version, "Monitor for blocking and consider rate limiting.")

    if result.automation_impact == "high":
        return f"{base_rec} HIGH IMPACT: Automated crawling may be blocked."
    elif result.automation_impact == "medium":
        return f"{base_rec} MEDIUM IMPACT: Some pages may require manual verification."

    return base_rec


def _get_blocking_recommendation(result: BlockingCheckResult) -> Optional[str]:
    """Get actionable recommendation based on blocking check."""
    if result.blocked and result.should_skip:
        return (
            "Page skipped due to reCAPTCHA blocking. Options: "
            "1) Run in headed mode for manual solving, "
            "2) Use proxy rotation, "
            "3) Reduce crawl rate, "
            "4) Mark page for manual review."
        )
    elif result.resolved:
        return f"Challenge auto-resolved after {result.wait_time_seconds:.1f}s. No action needed."
    elif result.challenge_visible:
        return "Challenge visible but not blocking. Continue monitoring."

    return None
